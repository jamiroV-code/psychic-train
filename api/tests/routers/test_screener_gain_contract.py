"""T34 / S2: the gain-chip contract, Python against its TypeScript mirror.

`web/lib/types/screener.ts` is kept in lockstep with `api/models/screener.py`
by hand; this reads the TS source and fails when `GainChip` drifts.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from api.analytics import screener_board
from api.data import watchlist as watchlist_store
from api.data.ccxt_adapter import OhlcvResult
from api.models.regime import CurrentLegState
from api.models.screener import CoinPanel, GainChip

_TS_PATH = Path(__file__).resolve().parents[3] / "web" / "lib" / "types" / "screener.ts"

# Python annotation -> the TS type the mirror must declare.
_EXPECTED_TS_TYPES = {
    "pct": "number | null",
    "open_ts": "string | null",
    "is_partial": "boolean",
    "stale": "boolean",
    "reason": "UnavailableReason | null",
}


def _ts_interface_fields(source: str, name: str) -> dict[str, str]:
    match = re.search(rf"export interface {name} \{{(.*?)\n\}}", source, re.S)
    assert match is not None, f"interface {name} not found in screener.ts"
    fields = {}
    for line in match.group(1).splitlines():
        field = re.match(r"\s*(\w+)\??:\s*([^;]+);", line)
        if field:
            fields[field.group(1)] = field.group(2).strip()
    return fields


def test_gain_chip_fields_match_typescript():
    source = _TS_PATH.read_text()
    ts_fields = _ts_interface_fields(source, "GainChip")
    assert set(ts_fields) == set(GainChip.model_fields)
    assert ts_fields == _EXPECTED_TS_TYPES
    assert set(_EXPECTED_TS_TYPES) == set(GainChip.model_fields)
    panel_fields = _ts_interface_fields(source, "CoinPanel")
    assert "gain_by_timeframe" in CoinPanel.model_fields
    assert panel_fields["gain_by_timeframe"] == "Record<Timeframe, GainChip>"
    assert panel_fields["percent_change_by_timeframe"] == "Record<Timeframe, number | null>"


def _df(n: int, freq: str, step: float) -> pd.DataFrame:
    closes = [100.0 + i * step for i in range(n)]
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(start="2024-01-01", periods=n, freq=freq, tz="UTC"),
            "open": [closes[0]] + closes[:-1],
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1.0] * n,
            "source": "test",
        }
    )


def test_percent_change_by_timeframe_equals_chip_pct(monkeypatch):
    frames = {"15m": _df(90, "15min", 1.0), "1h": _df(90, "h", -1.0), "4h": pd.DataFrame(), "1d": _df(90, "D", 2.0)}
    frames["1w"] = frames["1d"]

    def fetch(symbol, timeframe, since=None, limit=None, exchange=None):
        df = frames[timeframe]
        return OhlcvResult(symbol, timeframe, df, len(df) < 60, "ok" if not df.empty else "unavailable")

    no_leg = CurrentLegState(candidate_boundaries=[], confirmed_boundaries=[], composite_variant="reduced", has_data=False)
    monkeypatch.setattr(screener_board.ccxt_adapter, "fetch_ohlcv", fetch)
    monkeypatch.setattr(watchlist_store, "read_watchlist", lambda *a, **kw: ["BTC"])
    monkeypatch.setattr(screener_board.leg_boundary, "compute_current_leg_state", lambda *a, **k: no_leg)
    monkeypatch.setattr(screener_board.narrative_trigger, "assemble_narrative_categories", lambda *a, **k: [])

    panel = screener_board.build_screener_board(timeframe="1d").coins[0]
    assert set(panel.gain_by_timeframe) == {"15m", "1h", "4h", "1d", "1w"}
    for tf, chip in panel.gain_by_timeframe.items():
        assert panel.percent_change_by_timeframe[tf] == chip.pct, tf
    assert panel.gain_by_timeframe["15m"].pct > 0
    assert panel.gain_by_timeframe["1h"].pct < 0
    assert panel.gain_by_timeframe["4h"].pct is None
    assert panel.gain_by_timeframe["4h"].reason == "source-unavailable"
    # Serialized payload: the chip's open is a `Z` timestamp (convention 3).
    payload = panel.model_dump()
    assert payload["gain_by_timeframe"]["1d"]["open_ts"].endswith("Z")
