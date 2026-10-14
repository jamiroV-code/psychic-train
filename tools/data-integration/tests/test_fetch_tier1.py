"""Tier-1 fetch against the loopback fixture server (used as a forward proxy)."""
from __future__ import annotations

import logging

import pytest

from data_integration import status as st
from data_integration.approvals import ApprovalStore
from data_integration.fetch_tier1 import clients_built, fetch
from data_integration.gate import FetchPass, request_access
from data_integration.politeness import Politeness
from plugin_fixture_server import fixture_server  # noqa: F401
from _helpers import fixed_clock, make_record

HOSTS = ("example.test", "other.test", "robots-disallow.test", "robots-500.test")


@pytest.fixture
def real_pass(tmp_path):
    store = ApprovalStore(tmp_path / "ap")
    store.write(make_record(tier=1, hosts=HOSTS, pages=("/data/",)))
    p = request_access("example-src", 1, store, fixed_clock())
    assert isinstance(p, FetchPass)
    return p


def _go(server, url, pass_, **kw):
    kw.setdefault("politeness", Politeness(min_delay=0, sleeper=lambda s: None))
    return fetch(url, pass_, proxy=server.proxy_url, **kw)


def test_ok_page(fixture_server, real_pass):
    out = _go(fixture_server, "http://example.test/data/ok", real_pass)
    assert out.status == st.OK and out.http_status == 200 and b"<table>" in out.body
    assert fixture_server.paths() == ["/robots.txt", "/data/ok"]


def test_fake_pass_is_refused_with_zero_clients(fixture_server):
    before = clients_built()
    out = _go(fixture_server, "http://example.test/data/ok", object())
    assert out.status == st.REFUSED
    assert clients_built() == before and fixture_server.count == 0


def test_unpermitted_url_is_refused_with_zero_clients(fixture_server, real_pass):
    before = clients_built()
    for url in ("http://unlisted.test/data/ok", "http://example.test/other/ok", "http://example.test:8080/data/ok",
                "https://example.test/../data/ok", "not a url"):
        assert _go(fixture_server, url, real_pass).status == st.REFUSED
    assert clients_built() == before and fixture_server.count == 0


def test_client_built_only_after_permit(fixture_server, real_pass):
    before = clients_built()
    assert _go(fixture_server, "http://example.test/data/ok", real_pass).status == st.OK
    assert clients_built() == before + 1


def test_redirect_same_host(fixture_server, real_pass):
    out = _go(fixture_server, "http://example.test/data/redirect-same", real_pass)
    assert out.status == st.OK
    assert fixture_server.paths("example.test").count("/robots.txt") == 1


def test_redirect_to_other_listed_host_checks_robots_per_hop(fixture_server, real_pass):
    out = _go(fixture_server, "http://example.test/data/redirect-other", real_pass)
    assert out.status == st.OK
    assert "/robots.txt" in fixture_server.paths("other.test")


def test_redirect_to_unlisted_host_is_refused_without_following(fixture_server, real_pass):
    out = _go(fixture_server, "http://example.test/data/redirect-unlisted", real_pass)
    assert out.status == st.REFUSED
    assert fixture_server.paths("unlisted.test") == []


def test_redirect_loop_terminates(fixture_server, real_pass):
    out = _go(fixture_server, "http://example.test/data/redirect-loop", real_pass, max_redirects=3)
    assert out.status in {st.HTTP_ERROR, st.CONNECTION_FAILED} and "redirect" in out.detail


def test_robots_disallow(fixture_server, real_pass):
    out = _go(fixture_server, "http://robots-disallow.test/data/ok", real_pass)
    assert out.status == st.ROBOTS_BLOCKED
    assert "/data/ok" not in fixture_server.paths("robots-disallow.test")


def test_robots_server_error_fails_closed(fixture_server, real_pass):
    assert _go(fixture_server, "http://robots-500.test/data/ok", real_pass).status == st.ROBOTS_BLOCKED


def test_http_500_and_429(fixture_server, real_pass):
    out = _go(fixture_server, "http://example.test/data/500", real_pass)
    assert (out.status, out.http_status) == (st.HTTP_ERROR, 500)
    out = _go(fixture_server, "http://example.test/data/429", real_pass)
    assert (out.status, out.http_status) == (st.HTTP_ERROR, 429)


def test_timeout(fixture_server, real_pass):
    out = _go(fixture_server, "http://example.test/data/slow", real_pass, timeout=0.5)
    assert out.status == st.TIMEOUT


def test_connection_refused_maps_without_raising(fixture_server, real_pass):
    out = fetch("http://example.test/data/ok", real_pass, proxy="http://127.0.0.1:1", timeout=1.0,
                politeness=Politeness(min_delay=0, sleeper=lambda s: None))
    assert out.status in {st.CONNECTION_FAILED, st.ROBOTS_BLOCKED}


def test_challenge_page(fixture_server, real_pass):
    out = _go(fixture_server, "http://example.test/data/challenge", real_pass)
    assert out.status == st.CHALLENGE_PAGE


def test_outcome_status_always_in_closed_set(fixture_server, real_pass):
    for path in ("ok", "500", "challenge", "redirect-unlisted", "missing"):
        out = _go(fixture_server, f"http://example.test/data/{path}", real_pass)
        assert st.is_status(out.status)


def test_politeness_applied_between_requests(fixture_server, real_pass):
    sleeps = []
    clock = [0.0]
    pol = Politeness(min_delay=3.0, clock=lambda: clock[0], sleeper=lambda s: (sleeps.append(s), clock.__setitem__(0, clock[0] + s)))
    _go(fixture_server, "http://example.test/data/ok", real_pass, politeness=pol)
    assert sleeps and sleeps[-1] == pytest.approx(3.0)


def test_user_agent_is_honest(fixture_server, real_pass):
    _go(fixture_server, "http://example.test/data/ok", real_pass)
    assert all("data-integration" in r["ua"] and "Mozilla" not in r["ua"] for r in fixture_server.requests)


def test_request_log_lines_have_no_query_or_secrets(fixture_server, real_pass, caplog):
    with caplog.at_level(logging.INFO, logger="data_integration.fetch"):
        _go(fixture_server, "http://example.test/data/ok?api_key=sekret123", real_pass)
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "sekret123" not in text and "127.0.0.1" not in text
    assert "host=example.test" in text and "tier=1" in text
