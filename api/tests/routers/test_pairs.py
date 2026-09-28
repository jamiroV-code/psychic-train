"""GET /api/pairs + GET /api/pairs/{a}/{b} (cointegration-screener RFC-003, plan §11).

TestClient against the real app; `isolated_cache` throughout; tmp universe file.
The router only reads the persisted cache — `compute_pair_stats` is patched to
fail during every request to prove it.
"""
from __future__ import annotations

import json
import math
import statistics
import time

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.analytics.cointegration import pairs_response, stats
from api.data import cache
from api.main import app
from api.tests.pairs_fixtures import (
    ohlcv_frame,
    seed_realistic_results,
    seed_small_universe,
    write_universe,
)

client = TestClient(app)


@pytest.fixture
def seeded(isolated_cache, tmp_path, monkeypatch):
    coins = seed_small_universe(tmp_path, monkeypatch)
    pairs_response.compute_and_persist()

    def no_compute(*a, **k):
        raise AssertionError("router recomputed statistics on request")
    monkeypatch.setattr(stats, "compute_pair_stats", no_compute)
    monkeypatch.setattr(stats, "bh_adjust", no_compute)
    return coins


def _walk(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)
    else:
        yield obj


# ---------------------------------------------------------------- table

def test_table_shape_every_pair_present(seeded):
    r = client.get("/api/pairs")
    assert r.status_code == 200
    body = r.json()
    assert body["computation_status"] == "fresh" and body["stale_reason"] is None
    assert body["universe_size"] == 5 and body["pair_count"] == 10 == len(body["pairs"])
    assert body["min_overlap_days"] == stats.MIN_OVERLAP_DAYS
    assert body["diagnostic_scope"] == "whole_history_in_sample"
    assert "in-sample" in body["diagnostic_disclosure"]
    assert body["computed_at"]


def test_no_nan_and_nulls_only_where_documented(seeded):
    body = client.get("/api/pairs").json()
    for v in _walk(body):
        assert not (isinstance(v, float) and not math.isfinite(v))
    for p in body["pairs"]:
        if p["status"] == "ok":
            assert p["reason"] is None
            for k in ("eg_p_raw", "eg_p_bh", "eg_direction", "eg_p_other_direction", "half_life",
                      "z_score", "overlap_days", "sample_start", "sample_end"):
                assert p[k] is not None, k
            # AC-6: Johansen present alongside EG, never merged
            assert p["johansen"] is not None and p["johansen_reason"] is None
            assert set(p["johansen"]) == {"trace_stat", "crit_value_95", "rank_at_least_1"}
        else:
            assert p["reason"]
            for k in ("eg_p_raw", "eg_p_bh", "johansen", "half_life", "z_score"):
                assert p[k] is None, k
        if p["status"] == "coin_unavailable":
            assert p["overlap_days"] is None and p["sample_start"] is None


def test_sorted_bh_ascending_non_ok_last(seeded):
    ps = client.get("/api/pairs").json()["pairs"]
    statuses = [p["status"] for p in ps]
    assert statuses[:3] == ["ok"] * 3 and "ok" not in statuses[3:]
    bh = [p["eg_p_bh"] for p in ps[:3]]
    assert bh == sorted(bh)
    assert ps[0]["coin_a"] == "AAA" and ps[0]["coin_b"] == "BBB"  # the planted cointegrated pair


def _tie_row(a, b, bh, raw, status="ok"):
    return {"coin_a": a, "coin_b": b, "status": status, "eg_p_bh": bh, "eg_p_raw": raw}


def test_sort_tie_on_bh_breaks_by_raw_p():
    table = pd.DataFrame([
        _tie_row("AAA", "BBB", 0.05, 0.03),
        _tie_row("CCC", "DDD", 0.05, 0.01),
        _tie_row("EEE", "FFF", None, None, status="insufficient_overlap"),
    ])
    rows = pairs_response._sorted_rows(table)
    assert [(r["coin_a"], r["coin_b"]) for r in rows] == [("CCC", "DDD"), ("AAA", "BBB"), ("EEE", "FFF")]


def test_sort_tie_on_bh_and_raw_falls_back_to_names():
    table = pd.DataFrame([
        _tie_row("ZZZ", "BBB", 0.05, 0.01),
        _tie_row("AAA", "YYY", 0.05, 0.01),
        _tie_row("AAA", "CCC", 0.05, 0.01),
        _tie_row("BCH", "NEW", None, None, status="coin_unavailable"),
    ])
    rows = pairs_response._sorted_rows(table)
    assert [(r["coin_a"], r["coin_b"]) for r in rows] == [
        ("AAA", "CCC"), ("AAA", "YYY"), ("ZZZ", "BBB"), ("BCH", "NEW")]


# ---------------------------------------------------------------- staleness (a)-(e) + D-2..D-4

def test_a_results_unavailable(isolated_cache, tmp_path, monkeypatch):
    seed_small_universe(tmp_path, monkeypatch)
    r = client.get("/api/pairs")
    assert r.status_code == 200
    b = r.json()
    assert b["computation_status"] == "results_unavailable" and b["pairs"] == []
    assert "compute_pairs.py" in b["stale_reason"] and b["computed_at"] is None
    d = client.get("/api/pairs/AAA/BBB").json()
    assert d["computation_status"] == "results_unavailable" and d["pair"] is None


def test_b_universe_changed_serves_surviving_rows_only(seeded, tmp_path, monkeypatch):
    write_universe(tmp_path, monkeypatch, ["AAA", "BBB", "CCC", "FFF"])
    b = client.get("/api/pairs").json()
    assert b["computation_status"] == "stale"
    assert "universe changed: added FFF; removed DDD, EEE" in b["stale_reason"]
    pairs = {(p["coin_a"], p["coin_b"]) for p in b["pairs"]}
    assert pairs == {("AAA", "BBB"), ("AAA", "CCC"), ("BBB", "CCC")}
    d = client.get("/api/pairs/AAA/FFF").json()
    assert d["computation_status"] == "stale" and d["pair"] is None


def test_c_newer_bars_is_stale(seeded):
    df = cache.read_ohlcv("AAA", "1d")
    extra = ohlcv_frame(np.array([df.close.iloc[-1]]), end=pd.Timestamp("2026-09-26", tz="UTC"))
    cache.write_ohlcv("AAA", "1d", pd.concat([df, extra], ignore_index=True))
    b = client.get("/api/pairs").json()
    assert b["computation_status"] == "stale"
    assert "AAA has newer bars (cache 2026-09-26, results 2026-09-25)" in b["stale_reason"]
    assert len(b["pairs"]) == 10  # last-known-good rows still served


def test_bar_count_decrease_is_stale(seeded):
    df = cache.read_ohlcv("BBB", "1d")
    cache.write_ohlcv("BBB", "1d", df.iloc[10:])  # same last date, fewer bars (D-4)
    b = client.get("/api/pairs").json()
    assert b["computation_status"] == "stale" and "BBB bar count changed 500 → 490" in b["stale_reason"]


def test_d_fresh(seeded):
    b = client.get("/api/pairs").json()
    assert b["computation_status"] == "fresh" and b["stale_reason"] is None


@pytest.mark.parametrize("field,value,needle", [
    ("statsmodels_version", "0.0.1", "computed with statsmodels 0.0.1; installed"),
    ("eg_autolag", "bic", "computed with eg_autolag=bic; current aic"),
])
def test_e_config_mismatch_is_stale(seeded, field, value, needle):
    path = cache.pairs_provenance_path()
    prov = json.loads(path.read_text())
    prov[field] = value
    path.write_text(json.dumps(prov))
    b = client.get("/api/pairs").json()
    assert b["computation_status"] == "stale" and needle in b["stale_reason"]


def test_corrupt_cache_is_results_unavailable(seeded):
    cache.pairs_provenance_path().write_text("{not json")
    r = client.get("/api/pairs")
    assert r.status_code == 200
    b = r.json()
    assert b["computation_status"] == "results_unavailable" and "unreadable" in b["stale_reason"]


def test_bad_universe_file_is_500(seeded, tmp_path):
    (tmp_path / "pairs_universe.json").write_text("not json")
    r = client.get("/api/pairs")
    assert r.status_code == 500 and "not valid JSON" in r.json()["detail"]
    assert client.get("/api/pairs/AAA/BBB").status_code == 500


# ---------------------------------------------------------------- detail + path params

def test_detail_ok_pair(seeded):
    r = client.get("/api/pairs/AAA/BBB")
    assert r.status_code == 200
    d = r.json()
    p = d["pair"]
    assert d["computation_status"] == "fresh" and p["status"] == "ok"
    assert len(p["spread"]) == 500 and set(p["spread"][0]) == {"date", "spread", "z_score"}
    assert p["eg_a_on_b"]["dependent"] == "AAA" and p["eg_b_on_a"]["dependent"] == "BBB"
    assert p["spread_direction"] == p["eg_direction"]
    assert p["half_life_ar1_beta"] is not None
    assert p["z_score"] == pytest.approx(p["spread"][-1]["z_score"])


def test_detail_non_ok_pair_has_empty_spread(seeded):
    p = client.get("/api/pairs/AAA/EEE").json()["pair"]
    assert p["status"] == "coin_unavailable" and p["spread"] == [] and p["reason"]
    p = client.get("/api/pairs/DDD/AAA").json()["pair"]
    assert p["status"] == "insufficient_overlap" and p["spread"] == []


def test_detail_reverse_order_and_case_insensitive(seeded):
    base = client.get("/api/pairs/AAA/BBB").json()["pair"]
    for url in ("/api/pairs/aaa/bbb", "/api/pairs/BBB/AAA", "/api/pairs/bbb/Aaa"):
        assert client.get(url).json()["pair"] == base


def test_self_pair_422(seeded):
    r = client.get("/api/pairs/AAA/AAA")
    assert r.status_code == 422 and r.json()["detail"] == "a and b must be different coins"
    assert client.get("/api/pairs/zzzz/ZZZZ").status_code == 422  # self-pair precedes 404


def test_unknown_ticker_404(seeded):
    r = client.get("/api/pairs/AAA/ZZZZ")
    assert r.status_code == 404 and r.json()["detail"] == "ZZZZ is not in the pair-screener universe"


def test_malformed_ticker_422(seeded):
    assert client.get("/api/pairs/AAA/BB-B").status_code == 422


def test_johansen_refused_row_serves_ok_with_reason(isolated_cache, tmp_path, monkeypatch):
    seed_small_universe(tmp_path, monkeypatch)

    def refuse(*a, **k):
        raise stats.JohansenNumericallyUnstable("Johansen numerically unstable: max|imag(eig)|=1e-03 > 1e-09")
    monkeypatch.setattr(stats, "johansen", refuse)
    pairs_response.compute_and_persist()
    p = client.get("/api/pairs/AAA/BBB").json()["pair"]
    assert p["status"] == "ok" and p["johansen"] is None
    assert p["johansen_reason"].startswith("Johansen numerically unstable")
    assert p["eg_p_raw"] is not None and p["z_score"] is not None and p["spread"]


# ---------------------------------------------------------------- read-path timing gate (E8, D-8)

def _p95(xs):
    return sorted(xs)[max(0, math.ceil(0.95 * len(xs)) - 1)]


def test_read_path_timing_gate(isolated_cache, tmp_path, monkeypatch, capsys):
    seed_realistic_results(tmp_path, monkeypatch)
    assert client.get("/api/pairs").json()["computation_status"] == "fresh"
    client.get("/api/pairs/C00/C01")  # warm
    report = {}
    for name, url in (("table", "/api/pairs"), ("detail", "/api/pairs/C00/C01")):
        ts = []
        for _ in range(20):
            t = time.perf_counter()
            r = client.get(url)
            ts.append(time.perf_counter() - t)
            assert r.status_code == 200
        report[name] = (statistics.median(ts), _p95(ts))
    with capsys.disabled():
        for name, (med, p95) in report.items():
            soft = "under" if p95 < 0.5 else "OVER"
            print(f"\n[pairs timing] {name}: median {med * 1000:.0f} ms, p95 {p95 * 1000:.0f} ms "
                  f"({soft} 500 ms soft budget)")
    for name, (_, p95) in report.items():
        assert p95 < 3.0, f"{name} p95 {p95:.2f}s >= 3s"
