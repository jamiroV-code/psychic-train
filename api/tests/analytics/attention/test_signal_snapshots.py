"""W9: the daily frozen Discovery snapshot. Fixture world as in test_discovery.py; every path in tmp_path."""
from __future__ import annotations

import json
from datetime import date, timedelta

from api.analytics.attention import discovery as disc, signal_snapshots as snaps
from api.data.attention import categories_store, registry, store, universe_store
from api.data.attention.types import SourceSeries
from api.tests.analytics.attention.conftest import TODAY
from api.tests.analytics.attention.test_discovery import END, SUB, WEIGHTS, cfg, gain, put_change, world


def _world(tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7, "B": 6e7}, cats={"ai": ["A", "B"], "defi": ["A"]})
    gain("A")
    put_change("wikipedia", "B", 1.0, 1.0)


def _files(root):
    return sorted(p.name for p in (root / "attention" / "signals").glob("*.json"))


def test_snapshot_equals_live_result(isolated_cache, tmp_path, monkeypatch):
    _world(tmp_path, monkeypatch)
    out = snaps.take_snapshot(TODAY)
    assert {o["status"] for o in out} == {"written"}
    rows = snaps.read_snapshots(END, END, 30)
    live = disc.build_discovery(30, today=TODAY)
    expect = {c.symbol: c for cat in live.categories for c in cat.coins}
    assert {r["symbol"] for r in rows} == set(expect)
    for r in rows:
        c = expect[r["symbol"]]
        assert (r["date"], r["window"]) == (END.isoformat(), 30)
        assert r["score"] == c.raw_change and r["trigger"] == c.trigger
        assert (r["covered_weight"], r["rising_weight"]) == (c.covered_weight, c.rising_weight)
        assert r["sources"] == [{"source": s.source, "change": s.change, "as_of": s.as_of} for s in c.sources]
    assert next(r for r in rows if r["symbol"] == "A")["category_ids"] == ["ai", "defi"]
    assert next(r for r in rows if r["symbol"] == "B")["category_ids"] == ["ai"]


def test_three_windows_one_record_each(isolated_cache, tmp_path, monkeypatch):
    _world(tmp_path, monkeypatch)
    snaps.take_snapshot(TODAY)
    d = END.isoformat()
    assert _files(isolated_cache) == [f"{d}_w30.json", f"{d}_w7.json", f"{d}_w90.json"]
    assert {r["window"] for r in snaps.read_snapshots(END, END)} == {7, 30, 90}


def test_record_carries_config_and_hash(isolated_cache, tmp_path, monkeypatch):
    _world(tmp_path, monkeypatch)
    snaps.take_snapshot(TODAY)
    rec = json.loads((isolated_cache / "attention" / "signals" / f"{END.isoformat()}_w7.json").read_text())
    assert rec["config"]["source_weights"] == WEIGHTS and rec["config"]["exchange_sub_weights"] == SUB
    assert rec["config"]["trigger_pct"] == 60 and rec["config_hash"] == snaps.config_hash(rec["config"])


def test_rerun_is_idempotent(isolated_cache, tmp_path, monkeypatch):
    _world(tmp_path, monkeypatch)
    snaps.take_snapshot(TODAY)
    before = {n: (isolated_cache / "attention" / "signals" / n).read_bytes() for n in _files(isolated_cache)}
    out = snaps.take_snapshot(TODAY)
    assert {o["status"] for o in out} == {"exists"}
    assert before == {n: (isolated_cache / "attention" / "signals" / n).read_bytes() for n in _files(isolated_cache)}


def test_changed_config_is_reported_not_written(isolated_cache, tmp_path, monkeypatch):
    _world(tmp_path, monkeypatch)
    snaps.take_snapshot(TODAY)
    before = (isolated_cache / "attention" / "signals" / f"{END.isoformat()}_w7.json").read_bytes()
    w = dict(WEIGHTS, wikipedia=30, trends=20)
    monkeypatch.setattr(disc, "CONFIG_PATH", cfg(tmp_path, source_weights=w))
    out = snaps.take_snapshot(TODAY)
    assert {o["status"] for o in out} == {"config-changed"}
    assert all(o["stored_hash"] != o["current_hash"] for o in out)
    assert before == (isolated_cache / "attention" / "signals" / f"{END.isoformat()}_w7.json").read_bytes()


def test_later_data_does_not_rewrite_the_day(isolated_cache, tmp_path, monkeypatch):
    _world(tmp_path, monkeypatch)
    snaps.take_snapshot(TODAY)
    before = snaps.read_snapshots(END, END, 7)
    put_change("reddit", "A", 5.0, 1.0)      # a source fed later in the day
    put_change("wikipedia", "B", 9.0, 1.0)
    live = {c.symbol: c.raw_change for cat in disc.build_discovery(7, today=TODAY).categories for c in cat.coins}
    assert live["A"] != next(r for r in before if r["symbol"] == "A")["score"]  # live moved, stored must not
    snaps.take_snapshot(TODAY)
    assert snaps.read_snapshots(END, END, 7) == before


def test_snapshot_for_day_d_uses_data_up_to_d_only(isolated_cache, tmp_path, monkeypatch):
    _world(tmp_path, monkeypatch)
    ref = TODAY
    pts = [(TODAY + timedelta(days=i), 1000.0) for i in range(1, 8)]   # future days, huge values
    store.write_series(SourceSeries("wikipedia", "A", pts, "ok"), today=TODAY + timedelta(days=10))
    snaps.take_snapshot(ref)
    a = next(r for r in snaps.read_snapshots(END, END, 7) if r["symbol"] == "A")
    assert a["sources"][0]["as_of"] <= END.isoformat()
    assert all(s["as_of"] <= END.isoformat() for s in a["sources"])
    assert a["score"] < 500


def test_no_data_writes_nothing(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats=None)
    out = snaps.take_snapshot(TODAY)
    assert {o["status"] for o in out} == {"no-data"}
    assert _files(isolated_cache) == []


def test_reader_range_filter_and_summary(isolated_cache, tmp_path, monkeypatch):
    _world(tmp_path, monkeypatch)
    snaps.take_snapshot(TODAY)
    snaps.take_snapshot(TODAY + timedelta(days=1))
    snaps.take_snapshot(TODAY + timedelta(days=2))
    d0, d1, d2 = END, END + timedelta(days=1), END + timedelta(days=2)
    assert {r["date"] for r in snaps.read_snapshots(d0, d1, 7)} == {d0.isoformat(), d1.isoformat()}
    assert {r["date"] for r in snaps.read_snapshots(d2, d2, 7)} == {d2.isoformat()}
    assert snaps.read_snapshots(d0, d2, 14) == []
    assert snaps.read_snapshots(d2, d0, 7) == []
    s = snaps.summarize(snaps.read_snapshots(d0, d2, 7))
    assert s["days"] == 3 and s["coins"] == 2
    assert set(s["triggers_per_day"]) == {d.isoformat() for d in (d0, d1, d2)}
    assert snaps.summarize([]) == {"days": 0, "coins": 0, "triggers_per_day": {}}


def test_unreadable_record_is_skipped_by_reader(isolated_cache, tmp_path, monkeypatch):
    _world(tmp_path, monkeypatch)
    snaps.take_snapshot(TODAY)
    (isolated_cache / "attention" / "signals" / f"{END.isoformat()}_w7.json").write_text("{trunc")
    assert snaps.read_snapshots(END, END, 7) == []
    assert snaps.read_snapshots(END, END, 30)


def test_signals_dir_is_not_a_source(isolated_cache, tmp_path, monkeypatch):
    _world(tmp_path, monkeypatch)
    snaps.take_snapshot(TODAY)
    assert "signals" not in disc.series_names(disc.load_config()) and "signals" not in registry.FETCHERS
    assert registry.read_series("signals", "A", TODAY).state == "not-probed"
    assert store.read_points("signals", "A") == []
    assert categories_store.read_latest()["date"] == "2026-10-15"
    assert universe_store.read_latest()["date"] == "2026-10-15"
    # sources that glob the store per source name never see it
    assert not list((isolated_cache / "attention" / "signals").glob("*.parquet"))
