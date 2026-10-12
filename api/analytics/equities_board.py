"""Equities board, drill-down chart and spaghetti assembly (S9A).

Cache-only (D-1): every read goes through `lse_adapter.read_cached_equity`,
which never calls the network or reads the key. Fills come from the
add-triggered refresh, `POST /api/equities/refresh` and the market-hours
tick (`equities_refresh`).

The responses reuse the crypto models (`ScreenerBoardResponse`, `CoinPanel`,
`ChartSeries`, `ChartView`, `SpaghettiResponse`) with no model change:

* Only 1d and 1w exist. Gain chips keep the crypto meaning (newest candle,
  open to latest, D-3): 1d from the newest daily bar, 1w from the newest
  week of daily bars, opened by the week's first session, so a Monday
  holiday does not blank it.
* `stale` and `is_partial` come from `equities_calendar` (D-4), judged on
  the newest daily bar for both timeframes, so weekends and holidays are
  never overdue.
* Failure reasons map onto the closed `UnavailableReason`: bad_symbol ->
  bad-symbol; no file, no key or any other failure -> source-unavailable;
  under 60 bars -> insufficient-history.
* No clock skew against an exchange exists here: skew fields are null/False.
* Spaghetti has no reference lines (`references=[]`); order is store order.
"""
from __future__ import annotations

import math

import pandas as pd

from api.analytics.indicators import rsi as rsi_mod
from api.analytics.indicators import sma as sma_mod
from api.data import equities_calendar, equities_store, lse_adapter
from api.data.freshness import as_utc, iso_z
from api.models.screener import (
    ChartBar,
    ChartSeries,
    ChartView,
    CoinPanel,
    GainChip,
    RsiPoint,
    RsiReading,
    ScreenerBoardResponse,
    SpaghettiLine,
    SpaghettiResponse,
)

EQUITY_TIMEFRAMES = ("1d", "1w")
SPAGHETTI_WINDOW_BARS = {"1d": 200, "1w": 28}


def _now(now=None) -> pd.Timestamp:
    # Looked up at call time so tests inject the clock.
    return as_utc(lse_adapter._now() if now is None else now)


def _failure_reason(status: str | None) -> str:
    return "bad-symbol" if status == "bad_symbol" else "source-unavailable"


def _reason(df: pd.DataFrame, status: str | None) -> str:
    """Why a frame cannot be drawn: an empty frame carries the read's failure;
    a frame with bars but under `SMA_LENGTH` is short history."""
    if df is None or df.empty:
        return _failure_reason(status)
    return "insufficient-history"


def _read(ticker: str, timeframe: str, now: pd.Timestamp):
    result, fetched_at = lse_adapter.read_cached_equity(ticker, timeframe, now=now)
    df = result.df
    if df is not None and not df.empty:
        df = df.sort_values("timestamp").reset_index(drop=True)
    return result, df, fetched_at


def _last_ts(df: pd.DataFrame | None):
    if df is None or df.empty:
        return None
    return df["timestamp"].iloc[-1]


def _bars(timestamps, values) -> list[ChartBar]:
    return [
        ChartBar(timestamp=iso_z(ts), close=float(v))
        for ts, v in zip(timestamps, values)
        if v is not None and not pd.isna(v)
    ]


def _finite(value) -> bool:
    return value is not None and not pd.isna(value) and math.isfinite(float(value))


def _available(df: pd.DataFrame | None) -> bool:
    return df is not None and len(df) >= sma_mod.SMA_LENGTH


def _chart_series(df, status, timeframe, fetched_at, daily_df, now) -> ChartSeries:
    if not _available(df):
        return ChartSeries(price=[], sma=[], available=False, reason=_reason(df, status))
    daily_last = _last_ts(daily_df)
    return ChartSeries(
        price=_bars(df["timestamp"], df["close"]),
        sma=_bars(df["timestamp"], sma_mod.compute_sma(df)),
        available=True,
        last_bar_ts=iso_z(_last_ts(df)),
        fetched_at=iso_z(fetched_at),
        is_partial=equities_calendar.bar_is_partial(daily_last, now, timeframe),
        server_time=iso_z(now),
        stale=equities_calendar.bar_is_stale(daily_last, now),
    )


def _rsi_reading(df, status) -> RsiReading:
    if not _available(df):
        return RsiReading(reason=_reason(df, status))
    as_of = iso_z(_last_ts(df))
    series = rsi_mod.compute_rsi(df)
    last = None if series is None or series.empty else series.iloc[-1]
    if not _finite(last):
        return RsiReading(as_of=as_of, reason="flat-price")
    return RsiReading(value=float(last), as_of=as_of)


def _rsi_series(df) -> list[RsiPoint]:
    series = rsi_mod.compute_rsi(df)
    if series is None:
        return []
    return [
        RsiPoint(timestamp=iso_z(ts), value=float(v))
        for ts, v in zip(df["timestamp"], series)
        if _finite(v)
    ]


def _na(reason: str) -> GainChip:
    return GainChip(pct=None, open_ts=None, is_partial=False, stale=False, reason=reason)


def _chip(open_, close, open_ts, timeframe, daily_last, now) -> GainChip:
    if pd.isna(open_) or pd.isna(close) or open_ <= 0:
        return _na("insufficient-history")
    pct = float((close - open_) / open_ * 100.0)
    if not math.isfinite(pct):
        return _na("insufficient-history")
    return GainChip(
        pct=pct,
        open_ts=iso_z(open_ts),
        is_partial=bool(equities_calendar.bar_is_partial(daily_last, now, timeframe)),
        stale=equities_calendar.bar_is_stale(daily_last, now),
        reason=None,
    )


def gain_chips(daily_df: pd.DataFrame | None, status: str | None, now) -> dict[str, GainChip]:
    """The 1d and 1w chips from the daily bars. 1w opens at the first session
    of the newest daily bar's Monday-anchored week and is labelled with that
    Monday (as the derived weekly bars are)."""
    if daily_df is None or daily_df.empty:
        reason = _failure_reason(status)
        return {"1d": _na(reason), "1w": _na(reason)}
    newest = daily_df.iloc[-1]
    daily_last = newest["timestamp"]
    chip_1d = _chip(newest["open"], newest["close"], daily_last, "1d", daily_last, now)

    monday = as_utc(daily_last).normalize() - pd.Timedelta(days=as_utc(daily_last).weekday())
    days = daily_df["timestamp"].map(lambda ts: as_utc(ts).normalize())
    week = daily_df[days >= monday]
    chip_1w = _chip(week["open"].iloc[0], week["close"].iloc[-1], monday, "1w", daily_last, now)
    return {"1d": chip_1d, "1w": chip_1w}


def build_panel(ticker: str, timeframe: str, now) -> CoinPanel:
    now = _now(now)
    daily_result, daily_df, daily_fetched = _read(ticker, "1d", now)
    if timeframe == "1d":
        result, df, fetched_at = daily_result, daily_df, daily_fetched
    else:
        result, df, fetched_at = _read(ticker, timeframe, now)
    chips = gain_chips(daily_df, daily_result.status, now)
    return CoinPanel(
        symbol=result.symbol or ticker,
        chart=_chart_series(df, result.status, timeframe, fetched_at, daily_df, now),
        percent_change_by_timeframe={tf: chip.pct for tf, chip in chips.items()},
        gain_by_timeframe=chips,
        rsi=_rsi_reading(df, result.status),
    )


def build_board(timeframe: str = "1d", now=None) -> ScreenerBoardResponse:
    now = _now(now)
    panels = [build_panel(t, timeframe, now) for t in equities_store.load_tickers()]
    return ScreenerBoardResponse(
        timeframe=timeframe,
        coins=panels,
        server_time=iso_z(now),
        clock_skew_seconds=None,
        clock_skew_warning=False,
    )


def build_chart_view(ticker: str, timeframe: str = "1d", now=None) -> ChartView:
    now = _now(now)
    result, df, fetched_at = _read(ticker, timeframe, now)
    daily_df = df if timeframe == "1d" else _read(ticker, "1d", now)[1]
    chart = _chart_series(df, result.status, timeframe, fetched_at, daily_df, now)
    if chart.available:
        chart.rsi = _rsi_series(df)
    return ChartView(symbol=result.symbol or ticker, timeframe=timeframe, chart=chart)


def _spaghetti_line(ticker: str, timeframe: str, now) -> SpaghettiLine:
    result, df, _fetched = _read(ticker, timeframe, now)
    symbol = result.symbol or ticker
    if not _available(df):
        return SpaghettiLine(symbol=symbol, available=False, reason=_reason(df, result.status), points=[])
    window = df.tail(SPAGHETTI_WINDOW_BARS[timeframe])
    start = window["close"].iloc[0]
    if pd.isna(start) or start == 0:
        return SpaghettiLine(symbol=symbol, available=False, reason="insufficient-history", points=[])
    points = _bars(window["timestamp"], (window["close"] - start) / start * 100.0)
    daily_df = df if timeframe == "1d" else _read(ticker, "1d", now)[1]
    return SpaghettiLine(
        symbol=symbol,
        available=True,
        points=points,
        window_start=iso_z(window["timestamp"].iloc[0]),
        window_end=iso_z(window["timestamp"].iloc[-1]),
        bars=len(points),
        last_bar_ts=iso_z(_last_ts(df)),
        stale=equities_calendar.bar_is_stale(_last_ts(daily_df), now),
    )


def build_spaghetti(timeframe: str = "1d", now=None) -> SpaghettiResponse:
    now = _now(now)
    return SpaghettiResponse(
        timeframe=timeframe,
        window_cap_bars=SPAGHETTI_WINDOW_BARS[timeframe],
        server_time=iso_z(now),
        series=[_spaghetti_line(t, timeframe, now) for t in equities_store.load_tickers()],
        references=[],
    )
