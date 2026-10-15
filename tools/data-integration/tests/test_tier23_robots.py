"""AC-6: robots.txt is fetched over loopback BEFORE any navigation; blocked, unreachable or unparsable -> zero navigations."""
from __future__ import annotations

import socket

import pytest

from data_integration import status as st
from data_integration.approvals import ApprovalStore
from data_integration.fetch_tier2 import BrowserResponse, fetch as fetch2
from data_integration.fetch_tier3 import fetch as fetch3
from data_integration.gate import FetchPass, request_access
from data_integration.politeness import Politeness
from plugin_fixture_server import fixture_server  # noqa: F401
from _helpers import fixed_clock, make_record
from fixture_server import OK_BODY

HOSTS = ("example.test", "robots-disallow.test", "robots-500.test", "robots-garbage.test", "robots-hang.test")


class Stub:
    def __init__(self, server=None):
        self.server = server
        self.calls = 0
        self.robots_seen_first = None

    def __call__(self, url, pass_, options, timeout, proxy):
        self.calls += 1
        if self.server is not None:
            self.robots_seen_first = self.server.paths()[:1] == ["/robots.txt"]
        return BrowserResponse(200, OK_BODY)


def _pass(tmp_path, tier):
    store = ApprovalStore(tmp_path / "ap")
    store.write(make_record(tier=tier, hosts=HOSTS, pages=("/data/",)))
    p = request_access("example-src", tier, store, fixed_clock())
    assert isinstance(p, FetchPass)
    return p


def _call(tier, url, pass_, nav, proxy, **kw):
    kw.setdefault("politeness", Politeness(min_delay=0, sleeper=lambda s: None))
    fn = fetch2 if tier == 2 else fetch3
    return fn(url, pass_, navigator=nav, proxy=proxy, **kw)


@pytest.mark.parametrize("tier", [2, 3])
def test_robots_fetched_before_navigation(fixture_server, tmp_path, tier):
    nav = Stub(fixture_server)
    out = _call(tier, "http://example.test/data/ok", _pass(tmp_path, tier), nav, fixture_server.proxy_url)
    assert out.status == st.OK and nav.calls == 1 and nav.robots_seen_first is True


@pytest.mark.parametrize("tier", [2, 3])
@pytest.mark.parametrize("host", ["robots-disallow.test", "robots-500.test", "robots-garbage.test"])
def test_blocked_or_unparsable_robots_means_zero_navigations(fixture_server, tmp_path, tier, host):
    nav = Stub()
    out = _call(tier, f"http://{host}/data/ok", _pass(tmp_path, tier), nav, fixture_server.proxy_url)
    assert out.status == st.ROBOTS_BLOCKED and nav.calls == 0
    assert fixture_server.paths() == ["/robots.txt"]


@pytest.mark.parametrize("tier", [2, 3])
def test_slow_robots_means_zero_navigations(fixture_server, tmp_path, tier):
    nav = Stub()
    out = _call(tier, "http://robots-hang.test/data/ok", _pass(tmp_path, tier), nav, fixture_server.proxy_url, timeout=0.5)
    assert out.status == st.ROBOTS_BLOCKED and nav.calls == 0


@pytest.mark.parametrize("tier", [2, 3])
def test_unreachable_robots_means_zero_navigations(fixture_server, tmp_path, tier):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        dead = f"http://127.0.0.1:{s.getsockname()[1]}"
    nav = Stub()
    out = _call(tier, "http://example.test/data/ok", _pass(tmp_path, tier), nav, dead, timeout=2.0)
    assert out.status == st.ROBOTS_BLOCKED and nav.calls == 0
