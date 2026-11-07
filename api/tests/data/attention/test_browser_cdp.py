"""S-BrowserCDP acceptance (finish plan A1-A4, A16-A18). No installed browser is launched.

Unit tests drive the client over an in-memory scripted pipe (every refusal must happen BEFORE serialization:
nothing reaches `send`); the lifecycle tests run the REAL `browser_host` pipe transport against the spawned
`browser_fake_main` (A13).
"""
from __future__ import annotations

import json
import os
from collections import deque
from pathlib import Path

import pytest

from api.data.attention import browser_cdp as cdp
from api.data.attention import browser_host as h
from api.data.attention import browser_profile as p
from api.tests.data.attention.fixture_seams import spawn_launcher

FAKE = "api.tests.data.attention.browser_fake_main"
BINARY = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32" / "cmd.exe"
REDDIT = cdp.UrlPolicy("reddit", subreddits=("solana", "CryptoCurrency"))
X = cdp.UrlPolicy("x")
FORBIDDEN = ("Target.sendMessageToTarget", "Target.exposeDevToolsProtocol", "Target.setDiscoverTargets",
             "Target.setAutoAttach", "Target.attachToBrowserTarget", "Input.dispatchKeyEvent", "Input.insertText",
             "Fetch.enable", "Storage.getCookies", "Page.addScriptToEvaluateOnNewDocument", "Page.setBypassCSP",
             "Page.printToPDF", "Page.captureScreenshot", "Network.setCookie", "Network.setCookies",
             "Network.deleteCookies", "Network.getAllCookies", "Security.setIgnoreCertificateErrors",
             "Emulation.setUserAgentOverride", "Debugger.enable", "DOM.getDocument", "IO.read", "Tracing.start",
             "Log.enable", "Browser.grantPermissions", "Browser.setDownloadBehavior", "Runtime.callFunctionOn",
             "Runtime.compileScript", "Runtime.enable", "Network.getResponseBodyForInterception")


class ScriptPipe:
    """In-memory pipe: records every serialized frame and answers through `respond(message) -> [frames]`."""

    def __init__(self, respond=None):
        self.sent = []
        self.inbox = deque()
        self.respond = respond or default_reply

    def send(self, frame):
        assert isinstance(frame, bytes) and b"\0" not in frame
        self.sent.append(frame)
        for item in self.respond(json.loads(frame)):
            self.inbox.append(json.dumps(item).encode())

    def receive(self, *, timeout=10):
        if not self.inbox:
            raise h.BrowserFailure("cdp_timeout")
        return self.inbox.popleft()


def default_reply(message):
    result = {}
    if message["method"] == "Target.createTarget":
        result = {"targetId": "T1"}
    elif message["method"] == "Target.attachToTarget":
        result = {"sessionId": "S1"}
    reply = {"id": message["id"], "result": result}
    if "sessionId" in message:
        reply["sessionId"] = message["sessionId"]
    return [reply]


def opened(role="reddit_read", policy=REDDIT, respond=None, **kw):
    pipe = ScriptPipe(respond)
    client = cdp.CdpClient(pipe, role, policy, **kw)
    sid = client.open_page()
    pipe.sent.clear()
    return client, pipe, sid


# A1/A2: exact method table and the single chokepoint ------------------------------------------------------------

def test_method_tables_are_exact_per_role():
    check = {"Browser.getVersion", "Browser.close", "Target.createTarget", "Target.attachToTarget",
             "Target.closeTarget", "Page.enable", "Page.navigate", "Network.enable", "Network.getCookies",
             "Runtime.evaluate"}
    assert cdp.METHODS["session_check"] == frozenset(check)
    assert cdp.METHODS["reddit_read"] == frozenset(check | {"Network.getResponseBody", "Network.disable"})
    assert cdp.METHODS["bootstrap"] == cdp.METHODS["reddit_read"]
    assert not any(m.endswith("*") for table in cdp.METHODS.values() for m in table)


@pytest.mark.parametrize("method", FORBIDDEN)
def test_every_forbidden_method_refused_before_serialization_browser_and_session_level(method):
    client, pipe, sid = opened("bootstrap")
    for target in (None, sid):
        with pytest.raises(h.BrowserFailure, match="cdp_method_refused"):
            client._call(target, method, {})
    assert pipe.sent == []


def test_session_targeted_and_browser_level_methods_cannot_swap_scope():
    client, pipe, sid = opened()
    with pytest.raises(h.BrowserFailure, match="cdp_method_refused"):
        client._call(sid, "Browser.getVersion", {})
    with pytest.raises(h.BrowserFailure, match="cdp_method_refused"):
        client._call(None, "Page.enable", {})
    with pytest.raises(h.BrowserFailure, match="cdp_session_unknown"):
        client._call("S-unknown", "Page.enable", {})
    assert pipe.sent == []


def test_params_key_set_is_exact_and_no_command_embedding():
    client, pipe, sid = opened()
    bad = [
        (None, "Browser.getVersion", {"x": 1}),
        (None, "Target.createTarget", {"url": "about:blank", "newWindow": True}),
        (None, "Target.attachToTarget", {"targetId": "T1"}),
        (None, "Target.attachToTarget", {"targetId": "T1", "flatten": False}),
        (None, "Target.attachToTarget", {"targetId": "T-unknown", "flatten": True}),
        (sid, "Page.navigate", {"url": "https://www.reddit.com/", "referrer": "https://evil.example/"}),
        (sid, "Network.getCookies", {}),
        (sid, "Network.disable", {"method": "Input.insertText"}),
        (None, "Target.closeTarget", {"targetId": "T1", "message": json.dumps({"method": "Input.insertText"})}),
    ]
    for target, method, params in bad:
        with pytest.raises(h.BrowserFailure):
            client._call(target, method, params)
    with pytest.raises(h.BrowserFailure, match="cdp_params_refused"):
        client._call(sid, "Page.enable", [])
    assert pipe.sent == []


def test_outbound_frame_bound_64k():
    client, pipe, sid = opened()
    with pytest.raises(h.BrowserFailure):
        client.cookies(sid, ["https://www.reddit.com/"] * 5000)
    assert pipe.sent == []
    assert cdp.OUT_FRAME_LIMIT == 65536


def test_wire_frames_are_minimal_json_with_session_id():
    client, pipe, sid = opened()
    client.navigate(sid, "https://www.reddit.com/r/solana/new/")
    sent = json.loads(pipe.sent[0])
    assert sent == {"id": sent["id"], "method": "Page.navigate", "params": {"url": "https://www.reddit.com/r/solana/new/"},
                    "sessionId": sid}


# A3: URL policy ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "javascript:alert(1)", "data:text/html,x", "file:///C:/Windows/win.ini", "blob:https://www.reddit.com/1",
    "chrome://settings", "edge://settings", "devtools://devtools/x", "view-source:https://www.reddit.com/",
    "ftp://www.reddit.com/", "ws://www.reddit.com/", "http://www.reddit.com/", "https://evil.example/",
    "https://reddit.com/", "https://www.reddit.com.evil.example/", "https://user@www.reddit.com/",
    "https://www.reddit.com:8443/", "https://www.reddit.com/r/notconfigured/new/", "https://www.reddit.com/r/solana/",
    "https://www.reddit.com/r/solana/comments/ABC/", "https://www.reddit.com/r/solana/comments/abcdefghijklmnopq/",
    "https://www.reddit.com/r/solana/new/?sort=top", "https://www.reddit.com/#frag", "https://www.reddit.com/r/../",
    "https://WWW.REDDIT.COM/", "https://www.reddit.com/r/solana/new/ ", "about:blank", "https://x.com/home",
    "https://www.reddit.com\\@evil.example/",
])
def test_off_policy_navigations_refused_before_serialization(url):
    client, pipe, sid = opened()
    with pytest.raises(h.BrowserFailure, match="cdp_url_refused"):
        client.navigate(sid, url)
    assert pipe.sent == []


def test_allowed_templates_and_closed_query_set():
    for url in ("https://www.reddit.com/", "https://www.reddit.com/r/solana/new/",
                "https://www.reddit.com/r/CryptoCurrency/comments/1abc2d/", "https://www.reddit.com:443/r/solana/new/"):
        assert REDDIT.target(url) == url
    assert X.target("https://x.com/home") and X.target("https://x.com/")
    with pytest.raises(h.BrowserFailure):
        X.target("https://x.com/i/flow/login")
    queried = cdp.UrlPolicy("reddit", subreddits=("solana",), queries=("sort=new",))
    assert queried.target("https://www.reddit.com/r/solana/new/?sort=new")
    with pytest.raises(h.BrowserFailure):
        queried.target("https://www.reddit.com/r/solana/new/?sort=old")
    assert REDDIT.target("about:blank", create=True) == "about:blank"
    with pytest.raises(h.BrowserFailure):
        cdp.UrlPolicy("gateway")
    with pytest.raises(h.BrowserFailure):
        cdp.UrlPolicy("reddit", subreddits=("bad/../sub",))


def test_create_target_url_policy():
    client = cdp.CdpClient(ScriptPipe(), "session_check", REDDIT)
    with pytest.raises(h.BrowserFailure, match="cdp_url_refused"):
        client.open_page("javascript:1")
    assert client.open_page("https://www.reddit.com/") == "S1"


# A4: Runtime.evaluate ------------------------------------------------------------------------------------------

def test_evaluate_only_two_constructs():
    client, pipe, sid = opened(respond=lambda m: [{"id": m["id"], "sessionId": "S1",
                                                    "result": {"result": {"type": "string", "value": "about:blank"}}}]
                               if m["method"] == "Runtime.evaluate" else default_reply(m))
    assert client.location_href(sid) == "about:blank"
    client.scroll(sid, 200)
    client.scroll(sid, 4000)
    sent = [json.loads(f)["params"] for f in pipe.sent]
    assert sent[0] == {"expression": "location.href", "returnByValue": True, "awaitPromise": False}
    assert sent[1]["expression"] == "window.scrollBy(0,200)"
    pipe.sent.clear()
    for n in (199, 4001, True, 1.5, "300", -500):
        with pytest.raises(h.BrowserFailure, match="cdp_evaluate_refused"):
            client.scroll(sid, n)
    for params in ({"expression": "document.cookie", "returnByValue": True, "awaitPromise": False},
                   {"expression": "location.href", "returnByValue": True, "awaitPromise": True},
                   {"expression": "location.href", "returnByValue": True, "awaitPromise": False, "userGesture": True},
                   {"expression": "location.href", "returnByValue": True, "awaitPromise": False,
                    "includeCommandLineAPI": True},
                   {"expression": "window.scrollBy(0,300);fetch('/')", "returnByValue": True, "awaitPromise": False},
                   {"expression": "window.scrollBy(0, 300)", "returnByValue": True, "awaitPromise": False}):
        with pytest.raises(h.BrowserFailure):
            client._call(sid, "Runtime.evaluate", params)
    assert pipe.sent == []


def test_scroll_is_reddit_read_only_and_bounded_per_page():
    client, pipe, sid = opened("session_check")
    with pytest.raises(h.BrowserFailure, match="cdp_evaluate_refused"):
        client.scroll(sid, 500)
    client, pipe, sid = opened()
    for _ in range(12):
        client.scroll(sid, 500)
    with pytest.raises(h.BrowserFailure, match="capture_scroll_cap"):
        client.scroll(sid, 500)
    client.navigate(sid, "https://www.reddit.com/r/solana/new/")
    client.scroll(sid, 500)  # the cap is per page


# A18: bounded Network.enable and capture -----------------------------------------------------------------------

def test_network_enable_requires_exact_role_bounds():
    client, pipe, sid = opened()
    for params in ({}, {"maxTotalBufferSize": 262144}, {"maxTotalBufferSize": 10**9, "maxResourceBufferSize": 10**8},
                   {"maxTotalBufferSize": 1048576, "maxResourceBufferSize": 262144, "maxPostDataSize": 1}):
        with pytest.raises(h.BrowserFailure, match="cdp_params_refused"):
            client._call(sid, "Network.enable", params)
    assert pipe.sent == []


def test_role_bounds():
    assert (cdp.bounds("session_check").resource, cdp.bounds("session_check").total) == (65536, 262144)
    read = cdp.bounds("reddit_read")
    assert (read.resource, read.total, read.responses, read.scrolls_per_page, read.outstanding, read.seconds) == (
        262144, 1048576, 500, 12, 100, 600)
    assert cdp.bounds("reddit_read", 2 * 1024 * 1024).total == 8 * 1024 * 1024
    with pytest.raises(h.BrowserFailure):
        cdp.bounds("reddit_read", 2 * 1024 * 1024 + 1)
    boot = cdp.bounds("bootstrap")
    assert (boot.resource, boot.total, boot.responses, boot.navigations, boot.scrolls_per_page, boot.seconds) == (
        2097152, 16777216, 150, 15, 12, 600)
    pipe = ScriptPipe()
    cdp.CdpClient(pipe, "session_check", REDDIT).open_page()
    enable = [json.loads(f) for f in pipe.sent if b"Network.enable" in f]
    assert enable[0]["params"] == {"maxTotalBufferSize": 262144, "maxResourceBufferSize": 65536}


def events_for(url, rid="R1", status=200, mime="application/json", **response):
    def respond(message):
        frames = []
        if message["method"] == "Page.navigate":
            frames = [{"method": "Network.requestWillBeSent", "sessionId": "S1",
                       "params": {"requestId": rid, "type": "Document", "request": {"url": url, "method": "GET"}}},
                      {"method": "Page.frameNavigated", "sessionId": "S1", "params": {"frame": {"id": "F", "url": url}}},
                      {"method": "Network.responseReceived", "sessionId": "S1",
                       "params": {"requestId": rid, "type": "Document",
                                  "response": {"url": url, "status": status, "mimeType": mime, **response}}},
                      {"method": "Network.loadingFinished", "sessionId": "S1",
                       "params": {"requestId": rid, "encodedDataLength": 10}}]
        if message["method"] == "Network.getResponseBody":
            return [{"id": message["id"], "sessionId": "S1",
                     "error": {"code": -32000, "message": "Request content was evicted from inspector cache"}}]
        return frames + default_reply(message)
    return respond


def test_classification_ok_redirect_cache_http_error_and_failed():
    url = "https://www.reddit.com/r/solana/new/"
    for kw, expected in (({}, "data"), ({"status": 301}, "redirect"), ({"fromDiskCache": True}, "cached"),
                         ({"status": 503}, "http_error")):
        client, _, sid = opened(respond=events_for(url, **kw))
        client.navigate(sid, url)
        (record,) = client.responses()
        assert record.kind == expected and record.request_id == "R1" and record.url == url

    def failing(message):
        frames = []
        if message["method"] == "Page.navigate":
            frames = [{"method": "Network.requestWillBeSent", "sessionId": "S1",
                       "params": {"requestId": "R9", "type": "XHR", "request": {"url": url, "method": "GET"}}},
                      {"method": "Network.requestServedFromCache", "sessionId": "S1", "params": {"requestId": "R9"}},
                      {"method": "Network.loadingFailed", "sessionId": "S1",
                       "params": {"requestId": "R9", "errorText": "net::ERR_PROXY_CONNECTION_FAILED"}}]
        return frames + default_reply(message)
    client, _, sid = opened(respond=failing)
    client.navigate(sid, url)
    (record,) = client.responses()
    assert record.kind == "failed"
    with pytest.raises(h.BrowserFailure, match="capture_not_data"):
        client.body(sid, "R9")


def test_eviction_is_capture_evicted_never_empty():
    url = "https://www.reddit.com/r/solana/new/"
    client, _, sid = opened(respond=events_for(url))
    client.navigate(sid, url)
    with pytest.raises(h.BrowserFailure, match="capture_evicted"):
        client.body(sid, "R1")


def test_body_refused_for_unknown_or_unfinished_request_before_serialization():
    client, pipe, sid = opened()
    with pytest.raises(h.BrowserFailure, match="capture_not_ready"):
        client.body(sid, "nope")
    assert pipe.sent == []


def test_off_allowlist_main_frame_navigation_ends_session():
    url = "https://www.reddit.com/r/solana/new/"

    def redirect_away(message):
        frames = []
        if message["method"] == "Page.navigate":
            frames = [{"method": "Page.frameNavigated", "sessionId": "S1",
                       "params": {"frame": {"id": "F", "url": "https://evil.example/login"}}}]
        return frames + default_reply(message)
    client, pipe, sid = opened(respond=redirect_away)
    with pytest.raises(h.BrowserFailure, match="navigation_off_allowlist"):
        client.navigate(sid, url)
    with pytest.raises(h.BrowserFailure, match="navigation_off_allowlist"):
        client.location_href(sid)
    # Subresources and child frames are the relay's job (A6), not a session end.
    def subresource(message):
        frames = []
        if message["method"] == "Page.navigate":
            frames = [{"method": "Network.requestWillBeSent", "sessionId": "S1",
                       "params": {"requestId": "R2", "type": "Image", "request": {"url": "https://cdn.example/a.png"}}},
                      {"method": "Page.frameNavigated", "sessionId": "S1",
                       "params": {"frame": {"id": "C", "parentId": "F", "url": "https://ads.example/"}}}]
        return frames + default_reply(message)
    client, _, sid = opened(respond=subresource)
    client.navigate(sid, url)


def test_event_and_response_bounds():
    url = "https://www.reddit.com/r/solana/new/"

    def flood(message):
        frames = []
        if message["method"] == "Page.navigate":
            for i in range(160):
                frames.append({"method": "Network.requestWillBeSent", "sessionId": "S1",
                               "params": {"requestId": f"R{i}", "type": "XHR", "request": {"url": url, "method": "GET"}}})
                frames.append({"method": "Network.responseReceived", "sessionId": "S1",
                               "params": {"requestId": f"R{i}", "response": {"url": url, "status": 200}}})
        return frames + default_reply(message)
    client, _, sid = opened("bootstrap", respond=flood)
    client.navigate(sid, url)
    assert len(client.responses(finished=False)) <= 100
    assert {"capture_outstanding_cap"} <= client.limits_hit


def test_navigation_cap_in_bootstrap():
    client, _, sid = opened("bootstrap")
    for _ in range(15):
        client.navigate(sid, "https://www.reddit.com/")
    with pytest.raises(h.BrowserFailure, match="capture_navigation_cap"):
        client.navigate(sid, "https://www.reddit.com/")


def test_session_time_bound():
    now = [0.0]
    client, _, sid = opened(clock=lambda: now[0])
    now[0] = 601
    with pytest.raises(h.BrowserFailure, match="capture_time_exceeded"):
        client.navigate(sid, "https://www.reddit.com/")


def test_protocol_errors_carry_no_raw_frame():
    def junk(message):
        return [{"id": message["id"], "error": {"code": -32601, "message": "secret_cookie_value=abc"}}]
    client = cdp.CdpClient(ScriptPipe(junk), "session_check", REDDIT)
    with pytest.raises(h.BrowserFailure) as info:
        client.version()
    assert "secret" not in str(info.value) and str(info.value) == "cdp_command_failed"


# A17: cookie projection ----------------------------------------------------------------------------------------

def cookie_reply(message):
    if message["method"] == "Network.getCookies":
        return [{"id": message["id"], "sessionId": "S1", "result": {"cookies": [
            {"name": "reddit_session", "value": "SECRET", "expires": 1900000000, "domain": ".reddit.com"}]}}]
    return default_reply(message)


def test_reddit_cookie_values_dropped_at_parse_and_hook_refused():
    client, _, sid = opened(respond=cookie_reply)
    assert client.cookies(sid, ["https://www.reddit.com/"]) == [{"name": "reddit_session", "expires": 1900000000}]
    with pytest.raises(h.BrowserFailure, match="cdp_cookie_hook_refused"):
        client.cookies(sid, ["https://www.reddit.com/"], hook=lambda values: None)
    with pytest.raises(h.BrowserFailure, match="cdp_url_refused"):
        client.cookies(sid, ["https://evil.example/"])


def test_x_cookie_values_reach_only_the_in_memory_hook():
    seen = []
    client, _, sid = opened("session_check", X, respond=cookie_reply)
    projected = client.cookies(sid, ["https://x.com/"], hook=seen.extend)
    assert projected == [{"name": "reddit_session", "expires": 1900000000}]
    assert seen == [("reddit_session", "SECRET", 1900000000)]


# A16 lifecycle over the real host pipe and the spawned fake ----------------------------------------------------

def launch(tmp_path, pages):
    script = tmp_path / "script.json"
    script.write_text(json.dumps({"pages": pages, "cookies": [{"name": "a", "value": "v", "expires": 5}]}))
    h.write_admission(tmp_path, BINARY, h.executable_version(BINARY), outcome="tested_clean", destination_classes=[])
    host = h.BrowserHost(BINARY, tmp_path / "profiles", cache_root=tmp_path, policy=p.ProfilePolicy(True, True),
                         spawn=lambda argv: spawn_launcher(FAKE, *argv[1:], f"--fake-script={script}"),
                         memory=lambda: 9999)
    return host.launch("a", "a", 12345)


@pytest.mark.skipif(os.name != "nt", reason="native job-object launch is Windows-only (S-BrowserHost deviation)")
def test_real_pipe_round_trip_capture_and_eviction(tmp_path):
    small = "https://www.reddit.com/r/solana/new/"
    large = "https://www.reddit.com/r/solana/comments/abc123/"
    away = "https://www.reddit.com/r/CryptoCurrency/new/"
    pages = {small: {"body": json.dumps({"k": 1})}, large: {"body": "x" * 70000},
             away: {"final_url": "https://evil.example/"}}
    with launch(tmp_path, pages) as session:
        client = cdp.CdpClient(session.pipe, "session_check", REDDIT)
        assert client.version()["product"] == "FakeBrowser/1.0"
        sid = client.open_page()
        client.navigate(sid, small)
        assert client.location_href(sid) == small
        (record,) = [r for r in client.responses() if r.url == small]
        assert record.kind == "data"
        # Network.disable is outside the session_check table.
        with pytest.raises(h.BrowserFailure, match="cdp_method_refused"):
            client.network_disable(sid)
        assert client.cookies(sid, ["https://www.reddit.com/"]) == [{"name": "a", "expires": 5}]
        read = cdp.CdpClient(session.pipe, "reddit_read", REDDIT, max_body_bytes=65536)
        rsid = read.open_page()
        read.navigate(rsid, small)
        rid = [r for r in read.responses() if r.url == small][0].request_id
        assert json.loads(read.body(rsid, rid)) == {"k": 1}
        read.navigate(rsid, large)
        big = [r for r in read.responses() if r.url == large][0].request_id
        with pytest.raises(h.BrowserFailure, match="capture_evicted"):
            read.body(rsid, big)
        with pytest.raises(h.BrowserFailure, match="navigation_off_allowlist"):
            read.navigate(rsid, away)
        # The session is over after a policy end; teardown is the host's job-object close, not CDP.


def test_close_and_close_target_are_typed_commands():
    client, pipe, sid = opened()
    client.close_target("T1")
    with pytest.raises(h.BrowserFailure, match="cdp_session_unknown"):
        client.navigate(sid, "https://www.reddit.com/")
    client.close()
    assert [json.loads(f)["method"] for f in pipe.sent] == ["Target.closeTarget", "Browser.close"]
