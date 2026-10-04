"""Shared pydantic contract between api/analytics, api/routers and web/.

Public Contracts (PLAN.md): these field shapes are authoritative — RFC-002/
RFC-003/RFC-004 code against them, not invent fields ad hoc later.

`RegimeState` is RFC-001's throwaway STUB input type to
`select_active_benchmark` (`placeholder: bool = True` only) — explicitly NOT
a Public Contract; RFC-002 (item 44) replaces it wholesale with the real
`CurrentLegState`. `BenchmarkSelection` is the STABLE output type every
RFC-002+ consumer reads; its own shape never changes across that swap.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Timeframe = Literal["15m", "1h", "4h", "1d", "1w"]
TIMEFRAMES: tuple[Timeframe, ...] = ("15m", "1h", "4h", "1d", "1w")

RelativePerformanceTimeframe = Literal["7d", "30d", "90d", "ytd"]

MomentumStateLiteral = Literal["PASS", "FAIL", "insufficient"]

# RFC-005: why a ChartSeries has no data. Before this existed, `available:
# False` was documented as meaning "insufficient history" and was in fact
# produced by three unrelated causes — a misconfigured symbol, a dead data
# source, and genuinely short history — so a config bug reported itself to
# the operator as a history problem.
UnavailableReason = Literal["insufficient-history", "bad-symbol", "source-unavailable"]
TrendDirectionLiteral = Literal["up", "down", "insufficient"]

# ADR-4's closed confidence enum. RFC-001 only ever produces the
# `insufficient-data` placeholder (real badge wiring is RFC-004, item 64) —
# the type stays the full closed union so no later RFC has to widen it.
ConfidenceState = Literal["aligned", "mixed", "conflicting", "insufficient-data"]

# ADR-4's two derived-input closed enums (RFC-004, item 64a) — exposed on
# `CoinPanel` (below) alongside the aggregate `confidence` so
# `SignalDetailPanel` can render each signal from its own typed state
# rather than re-deriving it from the badge enum (Risk Prediction #4: an
# `insufficient-data` badge must not imply every individual signal is
# insufficient, so the detail panel needs the real per-signal readings, not
# a guess reverse-engineered from the aggregate).
LegContextLiteral = Literal["confirmed", "candidate-pending", "unavailable"]
NarrativeStateLiteral = Literal[
    "in-focus", "confirmed-emerging", "unconfirmed-emerging", "rotated-out", "unmapped", "unavailable"
]


class MomentumState(BaseModel):
    state: MomentumStateLiteral
    daily_value: float | None = None
    weekly_value: float | None = None


class TrendState(BaseModel):
    direction: TrendDirectionLiteral
    sma_value: float | None = None


class BenchmarkSelection(BaseModel):
    """STABLE output type (Public Contracts) — never replaced, only ever
    produced by RFC-001's stub logic today and RFC-002's real logic later.
    """

    active: Literal["BTC", "HYPE"]
    reason: str


class RegimeState(BaseModel):
    """RFC-001 STUB INPUT type to `select_active_benchmark` — NOT a Public
    Contract. Replaced wholesale by RFC-002's real `CurrentLegState` input
    (item 44); never extended in place.
    """

    placeholder: bool = True


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
    momentum: MomentumState
    trend: TrendState
    # RFC-004 wires the real badge here; RFC-001 always returns this literal
    # placeholder (item 15).
    confidence: ConfidenceState = "insufficient-data"
    # RFC-004 (item 64a, Risk Prediction #4): the same two derived inputs
    # `compute_badge` used to reach `confidence` above, exposed individually
    # so the frontend's `SignalDetailPanel` never has to reverse-engineer a
    # per-signal reading from the aggregate badge value. Defaults match
    # `confidence`'s own pre-RFC-004 placeholder shape.
    leg_context: LegContextLiteral = "unavailable"
    narrative_state: NarrativeStateLiteral = "unavailable"
    chart: ChartSeries
    # Kept for existing consumers; filled from `gain_by_timeframe[tf].pct`.
    percent_change_by_timeframe: dict[Timeframe, float | None]
    # T34 / S2 (additive): the current-candle chips themselves.
    gain_by_timeframe: dict[Timeframe, GainChip] = {}


class ScreenerBoardResponse(BaseModel):
    timeframe: Timeframe
    active_benchmark: BenchmarkSelection
    coins: list[CoinPanel]
    # T32 / S1 (additive, defaulted): server clock and its measured skew
    # against the exchange (seconds, host minus exchange; None = unknown).
    server_time: str | None = None
    clock_skew_seconds: float | None = None
    clock_skew_warning: bool = False


class ScalpMomentumState(BaseModel):
    state: MomentumStateLiteral
    value: float | None = None
    timeframe: Timeframe = "4h"


class ScalpView(BaseModel):
    symbol: str
    timeframe: Timeframe  # the chart's own interval (Amendment 2, default 4h)
    chart: ChartSeries
    # Always independently labeled with its own timeframe (default 4h) so
    # it's never visually mistaken for the chart's current zoom (AC-18).
    scalp_momentum: ScalpMomentumState


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
