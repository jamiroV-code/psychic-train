"""S-RGQL: the anonymous GraphQL live method over the in-process fake (`reddit_gql_fake`). No network, no real
token, no account; every value synthetic."""
from __future__ import annotations

import base64
import copy
import dataclasses
import json
import logging
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest

from api.data import cache
from api.data.attention import reddit_core as rc
from api.data.attention import reddit_gql as rg
from api.data.attention import reddit_items
from api.data.attention import reddit_live as rl
from api.data.attention import reddit_surface as rs
from api.data.attention import web_queries as wq
from api.data.attention.browser_session import DENY_ROUTES
from api.scripts import probe_owner as po
from api.tests.data.attention import reddit_gql_fake as fk

D = date(2026, 11, 5)
NOW = datetime(2026, 11, 6, 3, tzinfo=timezone.utc)
SALT = b"0123456789abcdef0123456789abcdef"
PLANTED_USER = "PlantedUserName77"
PLANTED_TEXT = "secret-body-words"
CC = "CryptoCurrency"


@pytest.fixture(autouse=True)
def _isolated(attention_cache):
    return attention_cache


def at(h: float) -> datetime:
    return datetime(D.year, D.month, D.day, tzinfo=timezone.utc) + timedelta(hours=h)


def write_surface(tmp_path, raw=None, name="surface.json"):
    path = tmp_path / name
    raw = fk.section_raw() if raw is None else raw
    raw = {**raw, "sha256": rs.section_sha256(raw)}
    path.write_text(json.dumps({"sections": {"gql_anon": raw}}), encoding="utf-8")
    return path, rs.load_section("gql_anon", raw)


def verify_record(section, *, day=NOW.date(), outcome="pass"):
    po.write_record(cache.CACHE_ROOT, po.make_record(
        probe_id="PR1", mode="verify", date_utc=day.isoformat(), commit="a" * 40, egress_class="direct",
        outcome=outcome, section="gql_anon", section_sha256=section.sha256, surface_revision=section.revision,
        counts=dict.fromkeys(po.COUNTS, 0), reason_codes=[], limits_hit=[]))


def config(path, **over):
    base = wq.load().config
    fields = {"reddit_live_methods": ["gql_anon"], "reddit_surface_path": str(path),
              "reddit_live_probe_max_age_days": 7, "reddit_live_gql_daily_request_cap": 600, **over}
    return dataclasses.replace(base, **fields)


def world(now=NOW) -> fk.FakeGql:
    f = fk.FakeGql(now=now)
    f.posts = [(f"t3_c{i}", CC, at(-24 + i / 2), "ccuser", "market talk", "") for i in range(2 * 51)]
    f.posts += [(f"t3_s{k}", "solana", at(h), f"{PLANTED_USER}{k}", f"SOL up {PLANTED_TEXT}", "body")
                for k, h in enumerate((3, 9, 15))]
    f.comments = [(f"t1_m{k}", "t3_s1", "solana", at(10 + k), PLANTED_USER, f"SOL yes {PLANTED_TEXT}")
                  for k in range(3)]
    return f


def method(path, fake, clock=lambda: NOW, **over):
    q = wq.load()
    return rg.GqlMethod(config(path, **over), transport=fake, clock=clock,
                        hasher=reddit_items.AuthorHasher(SALT), queries=lambda: q)


def poll(m, now, subs=("solana",), cap=600, threads_per_poll=30):
    ctx = rl.build_context(rg.STORE, subs, now, threads_per_poll=threads_per_poll, request_cap=cap)
    result = m.run_poll(ctx)
    rl.record_poll(rg.STORE, result)
    return result


@pytest.fixture
def ready(tmp_path):
    path, section = write_surface(tmp_path)
    verify_record(section)
    return path, section


# --- the B7 grammar ---------------------------------------------------------------------------------------------

def test_requests_grammar_loads_and_matches_endpoints(ready):
    _, section = ready
    req = rg.load_requests(section)
    assert set(req.operations) == {"posts", "comments"} and req.client_id == fk.CLIENT_ID
    assert fk.CLIENT_ID not in repr(req)
    url, body = rg.render(req.operations["posts"], subreddit="solana")
    assert url == "https://gql-fed.reddit.com/" and "after" not in body["variables"]
    assert body["variables"]["subredditName"] == "solana" and body["variables"]["pageSize"] == rg.PAGE_LIMIT


def _bad(fn):
    raw = fk.section_raw()
    fn(raw["requests"])
    return raw


BAD_REQUESTS = {
    "extra_key": lambda r: r.update(extra=1),
    "unknown_placeholder": lambda r: r["operations"]["posts"]["variables_template"].update(x="{user}"),
    "token_in_variables": lambda r: r["operations"]["posts"]["variables_template"].update(x="{token}"),
    "token_in_body": lambda r: r["operations"]["posts"]["body_template"].update(x="{token}"),
    "placeholder_in_body": lambda r: r["operations"]["posts"]["body_template"].update(x="{subreddit}"),
    "embedded_placeholder": lambda r: r["operations"]["posts"]["variables_template"].update(x="r/{subreddit}"),
    "template_basic_auth": lambda r: r["token"]["header_template"].update(Authorization="Basic AAAA"),
    "template_bearer_on_token": lambda r: r["token"]["header_template"].update(Authorization="Bearer {token}"),
    "literal_bearer": lambda r: r["operations"]["posts"]["header_template"].update(Authorization="Bearer abc"),
    "missing_bearer": lambda r: r["operations"]["posts"]["header_template"].pop("Authorization"),
    "cookie_header": lambda r: r["operations"]["posts"]["header_template"].update(Cookie="a=b"),
    "loid_header": lambda r: r["token"]["header_template"].update({"x-reddit-loid": "abc"}),
    "session_header": lambda r: r["operations"]["comments"]["header_template"].update({"x-reddit-session": "a"}),
    "token_header_value": lambda r: r["operations"]["posts"]["header_template"].update({"X-Op": "{token}"}),
    "host_header": lambda r: r["operations"]["posts"]["header_template"].update(Host="evil.test"),
    "foreign_host": lambda r: r["operations"]["posts"].update(host="evil.example.test"),
    "path_after": lambda r: r["operations"]["posts"].update(path="/{after}"),
    "token_path_placeholder": lambda r: r["token"].update(path="/x/{subreddit}"),
    "query_subreddit": lambda r: r["operations"]["posts"].update(path="/?sr={subreddit}"),
    "client_id_short": lambda r: r.update(client_id="abc"),
    "client_id_chars": lambda r: r.update(client_id="abc def ghi:"),
    "client_id_type": lambda r: r.update(client_id=12345678),
    "operation_unmatched": lambda r: r["operations"]["posts"].update(operationName="Other"),
    "lane_swapped": lambda r: r["operations"].update(posts=r["operations"]["comments"]),
    "body_overrides_variables": lambda r: r["operations"]["posts"]["body_template"].update(variables={}),
    "bad_method": lambda r: r["operations"]["posts"].update(method="PUT"),
    "token_pointer": lambda r: r["token"].update(token_pointer="access_token"),
}


@pytest.mark.parametrize("name", sorted(BAD_REQUESTS))
def test_requests_grammar_is_closed(name):
    section = rs.load_section("gql_anon", _bad(BAD_REQUESTS[name]))
    with pytest.raises(rg.RequestsInvalid):
        rg.load_requests(section)


def test_section_without_requests_is_refused(tmp_path):
    raw = fk.section_raw()
    del raw["requests"]
    with pytest.raises(rg.RequestsInvalid):
        rg.load_requests(rs.load_section("gql_anon", raw))


# --- gate refusals ----------------------------------------------------------------------------------------------

def test_gate_ready_only_with_fresh_matching_verify_record(tmp_path):
    path, section = write_surface(tmp_path)
    fake = world()
    assert method(path, fake).gate_state(NOW) == "needs_probe"  # no record
    verify_record(section, outcome="fail")
    assert method(path, fake).gate_state(NOW) == "needs_probe"
    verify_record(section, day=NOW.date() - timedelta(days=8))
    for p in (cache.CACHE_ROOT / "attention" / "_probes").glob("*.json"):
        if NOW.date().isoformat() in p.name:
            p.unlink()
    assert method(path, fake).gate_state(NOW) == "needs_probe"  # stale record
    verify_record(section)
    assert method(path, fake).gate_state(NOW) == "ready"
    changed = fk.section_raw(revision=2)
    path2, _ = write_surface(tmp_path, changed, "surface2.json")
    assert method(path2, fake).gate_state(NOW) == "needs_probe"  # hash/revision mismatch
    assert fake.calls == []


def test_gate_disabled_unavailable_unsupported_and_invalid(ready, tmp_path):
    path, _ = ready
    assert method(path, world(), reddit_live_methods=[]).gate_state(NOW) == "disabled"
    assert rg.GqlMethod(config(path), transport=None, clock=lambda: NOW).gate_state(NOW) == "method_unavailable"
    bad = fk.section_raw()
    bad["body_format"] = "protobuf"
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"sections": {"gql_anon": bad}}))
    assert method(p, world()).gate_state(NOW) == "unsupported_format"
    p.write_text(json.dumps({"sections": {"gql_anon": _bad(BAD_REQUESTS["cookie_header"])}}))
    assert method(p, world()).gate_state(NOW) == "needs_probe"
    assert method(tmp_path / "missing.json", world()).gate_state(NOW) == "needs_probe"


def test_factory_resolves_and_production_deps_default_deny(ready, monkeypatch):
    path, _ = ready
    cfg = config(path)
    got = rc.resolve_methods(cfg, SimpleNamespace(clock=lambda: NOW, gql_transport=world()))
    m = got["gql_anon"]
    assert isinstance(m, rg.GqlMethod) and isinstance(m, rl.LiveMethod) and m.store == "reddit_live_gql"
    assert m.gate_state(NOW) == "ready"
    denied = rc.resolve_method("gql_anon", cfg, SimpleNamespace(clock=lambda: NOW, routes=DENY_ROUTES))
    assert denied.gate_state(NOW) == "method_unavailable"
    proxied = dataclasses.replace(cfg, x_proxy_required=True)
    assert rc.resolve_method("gql_anon", proxied, SimpleNamespace(clock=lambda: NOW)).gate_state(NOW) == \
        "method_unavailable"
    direct = rg.make_method(cfg, SimpleNamespace(clock=lambda: NOW))
    if not (cfg.x_proxy_required or cfg.x_proxy_list_path or cfg.x_proxy_assignments_path
            or cfg.x_proxy_policy_path):
        assert isinstance(direct.transport, rg.HttpTransport)


def test_http_transport_reads_status_type_and_body():
    seen = []

    def handler(request):
        seen.append((request.method, str(request.url), request.headers.get("authorization"), request.content))
        return httpx.Response(200, headers={"content-type": "application/json"}, content=b'{"ok":true}')

    t = rg.HttpTransport(lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False,
                                                   follow_redirects=False))
    resp = t("POST", "https://gql-fed.reddit.com/", {"Authorization": "Bearer x"}, b"{}")
    assert (resp.status, resp.content_type, resp.body) == (200, "application/json", b'{"ok":true}')
    assert seen == [("POST", "https://gql-fed.reddit.com/", "Bearer x", b"{}")]

    def boom(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(rg.TransportError):
        rg.HttpTransport(lambda: httpx.AsyncClient(transport=httpx.MockTransport(boom)))("GET", "https://a.b/", {},
                                                                                          None)


# --- polls ------------------------------------------------------------------------------------------------------

def test_mint_header_is_code_built_and_bearer_used_after(ready):
    path, _ = ready
    fake = world()
    poll(method(path, fake), NOW)
    first = fake.seen_headers[0]
    assert fake.calls[0] == ("POST", "https://www.reddit.com/auth/v2/oauth/access-token/loid")
    assert first["Authorization"] == "Basic " + base64.b64encode(f"{fk.CLIENT_ID}:".encode()).decode()
    assert all(h["Authorization"].startswith("Bearer faketoken.") for h in fake.seen_headers[1:])
    assert fake.mints == 1


def test_posts_cursor_chain_reaches_the_floor(ready):
    path, _ = ready
    fake = world()
    r = poll(method(path, fake), NOW, subs=("solana",))
    lanes = {(lane.subreddit, lane.kind): lane for lane in r.lanes}
    cc = lanes[(CC, "posts")]
    assert cc.stop_reason == "exhausted" and cc.complete and cc.pages >= 3 and len(cc.cursor_chain) == cc.pages
    assert cc.floor == at(0) and cc.oldest <= at(0) and cc.newest == at(-24 + 101 / 2)
    sol = lanes[("solana", "posts")]
    assert sol.stop_reason == "exhausted" and sol.items_seen == 3 and dict(sol.threads)["t3_s1"] == 3
    ids = {i.id for i in r.items}
    assert "t3_ad" not in ids and {"t3_s0", "t3_s1", "t3_s2"} <= ids
    assert {i.coins for i in r.items if i.subreddit == "solana"} == {("SOL",)}
    assert r.requests == len(fake.calls) and rl.read_state(rg.STORE, NOW)["requests"] == r.requests


def test_thread_comments_paged_and_reopened(ready):
    path, _ = ready
    fake = world()
    m = method(path, fake)
    poll(m, NOW)
    fake.now = NOW + timedelta(hours=4)
    r = poll(m, fake.now)
    comments = [lane for lane in r.lanes if lane.kind == "comments"]
    assert comments and all(lane.stop_reason == "exhausted" for lane in comments)
    opened = {t for lane in comments for t, _ in lane.threads}
    assert "t3_s1" in opened
    lane = next(lane for lane in comments if "t3_s1" in dict(lane.threads))
    assert lane.subreddit == "solana" and lane.items_seen == 3 and lane.pages == 2
    assert {i.id for i in r.items if i.kind == "comment"} == {"t1_m0", "t1_m1", "t1_m2"}


def test_rejected_hash_marks_ops_stale_and_stops_without_storm(ready, tmp_path):
    path, section = ready
    fake = world()
    fake.stale_hash = True
    m = method(path, fake)
    r = poll(m, NOW, subs=("solana",))
    assert [lane.stop_reason for lane in r.lanes] == ["schema_mismatch"]  # first lane; the poll stopped
    assert len(fake.calls) == 2  # one mint, one operation: no retry
    assert rg.read_gql_state(NOW)["ops_stale"] == section.sha256
    assert m.gate_state(NOW) == "needs_probe"
    assert rg.read_gql_state(NOW + timedelta(days=1))["ops_stale"] == section.sha256  # survives the day
    raw2 = fk.section_raw(revision=2)
    path2, section2 = write_surface(tmp_path, raw2, "s2.json")
    verify_record(section2)
    assert method(path2, fake).gate_state(NOW) == "ready"  # a new published revision clears it


def test_block_page_stops_the_poll(ready):
    path, _ = ready
    fake = world()
    fake.block_after = 1
    r = poll(method(path, fake), NOW, subs=("solana",))
    stops = [lane.stop_reason for lane in r.lanes]
    assert stops[-1] == "error" and len(r.lanes) <= 2 and r.failed
    assert len(fake.calls) == 3  # mint, one good page, the block page; nothing after


def test_empty_shell_fails_lane_but_not_the_poll(ready):
    path, _ = ready
    fake = world()
    fake.empty_shell = True
    r = poll(method(path, fake), NOW, subs=("solana",))
    assert [lane.stop_reason for lane in r.lanes] == ["empty_shell", "empty_shell"]
    assert r.items == () and r.failed


def test_token_renewal_bounded_to_two_mints_per_day(ready):
    path, _ = ready
    fake = world()
    fake.expire_tokens_after = 2
    r = poll(method(path, fake), NOW, subs=("solana",))
    assert fake.mints == 2 and rg.read_gql_state(NOW)["mints"] == 2
    assert any(lane.stop_reason == "cap" for lane in r.lanes)
    calls = len(fake.calls)
    r2 = poll(method(path, fake), NOW + timedelta(hours=1), subs=("solana",))
    assert fake.mints == 2 and len(fake.calls) == calls  # restart, same UTC day: no third mint, nothing sent
    assert [lane.stop_reason for lane in r2.lanes] == ["cap"] and r2.requests == 0
    fake.now = NOW + timedelta(days=1)
    poll(method(path, fake, clock=lambda: fake.now), fake.now, subs=("solana",))
    assert fake.mints >= 3 and 1 <= rg.read_gql_state(fake.now)["mints"] <= rg.MAX_MINTS_PER_DAY


def test_token_ttl_expiry_renews_before_use_without_a_rejection(ready):
    path, _ = ready
    fake = world()
    fake.ttl = 300
    ticks = iter(range(10_000))
    m = method(path, fake, clock=lambda: NOW + timedelta(seconds=60 * next(ticks)))
    poll(m, NOW, subs=("solana",))
    assert fake.mints == 2  # renewed once when the clock passed the expiry margin, then the daily bound stops it
    bearers = [h["Authorization"][len("Bearer "):] for h in fake.seen_headers if h["Authorization"].startswith("Bearer")]
    assert bearers and set(bearers) <= set(fake._tokens)  # renewed before use: never sent an unknown token


def test_daily_cap_is_persisted_across_restarts_and_tokens(ready):
    path, _ = ready
    fake = world()
    r = poll(method(path, fake, reddit_live_gql_daily_request_cap=50), NOW, subs=("solana",), cap=6)
    assert r.requests == 6 and any(lane.stop_reason == "cap" for lane in r.lanes)
    assert rg.read_gql_state(NOW)["requests"] == 6
    sent = len(fake.calls)
    # A restart with a fresh context that would allow more still honours the persisted method counter.
    m = method(path, fake, reddit_live_gql_daily_request_cap=6)
    r2 = poll(m, NOW + timedelta(minutes=5), subs=("solana",), cap=600)
    assert r2.requests == 0 and len(fake.calls) == sent
    assert json.loads(rg.gql_state_path().read_text())["requests"] == 6
    fake.now = NOW + timedelta(days=1)
    r3 = poll(method(path, fake, clock=lambda: fake.now, reddit_live_gql_daily_request_cap=6), fake.now,
              subs=("solana",), cap=600)
    assert 0 < r3.requests <= 6  # a new UTC day starts at zero


def test_no_text_username_or_bearer_persisted_or_logged(ready, caplog, tmp_path):
    caplog.set_level(logging.DEBUG)
    path, _ = ready
    fake = world()
    m = method(path, fake)
    poll(m, NOW)
    fake.now = NOW + timedelta(hours=4)
    poll(m, fake.now)
    rl.commit_day(rg.STORE, D, wq.load(), now=fake.now, subreddits=("solana",))
    tokens = list(fake._tokens)
    assert tokens
    planted = [PLANTED_USER, PLANTED_TEXT, "faketoken", fk.CLIENT_ID, "Basic ", "Bearer "]
    # The owner's surface file legitimately holds the public client id and the `Bearer {token}` template.
    files = [p for p in cache.CACHE_ROOT.rglob("*") if p.is_file() and p.parent != tmp_path]
    assert files
    for p in files:
        text = p.read_text(encoding="utf-8", errors="replace")
        assert not [s for s in planted if s in text], p.name
    assert not [s for s in planted if s in caplog.text]
    assert "faketoken" not in repr(m) and fk.CLIENT_ID not in repr(m)
    assert set(json.loads(rg.gql_state_path().read_text())) == {"day", "requests", "mints", "ops_stale"}


def test_values_reach_the_core_store(ready):
    path, _ = ready
    fake = world()
    m = method(path, fake)
    for h in (0, 4, 8):
        fake.now = NOW + timedelta(hours=h)
        poll(m, fake.now)
    assert rc.read_items(rg.STORE, D)["t3_s1"].coins == ("SOL",)
    assert rl.read_lanes(rg.STORE, NOW.date(), NOW.date())
