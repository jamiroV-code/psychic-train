"""S-RBrowser (BR-1..BR-6): the PRIMARY Reddit browser method. No installed browser, no network.

The surface is the synthetic capture-to-surface workflow (`surface_tool.propose` over the synthetic captures of
`reddit_probe_fixtures`). Unit cases drive the method through the loopback PR2 driver seam (`FakeDriver`); the
end-to-end cases use the REAL host (job object), REAL relay (loopback, direct), REAL `CdpClient` and the REAL Reddit
route provider (`RedditRoutes` over the B2 `ProxyRuntime`, all-null direct configuration) against the spawned
`browser_fake_main` serving the same synthetic bodies.
"""
from __future__ import annotations

import dataclasses
import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from api.data import cache
from api.data.attention import browser_session as bs
from api.data.attention import reddit_accounts as ra
from api.data.attention import reddit_browser as rb
from api.data.attention import reddit_core as rc
from api.data.attention import reddit_items
from api.data.attention import reddit_live as rl
from api.data.attention import reddit_surface as rs
from api.data.attention import web_queries as wq
from api.scripts import probe_owner as po
from api.scripts import surface_tool as st
from api.tests.scripts import reddit_probe_fixtures as fx

BASE = fx.BASE
NOW = datetime.fromtimestamp(BASE + 600, timezone.utc)
FLOOR = datetime(2026, 10, 25, tzinfo=timezone.utc)
SUBS = ("bitcoin", "ethereum")
SALT = b"0123456789abcdef0123456789abcdef"
LABELS = ("ra_one", "ra_two")
WINDOWS = pytest.mark.skipif(os.name != "nt", reason="native job-object launch is Windows-only (S-BrowserHost)")


@pytest.fixture(autouse=True)
def _isolated(attention_cache):
    return attention_cache


def section_raw():
    p = st.propose("browser", fx.bootstrap_captures(SUBS), subreddits=SUBS)
    assert p.ok, p.reasons
    return p.section


def write_surface(tmp_path, raw=None):
    raw = section_raw() if raw is None else raw
    raw = {**raw, "sha256": rs.section_sha256(raw)}
    path = tmp_path / "surface.json"
    path.write_text(json.dumps({"sections": {"browser": raw}}), encoding="utf-8")
    return path, rs.load_section("browser", raw)


def record(section, *, mode="verify", day=NOW.date(), outcome="pass", sha=None, revision=None):
    po.write_record(cache.CACHE_ROOT, po.make_record(
        probe_id="PR2", mode=mode, date_utc=day.isoformat(), commit="a" * 40, egress_class="direct",
        outcome=outcome, section="browser", section_sha256=sha or section.sha256,
        surface_revision=revision or section.revision, counts=dict.fromkeys(po.COUNTS, 0), reason_codes=[],
        limits_hit=[]))


def config(path, **over):
    base = wq.load().config
    fields = dict(reddit_live_methods=("browser",), reddit_surface_path=str(path), reddit_live_probe_max_age_days=7,
                  reddit_browser_accounts=tuple({"label": x, "profile": x} for x in LABELS),
                  reddit_browser_account_rest_days=0, reddit_browser_account_daily_cap=200,
                  reddit_browser_daily_minutes=90, reddit_browser_daily_navigation_cap=400, x_accounts=(),
                  x_proxy_required=False, x_proxy_list_path=None, x_proxy_assignments_path=None,
                  x_proxy_policy_path=None)
    fields.update(over)
    return dataclasses.replace(base, **fields)


def mark_ready(*labels):
    for x in labels:
        ra.write_ready(x, NOW - timedelta(days=2), labels=LABELS)


class LoginDriver(fx.FakeDriver):
    def navigate(self, url):
        self.actions.append(("navigate", url))
        return "login_required"


class Sessions:
    """The sessions seam: one in-memory driver per account; optional refusal (busy host, unadmitted browser)."""

    def __init__(self, drivers=None, refuse=None):
        self.drivers = drivers if drivers is not None else {x: fx.FakeDriver() for x in LABELS}
        self.refuse, self.opened = refuse, []

    @contextmanager
    def open(self, label, *, role, section, subreddits):
        self.opened.append((label, role, tuple(subreddits)))
        if self.refuse:
            raise rb.Refused(self.refuse)
        yield self.drivers[label]


class Mono:
    def __init__(self, step=1.0):
        self.t, self.step = 0.0, step

    def __call__(self):
        self.t += self.step
        return self.t


def method(path, sessions=None, **over):
    q = wq.load()
    deps = SimpleNamespace(clock=lambda: NOW, reddit_sessions=sessions or Sessions(), browser_admission=lambda: None,
                           hasher=reddit_items.AuthorHasher(SALT), queries=lambda: q, monotonic=Mono())
    return rb.make_method(config(path, **over), deps)


def ctx(threads=(), left=400, subs=SUBS):
    return rl.PollContext(NOW, subs, {s: FLOOR for s in subs}, tuple(threads), left)


@pytest.fixture
def ready(tmp_path):
    path, section = write_surface(tmp_path)
    record(section)
    mark_ready(*LABELS)
    return path, section


# --- BR-1 gate --------------------------------------------------------------------------------------------------

def test_gate_ready_only_with_fresh_matching_verify_record_and_a_ready_account(tmp_path):
    path, section = write_surface(tmp_path)
    m = method(path)
    assert m.gate_state(NOW) == "needs_probe"  # no record
    record(section, mode="bootstrap", sha=None)
    assert m.gate_state(NOW) == "needs_probe"  # bootstrap-only
    record(section, day=NOW.date() - timedelta(days=9))
    assert m.gate_state(NOW) == "needs_probe"  # stale
    record(section, sha="b" * 64, day=NOW.date() - timedelta(days=1))
    assert m.gate_state(NOW) == "needs_probe"  # hash mismatch
    record(section, outcome="fail")
    assert m.gate_state(NOW) == "needs_probe"
    record(section)
    assert m.gate_state(NOW) == "no_ready_account"  # owner has not marked an account ready
    mark_ready("ra_two")
    assert m.gate_state(NOW) == "ready"


def test_gate_disabled_unconfigured_unadmitted_and_unsupported(ready, tmp_path):
    path, _ = ready
    assert method(path, reddit_live_methods=()).gate_state(NOW) == "disabled"
    assert method(path, reddit_surface_path=None).gate_state(NOW) == "needs_probe"
    m = rb.make_method(config(path, browser_path=None, browser_profiles_dir=None),
                       SimpleNamespace(clock=lambda: NOW))
    assert m.gate_state(NOW) == "method_unavailable"
    for reason in ("browser_unadmitted", "containment_residual_unaccepted"):
        m = method(path)
        m._admission = lambda reason=reason: reason
        assert m.gate_state(NOW) == reason
    raw = {**section_raw(), "body_format": "html"}
    bad, _ = (tmp_path / "x.json", None)
    bad.write_text(json.dumps({"sections": {"browser": raw}}), encoding="utf-8")
    assert method(bad).gate_state(NOW) == "unsupported_format"


def test_logged_out_or_proxy_required_accounts_are_not_ready(ready):
    path, _ = ready
    m = method(path)
    pool = m.routes.refresh()
    for x in LABELS:
        pool.record_session(x, "logged_out")
    assert m.gate_state(NOW) == "no_ready_account"
    assert pool.account_state("ra_one") == ("paused", "reddit_login_required")
    assert method(path, x_proxy_required=True).gate_state(NOW) == "no_ready_account"


def test_admission_state_reads_the_binary_record(tmp_path):
    from api.tests.data.attention.test_browser_session import BINARY
    cfg = config(tmp_path / "s.json", browser_path=str(BINARY))
    from api.data.attention import browser_host as h
    assert rb.admission_state(cfg) == "browser_unadmitted"
    h.write_admission(cache.CACHE_ROOT, BINARY, h.executable_version(BINARY), outcome="tested_clean",
                      destination_classes=[])
    assert rb.admission_state(cfg) is None


# --- BR-2 evidence state machine ----------------------------------------------------------------------------------

def test_posts_cursor_chain_to_exhaustion_and_threads_opened(ready):
    path, section = ready
    sess = Sessions()
    m = method(path, sess)
    result = m.run_poll(ctx(threads=("t3_bi0p",)))
    posts = {lane.subreddit: lane for lane in result.lanes if lane.kind == "posts"}
    assert {s: (lane.stop_reason, lane.pages, len(lane.cursor_chain)) for s, lane in posts.items()} == {
        "bitcoin": ("exhausted", 3, 3), "ethereum": ("exhausted", 3, 3)}
    assert posts["bitcoin"].items_seen == 36 and posts["bitcoin"].threads[0] == ("t3_bi0p", 2)
    comments = [lane for lane in result.lanes if lane.kind == "comments"]
    assert [(c.subreddit, c.stop_reason, c.threads, c.items_seen) for c in comments] == [
        ("bitcoin", "exhausted", (("t3_bi0p", 2),), 2)]
    assert result.navigations == 3 and m.last_account == "ra_one"
    assert sess.opened == [("ra_one", "reddit_read", SUBS)]
    actions = sess.drivers["ra_one"].actions
    assert [a for a in actions if a[0] == "navigate"] == [
        ("navigate", "https://www.reddit.com/r/bitcoin/new/"), ("navigate", "https://www.reddit.com/r/ethereum/new/"),
        ("navigate", "https://www.reddit.com/r/bitcoin/comments/bi0p/")]
    assert m.routes.accounts.reads_today("ra_one") == 3
    assert len(result.items) == 74 and all(isinstance(i, rc.LiveItem) for i in result.items)


def test_cursor_chain_needs_request_response_correlation(ready):
    _, section = ready

    class Shuffled(fx.FakeDriver):
        def drain(self):  # page 2 arrives with a forged cursor: the chain cannot continue
            out = super().drain()
            return [dataclasses.replace(c, url=c.url.replace("after=", "after=zz")) for c in out]

    d = Shuffled()
    chain = rb.read_chain(d, section, "posts", rb.listing_url("bitcoin"), budget=rb.PollBudget(5, 60),
                          max_pages=40, floor=FLOOR)
    assert (chain.stop, len(chain.pages)) == ("error", 1)


@pytest.mark.parametrize("driver,stop", [
    (fx.FakeDriver(status=500), "error"),
    (fx.FakeDriver(body_bytes=300), "empty_shell"),
    (fx.FakeDriver(pages=60), "cap"),  # 12 scrolls per page, then the lane is capped (never exhausted)
])
def test_every_lane_stop_reason(ready, driver, stop):
    _, section = ready
    chain = rb.read_chain(driver, section, "posts", rb.listing_url("bitcoin"), budget=rb.PollBudget(5, 600),
                          max_pages=40, floor=FLOOR)
    assert chain.stop == stop


def test_schema_mismatch_unsupported_format_and_block_page(ready):
    _, section = ready

    class Bodies(fx.FakeDriver):
        def __init__(self, doc=None, ctype="application/json", url=None):
            super().__init__()
            self.doc, self.ctype, self.url = doc, ctype, url

        def drain(self):
            out = super().drain()
            return [fx.capture(self.url or c.url, self.doc if self.doc is not None else json.loads(c.body),
                               ctype=self.ctype) for c in out]

    def run(d):
        return rb.read_chain(d, section, "posts", rb.listing_url("bitcoin"), budget=rb.PollBudget(5, 600),
                             max_pages=40, floor=FLOOR).stop

    broken = fx.listing("bitcoin", 0)
    broken["data"]["children"][0]["data"]["created_utc"] = "yesterday"
    assert run(Bodies(broken)) == "schema_mismatch"
    assert run(Bodies(ctype="text/html")) == "unsupported_format"
    # HTTP 200 block page in place of the listing: no matching response, an error state, never zero
    assert run(Bodies({"blocked": True}, url="https://www.reddit.com/blocked")) == "empty_shell"


def test_floor_ends_the_chain_and_older_items_stay_out(ready):
    _, section = ready
    floor = datetime.fromtimestamp(BASE - 15 * 60, timezone.utc)
    chain = rb.read_chain(fx.FakeDriver(), section, "posts", rb.listing_url("bitcoin"),
                          budget=rb.PollBudget(5, 600), max_pages=40, floor=floor)
    assert (chain.stop, len(chain.pages)) == ("exhausted", 2)


# --- BR-3 budgets -------------------------------------------------------------------------------------------------

def test_daily_navigation_and_account_caps(ready):
    path, _ = ready
    m = method(path)
    result = m.run_poll(ctx(threads=("t3_bi0p",), left=1))
    assert [(lane.subreddit, lane.stop_reason) for lane in result.lanes] == [("bitcoin", "exhausted"),
                                                                            ("ethereum", "cap")]
    assert result.navigations == 1
    m = method(path, reddit_browser_account_daily_cap=3)
    m.routes.refresh().charge("ra_one", 1)  # 1 from the first poll + 1: one navigation left under the cap
    m.routes.refresh().charge("ra_two", 3)  # ra_two is capped: locked, never selected
    result = m.run_poll(ctx())
    assert m.last_account == "ra_one" and result.navigations == 1


def test_browser_minutes_are_persisted_and_defer_the_next_poll(ready):
    path, _ = ready
    m = method(path, reddit_browser_daily_minutes=10)
    m.monotonic = Mono(step=400.0)
    m.run_poll(ctx())
    assert rb.read_browser_state(NOW)["seconds"] >= 600
    assert m.next_poll_due(NOW) == datetime(2026, 10, 27, tzinfo=timezone.utc)
    result = m.run_poll(ctx())
    assert {lane.stop_reason for lane in result.lanes} == {"cap"} and result.navigations == 0


def test_busy_host_waits_behind_the_harvest_lock(ready):
    path, _ = ready
    m = method(path, Sessions(refuse="browser_busy"))
    result = m.run_poll(ctx())
    assert result.lanes == () and result.navigations == 0
    assert m.next_poll_due(NOW) == NOW + timedelta(seconds=rb.BUSY_RETRY_S)
    assert m.gate_state(NOW) == "ready"


def test_session_refusal_is_a_gate_state_for_an_hour(ready):
    path, _ = ready
    m = method(path, Sessions(refuse="cdp_pipe_unavailable"))
    m.run_poll(ctx())
    assert m.gate_state(NOW) == "cdp_pipe_unavailable"
    assert m.gate_state(NOW + timedelta(seconds=rb.REFUSAL_HOLD_S + 1)) == "ready"


# --- BR-4 accounts in operation -----------------------------------------------------------------------------------

def test_login_required_pauses_the_account_and_retries_once_on_another(ready):
    path, _ = ready
    sess = Sessions({"ra_one": LoginDriver(), "ra_two": fx.FakeDriver()})
    m = method(path, sess)
    result = m.run_poll(ctx())
    assert [o[0] for o in sess.opened] == ["ra_one", "ra_two"] and m.last_account == "ra_two"
    assert {lane.stop_reason for lane in result.lanes} == {"exhausted"}
    assert result.navigations == 3  # the lost attempt's navigation stays charged
    pool = m.routes.refresh()
    assert pool.account_state("ra_one") == ("paused", "reddit_login_required")
    assert pool.reads_today("ra_one") == 1
    from api.data.attention import daily_facts
    events = daily_facts.read_events(NOW.date())
    assert [(e["kind"], e["account"], e["class"]) for e in events if e["kind"] == "challenge"] == [
        ("challenge", "ra_one", "login_required")]


def test_both_accounts_lost_is_login_required_never_zero(ready):
    path, _ = ready
    sess = Sessions({"ra_one": LoginDriver(), "ra_two": fx.FakeDriver(challenge=True)})
    m = method(path, sess)
    result = m.run_poll(ctx())
    assert {lane.stop_reason for lane in result.lanes} == {"login_required"} and result.failed
    pool = m.routes.refresh()
    assert pool.account_state("ra_two") == ("paused", "challenge")
    assert m.gate_state(NOW) == "no_ready_account"
    pool.record_session("ra_one", "logged_in")  # owner relogin (`browser_session --interactive`) reopens it
    assert m.gate_state(NOW) == "ready"


def test_unadmitted_route_pauses_the_route_not_the_session(ready):
    path, _ = ready

    class NoRoute(Sessions):
        @contextmanager
        def open(self, label, **kw):
            self.opened.append((label,))
            if label == "ra_one":
                raise rb.Lost("proxy_not_admitted")
            yield self.drivers[label]

    m = method(path, NoRoute())
    result = m.run_poll(ctx())
    assert m.last_account == "ra_two" and {lane.stop_reason for lane in result.lanes} == {"exhausted"}


# --- routes: the real Reddit provider over the B2 runtime --------------------------------------------------------

def test_reddit_routes_direct_only_under_the_all_null_configuration(ready):
    path, _ = ready
    routes = rb.RedditRoutes(config(path))
    assert routes.route_admission("reddit", "ra_one") == "unadmitted"  # before reconciliation: default deny
    assert routes.admitted_route("reddit", "ra_one") == "proxy_not_admitted"
    routes.refresh()
    assert routes.route_admission("reddit", "ra_one") == "direct"
    route = routes.admitted_route("reddit", "ra_one")
    assert isinstance(route, bs.AdmittedRoute) and route.mode == "direct" and route.admission().revision
    assert routes.admitted_route("x", "ra_one") == "proxy_not_admitted"
    assert routes.admitted_route("reddit", "nobody") == "proxy_not_admitted"
    assert "ra_one" not in repr(routes)
    hosts = rb._Hosts(routes, ("www.reddit.com",)).admitted_route("reddit", "ra_one")
    assert hosts.hosts == ("www.reddit.com",)


def test_reddit_routes_refuse_when_proxies_are_required_or_unreadable(ready):
    path, _ = ready
    routes = rb.RedditRoutes(config(path, x_proxy_required=True))
    routes.refresh()  # proxy required without the private files: ProxyFailure -> every label unadmitted
    assert routes.route_admission("reddit", "ra_one") == "unadmitted"
    assert routes.admitted_route("reddit", "ra_one") == "proxy_not_admitted"


def test_reddit_routes_proxy_mode_uses_the_admitted_assignment(ready):
    path, _ = ready
    from api.data.attention import browser_relay as relay
    from api.data.attention.x_proxy_runtime import Admission, Snapshot

    cfg = config(path)
    clock = [NOW]

    class Runtime:
        def __init__(self):
            self.snapshot = Snapshot(cfg, object(), {}, {"ra_one": "rev-a"}, None, None,
                                     {"ra_one": SimpleNamespace(route="private-route", proxy_id="p1")})
            self.admissions, self.clock = {}, lambda: clock[0]

        def admitted(self, label):
            a = self.admissions.get(label)
            return bool(a and a.revision == "rev-a" and a.checked_at <= clock[0] < a.expires_at)

        def route_admission(self, site, label):
            return "proxy" if self.admitted(label) else "unadmitted"

        def reconcile(self, pool, *, reddit=None):
            assert reddit is not None and isinstance(pool, rb._XUntouched)
            return set()

        def admit(self, label, view):
            self.admissions[label] = Admission("p1", "rev-a", NOW, NOW + timedelta(hours=1))

    rt = Runtime()
    routes = rb.RedditRoutes(cfg, runtime=rt)
    routes.refresh()
    assert routes.admitted_route("reddit", "ra_one") == "proxy_not_admitted"
    assert routes.admittable("ra_one") and not routes.admittable("ra_two")
    routes.admit("ra_one")
    route = routes.admitted_route("reddit", "ra_one")
    assert (route.mode, route.revision, route.route) == ("proxy", "rev-a", "private-route")
    assert isinstance(route.admission(), relay.Admission)
    clock[0] = NOW + timedelta(hours=2)  # admission expired: the relay's next CONNECT is refused
    assert route.admission() is None


# --- BR-5 honesty, values, secrets ---------------------------------------------------------------------------------

def test_values_are_labelled_reddit_live_browser_and_hold_no_text(ready, tmp_path):
    path, _ = ready
    m = method(path)
    result = m.run_poll(ctx(threads=("t3_bi0p",)))
    rl.record_poll(rb.STORE, result)
    assert rb.STORE == "reddit_live_browser" and m.label == rc.LABELS["browser"]
    assert rc.read_items(rb.STORE, BASE_DAY())
    assert rl.read_lanes(rb.STORE, NOW.date(), NOW.date())
    planted = [fx.SECRET_MARK, "user1", "commenter2"]
    files = [p for p in cache.CACHE_ROOT.rglob("*") if p.is_file() and p.parent != tmp_path]
    assert files
    for p in files:
        text = p.read_text(encoding="utf-8", errors="replace")
        assert not [s for s in planted if s in text], p.name
    assert not [s for s in planted if s in repr(result) + repr(m)]


def BASE_DAY():
    return datetime.fromtimestamp(BASE, timezone.utc).date()


def test_factory_table_resolves_the_browser_method(ready):
    path, _ = ready
    methods = rc.resolve_methods(config(path), SimpleNamespace(clock=lambda: NOW))
    assert isinstance(methods["browser"], rb.BrowserMethod)
    assert isinstance(methods["browser"], rl.LiveMethod)


# --- end to end over the spawned fake browser ---------------------------------------------------------------------

def fake_pages(subs=SUBS):
    pages = {}
    for sub in subs:
        caps = [{"url": fx.listing_url(sub, p), "body": json.dumps(fx.listing(sub, p))} for p in range(3)]
        pages[rb.listing_url(sub)] = {"body": "{}", "xhr": caps[:1], "scrolls": [[c] for c in caps[1:]]}
    pages[rb.thread_url("bitcoin", "t3_bi0p")] = {"body": "{}", "xhr": [
        {"url": f"{fx.HOST}/svc/r/bitcoin/comments/bi0p.json", "body": json.dumps(fx.thread("bitcoin", 0))}]}
    return pages


def e2e(path, tmp_path, cookies):
    from api.tests.data.attention import test_browser_session as tbs
    host = tbs.make_host(tmp_path, cookies=cookies, pages=fake_pages())
    cfg = config(path, browser_path=str(tbs.BINARY), browser_profiles_dir=str(tmp_path / "profiles"))
    q = wq.load()
    routes = rb.RedditRoutes(cfg)
    sessions = rb.BrowserSessions(cfg, host=host, routes=routes, sleep=lambda s: None, wall=lambda: tbs.NOW)
    deps = SimpleNamespace(clock=lambda: NOW, reddit_routes=routes, reddit_sessions=sessions,
                           hasher=reddit_items.AuthorHasher(SALT), queries=lambda: q)
    return rb.make_method(cfg, deps), tbs


@WINDOWS
def test_end_to_end_real_host_cdp_relay_and_route_provider(ready, tmp_path):
    path, _ = ready
    from api.tests.data.attention import test_browser_session as tbs
    m, tbs = e2e(path, tmp_path, tbs.R_IN)
    from api.data.attention import browser_host as h
    h.write_admission(cache.CACHE_ROOT, tbs.BINARY, h.executable_version(tbs.BINARY), outcome="tested_clean",
                      destination_classes=[])
    assert m.gate_state(NOW) == "ready"
    result = m.run_poll(ctx(threads=("t3_bi0p",)))
    assert [(lane.subreddit, lane.kind, lane.stop_reason, lane.pages) for lane in result.lanes] == [
        ("bitcoin", "posts", "exhausted", 3), ("ethereum", "posts", "exhausted", 3),
        ("bitcoin", "comments", "exhausted", 1)]
    assert result.navigations == 3 and m.last_account == "ra_one"
    rl.record_poll(rb.STORE, result)
    for p in cache.CACHE_ROOT.rglob("*"):
        if p.is_file() and p.name not in ("script.json", "fake_cookies.json"):
            assert tbs.MARKER.encode() not in p.read_bytes() and fx.SECRET_MARK.encode() not in p.read_bytes()


@WINDOWS
def test_end_to_end_logged_out_profile_pauses_both_accounts(ready, tmp_path):
    path, _ = ready
    from api.tests.data.attention import test_browser_session as tbs
    m, tbs = e2e(path, tmp_path, [c for c in tbs.R_IN if c["name"] != "reddit_session"])
    result = m.run_poll(ctx())
    assert {lane.stop_reason for lane in result.lanes} == {"login_required"}
    pool = m.routes.refresh()
    assert [pool.account_state(x) for x in LABELS] == [("paused", "reddit_login_required")] * 2
