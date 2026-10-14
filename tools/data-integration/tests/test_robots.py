"""robots.txt: needs a pass, per-hop, fail closed, shares UA/politeness/logging."""
from __future__ import annotations

import pytest

from data_integration.approvals import ApprovalStore
from data_integration.fetch_tier1 import HttpClient
from data_integration.gate import FetchPass, request_access
from data_integration.politeness import USER_AGENT, Politeness
from data_integration.robots import RobotsChecker
from plugin_fixture_server import fixture_server  # noqa: F401
from _helpers import fixed_clock, make_record

HOSTS = ("example.test", "robots-disallow.test", "robots-500.test", "robots-garbage.test", "robots-hang.test")


def _pass(tmp_path):
    store = ApprovalStore(tmp_path / "ap")
    store.write(make_record(tier=1, hosts=HOSTS, pages=("/data/",)))
    p = request_access("example-src", 1, store, fixed_clock())
    assert isinstance(p, FetchPass)
    return p


def _checker(server, timeout=5.0):
    pol = Politeness(min_delay=0, sleeper=lambda s: None)
    client = HttpClient(proxy=server.proxy_url, timeout=timeout, politeness=pol, tier=1)
    return RobotsChecker(client)


def test_allowed_when_robots_allows(fixture_server, tmp_path):
    ok, _ = _checker(fixture_server).allowed("http://example.test/data/ok", _pass(tmp_path))
    assert ok
    assert fixture_server.paths("example.test") == ["/robots.txt"]


def test_disallow_blocks(fixture_server, tmp_path):
    ok, detail = _checker(fixture_server).allowed("http://robots-disallow.test/data/ok", _pass(tmp_path))
    assert not ok and "disallow" in detail


@pytest.mark.parametrize("host", ["robots-500.test", "robots-garbage.test"])
def test_fails_closed_on_server_error_or_garbage(fixture_server, tmp_path, host):
    ok, _ = _checker(fixture_server).allowed(f"http://{host}/data/ok", _pass(tmp_path))
    assert not ok


def test_fails_closed_on_timeout(fixture_server, tmp_path):
    ok, _ = _checker(fixture_server, timeout=0.5).allowed("http://robots-hang.test/data/ok", _pass(tmp_path))
    assert not ok


def test_fails_closed_when_unreachable(fixture_server, tmp_path):
    pol = Politeness(min_delay=0, sleeper=lambda s: None)
    client = HttpClient(proxy="http://127.0.0.1:1", timeout=1.0, politeness=pol, tier=1)
    ok, _ = RobotsChecker(client).allowed("http://example.test/data/ok", _pass(tmp_path))
    assert not ok


def test_robots_cached_per_host(fixture_server, tmp_path):
    chk, p = _checker(fixture_server), _pass(tmp_path)
    chk.allowed("http://example.test/data/ok", p)
    chk.allowed("http://example.test/data/slow2", p)
    assert fixture_server.paths("example.test").count("/robots.txt") == 1


def test_robots_fetch_requires_a_real_pass_and_listed_host(fixture_server, tmp_path):
    chk = _checker(fixture_server)
    ok, _ = chk.allowed("http://example.test/data/ok", object())
    assert not ok
    ok, _ = chk.allowed("http://unlisted.test/data/ok", _pass(tmp_path))
    assert not ok
    assert fixture_server.count == 0


def test_robots_request_uses_shared_user_agent(fixture_server, tmp_path):
    _checker(fixture_server).allowed("http://example.test/data/ok", _pass(tmp_path))
    assert [r["ua"] for r in fixture_server.requests] == [USER_AGENT]
