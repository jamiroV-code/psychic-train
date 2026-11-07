"""S-RGQL: the PR1 (`gql_anon`) owner-probe executor over the in-process fake. No network, no real token."""
import dataclasses
import json
from datetime import date, datetime, timedelta, timezone

import pytest

from api.data.attention import reddit_surface as rs
from api.data.attention import web_queries as wq
from api.scripts import probe_executors  # noqa: F401 - the default registry, PR1 included
from api.scripts import probe_gql as pg
from api.scripts import probe_owner as po
from api.tests.data.attention import reddit_gql_fake as fk

TODAY = date(2026, 11, 6)
NOW = datetime(2026, 11, 6, 3, tzinfo=timezone.utc)
D = date(2026, 11, 5)


def at(h):
    return datetime(D.year, D.month, D.day, tzinfo=timezone.utc) + timedelta(hours=h)


def world():
    f = fk.FakeGql(now=NOW)
    f.posts = [(f"t3_c{i}", "CryptoCurrency", at(-24 + i / 2), "u", "talk", "") for i in range(102)]
    f.comments = [(f"t1_m{k}", "t3_c40", "CryptoCurrency", at(21), "u", "x") for k in range(3)]
    return f


def surface(tmp_path, raw=None):
    raw = fk.section_raw() if raw is None else raw
    raw = {**raw, "sha256": rs.section_sha256(raw)}
    path = tmp_path / "surface.json"
    path.write_text(json.dumps({"sections": {"gql_anon": raw}}))
    return path, rs.load_section("gql_anon", raw)


def go(tmp_path, mode, deps, surface_path=None):
    return po.run("PR1", approval=po.plan("PR1", mode)["approval_digest"], cache_root=tmp_path / "cache",
                  commit="a" * 40, today=TODAY, mode=mode, surface_path=surface_path, dependencies=deps)


def test_pr1_is_registered_by_s_rgql():
    assert po.EXECUTORS["PR1"] is pg.pr1_gql_anon
    assert "PR2" not in po.EXECUTORS


def test_dry_run_builds_nothing(tmp_path):
    def forbidden():
        pytest.fail("dependencies built on a dry run")
    assert po.run("PR1", approval=None, cache_root=tmp_path, commit="a" * 40, dependencies=forbidden)["dry_run"]


def test_bootstrap_pass_on_the_draft_section(tmp_path):
    _, section = surface(tmp_path)
    fake = world()
    r = go(tmp_path, "bootstrap", {"transport": fake, "section": section, "now": lambda: NOW})
    assert r["outcome"] == "pass" and r["mode"] == "bootstrap" and r["section_sha256"] is None
    assert r["counts"]["requests"] == len(fake.calls) <= 120
    assert fake.calls[0][1].endswith(fk.TOKEN_PATH)


def test_verify_binds_the_published_section_and_opens_the_gate(tmp_path):
    path, section = surface(tmp_path)
    fake = world()
    r = go(tmp_path, "verify", {"transport": fake, "now": lambda: NOW}, surface_path=path)
    assert r["outcome"] == "pass" and r["section"] == "gql_anon"
    assert (r["section_sha256"], r["surface_revision"]) == (section.sha256, 1)
    assert po.verify_gate(tmp_path / "cache", "gql_anon", surface_path=path, max_age_days=7, today=TODAY) == "ok"
    text = json.dumps(r)
    assert "faketoken" not in text and fk.CLIENT_ID not in text and "Basic" not in text
    for p in (tmp_path / "cache").rglob("*.json"):
        body = p.read_text()
        assert "faketoken" not in body and fk.CLIENT_ID not in body


@pytest.mark.parametrize("setup,reason", [
    (lambda f: setattr(f, "stale_hash", True), "queryid_changed"),
    (lambda f: setattr(f, "block_after", 0), "blocked"),
    (lambda f: setattr(f, "empty_shell", True), "empty_shell"),
    (lambda f: setattr(f, "token_status", 429), "rate_limited"),
])
def test_failures_are_recorded_as_reason_codes(tmp_path, setup, reason):
    path, _ = surface(tmp_path)
    fake = world()
    setup(fake)
    r = go(tmp_path, "verify", {"transport": fake, "now": lambda: NOW}, surface_path=path)
    assert r["outcome"] == "fail" and r["reason_codes"] == [reason]
    assert po.verify_gate(tmp_path / "cache", "gql_anon", surface_path=path, max_age_days=7,
                          today=TODAY) == "probe_failed"


def test_budget_bounds_the_run(tmp_path, monkeypatch):
    path, _ = surface(tmp_path)
    fake = world()
    fake.page_size = 1  # 50+ pages to the day start: the 120-request budget ends the run
    fake.posts = [(f"t3_c{i}", "CryptoCurrency", at(-24 + i / 10), "u", "talk", "") for i in range(510)]
    r = go(tmp_path, "verify", {"transport": fake, "now": lambda: NOW}, surface_path=path)
    assert r["outcome"] == "fail" and r["reason_codes"] == ["budget_exhausted"]
    assert r["counts"]["requests"] == len(fake.calls) == 120 and r["limits_hit"] == ["requests"]


def test_invalid_requests_block_is_a_failure_not_a_send(tmp_path):
    raw = fk.section_raw()
    raw["requests"]["operations"]["posts"]["header_template"]["Cookie"] = "a=b"
    _, section = surface(tmp_path, raw)
    fake = world()
    r = go(tmp_path, "bootstrap", {"transport": fake, "section": section, "now": lambda: NOW})
    assert r["outcome"] == "fail" and r["reason_codes"] == ["schema_mismatch"] and fake.calls == []


def test_production_dependencies_default_deny(tmp_path):
    base = wq.load().config
    path, _ = surface(tmp_path)
    with pytest.raises(po.ProbeRefused, match="surface_unpublished"):
        pg.build_dependencies(dataclasses.replace(base, reddit_surface_path=None))
    with pytest.raises(po.ProbeRefused, match="route_not_admitted"):
        pg.build_dependencies(dataclasses.replace(base, reddit_surface_path=str(path), x_proxy_required=True))
