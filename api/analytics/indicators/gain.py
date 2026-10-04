"""Current-candle gain chips (T34 / S2).

Each chip is the newest bar of its timeframe read open to latest price:
`pct = (close - open) / open x 100`. 15m/1h/4h/1d use their own newest bar
(1d therefore means "since 00:00 UTC"); 1w uses the newest Monday-anchored
bucket derived from the daily bars. This module is the single source of
truth for the chip value; the web client only formats it.

A chip with nothing honest to show is N/A with a reason, never 0. A flat
candle (open == close) is a real 0.0.
"""
from __future__ import annotations

import pandas as pd

from api.data import ccxt_adapter, freshness
from api.models.screener import GainChip, Timeframe, UnavailableReason

# Same vocabulary as the chart's own `reason` (RFC-005): adapter status wins
# when it reports a real failure, otherwise the cause is short history.
_STATUS_TO_REASON: dict[str, UnavailableReason] = {
    "bad_symbol": "bad-symbol",
    "unavailable": "source-unavailable",
    "stale": "source-unavailable",
}


def reason_for_status(status: str | None) -> UnavailableReason:
    return _STATUS_TO_REASON.get(status or "", "insufficient-history")


def _na(reason: UnavailableReason) -> GainChip:
    return GainChip(pct=None, open_ts=None, is_partial=False, stale=False, reason=reason)


def _newest_weekly_bucket(daily_df: pd.DataFrame) -> pd.Series | None:
    """The newest bucket of `_derive_weekly_from_daily`, or None when that
    bucket's Monday bar is missing: the derivation labels a bucket with its
    Monday even when the Monday bar is absent, so its `open` would be some
    later day's open (D9)."""
    weekly = ccxt_adapter._derive_weekly_from_daily(daily_df, source="derived")
    if weekly.empty:
        return None
    bucket = weekly.iloc[-1]
    monday = freshness.as_utc(bucket["timestamp"]).normalize()
    daily_days = {freshness.as_utc(ts).normalize() for ts in daily_df["timestamp"]}
    return bucket if monday in daily_days else None


def compute_gain_chip(
    df: pd.DataFrame | None,
    timeframe: Timeframe,
    now,
    status: str | None = None,
    daily_df: pd.DataFrame | None = None,
) -> GainChip:
    """One chip. `now` is the reference time (host clock corrected by skew).

    For `1w`, pass the daily bars as `daily_df` (or as `df`): the chip is
    built from them, and staleness is judged on the newest daily bar (B5).
    """
    if timeframe == "1w":
        source = daily_df if daily_df is not None else df
        if source is None or source.empty:
            return _na(reason_for_status(status))
        bar = _newest_weekly_bucket(source.sort_values("timestamp"))
        if bar is None:
            return _na("insufficient-history")
        stale_ref = source["timestamp"].max()
    else:
        if df is None or df.empty:
            return _na(reason_for_status(status))
        bar = df.sort_values("timestamp").iloc[-1]
        stale_ref = bar["timestamp"]

    open_, close = bar["open"], bar["close"]
    if pd.isna(open_) or pd.isna(close) or open_ <= 0:
        return _na("insufficient-history")
    return GainChip(
        pct=float((close - open_) / open_ * 100.0),
        open_ts=freshness.iso_z(bar["timestamp"]),
        is_partial=bool(freshness.is_partial(bar["timestamp"], timeframe, now)),
        stale=freshness.is_stale(stale_ref, timeframe, now),
        reason=None,
    )


def compute_gain_chips(
    dfs_by_tf: dict[Timeframe, pd.DataFrame],
    statuses_by_tf: dict[Timeframe, str],
    now,
) -> dict[Timeframe, GainChip]:
    """All five chips for one coin; each slot independent of the others."""
    return {
        tf: compute_gain_chip(
            df, tf, now, statuses_by_tf.get(tf),
            daily_df=dfs_by_tf.get("1d") if tf == "1w" else None,
        )
        for tf, df in dfs_by_tf.items()
    }
