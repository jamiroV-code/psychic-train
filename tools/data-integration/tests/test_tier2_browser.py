"""Tier-2 browser fetch: stub navigator for the default run; one real-browser test marked `browser`."""
from __future__ import annotations

import hashlib

import pytest

from data_integration import status as st
from data_integration.approvals import ApprovalStore
from data_integration.fetch_tier2 import BrowserResponse, default_navigator, fetch
from data_integration.gate import FetchPass, request_access
from data_integration.parse import parse_table
from data_integration.politeness import Politeness
from data_integration.response_cache import ResponseCache
from plugin_fixture_server import fixture_server  # noqa: F401
from _helpers import fixed_clock, make_record
from fixture_server import CAPTCHA_BODY, CHALLENGE_BODY, JS_PAGE_BODY

HOSTS = ("example.test", "other.test", "robots-disallow.test")
RENDERED = b"<html><body><table><tr><th>d</th><th>v</th></tr><tr><td>2026-01-01</td><td>1</td></tr></table></body></html>"


class Stub:
    def __init__(self, response=None, error=None):
        self.response = response or BrowserResponse(200, RENDERED)
        self.error = error
        self.calls = []

    def __call__(self, url, pass_, options, timeout, proxy):
        self.calls.append(url)
        if self.error:
            raise self.error
        return self.response


def _pass(tmp_path, tier=2):
    store = ApprovalStore(tmp_path / "ap")
    store.write(make_record(tier=tier, hosts=HOSTS, pages=("/data/", "/js/", "/block/")))
    p = request_access("example-src", tier, store, fixed_clock())
    assert isinstance(p, FetchPass)
    return p


def _go(server, url, pass_, nav, **kw):
    kw.setdefault("politeness", Politeness(min_delay=0, sleeper=lambda s: None))
    return fetch(url, pass_, navigator=nav, proxy=server.proxy_url, **kw)


def test_ok_page_parses_and_hashes(fixture_server, tmp_path):
    nav = Stub()
    out = _go(fixture_server, "http://example.test/data/ok", _pass(tmp_path), nav)
    assert out.status == st.OK and out.http_status == 200
    assert out.body_sha256 == hashlib.sha256(RENDERED).hexdigest()
    assert fixture_server.paths() == ["/robots.txt"] and nav.calls == ["http://example.test/data/ok"]
    assert parse_table(out.body).rows == (("2026-01-01", "1"),)


def test_tier1_pass_is_refused_without_navigation(fixture_server, tmp_path):
    nav = Stub()
    out = _go(fixture_server, "http://example.test/data/ok", _pass(tmp_path, tier=1), nav)
    assert out.status == st.REFUSED and nav.calls == [] and fixture_server.count == 0


def test_fake_pass_is_refused_without_navigation(fixture_server):
    nav = Stub()
    out = _go(fixture_server, "http://example.test/data/ok", object(), nav)
    assert out.status == st.REFUSED and nav.calls == [] and fixture_server.count == 0


def test_url_outside_pass_is_refused(fixture_server, tmp_path):
    nav = Stub()
    out = _go(fixture_server, "http://example.test/private/x", _pass(tmp_path), nav)
    assert out.status == st.REFUSED and nav.calls == [] and fixture_server.count == 0


def test_final_url_outside_pass_is_refused(fixture_server, tmp_path):
    nav = Stub(BrowserResponse(200, RENDERED, final_url="http://unlisted.test/data/ok"))
    out = _go(fixture_server, "http://example.test/data/ok", _pass(tmp_path), nav)
    assert out.status == st.REFUSED and "final url" in out.detail


def test_final_url_inside_pass_is_checked_against_robots(fixture_server, tmp_path):
    nav = Stub(BrowserResponse(200, RENDERED, final_url="http://robots-disallow.test/data/ok"))
    out = _go(fixture_server, "http://example.test/data/ok", _pass(tmp_path), nav)
    assert out.status == st.ROBOTS_BLOCKED


def test_aborted_off_pass_request_is_refused(fixture_server, tmp_path):
    nav = Stub(BrowserResponse(0, blocked_url="http://unlisted.test/x"))
    out = _go(fixture_server, "http://example.test/data/ok", _pass(tmp_path), nav)
    assert out.status == st.REFUSED


@pytest.mark.parametrize("code,body,expected", [
    (200, CHALLENGE_BODY, st.CHALLENGE_PAGE),
    (403, CHALLENGE_BODY, st.CHALLENGE_PAGE),
    (200, CAPTCHA_BODY, st.CHALLENGE_PAGE),
    (403, b"forbidden", st.HTTP_ERROR),
    (500, b"boom", st.HTTP_ERROR),
])
def test_block_style_pages_map_to_closed_statuses(fixture_server, tmp_path, code, body, expected):
    out = _go(fixture_server, "http://example.test/block/x", _pass(tmp_path), Stub(BrowserResponse(code, body)))
    assert out.status == expected and out.body_sha256 is None


def test_body_over_cap_is_http_error(fixture_server, tmp_path):
    out = _go(fixture_server, "http://example.test/data/ok", _pass(tmp_path), Stub(), max_body_bytes=10)
    assert out.status == st.HTTP_ERROR and "too large" in out.detail


def test_navigator_failure_maps_to_status(fixture_server, tmp_path):
    p = _pass(tmp_path)
    assert _go(fixture_server, "http://example.test/data/ok", p, Stub(error=RuntimeError("boom"))).status == st.CONNECTION_FAILED
    assert _go(fixture_server, "http://example.test/data/ok", p, Stub(error=TimeoutError("timed out"))).status == st.TIMEOUT


def test_cache_tier_mismatch_refused_and_hit_skips_navigation(fixture_server, tmp_path):
    p = _pass(tmp_path)
    nav = Stub()
    assert _go(fixture_server, "http://example.test/data/ok", p, nav, cache=ResponseCache(tmp_path / "c", tier=1)).status == st.REFUSED
    cache = ResponseCache(tmp_path / "c2", tier=2)
    assert _go(fixture_server, "http://example.test/data/ok", p, nav, cache=cache).status == st.OK
    again = _go(fixture_server, "http://example.test/data/ok", p, nav, cache=cache)
    assert again.body == RENDERED and len(nav.calls) == 1


def test_log_line_has_tier_2_and_no_query(fixture_server, tmp_path, caplog):
    caplog.set_level("INFO", logger="data_integration.fetch")
    _go(fixture_server, "http://example.test/data/ok?secret=1", _pass(tmp_path), Stub())
    lines = [r.getMessage() for r in caplog.records if "tier=2" in r.getMessage()]
    assert lines and all("secret" not in ln for ln in lines)


@pytest.mark.browser
def test_real_browser_renders_js_table(fixture_server, tmp_path):
    out = fetch("http://example.test/js/table", _pass(tmp_path), navigator=default_navigator, proxy=fixture_server.proxy_url,
                timeout=30.0, politeness=Politeness(min_delay=0, sleeper=lambda s: None))
    assert out.status == st.OK and b"<table>" in out.body and b"2026-01-02" in out.body
    assert b'<div id="out"><table>' not in JS_PAGE_BODY  # the source has no built table; the browser made it
    assert b'<div id="out"><table>' in out.body
