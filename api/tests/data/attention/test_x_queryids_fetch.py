"""S-XProto XP-2: bounded static sentinel with an explicit route; the network seam is injected (no live X)."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from api.data.attention import x_proxy as p
from api.data.attention import x_queryids as q
from api.data.attention import x_queryids_fetch as f

NOW = datetime(2026, 11, 7, 6, tzinfo=UTC)
NEW = "vLHjqbDv7TPFMBkIIO1nOA"
HASH = "7e80395699a4329fa"
MARKER = "SYNTHETIC_ROUTE_CREDENTIAL_MARKER"
EMBED = f'<script src="https://abs.twimg.com/responsive-web/client-web/main.{HASH}.js"></script>'.encode()
BUNDLE = f'{{queryId:"{NEW}",operationName:"SearchTimeline"}};{{queryId:"AMIBMjtxEEATh4z8V9GtRg",operationName:"UserByScreenName"}}'.encode()


def config(mode="sentinel", budget=6, proxied=False):
    return SimpleNamespace(x_queryid_mode=mode, x_queryid_static_budget_per_day=budget, x_proxy_required=proxied,
                           x_proxy_list_path=None, x_proxy_assignments_path=None, x_proxy_policy_path=None)


class Fake:
    def __init__(self, *bodies):
        self.bodies, self.calls = list(bodies), []

    async def __call__(self, route, policy, url):
        self.calls.append((route, policy, url))
        body = self.bodies.pop(0)
        if isinstance(body, Exception):
            raise body
        return body


def policy(*origins):
    return SimpleNamespace(validate_url=lambda url: p.require(p.canonical_origin(url) in origins, "proxy_policy"))


ROUTE = SimpleNamespace(url="https://proxy.test", auth=("user", MARKER))


def test_off_mode_never_fetches_and_leaves_state_untouched(tmp_path):
    fake = Fake()
    assert f.run_check(config(mode="off"), cache_root=tmp_path, now=NOW, get=fake) is None
    assert fake.calls == [] and not (tmp_path / "attention").exists()


@pytest.mark.parametrize("mode", ["sentinel", "auto"])
def test_direct_check_fetches_two_fixed_urls_and_records_a_candidate(tmp_path, mode):
    fake = Fake(EMBED, BUNDLE)
    state = f.run_check(config(mode=mode), cache_root=tmp_path, now=NOW, get=fake)
    assert [c[2] for c in fake.calls] == [q.EMBED_URL, q.bundle_url(HASH)]
    assert all(c[0] is None and c[1] is None for c in fake.calls)  # explicit direct route
    assert state["check_state"] == "candidate" and state["budget"] == {"day": "2026-11-07", "used": 2}
    assert q.active_id(state, "SearchTimeline") == q.PINNED["SearchTimeline"]  # the sentinel never adopts
    assert q.load(q.state_path(tmp_path)) == state


def test_daily_budget_caps_gets_and_resets_on_the_next_utc_day(tmp_path):
    fake = Fake(*([EMBED, BUNDLE] * 4))
    for _ in range(3):
        f.run_check(config(budget=5), cache_root=tmp_path, now=NOW, get=fake)
    assert len(fake.calls) == 4  # a check needs two GETs; the fifth unit cannot start a third check
    f.run_check(config(budget=5), cache_root=tmp_path, now=NOW + timedelta(days=1), get=fake)
    assert len(fake.calls) == 6


@pytest.mark.parametrize("failure,expected", [
    ([p.ProxyFailure("proxy_timeout")], "blocked"), ([RuntimeError("boom")], "blocked"),
    ([b"<html>no bundle</html>"], "unknown"), ([b"\xff\xfe"], "unknown"),
    ([EMBED, p.ProxyFailure("proxy_response")], "blocked"), ([EMBED, b"garbage"], "unknown"),
    ([EMBED, b"x" * (q.BUNDLE_LIMIT + 1)], "unknown")])
def test_blocked_or_malformed_never_reports_ok_or_stale(tmp_path, failure, expected):
    state = f.run_check(config(), cache_root=tmp_path, now=NOW, get=Fake(*failure))
    assert state["check_state"] == expected and state["last_check"] == NOW.isoformat()
    assert all(entry["candidate"] is None for entry in state["operations"].values())


def test_proxied_without_admitted_route_does_not_fetch(tmp_path):
    fake = Fake()
    state = f.run_check(config(proxied=True), cache_root=tmp_path, now=NOW, get=fake)
    assert fake.calls == [] and state["check_state"] == "unknown" and state["budget"]["used"] == 0


def test_proxied_route_requires_static_origins_in_policy_else_refused(tmp_path):
    fake = Fake()
    state = f.run_check(config(proxied=True), cache_root=tmp_path, now=NOW, route=ROUTE,
                        policy=policy("https://x.com"), get=fake)
    assert fake.calls == [] and state["check_state"] == "refused_by_policy"
    fake = Fake(EMBED, BUNDLE)
    allowed = policy("https://x.com", "https://abs.twimg.com")
    state = f.run_check(config(proxied=True), cache_root=tmp_path, now=NOW, route=ROUTE, policy=allowed, get=fake)
    assert state["check_state"] == "candidate" and all(c[0] is ROUTE and c[1] is allowed for c in fake.calls)
    text = q.state_path(tmp_path).read_text(encoding="utf-8")
    assert MARKER not in text and "proxy.test" not in text


def test_direct_config_refuses_a_supplied_route(tmp_path):
    with pytest.raises(ValueError):
        f.run_check(config(), cache_root=tmp_path, now=NOW, route=ROUTE, policy=policy(), get=Fake())


def test_default_get_uses_no_cookies_no_redirects_and_a_bounded_body(monkeypatch):
    seen = {}
    class Response:
        status_code = 200
        headers = {}
        async def aiter_raw(self):
            yield b"a" * 10
        async def __aenter__(self):
            return self
        async def __aexit__(self, *exc):
            return False
    class Client:
        def stream(self, method, url, headers=None):
            seen.update(method=method, url=url)
            return Response()
        async def __aenter__(self):
            return self
        async def __aexit__(self, *exc):
            return False
    from api.data.attention import x_proxy_transport as transport
    def direct_client(*, headers=None, cookies=None):
        seen.update(headers=headers, cookies=cookies)
        return Client()
    monkeypatch.setattr(transport, "direct_client", direct_client)
    import asyncio
    assert asyncio.run(f.static_get(None, None, q.EMBED_URL)) == b"a" * 10
    assert seen["cookies"] is None and seen["method"] == "GET" and seen["url"] == q.EMBED_URL
    assert seen["headers"]["user-agent"] == "attention-probe/0.1"
    routed = []
    async def one_shot(route, policy_, url, limit, *, headers=None):
        assert headers == {"user-agent": "attention-probe/0.1"}
        routed.append((route, url, limit))
        return b"ok"
    from api.data.attention import x_proxy_runtime as runtime
    monkeypatch.setattr(runtime, "one_shot", one_shot)
    assert asyncio.run(f.static_get(ROUTE, object(), q.EMBED_URL)) == b"ok"
    assert routed == [(ROUTE, q.EMBED_URL, q.BUNDLE_LIMIT)]
    with pytest.raises(p.ProxyFailure):
        asyncio.run(f.static_get(None, None, "https://evil.example/main.js"))


def test_state_never_holds_bodies(tmp_path):
    f.run_check(config(), cache_root=tmp_path, now=NOW, get=Fake(EMBED, BUNDLE))
    assert set(json.loads(q.state_path(tmp_path).read_text(encoding="utf-8"))) == {
        "version", "check_state", "last_check", "bundle_sha256", "budget", "operations", "evidence"}


def test_off_mode_does_not_read_or_rewrite_existing_state(tmp_path, monkeypatch):
    path = q.state_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"SYNTHETIC_UNREAD_STATE")
    monkeypatch.setattr(q, "load", lambda path: pytest.fail("off must not load"))
    assert f.run_check(config(mode="off"), cache_root=tmp_path, now=NOW, get=Fake()) is None
    assert path.read_bytes() == b"SYNTHETIC_UNREAD_STATE"


@pytest.mark.parametrize("kind", ["overflow", "redirect", "error", "partial_route"])
def test_one_shot_direct_refuses_bad_responses_and_partial_routes(monkeypatch, kind):
    import asyncio
    from api.data.attention import x_proxy_runtime as runtime, x_proxy_transport as transport
    calls = []
    class Response:
        status_code = 302 if kind == "redirect" else 403 if kind == "error" else 200
        headers = {}
        async def aiter_raw(self):
            yield b"x" * 9
        async def __aenter__(self):
            return self
        async def __aexit__(self, *exc):
            return False
    class Client:
        def stream(self, method, url, **kwargs):
            calls.append((method, url))
            return Response()
        async def __aenter__(self):
            return self
        async def __aexit__(self, *exc):
            return False
    monkeypatch.setattr(transport, "direct_client", lambda **kwargs: Client())
    with pytest.raises(p.ProxyFailure):
        asyncio.run(runtime.one_shot(None, object() if kind == "partial_route" else None, q.EMBED_URL, 8))
    assert len(calls) == (0 if kind == "partial_route" else 1)
