"""T130: weights v2 (search vote group, early-source gate, weight 0 parked, per-day weights versions).
Pure scoring on in-memory series, plus the fixture world for history and snapshots; every path in tmp_path."""
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
from api.tests.analytics.attention.test_discovery import (
    END,
    SUB,
    WEIGHTS,
    put_change,
    world,
)

V2 = {"trends": 25, "reddit": 20, "xsearch": 15, "exchange_activity": 15, "wikipedia": 10, "defillama": 5,
      "github_dev": 0}
GROUPS = {"search": ["trends", "wikipedia"]}
EARLY = ["trends", "reddit", "xsearch"]
SERIES = {"exchange_activity": "coingecko"}   # the slot falls back to CoinGecko when no exchange has data


def v2cfg(**over):
    return {"source_weights": dict(V2), "source_groups": GROUPS, "early_sources": EARLY, "weights_version": 2,
            "exchange_sub_weights": dict(SUB), "rising_threshold_pct": 10, "trigger_pct": 60,
            "min_covered_weight": 30, "min_history_days": 30, "winsor_percentile": 95, "recent_days": 7,
            "max_source_lag_days": 3, "universe_rules": {"min_narrative_coins": 1}, **over}


def pts(change_pct):
    """130 days ending END: 1.0, then the last 7 days at 1 + change/100, so the source change is `change_pct`."""
    return [(END - timedelta(days=129 - i), 1.0 + (change_pct / 100.0 if i >= 123 else 0.0)) for i in range(130)]


def data_for(changes: dict[str, float]):
    """{weighted source: change %} -> the `data` mapping `_coin` reads; every other series unavailable."""
    data = {(s, "A"): SourceSeries(s, "A", [], "unavailable") for s in disc.WEIGHTED_SOURCES}
    for s in (*disc.EXCHANGE_SERIES.values(), disc.FALLBACK_SERIES):
        data[(s, "A")] = SourceSeries(s, "A", [], "unavailable")
    for s, c in changes.items():
        name = SERIES.get(s, s)
        data[(name, "A")] = SourceSeries(name, "A", pts(c), "ok")
    return data


def score(changes, cfg=None):
    c = disc._coin("A", cfg or v2cfg(), data_for(changes), END, 7, 30, 3)
    return None if c is None else {"score": c[0], "covered": c[1], "rising": c[2], "trigger": c[3]}


# ---- rescale with v2 weights ------------------------------------------------------------------

@pytest.mark.parametrize("changes", [
    {"trends": 20, "reddit": 0},
    {"trends": 50, "exchange_activity": -10, "wikipedia": 5},
    {"reddit": 30, "xsearch": 15, "defillama": 40},
])
def test_score_rescales_over_available_v2_weight(changes):
    r = score(changes)
    want = sum(V2[s] * c for s, c in changes.items()) / sum(V2[s] for s in changes)
    assert r["score"] == pytest.approx(want, rel=1e-6)
    assert r["covered"] == sum(V2[s] for s in changes)


# ---- search vote group ------------------------------------------------------------------------

@pytest.mark.parametrize("changes, rising", [
    ({"trends": 20, "wikipedia": 0}, 35),     # 25/35 rising inside the group: the group votes 35
    ({"trends": 0, "wikipedia": 20}, 0),      # 10/35: the group does not rise
    ({"trends": 20, "wikipedia": 20}, 35),
    ({"wikipedia": 20}, 10),                  # only wikipedia available: 10/10
    ({"trends": 20, "wikipedia": 0, "reddit": 20}, 55),
    ({"trends": 0, "wikipedia": 20, "reddit": 20}, 20),
])
def test_search_group_votes_once(changes, rising):
    r = score(changes)
    assert r["rising"] == rising
    assert r["covered"] == sum(V2[s] for s in changes)   # covered weight is unchanged by grouping


def test_group_threshold_is_half_of_available_group_weight():
    cfg = v2cfg(source_weights={**V2, "wikipedia": 25})   # 25 vs 25: exactly 50% rises
    assert score({"trends": 0, "wikipedia": 20}, cfg)["rising"] == 50


# ---- early-source gate ------------------------------------------------------------------------

@pytest.mark.parametrize("changes, trigger", [
    ({"exchange_activity": 50, "defillama": 50, "wikipedia": 50}, False),   # confirming only: never
    ({"exchange_activity": 50, "wikipedia": 50, "defillama": 50, "trends": 0}, False),   # early present, flat
    ({"reddit": 20, "exchange_activity": 20}, True),                         # early rising + confirming
    ({"xsearch": 20, "exchange_activity": 20}, True),                        # 30 covered: exactly the floor
    ({"trends": 20, "wikipedia": 0}, True),
    ({"reddit": 20}, False),                                                 # 20 < min_covered_weight 30
    ({"reddit": 20, "exchange_activity": 0, "defillama": 0, "wikipedia": 0}, False),   # 20/50 < 60%
])
def test_early_source_gate(changes, trigger):
    assert score(changes)["trigger"] is trigger


def test_confirming_only_never_triggers_even_without_gate_violation_elsewhere():
    r = score({"exchange_activity": 90, "wikipedia": 90, "defillama": 90})
    assert r["rising"] == r["covered"] == 30 and r["trigger"] is False


def test_without_new_keys_scoring_is_v1():
    cfg = {k: v for k, v in v2cfg(source_weights=dict(WEIGHTS)).items()
           if k not in ("source_groups", "early_sources", "weights_version")}
    r = score({"wikipedia": 20, "exchange_activity": 20}, cfg)
    assert (r["covered"], r["rising"], r["trigger"]) == (35, 35, True)


# ---- weight 0: parked -------------------------------------------------------------------------

def test_weight_zero_source_is_ignored_and_not_read():
    data = data_for({"reddit": 20, "exchange_activity": 20})
    data[("github_dev", "A")] = SourceSeries("github_dev", "A", pts(500), "ok")
    c = disc._coin("A", v2cfg(), data, END, 7, 30, 3)
    assert c[1] == 35 and "github_dev" not in {s.source for s in c[4]}
    assert "github_dev" not in disc.series_names(v2cfg())


def test_weight_zero_series_still_read_when_an_older_version_weights_it():
    cfg = v2cfg(weights_history=[{"weights_version": 1, "until": "2026-10-01", "source_weights": dict(WEIGHTS),
                                  "source_groups": {}, "early_sources": []}])
    assert "github_dev" in disc.series_names(cfg)


def test_sources_panel_shows_parked_source_off_and_uncounted(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.delenv("X_LIVE", raising=False)
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]}, source_weights=V2, source_groups=GROUPS,
          early_sources=EARLY, weights_version=2)
    src_mod.clear_cache()
    res = src_mod.build_sources(TODAY)
    gh = next(r for r in res.sources if r.id == "github_dev")
    assert (gh.state, gh.weight) == ("off", 0) and "parked" in gh.note
    assert res.total_sources == 6


# ---- load validation --------------------------------------------------------------------------

def test_v2_shape_loads(tmp_path):
    p = tmp_path / "d.json"
    p.write_text(json.dumps(v2cfg()))
    assert disc.load_config(p)["early_sources"] == EARLY


def test_weights_need_not_sum_to_100(tmp_path):
    p = tmp_path / "d.json"
    p.write_text(json.dumps(v2cfg()))
    assert sum(disc.load_config(p)["source_weights"].values()) == 90


HIST1 = {"weights_version": 1, "until": "2026-10-21", "source_weights": dict(WEIGHTS), "source_groups": {},
         "early_sources": []}


@pytest.mark.parametrize("over", [
    {"early_source": EARLY},                                       # unknown top-level key (typo)
    {"source_weights": {**V2, "reddit": -1}},
    {"source_weights": {**V2, "github": 5}},
    {"source_weights": {k: 0 for k in V2}},                        # nothing weighted
    {"early_sources": ["trends", "tiktok"]},
    {"early_sources": "trends"},
    {"source_groups": {"search": ["trends", "google"]}},
    {"source_groups": {"search": ["trends", "wikipedia"], "social": ["reddit", "trends"]}},   # trends twice
    {"source_groups": {"search": []}},
    {"source_groups": ["trends"]},
    {"weights_version": 0},
    {"weights_version": 2.5},
    {"weights_history": [{**HIST1, "weights_version": 2}]},       # not below the current version
    {"weights_history": [{**HIST1, "until": "21-10-2026"}]},
    {"weights_history": [{**HIST1, "extra": 1}]},
    {"weights_history": [{**HIST1, "source_weights": {**WEIGHTS, "wikipedia": -1}}]},
    {"weights_history": [HIST1, {**HIST1, "until": "2026-10-01"}]},   # versions and dates not increasing
    {"weights_history": [HIST1]} | {"weights_version": None},
])
def test_invalid_v2_config_is_rejected(tmp_path, over):
    p = tmp_path / "d.json"
    p.write_text(json.dumps({**v2cfg(), **over}))
    with pytest.raises(ValueError):
        disc.load_config(p)


# ---- weights versions by day ------------------------------------------------------------------

def test_shipped_config_is_v3_with_v1_v2_history():
    c = disc.load_config()
    assert c["source_weights"] == V2 and c["source_groups"] == GROUPS and c["early_sources"] == EARLY
    assert c["weights_version"] == 3   # T204: v3 = v2 weights + fallback_coverage_only
    assert (c["rising_threshold_pct"], c["trigger_pct"], c["min_covered_weight"], c["min_history_days"]) == (
        10, 60, 30, 30)
    old = disc.weights_for_day(c, date(2026, 10, 21))
    new = disc.weights_for_day(c, date(2026, 10, 22))
    assert (old["weights_version"], old["source_weights"]) == (1, WEIGHTS)
    assert old["source_groups"] == {} and old["early_sources"] == []
    assert (new["weights_version"], new["source_weights"]) == (2, V2)
    assert disc.weights_for_day(c, date(2026, 10, 27))["weights_version"] == 3


def frozen_mismatches(cfg: dict, records: list[dict]) -> list[str]:
    """Frozen records not scored with the weights `weights_for_day(cfg, day)` gives for their day.

    What a record was scored with is its `weights` (T150), else its OWN config's version for its day (pre-T130 configs have no history, so
    that is their top-level weights), its `weights_version` (1 when absent), and, as evidence from the rows, each
    row's covered weight = the sum of those weights over the sources it lists."""
    out = []
    for rec in records:
        day, name = date.fromisoformat(rec["date"]), f"{rec['date']}_w{rec['window']}"
        want = disc.weights_for_day(cfg, day)
        used = rec.get("weights") or disc.weights_for_day(rec["config"], day)
        if used["source_weights"] != want["source_weights"]:
            out.append(f"{name}: weights")
        elif rec.get("weights_version", 1) != want["weights_version"]:
            out.append(f"{name}: version")
        elif any(abs(r["covered_weight"] - sum(want["source_weights"][SLOT_OF.get(x["source"], x["source"])]
                                               for x in r["sources"])) > 1e-9 for r in rec["rows"]):
            out.append(f"{name}: rows")
    return out


SLOT_OF = {disc.FALLBACK_SERIES: disc.SLOT}   # a row lists the CoinGecko fallback in the exchange slot's place


def _frozen(day: str, config: dict, version: int | None, covered=(35.0,), sources=("wikipedia", "coingecko")):
    rec = {"date": day, "window": 30, "config": config,
           "rows": [{"covered_weight": c, "sources": [{"source": s} for s in sources]} for c in covered]}
    return rec if version is None else {**rec, "weights_version": version}


HIST2 = {"weights_version": 2, "until": "2026-10-26", "source_weights": V2, "source_groups": GROUPS,
         "early_sources": EARLY}   # T204: v2 is history; v3 adds only fallback_coverage_only
SHIPPED_LIKE = {"weights_version": 2, "source_weights": V2, "source_groups": GROUPS, "early_sources": EARLY,
                "weights_history": [HIST1]}
OLD_CODE_CFG = {"source_weights": dict(WEIGHTS)}   # a record frozen by pre-T130 code: v1 weights, no history


@pytest.mark.parametrize("rec, bad", [
    (_frozen("2026-10-20", OLD_CODE_CFG, None), False),                 # pre-T130 code, v1 day
    (_frozen("2026-10-21", SHIPPED_LIKE, 1), False),                    # T130 code, v1 day: full config stored
    (_frozen("2026-10-22", SHIPPED_LIKE, 2, covered=(25.0,)), False),   # T130 code, v2 day
    (_frozen("2026-10-22", OLD_CODE_CFG, None), True),                  # the race: old code froze a v2 day
    (_frozen("2026-10-21", SHIPPED_LIKE, 2), True),                     # version disagrees with the table
    (_frozen("2026-10-21", SHIPPED_LIKE, 1, covered=(25.0,)), True),    # rows were not scored with v1
])
def test_frozen_mismatch_check(rec, bad):
    """T150: the guard must read the weights a record was SCORED with (its own config's version for its day),
    not the stored top-level `source_weights`, which since T130 is the current version."""
    assert bool(frozen_mismatches(disc.load_config() | {"weights_history": [HIST1, HIST2]}, [rec])) is bad


def test_committed_frozen_snapshots_match_their_days_weights():
    """D10 guard: every committed frozen day keeps the weights it was scored with. A refresh by pre-change code
    that freezes a day after `weights_history[-1].until` fails here; then move `until` to that day."""
    folder = Path(disc.CONFIG_PATH).parent / "cache" / "attention" / "signals"
    records = [json.loads(p.read_text()) for p in sorted(folder.glob("*_w*.json"))]
    assert records
    assert frozen_mismatches(disc.load_config(), records) == []


HIST_TEST = {"weights_version": 1, "until": (END - timedelta(days=3)).isoformat(),
             "source_weights": dict(WEIGHTS), "source_groups": {}, "early_sources": []}


def _vworld(tmp_path, monkeypatch, **over):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]}, source_weights=V2, source_groups=GROUPS,
          early_sources=EARLY, weights_version=2, min_history_days=30, **over)
    put_change("wikipedia", "A", 2.0, 1.0)
    put_change("coingecko", "A", 2.0, 1.0)


def test_history_scores_each_day_with_its_version(isolated_cache, tmp_path, monkeypatch):
    _vworld(tmp_path, monkeypatch, weights_history=[HIST_TEST])
    h = {d.date: d for d in hist.coin_history("A", 7, today=TODAY).days}
    v1_day, v2_day = h[HIST_TEST["until"]], h[END.isoformat()]
    assert v1_day.weights_version == 1 and v2_day.weights_version == 2
    assert v1_day.covered_weight == 35 and v2_day.covered_weight == 25
    assert v1_day.trigger is True and v2_day.trigger is False   # wikipedia + exchange: confirming only


def test_v1_chart_day_unchanged_by_v2_switch(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]}, min_history_days=30)
    put_change("wikipedia", "A", 2.0, 1.0)
    put_change("coingecko", "A", 2.0, 1.0)
    before = {d.date: d.model_dump() for d in hist.coin_history("A", 7, today=TODAY).days}
    hist.clear_cache()
    _vworld(tmp_path, monkeypatch, weights_history=[HIST_TEST])
    after = {d.date: d.model_dump() for d in hist.coin_history("A", 7, today=TODAY).days}
    for day, row in before.items():
        if day <= HIST_TEST["until"]:
            assert after[day] == row
    assert after[END.isoformat()] != before[END.isoformat()]


def test_category_history_day_carries_version(isolated_cache, tmp_path, monkeypatch):
    _vworld(tmp_path, monkeypatch, weights_history=[HIST_TEST])
    h = {d.date: d for d in hist.category_history("ai", 7, today=TODAY).days}
    assert h[HIST_TEST["until"]].weights_version == 1 and h[END.isoformat()].weights_version == 2


def test_live_response_carries_version(isolated_cache, tmp_path, monkeypatch):
    _vworld(tmp_path, monkeypatch, weights_history=[HIST_TEST])
    assert disc.build_discovery(30, today=TODAY).weights_version == 2
    early = disc.build_discovery(30, today=date.fromisoformat(HIST_TEST["until"]) + timedelta(days=1))
    assert early.weights_version == 1


def test_new_snapshot_records_weights_version(isolated_cache, tmp_path, monkeypatch):
    _vworld(tmp_path, monkeypatch, weights_history=[HIST_TEST])
    snaps.take_snapshot(TODAY)
    rec = json.loads((isolated_cache / "attention" / "signals" / f"{END.isoformat()}_w7.json").read_text())
    assert rec["weights_version"] == 2
    assert {r["weights_version"] for r in snaps.read_snapshots(END, END)} == {2}


@pytest.mark.parametrize("offset, version", [(-1, 1), (0, 1), (1, 2)])   # day before, boundary day, day after
def test_snapshot_records_the_weights_it_was_scored_with(isolated_cache, tmp_path, monkeypatch, offset, version):
    """T150: a new record stores the weights version USED for its day (`weights`), its label equals that version,
    and its rows' covered weights are sums of those weights (wikipedia + CoinGecko slot: v1 35, v2 25)."""
    _vworld(tmp_path, monkeypatch, weights_history=[HIST_TEST])
    day = date.fromisoformat(HIST_TEST["until"]) + timedelta(days=offset)
    snaps.take_snapshot(day + timedelta(days=1))
    rec = json.loads((isolated_cache / "attention" / "signals" / f"{day.isoformat()}_w7.json").read_text())
    used = WEIGHTS if version == 1 else V2
    assert rec["weights_version"] == rec["weights"]["weights_version"] == version
    assert rec["weights"]["source_weights"] == used
    assert [r["covered_weight"] for r in rec["rows"]] == [used["wikipedia"] + used["exchange_activity"]]
    assert frozen_mismatches(disc.load_config(), [rec]) == []


def test_frozen_v1_snapshot_is_not_rewritten_and_reads_as_v1(isolated_cache, tmp_path, monkeypatch):
    _vworld(tmp_path, monkeypatch, weights_history=[HIST_TEST])
    folder = isolated_cache / "attention" / "signals"
    folder.mkdir(parents=True, exist_ok=True)
    old = {"date": END.isoformat(), "window": 7, "categories_as_of": "2026-10-14", "config_hash": "0" * 16,
           "config": {"source_weights": WEIGHTS}, "categories": [],
           "rows": [{"date": END.isoformat(), "window": 7, "symbol": "A", "category_ids": ["ai"], "score": 1.0,
                     "covered_weight": 35, "rising_weight": 35, "trigger": True, "sources": []}]}
    path = folder / f"{END.isoformat()}_w7.json"
    path.write_text(json.dumps(old))
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    out = {o["window"]: o for o in snaps.take_snapshot(TODAY)}
    assert out[7]["status"] == "config-changed"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
    rows = snaps.read_snapshots(END, END, 7)
    assert [(r["symbol"], r["weights_version"], r["trigger"]) for r in rows] == [("A", 1, True)]
