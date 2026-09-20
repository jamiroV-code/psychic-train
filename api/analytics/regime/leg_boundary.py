"""Fork A leg-boundary: statistical candidate detection (ADR-1) +
price-structure confirmation (items 37-38), plus the `CurrentLegState`
orchestration that assembles both into the real input
`benchmark.select_active_benchmark` (item 44) consumes.

Candidates never silently disappear once detected (ADR-3) — callers always
receive both `candidate_boundaries` and `confirmed_boundaries`.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from api.analytics.regime import liquidity_composite
from api.data import ccxt_adapter
from api.models.regime import CurrentLegState, LegBoundary

# ADR-1's named constants — reviewable/changeable in one place, per the same
# discipline as the |z| >= 1.5 threshold itself (VALIDATE finding).
ROC_WINDOW_DAYS = 14
ZSCORE_BASELINE = "expanding"
ZSCORE_MIN_PERIODS = 5
ZSCORE_THRESHOLD = 1.5
SUSTAINED_DAYS = 5

# Price-structure confirmation (item 38).
CONFIRMATION_WINDOW_DAYS = 10
STRUCTURE_LOOKBACK_BARS = 20  # bars either side used to establish prior swing structure


@dataclass
class BoundaryCandidate:
    date: pd.Timestamp
    z_score: float


@dataclass
class BoundaryConfirmation:
    candidate_date: pd.Timestamp
    confirmed: bool
    confirmed_date: pd.Timestamp | None


def detect_candidate_boundaries(composite_series: pd.DataFrame) -> list[BoundaryCandidate]:
    """ADR-1: rolling `ROC_WINDOW_DAYS`-day rate-of-change of the composite,
    z-scored against its own expanding (`ZSCORE_BASELINE`) history, flags a
    candidate date where `|z| >= ZSCORE_THRESHOLD` sustained for
    `>= SUSTAINED_DAYS` consecutive points. `composite_series` has columns
    `date`, `composite` — already the caller's chosen variant (reduced or
    full, ADR-2/`select_composite_variant`).
    """
    if composite_series is None or composite_series.empty or len(composite_series) < ROC_WINDOW_DAYS + 1:
        return []

    df = composite_series.sort_values("date").reset_index(drop=True)
    roc = df["composite"].pct_change(periods=ROC_WINDOW_DAYS)
    mean = roc.expanding(min_periods=ZSCORE_MIN_PERIODS).mean()
    std = roc.expanding(min_periods=ZSCORE_MIN_PERIODS).std()
    z = ((roc - mean) / std).replace([np.inf, -np.inf], np.nan)

    sustained = z.abs() >= ZSCORE_THRESHOLD
    sustained = sustained.fillna(False)
    run_id = (sustained != sustained.shift()).cumsum()
    run_len = sustained.groupby(run_id).cumcount() + 1

    # Only the first bar of a qualifying run is the candidate's date — once
    # flagged, the rest of the sustained run is the same event, not a new
    # candidate every day it stays sustained.
    flagged = sustained & (run_len >= SUSTAINED_DAYS)
    first_of_run = flagged & ~flagged.shift(fill_value=False)

    candidates: list[BoundaryCandidate] = []
    for idx in df.index[first_of_run]:
        candidates.append(BoundaryCandidate(date=df.loc[idx, "date"], z_score=float(z.loc[idx])))
    return candidates


def _has_structure_shift(btc_price_df: pd.DataFrame, center_idx: int) -> bool:
    """BTC higher-high/higher-low (or mirrored lower-low/lower-high)
    structure shift check around `center_idx` (item 38): compares the swing
    high/low in the `STRUCTURE_LOOKBACK_BARS` window before `center_idx`
    against the window after it.
    """
    lo = max(0, center_idx - STRUCTURE_LOOKBACK_BARS)
    hi = min(len(btc_price_df), center_idx + STRUCTURE_LOOKBACK_BARS)
    before = btc_price_df.iloc[lo:center_idx]
    after = btc_price_df.iloc[center_idx:hi]
    if before.empty or after.empty:
        return False
    before_high, before_low = before["high"].max(), before["low"].min()
    after_high, after_low = after["high"].max(), after["low"].min()
    up_shift = after_high > before_high and after_low > before_low
    down_shift = after_high < before_high and after_low < before_low
    return bool(up_shift or down_shift)


def confirm_boundaries(
    candidates: list[BoundaryCandidate], btc_price_df: pd.DataFrame
) -> list[BoundaryConfirmation]:
    """Item 38: a candidate is confirmed when BTC's price structure shows a
    higher-high/higher-low (or mirrored lower-low/lower-high) shift within
    +/- `CONFIRMATION_WINDOW_DAYS` trading days of the candidate date.
    Unconfirmed candidates are still returned (ADR-3) with
    `confirmed=False`, never dropped.
    """
    if btc_price_df is None or btc_price_df.empty:
        return [BoundaryConfirmation(candidate_date=c.date, confirmed=False, confirmed_date=None) for c in candidates]

    df = btc_price_df.sort_values("timestamp").reset_index(drop=True)
    results: list[BoundaryConfirmation] = []

    for c in candidates:
        deltas = (df["timestamp"] - c.date).abs()
        center_idx = int(deltas.idxmin())
        within_window = deltas.iloc[center_idx] <= pd.Timedelta(days=CONFIRMATION_WINDOW_DAYS)
        confirmed = bool(within_window and _has_structure_shift(df, center_idx))
        results.append(
            BoundaryConfirmation(
                candidate_date=c.date,
                confirmed=confirmed,
                confirmed_date=df.loc[center_idx, "timestamp"] if confirmed else None,
            )
        )
    return results


def compute_current_leg_state(as_of: pd.Timestamp | None = None) -> CurrentLegState:
    """Orchestrates variant selection + candidate detection + confirmation
    into the real `CurrentLegState` input `benchmark.select_active_benchmark`
    (item 44) consumes — replaces RFC-001's `RegimeState` stub wholesale.
    Also backs `GET /api/regime/legs` (item 42).
    """
    as_of = as_of or pd.Timestamp.now(tz="utc")
    variant = liquidity_composite.select_composite_variant(as_of)
    composite = (
        liquidity_composite.build_full_composite()
        if variant == "full"
        else liquidity_composite.build_reduced_composite()
    )

    if not composite.available:
        return CurrentLegState(candidate_boundaries=[], confirmed_boundaries=[], composite_variant=variant, has_data=False)

    candidates = detect_candidate_boundaries(composite.series)
    btc_daily = ccxt_adapter.fetch_ohlcv("BTC", "1d")
    confirmations = confirm_boundaries(candidates, btc_daily.df)
    confirmed_by_date = {c.candidate_date: c for c in confirmations if c.confirmed}

    candidate_models = [
        LegBoundary(
            date=c.date.date().isoformat(),
            z_score=c.z_score,
            confirmed=c.date in confirmed_by_date,
            confirmed_date=(
                confirmed_by_date[c.date].confirmed_date.date().isoformat()
                if c.date in confirmed_by_date and confirmed_by_date[c.date].confirmed_date is not None
                else None
            ),
        )
        for c in candidates
    ]
    confirmed_models = [m for m in candidate_models if m.confirmed]

    return CurrentLegState(
        candidate_boundaries=candidate_models,
        confirmed_boundaries=confirmed_models,
        composite_variant=variant,
        has_data=True,
    )
