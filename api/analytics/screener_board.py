"""Screener board assembly — orchestrates adapters + analytics into the API
response models (items 15, 20, 21, 29a, 29h, 29j, 29k/29l).

Deliberately framework-independent (no FastAPI import) so it can be
exercised directly by tests without an HTTP client — `routers/screener.py`
is a thin FastAPI wrapper around these functions. This split isn't spelled
out as its own file in PLAN.md's Touchpoints list, but follows directly from
the Architecture Clarification's own rule ("routers/ exposes HTTP... no
router calls a provider directly"): the actual assembly logic lives here so
`routers/screener.py` has nothing left to do but bind HTTP verbs to it. It
also happens to be what makes AC-4/5/6/7/16/17/18/19/20/14/15 testable at
all in this sandbox, where FastAPI itself could not be installed (see
EXECUTE report Deviations) — but the split is motivated by the plan's own
architecture rule, not invented solely to route around that.
"""
from __future__ import annotations

import pandas as pd

from api.analytics.confidence import badge
from api.analytics.indicators import gain as gain_mod
from api.analytics.indicators import momentum as momentum_mod
from api.analytics.indicators import trend as trend_mod
from api.analytics.narrative import mapping as narrative_mapping
from api.analytics.narrative import trigger as narrative_trigger
from api.analytics.regime import leg_boundary
from api.analytics.regime.benchmark import select_active_benchmark
from api.data import ccxt_adapter, freshness
from api.data import watchlist as watchlist_store
from api.models.narrative import NarrativeCategory
from api.models.screener import (
    TIMEFRAMES,
    ChartBar,
    ChartSeries,
    CoinPanel,
    MomentumState,
    RelativePerformanceResponse,
    RelativePerformanceSeries,
    RelativePerformanceTimeframe,
    ScalpMomentumState,
    ScalpView,
    ScreenerBoardResponse,
    Timeframe,
    TrendState,
)

DEFAULT_BOARD_TIMEFRAME: Timeframe = "1d"
DEFAULT_SCALP_TIMEFRAME: Timeframe = "4h"

RELATIVE_PERFORMANCE_WINDOW_DAYS: dict[RelativePerformanceTimeframe, int] = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "ytd": 365,
}


def _series_to_chart_bars(timestamps: pd.Series, values: pd.Series) -> list[ChartBar]:
    bars: list[ChartBar] = []
    for ts, val in zip(timestamps, values):
        if pd.isna(val):
            continue
        ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        bars.append(ChartBar(timestamp=ts_str, close=float(val)))
    return bars


# RFC-005: the adapter's `status` used to be computed and then thrown away
# here — this module derived `available` purely from `len(df)`, so the one
# honest signal the adapter produced never reached the response. A dead data
# source and a misconfigured symbol both arrived at the UI as "insufficient
# history". This maps status onto the response's own reason vocabulary.
_STATUS_TO_REASON = {
    "bad_symbol": "bad-symbol",
    "unavailable": "source-unavailable",
    "stale": "source-unavailable",
}


def _reason_for(status: str | None) -> str:
    """Why a series has no data. Adapter status wins when it reports a real
    failure; otherwise the cause really is short history.
    """
    return _STATUS_TO_REASON.get(status or "", "insufficient-history")


def _last_bar(df: pd.DataFrame | None):
    if df is None or df.empty:
        return None
    return df["timestamp"].max()


def _chart_series(
    df: pd.DataFrame,
    available: bool,
    status: str | None = None,
    *,
    timeframe: Timeframe | None = None,
    fetched_at=None,
    stale_ref_df: pd.DataFrame | None = None,
    now: pd.Timestamp | None = None,
) -> ChartSeries:
    """`stale_ref_df` is the series whose last bar decides `stale` (the daily
    bars for `1w`, B5); it defaults to `df` itself. `stale` is computed from
    that bar's age, never from `status` (A1)."""
    if not available or df is None or df.empty:
        return ChartSeries(
            price=[], sma=[], available=False, reason=_reason_for(status)
        )
    sma = trend_mod.compute_sma(df)
    freshness_fields = {}
    if timeframe is not None:
        now = ccxt_adapter._now() if now is None else now
        ref_now = ccxt_adapter.reference_now(now)
        last = _last_bar(df)
        stale_ref = _last_bar(stale_ref_df) if stale_ref_df is not None else last
        freshness_fields = {
            "last_bar_ts": freshness.iso_z(last),
            "fetched_at": freshness.iso_z(fetched_at),
            "is_partial": freshness.is_partial(last, timeframe, ref_now),
            "server_time": freshness.iso_z(now),
            "stale": freshness.is_stale(stale_ref, timeframe, ref_now),
        }
    return ChartSeries(
        price=_series_to_chart_bars(df["timestamp"], df["close"]),
        sma=_series_to_chart_bars(df["timestamp"], sma),
        available=True,
        **freshness_fields,
    )


def _coin_narrative_state(symbol: str, categories_by_id: dict[str, NarrativeCategory]) -> badge.NarrativeState:
    """RFC-004 item 64a: resolves one coin's `narrative_state` via
    `mapping.map_coin_to_category` + a lookup against this board-build's
    already-fetched category list — never re-fetches per coin. See
    `badge.derive_narrative_state`'s docstring for why `has_mapping` is
    threaded through explicitly rather than collapsing "no mapping" and
    "mapping exists but wasn't fetched" into the same `None` case.
    """
    category_id = narrative_mapping.map_coin_to_category(symbol)
    category = categories_by_id.get(category_id) if category_id else None
    return badge.derive_narrative_state(category, has_mapping=category_id is not None)


def build_coin_panel(
    symbol: str,
    timeframe: Timeframe = DEFAULT_BOARD_TIMEFRAME,
    leg_context: badge.LegContext = "unavailable",
    categories_by_id: dict[str, NarrativeCategory] | None = None,
    now: pd.Timestamp | None = None,
) -> CoinPanel:
    """Assembles one coin's panel. `momentum`/`trend`'s PASS/FAIL fields are
    always computed from real daily+weekly bars regardless of `timeframe`
    (AC-16) — `timeframe` only selects which series populate `chart`.

    `leg_context`/`categories_by_id` (RFC-004, items 62/64/64a): the real
    confidence badge. `leg_context` is derived once per board build (it's a
    shared macro-level read, not per-coin) and passed in; `categories_by_id`
    is this build's one shared narrative-category fetch, keyed by
    `category_id`, so a board of N coins only ever fetches narrative data
    once, not N times. Both default to values that resolve to
    `insufficient-data` so `build_coin_panel` stays callable on its own
    (e.g. future direct callers, or tests) without silently fabricating a
    stronger badge than the caller actually has data for.
    """
    daily = ccxt_adapter.fetch_ohlcv(symbol, "1d")
    weekly = ccxt_adapter.fetch_ohlcv(symbol, "1w")
    momentum_result = momentum_mod.compute_dual_timeframe_momentum(daily.df, weekly.df)
    trend_result = trend_mod.compute_trend(daily.df)  # panel's headline trend stays daily-based

    dfs_by_tf: dict[Timeframe, pd.DataFrame] = {"1d": daily.df, "1w": weekly.df}
    statuses_by_tf: dict[Timeframe, str] = {"1d": daily.status, "1w": weekly.status}
    fetched_by_tf = {"1d": daily.fetched_at, "1w": weekly.fetched_at}
    for tf in TIMEFRAMES:
        if tf not in dfs_by_tf:
            result = ccxt_adapter.fetch_ohlcv(symbol, tf)
            dfs_by_tf[tf] = result.df
            statuses_by_tf[tf] = result.status
            fetched_by_tf[tf] = result.fetched_at
    now = ccxt_adapter._now() if now is None else now
    # T34 / S2: current-candle chips (open to latest), judged against the
    # same skew-corrected reference time as the chart's freshness fields.
    chips_by_tf = gain_mod.compute_gain_chips(dfs_by_tf, statuses_by_tf, ccxt_adapter.reference_now(now))

    display_df = dfs_by_tf[timeframe]
    display_available = len(display_df) >= trend_mod.SMA_LENGTH
    # RFC-005: carry the adapter's own verdict for the displayed timeframe.
    # `1d`/`1w` have their results to hand; other timeframes are re-read from
    # the per-timeframe results collected above.
    display_status = statuses_by_tf.get(timeframe)

    momentum_state = MomentumState(**momentum_result.__dict__)
    trend_state = TrendState(**trend_result.__dict__)
    narrative_state = _coin_narrative_state(symbol, categories_by_id or {})
    confidence = badge.compute_badge(momentum_state, trend_state, leg_context, narrative_state)

    return CoinPanel(
        symbol=symbol,
        momentum=momentum_state,
        trend=trend_state,
        confidence=confidence,
        # RFC-004 (item 64a, Risk Prediction #4): exposed individually
        # alongside `confidence` so the frontend never has to reverse-
        # engineer a per-signal reading from the aggregate badge.
        leg_context=leg_context,
        narrative_state=narrative_state,
        chart=_chart_series(
            display_df, display_available, display_status,
            timeframe=timeframe,
            fetched_at=fetched_by_tf.get(timeframe),
            # 1w staleness is judged on its daily bar (B5).
            stale_ref_df=daily.df if timeframe == "1w" else None,
            now=now,
        ),
        percent_change_by_timeframe={tf: chip.pct for tf, chip in chips_by_tf.items()},
        gain_by_timeframe=chips_by_tf,
    )


def build_screener_board(timeframe: Timeframe = DEFAULT_BOARD_TIMEFRAME) -> ScreenerBoardResponse:
    coins = watchlist_store.read_watchlist()
    # RFC-002 item 44: real CurrentLegState replaces RFC-001's RegimeState
    # stub wholesale — select_active_benchmark's own signature/output type
    # (BenchmarkSelection) is unchanged by the swap.
    leg_state = leg_boundary.compute_current_leg_state()
    benchmark = select_active_benchmark(leg_state)

    # RFC-004 (items 62/64/64a): one shared leg_context + one shared
    # narrative-category fetch for the whole board, not re-derived/re-fetched
    # per coin.
    leg_context = badge.derive_leg_context(leg_state)
    categories = narrative_trigger.assemble_narrative_categories()
    categories_by_id = {c.id: c for c in categories}

    now = ccxt_adapter._now()
    panels = [
        build_coin_panel(symbol, timeframe, leg_context=leg_context, categories_by_id=categories_by_id, now=now)
        for symbol in coins
    ]
    skew = ccxt_adapter.last_clock_skew()
    return ScreenerBoardResponse(
        timeframe=timeframe,
        active_benchmark=benchmark,
        coins=panels,
        server_time=freshness.iso_z(now),
        clock_skew_seconds=skew,
        clock_skew_warning=ccxt_adapter.clock_skew_warning(skew),
    )


def build_scalp_view(symbol: str, timeframe: Timeframe = DEFAULT_SCALP_TIMEFRAME) -> ScalpView:
    """The chart's own interval is switchable (Amendment 2, AC-18); the
    scalp RSI reading itself always comes from real 4h bars and stays
    labeled `4h`, independent of `timeframe`.
    """
    display = ccxt_adapter.fetch_ohlcv(symbol, timeframe)
    daily_ref = ccxt_adapter.fetch_ohlcv(symbol, "1d").df if timeframe == "1w" else None
    scalp_source = display if timeframe == "4h" else ccxt_adapter.fetch_ohlcv(symbol, "4h")
    scalp_result = momentum_mod.compute_scalp_momentum(scalp_source.df, timeframe="4h")
    display_available = len(display.df) >= trend_mod.SMA_LENGTH

    return ScalpView(
        symbol=symbol,
        timeframe=timeframe,
        chart=_chart_series(
            display.df, display_available, display.status,
            timeframe=timeframe, fetched_at=display.fetched_at, stale_ref_df=daily_ref,
        ),
        scalp_momentum=ScalpMomentumState(**scalp_result.__dict__),
    )


def build_relative_performance(
    timeframe: RelativePerformanceTimeframe = "30d",
) -> RelativePerformanceResponse:
    """AC-14/15: every watchlist coin normalized to % change from the
    selected window's own start bar. A coin with too little history for
    that window returns `available=False` individually (AC-12's rule
    applied here too) — never omitted or zero-filled, and other coins on
    the same response are unaffected.
    """
    coins = watchlist_store.read_watchlist()
    window_days = RELATIVE_PERFORMANCE_WINDOW_DAYS[timeframe]
    series_list: list[RelativePerformanceSeries] = []

    for symbol in coins:
        result = ccxt_adapter.fetch_ohlcv(symbol, "1d")
        df = result.df
        if df.empty:
            # RFC-005: an empty frame here means the fetch failed, not that
            # the coin is young. Say which.
            series_list.append(
                RelativePerformanceSeries(
                    symbol=symbol, available=False, points=[],
                    reason=_reason_for(result.status),
                )
            )
            continue

        cutoff = df["timestamp"].max() - pd.Timedelta(days=window_days)

        # A coin whose own earliest cached bar is AFTER the window's start
        # doesn't actually cover the requested window — flag unavailable
        # rather than silently normalizing a truncated line (AC-15).
        if df["timestamp"].min() > cutoff:
            series_list.append(
                RelativePerformanceSeries(
                    symbol=symbol, available=False, points=[],
                    reason="insufficient-history",
                )
            )
            continue

        windowed = df[df["timestamp"] >= cutoff]
        start_close = windowed["close"].iloc[0] if len(windowed) else None

        if len(windowed) < 2 or start_close is None or pd.isna(start_close) or start_close == 0:
            series_list.append(
                RelativePerformanceSeries(
                    symbol=symbol, available=False, points=[],
                    reason="insufficient-history",
                )
            )
            continue

        pct = (windowed["close"] - start_close) / start_close * 100.0
        series_list.append(
            RelativePerformanceSeries(
                symbol=symbol,
                available=True,
                points=_series_to_chart_bars(windowed["timestamp"], pct),
            )
        )

    return RelativePerformanceResponse(timeframe=timeframe, series=series_list)
