"""Shared pydantic contract between api/analytics, api/routers and web/.

Public Contracts (PLAN.md): these field shapes are authoritative — RFC-002/
RFC-003/RFC-004 code against them, not invent fields ad hoc later.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Timeframe = Literal["15m", "1h", "4h", "1d", "1w"]
TIMEFRAMES: tuple[Timeframe, ...] = ("15m", "1h", "4h", "1d", "1w")

# RFC-005: why a ChartSeries has no data. Before this existed, `available:
# False` was documented as meaning "insufficient history" and was in fact
# produced by three unrelated causes — a misconfigured symbol, a dead data
# source, and genuinely short history — so a config bug reported itself to
# the operator as a history problem.
UnavailableReason = Literal["insufficient-history", "bad-symbol", "source-unavailable"]

# T40 / S5a (C6): why an RSI reading has no value. The chart's reasons, plus
# `flat-price` for a frame long enough but with no price change at all.
RsiReason = Literal["insufficient-history", "bad-symbol", "source-unavailable", "flat-price"]


class RsiReading(BaseModel):
    """RSI(14, Wilder) on the displayed timeframe's own frame, forming candle
    included. `value` is None with a `reason` when there is nothing honest to
    show, never 0. `as_of` is the last bar, ISO-8601 UTC with a trailing `Z`.
    """

    value: float | None = None
    length: int = 14
    as_of: str | None = None
    reason: RsiReason | None = None


class RsiPoint(BaseModel):
    timestamp: str
    value: float


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
    # T40 / S5a (additive, defaulted): the RSI series, filled only by the
    # drill-down chart view; board charts keep `[]`. Timestamps end in `Z`.
    rsi: list[RsiPoint] = []


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
    # T40 / S5a (additive): RSI of the displayed timeframe.
    rsi: RsiReading = RsiReading()


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


class SpaghettiLine(BaseModel):
    """T37 / S6: one coin's line on the spaghetti chart. `points[].close`
    holds the percent change from the window's first close, so an available
    line starts at 0. An unavailable coin has no points and a `reason`, never
    a flat line. Timestamps are ISO-8601 UTC with a trailing `Z`.
    """

    symbol: str
    available: bool
    reason: UnavailableReason | None = None
    points: list[ChartBar]
    window_start: str | None = None
    window_end: str | None = None
    bars: int = 0
    last_bar_ts: str | None = None
    stale: bool = False


class SpaghettiResponse(BaseModel):
    """T37 / S6: every watchlist coin over the last `window_cap_bars` bars of
    its own frame at `timeframe`. BTC and HYPE ride in `references`, never in
    `series`, whether or not they are on the watchlist.
    """

    timeframe: Timeframe
    window_cap_bars: int
    server_time: str | None = None
    series: list[SpaghettiLine]
    references: list[SpaghettiLine]
