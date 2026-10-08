"""Shared pydantic contract between api/analytics, api/routers and web/.

Public Contracts (PLAN.md): these field shapes are authoritative — RFC-002/
RFC-003/RFC-004 code against them, not invent fields ad hoc later.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Timeframe = Literal["15m", "1h", "4h", "1d", "1w"]
TIMEFRAMES: tuple[Timeframe, ...] = ("15m", "1h", "4h", "1d", "1w")

RelativePerformanceTimeframe = Literal["7d", "30d", "90d", "ytd"]

# RFC-005: why a ChartSeries has no data. Before this existed, `available:
# False` was documented as meaning "insufficient history" and was in fact
# produced by three unrelated causes — a misconfigured symbol, a dead data
# source, and genuinely short history — so a config bug reported itself to
# the operator as a history problem.
UnavailableReason = Literal["insufficient-history", "bad-symbol", "source-unavailable"]


class ChartBar(BaseModel):
    timestamp: str
    close: float


class ChartSeries(BaseModel):
    """Pre-computed price + SMA series for one coin's chart, at whichever
    `timeframe` the containing response carries. `MiniChart` (web/) only
    ever renders these — it never fetches or computes itself.
    """

    price: list[ChartBar]
    sma: list[ChartBar]
    available: bool
    # RFC-005: set ONLY when `available` is False. Optional with a None
    # default, so existing consumers that read only `available` are
    # unaffected (additive Public Contract change).
    reason: UnavailableReason | None = None
    # T32 / S1 (additive, defaulted): how fresh the series is. Timestamps are
    # ISO-8601 UTC with a trailing `Z`. `stale` is judged on the last bar's
    # age (1w: on its daily bar), not on the adapter status, so an aged cache
    # served while the source is down still says so. An unavailable chart
    # carries nulls and `stale=False`.
    last_bar_ts: str | None = None
    fetched_at: str | None = None
    is_partial: bool | None = None
    server_time: str | None = None
    stale: bool = False


class GainChip(BaseModel):
    """T34 / S2: one current-candle gain chip, open to latest price of the
    timeframe's newest bar (1w: the newest Monday-anchored week). `pct` is
    None with a `reason` when there is nothing honest to show, never 0; a
    flat candle is a real 0.0. `open_ts` is the bar's open, ISO-8601 UTC with
    a trailing `Z`. `stale` uses the chart's rule (1w: judged on its daily
    bar).
    """

    pct: float | None = None
    open_ts: str | None = None
    is_partial: bool = False
    stale: bool = False
    reason: UnavailableReason | None = None


class CoinPanel(BaseModel):
    symbol: str
    chart: ChartSeries
    # Kept for existing consumers; filled from `gain_by_timeframe[tf].pct`.
    percent_change_by_timeframe: dict[Timeframe, float | None]
    # T34 / S2 (additive): the current-candle chips themselves.
    gain_by_timeframe: dict[Timeframe, GainChip] = {}


class ScreenerBoardResponse(BaseModel):
    timeframe: Timeframe
    coins: list[CoinPanel]
    # T32 / S1 (additive, defaulted): server clock and its measured skew
    # against the exchange (seconds, host minus exchange; None = unknown).
    server_time: str | None = None
    clock_skew_seconds: float | None = None
    clock_skew_warning: bool = False


class ChartView(BaseModel):
    """T36 / S4: the drill-down's chart at its own interval (default 4h)."""

    symbol: str
    timeframe: Timeframe
    chart: ChartSeries


class RelativePerformanceSeries(BaseModel):
    symbol: str
    available: bool
    points: list[ChartBar]  # `close` here holds % change from the window's start
    # RFC-005: build_relative_performance sets available=False at three
    # separate call sites for three different reasons and previously said
    # which at none of them.
    reason: UnavailableReason | None = None


class RelativePerformanceResponse(BaseModel):
    timeframe: RelativePerformanceTimeframe
    series: list[RelativePerformanceSeries]
