"""SPEC rules 17-20, AC41, AC46, AC47, AC52, AC53, AC55 (W8d2): the twscrape wrapper behind the W8d1 `XReader`.

The library is imported lazily, inside `load_library` only, and only after the environment guard passed; nothing
at module level touches the network. The pure decisions (reason mapping, pool, canary, fallback decision, parse
drop, raw archive) stay in `x_reader`, `x_pool` and `x_raw`; this module maps the library onto them.

- Design A: ONE accounts file and ONE `API` per account (`<x_accounts_db_path>/<label>.db`), built with
  `raise_when_no_account=True, wait_timeout=0` and nothing else (never `debug`, never a proxy, never a user agent).
  A unit therefore never spans two accounts; failover is `x_pool`'s.
- Start (`start`) refuses with reason codes, never values: the environment guard (`x_reader.env_problems`), the
  configured pin equal to the code pin, the installed package's `direct_url.json` commit id equal to the pinned
  full SHA (the version string 0.20.1 is no guard), the accounts directory (absolute, outside the repository,
  owner-only permissions on POSIX; on Windows the ACL is not checked and the health line says so) and the pool
  size and labels. Start cleans the library's `/tmp/twscrape*` dumps; `service_env` gives the X process a private
  temporary directory.
- Reads: `search_raw` pages one at a time (the library skips empty pages and retries on its own; both show as a
  drop of `x-rate-limit-remaining` larger than one between two pages of one account and are counted as
  `retries`); the entries' times come from the tweet ids (snowflakes), so dropped entries keep their time. A
  failure keeps only its class (`map_exception`), never the message.
- Curl fallback (rule 19): only when `x_allow_curl_backend` is true and the installed `curl_cffi` is verified
  (exact name, 0.16.3, the wheel tag of the detected platform, and the install record's hash equal to the table
  entry, which equals the hash `uv.lock` makes uv check at install). The retry runs in a SEPARATE process
  (`python -m api.data.attention.twscrape_reader --curl-fallback`) whose environment alone has
  `TWS_HTTP_BACKEND=curl`; it reads one page from the cursor the default backend stopped at.

Owner procedures (exact commands in the W8d2 report):
- Install on the 24/7 host: `uv sync --project api --frozen --group xreader`, then
  `uv run --project api --frozen python -m api.data.attention.twscrape_reader --write-curl-record`.
- Cookie refresh is the library's upsert `pool.add_account_cookies(label, cookies)` on that account's own file:
  put the cookie string in the environment variable `X_REFRESH_COOKIES` (never on the command line) and run
  `python -m api.data.attention.twscrape_reader --refresh-cookies <label>`; it records the refresh time for the
  cookie age in the health line and sets the file to owner-only on POSIX. Then remove the variable.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import stat
import sys
import tomllib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from api.data import cache
from api.data.attention import x_filters, x_pool
from api.data.attention import x_reader as xr
from api.data.attention.web_queries import CollectorConfig

REPO_ROOT = Path(__file__).resolve().parents[3]
LOCK_PATH = REPO_ROOT / "api" / "uv.lock"
GROUP = "xreader"
PINNED_COMMIT = xr.TWSCRAPE_PINNED_COMMIT
REQUIREMENT = f"{xr.TWSCRAPE_PACKAGE} @ git+{xr.TWSCRAPE_REPO}@{PINNED_COMMIT}"
# twscrape's own dependencies, exact (W8a2 report 9.1); shared packages keep the main lock's versions.
GROUP_PINS = {"aiosqlite": "0.22.1", "beautifulsoup4": "4.15.0", "soupsieve": "3.0.3", "fake-useragent": "2.2.0",
              "loguru": "0.7.3", "py-machineid": "1.0.0", "pyotp": "2.10.0", "curl-cffi": xr.CURL_CFFI_PIN}
CURL_VERSION = xr.CURL_CFFI_PIN
# The wheels the fallback may run on (W8a2 report 9.2, re-read from PyPI by W8d2); also in uv.lock.
CURL_WHEELS = {
    "win_amd64": ("curl_cffi-0.16.3-cp310-abi3-win_amd64.whl",
                  "fe87b66e324ed7318166698e02169f3208dbda32b872a27d2bc61a9c19b335eb"),
    "manylinux_x86_64": ("curl_cffi-0.16.3-cp310-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl",
                         "a875a661e2f9a949be29454880bbb9553307a487c4c08819738298cf5c1622e2"),
    "musllinux_x86_64": ("curl_cffi-0.16.3-cp310-abi3-musllinux_1_2_x86_64.whl",
                         "20a7b1b473371cfaf2118958034977e457c6fa279fbd11543c9e0ab58be9eedd"),
}
CURL_WHEEL_TAGS = {"win_amd64": "cp310-abi3-win_amd64", "manylinux_x86_64": "cp310-abi3-manylinux2014_x86_64",
                   "musllinux_x86_64": "cp310-abi3-musllinux_1_2_x86_64"}
CURL_SDIST_SHA = "d15d0c2a35f2d75bec430c28946c2a833f421c85773bdb0795182cc5c515665b"  # never built
CURL_RECORD = "x_curl_install.json"
# Split strings: the banned malware names never appear whole in this repository.
BANNED = ("x" + "scrape", "klox" + "eld", "gunk" + "onchi")
REQUIRED_ENV = {"TWS_TELEMETRY": "0", "DO_NOT_TRACK": "1", "TWS_LOG_LEVEL": "WARNING", "TWS_RAISE_WHEN_NO_ACCOUNT": "1"}
TMP_VARS = ("TMPDIR", "TEMP", "TMP")
DUMP_GLOB = "twscrape*"
LIBRARY_DUMP_ROOT = Path("/tmp")  # the library writes its dumps there by a literal path
XCLID_404_PREFIX = "Failed to get XClIdGen"
SETUP_REQUESTS_ESTIMATE = 3  # transaction-id setup per process and account (x.com page, migrate, JS bundle); estimate
COOKIE_AGES = "cookie_ages.json"
_SNOWFLAKE_EPOCH_MS = 1288834974657
_STATUS_RE = re.compile(r"^Blocked by \w+: (\d{3})\b")
_GIT_REQ_RE = re.compile(r"^twscrape @ git\+(?P<url>\S+)@(?P<ref>\S+)$")
_PIN_REQ_RE = re.compile(r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)==(?P<ver>[0-9]+(\.[0-9]+)*)$")
_LOADED: dict = {}  # the loaded library, once per process


class XStartRefused(Exception):
    """X does not start; `reasons` are codes (variable names, check names), never values."""

    def __init__(self, reasons: list[str]):
        super().__init__()
        self.reasons = list(reasons)

    def __str__(self) -> str:
        return "XStartRefused " + ",".join(self.reasons)


class CurlUnavailable(Exception):
    def __init__(self, reason: str):
        super().__init__()
        self.reason = reason

    def __str__(self) -> str:
        return f"CurlUnavailable {self.reason}"


class RefreshFailed(Exception):
    def __init__(self, cls: str):
        super().__init__()
        self.cls = cls

    def __str__(self) -> str:
        return f"RefreshFailed {self.cls}"


# --- names, pins, identity ----------------------------------------------------------------------------------------

def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.strip()).lower()


def req_name(spec: str) -> str:
    m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", spec)
    return _norm(m.group(1)) if m else ""


def _distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def name_problem(name: str, expected: str) -> str | None:
    """None for the exact (normalised) name; `banned`, `near_name` or `unknown` otherwise."""
    n, e = _norm(name), _norm(expected)
    flat, flat_e = n.replace("-", ""), e.replace("-", "")
    if any(b in flat for b in BANNED):
        return "banned"
    if n == e:
        return None
    if flat == flat_e or flat_e in flat or _distance(flat, flat_e) <= 2:
        return "near_name"
    return "unknown"


def requirement_problems(reqs: Iterable[str]) -> list[str]:
    """`<name>:<problem>` for the optional group: twscrape only from the vladkens URL at the full pinned SHA, the
    other packages exactly at their pins; any other name is refused (banned, near-name or unknown)."""
    problems, seen = [], set()
    for spec in reqs:
        name = req_name(spec)
        if name == "twscrape":
            m = _GIT_REQ_RE.match(spec.strip())
            ok = m and m.group("url") == xr.TWSCRAPE_REPO and m.group("ref") == PINNED_COMMIT
            if not ok:
                problems.append("twscrape:short_or_other_sha")
            seen.add(name)
            continue
        if name in GROUP_PINS:
            m = _PIN_REQ_RE.match(spec.strip())
            if not m or m.group("ver") != GROUP_PINS[name]:
                problems.append(f"{name}:not_exact_pin")
            seen.add(name)
            continue
        expected = min(["twscrape", *GROUP_PINS], key=lambda e: _distance(name.replace("-", ""), e.replace("-", "")))
        problems.append(f"{name}:{name_problem(name, expected)}")
    problems += [f"{n}:missing" for n in ["twscrape", *GROUP_PINS] if n not in seen]
    return sorted(problems)


@dataclass(frozen=True)
class DistInfo:
    """What the installed distribution says about itself (no import of the package)."""

    name: str
    version: str
    direct_url: str | None
    wheel: str | None


def find_dist(name: str) -> DistInfo | None:
    from importlib import metadata

    try:
        d = metadata.distribution(name)
    except metadata.PackageNotFoundError:
        return None
    return DistInfo(d.metadata["Name"], d.version, d.read_text("direct_url.json"), d.read_text("WHEEL"))


def identity_problem(dist: DistInfo | None, pinned: str) -> str | None:
    """None when the installed twscrape came from the vladkens repository at exactly `pinned`."""
    if dist is None:
        return "not_installed"
    if name_problem(dist.name, xr.TWSCRAPE_PACKAGE) is not None:
        return "name_mismatch"
    try:
        direct = json.loads(dist.direct_url or "")
        vcs = direct["vcs_info"]
        ok = (vcs.get("vcs") == "git" and direct.get("url") in (xr.TWSCRAPE_REPO, xr.TWSCRAPE_REPO + ".git")
              and vcs.get("commit_id") == pinned and re.fullmatch(r"[0-9a-f]{40}", pinned or ""))
    except (ValueError, KeyError, TypeError, AttributeError):
        ok = False
    return None if ok else "commit_mismatch"


# --- curl_cffi: platform, lock, install record --------------------------------------------------------------------

def platform_key(sys_platform: str | None = None, machine: str | None = None, libc: str | None = None, *,
                 free_threaded: bool | None = None) -> str | None:
    """The `CURL_WHEELS` key for this interpreter, or None (unknown platform or architecture: no fallback)."""
    if sys_platform is None:
        import platform
        import sysconfig

        sys_platform, machine = sys.platform, platform.machine()
        libc = platform.libc_ver()[0] or ("musl" if Path("/lib/ld-musl-x86_64.so.1").exists() else "")
        free_threaded = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
    if free_threaded:
        return None  # the abi3 wheel does not serve a free-threaded interpreter
    arch = (machine or "").lower()
    if sys_platform == "win32" and arch in ("amd64", "x86_64"):
        return "win_amd64"
    if sys_platform.startswith("linux") and arch == "x86_64":
        return {"glibc": "manylinux_x86_64", "musl": "musllinux_x86_64"}.get(libc or "")
    return None


def lock_text() -> str:
    return LOCK_PATH.read_text(encoding="utf-8")


def lock_curl_hashes(text: str) -> dict[str, str]:
    """Wheel file name -> `sha256:<hex>` for curl-cffi at the pinned version in `uv.lock`."""
    for pkg in tomllib.loads(text).get("package", []):
        if pkg.get("name") == "curl-cffi" and pkg.get("version") == CURL_VERSION:
            return {w["url"].rsplit("/", 1)[1]: w["hash"] for w in pkg.get("wheels", [])}
    return {}


def install_record(key: str | None, text: str) -> dict:
    """The record of the wheel this platform installs; refused unless `uv.lock` holds the table's hash for it."""
    if key not in CURL_WHEELS:
        raise CurlUnavailable("unknown_platform")
    wheel, sha = CURL_WHEELS[key]
    if lock_curl_hashes(text).get(wheel) != "sha256:" + sha:
        raise CurlUnavailable("lock_hash_mismatch")
    return {"package": "curl_cffi", "version": CURL_VERSION, "platform": key, "wheel": wheel, "sha256": sha}


def record_path() -> Path:
    return cache.CACHE_ROOT / "attention" / "_pc_state" / CURL_RECORD


def write_install_record(rec: dict) -> None:
    record_path().parent.mkdir(parents=True, exist_ok=True)
    cache._atomic_write_json(rec, record_path())


def read_install_record() -> dict | None:
    try:
        rec = json.loads(record_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return rec if isinstance(rec, dict) else None


def curl_status(record: dict | None, key: str | None, dist: DistInfo | None) -> str:
    """`ok`, or why the fallback is off; checked at start and shown in the health line."""
    if key not in CURL_WHEELS:
        return "unknown_platform"
    if dist is None:
        return "not_installed"
    if name_problem(dist.name, "curl-cffi") is not None:
        return "name_mismatch"
    if dist.version != CURL_VERSION:
        return "version_mismatch"
    tags = {ln.split(":", 1)[1].strip() for ln in (dist.wheel or "").splitlines() if ln.startswith("Tag:")}
    if not record:
        return "record_missing"
    if record.get("platform") != key:
        return "record_platform_mismatch"
    if CURL_WHEEL_TAGS[key] not in tags:
        return "wheel_tag_mismatch"
    wheel, sha = CURL_WHEELS[key]
    if record.get("sha256") != sha or record.get("wheel") != wheel or record.get("version") != CURL_VERSION:
        return "hash_mismatch"
    return "ok"


# --- environment, temporary files, accounts directory ------------------------------------------------------------

def env_guard(env: Mapping[str, str], *, fallback: bool = False) -> list[str]:
    return xr.env_problems(env, fallback_process=fallback)


def service_env(base: Mapping[str, str], *, private_tmp: Path, fallback: bool = False) -> dict:
    """The X process environment: the required switches, no proxy, a private temporary directory, and
    `TWS_HTTP_BACKEND=curl` only for the fallback child."""
    proxies = {v.upper() for v in xr.PROXY_VARS}
    env = {k: v for k, v in base.items() if k.upper() not in proxies and k.upper() != "TWS_HTTP_BACKEND"}
    env.update(REQUIRED_ENV)
    env.update(dict.fromkeys(TMP_VARS, str(private_tmp)))
    if fallback:
        env["TWS_HTTP_BACKEND"] = "curl"
    return env


def private_tmp() -> Path:
    return cache.CACHE_ROOT / "attention" / "_x_tmp"


def clean_dumps(roots: Iterable[Path]) -> int:
    """Delete the library's dumps (`twscrape*`: parse errors with raw tweet JSON, debug dumps) under `roots`."""
    removed = 0
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for p in root.glob(DUMP_GLOB):
            if p.is_dir() and not p.is_symlink():
                shutil.rmtree(p)
            else:
                p.unlink()
            removed += 1
    return removed


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def permission_note(*, posix: bool = os.name == "posix") -> str | None:
    return None if posix else "windows_acl_not_checked"


def accounts_problems(config: CollectorConfig, *, repo_root: Path = REPO_ROOT, posix: bool = os.name == "posix",
                      stat_fn: Callable = os.stat, uid: int | None = None) -> list[str]:
    """Codes for what stops X at start: path, pool size, account files, permissions (owner-only on POSIX)."""
    raw = config.x_accounts_db_path
    if not raw:
        return ["accounts_path_unset"]
    d = Path(raw)
    if not d.is_absolute():
        return ["accounts_path_not_absolute"]
    if _inside(d, repo_root):
        return ["accounts_path_in_repo"]
    if not d.is_dir():
        return ["accounts_path_missing"]
    labels = list(config.x_accounts)
    if not 1 <= len(labels) <= config.x_pool_max:
        return ["pool_size"]
    files = {p.stem for p in d.glob("*.db")}
    if files - set(labels):
        return ["unknown_account_file"]
    if set(labels) - files:
        return ["missing_account_file"]
    if posix:
        me = os.getuid() if uid is None else uid
        for p in [d] + [d / f"{x}.db" for x in labels]:
            st = stat_fn(p)
            if stat.S_IMODE(st.st_mode) & 0o077 or st.st_uid != me:
                return ["permissions"]
    return []


def _ages_path(config: CollectorConfig) -> Path:
    return Path(config.x_accounts_db_path) / COOKIE_AGES


def cookie_ages(config: CollectorConfig, *, now: datetime) -> dict[str, int | None]:
    """Whole days since each account's last cookie refresh (None: never refreshed through `refresh_cookies`)."""
    try:
        seen = json.loads(_ages_path(config).read_text(encoding="utf-8")) if config.x_accounts_db_path else {}
    except (OSError, ValueError):
        seen = {}
    out = {}
    for label in config.x_accounts:
        try:
            out[label] = (now - datetime.fromisoformat(seen[label])).days
        except (KeyError, TypeError, ValueError):
            out[label] = None
    return out


# --- the library --------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Library:
    API: Callable
    parse_tweets: Callable
    NoAccountError: type
    AbortReqError: type
    ApiError: type
    GqlFeaturesOutdatedError: type
    XClIdParseError: type


def load_library() -> Library:
    """Import the wrapped surface of twscrape (call only after `env_guard` passed)."""
    import twscrape
    from twscrape.models import parse_tweets

    lib = Library(twscrape.API, parse_tweets, twscrape.NoAccountError, twscrape.AbortReqError, twscrape.ApiError,
                  twscrape.GqlFeaturesOutdatedError, twscrape.XClIdParseError)
    _LOADED["twscrape"] = lib
    return lib


def map_exception(exc: BaseException, lib: Library) -> xr.ReaderFailure:
    """The W8d1 failure kind of a library exception; the message is read for its prefix only and dropped."""
    if isinstance(exc, xr.ReaderFailure):
        return exc
    if isinstance(exc, lib.NoAccountError):
        return xr.ReaderFailure("no_account")
    if isinstance(exc, lib.GqlFeaturesOutdatedError):
        return xr.ReaderFailure("gql_outdated")
    if isinstance(exc, lib.XClIdParseError):
        return xr.ReaderFailure("xclid_parse")
    if isinstance(exc, lib.ApiError):
        return xr.ReaderFailure("api")
    if isinstance(exc, lib.AbortReqError):
        text = str(exc)
        if text.startswith(XCLID_404_PREFIX):
            return xr.ReaderFailure("not_found")
        m = _STATUS_RE.match(text)
        return xr.ReaderFailure("abort", text=text, status=int(m.group(1)) if m else None)
    return xr.ReaderFailure("api")


def timeline_entry_ids(body) -> tuple[str, ...]:
    """The `tweet-<id>` timeline entry ids of a raw page, in order (cursors and modules are not tweets)."""
    out: list[str] = []

    def walk(v):
        if isinstance(v, dict):
            e = v.get("entryId")
            if isinstance(e, str) and e.startswith("tweet-") and e not in out:
                out.append(e)
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(body)
    return tuple(out)


def bottom_cursor(body) -> str | None:
    found: list[str] = []

    def walk(v):
        if isinstance(v, dict):
            if v.get("cursorType") == "Bottom" and isinstance(v.get("value"), str):
                found.append(v["value"])
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(body)
    return found[-1] if found else None


def entry_time(entry_id: str) -> datetime | None:
    """The timestamp in a tweet id (snowflake), so an entry the parser dropped still has its time; whole seconds,
    like the tweet's own `created_at` (checked against the library's mocked search page: 20 of 20 equal)."""
    tail = entry_id.split("-", 1)[-1]
    if not tail.isdigit():
        return None
    ms = (int(tail) >> 22) + _SNOWFLAKE_EPOCH_MS
    return datetime.fromtimestamp(ms // 1000, tz=UTC)


def _int(v) -> int | None:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _aware(ts):
    if isinstance(ts, datetime) and ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts


def _count(value) -> int | None:
    """A library count as int; a missing count stays None (never read as 0)."""
    return None if value is None else int(value)


def to_tweet(t) -> x_filters.Tweet:
    u = t.user
    user = x_filters.XUser(int(u.id), _aware(u.created), _count(u.followersCount), _count(u.statusesCount),
                           u.profileImageUrl or "", bool(u.protected))
    rt = getattr(t, "retweetedTweet", None)
    return x_filters.Tweet(int(t.id), _aware(t.date), t.rawContent or "", user, t.lang or "", tuple(t.cashtags or ()),
                           int(rt.id) if rt is not None else None, t.inReplyToTweetId, _count(t.likeCount),
                           _count(t.replyCount), _count(t.quoteCount), _count(t.retweetCount), t.viewCount)


def window_query(terms: str, *, start: datetime, end: datetime, lang: str) -> str:
    """The query for an explicit [start, end) window in epoch seconds (the form X honours, P-X9); a later
    slice can read sub-day slices with it unchanged."""
    if start.tzinfo is None or end.tzinfo is None or not start < end:
        raise ValueError("window must be timezone-aware with start before end")
    window = f"since_time:{int(start.timestamp())} until_time:{int(end.timestamp())}"
    return " ".join([terms] + ([f"lang:{lang}"] if lang else []) + ["-filter:replies -filter:retweets", window])


class TwscrapeReader:
    """One account: its own accounts file and its own `API`. Implements `x_reader.XReader`."""

    def __init__(self, label: str, db_path: Path, lib: Library, *, max_entries: int, version: str = "unknown",
                 commit: str | None = PINNED_COMMIT, account_names: tuple[str, ...] = ()):
        import asyncio

        self.label, self.version, self.commit = label, f"twscrape {version}", commit
        self.overhead_requests = 0
        self.account_names = tuple(account_names)
        self.max_entries = max_entries
        self._lib = lib
        self._api = lib.API(str(db_path), raise_when_no_account=True, wait_timeout=0)
        self._loop = asyncio.new_event_loop()
        self._gen = None
        self._query: str | None = None
        self._kv: dict = {}
        self._page = -1
        self._read = 0
        self.cursor: str | None = None
        self._remaining: int | None = None

    def _run(self, coro):
        return self._loop.run_until_complete(coro)

    def _close_gen(self) -> None:
        gen, self._gen = self._gen, None
        if gen is not None:
            with contextlib.suppress(Exception):  # closing a failed generator; nothing to report
                self._run(gen.aclose())

    def search_raw(self, query: str, kv: dict, page: int) -> xr.RawPage | None:
        if page == 0:
            self._close_gen()
            self._query, self._kv, self._read, self.cursor, self._remaining = query, dict(kv), 0, None, None
        elif query != self._query or page != self._page + 1:
            raise ValueError("pages of one query are read in order")
        self._page = page
        if self._gen is None:
            start_kv = {**self._kv, **({"cursor": self.cursor} if self.cursor else {})}
            self._gen = self._api.search_raw(query, limit=max(1, self.max_entries - self._read), kv=start_kv)
        try:
            rep = self._run(self._gen.__anext__())
        except StopAsyncIteration:
            self._close_gen()
            return None
        except Exception as exc:  # noqa: BLE001 - every library failure maps to a kind; the message is dropped
            self._close_gen()
            failure = map_exception(exc, self._lib)
        else:
            failure = None
        if failure is not None:
            raise failure
        if not self.overhead_requests:
            self.overhead_requests = SETUP_REQUESTS_ESTIMATE
        try:
            body = rep.json()
        except Exception:  # noqa: BLE001 - an unreadable page is a parse failure
            body = None
        if not isinstance(body, dict):
            raise xr.ReaderFailure("parse")
        return self.page_from(body, rep.headers)

    def resume(self, query: str, kv: dict, cursor: str | None) -> xr.RawPage | None:
        """The fallback child's single page: the first page of `query`, or the page after `cursor`."""
        if not cursor:
            return self.search_raw(query, kv, 0)
        self._close_gen()
        self._query, self._kv, self._page, self._read, self.cursor = query, dict(kv), 0, 0, cursor
        return self.search_raw(query, kv, 1)

    def page_from(self, body: dict, headers: Mapping) -> xr.RawPage:
        """A `RawPage` from a response body and its headers; advances this reader's cursor."""
        h = {str(k).lower(): v for k, v in (headers or {}).items()}
        remaining, limit = _int(h.get("x-rate-limit-remaining")), _int(h.get("x-rate-limit-limit"))
        retries = 0
        if self._remaining is not None and remaining is not None and remaining < self._remaining:
            retries = self._remaining - remaining - 1
        self._remaining = remaining
        ids = timeline_entry_ids(body)
        self._read += len(ids)
        self.cursor = bottom_cursor(body)
        times = tuple(t for t in (entry_time(i) for i in ids) if t is not None)
        return xr.RawPage(body, ids, remaining, limit, retries, times)

    def adopt(self, body: dict, headers: Mapping) -> xr.RawPage:
        """A page the fallback child read for this account: the next default-backend page continues after it."""
        self._close_gen()
        self._remaining = None
        return self.page_from(body, headers)

    def parse_tweets(self, body: dict) -> list[x_filters.Tweet]:
        try:
            return [to_tweet(t) for t in self._lib.parse_tweets(body, -1)]
        except Exception:  # noqa: BLE001 - whatever the parser raised, it is a parse failure
            raise xr.ReaderFailure("parse") from None

    def pool_row(self) -> xr.PoolRow:
        try:
            acc = self._run(self._api.pool.get(self.label))
        except ValueError:
            return xr.PoolRow(False, None)  # no row: the account needs a cookie refresh
        except Exception:  # noqa: BLE001 - an unreadable row is a server-side failure
            return xr.PoolRow(True, "unreadable")
        locks = {k: _aware(v) for k, v in (acc.locks or {}).items()}
        return xr.PoolRow(bool(acc.active), acc.error_msg, locks, _aware(acc.last_used))

    def close(self) -> None:
        self._close_gen()
        self._loop.close()


# --- the curl fallback child --------------------------------------------------------------------------------------

def fallback_request(label: str, db: Path, query: str, kv: Mapping, *, cursor: str | None) -> dict:
    """What the child is told: the account, its file, the query and the search variables (no other options)."""
    if set(kv) - {"product"}:
        raise ValueError("only the search product may be passed to the fallback")
    return {"label": label, "db": str(db), "query": query,
            "kv": {**kv, **({"cursor": cursor} if cursor else {})}}


def child_reply_for(failure: xr.ReaderFailure) -> dict:
    return {"status": "fail", "kind": failure.kind, "abort": failure.abort}


def run_child(request: dict, env: Mapping[str, str], *, timeout: float = 180) -> dict:
    """Run the fallback child (`--curl-fallback`) with `env`; its reply, or a failure reply."""
    import subprocess

    try:
        done = subprocess.run([sys.executable, "-m", __name__, "--curl-fallback"], input=json.dumps(request),
                              capture_output=True, text=True, env=dict(env), cwd=str(REPO_ROOT), timeout=timeout,
                              check=False)
        reply = json.loads(done.stdout.strip().splitlines()[-1]) if done.stdout.strip() else {}
    except (OSError, ValueError, subprocess.SubprocessError):
        reply = {}
    return reply if isinstance(reply, dict) and reply.get("status") else {"status": "fail", "kind": "api"}


@dataclass
class CurlFallback:
    """`x_pool.Fallback`: one retry of a blocked page in the curl child; the pool decides when (once a UTC day)."""

    readers: Mapping[str, TwscrapeReader]
    accounts_dir: Path
    env: Mapping[str, str]
    run: Callable[[dict, Mapping[str, str]], dict] = run_child

    def __call__(self, label: str, query: str, kv: dict, page: int) -> xr.RawPage | None:
        reader = self.readers[label]
        req = fallback_request(label, self.accounts_dir / f"{label}.db", query, kv,
                               cursor=reader.cursor if page else None)
        reply = self.run(req, service_env(self.env, private_tmp=private_tmp(), fallback=True))
        status = reply.get("status")
        if status == "ok" and isinstance(reply.get("body"), dict):
            return reader.adopt(reply["body"], {"x-rate-limit-remaining": reply.get("remaining"),
                                                "x-rate-limit-limit": reply.get("limit")})
        if status == "empty":
            return None
        kind = reply.get("kind") if reply.get("kind") in xr.FAILURE_KINDS else "api"
        text = {"cloudflare": xr.CLOUDFLARE_PREFIX, "html": xr.HTML_PREFIX}.get(reply.get("abort"))
        raise xr.ReaderFailure(kind, text=text)


# --- start, health, cookie refresh --------------------------------------------------------------------------------

@dataclass
class XStart:
    readers: dict[str, TwscrapeReader]
    fallback: CurlFallback | None
    curl_status: str
    notes: list[str] = field(default_factory=list)

    def close(self) -> None:
        for r in self.readers.values():
            r.close()


def _curl(config: CollectorConfig, platform: str | None, dist_lookup, record: dict | None) -> str:
    if not config.x_allow_curl_backend:
        return "flag_false"
    return curl_status(record, platform, dist_lookup("curl_cffi"))


def start(config: CollectorConfig, *, env: Mapping[str, str] = os.environ, repo_root: Path = REPO_ROOT,
          dist_lookup: Callable[[str], DistInfo | None] = find_dist, load: Callable[[], Library] = load_library,
          platform: str | None = None, dump_roots: Iterable[Path] | None = None, curl_record: dict | None = None,
          run_child: Callable = run_child, account_names: Mapping[str, tuple[str, ...]] | None = None) -> XStart:
    """One reader per configured account, or `XStartRefused` with every reason (nothing imported before the
    environment passed; no library call is made here other than building each account's `API`)."""
    bad = env_guard(env)
    reasons = [f"env:{name}" for name in bad]
    if config.x_pinned_commit != PINNED_COMMIT:
        reasons.append("pin_mismatch")
    dist = dist_lookup("twscrape")
    ident = identity_problem(dist, PINNED_COMMIT)
    if ident:
        reasons.append(ident)
    reasons += accounts_problems(config, repo_root=repo_root)
    if reasons:
        raise XStartRefused(reasons)
    clean_dumps([LIBRARY_DUMP_ROOT, private_tmp()] if dump_roots is None else dump_roots)
    lib = load()
    d = Path(config.x_accounts_db_path)
    names = account_names or {}
    readers = {x: TwscrapeReader(x, d / f"{x}.db", lib, max_entries=config.x_page_cap * xr.PAGE_ENTRIES,
                                 version=dist.version, account_names=tuple(names.get(x, ())))
               for x in config.x_accounts}
    record = curl_record if curl_record is not None else read_install_record()
    curl = _curl(config, platform, dist_lookup, record)
    notes = [n for n in (permission_note(),) if n]
    fallback = None
    if curl == "ok":
        fallback = CurlFallback(readers, d, env, run_child)
    else:
        notes.append(f"curl_fallback_off:{curl}")
    return XStart(readers, fallback, curl, notes)


def reader_status(config: CollectorConfig, *, env: Mapping[str, str], now: datetime,
                  dist_lookup: Callable[[str], DistInfo | None] = find_dist, platform: str | None = None,
                  curl_record: dict | None = None, repo_root: Path = REPO_ROOT) -> dict:
    """The X reader's health: counts, labels, states and check results only, never a secret, path or value."""
    bad = env_guard(env)
    paths = accounts_problems(config, repo_root=repo_root)
    labels = list(config.x_accounts)
    ages = cookie_ages(config, now=now) if labels else {}
    if labels:
        pool = x_pool.XPool(labels, clock=lambda: now).health()
        accts = [{"label": a["label"], "state": a["state"], "reason": a["reason"], "last_used": a["last_used"],
                  "cookie_age_days": ages.get(a["label"])} for a in pool["accounts"]]
    else:
        pool, accts = {"active": 0, "curl_uses": 0, "curl_last_use": None, "canary_note": None}, []
    return {"active": pool["active"], "total": len(labels), "accounts": accts,
            "installed": dist_lookup("twscrape") is not None,
            "commit_match": identity_problem(dist_lookup("twscrape"), PINNED_COMMIT) is None
            and config.x_pinned_commit == PINNED_COMMIT,
            "env_ok": not bad, "env_bad": bad, "accounts_path": ",".join(paths) or "ok",
            "permissions": permission_note() or "checked",
            "curl_fallback": _curl(config, platform, dist_lookup, curl_record),
            "curl_uses": pool["curl_uses"], "curl_last_use": pool["curl_last_use"],
            "canary_note": pool["canary_note"]}


_WORD = re.compile(r"[a-z0-9_:,.+-]{1,80}")


def _word(v) -> str:
    if v is None:
        return "none"
    if isinstance(v, bool):
        return "true" if v else "false"
    s = str(v)
    return s if _WORD.fullmatch(s) else "redacted"


def status_lines(h: dict) -> list[str]:
    """`reader_status` as probe lines; every value is a number, a known code, a label or an ISO time."""
    lines = [(f"xreader accounts_active={h['active']} accounts_total={h['total']}"
              f" commit_match={_word(h['commit_match'])}"
              f" env_ok={_word(h['env_ok'])} env_bad={_word(','.join(h['env_bad']) or None)}"
              f" installed={_word(h['installed'])} accounts_path={_word(h['accounts_path'])}"
              f" permissions={_word(h['permissions'])} curl_fallback={_word(h['curl_fallback'])}"
              f" curl_uses={h['curl_uses']} curl_last_use={_word(h['curl_last_use'])}")]
    for a in h["accounts"]:
        lines.append(f"account label={_word(a['label'])} state={_word(a['state'])} reason={_word(a['reason'])}"
                     f" last_used={_word(a['last_used'])} cookie_age_days={_word(a['cookie_age_days'])}")
    return lines


def refresh_cookies(label: str, cookies: str, *, config: CollectorConfig, env: Mapping[str, str] = os.environ,
                    now: datetime, repo_root: Path = REPO_ROOT, load: Callable[[], Library] = load_library) -> None:
    """The cookie upsert `pool.add_account_cookies(label, cookies)` on that account's own file."""
    import asyncio

    if label not in config.x_accounts:
        raise ValueError("label is not configured")
    bad = env_guard(env)
    problems = [f"env:{name}" for name in bad]
    problems += [p for p in accounts_problems(config, repo_root=repo_root) if p != "missing_account_file"]
    if problems:
        raise XStartRefused(problems)
    path = Path(config.x_accounts_db_path) / f"{label}.db"
    try:
        api = load().API(str(path), raise_when_no_account=True, wait_timeout=0)
        asyncio.run(api.pool.add_account_cookies(label, cookies))
    except Exception as exc:  # noqa: BLE001 - only the class is reported; the message can hold the cookies
        cls = type(exc).__name__
    else:
        cls = None
    if cls:
        raise RefreshFailed(cls)
    if os.name == "posix":
        os.chmod(path, 0o600)
    ages_path = _ages_path(config)
    try:
        ages = json.loads(ages_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        ages = {}
    ages[label] = now.astimezone(UTC).isoformat()
    cache._atomic_write_json(ages, ages_path)
    if os.name == "posix":
        os.chmod(ages_path, 0o600)


# --- command line: the fallback child, the install record, the cookie refresh -------------------------------------

def _child(stdin: str, env: Mapping[str, str]) -> dict:
    """The fallback process: one page on the curl backend for one account, from the given cursor."""
    if env_guard(env, fallback=True):
        return {"status": "refused", "reason": "env"}
    if identity_problem(find_dist("twscrape"), PINNED_COMMIT):
        return {"status": "refused", "reason": "identity"}
    if curl_status(read_install_record(), platform_key(), find_dist("curl_cffi")) != "ok":
        return {"status": "refused", "reason": "curl"}
    try:
        req = json.loads(stdin)
        label, db, query, kv = req["label"], Path(req["db"]), req["query"], dict(req["kv"])
    except (ValueError, KeyError, TypeError):
        return {"status": "refused", "reason": "request"}
    reader = TwscrapeReader(label, db, load_library(), max_entries=xr.PAGE_ENTRIES)
    try:
        raw = reader.resume(query, kv, kv.pop("cursor", None))
    except xr.ReaderFailure as f:
        return child_reply_for(f)
    finally:
        reader.close()
    if raw is None:
        return {"status": "empty"}
    return {"status": "ok", "body": raw.body, "remaining": raw.rate_limit_remaining, "limit": raw.rate_limit_limit}


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="twscrape_reader", description="X reader owner commands (codes only).")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--curl-fallback", action="store_true", help="internal: the curl fallback child")
    g.add_argument("--write-curl-record", action="store_true", help="record the curl_cffi wheel for this platform")
    g.add_argument("--refresh-cookies", metavar="LABEL", help="cookie upsert; cookies from X_REFRESH_COOKIES")
    args = p.parse_args(argv)
    if args.curl_fallback:
        print(json.dumps(_child(sys.stdin.read(), os.environ)))
        return 0
    if args.write_curl_record:
        key = platform_key()
        try:
            rec = install_record(key, lock_text())
        except CurlUnavailable as e:
            print(f"curl_record status={e.reason}")
            return 2
        dist = find_dist("curl_cffi")
        status = curl_status(rec, key, dist)
        if status == "ok":
            write_install_record(rec)
        print(f"curl_record status={status} platform={key}")
        return 0 if status == "ok" else 2
    from api.data.attention import web_queries

    cookies = os.environ.get("X_REFRESH_COOKIES", "")
    if not cookies:
        print("refresh status=no_cookies_in_env")
        return 2
    try:
        refresh_cookies(args.refresh_cookies, cookies, config=web_queries.load().config,
                        now=datetime.now(UTC))
    except (XStartRefused, RefreshFailed, ValueError) as e:
        reasons = getattr(e, "reasons", None)
        detail = ",".join(reasons) if reasons else reasons
        print(f"refresh status={_word(type(e).__name__)} detail={_word(detail)}")
        return 2
    print(f"refresh status=ok label={_word(args.refresh_cookies)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
