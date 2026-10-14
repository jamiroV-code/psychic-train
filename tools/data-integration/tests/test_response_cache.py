"""Response cache: second call is a cache_hit with zero requests; refresh makes one allowed request."""
from __future__ import annotations

import pytest

from data_integration import status as st
from data_integration.approvals import ApprovalStore
from data_integration.fetch_tier1 import fetch
from data_integration.gate import request_access
from data_integration.politeness import Politeness
from data_integration.response_cache import ResponseCache
from plugin_fixture_server import fixture_server  # noqa: F401
from _helpers import fixed_clock, make_record


@pytest.fixture
def real_pass(tmp_path):
    store = ApprovalStore(tmp_path / "ap")
    store.write(make_record(tier=1, hosts=("example.test",), pages=("/data/",)))
    return request_access("example-src", 1, store, fixed_clock())


def _go(server, pass_, cache, url="http://example.test/data/ok", **kw):
    return fetch(url, pass_, proxy=server.proxy_url, cache=cache,
                 politeness=Politeness(min_delay=0, sleeper=lambda s: None), **kw)


def test_second_call_is_cache_hit_with_zero_requests(fixture_server, real_pass, tmp_path):
    cache = ResponseCache(tmp_path / "rc")
    first = _go(fixture_server, real_pass, cache)
    n = fixture_server.count
    second = _go(fixture_server, real_pass, cache)
    assert first.status == st.OK and second.status == st.CACHE_HIT
    assert second.body == first.body and fixture_server.count == n


def test_forced_refresh_makes_one_allowed_request(fixture_server, real_pass, tmp_path):
    cache = ResponseCache(tmp_path / "rc")
    _go(fixture_server, real_pass, cache)
    n = fixture_server.paths().count("/data/ok")
    out = _go(fixture_server, real_pass, cache, refresh=True)
    assert out.status == st.OK and fixture_server.paths().count("/data/ok") == n + 1


def test_cache_hit_still_requires_permit(fixture_server, real_pass, tmp_path):
    cache = ResponseCache(tmp_path / "rc")
    _go(fixture_server, real_pass, cache)
    assert _go(fixture_server, object(), cache).status == st.REFUSED


def test_errors_are_not_cached(fixture_server, real_pass, tmp_path):
    cache = ResponseCache(tmp_path / "rc")
    assert _go(fixture_server, real_pass, cache, url="http://example.test/data/500").status == st.HTTP_ERROR
    assert cache.get("http://example.test/data/500") is None


def test_cache_roundtrip_and_corrupt_entry(fixture_server, tmp_path):
    cache = ResponseCache(tmp_path / "rc")
    assert cache.get("http://example.test/data/ok") is None
    cache.put("http://example.test/data/ok", 200, b"abc")
    hit = cache.get("http://example.test/data/ok")
    assert hit.status == st.CACHE_HIT and hit.body == b"abc" and hit.http_status == 200
    for f in (tmp_path / "rc").iterdir():
        f.write_bytes(b"\x00garbage")
    assert cache.get("http://example.test/data/ok") is None
