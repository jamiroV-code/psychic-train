"""Pair screener persistence + response assembly (cointegration-screener RFC-003).

Two paths, deliberately separate (ADR-8 Amendment):

- **Compute path** (`compute_and_persist`) — called only by
  `api/scripts/compute_pairs.py`. Reads OHLCV only via `cache.read_ohlcv`
  (never the network), runs `stats.compute_pair_stats` per pair plus
  `stats.bh_adjust`, and writes spreads, `results.parquet`, then
  `provenance.json` LAST. Provenance is deleted first, so an interrupted run
  reads as `results_unavailable`, never as `fresh`.
- **Read path** (`read_table`, `read_detail`) — called only by the router.
  Persisted-file reads plus the 5-check staleness comparison. Never calls
  `compute_pair_stats` or `bh_adjust`.

Every path goes through `cache.py` helpers resolved from `CACHE_ROOT` at call
time, so `isolated_cache` redirects all of it.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import statsmodels

from api.analytics.cointegration import stats
from api.data import cache, pairs_universe
from api.models.pairs import (
    EGDirectionOut,
    HalfLifeOut,
    JohansenOut,
    PairDetail,
    PairDetailResponse,
    PairsResponse,
    PairSummary,
    SpreadPoint,
)

TIMEFRAME = "1d"
REFRESH_HINT = "run compute_pairs.py to refresh"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso(d: Any) -> str | None:
    return None if d is None else pd.Timestamp(d).date().isoformat()


def _opt(v: Any) -> Any:
    """Parquet round-trips turn None into NaN/NA in numeric columns; map back to None."""
    if v is None or v is pd.NA:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v.item() if hasattr(v, "item") else v


# ------------------------------------------------------------------ compute path

@dataclass(frozen=True)
class ComputeSummary:
    pair_count: int
    status_counts: dict[str, int]
    not_mean_reverting: int
    johansen_refused: int
    bh_significant_05: int
    elapsed_s: float
    provenance: dict


def _direction_label(r: stats.PairStatsResult) -> tuple[str | None, str | None]:
    """(lower-p direction label, other direction's p) — D3."""
    if r.status != "ok" or r.eg_a_on_b is None or r.eg_b_on_a is None:
        return None, None
    main, other = (
        (r.eg_a_on_b, r.eg_b_on_a) if r.eg_rank_direction == "a_on_b" else (r.eg_b_on_a, r.eg_a_on_b)
    )
    return f"{main.dependent}~{main.independent}", other.p_value


def _row(r: stats.PairStatsResult, p_bh: float | None) -> dict:
    label, p_other = _direction_label(r)
    row: dict[str, Any] = {
        "coin_a": r.symbol_a,
        "coin_b": r.symbol_b,
        "status": r.status,
        "reason": r.reason,
        "overlap_days": r.overlap_days,
        "sample_start": _iso(r.sample_start),
        "sample_end": _iso(r.sample_end),
        "eg_p_raw": r.eg_min_p if r.status == "ok" else None,
        "eg_p_bh": p_bh,
        "eg_direction": label,
        "eg_p_other_direction": p_other,
        "johansen_trace_stat": r.johansen.trace_stat_r0 if r.johansen else None,
        "johansen_crit_95": r.johansen.crit_95 if r.johansen else None,
        "johansen_rank_at_least_1": r.johansen.rank_at_least_1 if r.johansen else None,
        "johansen_reason": r.johansen_reason,
        "half_life_state": r.half_life.state if r.half_life else None,
        "half_life_days": r.half_life.days if r.half_life else None,
        "half_life_ar1_beta": r.half_life.ar1_beta if r.half_life else None,
        "z_score": r.zscore,
    }
    for key, eg in (("ab", r.eg_a_on_b), ("ba", r.eg_b_on_a)):
        for f in ("hedge_ratio", "intercept", "t_stat", "p_value"):
            row[f"eg_{key}_{f}"] = getattr(eg, f) if eg else None
    return row


def _spread_frame(spread: pd.Series) -> pd.DataFrame:
    vals = spread.to_numpy(dtype=float)
    z = (vals - vals.mean()) / vals.std(ddof=1)  # ADR-4, per point
    return pd.DataFrame({
        "date": pd.DatetimeIndex(spread.index).tz_localize(None).date
        if pd.DatetimeIndex(spread.index).tz is not None else pd.DatetimeIndex(spread.index).date,
        "spread": vals,
        "z_score": z,
    })


def _atomic_write_bytes(path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _coin_snapshot(coins: list[str]) -> tuple[dict, dict]:
    stats_by_coin = cache.ohlcv_footer_stats_many(coins, TIMEFRAME)
    last = {c: _iso(ts) for c, (_, ts) in stats_by_coin.items()}
    count = {c: int(n) for c, (n, _) in stats_by_coin.items()}
    return last, count


def compute_and_persist() -> ComputeSummary:
    """Compute every pair of the current universe and persist the results cache."""
    t0 = time.perf_counter()
    coins = pairs_universe.load_universe()
    pairs = pairs_universe.enumerate_pairs(coins)

    # E5: cache reads only. Empty frame -> None -> stats maps the pair to coin_unavailable.
    frames: dict[str, pd.DataFrame | None] = {}
    for c in coins:
        df = cache.read_ohlcv(c, TIMEFRAME)
        frames[c] = None if df is None or df.empty else df
    last_bar, bar_count = _coin_snapshot(coins)

    results = [stats.compute_pair_stats(frames[a], frames[b], a, b) for a, b in pairs]
    p_bh = stats.bh_adjust(results)

    # Invalidate first: from here until provenance is rewritten, readers see results_unavailable.
    prov_path = cache.pairs_provenance_path()
    prov_path.parent.mkdir(parents=True, exist_ok=True)  # E9
    prov_path.unlink(missing_ok=True)

    spreads_dir = cache.pairs_spreads_dir()
    staging = spreads_dir.with_name("spreads.tmp")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    for r in results:
        if r.status == "ok" and r.spread is not None:
            _spread_frame(r.spread).to_parquet(
                staging / cache.pairs_spread_path(r.symbol_a, r.symbol_b).name, index=False
            )
    shutil.rmtree(spreads_dir, ignore_errors=True)
    os.replace(staging, spreads_dir)

    table = pd.DataFrame([_row(r, p) for r, p in zip(results, p_bh)])
    res_path = cache.pairs_results_path()
    tmp = res_path.with_name(res_path.name + ".tmp")
    table.to_parquet(tmp, index=False)
    os.replace(tmp, res_path)

    provenance = {
        "computed_at": _utc_now_iso(),
        "universe": coins,
        "per_coin_last_bar_date": last_bar,
        "per_coin_bar_count": bar_count,
        "statsmodels_version": statsmodels.__version__,
        "eg_autolag": stats.EG_AUTOLAG,
    }
    _atomic_write_bytes(prov_path, json.dumps(provenance, indent=2).encode("utf-8"))

    counts = {s: 0 for s in ("ok", "insufficient_overlap", "coin_unavailable")}
    for r in results:
        counts[r.status] += 1
    return ComputeSummary(
        pair_count=len(results),
        status_counts=counts,
        not_mean_reverting=sum(
            1 for r in results if r.half_life is not None and r.half_life.state == "not_mean_reverting"
        ),
        johansen_refused=sum(1 for r in results if r.johansen_reason),
        bh_significant_05=sum(1 for p in p_bh if p is not None and p < 0.05),
        elapsed_s=time.perf_counter() - t0,
        provenance=provenance,
    )


# ------------------------------------------------------------------ read path

@dataclass(frozen=True)
class _Loaded:
    status: str  # fresh | stale | results_unavailable
    reason: str | None
    computed_at: str | None
    table: pd.DataFrame | None


def _staleness_reasons(prov: dict, coins: list[str]) -> list[str]:
    reasons: list[str] = []
    recorded = list(prov.get("universe") or [])
    added = [c for c in coins if c not in recorded]
    removed = [c for c in recorded if c not in coins]
    if added or removed:
        parts = []
        if added:
            parts.append("added " + ", ".join(added))
        if removed:
            parts.append("removed " + ", ".join(removed))
        reasons.append("universe changed: " + "; ".join(parts))

    rec_last = prov.get("per_coin_last_bar_date") or {}
    rec_count = prov.get("per_coin_bar_count") or {}
    current = [c for c in coins if c in recorded]
    now_last, now_count = _coin_snapshot(current)
    for c in current:
        was_d, now_d = rec_last.get(c), now_last[c]
        if now_d is not None and (was_d is None or now_d > was_d):
            reasons.append(f"{c} has newer bars (cache {now_d}, results {was_d})")
        elif int(rec_count.get(c, -1)) != now_count[c]:  # D-4: any change
            reasons.append(f"{c} bar count changed {rec_count.get(c)} → {now_count[c]}")

    installed = statsmodels.__version__
    if prov.get("statsmodels_version") != installed:
        reasons.append(
            f"computed with statsmodels {prov.get('statsmodels_version')}; installed {installed}"
        )
    if prov.get("eg_autolag") != stats.EG_AUTOLAG:
        reasons.append(
            f"computed with eg_autolag={prov.get('eg_autolag')}; current {stats.EG_AUTOLAG}"
        )
    return reasons


def _load(coins: list[str]) -> _Loaded:
    prov_path, res_path = cache.pairs_provenance_path(), cache.pairs_results_path()
    if not prov_path.exists() or not res_path.exists():
        return _Loaded("results_unavailable", f"no results yet — {REFRESH_HINT}", None, None)
    try:
        prov = json.loads(prov_path.read_text(encoding="utf-8"))
        if not isinstance(prov, dict):
            raise ValueError("provenance.json is not an object")
        table = pd.read_parquet(res_path)
    except Exception as exc:  # corrupt cache is a data state, never a 500
        return _Loaded(
            "results_unavailable",
            f"results cache unreadable ({type(exc).__name__}: {exc}) — {REFRESH_HINT}",
            None, None,
        )
    reasons = _staleness_reasons(prov, coins)
    universe = set(coins)
    table = table[table["coin_a"].isin(universe) & table["coin_b"].isin(universe)]  # D-2
    if reasons:
        return _Loaded("stale", "; ".join(reasons) + f" — {REFRESH_HINT}", prov.get("computed_at"), table)
    return _Loaded("fresh", None, prov.get("computed_at"), table)


def _summary_fields(row: dict) -> dict:
    ok = row["status"] == "ok"
    johansen = None
    if ok and _opt(row.get("johansen_trace_stat")) is not None:
        johansen = JohansenOut(
            trace_stat=float(row["johansen_trace_stat"]),
            crit_value_95=float(row["johansen_crit_95"]),
            rank_at_least_1=bool(row["johansen_rank_at_least_1"]),
        )
    hl = None
    if ok and _opt(row.get("half_life_state")) is not None:
        hl = HalfLifeOut(state=row["half_life_state"], days=_opt(row.get("half_life_days")))
    overlap = _opt(row.get("overlap_days"))
    return dict(
        coin_a=row["coin_a"], coin_b=row["coin_b"], status=row["status"],
        reason=_opt(row.get("reason")),
        overlap_days=None if overlap is None else int(overlap),
        sample_start=_opt(row.get("sample_start")), sample_end=_opt(row.get("sample_end")),
        eg_p_raw=_opt(row.get("eg_p_raw")), eg_p_bh=_opt(row.get("eg_p_bh")),
        eg_direction=_opt(row.get("eg_direction")),
        eg_p_other_direction=_opt(row.get("eg_p_other_direction")),
        johansen=johansen, johansen_reason=_opt(row.get("johansen_reason")),
        half_life=hl, z_score=_opt(row.get("z_score")),
    )


def _sorted_rows(table: pd.DataFrame) -> list[dict]:
    rows = table.to_dict("records")
    ok = sorted((r for r in rows if r["status"] == "ok"), key=lambda r: (r["eg_p_bh"], r["coin_a"], r["coin_b"]))
    rest = sorted((r for r in rows if r["status"] != "ok"), key=lambda r: (r["coin_a"], r["coin_b"]))
    return ok + rest


def read_table() -> PairsResponse:
    """GET /api/pairs. Raises `pairs_universe.UniverseFileError` for a bad universe (router -> 500)."""
    coins = pairs_universe.load_universe()
    loaded = _load(coins)
    pairs = [] if loaded.table is None else [PairSummary(**_summary_fields(r)) for r in _sorted_rows(loaded.table)]
    return PairsResponse(
        generated_utc=_utc_now_iso(), computed_at=loaded.computed_at,
        computation_status=loaded.status, stale_reason=loaded.reason,
        universe_size=len(coins), pair_count=len(pairs),
        min_overlap_days=stats.MIN_OVERLAP_DAYS, pairs=pairs,
    )


def _eg(row: dict, key: str) -> EGDirectionOut | None:
    if _opt(row.get(f"eg_{key}_p_value")) is None:
        return None
    a, b = row["coin_a"], row["coin_b"]
    dep, ind = (a, b) if key == "ab" else (b, a)
    return EGDirectionOut(
        dependent=dep, independent=ind,
        **{f: float(row[f"eg_{key}_{f}"]) for f in ("hedge_ratio", "intercept", "t_stat", "p_value")},
    )


def read_detail(a: str, b: str) -> PairDetailResponse:
    """GET /api/pairs/{a}/{b}. `a`/`b` already uppercased and universe-validated by the router."""
    coins = pairs_universe.load_universe()
    loaded = _load(coins)
    envelope = dict(generated_utc=_utc_now_iso(), computed_at=loaded.computed_at)
    if loaded.table is None:
        return PairDetailResponse(**envelope, computation_status=loaded.status,
                                  stale_reason=loaded.reason, pair=None)
    t = loaded.table
    hit = t[((t["coin_a"] == a) & (t["coin_b"] == b)) | ((t["coin_a"] == b) & (t["coin_b"] == a))]
    if hit.empty:  # pair involves a coin added since the last compute -> stale names it
        return PairDetailResponse(**envelope, computation_status=loaded.status,
                                  stale_reason=loaded.reason, pair=None)
    row = hit.iloc[0].to_dict()
    spread: list[SpreadPoint] = []
    if row["status"] == "ok":
        path = cache.pairs_spread_path(row["coin_a"], row["coin_b"])
        try:
            sdf = pd.read_parquet(path)
        except Exception as exc:
            return PairDetailResponse(
                **envelope, computation_status="results_unavailable",
                stale_reason=f"spread file for {row['coin_a']}/{row['coin_b']} unreadable "
                             f"({type(exc).__name__}) — {REFRESH_HINT}",
                pair=None,
            )
        spread = [
            SpreadPoint(date=pd.Timestamp(d).date().isoformat(), spread=float(s), z_score=float(z))
            for d, s, z in zip(sdf["date"], sdf["spread"], sdf["z_score"])
        ]
    fields = _summary_fields(row)
    detail = PairDetail(
        **fields,
        eg_a_on_b=_eg(row, "ab"), eg_b_on_a=_eg(row, "ba"),
        spread_direction=fields["eg_direction"],
        half_life_ar1_beta=_opt(row.get("half_life_ar1_beta")) if row["status"] == "ok" else None,
        spread=spread,
    )
    return PairDetailResponse(**envelope, computation_status=loaded.status,
                              stale_reason=loaded.reason, pair=detail)
