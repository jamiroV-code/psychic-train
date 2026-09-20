"""Macro-liquidity composite: `reduced` (4-part, deep FRED/DefiLlama
history) and `full` (6-part, via LiqTide's own endpoint, valid only from
the 2024-01-11 cutover) variants, plus the date/availability-aware variant
selector (ADR-2, items 33-35).

Stage 0 research finding (RFC-002, re-confirmed against the live LiqTide
endpoint): LiqTide's own `metrics` series only go back to ~2024-09 (net
liquidity, dollar) / ~2025-06 (btc_dom) — nowhere near deep enough for the
2017/2020-21 backtest (item 40). This is exactly why ADR-2 requires the
`reduced` composite to be built independently from FRED
(`fred_adapter.py`, decades of history) and DefiLlama (`defillama_adapter.py`,
stablecoin supply back to 2017-11-29 — item 32's probe confirmed sufficient
depth) rather than from LiqTide's own short-lived endpoint. The `full`
composite intentionally reuses LiqTide directly (consumption option 1,
`data-sources/all-data-sources.md`) since its own history already covers
its entire valid date range (>= 2024-01-11).

Known, documented data-availability gap (ADR-1 precedent: "document, never
silently guess"): no free, keyless, deep-history (back to 2017) BTC-dominance
series was found at Stage 0 — CoinGecko's historical global-market-cap-chart
endpoint is confirmed paid-tier-only. The reduced composite's BTC-dominance
component is therefore built only from whatever LiqTide `btc_dom` history
has actually accumulated locally (from the day this adapter first ran
onward) rather than backfilled; a date with no cached `btc_dom` value
contributes no value for that component only (never zero-filled), so the
2017/2020-21 backtest (item 40, Hybrid gate) is run and reviewed on the
net-liquidity + dollar-strength + stablecoin-supply components for
pre-accumulation dates. Recorded again in the backtest script and Test
Infra Improvement Notes, not just here.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from api.data import cache, defillama_adapter, fred_adapter, liqtide_adapter

CUTOVER_DATE = pd.Timestamp("2024-01-11", tz="utc")

# The full-composite inputs this plan reads from LiqTide (see
# liqtide_adapter.METRIC_KEYS) — all four must be available for a given
# date for `select_composite_variant` to pick "full" at/after the cutover
# (ADR-2: "per-input availability re-checked at read time, not assumed from
# the date alone").
FULL_COMPOSITE_INPUTS = liqtide_adapter.METRIC_KEYS

ZSCORE_MIN_PERIODS = 5  # need at least this many points before a z-score is meaningful

NET_LIQUIDITY_ROC_DAYS = 28  # ~4wk change, calendar days
DOLLAR_ROC_DAYS = 30  # ~1mo change
BTC_DOM_ROC_DAYS = 30
STABLECOIN_ROC_DAYS = 7  # data-sources doc's weight table: "7-day change"


@dataclass
class CompositeResult:
    variant: str  # "reduced" | "full"
    series: pd.DataFrame  # columns: date, composite (mean of available z-scored components)
    available: bool


def _zscore(series: pd.Series) -> pd.Series:
    """Expanding z-score against the series' own history-to-date — ADR-1's
    `ZSCORE_BASELINE="expanding"` discipline (`leg_boundary.py`) applied
    here too, for the same reason: these input series are themselves short
    and a fixed trailing window would shrink the effective sample further.
    """
    mean = series.expanding(min_periods=ZSCORE_MIN_PERIODS).mean()
    std = series.expanding(min_periods=ZSCORE_MIN_PERIODS).std()
    z = (series - mean) / std
    return z.replace([np.inf, -np.inf], np.nan)


def _roc(series: pd.Series, window_days: int) -> pd.Series:
    return series.pct_change(periods=window_days)


def build_reduced_composite(
    date_range: tuple[pd.Timestamp, pd.Timestamp] | None = None,
) -> CompositeResult:
    """4-part reduced composite (ADR-2, stablecoin-supply included per item
    32's probe confirming sufficient DefiLlama depth): net-liquidity
    4wk-change + dollar-strength 1mo-change (inverted — a stronger dollar
    is liquidity-tightening, matching the weight table's own "inverted"
    annotation) + stablecoin-supply 7d-change + BTC-dominance 30d-trend
    (inverted — rising dominance is rotation OUT of alts), each
    expanding-z-scored and averaged across whichever components have data
    for a given date (never zero-filled for a missing component — this
    project's general "unavailable, never neutral" discipline; item 32's
    probe result is one specific instance of it).
    """
    net_liq = fred_adapter.fetch_net_liquidity()
    dollar = fred_adapter.fetch_series(fred_adapter.BROAD_DOLLAR)
    stables = defillama_adapter.fetch_stablecoin_supply()
    liqtide_history = cache.read_liqtide_history()

    frames: list[pd.DataFrame] = []

    if not net_liq.df.empty:
        nl = net_liq.df.rename(columns={"value": "net_liquidity"}).copy()
        nl["net_liquidity_z"] = _zscore(_roc(nl["net_liquidity"], NET_LIQUIDITY_ROC_DAYS))
        frames.append(nl[["date", "net_liquidity_z"]])

    if not dollar.df.empty:
        d = dollar.df.rename(columns={"value": "dollar"}).copy()
        # inverted: rising dollar -> tightening -> negative liquidity signal
        d["dollar_z"] = -_zscore(_roc(d["dollar"], DOLLAR_ROC_DAYS))
        frames.append(d[["date", "dollar_z"]])

    if not stables.df.empty:
        s = stables.df.rename(columns={"value": "stables"}).copy()
        s["stables_z"] = _zscore(_roc(s["stables"], STABLECOIN_ROC_DAYS))
        frames.append(s[["date", "stables_z"]])

    if liqtide_history is not None and not liqtide_history.empty and "btc_dom" in liqtide_history.columns:
        bd = liqtide_history[["date", "btc_dom"]].dropna(subset=["btc_dom"]).copy()
        bd["date"] = pd.to_datetime(bd["date"], utc=True)
        bd = bd.sort_values("date")
        # inverted: rising BTC dominance -> rotation OUT of alts -> negative
        # signal for an "alt-rotation" liquidity-regime read.
        bd["btc_dom_z"] = -_zscore(_roc(bd["btc_dom"], BTC_DOM_ROC_DAYS))
        frames.append(bd[["date", "btc_dom_z"]])

    if not frames:
        return CompositeResult(variant="reduced", series=pd.DataFrame(columns=["date", "composite"]), available=False)

    merged = frames[0]
    for f in frames[1:]:
        merged = pd.merge(merged, f, on="date", how="outer")
    merged = merged.sort_values("date")
    z_cols = [c for c in merged.columns if c != "date"]
    merged["composite"] = merged[z_cols].mean(axis=1, skipna=True)
    merged = merged.dropna(subset=["composite"])

    if date_range is not None:
        start, end = date_range
        merged = merged[(merged["date"] >= start) & (merged["date"] <= end)]

    return CompositeResult(variant="reduced", series=merged[["date", "composite"]].reset_index(drop=True), available=not merged.empty)


def build_full_composite(
    date_range: tuple[pd.Timestamp, pd.Timestamp] | None = None,
) -> CompositeResult:
    """6-part full composite, valid only >= CUTOVER_DATE (ADR-2) — consumed
    directly from LiqTide's own archived history (consumption option 1),
    not reproduced input-by-input. LiqTide's own `tide_score` already IS
    the finished 6-part composite (its `tide_index.components`/`weights`
    cover all six per the data-sources doc's weight table) — this function
    reads the archived daily payloads (`cache/liqtide/*.parquet`, written
    by `liqtide_adapter.fetch_latest`) and z-scores `tide_score` the same
    way `build_reduced_composite` z-scores its own inputs, so both variants
    are comparable on the same scale for `leg_boundary.py`'s detection rule.
    """
    history = cache.read_liqtide_history()
    if history is None or history.empty or "tide_score" not in history.columns:
        return CompositeResult(variant="full", series=pd.DataFrame(columns=["date", "composite"]), available=False)

    df = history.dropna(subset=["tide_score"]).copy()
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.sort_values("date")
    df = df[df["date"] >= CUTOVER_DATE]
    df["composite"] = _zscore(df["tide_score"])
    df = df.dropna(subset=["composite"])

    if date_range is not None:
        start, end = date_range
        df = df[(df["date"] >= start) & (df["date"] <= end)]

    return CompositeResult(variant="full", series=df[["date", "composite"]].reset_index(drop=True), available=not df.empty)


def _full_composite_inputs_available_for(date: pd.Timestamp) -> bool:
    """ADR-2: the full composite is only selected when every one of its
    inputs is actually available for the given date, re-checked at read
    time, not assumed from the date alone.
    """
    history = cache.read_liqtide_history()
    if history is None or history.empty:
        return False
    history = history.copy()
    history["date"] = pd.to_datetime(history["date"], utc=True)
    row = history[history["date"] == pd.Timestamp(date).normalize()]
    if row.empty:
        return False
    first = row.iloc[0]
    return all(col in row.columns and pd.notna(first[col]) for col in FULL_COMPOSITE_INPUTS)


def select_composite_variant(date: pd.Timestamp) -> str:
    """ADR-2's rule: `date >= CUTOVER_DATE` AND every full-composite input
    actually available for that date -> `"full"`, else `"reduced"`.
    """
    ts = pd.Timestamp(date)
    if ts.tzinfo is None:
        ts = ts.tz_localize("utc")
    if ts >= CUTOVER_DATE and _full_composite_inputs_available_for(ts):
        return "full"
    return "reduced"
