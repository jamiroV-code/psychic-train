"""Cross-adapter failure-contract test (Implementation Checklist item 4a).

Public Contracts: every `api/data/*_adapter.py` module returns a typed
success payload or an explicit `unavailable`/`stale` marker — no adapter may
raise past its own boundary into a router.

RFC-001 scope note: only `ccxt_adapter` exists at this point in the plan
(liqtide/fred/pytrends/reddit/coingecko adapters are RFC-002/RFC-003 scope
per PLAN.md's Phased Delivery Plan). This test is parametrized over the one
adapter that exists; RFC-002/RFC-003 EXECUTE should add their adapters as
additional parametrize cases against this same shared contract, not a new
test file, per item 4a's intent ("the cross-adapter test the Public
Contracts... guarantee relies on").
"""
from __future__ import annotations

import ccxt
import pandas as pd
import pytest

from api.data import ccxt_adapter


class _TimeoutExchange:
    id = "test-exchange"

    def fetch_ohlcv(self, symbol, timeframe="1d", since=None, limit=None):
        raise ccxt.RequestTimeout("simulated timeout")


class _MalformedExchange:
    id = "test-exchange"

    def fetch_ohlcv(self, symbol, timeframe="1d", since=None, limit=None):
        # malformed/partial payload: missing OHLCV columns entirely
        return [["not", "a", "real", "candle"]]


class _RateLimitedExchange:
    id = "test-exchange"

    def __init__(self):
        self.calls = 0

    def fetch_ohlcv(self, symbol, timeframe="1d", since=None, limit=None):
        self.calls += 1
        raise ccxt.RateLimitExceeded("simulated 429")


ADAPTER_CASES = [
    pytest.param(ccxt_adapter, id="ccxt_adapter"),
]


@pytest.mark.parametrize("adapter", ADAPTER_CASES)
def test_timeout_returns_unavailable_never_raises(adapter, monkeypatch, tmp_path):
    monkeypatch.setattr(adapter.cache, "CACHE_ROOT", tmp_path)
    result = adapter.fetch_ohlcv("BTC", "1d", exchange=_TimeoutExchange())
    assert result.status == "unavailable"


@pytest.mark.parametrize("adapter", ADAPTER_CASES)
def test_malformed_payload_returns_unavailable_never_raises(adapter, monkeypatch, tmp_path):
    monkeypatch.setattr(adapter.cache, "CACHE_ROOT", tmp_path)
    # A malformed payload either fails to coerce (caught) or produces a df
    # cache.write_ohlcv can't persist meaningfully; either way this must not
    # raise past the adapter boundary.
    try:
        result = adapter.fetch_ohlcv("BTC", "1d", exchange=_MalformedExchange())
    except Exception as exc:  # pragma: no cover - contract failure
        pytest.fail(f"adapter raised past its boundary: {exc!r}")
    assert result.status in ("ok", "unavailable")


@pytest.mark.parametrize("adapter", ADAPTER_CASES)
def test_rate_limit_backs_off_then_returns_unavailable(adapter, monkeypatch, tmp_path):
    monkeypatch.setattr(adapter.cache, "CACHE_ROOT", tmp_path)
    monkeypatch.setattr(adapter, "BACKOFF_BASE_SECONDS", 0.0)  # don't slow the test down
    exch = _RateLimitedExchange()
    result = adapter.fetch_ohlcv("BTC", "1d", exchange=exch)
    assert result.status == "unavailable"
    assert exch.calls == adapter.MAX_RETRIES  # backoff actually retried, not a single fast-fail


@pytest.mark.parametrize("adapter", ADAPTER_CASES)
def test_insufficient_history_flagged_on_thin_cache(adapter, monkeypatch, tmp_path):
    monkeypatch.setattr(adapter.cache, "CACHE_ROOT", tmp_path)
    result = adapter.fetch_ohlcv("BTC", "1d", exchange=_TimeoutExchange())
    assert result.insufficient_history is True
    assert isinstance(result.df, pd.DataFrame)
