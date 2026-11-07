"""CDP client over the debugging pipe (finish plan S-BrowserCDP: A1-A4, A16-A18). Default off.

Every outbound frame is built by ONE private function, `CdpClient._frame`, which validates role, method, scope,
session, exact parameter keys/values, URL policy and evaluate policy, and only then serializes and writes to the
pipe (`browser_host.PipeTransport.send`, NUL framing, 1 MiB inbound ceiling). There is no raw send. The method
tables contain no input, interception, storage or emulation domain, so "never types credentials" is a property
of the table. Raw frames, events and cookie values are never logged, persisted or put into an exception: every
failure is a closed reason code (`BrowserFailure`).
"""
from __future__ import annotations

import base64
import binascii
import json
import re
import time
from collections import deque
from dataclasses import dataclass

from api.data.attention.browser_host import BrowserFailure, require

OUT_FRAME_LIMIT = 65536
DEFAULT_BODY = 262144
HARD_BODY = 2 * 1024 * 1024
SITE_HOSTS = {"x": "x.com", "reddit": "www.reddit.com"}

_SESSION_CHECK = frozenset({"Browser.getVersion", "Browser.close", "Target.createTarget", "Target.attachToTarget",
                            "Target.closeTarget", "Page.enable", "Page.navigate", "Network.enable",
                            "Network.getCookies", "Runtime.evaluate"})
_READ = _SESSION_CHECK | {"Network.getResponseBody", "Network.disable"}
# A1: exact per role, no wildcards; `bootstrap` differs from `reddit_read` only in its capture bounds (A18).
METHODS = {"session_check": _SESSION_CHECK, "reddit_read": frozenset(_READ), "bootstrap": frozenset(_READ)}
BROWSER_LEVEL = frozenset({"Browser.getVersion", "Browser.close", "Target.createTarget", "Target.attachToTarget",
                           "Target.closeTarget"})

_URL = re.compile(r"https://([a-z0-9.-]{1,253})(:443)?(/[A-Za-z0-9_/]*)(?:\?([A-Za-z0-9_=&.-]{1,200}))?\Z")
_OBSERVED = re.compile(r"https://([a-z0-9.-]{1,253})(:443)?(?:[/?#]|\Z)")
_SUB = re.compile(r"[A-Za-z0-9_]{2,21}\Z")
_QUERY = re.compile(r"[A-Za-z0-9_=&.-]{1,200}\Z")
_LISTING = re.compile(r"/r/([A-Za-z0-9_]{2,21})/new/\Z")
_THREAD = re.compile(r"/r/([A-Za-z0-9_]{2,21})/comments/[a-z0-9]{1,16}/\Z")
_SCROLL = re.compile(r"window\.scrollBy\(0,([1-9][0-9]{2,3})\)\Z")
_HREF = "location.href"


@dataclass(frozen=True)
class Bounds:
    resource: int
    total: int
    responses: int
    navigations: int | None
    scrolls_per_page: int
    outstanding: int
    seconds: int


def bounds(role, max_body_bytes=None):
    """A18 capture bounds; only `reddit_read` takes the surface section's `max_body_bytes` (hard cap 2 MiB)."""
    require(role in METHODS, "cdp_role_invalid")
    if role != "reddit_read":
        require(max_body_bytes is None, "cdp_bounds_invalid")
        if role == "bootstrap":
            return Bounds(HARD_BODY, 16 * 1024 * 1024, 150, 15, 12, 100, 600)
        return Bounds(65536, 262144, 500, None, 0, 100, 600)
    size = DEFAULT_BODY if max_body_bytes is None else max_body_bytes
    require(type(size) is int and 1 <= size <= HARD_BODY, "cdp_bounds_invalid")
    return Bounds(size, 4 * size, 500, None, 12, 100, 600)


class UrlPolicy:
    """A3: `about:blank` (create only) or an application-built https URL on the site's single host."""

    def __init__(self, site, *, subreddits=(), queries=()):
        require(site in SITE_HOSTS, "cdp_policy_invalid")
        require(all(isinstance(s, str) and _SUB.match(s) for s in subreddits), "cdp_policy_invalid")
        require(all(isinstance(q, str) and _QUERY.match(q) for q in queries), "cdp_policy_invalid")
        self.site = site
        self.host = SITE_HOSTS[site]
        self.subreddits = frozenset(subreddits) if site == "reddit" else frozenset()
        self.queries = frozenset(queries)

    def target(self, url, *, create=False):
        if create and url == "about:blank":
            return url
        match = _URL.match(url) if isinstance(url, str) else None
        require(match is not None and match.group(1) == self.host, "cdp_url_refused")
        path, query = match.group(3), match.group(4)
        require(query is None or query in self.queries, "cdp_url_refused")
        if path == "/" or (self.site == "x" and path == "/home"):
            return url
        sub = (_LISTING.match(path) or _THREAD.match(path)) if self.site == "reddit" else None
        require(sub is not None and sub.group(1) in self.subreddits, "cdp_url_refused")
        return url

    def observed_ok(self, url):
        """Observed main-frame/document URLs: scheme and host only; subresource hosts are the relay's (A6)."""
        if url == "about:blank":
            return True
        match = _OBSERVED.match(url) if isinstance(url, str) else None
        return match is not None and match.group(1) == self.host


@dataclass
class Record:
    request_id: str
    session: str
    url: str
    method: str
    status: int | None = None
    mime: str | None = None
    cached: bool = False
    state: str = "open"
    kind: str = "pending"


def _keys(params, *names):
    require(set(params) == set(names), "cdp_params_refused")


class CdpClient:
    """One role, one URL policy, one pipe. Commands are synchronous: at most one pending request."""

    def __init__(self, pipe, role, policy, *, max_body_bytes=None, clock=time.monotonic, timeout=30):
        require(role in METHODS and isinstance(policy, UrlPolicy), "cdp_role_invalid")
        self.role = role
        self.policy = policy
        self.bounds = bounds(role, max_body_bytes)
        self.limits_hit = set()
        self._pipe = pipe
        self._clock = clock
        self._started = clock()
        self._timeout = timeout
        self._next = 0
        self._failure = None
        self._targets = {}
        self._sessions = set()
        self._scrolls = {}
        self._navigations = 0
        self._responses = 0
        self._open = {}
        self._done = deque(maxlen=self.bounds.responses)

    # The single serialization chokepoint (A2) ---------------------------------------------------------------
    def _frame(self, session_id, method, params):
        require(self._failure is None, self._failure or "")
        require(self._clock() - self._started <= self.bounds.seconds, "capture_time_exceeded")
        require(isinstance(method, str) and method in METHODS[self.role], "cdp_method_refused")
        require((session_id is None) == (method in BROWSER_LEVEL), "cdp_method_refused")
        require(session_id is None or session_id in self._sessions, "cdp_session_unknown")
        require(type(params) is dict, "cdp_params_refused")
        self._validate(session_id, method, params)
        self._next += 1
        message = {"id": self._next, "method": method, "params": params}
        if session_id is not None:
            message["sessionId"] = session_id
        frame = json.dumps(message, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
        require(len(frame) <= OUT_FRAME_LIMIT, "cdp_frame_too_large")
        self._pipe.send(frame)
        if method == "Page.navigate":
            self._navigations += 1
            self._scrolls[session_id] = 0
        elif method == "Runtime.evaluate" and params["expression"] != _HREF:
            self._scrolls[session_id] = self._scrolls.get(session_id, 0) + 1
        return self._next

    def _validate(self, sid, method, params):
        if method in {"Browser.getVersion", "Browser.close", "Page.enable", "Network.disable"}:
            _keys(params)
        elif method == "Target.createTarget":
            _keys(params, "url")
            self.policy.target(params["url"], create=True)
        elif method == "Target.attachToTarget":
            _keys(params, "targetId", "flatten")
            require(params["flatten"] is True and params["targetId"] in self._targets, "cdp_params_refused")
        elif method == "Target.closeTarget":
            _keys(params, "targetId")
            require(params["targetId"] in self._targets, "cdp_params_refused")
        elif method == "Page.navigate":
            _keys(params, "url")
            self.policy.target(params["url"])
            cap = self.bounds.navigations
            require(cap is None or self._navigations < cap, "capture_navigation_cap")
        elif method == "Network.enable":
            require(params == {"maxTotalBufferSize": self.bounds.total,
                               "maxResourceBufferSize": self.bounds.resource}, "cdp_params_refused")
        elif method == "Network.getCookies":
            _keys(params, "urls")
            urls = params["urls"]
            require(type(urls) is list and urls, "cdp_params_refused")
            for url in urls:
                self.policy.target(url)
        elif method == "Runtime.evaluate":
            _keys(params, "expression", "returnByValue", "awaitPromise")
            require(params["returnByValue"] is True and params["awaitPromise"] is False, "cdp_evaluate_refused")
            expression = params["expression"]
            if expression != _HREF:
                match = _SCROLL.match(expression) if isinstance(expression, str) else None
                require(match is not None and 200 <= int(match.group(1)) <= 4000
                        and self.role != "session_check", "cdp_evaluate_refused")
                require(self._scrolls.get(sid, 0) < self.bounds.scrolls_per_page, "capture_scroll_cap")
        elif method == "Network.getResponseBody":
            _keys(params, "requestId")
            self._data_record(sid, params["requestId"])
        else:  # pragma: no cover - every table entry has a validator
            raise BrowserFailure("cdp_method_refused")

    def _call(self, session_id, method, params):
        command = self._frame(session_id, method, params)
        deadline = self._clock() + self._timeout
        while True:
            remaining = deadline - self._clock()
            require(remaining > 0, "cdp_timeout")
            try:
                message = json.loads(self._pipe.receive(timeout=remaining))
            except ValueError:
                raise BrowserFailure("cdp_protocol_error") from None
            require(type(message) is dict, "cdp_protocol_error")
            if "id" not in message:
                self._event(message)
                require(self._failure is None, self._failure or "")
                continue
            require(message["id"] == command and message.get("sessionId") == session_id, "cdp_protocol_error")
            error = message.get("error")
            if error is not None:
                evicted = (method == "Network.getResponseBody" and type(error) is dict
                           and error.get("code") == -32000 and "evicted" in str(error.get("message", "")))
                raise BrowserFailure("capture_evicted" if evicted else "cdp_command_failed")
            result = message.get("result")
            require(type(result) is dict, "cdp_protocol_error")
            return result

    # Events: bounded, requestId-correlated capture (A3/A18) -------------------------------------------------
    def _event(self, message):
        sid, params, name = message.get("sessionId"), message.get("params"), message.get("method")
        if sid not in self._sessions or type(params) is not dict:
            return
        if name == "Page.frameNavigated":
            frame = params.get("frame")
            if type(frame) is dict and "parentId" not in frame and not self.policy.observed_ok(frame.get("url")):
                self._failure = "navigation_off_allowlist"
            return
        rid = params.get("requestId")
        if not isinstance(rid, str):
            return
        if name == "Network.requestWillBeSent":
            request = params.get("request") if type(params.get("request")) is dict else {}
            url = request.get("url") if isinstance(request.get("url"), str) else ""
            if params.get("type") == "Document" and not self.policy.observed_ok(url):
                self._failure = "navigation_off_allowlist"
                return
            if rid in self._open and type(params.get("redirectResponse")) is dict:
                hop = self._open.pop(rid)
                hop.status, hop.state, hop.kind = params["redirectResponse"].get("status"), "finished", "redirect"
                self._done.append(hop)
            if len(self._open) >= self.bounds.outstanding:
                self.limits_hit.add("capture_outstanding_cap")
                return
            method = request.get("method") if isinstance(request.get("method"), str) else "GET"
            self._open[rid] = Record(rid, sid, url[:2048], method[:16])
            return
        record = self._open.get(rid)
        if record is None or record.session != sid:
            return
        if name == "Network.responseReceived":
            self._responses += 1
            if self._responses > self.bounds.responses:
                self.limits_hit.add("capture_response_cap")
                self._open.pop(rid)
                return
            response = params.get("response") if type(params.get("response")) is dict else {}
            status = response.get("status")
            record.status = status if type(status) is int else None
            record.mime = response.get("mimeType") if isinstance(response.get("mimeType"), str) else None
            record.cached = record.cached or response.get("fromDiskCache") is True
        elif name == "Network.requestServedFromCache":
            record.cached = True
        elif name in {"Network.loadingFinished", "Network.loadingFailed"}:
            self._open.pop(rid)
            record.state = "finished" if name == "Network.loadingFinished" else "failed"
            record.kind = _classify(record)
            self._done.append(record)

    def _data_record(self, sid, request_id):
        found = [r for r in self._done if r.request_id == request_id and r.session == sid]
        require(isinstance(request_id, str) and found, "capture_not_ready")
        require(found[-1].kind == "data", "capture_not_data")
        return found[-1]

    # Public typed commands ----------------------------------------------------------------------------------
    def version(self):
        result = self._call(None, "Browser.getVersion", {})
        return {k: result.get(k) for k in ("protocolVersion", "product")}

    def open_page(self, url="about:blank"):
        target = self._call(None, "Target.createTarget", {"url": url}).get("targetId")
        require(isinstance(target, str) and target, "cdp_protocol_error")
        self._targets[target] = None
        sid = self._call(None, "Target.attachToTarget", {"targetId": target, "flatten": True}).get("sessionId")
        require(isinstance(sid, str) and sid, "cdp_protocol_error")
        self._targets[target] = sid
        self._sessions.add(sid)
        self._call(sid, "Page.enable", {})
        self._call(sid, "Network.enable", {"maxTotalBufferSize": self.bounds.total,
                                           "maxResourceBufferSize": self.bounds.resource})
        return sid

    def close_target(self, target_id):
        self._call(None, "Target.closeTarget", {"targetId": target_id})
        self._sessions.discard(self._targets.pop(target_id, None))

    def navigate(self, sid, url):
        self._call(sid, "Page.navigate", {"url": url})

    def location_href(self, sid):
        result = self._call(sid, "Runtime.evaluate", {"expression": _HREF, "returnByValue": True,
                                                      "awaitPromise": False})
        value = result.get("result", {}).get("value") if type(result.get("result")) is dict else None
        require(isinstance(value, str), "cdp_protocol_error")
        return value

    def scroll(self, sid, pixels):
        require(type(pixels) is int and 200 <= pixels <= 4000, "cdp_evaluate_refused")
        self._call(sid, "Runtime.evaluate", {"expression": f"window.scrollBy(0,{pixels})", "returnByValue": True,
                                             "awaitPromise": False})

    def cookies(self, sid, urls, hook=None):
        """A17: projected to names and expiry at parse; X values reach only the in-memory `hook`."""
        require(hook is None or self.policy.site == "x", "cdp_cookie_hook_refused")
        result = self._call(sid, "Network.getCookies", {"urls": list(urls)})
        cookies = result.get("cookies")
        require(type(cookies) is list, "cdp_protocol_error")
        projected, values = [], []
        for cookie in cookies:
            require(type(cookie) is dict and isinstance(cookie.get("name"), str), "cdp_protocol_error")
            expires = cookie.get("expires") if type(cookie.get("expires")) in (int, float) else None
            projected.append({"name": cookie["name"], "expires": expires})
            if hook is not None and isinstance(cookie.get("value"), str):
                values.append((cookie["name"], cookie["value"], expires))
        del cookies, result
        if hook is not None:
            hook(values)
        return projected

    def body(self, sid, request_id):
        self._data_record(sid, request_id)
        result = self._call(sid, "Network.getResponseBody", {"requestId": request_id})
        body = result.get("body")
        require(isinstance(body, str) and len(body) <= self.bounds.resource * 4 // 3 + 4, "capture_too_large")
        if result.get("base64Encoded") is True:
            try:
                data = base64.b64decode(body, validate=True)
            except (binascii.Error, ValueError):
                raise BrowserFailure("cdp_protocol_error") from None
        else:
            data = body.encode("utf-8")
        require(len(data) <= self.bounds.resource, "capture_too_large")
        return data

    def network_disable(self, sid):
        self._call(sid, "Network.disable", {})

    def close(self):
        self._call(None, "Browser.close", {})

    def responses(self, *, finished=True):
        """Retained, bounded metadata; `kind` in data/redirect/cached/http_error/failed (never counted as data)."""
        done = list(self._done)
        return done if finished else done + list(self._open.values())


def _classify(record):
    if record.state == "failed":
        return "failed"
    if record.status is not None and 300 <= record.status < 400:
        return "redirect"
    if record.cached:
        return "cached"
    if record.status is None or not 200 <= record.status < 300:
        return "http_error"
    return "data"
