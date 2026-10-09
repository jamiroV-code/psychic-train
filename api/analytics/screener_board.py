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

from api.analytics.indicators import gain as gain_mod
from api.analytics.indicators import sma as sma_mod
from api.data import ccxt_adapter, freshness
from api.data import watchlist as watchlist_store
from api.models.screener import (
    TIMEFRAMES,
    ChartBar,
    ChartSeries,
    ChartView,
    CoinPanel,
    ScreenerBoardResponse,
    SpaghettiLine,
    SpaghettiResponse,
    Timeframe,
)

DEFAULT_BOARD_TIMEFRAME: Timeframe = "1d"
DEFAULT_CHART_TIMEFRAME: Timeframe = "4h"

# T37 / S6 (C5): the spaghetti window is the last N bars of each coin's own
# frame; 1w is capped at 28 weeks.
SPAGHETTI_WINDOW_BARS: dict[Timeframe, int] = {
    "15m": 200,
    "1h": 200,
    "4h": 200,
    "1d": 200,
    "1w": 28,
}
# Always drawn as references, never as coin lines.
SPAGHETTI_REFERENCES: tuple[str, ...] = ("BTC", "HYPE")


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
    sma = sma_mod.compute_sma(df)
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


def build_coin_panel(
    symbol: str,
    timeframe: Timeframe = DEFAULT_BOARD_TIMEFRAME,
    now: pd.Timestamp | None = None,
) -> CoinPanel:
    """Assembles one coin's panel: `timeframe` selects which series populate
    `chart`; the gain chips cover every timeframe.
    """
    dfs_by_tf: dict[Timeframe, pd.DataFrame] = {}
    statuses_by_tf: dict[Timeframe, str] = {}
    fetched_by_tf = {}
    for tf in ("1d", "1w", *(t for t in TIMEFRAMES if t not in ("1d", "1w"))):
        result = ccxt_adapter.fetch_ohlcv(symbol, tf)
        dfs_by_tf[tf] = result.df
        statuses_by_tf[tf] = result.status
        fetched_by_tf[tf] = result.fetched_at
    now = ccxt_adapter._now() if now is None else now
    # T34 / S2: current-candle chips (open to latest), judged against the
    # same skew-corrected reference time as the chart's freshness fields.
    chips_by_tf = gain_mod.compute_gain_chips(dfs_by_tf, statuses_by_tf, ccxt_adapter.reference_now(now))

    display_df = dfs_by_tf[timeframe]
    display_available = len(display_df) >= sma_mod.SMA_LENGTH
    # RFC-005: carry the adapter's own verdict for the displayed timeframe.
    display_status = statuses_by_tf.get(timeframe)

    return CoinPanel(
        symbol=symbol,
        chart=_chart_series(
            display_df, display_available, display_status,
            timeframe=timeframe,
            fetched_at=fetched_by_tf.get(timeframe),
            # 1w staleness is judged on its daily bar (B5).
            stale_ref_df=dfs_by_tf["1d"] if timeframe == "1w" else None,
            now=now,
        ),
        percent_change_by_timeframe={tf: chip.pct for tf, chip in chips_by_tf.items()},
        gain_by_timeframe=chips_by_tf,
    )


def build_screener_board(timeframe: Timeframe = DEFAULT_BOARD_TIMEFRAME) -> ScreenerBoardResponse:
    coins = watchlist_store.read_watchlist()
    now = ccxt_adapter._now()
    panels = [build_coin_panel(symbol, timeframe, now=now) for symbol in coins]
    skew = ccxt_adapter.last_clock_skew()
    return ScreenerBoardResponse(
        timeframe=timeframe,
        coins=panels,
        server_time=freshness.iso_z(now),
        clock_skew_seconds=skew,
        clock_skew_warning=ccxt_adapter.clock_skew_warning(skew),
    )


def build_chart_view(symbol: str, timeframe: Timeframe = DEFAULT_CHART_TIMEFRAME) -> ChartView:
    """The drill-down chart at its own switchable interval (Amendment 2,
    AC-18); 1w staleness is judged on its daily bar (B5).
    """
    display = ccxt_adapter.fetch_ohlcv(symbol, timeframe)
    daily_ref = ccxt_adapter.fetch_ohlcv(symbol, "1d").df if timeframe == "1w" else None
    display_available = len(display.df) >= sma_mod.SMA_LENGTH

    return ChartView(
        symbol=symbol,
        timeframe=timeframe,
        chart=_chart_series(
            display.df, display_available, display.status,
            timeframe=timeframe, fetched_at=display.fetched_at, stale_ref_df=daily_ref,
        ),
    )


def _spaghetti_line(symbol: str, timeframe: Timeframe, ref_now: pd.Timestamp) -> SpaghettiLine:
    """One coin over the last `SPAGHETTI_WINDOW_BARS[timeframe]` bars of its
    own frame, as percent change from the window's first close. A coin with
    fewer bars than the board chart needs (`sma.SMA_LENGTH`), or whose fetch
    failed, is `available=False` with a reason and no points.
    """
    result = ccxt_adapter.fetch_ohlcv(symbol, timeframe)
    df = result.df
    if df is None or df.empty or len(df) < sma_mod.SMA_LENGTH:
        return SpaghettiLine(symbol=symbol, available=False, reason=_reason_for(result.status), points=[])

    df = df.sort_values("timestamp")
    window = df.tail(SPAGHETTI_WINDOW_BARS[timeframe])
    start_close = window["close"].iloc[0]
    if pd.isna(start_close) or start_close == 0:
        return SpaghettiLine(symbol=symbol, available=False, reason="insufficient-history", points=[])

    pct = (window["close"] - start_close) / start_close * 100.0
    points = [
        ChartBar(timestamp=freshness.iso_z(ts), close=float(v))
        for ts, v in zip(window["timestamp"], pct)
        if not pd.isna(v)
    ]
    last = _last_bar(df)
    # 1w staleness is judged on its daily bar (B5), as on the board.
    stale_ref = _last_bar(ccxt_adapter.fetch_ohlcv(symbol, "1d").df) if timeframe == "1w" else last
    return SpaghettiLine(
        symbol=symbol,
        available=True,
        points=points,
        window_start=freshness.iso_z(window["timestamp"].iloc[0]),
        window_end=freshness.iso_z(window["timestamp"].iloc[-1]),
        bars=len(points),
        last_bar_ts=freshness.iso_z(last),
        stale=freshness.is_stale(stale_ref, timeframe, ref_now),
    )


def build_spaghetti(timeframe: Timeframe = DEFAULT_BOARD_TIMEFRAME) -> SpaghettiResponse:
    """T37 / S6 (C5): every watchlist coin as percent change from its own
    window start, so every available line starts at 0. BTC and HYPE are
    always references, never coin lines. No ranking: the order is the
    watchlist's.
    """
    now = ccxt_adapter._now()
    ref_now = ccxt_adapter.reference_now(now)
    references = {s.upper() for s in SPAGHETTI_REFERENCES}
    coins = [s for s in watchlist_store.read_watchlist() if s.upper() not in references]
    return SpaghettiResponse(
        timeframe=timeframe,
        window_cap_bars=SPAGHETTI_WINDOW_BARS[timeframe],
        server_time=freshness.iso_z(now),
        series=[_spaghetti_line(s, timeframe, ref_now) for s in coins],
        references=[_spaghetti_line(s, timeframe, ref_now) for s in SPAGHETTI_REFERENCES],
    )
