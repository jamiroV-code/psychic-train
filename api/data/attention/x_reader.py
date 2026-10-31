"""SPEC rules 17-20, AC41, AC46, AC53-AC55: the X reader seam for the X library, its failures and the pure
decisions around them. Nothing from the library is imported here; the wrapper that does (W8d2) maps the library's
objects and exceptions onto `RawPage`, `PoolRow`, `ReaderFailure` and `x_filters.Tweet`.

- Pin (data only): the library is pinned by its full commit id `TWSCRAPE_PINNED_COMMIT`; the version string is
  no guard. W8d2 installs it in an optional dependency group and checks the installed commit id against this.
- `XReader`: one reader holds ONE account (design A: one accounts file and one API per account), so a unit can
  never span two accounts; failover happens only in `x_pool`.
- `no_account_cause`: a NoAccountError is ambiguous (ban, rate limit, the library's in-flight lock or server
  error), so the cause is read from that account's pool row: inactive is a ban or logout (codes 88, 326, 32 or a
  bare 403); active with a future search lock is a rate limit only with rate-limit evidence from our side (an
  HTTP 429, the code 88 on an active row, `x-rate-limit-remaining` at `RATE_LIMIT_NEAR` or below on that account's
  last page) or a lock longer than an in-flight lock can be; a bare lock without that evidence is the library's
  in-flight lock (taken at queue take for `IN_FLIGHT_LOCK`, left behind by a killed process) and is waited out;
  anything else is a server error.
- `fallback_decision`: the owner-allowed curl backend fallback (rule 19, amended by T179) applies only to an abort
  whose text starts with `Blocked by Cloudflare` or `Blocked by HTML` on the default backend, only with
  `x_allow_curl_backend` true, and only once per UTC day for the whole pool (canary and units together); it never
  applies to a rate limit, a login or ban code, or anything else.
- `parse_drop`: raw timeline entries compared with parsed tweets (the library drops a tweet it cannot parse): a
  page of several entries with none parsed, or a drop rate above the threshold on a page of at least
  `PARSE_DROP_RATE_MIN_ENTRIES` entries, stops X; a drop on a smaller page (`small_page_drop`) counts toward the
  three-failure `layout_changed` streak instead (one dropped tweet of five is no evidence of a layout change).
- `env_problems`: the process environment check, a pure function over a dict of variables.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol, runtime_checkable

from api.data.attention import x_filters, x_window

TWSCRAPE_PACKAGE = "twscrape"
TWSCRAPE_REPO = "https://github.com/vladkens/twscrape"
TWSCRAPE_PINNED_COMMIT = "63f61a518e576ea5c132f1156c03dda0520d76c1"
CURL_CFFI_PIN = "0.16.3"  # the fallback process only; hash-pinned wheel, W8d2
SEARCH_QUEUE = "SearchTimeline"
IN_FLIGHT_LOCK = timedelta(minutes=15)  # the library's in-use lock at queue take (removed on unlock)
IN_FLIGHT_SLACK = timedelta(minutes=1)  # clock skew between the library's stamp and ours
IN_FLIGHT_REASON = "in_flight_lock"
RATE_LIMIT_CODE = 88
RATE_LIMIT_STATUS = 429
RATE_LIMIT_NEAR = 1  # remaining at or below this: the next request reaches 0 (the library hides the 0 itself)
CLOUDFLARE_PREFIX = "Blocked by Cloudflare"
HTML_PREFIX = "Blocked by HTML"
PARSER_VERSION = "x-parse-1"
PAGE_ENTRIES = x_window.PAGE_ENTRIES
PARSE_DROP_MIN_ENTRIES = 2  # "several" raw entries with zero parsed is a layout change
PARSE_DROP_RATE_MIN_ENTRIES = 10  # the drop-rate test needs a page this large
INACTIVE_CODES = {88: "x_account_suspended", 326: "x_account_suspended", 32: "x_login_required"}
FAILURE_KINDS = ("no_account", "abort", "api", "gql_outdated", "xclid_parse", "not_found", "parse")
DRIFT_KINDS = frozenset({"gql_outdated", "xclid_parse", "not_found", "parse"})
_CODE_RE = re.compile(r"\((\d{1,4})\)")
PROXY_VARS = ("TWS_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "tws_proxy", "http_proxy", "https_proxy",
              "all_proxy")
LOG_LEVELS_OK = frozenset({"WARNING", "ERROR", "CRITICAL"})


@dataclass(frozen=True)
class RawPage:
    """One `search_raw` response: the JSON body, the tweet entry ids in it, the rate-limit numbers, retries, and
    the entries' own timestamps when the wrapper can read them without the parser (`entry_times`, may be empty)."""

    body: dict
    entry_ids: tuple[str, ...]
    rate_limit_remaining: int | None = None
    rate_limit_limit: int | None = None
    retries: int = 0  # extra requests the library made for this page (counted as pages)
    entry_times: tuple[datetime, ...] = ()

    def headers(self) -> dict:
        return {"x-rate-limit-remaining": self.rate_limit_remaining, "x-rate-limit-limit": self.rate_limit_limit}


@dataclass(frozen=True)
class PoolRow:
    """What `pool.get(label)` tells about one account: active flag, raw error text, per-queue locks, last use."""

    active: bool
    error_msg: str | None
    locks: dict = field(default_factory=dict)
    last_used: datetime | None = None


class ReaderFailure(Exception):
    """A reader failure by kind. An abort keeps only its classification (`cloudflare`, `html`, `other`), never
    the text, and `str()` is the class and kind only, so nothing from a response reaches a log."""

    def __init__(self, kind: str, *, text: str | None = None, status: int | None = None):
        if kind not in FAILURE_KINDS:
            raise ValueError("unknown failure kind")
        if status is not None and (not isinstance(status, int) or isinstance(status, bool)):
            raise TypeError("status must be an int HTTP status")
        super().__init__()
        self.kind, self.status = kind, status
        self.abort = abort_kind(text) if kind == "abort" else None

    def __str__(self) -> str:
        return f"ReaderFailure {self.kind}" + (f" {self.abort}" if self.abort else "")


@runtime_checkable
class XReader(Protocol):
    label: str
    version: str
    commit: str | None
    overhead_requests: int  # per-process setup requests (transaction-id pages), unmetered by the budget
    account_names: tuple[str, ...]  # the account's real screen name and id, scrubbed from archived pages

    def search_raw(self, query: str, kv: dict, page: int) -> RawPage | None: ...

    def parse_tweets(self, body: dict) -> list[x_filters.Tweet]: ...

    def pool_row(self) -> PoolRow: ...


def abort_kind(text: str | None) -> str:
    """`cloudflare` or `html` by the exact text prefix the library uses; anything else is `other`."""
    if isinstance(text, str) and text.startswith(CLOUDFLARE_PREFIX):
        return "cloudflare"
    if isinstance(text, str) and text.startswith(HTML_PREFIX):
        return "html"
    return "other"


def error_code(msg: str | None) -> int | None:
    m = _CODE_RE.search(msg) if isinstance(msg, str) else None
    return int(m.group(1)) if m else None


def _aware(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return ts.astimezone(timezone.utc)


def near_rate_limit(remaining: int | None) -> bool:
    """A page's `x-rate-limit-remaining` says the account's next request reaches the limit."""
    return remaining is not None and remaining <= RATE_LIMIT_NEAR


def search_lock(row: PoolRow) -> datetime | None:
    lock = (row.locks or {}).get(SEARCH_QUEUE)
    return None if lock is None else _aware(lock)


def no_account_cause(row: PoolRow, now: datetime, *, rate_limit_evidence: bool) -> tuple[str, str]:
    """(cause, reason) for a NoAccountError from the account's pool row.

    inactive: ("inactive", owner alert reason); 32, a bare 403 (no text) or text without a code need a fresh
    login (cookie refresh), 88, 326 and any other code are a suspension. Active with a future search lock:
    ("locked", "rate_limited") with `rate_limit_evidence` from our side, the code 88 on the row, or a lock longer
    than an in-flight lock; else ("waiting", "in_flight_lock"), a lock that ends by itself. Otherwise
    ("server_error", "failed").
    """
    if not row.active:
        code = error_code(row.error_msg)
        if code in INACTIVE_CODES:
            return "inactive", INACTIVE_CODES[code]
        return "inactive", "x_login_required" if row.error_msg is None or code is None else "x_account_suspended"
    lock, now = search_lock(row), _aware(now)
    if lock is None or lock <= now:
        return "server_error", "failed"
    longer = lock > now + IN_FLIGHT_LOCK + IN_FLIGHT_SLACK  # no in-flight lock lasts that long
    if rate_limit_evidence or error_code(row.error_msg) == RATE_LIMIT_CODE or longer:
        return "locked", "rate_limited"
    return "waiting", IN_FLIGHT_REASON


def fallback_decision(kind: str, *, allow_curl: bool, retried: bool) -> str:
    """`curl_retry`, `pause_day` or `not_applicable` (the failure is handled elsewhere, never by the fallback)."""
    if kind in ("cloudflare", "html"):
        return "curl_retry" if allow_curl is True and not retried else "pause_day"
    return "not_applicable"


def parse_drop(*, entries: int, parsed: int, threshold: float) -> bool:
    """True when parsing lost tweets: several entries and none parsed, or a drop rate above the threshold."""
    if entries <= 0:
        return False
    if entries >= PARSE_DROP_MIN_ENTRIES and parsed == 0:
        return True
    return entries >= PARSE_DROP_RATE_MIN_ENTRIES and (entries - parsed) / entries > threshold


def small_page_drop(*, entries: int, parsed: int) -> bool:
    """A page below the rate-test size that lost tweets without tripping `parse_drop`: a drift failure."""
    return parsed < entries < PARSE_DROP_RATE_MIN_ENTRIES and not (parsed == 0 and entries >= PARSE_DROP_MIN_ENTRIES)


def env_problems(env: Mapping[str, str], *, fallback_process: bool = False) -> list[str]:
    """Names of the variables that stop the X process from starting (values are never reported)."""
    bad = []
    if env.get("TWS_TELEMETRY") != "0":
        bad.append("TWS_TELEMETRY")
    if env.get("DO_NOT_TRACK") != "1":
        bad.append("DO_NOT_TRACK")
    if str(env.get("TWS_LOG_LEVEL", "")).upper() not in LOG_LEVELS_OK:
        bad.append("TWS_LOG_LEVEL")
    if env.get("TWS_RAISE_WHEN_NO_ACCOUNT") != "1":
        bad.append("TWS_RAISE_WHEN_NO_ACCOUNT")
    bad += [name for name in PROXY_VARS if env.get(name)]
    backend = env.get("TWS_HTTP_BACKEND")
    if (backend != "curl") if fallback_process else (backend is not None):
        bad.append("TWS_HTTP_BACKEND")
    return bad


def _tweet_json(t: x_filters.Tweet) -> dict:
    u = t.user
    return {"id": t.id, "date": t.date.isoformat(), "text": t.text, "lang": t.lang, "cashtags": list(t.cashtags),
            "retweeted_id": t.retweeted_id, "reply_to_id": t.reply_to_id, "like": t.like, "reply": t.reply,
            "quote": t.quote, "retweet": t.retweet, "views": t.views,
            "user": {"id": u.id, "created": u.created.isoformat(), "followers": u.followers, "statuses": u.statuses,
                     "profile_image_url": u.profile_image_url, "protected": u.protected}}


def _tweet_from_json(d: dict) -> x_filters.Tweet:
    u = d["user"]
    user = x_filters.XUser(u["id"], datetime.fromisoformat(u["created"]), u["followers"], u["statuses"],
                           u["profile_image_url"], u["protected"])
    return x_filters.Tweet(d["id"], datetime.fromisoformat(d["date"]), d["text"], user, d["lang"],
                           tuple(d["cashtags"]), d["retweeted_id"], d["reply_to_id"], d["like"], d["reply"],
                           d["quote"], d["retweet"], d["views"])


@dataclass
class FakeXReader:
    """Scripted raw pages for tests: each `search_raw` returns the next item or raises it when it is a failure.

    Its pages hold tweets as JSON entries; an entry marked `broken` is skipped by `parse_tweets`, like the library
    skipping a tweet it cannot parse. An empty script is a parse failure (fail closed).
    """

    label: str
    items: list = field(default_factory=list)
    row: PoolRow = field(default_factory=lambda: PoolRow(True, None))
    version: str = "fake-1"
    commit: str | None = None
    overhead_requests: int = 0
    account_names: tuple[str, ...] = ()
    calls: list = field(default_factory=list)

    @staticmethod
    def entry(t: x_filters.Tweet, broken: bool = False) -> dict:
        return {"entryId": f"tweet-{t.id}", "tweet": _tweet_json(t), "broken": broken}

    @classmethod
    def page_of(cls, tweets, *, broken: int = 0, retries: int = 0, remaining: int | None = 40) -> RawPage:
        """A raw page of `tweets`; the last `broken` of them cannot be parsed."""
        n = len(tweets)
        entries = [cls.entry(t, broken=i >= n - broken) for i, t in enumerate(tweets)]
        return RawPage({"entries": entries}, tuple(e["entryId"] for e in entries), remaining, 50, retries,
                       tuple(t.date for t in tweets))

    def search_raw(self, query: str, kv: dict, page: int) -> RawPage | None:
        self.calls.append((query, dict(kv), page))
        if not self.items:
            raise ReaderFailure("parse")
        item = self.items.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    def parse_tweets(self, body: dict) -> list[x_filters.Tweet]:
        return [_tweet_from_json(e["tweet"]) for e in body.get("entries", []) if not e.get("broken")]

    def pool_row(self) -> PoolRow:
        return self.row


def canary_ids(tweets, start: datetime, end: datetime) -> set[int]:
    """Ids of the parsed canary tweets inside [start, end)."""
    return {t.id for t in tweets if start <= _aware(t.date) < end}
