"""Tier-3 gating, block-page mapping and option pass-through (stub navigator; no real protected site)."""
from __future__ import annotations

import pytest

from data_integration import status as st
from data_integration.approvals import ApprovalStore
from data_integration.fetch_tier2 import BrowserResponse
from data_integration.fetch_tier3 import fetch
from data_integration.gate import FetchPass, request_access
from data_integration.politeness import Politeness
from plugin_fixture_server import fixture_server  # noqa: F401
from _helpers import fixed_clock, make_record
from fixture_server import CAPTCHA_BODY, CHALLENGE_BODY, OK_BODY

HOSTS = ("example.test",)


class Stub:
    def __init__(self, response=None):
        self.response = response or BrowserResponse(200, OK_BODY)
        self.calls = []

    def __call__(self, url, pass_, options, timeout, proxy):
        self.calls.append((url, dict(options)))
        return self.response


def _pass(tmp_path, tier):
    store = ApprovalStore(tmp_path / "ap")
    store.write(make_record(tier=tier, hosts=HOSTS, pages=("/data/", "/block/")))
    p = request_access("example-src", tier, store, fixed_clock())
    assert isinstance(p, FetchPass)
    return p


def _go(server, url, pass_, nav, **kw):
    kw.setdefault("politeness", Politeness(min_delay=0, sleeper=lambda s: None))
    return fetch(url, pass_, navigator=nav, proxy=server.proxy_url, **kw)


def test_tier2_pass_is_refused_with_options_untouched(fixture_server, tmp_path):
    nav = Stub()
    out = _go(fixture_server, "http://example.test/data/ok", _pass(tmp_path, 2), nav, options={"humanize": True})
    assert out.status == st.REFUSED and nav.calls == [] and fixture_server.count == 0


def test_tier3_pass_passes_options_through(fixture_server, tmp_path):
    nav = Stub()
    out = _go(fixture_server, "http://example.test/data/ok", _pass(tmp_path, 3), nav,
              options={"humanize": True, "network_idle": True})
    assert out.status == st.OK and out.body_sha256
    assert nav.calls == [("http://example.test/data/ok", {"humanize": True, "network_idle": True})]


def test_no_options_means_empty_options(fixture_server, tmp_path):
    nav = Stub()
    _go(fixture_server, "http://example.test/data/ok", _pass(tmp_path, 3), nav)
    assert nav.calls[0][1] == {}


@pytest.mark.parametrize("opts", [{"solve_cloudflare": True}, {"solve_cloudflare": False}, {"proxy": "http://x"}, {"page_action": 1}])
def test_unknown_or_solving_options_are_refused(fixture_server, tmp_path, opts):
    nav = Stub()
    out = _go(fixture_server, "http://example.test/data/ok", _pass(tmp_path, 3), nav, options=opts)
    assert out.status == st.REFUSED and nav.calls == [] and fixture_server.count == 0


def test_fake_pass_is_refused(fixture_server):
    nav = Stub()
    assert _go(fixture_server, "http://example.test/data/ok", "token", nav).status == st.REFUSED and nav.calls == []


@pytest.mark.parametrize("code,body,expected", [
    (200, CHALLENGE_BODY, st.CHALLENGE_PAGE),
    (403, CHALLENGE_BODY, st.CHALLENGE_PAGE),
    (200, CAPTCHA_BODY, st.CHALLENGE_PAGE),
    (403, b"forbidden", st.HTTP_ERROR),
])
def test_block_pages_map_to_closed_statuses(fixture_server, tmp_path, code, body, expected):
    out = _go(fixture_server, "http://example.test/block/x", _pass(tmp_path, 3), Stub(BrowserResponse(code, body)))
    assert out.status == expected and st.is_status(out.status)


def test_log_line_has_tier_3(fixture_server, tmp_path, caplog):
    caplog.set_level("INFO", logger="data_integration.fetch")
    _go(fixture_server, "http://example.test/data/ok", _pass(tmp_path, 3), Stub())
    assert any("tier=3" in r.getMessage() for r in caplog.records)
