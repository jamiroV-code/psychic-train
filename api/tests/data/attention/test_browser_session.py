"""S-Cookie-C acceptance (finish plan CK-1..CK-7): harvest-only session helper core. No installed browser runs.

End-to-end cases use the REAL `browser_host` (native job object), the REAL `browser_relay` (loopback, direct
mode) and the REAL `CdpClient` against the spawned `browser_fake_main`; only the spawn command, memory reader,
clock and the injected seams (DayGuard, RouteProvider) are fakes. The polling loop is additionally driven over an
in-memory pipe with the real `CdpClient` so every serialized frame can be inspected (no `Input.*`).
"""
from __future__ import annotations

import io
import json
import math
import os
import sys
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import pytest

from api.data import cache
from api.data.attention import browser_cdp as cdp
from api.data.attention import browser_host as h
from api.data.attention import browser_profile as p
from api.data.attention import browser_relay as relay
from api.data.attention import browser_session as bs
from api.data.attention import reddit_accounts as ra
from api.tests.data.attention.fixture_seams import spawn_launcher

FAKE = "api.tests.data.attention.browser_fake_main"
BINARY = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32" / "cmd.exe"
NOW = 1_800_000_000.0
DAY = 86400
MARKER = "SECRETMARKER0123456789"
WINDOWS = pytest.mark.skipif(os.name != "nt", reason="native job-object launch is Windows-only (S-BrowserHost)")
X_IN = [{"name": "auth_token", "value": MARKER + "a", "expires": NOW + 40 * DAY},
        {"name": "ct0", "value": MARKER + "c", "expires": NOW + 3 * DAY},
        {"name": "guest_id", "value": MARKER + "g", "expires": NOW + 300 * DAY}]
R_IN = [{"name": "reddit_session", "value": MARKER + "r", "expires": NOW + 20 * DAY},
        {"name": "loid", "value": MARKER + "l", "expires": NOW + 300 * DAY}]


@pytest.fixture(autouse=True)
def _isolated(attention_cache):
    yield


# Injected seams --------------------------------------------------------------------------------------------------

class Guard:
    def __init__(self, answer=True):
        self.calls, self.answer = [], answer

    def try_claim(self, site, label, day):
        self.calls.append((site, label, day))
        return self.answer


class Routes:
    def __init__(self, answer=None):
        self.calls = []
        self.answer = answer if answer is not None else bs.AdmittedRoute(
            "direct", "rev-1", lambda: relay.Admission("rev-1", math.inf))

    def admitted_route(self, site, label):
        self.calls.append((site, label))
        return self.answer


# Real host over the spawned fake ---------------------------------------------------------------------------------

def make_host(tmp_path, *, cookies=(), pages=None, policy=(True, True), memory=9999, admission="tested_clean",
              spawn=None, launches=None):
    script = tmp_path / "script.json"
    script.write_text(json.dumps({"pages": pages or {}, "cookies": list(cookies)}))
    if admission:
        h.write_admission(tmp_path, BINARY, h.executable_version(BINARY), outcome=admission, destination_classes=[])

    def default_spawn(argv):
        if launches is not None:
            launches.append(1)
        return spawn_launcher(FAKE, *argv[1:], f"--fake-script={script}")

    return h.BrowserHost(BINARY, tmp_path / "profiles", cache_root=tmp_path, policy=p.ProfilePolicy(*policy),
                         spawn=spawn or default_spawn, memory=lambda: memory)


def check(host, site="reddit", label="acct1", *, mode="automatic", guard=None, routes=None, **kw):
    return bs.check_session(site, label, host=host, profile_name=label, day_guard=guard or Guard(),
                            routes=routes or Routes(), mode=mode, timeout=30, wall=lambda: NOW,
                            sleep=lambda s: None, **kw)


def secret_free(result):
    text = json.dumps(result.public()) + repr(result) + str(result)
    assert MARKER not in text
    return result


def assert_no_marker_on_disk(root):
    for path in Path(root).rglob("*"):
        if path.is_file() and path.name != "script.json" and path.name != "fake_cookies.json":
            assert MARKER.encode() not in path.read_bytes(), path


# CK-1 classification (pure) --------------------------------------------------------------------------------------

def jar(*pairs):
    return [{"name": n, "expires": e} for n, e in pairs]


@pytest.mark.parametrize("href,cookies,state,reason", [
    ("https://x.com/home", jar(("auth_token", NOW + DAY * 40), ("ct0", NOW + DAY)), "logged_in", None),
    ("https://x.com/home", jar(("auth_token", NOW + DAY)), "login_required", "session_cookie_missing"),
    ("https://x.com/i/flow/login", jar(("auth_token", NOW + DAY), ("ct0", NOW + DAY)), "login_required", "login_page"),
    ("https://x.com/logout", jar(), "login_required", "login_page"),
    ("https://x.com/account/access", jar(("auth_token", NOW + DAY), ("ct0", NOW + DAY)), "challenge", "challenge_page"),
    ("https://x.com/explore", jar(("auth_token", NOW + DAY), ("ct0", NOW + DAY)), "login_required", "not_home"),
    ("https://www.x.com/home", jar(("auth_token", NOW + DAY), ("ct0", NOW + DAY)), "login_required", "host_mismatch"),
])
def test_x_classification(href, cookies, state, reason):
    assert bs.classify("x", href, cookies, NOW)[:2] == (state, reason)


@pytest.mark.parametrize("href,cookies,state,reason", [
    ("https://www.reddit.com/", jar(("reddit_session", NOW + DAY * 20)), "logged_in", None),
    ("https://www.reddit.com:443/", jar(("reddit_session", NOW + DAY * 20)), "logged_in", None),
    ("https://www.reddit.com/", jar(("loid", NOW + DAY)), "login_required", "session_cookie_missing"),
    ("https://www.reddit.com/", jar(("reddit_session", NOW - 1)), "login_required", "session_cookie_expired"),
    ("https://www.reddit.com/", jar(("reddit_session", -1)), "login_required", "session_cookie_expired"),
    ("https://www.reddit.com/login/", jar(("reddit_session", NOW + DAY)), "login_required", "login_page"),
    ("https://www.reddit.com/register/", jar(), "login_required", "login_page"),
    ("https://www.reddit.com/account/suspended/", jar(("reddit_session", NOW + DAY)), "challenge", "challenge_page"),
    ("https://www.reddit.com/verify/", jar(("reddit_session", NOW + DAY)), "challenge", "challenge_page"),
    ("https://www.reddit.com/captcha/", jar(("reddit_session", NOW + DAY)), "challenge", "challenge_page"),
    # Host normalization: only the single normalized host counts (A3); bare/old hosts are off-allowlist.
    ("https://reddit.com/", jar(("reddit_session", NOW + DAY)), "login_required", "host_mismatch"),
    ("https://old.reddit.com/", jar(("reddit_session", NOW + DAY)), "login_required", "host_mismatch"),
    ("https://WWW.REDDIT.COM/", jar(("reddit_session", NOW + DAY)), "login_required", "host_mismatch"),
    ("http://www.reddit.com/", jar(("reddit_session", NOW + DAY)), "login_required", "host_mismatch"),
    ("about:blank", jar(("reddit_session", NOW + DAY)), "login_required", "host_mismatch"),
])
def test_reddit_classification_and_host_normalization(href, cookies, state, reason):
    assert bs.classify("reddit", href, cookies, NOW)[:2] == (state, reason)


@pytest.mark.parametrize("expiries,klass", [
    ((), "absent"), ((-1,), "session"), ((NOW - 5,), "expired"), ((NOW + 3600,), "lt_1d"),
    ((NOW + 3 * DAY,), "lt_7d"), ((NOW + 20 * DAY,), "lt_30d"), ((NOW + 40 * DAY,), "ge_30d"),
    ((NOW + 40 * DAY, NOW + 3600), "lt_1d")])
def test_ck5_expiry_class_is_earliest_required_cookie(expiries, klass):
    cookies = jar(*[("reddit_session", e) for e in expiries])
    assert bs.expiry_class(cookies, ("reddit_session",), NOW)[1] == klass


# CK-1 end to end (real host, real relay, real CDP client, spawned fake) ------------------------------------------

@WINDOWS
def test_x_logged_in_values_only_in_memory_for_caller(tmp_path):
    result = check(make_host(tmp_path, cookies=X_IN), "x")
    assert (result.state, result.reason) == ("logged_in", None)
    assert result.cookie_names_present == ("auth_token", "ct0", "guest_id")
    assert result.earliest_expiry == NOW + 3 * DAY and result.expiry_class == "lt_7d"
    assert {n: v for n, v, _ in result.cookies} == {"auth_token": MARKER + "a", "ct0": MARKER + "c",
                                                     "guest_id": MARKER + "g"}
    secret_free(result)
    assert "cookies" not in result.public()
    assert_no_marker_on_disk(tmp_path)


@WINDOWS
def test_x_logged_out_drops_values(tmp_path):
    pages = {"https://x.com/home": {"final_url": "https://x.com/i/flow/login"}}
    result = check(make_host(tmp_path, cookies=X_IN[1:], pages=pages), "x")
    assert (result.state, result.reason, result.cookies) == ("login_required", "login_page", ())


@WINDOWS
def test_reddit_logged_in_values_discarded_at_parse(tmp_path):
    result = secret_free(check(make_host(tmp_path, cookies=R_IN)))
    assert (result.state, result.reason, result.cookies) == ("logged_in", None, ())
    assert result.cookie_names_present == ("loid", "reddit_session")
    assert result.expiry_class == "lt_30d"
    assert_no_marker_on_disk(tmp_path)


@WINDOWS
@pytest.mark.parametrize("final,cookies,state,reason", [
    ("https://www.reddit.com/", R_IN[1:], "login_required", "session_cookie_missing"),
    ("https://www.reddit.com/", [dict(R_IN[0], expires=NOW - 60)], "login_required", "session_cookie_expired"),
    ("https://www.reddit.com/login/", R_IN, "login_required", "login_page"),
    ("https://www.reddit.com/account/suspended/", R_IN, "challenge", "challenge_page"),
    ("https://www.reddit.com/captcha/", R_IN, "challenge", "challenge_page"),
    # A redirect to bare reddit.com is an off-allowlist navigation: the CDP client ends the session.
    ("https://reddit.com/", R_IN, "login_required", "navigation_off_allowlist"),
])
def test_reddit_states_stop_without_retry(tmp_path, final, cookies, state, reason):
    launches = []
    pages = {"https://www.reddit.com/": {"final_url": final}}
    result = secret_free(check(make_host(tmp_path, cookies=cookies, pages=pages, launches=launches)))
    assert (result.state, result.reason) == (state, reason)
    assert len(launches) == 1  # never retried, never relaunched


@WINDOWS
def test_ac1_profile_isolation_and_restart_persistence(tmp_path):
    host = make_host(tmp_path, cookies=R_IN)
    assert check(host, label="acct1").state == "logged_in"
    first = (tmp_path / "profiles" / "acct1" / "fake_identity.json").read_text()
    assert check(host, label="acct1", guard=Guard()).state == "logged_in"
    assert (tmp_path / "profiles" / "acct1" / "fake_identity.json").read_text() == first
    assert check(host, label="acct2").state == "logged_in"
    assert (tmp_path / "profiles" / "acct2" / "fake_identity.json").read_text() != first
    assert not (tmp_path / "attention" / "_pc_state" / "browser_launches" / "acct1.json").exists()


# CK-7 refused outcome --------------------------------------------------------------------------------------------

@WINDOWS
@pytest.mark.parametrize("kw,reason", [
    ({"policy": (False, False)}, "profile_policy_unsatisfied"),
    ({"admission": None}, "browser_unadmitted"),
    ({"admission": "containment_residual_unaccepted"}, "containment_residual_unaccepted"),
    ({"memory": 100}, "low_memory"),
])
def test_gates_refuse_and_nothing_else_runs(tmp_path, kw, reason):
    launches = []
    result = check(make_host(tmp_path, cookies=R_IN, launches=launches, **kw))
    assert (result.state, result.reason) == ("refused", reason)
    assert launches == [] and result.cookie_names_present == ()


@WINDOWS
def test_browser_busy_when_the_collector_holds_the_lock(tmp_path):
    launches = []
    host = make_host(tmp_path, cookies=R_IN, launches=launches)
    with h.MachineLock():
        result = check(host)
    assert (result.state, result.reason, launches) == ("refused", "browser_busy", [])


@WINDOWS
def test_cdp_pipe_unavailable_is_refused(tmp_path):
    host = make_host(tmp_path, spawn=lambda argv: [sys.executable, "-c", "pass"])
    result = check(host)
    assert (result.state, result.reason) == ("refused", "cdp_pipe_unavailable")


@pytest.mark.parametrize("answer", ["proxy_not_admitted", "unadmitted", None,
                                    "DEFAULT"])
def test_route_refusal_is_proxy_not_admitted_and_launches_nothing(tmp_path, answer):
    routes = Routes()
    routes.answer = (bs.AdmittedRoute("proxy", "rev-1", lambda: relay.Admission("rev-1", math.inf))
                     if answer == "DEFAULT" else answer)  # proxy mode without a PrivateRoute: relay refuses
    launches = []
    host = make_host(tmp_path, launches=launches) if os.name == "nt" else object()
    result = check(host, routes=routes)
    assert (result.state, result.reason) == ("refused", "proxy_not_admitted")
    assert routes.calls == [("reddit", "acct1")] and launches == []


def test_refused_reason_set_is_exactly_ck7():
    assert set(bs.REFUSED_REASONS) == {"browser_unadmitted", "containment_residual_unaccepted",
                                       "cdp_pipe_unavailable", "profile_policy_unsatisfied", "proxy_not_admitted",
                                       "browser_busy", "low_memory"}
    assert bs.STATES == ("logged_in", "login_required", "challenge", "refused", "failed")


# CK-2 day guard --------------------------------------------------------------------------------------------------

def test_second_automatic_attempt_refused_before_anything_runs(tmp_path):
    guard, routes = Guard(answer=False), Routes()
    result = check(object(), guard=guard, routes=routes)
    assert (result.state, result.reason) == ("failed", "daily_check_used")
    assert guard.calls == [("reddit", "acct1", "2027-01-15")]
    assert routes.calls == []


@WINDOWS
def test_interactive_and_probe_bypass_the_day_guard_and_are_owner_initiated(tmp_path):
    host = make_host(tmp_path, cookies=R_IN)
    for mode in ("interactive", "probe"):
        guard = Guard(answer=False)
        result = check(host, mode=mode, guard=guard)
        assert guard.calls == [] and result.state == "logged_in"
        assert result.owner_initiated is True and result.mode == mode
    assert check(host, guard=Guard()).owner_initiated is False


def _pool(labels=("acct1",)):
    clock = lambda: datetime.fromtimestamp(NOW, timezone.utc)
    return ra.RedditAccounts(list(labels), clock=clock)


def test_real_reddit_day_guard_cli_vs_worker_atomic_and_survives_restart():
    refusal = Routes(answer="proxy_not_admitted")  # claim happens first; refusal keeps the browser out
    results, barrier = [], threading.Barrier(6)

    def claimant():
        barrier.wait()
        results.append(bs.check_session("reddit", "acct1", host=object(), profile_name="acct1",
                                         day_guard=_pool(), routes=refusal, timeout=30, wall=lambda: NOW))

    threads = [threading.Thread(target=claimant) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(r.reason for r in results) == ["daily_check_used"] * 5 + ["proxy_not_admitted"]
    # Restart: a fresh owner instance (new process) still sees today's claim; tomorrow is free again.
    again = bs.check_session("reddit", "acct1", host=object(), profile_name="acct1", day_guard=_pool(),
                             routes=refusal, timeout=30, wall=lambda: NOW)
    assert again.reason == "daily_check_used"
    tomorrow = bs.check_session("reddit", "acct1", host=object(), profile_name="acct1", day_guard=_pool(),
                                routes=refusal, timeout=30, wall=lambda: NOW + DAY)
    assert tomorrow.reason == "proxy_not_admitted"


# Polling over the real CDP client (in-memory pipe) ---------------------------------------------------------------

class ScriptPipe:
    def __init__(self, hrefs, jars):
        self.sent, self.inbox = [], deque()
        self.hrefs, self.jars, self.reads = deque(hrefs), deque(jars), 0

    def send(self, frame):
        self.sent.append(frame)
        message = json.loads(frame)
        method, result = message["method"], {}
        if method == "Target.createTarget":
            result = {"targetId": "T1"}
        elif method == "Target.attachToTarget":
            result = {"sessionId": "S1"}
        elif method == "Runtime.evaluate":
            value = self.hrefs[0] if len(self.hrefs) == 1 else self.hrefs.popleft()
            result = {"result": {"type": "string", "value": value}}
        elif method == "Network.getCookies":
            result = {"cookies": self.jars[0] if len(self.jars) == 1 else self.jars.popleft()}
        reply = {"id": message["id"], "result": result}
        if "sessionId" in message:
            reply["sessionId"] = message["sessionId"]
        self.inbox.append(json.dumps(reply).encode())

    def receive(self, *, timeout=10):
        if not self.inbox:
            raise h.BrowserFailure("cdp_timeout")
        return self.inbox.popleft()

    def methods(self):
        return [json.loads(f)["method"] for f in self.sent]


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def test_owner_interactive_polling_sends_no_input_and_finishes_on_login():
    login = "https://x.com/i/flow/login"
    pipe = ScriptPipe([login, login, login, "https://x.com/home"], [[], [], [], X_IN])
    clock = Clock()
    client = cdp.CdpClient(pipe, "session_check", cdp.UrlPolicy("x"), clock=clock)
    fields = bs.observe(client, "x", interactive=True, timeout=120, clock=clock, sleep=clock.sleep, wall=lambda: NOW)
    assert fields["state"] == "logged_in" and len(fields["cookies"]) == 3
    methods = pipe.methods()
    assert not [m for m in methods if m.startswith("Input.") or m in {"Runtime.callFunctionOn"}]
    assert methods.count("Page.navigate") == 1  # never re-navigates while the owner works
    assert set(methods) <= cdp.METHODS["session_check"]
    assert clock.now <= 120


def test_owner_interactive_polling_stops_at_timeout_with_last_state():
    pipe = ScriptPipe(["https://x.com/account/access"], [[]])
    clock = Clock()
    client = cdp.CdpClient(pipe, "session_check", cdp.UrlPolicy("x"), clock=clock)
    fields = bs.observe(client, "x", interactive=True, timeout=60, clock=clock, sleep=clock.sleep, wall=lambda: NOW)
    assert (fields["state"], fields["reason"], fields["cookies"]) == ("challenge", "challenge_page", ())
    assert 60 <= clock.now <= 65


def test_automatic_check_waits_only_for_the_page_then_classifies_once():
    pipe = ScriptPipe(["about:blank", "about:blank", "https://www.reddit.com/"], [R_IN])
    clock = Clock()
    client = cdp.CdpClient(pipe, "session_check", cdp.UrlPolicy("reddit"), clock=clock)
    fields = bs.observe(client, "reddit", interactive=False, timeout=60, clock=clock, sleep=clock.sleep,
                        wall=lambda: NOW)
    assert fields["state"] == "logged_in" and fields["cookies"] == ()
    assert pipe.methods().count("Network.getCookies") == 1


def test_probe_mode_uses_bootstrap_role_and_records_names_and_expiry_class():
    pipe = ScriptPipe(["https://www.reddit.com/"], [R_IN])
    clock = Clock()
    client = cdp.CdpClient(pipe, bs.ROLES["probe"], cdp.UrlPolicy("reddit"), clock=clock)
    fields = bs.observe(client, "reddit", interactive=False, timeout=60, clock=clock, sleep=clock.sleep,
                        wall=lambda: NOW)
    assert bs.ROLES == {"automatic": "session_check", "interactive": "session_check", "probe": "bootstrap"}
    enable = [json.loads(f) for f in pipe.sent if json.loads(f)["method"] == "Network.enable"][0]
    assert enable["params"]["maxResourceBufferSize"] == cdp.bounds("bootstrap").resource
    assert fields["cookie_names_present"] == ("loid", "reddit_session") and fields["expiry_class"] == "lt_30d"


# CLI -------------------------------------------------------------------------------------------------------------

class Cfg:
    browser_path = None
    browser_profiles_dir = None
    x_account_profiles = {"xacct": "xprofile"}
    reddit_browser_accounts = ({"label": "acct1", "profile": "rprofile"},)
    reddit_browser_account_daily_cap = 200
    reddit_browser_account_rest_days = 0
    x_harvest_timeout_s = 120
    browser_memory_floor_mb = 1536
    browser_rss_ceiling_mb = 1200
    x_proxy_required = False


def test_cli_x_automatic_without_wired_guard_fails_closed_and_prints_codes_only():
    out = io.StringIO()
    code = bs.main(["--site", "x", "--label", "xacct"], config=Cfg(), out=out)
    line = json.loads(out.getvalue())
    assert code == 2 and line["state"] == "failed" and line["reason"] == "day_guard_unavailable"


def test_cli_unconfigured_browser_or_label_fails_closed():
    out = io.StringIO()
    assert bs.main(["--site", "reddit", "--label", "nobody", "--interactive"], config=Cfg(), out=out) == 2
    assert json.loads(out.getvalue())["reason"] == "label_unconfigured"
    out = io.StringIO()
    assert bs.main(["--site", "reddit", "--label", "acct1", "--interactive"], config=Cfg(), out=out) == 2
    assert json.loads(out.getvalue())["reason"] == "browser_not_configured"


def test_cli_default_route_provider_is_default_deny():
    assert bs.DENY_ROUTES.admitted_route("reddit", "acct1") == "proxy_not_admitted"
    assert bs.DENY_ROUTES.admitted_route("x", "acct1") == "proxy_not_admitted"


@WINDOWS
def test_cli_interactive_reddit_with_injected_host_prints_one_secret_free_line(tmp_path):
    out = io.StringIO()
    host = make_host(tmp_path, cookies=R_IN)
    code = bs.main(["--site", "reddit", "--label", "acct1", "--interactive"], config=Cfg(), host=host,
                   routes=Routes(), out=out)
    assert code == 0 and MARKER not in out.getvalue()
    line = json.loads(out.getvalue())
    assert line["state"] == "logged_in" and line["owner_initiated"] is True and "cookies" not in line


@WINDOWS
def test_cli_init_profile_creates_the_profile_via_a10(tmp_path):
    out = io.StringIO()
    host = make_host(tmp_path)
    assert bs.main(["--site", "reddit", "--label", "acct1", "--init-profile"], config=Cfg(), host=host, out=out) == 0
    assert (tmp_path / "profiles" / "rprofile").is_dir()
    assert json.loads(out.getvalue()) == {"site": "reddit", "label": "acct1", "profile": "created"}

def test_cli_private_config_loads_selected_path(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from api.data.attention import web_queries
    seen = []
    config = SimpleNamespace(x_proxy_required=False, x_proxy_list_path=None,
        x_proxy_assignments_path=None, x_proxy_policy_path=None, reddit_browser_accounts=())
    monkeypatch.setattr(web_queries, "load", lambda path=None: (
        seen.append(path) or SimpleNamespace(config=config)))
    path = tmp_path / "private.json"
    out = io.StringIO()
    assert bs.main(["--site", "reddit", "--label", "absent", "--queries", str(path)], out=out) == 2
    assert seen == [path]
    assert "label_unconfigured" in out.getvalue()


@pytest.mark.parametrize("kind", ["relative", "repository"])
def test_cli_private_config_rejects_unsafe_path(kind):
    from api.data.attention import web_queries
    path = "private.json" if kind == "relative" else str(web_queries.QUERIES_PATH)
    with pytest.raises(SystemExit) as exc:
        bs.main(["--site", "reddit", "--label", "a", "--queries", path])
    assert exc.value.code == 2
