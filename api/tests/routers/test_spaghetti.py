"""T37 / S6 — the spaghetti chart (C5).

Every watchlist coin is drawn as percent change from the first close of its
own window (the last N bars of its own frame: 200, or 28 for 1w), so every
available line starts at 0. BTC and HYPE ride in `references`, never as coin
lines. A thin or failed coin is explicit no-data with a reason, never a flat
line at zero.
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import pytest

from api.analytics import screener_board
from api.data import ccxt_adapter, refresh_worker
from api.data import watchlist as watchlist_store
from api.data.ccxt_adapter import OhlcvResult
from api.models.screener import SpaghettiLine, SpaghettiResponse

NOW = pd.Timestamp("2026-10-03T14:10:00Z")
_FREQ = {"15m": "15min", "1h": "h", "4h": "4h", "1d": "D", "1w": "W-MON"}
_END = {
    "15m": "2026-10-03T14:00:00Z",
    "1h": "2026-10-03T14:00:00Z",
    "4h": "2026-10-03T12:00:00Z",
    "1d": "2026-10-03T00:00:00Z",
    "1w": "2026-09-28T00:00:00Z",
}
_ZFORM = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _df(tf: str, closes: list[float]) -> pd.DataFrame:
    idx = pd.date_range(end=pd.Timestamp(_END[tf]), periods=len(closes), freq=_FREQ[tf], tz="UTC")
    return pd.DataFrame({
        "timestamp": idx, "open": closes, "high": closes, "low": closes, "close": closes,
        "volume": 1.0, "source": "fixture",
    })


def _install(monkeypatch, frames: dict[str, list[float]], watchlist: list[str], status=None):
    """`frames` maps symbol -> closes (same closes on every timeframe);
    `status` maps symbol -> adapter status for an empty frame."""
    status = status or {}
    calls: list[tuple[str, str]] = []

    def fake_fetch(symbol, timeframe, since=None, limit=None, exchange=None):
        calls.append((symbol, timeframe))
        closes = frames.get(symbol)
        df = _df(timeframe, closes) if closes else pd.DataFrame()
        st = status.get(symbol, "ok" if closes else "unavailable")
        return OhlcvResult(symbol, timeframe, df, len(df) < 60, st)

    monkeypatch.setattr(screener_board.ccxt_adapter, "fetch_ohlcv", fake_fetch)
    monkeypatch.setattr(ccxt_adapter, "_now", lambda: NOW, raising=False)
    monkeypatch.setattr(ccxt_adapter, "last_clock_skew", lambda: None, raising=False)
    monkeypatch.setattr(watchlist_store, "read_watchlist", lambda *a, **kw: list(watchlist))
    return calls


def _ramp(n: int, start: float = 100.0) -> list[float]:
    return [start + i for i in range(n)]


def _by_symbol(body: SpaghettiResponse) -> dict[str, SpaghettiLine]:
    return {line.symbol: line for line in [*body.series, *body.references]}


def test_series_is_percent_change_from_each_coins_own_window_start(monkeypatch):
    # 250 bars; the 1d window is the last 200, so it starts at close 150.
    _install(monkeypatch, {"SOL": _ramp(250), "ETH": _ramp(90, start=10.0), "BTC": _ramp(90), "HYPE": _ramp(90)},
             ["SOL", "ETH"])
    body = screener_board.build_spaghetti("1d")
    lines = _by_symbol(body)
    sol = lines["SOL"]
    assert sol.points[-1].close == pytest.approx((349 - 150) / 150 * 100)
    # ETH is normalized from ITS OWN first close (10), not SOL's.
    eth = lines["ETH"]
    assert eth.points[-1].close == pytest.approx((99 - 10) / 10 * 100)


def test_every_available_line_starts_at_zero(monkeypatch):
    _install(monkeypatch, {"SOL": _ramp(250), "ETH": _ramp(70, start=3.0), "BTC": _ramp(120), "HYPE": _ramp(61)},
             ["SOL", "ETH"])
    for tf in ("15m", "1h", "4h", "1d", "1w"):
        body = screener_board.build_spaghetti(tf)
        for line in [*body.series, *body.references]:
            assert line.available, (tf, line.symbol)
            assert line.points[0].close == pytest.approx(0.0), (tf, line.symbol)


def test_window_is_the_boards_last_bars_capped_per_timeframe(monkeypatch):
    _install(monkeypatch, {"SOL": _ramp(250), "BTC": _ramp(250), "HYPE": _ramp(250)}, ["SOL"])
    for tf, cap in (("15m", 200), ("1h", 200), ("4h", 200), ("1d", 200), ("1w", 28)):
        body = screener_board.build_spaghetti(tf)
        assert body.window_cap_bars == cap
        sol = _by_symbol(body)["SOL"]
        assert sol.bars == cap == len(sol.points)
        frame = _df(tf, _ramp(250))
        assert sol.window_start == frame["timestamp"].iloc[-cap].strftime("%Y-%m-%dT%H:%M:%SZ")
        assert sol.window_end == frame["timestamp"].iloc[-1].strftime("%Y-%m-%dT%H:%M:%SZ")
        assert sol.points[0].timestamp == sol.window_start
        assert sol.last_bar_ts == sol.window_end
    # A coin with fewer bars than the cap but past the 60-bar rule keeps all of them.
    _install(monkeypatch, {"SOL": _ramp(75), "BTC": _ramp(75), "HYPE": _ramp(75)}, ["SOL"])
    assert _by_symbol(screener_board.build_spaghetti("1d"))["SOL"].bars == 75


def test_btc_and_hype_are_references_not_coin_lines(monkeypatch):
    frames = {"SOL": _ramp(90), "BTC": _ramp(90), "HYPE": _ramp(90)}
    _install(monkeypatch, frames, ["BTC", "SOL", "HYPE"])
    body = screener_board.build_spaghetti("1d")
    assert [s.symbol for s in body.series] == ["SOL"]
    assert [r.symbol for r in body.references] == ["BTC", "HYPE"]
    # Present even when the watchlist does not hold them.
    _install(monkeypatch, frames, ["SOL"])
    body = screener_board.build_spaghetti("1d")
    assert [r.symbol for r in body.references] == ["BTC", "HYPE"]
    assert all(r.available for r in body.references)


def test_thin_and_failed_coins_are_explicit_no_data_never_flat_zero(monkeypatch):
    _install(
        monkeypatch,
        {"SOL": _ramp(90), "THIN": _ramp(59), "BTC": _ramp(90)},
        ["SOL", "THIN", "TYPO", "DEAD"],
        status={"TYPO": "bad_symbol", "DEAD": "unavailable", "HYPE": "unavailable"},
    )
    lines = _by_symbol(screener_board.build_spaghetti("1d"))
    assert lines["SOL"].available is True
    for symbol, reason in (("THIN", "insufficient-history"), ("TYPO", "bad-symbol"),
                           ("DEAD", "source-unavailable"), ("HYPE", "source-unavailable")):
        line = lines[symbol]
        assert line.available is False, symbol
        assert line.reason == reason, symbol
        assert line.points == [], symbol
        assert line.bars == 0 and line.window_start is None and line.last_bar_ts is None


def test_payload_timestamps_are_utc_z(monkeypatch):
    _install(monkeypatch, {"SOL": _ramp(90), "BTC": _ramp(90), "HYPE": _ramp(90)}, ["SOL"])
    for tf in ("15m", "1w"):
        body = screener_board.build_spaghetti(tf).model_dump()
        assert body["server_time"] == "2026-10-03T14:10:00Z"
        for line in [*body["series"], *body["references"]]:
            for field in ("window_start", "window_end", "last_bar_ts"):
                assert _ZFORM.match(line[field]), (field, line[field])
            assert all(_ZFORM.match(p["timestamp"]) for p in line["points"])


def _ts_interface(name: str) -> dict[str, str]:
    src = (Path(__file__).resolve().parents[3] / "web" / "lib" / "types" / "screener.ts").read_text()
    match = re.search(r"export interface " + name + r"\s*\{(.*?)\n\}", src, re.S)
    assert match, f"interface {name} not found in screener.ts"
    fields = {}
    for line in match.group(1).splitlines():
        m = re.match(r"\s*(\w+)\??:\s*([^;]+);", line)
        if m:
            fields[m.group(1)] = m.group(2).strip()
    return fields


def test_pydantic_fields_match_typescript_interfaces():
    expected = {
        "SpaghettiLine": {
            "symbol": "string", "available": "boolean", "reason": "UnavailableReason | null",
            "points": "ChartBar[]", "window_start": "string | null", "window_end": "string | null",
            "bars": "number", "last_bar_ts": "string | null", "stale": "boolean",
        },
        "SpaghettiResponse": {
            "timeframe": "Timeframe", "window_cap_bars": "number", "server_time": "string | null",
            "series": "SpaghettiLine[]", "references": "SpaghettiLine[]",
        },
    }
    for model, name in ((SpaghettiLine, "SpaghettiLine"), (SpaghettiResponse, "SpaghettiResponse")):
        ts = _ts_interface(name)
        assert set(ts) == set(model.model_fields), f"{name}: pydantic and TypeScript field names differ"
        assert ts == expected[name]
        for field, info in model.model_fields.items():
            nullable_py = info.default is None and not info.is_required()
            assert ("| null" in ts[field]) == nullable_py, f"{name}.{field}: nullability differs"


def test_spaghetti_read_is_cache_only_while_worker_runs(monkeypatch):
    from api.routers import screener as screener_router

    calls = _install(monkeypatch, {"SOL": _ramp(90), "BTC": _ramp(90), "HYPE": _ramp(90)}, ["SOL"])
    state = {"cache_only": False}
    seen: list[bool] = []

    @contextmanager
    def fake_cached_reads_only():
        state["cache_only"] = True
        try:
            yield
        finally:
            state["cache_only"] = False

    original = screener_board.ccxt_adapter.fetch_ohlcv

    def recording_fetch(*a, **kw):
        seen.append(state["cache_only"])
        return original(*a, **kw)

    monkeypatch.setattr(screener_board.ccxt_adapter, "fetch_ohlcv", recording_fetch)
    monkeypatch.setattr(ccxt_adapter, "cached_reads_only", fake_cached_reads_only)
    monkeypatch.setattr(refresh_worker, "is_running", lambda: True)

    body = screener_router.get_spaghetti(timeframe="1d")
    assert body.series and seen and all(seen), "a spaghetti read fetched outside cache-only mode"
    assert len(calls) == len(seen)

    # Worker off: the S1 fetch-through, no cache-only wrapper.
    seen.clear()
    monkeypatch.setattr(refresh_worker, "is_running", lambda: False)
    screener_router.get_spaghetti(timeframe="1d")
    assert seen and not any(seen)
