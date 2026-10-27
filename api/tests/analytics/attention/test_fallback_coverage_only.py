"""T204: the CoinGecko volume fallback in the exchange_activity slot counts for coverage only, never as a rising vote.
Versioned like weights (weights v3 = v2 weights + `fallback_coverage_only`), so frozen days keep the old rule."""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from api.analytics.attention import discovery as disc
from api.analytics.attention import discovery_history as hist
from api.analytics.attention import signal_snapshots as snaps
from api.analytics.attention import sources as src_mod
from api.data.attention.types import SourceSeries
from api.tests.analytics.attention.conftest import TODAY
from api.tests.analytics.attention.test_discovery import END, put_change, world
from api.tests.analytics.attention.test_weights_v2 import EARLY, GROUPS, V2, pts, v2cfg

SIGNALS = Path(disc.CONFIG_PATH).parent / "cache" / "attention" / "signals"
# Each source's registry series; the exchange slot is filled by `exchange` (a real exchange) or the fallback.
SERIES = {"exchange": "exchange_volume", "fallback": disc.FALLBACK_SERIES}


def v3cfg(**over):
    return v2cfg(weights_version=3, fallback_coverage_only=True, **over)


def data_for(changes: dict[str, float]):
    data = {(s, "A"): SourceSeries(s, "A", [], "unavailable")
            for s in (*disc.WEIGHTED_SOURCES, *disc.EXCHANGE_SERIES.values(), disc.FALLBACK_SERIES)}
    for s, c in changes.items():
        name = SERIES.get(s, s)
        data[(name, "A")] = SourceSeries(name, "A", pts(c), "ok")
    return data


def score(changes, cfg):
    c = disc._coin("A", cfg, data_for(changes), END, 7, 30, 3)
    return None if c is None else {"score": c[0], "covered": c[1], "rising": c[2], "trigger": c[3], "sources": c[4]}


# ---- scoring rule -----------------------------------------------------------------------------

def test_fallback_only_coin_never_votes_but_keeps_coverage():
    old, new = score({"fallback": 50}, v2cfg()), score({"fallback": 50}, v3cfg())
    assert old["covered"] == new["covered"] == 15
    assert old["rising"] == 15 and new["rising"] == 0
    assert new["trigger"] is False
    assert new["score"] == pytest.approx(old["score"])   # the score still reads the CoinGecko change


def test_fallback_vote_was_the_difference():
    """reddit 20 rising + CoinGecko rising: old rule 35/35 triggers; new rule 20/35 (57%) does not."""
    changes = {"reddit": 30, "fallback": 30}
    old, new = score(changes, v2cfg()), score(changes, v3cfg())
    assert (old["covered"], old["rising"], old["trigger"]) == (35, 35, True)
    assert (new["covered"], new["rising"], new["trigger"]) == (35, 20, False)


def test_real_exchange_still_votes():
    changes = {"reddit": 30, "exchange": 30}
    new = score(changes, v3cfg())
    assert (new["covered"], new["rising"], new["trigger"]) == (35, 35, True)
    assert new == score(changes, v2cfg())
    slot = next(s for s in new["sources"] if s.source == disc.SLOT)
    assert slot.coverage_only is False


@pytest.mark.parametrize("cg, old_rising", [(-5, 25), (30, 40)])
def test_trends_rising_with_coingecko_only(cg, old_rising):
    """Trends 25 rising + CoinGecko 15: rising 25 of covered 40 = 62.5% >= 60, so it still triggers either way."""
    old, new = score({"trends": 20, "fallback": cg}, v2cfg()), score({"trends": 20, "fallback": cg}, v3cfg())
    assert old["covered"] == new["covered"] == 40
    assert (old["rising"], new["rising"]) == (old_rising, 25)
    assert old["trigger"] is new["trigger"] is True


def test_fallback_cannot_open_the_early_gate():
    """A slot listed as an early source: the fallback still never counts as that early source rising."""
    cfg = v3cfg(early_sources=["exchange_activity"])
    assert score({"wikipedia": 30, "fallback": 30}, cfg)["trigger"] is False
    assert score({"wikipedia": 30, "fallback": 30}, v2cfg(early_sources=["exchange_activity"]))["trigger"] is True


def test_fallback_source_is_labelled_coverage_only():
    new = score({"trends": 20, "fallback": 5}, v3cfg())
    cg = next(s for s in new["sources"] if s.source == disc.FALLBACK_SERIES)
    assert cg.coverage_only is True
    old = score({"trends": 20, "fallback": 5}, v2cfg())
    assert next(s for s in old["sources"] if s.source == disc.FALLBACK_SERIES).coverage_only is False


def test_payload_is_additive():
    """Old source fields keep their names and values; `coverage_only` is the only new key."""
    old = score({"trends": 20, "fallback": 5}, v2cfg())["sources"]
    new = score({"trends": 20, "fallback": 5}, v3cfg())["sources"]
    for o, n in zip(old, new):
        od, nd = o.model_dump(), n.model_dump()
        assert set(nd) - set(od) == set() and set(nd) == {"source", "change", "as_of", "members", "coverage_only"}
        assert {k: v for k, v in nd.items() if k != "coverage_only"} == {
            k: v for k, v in od.items() if k != "coverage_only"}


# ---- config and versions ----------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["yes", 1, None])
def test_flag_must_be_a_bool(bad):
    with pytest.raises(ValueError, match="fallback_coverage_only"):
        disc.validate_config(v3cfg(fallback_coverage_only=bad))


def test_weights_for_day_carries_the_flag():
    hist_v2 = {"weights_version": 2, "until": "2026-10-26", "source_weights": dict(V2), "source_groups": GROUPS,
               "early_sources": EARLY}
    cfg = disc.validate_config(v3cfg(weights_history=[hist_v2]))
    assert disc.weights_for_day(cfg, date(2026, 10, 26))["fallback_coverage_only"] is False
    assert disc.weights_for_day(cfg, date(2026, 10, 27))["fallback_coverage_only"] is True


def test_shipped_config_changes_only_the_rule():
    cfg = disc.load_config()
    v2, v3 = disc.weights_for_day(cfg, date(2026, 10, 26)), disc.weights_for_day(cfg, date(2026, 10, 27))
    assert (v2["weights_version"], v3["weights_version"]) == (2, 3)
    assert (v2["fallback_coverage_only"], v3["fallback_coverage_only"]) == (False, True)
    for k in ("source_weights", "source_groups", "early_sources"):
        assert v2[k] == v3[k]
    assert (cfg["rising_threshold_pct"], cfg["trigger_pct"], cfg["min_covered_weight"]) == (10, 60, 30)


# ---- history safety ---------------------------------------------------------------------------

def rule_boundary(cfg: dict) -> date:
    """First day scored with the coverage-only rule: the day after the last version without it."""
    old = [h for h in cfg.get("weights_history", []) if not h.get("fallback_coverage_only")]
    return date.fromisoformat(old[-1]["until"]) + timedelta(days=1)


def frozen_without_rule(records: list[dict]) -> list[date]:
    """Days frozen by code or config that did not apply the rule (no `weights.fallback_coverage_only`)."""
    return [date.fromisoformat(r["date"]) for r in records if not (r.get("weights") or {}).get("fallback_coverage_only")]


def boundary_violations(cfg: dict, records: list[dict]) -> list[date]:
    """PR #163 guard pattern: the boundary must lie AFTER every day frozen without the rule. A day frozen by
    pre-change code at or after the boundary would hold the old rule for a day the table gives to the new one."""
    b = rule_boundary(cfg)
    return sorted({d for d in frozen_without_rule(records) if d >= b})


@pytest.mark.parametrize("frozen_day, bad", [("2026-10-25", False), ("2026-10-26", False), ("2026-10-27", True)])
def test_boundary_guard_catches_old_code_freezing_a_new_day(frozen_day, bad):
    rec = {"date": frozen_day, "window": 7, "weights": {"weights_version": 2}}
    assert bool(boundary_violations(disc.load_config(), [rec])) is bad


def test_boundary_guard_accepts_a_new_rule_record_after_the_boundary():
    rec = {"date": "2026-10-27", "window": 7, "weights": {"weights_version": 3, "fallback_coverage_only": True}}
    assert boundary_violations(disc.load_config(), [rec]) == []


def test_committed_frozen_days_lie_before_the_rule_boundary():
    """Fails if a committed record frozen without the rule is dated at/after the boundary; then move v2 `until`."""
    records = [json.loads(p.read_text()) for p in sorted(SIGNALS.glob("*_w*.json"))]
    assert records
    assert boundary_violations(disc.load_config(), records) == []
    assert rule_boundary(disc.load_config()) > max(frozen_without_rule(records))


# sha256 of every frozen record committed before T204: they are authoritative and never rewritten.
FROZEN_SHA256 = {
    "2026-10-17_w30.json": "eb4730e44d5f7f17d86fc1e704a87c69b1a247d4fc1ab41aca0555f226bbcdde",
    "2026-10-17_w7.json": "597fb394fcfc3207c5f8adfc35e57827f39cf81e6cff031787678a2e76d6aef1",
    "2026-10-17_w90.json": "09946558044b0bfa7093dfeb5fe1ab586eca6b762fd89301b807eb01ec9909ac",
    "2026-10-18_w30.json": "fdbb7401920807edeb3e47cd1c0d5cca7fca4ed94128020eeca7251c3a355477",
    "2026-10-18_w7.json": "ee120bfd03204136e6c0fc0b897b39ed78ea399b1aa1e758eb779fba0047c886",
    "2026-10-18_w90.json": "ae58a70d41ead6c933715f47bced3a615f2a37b96362d9dbdac69e2da05a90fe",
    "2026-10-19_w30.json": "b63eee4ee5fc142ab0efdb2db7ad43291578291c10cad9b020c39cfdb75dd138",
    "2026-10-19_w7.json": "d6045cbd3d0ac20869ccf628bff2c42b9a3e2990f436f26e028cbfe20c4a0697",
    "2026-10-19_w90.json": "9d60169c843433b739dd993d41681edff52fc14acf3e7e6692b6ad4572d1842d",
    "2026-10-20_w30.json": "fe57a71878435f78eef4edd1ad00d6625991dd5e37130cab46b7cc1476ae3f9e",
    "2026-10-20_w7.json": "674c166245a53f66b118df75b1b11688e719ae2cdebbd1ff3307860a2dc21143",
    "2026-10-20_w90.json": "bb8badc85b2779217f60df2fc0031bb3833a96567005f9cb8e96e3122a9911e8",
    "2026-10-21_w30.json": "683c90e6c72f20aca1acf495548b2037634c98946600ff08d05667244325cf19",
    "2026-10-21_w7.json": "c36d34389045f68dccadc2146c56048a487eb4e1597ce8260bacefb33d64383d",
    "2026-10-21_w90.json": "8d84bcedc77f28398dc81e06522f26e2742bee4b4cc7d130fb845505705a2928",
    "2026-10-22_w30.json": "19fb2815b4f55e53480c1392df7d8ca3525e8b6f3afd0436ad9b7fc92f7a46ed",
    "2026-10-22_w7.json": "39a6fa00289bd174eb4e2c6f3daf376af8237c332f594d19908959b211d046c8",
    "2026-10-22_w90.json": "f0c93e113ec250760e0790efa73bb2c46395667d37f45e791def9cbe336ac317",
    "2026-10-23_w30.json": "f0eb06c89ff33c4c9448ab3969ba1f2229370b8df980f38cf2f6639bdf6405f7",
    "2026-10-23_w7.json": "f8b956899fa37bb0f35e49b82f764726a0bb08ad85583cebb4519ed3ccde5a87",
    "2026-10-23_w90.json": "794c6dc34a5769edc453fc4f2d49efaa74866833609931da3f4f76ad08d4fa6a",
    "2026-10-24_w30.json": "c9177ea31ee02697af10d8df07904cc4aa3edbf4c5a4816242fc1867d9ea8cd5",
    "2026-10-24_w7.json": "b7d1c72ceaf5bbeb37c8ebc5ffa15a6615df6897128c2a2ed642c8177cf568e1",
    "2026-10-24_w90.json": "19f4e387da8686a8910ee3a1b9c993b349047be994557481d5a1ad00d5817165",
    "2026-10-25_w30.json": "a7c116c519c2fc731856f47394828f5404c4d3c4a330a71745d3d20aff44ba42",
    "2026-10-25_w7.json": "f03f0021816fb502c47cecf048e1faf73c9d899e84a13578a51cb0698178d008",
    "2026-10-25_w90.json": "f19f719555ebb6fa2e0adabe73426c82d504f026709a743bf6b7df02ad672647",
}


@pytest.mark.parametrize("name", sorted(FROZEN_SHA256))
def test_committed_frozen_records_are_byte_identical(name):
    assert hashlib.sha256((SIGNALS / name).read_bytes()).hexdigest() == FROZEN_SHA256[name]


HIST_V2 = {"weights_version": 2, "until": (END - timedelta(days=3)).isoformat(), "source_weights": dict(V2),
           "source_groups": GROUPS, "early_sources": EARLY}


def _rworld(tmp_path, monkeypatch):
    """Coin A: reddit and CoinGecko both rising (no exchange data); v2 up to END-3, v3 after."""
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]}, source_weights=V2, source_groups=GROUPS,
          early_sources=EARLY, weights_version=3, fallback_coverage_only=True, weights_history=[HIST_V2],
          min_history_days=30)
    put_change("reddit", "A", 2.0, 1.0)
    put_change("coingecko", "A", 2.0, 1.0)


def test_chart_recompute_uses_the_rule_version_of_each_day(isolated_cache, tmp_path, monkeypatch):
    _rworld(tmp_path, monkeypatch)
    h = {d.date: d for d in hist.coin_history("A", 7, today=TODAY).days}
    old_day, new_day = h[HIST_V2["until"]], h[END.isoformat()]
    assert (old_day.weights_version, old_day.covered_weight, old_day.rising_weight, old_day.trigger) == (2, 35, 35, True)
    assert (new_day.weights_version, new_day.covered_weight, new_day.rising_weight, new_day.trigger) == (3, 35, 20, False)
    cat = {d.date: d for d in hist.category_history("ai", 7, today=TODAY).days}
    assert (cat[HIST_V2["until"]].triggered_count, cat[END.isoformat()].triggered_count) == (1, 0)


@pytest.mark.parametrize("offset, rule", [(0, False), (1, True)])   # boundary day keeps the old rule, next day new
def test_new_snapshot_records_the_rule_it_was_scored_with(isolated_cache, tmp_path, monkeypatch, offset, rule):
    _rworld(tmp_path, monkeypatch)
    day = date.fromisoformat(HIST_V2["until"]) + timedelta(days=offset)
    snaps.take_snapshot(day + timedelta(days=1))
    rec = json.loads((isolated_cache / "attention" / "signals" / f"{day.isoformat()}_w7.json").read_text())
    assert rec["weights"]["fallback_coverage_only"] is rule
    assert [(r["rising_weight"], r["trigger"]) for r in rec["rows"]] == [(20, False) if rule else (35, True)]


def test_existing_frozen_record_is_not_rewritten_by_the_new_rule(isolated_cache, tmp_path, monkeypatch):
    _rworld(tmp_path, monkeypatch)
    folder = isolated_cache / "attention" / "signals"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{END.isoformat()}_w7.json"
    path.write_text(json.dumps({"date": END.isoformat(), "window": 7, "config_hash": "0" * 16, "rows": []}))
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    out = {o["window"]: o for o in snaps.take_snapshot(TODAY)}
    assert out[7]["status"] == "config-changed"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha


def test_live_payload_marks_the_fallback(isolated_cache, tmp_path, monkeypatch):
    _rworld(tmp_path, monkeypatch)
    coin = disc.build_discovery(7, today=TODAY).categories[0].coins[0]
    assert (coin.covered_weight, coin.rising_weight, coin.trigger) == (35, 20, False)
    assert [(s.source, s.coverage_only) for s in coin.sources] == [("reddit", False), ("coingecko", True)]


def test_sources_panel_labels_the_fallback_coverage_only(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.delenv("X_LIVE", raising=False)
    _rworld(tmp_path, monkeypatch)
    src_mod.clear_cache()
    res = src_mod.build_sources(TODAY)
    cg = next(r for r in res.sources if r.id == disc.FALLBACK_SERIES)
    slot = next(r for r in res.sources if r.id == disc.SLOT)
    assert cg.label == "CoinGecko volume (coverage only)"
    assert "coverage only" in slot.note and "never a rising vote" in slot.note


def test_sources_panel_keeps_the_old_label_before_the_boundary(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.delenv("X_LIVE", raising=False)
    _rworld(tmp_path, monkeypatch)
    src_mod.clear_cache()
    res = src_mod.build_sources(date.fromisoformat(HIST_V2["until"]) + timedelta(days=1))
    assert next(r for r in res.sources if r.id == disc.FALLBACK_SERIES).label == "CoinGecko (volume fallback)"
