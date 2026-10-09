"""T38 / S7: GET /api/regime/btc-legs and the cache-only BTC read of both
regime leg endpoints (C8; S8 open item a).

The cache-only tests stub `liquidity_composite`'s builders and
`select_composite_variant` as `test_leg_boundary.py` does, so no network is
touched, and replace the adapter's exchange with one that records every
call: while the worker runs it must see none.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from api.analytics.regime import leg_boundary, liquidity_composite
from api.data import cache, ccxt_adapter, refresh_worker
from api.main import app
from api.models.regime import (
    AgeEstimate,
    BtcLeg,
    BtcLegBoundary,
    BtcLegChartResponse,
    CompositeEstimate,
    CurrentLeg,
    LatestCandidate,
    LegEstimate,
)
from api.routers import regime as regime_router

ROOT = Path(__file__).resolve().parents[3]
_ZFORM = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _composite() -> pd.DataFrame:
    """Flat with one sharp sustained shift at day 100: one candidate there."""
    dates = pd.date_range("2023-01-01", periods=200, freq="D", tz="utc")
    values = np.full(200, 100.0)
    values[100:] += 4.0
    return pd.DataFrame({"date": dates, "composite": values})


def _btc_bars() -> pd.DataFrame:
    """Flat, then a clean higher-high/higher-low shift at bar 100."""
    stamps = pd.date_range("2023-01-01", periods=200, freq="D", tz="utc")
    close = np.full(200, 100.0)
    close[100:] = 101.0 + np.arange(100) * 0.5
    return pd.DataFrame(
        {
            "timestamp": stamps,
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.full(200, 1.0),
            "source": "fixture",
        }
    )


def _stub_composite(monkeypatch):
    class _Result:
        available = True
        series = _composite()
        variant = "reduced"

    monkeypatch.setattr(liquidity_composite, "select_composite_variant", lambda d: "reduced")
    monkeypatch.setattr(liquidity_composite, "build_reduced_composite", lambda *a, **k: _Result())
    monkeypatch.setattr(liquidity_composite, "build_full_composite", lambda *a, **k: _Result())


def _seed_btc(monkeypatch, isolated_cache) -> list[str]:
    """An old BTC 1d cache (so a fetch-through read would go to the
    exchange) and an exchange that records every call."""
    cache.write_ohlcv("BTC", "1d", _btc_bars(), fetched_at=pd.Timestamp("2023-07-20", tz="UTC"))
    calls: list[str] = []

    def recording_exchange():
        calls.append("exchange")
        return None  # the adapter then serves the cache as "unavailable"

    monkeypatch.setattr(ccxt_adapter, "_exchange", recording_exchange)
    monkeypatch.setattr(ccxt_adapter, "set_refresh_hook", lambda hook: None)
    return calls


def test_endpoint_shape_and_utc_z_timestamps(monkeypatch, isolated_cache):
    _stub_composite(monkeypatch)
    _seed_btc(monkeypatch, isolated_cache)
    monkeypatch.setattr(refresh_worker, "is_running", lambda: True)

    resp = TestClient(app).get("/api/regime/btc-legs")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == set(BtcLegChartResponse.model_fields)
    assert body["available"] is True
    assert body["bar_count"] == 200 == len(body["btc"])
    for field in ("server_time", "first_bar_ts", "last_bar_ts"):
        assert _ZFORM.match(body[field]), (field, body[field])
    assert all(_ZFORM.match(p["timestamp"]) for p in body["btc"])
    assert body["first_bar_ts"] == "2023-01-01T00:00:00Z"
    assert len(body["boundaries"]) == 1 and len(body["legs"]) == 1
    leg = body["legs"][0]
    assert leg["is_current"] is True and leg["end"] is None
    assert body["current_leg"]["start_date"] == leg["start"]
    assert body["estimate"]["heading"] == "Estimate (rule over the numbers shown)"
    assert body["estimate"]["age"]["label"] is None  # no earlier legs here
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", body["boundaries"][0]["date"])


def _ts_interfaces() -> dict[str, dict[str, str]]:
    src = (ROOT / "web" / "lib" / "types" / "btc-legs.ts").read_text()
    out = {}
    for match in re.finditer(r"export interface (\w+)\s*\{(.*?)\n\}", src, re.S):
        fields = {}
        for line in match.group(2).splitlines():
            m = re.match(r"\s*(\w+)\??:\s*([^;]+);", line)
            if m:
                fields[m.group(1)] = m.group(2).strip()
        out[match.group(1)] = fields
    return out


def test_pydantic_fields_match_typescript_interfaces():
    ts = _ts_interfaces()
    models = (
        BtcLegBoundary, BtcLeg, LatestCandidate, CurrentLeg, AgeEstimate, CompositeEstimate, LegEstimate,
        BtcLegChartResponse,
    )
    assert set(ts) == {m.__name__ for m in models}
    for model in models:
        fields = ts[model.__name__]
        assert set(fields) == set(model.model_fields), f"{model.__name__}: pydantic and TypeScript field names differ"
        for field, info in model.model_fields.items():
            nullable_py = info.default is None and not info.is_required()
            assert ("| null" in fields[field]) == nullable_py, f"{model.__name__}.{field}: nullability differs"
    assert ts["BtcLegChartResponse"]["btc"] == "ChartBar[]"
    assert ts["AgeEstimate"]["label"] == "AgeLabel | null"
    assert ts["CompositeEstimate"]["label"] == "CompositeChangeLabel | null"
    src = (ROOT / "web" / "lib" / "types" / "btc-legs.ts").read_text()
    assert 'export type AgeLabel = "early" | "mid" | "late";' in src
    assert 'export type CompositeChangeLabel = "rising" | "falling" | "flat";' in src


def test_btc_legs_read_is_cache_only_while_worker_runs(monkeypatch, isolated_cache):
    _stub_composite(monkeypatch)
    calls = _seed_btc(monkeypatch, isolated_cache)
    monkeypatch.setattr(refresh_worker, "is_running", lambda: True)

    body = regime_router.get_btc_legs()
    assert body.available is True and body.bar_count == 200
    assert calls == [], "the BTC leg chart reached the exchange while the worker runs"

    # Worker off: the S1 fetch-through goes to the exchange for the stale cache.
    monkeypatch.setattr(refresh_worker, "is_running", lambda: False)
    regime_router.get_btc_legs()
    assert calls


def test_regime_legs_read_is_cache_only_while_worker_runs(monkeypatch, isolated_cache):
    _stub_composite(monkeypatch)
    calls = _seed_btc(monkeypatch, isolated_cache)
    monkeypatch.setattr(refresh_worker, "is_running", lambda: True)

    body = regime_router.get_legs()
    assert body.candidate_boundaries, "fixture should yield a candidate, so the BTC read happens"
    assert calls == [], "/api/regime/legs reached the exchange while the worker runs"
    # The cached bars were still used to confirm.
    assert body.confirmed_boundaries

    monkeypatch.setattr(refresh_worker, "is_running", lambda: False)
    regime_router.get_legs()
    assert calls


S7_VERDICT_FILES = (
    "api/analytics/regime/btc_legs.py",
    "web/lib/btc-leg-lines.ts",
    "web/components/screener/BtcLegChart.tsx",
    "web/components/screener/LegEstimate.tsx",
)
S7_VERDICT_WORDS = re.compile(
    r"\b(bullish|bearish|bull|bear|buy|sell|confidence|signal|outperform|outperforming|underperform|"
    r"underperforming|risk-on|risk-off|favorable)\b",
    re.I,
)


def test_btc_legs_sources_contain_no_verdict_words():
    hits = []
    for rel in S7_VERDICT_FILES:
        path = ROOT / rel
        assert path.exists(), rel
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if S7_VERDICT_WORDS.search(line):
                hits.append(f"{rel}:{n}: {line.strip()}")
    assert hits == []
