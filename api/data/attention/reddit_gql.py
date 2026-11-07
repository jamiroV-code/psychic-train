"""Finish plan S-RGQL, contract B7: the anonymous GraphQL Reddit live method (`gql_anon` -> store `reddit_live_gql`).

Honest scope: this IMPERSONATES Reddit's Android app (Rule 8, REF-R §3/§4) with an app-only token and no account; it
can be closed by Reddit at any time. Comments are observed only for the threads the method opens
(`threads_opened`). Default off: nothing runs unless `gql_anon` is named in `reddit_live_methods`.

Gate (`gate_state`): `gql_anon` switched on; the published `gql_anon` section of `reddit_surface_path` loads and
carries a valid B7 `requests` block; a `verify` record of probe PR1 is fresh and matches the section hash and
revision (`probe_owner.verify_gate`); the persisted operations are not marked stale for this section hash; an
admitted transport exists. Anything else is `needs_probe` (or `unsupported_format`, `disabled`,
`method_unavailable`), never an exception.

B7 request grammar (closed; inside the hashed `gql_anon` section under `requests`, owner-approved amendment
07-11-26 so the templates are hash-bound with the section):
  {"client_id": <public app identifier, [A-Za-z0-9_-]{8,64}>,
   "token": {host, method, path, header_template, body_template, token_pointer, expires_pointer|null},
   "operations": {"posts": OP, "comments": OP}}
  OP = {host, method, path, header_template, body_template, operationName, variables_template}
Placeholders: `{subreddit}` (variables or path segment), `{after}` (variables or query value), `{post_id}`
(variables or path segment), `{limit}` (variables or query value), `{token}` ONLY as the exact operation header
`Authorization: Bearer {token}`. Header templates are nonsecret literals; any other credential-named header is
refused, and the token template may carry no `Authorization` at all: the mint header
`Authorization: Basic base64(<client_id>:)` is built HERE in code (B7 amendment, owner acknowledgement pending).
Each operation must map to a section endpoint of its lane (`reddit_surface.match_request`), whose B1 constructs
read the response (`extract_page`, full-text contract included).

Bounds: the daily request cap (`reddit_live_gql_daily_request_cap`) is a PERSISTED counter charged before every
send (mints included), independent of tokens and restarts; at most 2 token mints per UTC day; the bearer token lives
in memory only (never persisted, logged or put in a repr). A rejected persisted-query hash marks the operations
`ops_stale` for this section hash (owner action: new surface revision and PR1 verify); the poll stops at once,
no retry storm. Nothing here stores text or usernames: items are reduced at once (`reddit_core.reduce_item`).
"""
from __future__ import annotations

import asyncio
import base64
import copy
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

from api.data import cache
from api.data.attention import reddit_core, reddit_live
from api.data.attention import reddit_surface as rs

SECTION = "gql_anon"
STORE = reddit_core.STORES[SECTION]
LANE_OPS = ("posts", "comments")
MAX_MINTS_PER_DAY = 2
DEFAULT_TOKEN_TTL_S = 3600
TOKEN_MARGIN_S = 120
PAGE_LIMIT = 100  # the rendered `{limit}`
MAX_PAGES_PER_LANE = 40
MAX_PAGES_PER_THREAD = 5
PLACEHOLDERS = ("{subreddit}", "{after}", "{post_id}", "{limit}")
PATH_PLACEHOLDERS = ("{subreddit}", "{post_id}")
QUERY_PLACEHOLDERS = ("{after}", "{limit}")
BEARER = "Bearer {token}"
CLIENT_ID_RE = re.compile(r"[A-Za-z0-9_-]{8,64}")
HEADER_NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9-]{0,63}")
CREDENTIAL_RE = re.compile(r"auth|cookie|token|secret|session|passw|credential|bearer|api-?key|loid", re.IGNORECASE)
TRANSPORT_HEADERS = frozenset({"host", "content-length", "transfer-encoding", "connection", "proxy-authorization"})
TOKEN_RE = re.compile(r"[A-Za-z0-9._~+/=-]{16,8192}")
STALE_MARKERS = ("persistedquerynotfound", "persisted_query_not_found")
METHODS = ("GET", "POST")


class RequestsInvalid(ValueError):
    """The `requests` block is not valid B7 grammar; never holds a value."""

    def __init__(self, where: str):
        super().__init__(f"requests_invalid: {where}")
        self.reason = "surface_invalid"


class GqlStop(Exception):
    """One request cannot continue; `reason` is a lane stop reason, `kind` the transport class for probes."""

    def __init__(self, reason: str, kind: str):
        super().__init__(f"{reason}:{kind}")
        self.reason, self.kind = reason, kind


# --- the B7 grammar ---

@dataclass(frozen=True)
class TokenRequest:
    host: str
    method: str
    path: str
    headers: tuple[tuple[str, str], ...]
    body: dict | None
    token_pointer: tuple[str, ...]
    expires_pointer: tuple[str, ...] | None


@dataclass(frozen=True)
class Operation:
    lane: str
    host: str
    method: str
    path: str
    headers: tuple[tuple[str, str], ...]
    body: dict
    operation_name: str
    variables: dict


@dataclass(frozen=True)
class Requests:
    client_id: str = field(repr=False)
    token: TokenRequest
    operations: dict[str, Operation]


def _keys(d, required: set[str], optional: set[str], where: str) -> dict:
    if not isinstance(d, dict) or not required <= set(d) or set(d) - required - optional:
        raise RequestsInvalid(where)
    return d


def _no_placeholder(value, where: str) -> None:
    """Template JSON that may hold no placeholder at all (and no `{token}` anywhere)."""
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str) or "{" in k or "}" in k:
                raise RequestsInvalid(where)
            _no_placeholder(v, where)
    elif isinstance(value, list):
        for v in value:
            _no_placeholder(v, where)
    elif isinstance(value, str):
        if "{" in value or "}" in value:
            raise RequestsInvalid(where)
    elif not (value is None or isinstance(value, (bool, int, float))):
        raise RequestsInvalid(where)


def _variables(value, where: str) -> None:
    """Variables: a placeholder is a whole string value from `PLACEHOLDERS`; nothing else holds braces."""
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str) or "{" in k or "}" in k:
                raise RequestsInvalid(where)
            _variables(v, where)
    elif isinstance(value, list):
        for v in value:
            _variables(v, where)
    elif isinstance(value, str):
        if ("{" in value or "}" in value) and value not in PLACEHOLDERS:
            raise RequestsInvalid(where)
    elif not (value is None or isinstance(value, (bool, int, float))):
        raise RequestsInvalid(where)


def _path(text, where: str, *, placeholders: bool) -> str:
    if not isinstance(text, str) or not text.startswith("/") or len(text) > 512 or "#" in text or any(
            ch.isspace() or ord(ch) < 32 for ch in text):
        raise RequestsInvalid(where)
    path, _, query = text.partition("?")
    for seg in path.split("/")[1:]:
        if ("{" in seg or "}" in seg) and not (placeholders and seg in PATH_PLACEHOLDERS):
            raise RequestsInvalid(where)
    for k, v in parse_qsl(query, keep_blank_values=True):
        if "{" in k or "}" in k or (("{" in v or "}" in v) and not (placeholders and v in QUERY_PLACEHOLDERS)):
            raise RequestsInvalid(where)
    return text


def _headers(raw, where: str, *, bearer: bool) -> tuple[tuple[str, str], ...]:
    if not isinstance(raw, dict) or len(raw) > 24:
        raise RequestsInvalid(where)
    out, seen, has_bearer = [], set(), False
    for name, value in raw.items():
        low = name.lower() if isinstance(name, str) else ""
        if (not isinstance(name, str) or not HEADER_NAME_RE.fullmatch(name) or low in seen
                or low in TRANSPORT_HEADERS or not isinstance(value, str) or len(value) > 256
                or any(ord(ch) < 32 for ch in value)):
            raise RequestsInvalid(where)
        seen.add(low)
        if low == "authorization":
            if not bearer or value != BEARER:  # the token request never carries one: the mint header is code-owned
                raise RequestsInvalid(where + ".authorization")
            has_bearer = True
        elif CREDENTIAL_RE.search(name) or "{" in value or "}" in value:
            raise RequestsInvalid(where + ".credential")
        out.append((name, value))
    if bearer and not has_bearer:
        raise RequestsInvalid(where + ".authorization")
    return tuple(out)


def _host(raw, hosts: tuple[str, ...], where: str) -> str:
    if raw not in hosts:
        raise RequestsInvalid(where)
    return raw


def load_requests(section: rs.Section) -> Requests:
    """Validate the section's B7 `requests` block; any deviation raises `RequestsInvalid`."""
    if section.name != SECTION or section.requests is None:
        raise RequestsInvalid("requests")
    raw = _keys(section.requests, {"client_id", "token", "operations"}, set(), "requests")
    cid = raw["client_id"]
    if not isinstance(cid, str) or not CLIENT_ID_RE.fullmatch(cid):
        raise RequestsInvalid("client_id")
    t = _keys(raw["token"], {"host", "method", "path", "header_template", "body_template", "token_pointer",
                             "expires_pointer"}, set(), "token")
    if t["method"] not in METHODS:
        raise RequestsInvalid("token.method")
    if t["body_template"] is not None:
        if not isinstance(t["body_template"], dict):
            raise RequestsInvalid("token.body_template")
        _no_placeholder(t["body_template"], "token.body_template")
    try:
        tp = rs.parse_pointer(t["token_pointer"])
        ep = None if t["expires_pointer"] is None else rs.parse_pointer(t["expires_pointer"])
    except rs.SurfaceInvalid:
        raise RequestsInvalid("token.pointer") from None
    if not tp:
        raise RequestsInvalid("token.pointer")
    token = TokenRequest(_host(t["host"], section.hosts, "token.host"), t["method"],
                         _path(t["path"], "token.path", placeholders=False),
                         _headers(t["header_template"], "token.header_template", bearer=False),
                         copy.deepcopy(t["body_template"]), tp, ep)
    ops_raw = _keys(raw["operations"], set(LANE_OPS), set(), "operations")
    ops = {}
    for lane in LANE_OPS:
        o = _keys(ops_raw[lane], {"host", "method", "path", "header_template", "body_template", "operationName",
                                  "variables_template"}, set(), f"operations.{lane}")
        name = o["operationName"]
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name):
            raise RequestsInvalid(f"operations.{lane}.operationName")
        if o["method"] not in METHODS or not isinstance(o["body_template"], dict) or {
                "operationName", "variables"} & set(o["body_template"]):
            raise RequestsInvalid(f"operations.{lane}")
        _no_placeholder(o["body_template"], f"operations.{lane}.body_template")
        if not isinstance(o["variables_template"], dict):
            raise RequestsInvalid(f"operations.{lane}.variables_template")
        _variables(o["variables_template"], f"operations.{lane}.variables_template")
        op = Operation(lane, _host(o["host"], section.hosts, f"operations.{lane}.host"), o["method"],
                       _path(o["path"], f"operations.{lane}.path", placeholders=True),
                       _headers(o["header_template"], f"operations.{lane}.header_template", bearer=True),
                       copy.deepcopy(o["body_template"]), name, copy.deepcopy(o["variables_template"]))
        url, body = render(op, subreddit="CryptoCurrency", post_id="t3_a", limit=1)
        endpoint = rs.match_request(section, op.method, url, _bytes(body))
        if endpoint is None or endpoint.lane != lane:
            raise RequestsInvalid(f"operations.{lane}.endpoint")
        ops[lane] = op
    return Requests(cid, token, ops)


def _fill(value, values: dict):
    if isinstance(value, dict):
        return {k: _fill(v, values) for k, v in value.items() if not (v == "{after}" and values["{after}"] is None)}
    if isinstance(value, list):
        return [_fill(v, values) for v in value]
    if isinstance(value, str) and value in values:
        return values[value]
    return value


def render(op: Operation, *, subreddit: str | None = None, post_id: str | None = None,
           limit: int = PAGE_LIMIT) -> tuple[str, dict]:
    """The first page's URL and JSON body (`{after}` omitted; the cursor is placed by `reddit_surface`)."""
    values = {"{subreddit}": subreddit, "{post_id}": post_id, "{limit}": limit, "{after}": None}
    path, _, query = op.path.partition("?")
    segs = [str(values[s]) if s in PATH_PLACEHOLDERS else s for s in path.split("/")]
    if any(s == "None" for s in segs):
        raise ValueError("missing path value")
    pairs = [(k, str(values[v]) if v in QUERY_PLACEHOLDERS else v) for k, v in parse_qsl(query, keep_blank_values=True)
             if v != "{after}"]
    url = f"https://{op.host}" + "/".join(segs) + (f"?{urlencode(pairs)}" if pairs else "")
    body = {**copy.deepcopy(op.body), "operationName": op.operation_name, "variables": _fill(op.variables, values)}
    return url, body


def _bytes(body: dict | None) -> bytes | None:
    return None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")


# --- transport ---

@dataclass(frozen=True)
class Response:
    status: int
    content_type: str | None
    body: bytes = field(repr=False)


Transport = Callable[[str, str, dict, "bytes | None"], Response]


class TransportError(Exception):
    """The request did not complete; the class name is all that is ever reported."""


class HttpTransport:
    """The production transport: the B2 hardened httpx clients (`x_proxy_transport`), direct or through the admitted
    proxy route with the owner's policy narrowed to the section hosts. No redirects, no environment proxies."""

    def __init__(self, client_factory: Callable[[], object]):
        self._factory = client_factory

    def __call__(self, method: str, url: str, headers: dict, body: bytes | None) -> Response:
        try:
            return asyncio.run(self._send(method, url, headers, body))
        except Exception as exc:  # noqa: BLE001 - only the class survives
            raise TransportError(type(exc).__name__) from None

    async def _send(self, method, url, headers, body) -> Response:
        client = self._factory()
        try:
            resp = await client.request(method, url, headers=headers, content=body)
            data = await resp.aread()
            return Response(resp.status_code, resp.headers.get("content-type"), data)
        finally:
            await client.aclose()


def route_transport(config, *, routes=None, policy=None, hosts: tuple[str, ...] = ()) -> HttpTransport | None:
    """The admitted transport, or None (the gate is then `method_unavailable`). With a route provider its answer
    for `("reddit", "gql_anon")` decides; without one only `direct` is admitted, and only when no X proxy route is
    configured at all (the PX1 rule: an owner with proxies never leaks a direct request by default)."""
    from api.data.attention import x_proxy, x_proxy_transport as xpt
    if routes is not None:
        from api.data.attention.browser_session import AdmittedRoute
        route = routes.admitted_route("reddit", SECTION)
        if not isinstance(route, AdmittedRoute) or route.mode not in ("direct", "proxy"):
            return None
        if route.mode == "proxy":
            if policy is None or not isinstance(route.route, x_proxy.PrivateRoute) or not hosts:
                return None
            import dataclasses
            narrowed = dataclasses.replace(policy, origins=frozenset(
                x_proxy.canonical_origin(f"https://{h}/") for h in hosts))
            return HttpTransport(lambda: xpt.client(route.route, narrowed))
        return HttpTransport(xpt.direct_client)
    if config.x_proxy_required or any(getattr(config, k, None) is not None for k in
                                      ("x_proxy_list_path", "x_proxy_assignments_path", "x_proxy_policy_path")):
        return None
    return HttpTransport(xpt.direct_client)


# --- persisted counters (cap, mints, stale operations) ---

def gql_state_path() -> Path:
    return reddit_live.state_path(STORE).parent / "_gql_state.json"


def read_gql_state(now: datetime) -> dict:
    day = now.astimezone(timezone.utc).date().isoformat()
    path = gql_state_path()
    s = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    stale = s.get("ops_stale")
    if s.get("day") != day:
        s = {"day": day, "requests": 0, "mints": 0}
    s["ops_stale"] = stale  # survives the day change: only a new section hash clears it
    return s


def _write_state(s: dict) -> None:
    path = gql_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    cache._atomic_write_json(s, path)


# --- the client: one token, charged sends ---

class GqlClient:
    """Mints and uses one in-memory bearer token; `charge()` is called BEFORE every send and may stop it."""

    def __init__(self, section: rs.Section, requests: Requests, transport: Transport, *,
                 charge: Callable[[], bool], may_mint: Callable[[], bool], clock: Callable[[], datetime]):
        self.section, self.requests, self.transport = section, requests, transport
        self._charge, self._may_mint, self._clock = charge, may_mint, clock
        self._token: str | None = None
        self._expires: datetime | None = None
        self.sent = 0

    def __repr__(self) -> str:
        return "GqlClient()"

    def _send(self, method, url, headers, body) -> Response:
        if not self._charge():
            raise GqlStop("cap", "budget_exhausted")
        self.sent += 1
        try:
            return self.transport(method, url, headers, body)
        except Exception:  # noqa: BLE001 - transport failures are a class only
            raise GqlStop("error", "transport_failed") from None

    def _token_valid(self) -> bool:
        return (self._token is not None and self._expires is not None
                and self._clock() < self._expires - timedelta(seconds=TOKEN_MARGIN_S))

    def mint(self) -> None:
        if not self._may_mint():
            raise GqlStop("cap", "budget_exhausted")
        t = self.requests.token
        basic = base64.b64encode(f"{self.requests.client_id}:".encode("ascii")).decode("ascii")
        headers = dict(t.headers)
        headers["Authorization"] = "Basic " + basic  # code-owned; templates can never supply it
        if t.body is not None:
            headers.setdefault("Content-Type", "application/json")
        resp = self._send(t.method, f"https://{t.host}{t.path}", headers, _bytes(t.body))
        _status_stop(resp.status)
        try:
            doc = json.loads(resp.body)
        except ValueError:
            raise GqlStop("schema_mismatch", "schema_mismatch") from None
        token = rs.resolve(doc, t.token_pointer)
        if not isinstance(token, str) or not TOKEN_RE.fullmatch(token):
            raise GqlStop("schema_mismatch", "schema_mismatch")
        ttl = DEFAULT_TOKEN_TTL_S
        if t.expires_pointer is not None:
            ttl = rs.resolve(doc, t.expires_pointer)
            if isinstance(ttl, bool) or not isinstance(ttl, int) or not 300 <= ttl <= 7 * 86400:
                raise GqlStop("schema_mismatch", "schema_mismatch")
        self._token, self._expires = token, self._clock() + timedelta(seconds=ttl)

    def page(self, lane: str, *, subreddit: str | None = None, post_id: str | None = None,
             cursor: str | None = None) -> rs.Page:
        """One operation page through the section's endpoint; renews an expired or rejected token once."""
        op = self.requests.operations[lane]
        url, body = render(op, subreddit=subreddit, post_id=post_id)
        ep = rs.match_request(self.section, op.method, url, _bytes(body))
        if ep is None:
            raise GqlStop("schema_mismatch", "schema_mismatch")
        if cursor is not None:
            try:
                url, body = rs.place_cursor(ep, url, body, cursor)
            except rs.SurfaceError as exc:
                raise GqlStop(exc.reason, "schema_mismatch") from None
        for attempt in (0, 1):
            if not self._token_valid():
                self.mint()
            headers = {k: (f"Bearer {self._token}" if v == BEARER else v) for k, v in op.headers}
            resp = self._send(op.method, url, headers, _bytes(body))
            if resp.status == 401 and attempt == 0:
                self._token = None  # rejected: one renewal, never a loop
                continue
            break
        _stale_check(resp)
        _status_stop(resp.status)
        try:
            return rs.extract_page(self.section, ep, status=resp.status, content_type=resp.content_type,
                                   body=resp.body)
        except rs.SurfaceError as exc:
            raise GqlStop(exc.reason, exc.reason if exc.reason in (
                "schema_mismatch", "unsupported_format", "empty_shell") else "transport_failed") from None


class OpsStale(GqlStop):
    def __init__(self):
        super().__init__("schema_mismatch", "queryid_changed")


def _status_stop(status: int) -> None:
    if status == 200:
        return
    if status == 429:
        raise GqlStop("error", "rate_limited")
    if status in (401, 403):
        raise GqlStop("error", "blocked")
    raise GqlStop("error", "transport_failed")


def _stale_check(resp: Response) -> None:
    """A rejected persisted-query hash (GraphQL `errors` naming it) marks the operations stale."""
    if not resp.body or b"ersist" not in resp.body:
        return
    try:
        doc = json.loads(resp.body)
    except ValueError:
        return
    errors = doc.get("errors") if isinstance(doc, dict) else None
    for e in errors if isinstance(errors, list) else ():
        text = json.dumps(e).lower() if isinstance(e, dict) else ""
        if any(m in text for m in STALE_MARKERS):
            raise OpsStale()


# --- the LiveMethod ---

class GqlMethod:
    method_id = SECTION
    label = reddit_core.LABELS[SECTION]
    store = STORE

    def __init__(self, config, *, transport: Transport | None, clock: Callable[[], datetime],
                 hasher=None, queries=None):
        self.config, self.transport, self.clock = config, transport, clock
        self._hasher, self._queries = hasher, queries

    def __repr__(self) -> str:
        return "GqlMethod()"

    def _section(self) -> rs.Section:
        return rs.load_surface(Path(self.config.reddit_surface_path), SECTION)

    def gate_state(self, now: datetime) -> str:
        from api.scripts import probe_owner
        if SECTION not in self.config.reddit_live_methods:
            return "disabled"
        if not self.config.reddit_surface_path:
            return "needs_probe"
        try:
            section = self._section()
            load_requests(section)
        except rs.SurfaceInvalid as exc:
            return "unsupported_format" if exc.reason == "unsupported_format" else "needs_probe"
        except RequestsInvalid:
            return "needs_probe"
        verdict = probe_owner.verify_gate(cache.CACHE_ROOT, SECTION, surface_path=Path(self.config.reddit_surface_path),
                                          max_age_days=self.config.reddit_live_probe_max_age_days,
                                          today=now.astimezone(timezone.utc).date())
        if verdict != "ok" or read_gql_state(now)["ops_stale"] == section.sha256:
            return "needs_probe"
        return "ready" if self.transport is not None else "method_unavailable"

    def next_poll_due(self, now: datetime) -> datetime | None:
        return None

    def close(self) -> None:
        return None

    def _matchers(self):
        from api.data.attention import reddit_items, reddit_metrics, web_queries
        hasher = self._hasher or reddit_items.AuthorHasher(reddit_items.load_salt(create=True))
        q = self._queries() if self._queries is not None else web_queries.load()
        terms = reddit_metrics.coin_terms(q)
        return hasher, (lambda text: reddit_metrics.matched_coins(text, terms))

    def run_poll(self, ctx: reddit_live.PollContext) -> reddit_live.PollResult:
        now = ctx.now
        section = self._section()
        requests = load_requests(section)
        hasher, match = self._matchers()
        cap = self.config.reddit_live_gql_daily_request_cap
        left = [ctx.requests_left]

        def charge() -> bool:
            s = read_gql_state(now)
            if left[0] <= 0 or s["requests"] >= cap:
                return False
            s["requests"] += 1
            left[0] -= 1
            _write_state(s)
            return True

        def may_mint() -> bool:
            s = read_gql_state(now)
            if s["mints"] >= MAX_MINTS_PER_DAY:
                return False
            s["mints"] += 1
            _write_state(s)
            return True

        client = GqlClient(section, requests, self.transport, charge=charge, may_mint=may_mint, clock=self.clock)
        pid, lanes, items, aborted = now.isoformat(), [], [], False
        listed_counts: dict[str, tuple[str, int]] = {}
        for sub in ctx.subreddits:
            lane, raws, aborted = self._posts_lane(client, sub, ctx.floors[sub], pid, now, section)
            lanes.append(lane)
            items += [reddit_core.reduce_item(r, hasher, match) for r in raws]
            for r in raws:
                listed_counts[r.id] = (r.subreddit, r.num_comments or 0)
            if aborted:
                break
        if not aborted and ctx.threads:
            lanes += self._comment_lanes(client, ctx, listed_counts, pid, now, section, items, hasher, match)
        return reddit_live.PollResult(pid, now, tuple(lanes), tuple(items), client.sent)

    def _stop(self, exc: GqlStop, section: rs.Section, now: datetime) -> bool:
        """Record what a stop means; True when the whole poll must end (cap, stale operations, block, error)."""
        if isinstance(exc, OpsStale):
            s = read_gql_state(now)
            s["ops_stale"] = section.sha256
            _write_state(s)
        return exc.reason in ("cap", "error") or isinstance(exc, OpsStale)

    def _posts_lane(self, client, sub, floor, pid, now, section):
        seen, chain, pages, stop, cursor, aborted = [], [], 0, "exhausted", None, False
        while True:
            if pages >= MAX_PAGES_PER_LANE:
                stop = "cap"
                break
            try:
                page = client.page("posts", subreddit=sub, cursor=cursor)
            except GqlStop as exc:
                stop, aborted = exc.reason, self._stop(exc, section, now)
                break
            pages += 1
            seen += page.items
            if page.items:
                chain.append((page.next_cursor or page.items[-1].id, min(r.created for r in page.items)))
            reached = any(r.created <= floor for r in page.items)
            if reached or page.has_more is False or not page.next_cursor:
                break
            cursor = page.next_cursor
        newer = [r for r in seen if r.created > floor]
        listed = newer + sorted((r for r in seen if r.created <= floor), key=lambda r: r.created, reverse=True)[:1]
        lane = reddit_live.LaneEvidence(
            sub, "posts", pid, now, floor, max((r.created for r in listed), default=None),
            min((r.created for r in listed), default=None), len(newer), pages, tuple(chain), stop,
            tuple((r.id, r.num_comments or 0) for r in listed if r.kind == "post"))
        return lane, listed, aborted

    def _thread_subreddits(self, now) -> dict[str, tuple[str, int]]:
        out: dict[str, tuple[str, int]] = {}
        for lane in reddit_live.read_lanes(STORE, now.date() - timedelta(days=2), now.date()):
            if lane.kind == "posts":
                for t, n in lane.threads:
                    out[t] = (lane.subreddit, n)
        return out

    def _comment_lanes(self, client, ctx, listed_counts, pid, now, section, items, hasher, match):
        known = {**self._thread_subreddits(now), **listed_counts}
        done: dict[str, list] = {}
        failed: dict[str, tuple[list, str]] = {}
        stats: dict[str, list] = {}
        for t in ctx.threads:
            if t not in known:
                continue  # never listed by this method: no subreddit to attribute it to
            sub, count = known[t]
            cursor, pages, stop, got, abort = None, 0, "exhausted", [], False
            while True:
                if pages >= MAX_PAGES_PER_THREAD:
                    stop = "cap"
                    break
                try:
                    page = client.page("comments", post_id=t, cursor=cursor)
                except GqlStop as exc:
                    stop, abort = exc.reason, self._stop(exc, section, now)
                    break
                pages += 1
                got += [r for r in page.items if r.kind == "comment"]
                if page.has_more is False or not page.next_cursor:
                    break
                cursor = page.next_cursor
            items += [reddit_core.reduce_item(r, hasher, match) for r in got]
            st = stats.setdefault(sub, [0, 0, None, None])
            st[0] += pages
            st[1] += len(got)
            for r in got:
                st[2] = r.created if st[2] is None else max(st[2], r.created)
                st[3] = r.created if st[3] is None else min(st[3], r.created)
            if stop == "exhausted":
                done.setdefault(sub, []).append((t, count))
            else:
                failed.setdefault(sub, ([], stop))[0].append((t, count))
            if abort:
                break
        lanes = []
        for sub in dict.fromkeys([*done, *failed]):
            pages, n, newest, oldest = stats.get(sub, [0, 0, None, None])
            if sub in done:
                lanes.append(reddit_live.LaneEvidence(sub, "comments", pid, now, None, newest, oldest, n, pages, (),
                                                      "exhausted", tuple(done[sub])))
            if sub in failed:
                threads, stop = failed[sub]
                lanes.append(reddit_live.LaneEvidence(sub, "comments", pid, now, None, None, None, 0, 0, (), stop,
                                                      tuple(threads)))
        return lanes


def make_method(config, deps) -> GqlMethod:
    """RC-9 factory: `deps` from the worker (`clock`, optionally `gql_transport`, `routes`, `proxy_policy`,
    `hasher`, `queries`). Without an admitted transport the method's gate is `method_unavailable`."""
    clock = getattr(deps, "clock", None) or (lambda: datetime.now(timezone.utc))
    transport = getattr(deps, "gql_transport", None)
    if transport is None:
        hosts: tuple[str, ...] = ()
        if config.reddit_surface_path:
            try:
                hosts = rs.load_surface(Path(config.reddit_surface_path), SECTION).hosts
            except rs.SurfaceInvalid:
                hosts = ()
        transport = route_transport(config, routes=getattr(deps, "routes", None),
                                    policy=getattr(deps, "proxy_policy", None), hosts=hosts)
    return GqlMethod(config, transport=transport, clock=clock, hasher=getattr(deps, "hasher", None),
                     queries=getattr(deps, "queries", None))
