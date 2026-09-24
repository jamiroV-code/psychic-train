"""RFC-2: Hyperliquid snapshot adapter. Fixture-only, no network."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import ccxt
import pytest

from api.data import hyperliquid_narrative_adapter as hl

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


def _t(symbol, name, vol, **info):
    return symbol, {"symbol": symbol, "quoteVolume": vol, "info": {"name": name, "dayNtlVlm": str(vol), **info}}


def tickers():
    return dict([
        _t("BTC/USDC:USDC", "BTC", 1000.0),
        _t("KPEPE/USDC:USDC", "kPEPE", 50.0),
        _t("OLD/USDC:USDC", "OLD", 5.0, isDelisted=True),
        _t("XYZ-TSLA/USDC:USDC", "xyz:TSLA", 700.0, hip3=True),
        _t("FOO/USDC:USDC", "FOO", None),
    ])


class FakeEx:
    def __init__(self, result=None, exc=None):
        self.result, self.exc, self.calls = result, exc, []

    def fetch_tickers(self, symbols=None, params={}):
        self.calls.append(params)
        if self.exc:
            raise self.exc
        return self.result


def test_parses_active_non_hip3_perps_and_requests_swap_only():
    ex = FakeEx(tickers())
    r = hl.fetch_daily_market_snapshot(exchange=ex, now=NOW)
    assert ex.calls == [{"type": "swap"}]
    assert r.status == "ok" and r.as_of == "2026-09-24"
    names = {p.base_name: p for p in r.perps}
    assert set(names) == {"BTC", "kPEPE", "FOO"}  # delisted + HIP-3 excluded
    assert names["kPEPE"].base == "KPEPE" and names["kPEPE"].quote_volume == 50.0
    assert names["FOO"].quote_volume is None  # missing stays None, never 0


@pytest.mark.parametrize("exc", [ccxt.RequestTimeout("t"), ccxt.NetworkError("n"), RuntimeError("x")])
def test_failure_is_unavailable_never_raises(exc):
    r = hl.fetch_daily_market_snapshot(exchange=FakeEx(exc=exc), now=NOW)
    assert r.status == "unavailable" and r.perps == [] and r.reason.startswith("fetch-failed")


def test_no_exchange_and_empty_list_are_unavailable(monkeypatch):
    monkeypatch.setattr(hl.ccxt_adapter, "_exchange", lambda: None)
    assert hl.fetch_daily_market_snapshot(now=NOW).reason == "exchange-unavailable"
    assert hl.fetch_daily_market_snapshot(exchange=FakeEx({}), now=NOW).reason == "empty-market-list"


def test_redistributable_is_conservative_single_constant():
    assert hl.HYPERLIQUID_REDISTRIBUTABLE is False
    assert hl.fetch_daily_market_snapshot(exchange=FakeEx(tickers()), now=NOW).redistributable is False


def test_utc_date_boundary():
    last = datetime(2026, 9, 24, 23, 59, 59, tzinfo=timezone.utc)
    first = datetime(2026, 9, 25, 0, 0, 0, tzinfo=timezone.utc)
    assert hl.utc_date(last) == "2026-09-24"
    assert hl.utc_date(first) == "2026-09-25"
    # A non-UTC wall clock is converted, not taken at face value.
    plus2 = timezone(timedelta(hours=2))
    assert hl.utc_date(datetime(2026, 9, 25, 1, 30, tzinfo=plus2)) == "2026-09-24"
    with pytest.raises(ValueError):
        hl.utc_date(datetime(2026, 9, 24))


@pytest.mark.integration
def test_real_hyperliquid_snapshot():
    r = hl.fetch_daily_market_snapshot()
    assert r.status == "ok", r.reason
    names = {p.base_name for p in r.perps}
    assert "BTC" in names
    assert all(":" not in n for n in names)
    print(sorted(n for n in names if n.startswith("k")))
