"""The Parquet -> DuckDB round trip must preserve UTC (ADR-6).

Why this file exists, stated plainly: ADR-5's 13 golden-value tests were green
while the live weekly series was still wrong. They call
`_derive_weekly_from_daily` directly on tz-aware UTC fixtures and never cross
the cache boundary, and the boundary is where the defect lived — DuckDB
converts a TIMESTAMP WITH TIME ZONE to the session timezone on read, which
defaulted to the machine's local zone. On a Europe/Brussels machine the
weekly anchor landed on Brussels midnight: labelled Monday locally, Sunday
22:00 in UTC, and moving by an hour across each DST transition.

Every test here therefore writes through the cache and reads back out through
it. A test that builds a DataFrame in memory and asserts on it cannot fail the
way production did.

The first half covers OHLCV; the second covers the other readers (liquidity,
liqtide, legs, narrative, trending), which the UTC pin also changed and which
had no assertion until now.
"""
from __future__ import annotations

import pandas as pd
import pytest

from api.data import cache, ccxt_adapter


def _utc_daily(start: str = "2026-08-31", end: str = "2026-09-19") -> pd.DataFrame:
    """Daily bars at 00:00 UTC — what the exchange actually sends."""
    idx = pd.date_range(start, end, freq="D", tz="UTC")
    n = range(len(idx))
    return pd.DataFrame(
        {
            "timestamp": idx,
            "open": [100 + i for i in n],
            "high": [105 + i for i in n],
            "low": [95 + i for i in n],
            "close": [101 + i for i in n],
            "volume": [10 + i for i in n],
            "source": ["fixture"] * len(idx),
        }
    )


# --------------------------------------------------------------------------
# The contract.
# --------------------------------------------------------------------------
def test_read_ohlcv_returns_utc_regardless_of_machine_timezone(isolated_cache):
    cache.write_ohlcv("BTC", "1d", _utc_daily())
    out = cache.read_ohlcv("BTC", "1d")

    assert len(out) > 0
    tz = out["timestamp"].dt.tz
    assert tz is not None, "cached timestamps came back tz-naive — timezone information was lost"
    assert str(tz) == "UTC", (
        f"cached timestamps came back as {tz!r}, not UTC. DuckDB is converting to the "
        "session timezone; see cache._connect()."
    )


def test_round_trip_preserves_the_exact_instants(isolated_cache):
    original = _utc_daily()
    cache.write_ohlcv("BTC", "1d", original)
    out = cache.read_ohlcv("BTC", "1d")
    pd.testing.assert_series_equal(
        out["timestamp"].reset_index(drop=True),
        original["timestamp"].reset_index(drop=True),
        check_names=False,
    )


def test_daily_bars_read_back_at_midnight_utc(isolated_cache):
    """The symptom that exposed this: bars stored at 00:00 UTC were read back
    at 01:00/02:00 local, which is what moved the weekly anchor."""
    cache.write_ohlcv("BTC", "1d", _utc_daily())
    out = cache.read_ohlcv("BTC", "1d")
    times = out["timestamp"].dt.strftime("%H:%M:%S").unique().tolist()
    assert times == ["00:00:00"], f"expected every daily bar at 00:00 UTC, got {times}"


# --------------------------------------------------------------------------
# The consequence — this is the assertion the ADR-5 suite could not make.
# --------------------------------------------------------------------------
def test_weekly_anchor_is_monday_midnight_utc_after_a_round_trip(isolated_cache):
    cache.write_ohlcv("BTC", "1d", _utc_daily())
    daily = cache.read_ohlcv("BTC", "1d")

    weekly = ccxt_adapter._derive_weekly_from_daily(daily, source="fixture")
    stamps = pd.to_datetime(weekly["timestamp"], utc=True)

    assert stamps.dt.dayofweek.unique().tolist() == [0], (
        "weekly bars are not Monday-anchored in UTC. Monday in a local timezone is "
        "Sunday 22:00/23:00 UTC — that is the ADR-6 defect, not the ADR-5 one."
    )
    assert stamps.dt.strftime("%H:%M:%S").unique().tolist() == ["00:00:00"], (
        "weekly bars are Monday but not at midnight UTC — the anchor is still local."
    )


def test_full_fetch_path_writes_utc_anchored_weeklies(isolated_cache):
    """End to end through `fetch_ohlcv`, then read the file back — the exact
    path that produced Sunday-labelled bars on the live cache."""

    class _Exchange:
        id = "fixture-exchange"

        def load_markets(self):
            return {"BTC/USDC:USDC": {"swap": True, "spot": False, "base": "BTC", "baseName": "BTC", "active": True}}

        @property
        def markets(self):
            return self.load_markets()

        def fetch_ohlcv(self, symbol, timeframe="1d", since=None, limit=None):
            df = _utc_daily()
            return [
                [int(r.timestamp.timestamp() * 1000), float(r.open), float(r.high),
                 float(r.low), float(r.close), float(r.volume)]
                for r in df.itertuples(index=False)
            ]

    ccxt_adapter.fetch_ohlcv("BTC", "1w", exchange=_Exchange())
    on_disk = pd.to_datetime(cache.read_ohlcv("BTC", "1w")["timestamp"], utc=True)

    assert not on_disk.empty
    assert on_disk.dt.dayofweek.unique().tolist() == [0]
    assert on_disk.dt.strftime("%H:%M:%S").unique().tolist() == ["00:00:00"]


# --------------------------------------------------------------------------
# DST — the part that would otherwise only break twice a year.
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "start,end,label",
    [
        ("2026-03-23", "2026-04-13", "spring forward (EU DST starts 2026-03-29)"),
        ("2026-10-19", "2026-11-09", "fall back (EU DST ends 2026-10-25)"),
    ],
)
def test_week_length_is_constant_across_a_dst_transition(isolated_cache, start, end, label):
    """A locally-anchored week is 167 or 169 hours long in the transition week.
    A UTC-anchored one is always 168."""
    cache.write_ohlcv("BTC", "1d", _utc_daily(start, end))
    daily = cache.read_ohlcv("BTC", "1d")
    weekly = ccxt_adapter._derive_weekly_from_daily(daily, source="fixture")

    stamps = pd.to_datetime(weekly["timestamp"], utc=True).sort_values()
    gaps = stamps.diff().dropna().unique().tolist()
    assert gaps == [pd.Timedelta(days=7)], (
        f"{label}: weekly spacing was {gaps}, not a constant 7 days — the anchor is "
        "following a local clock, not UTC."
    )


# --------------------------------------------------------------------------
# The other readers (ADR-6 residual 4).
#
# `_connect()`'s UTC pin applies to every read in `cache.py`, not just OHLCV,
# but only OHLCV had an assertion. These caches key on a `date` column rather
# than `timestamp`, and `_as_utc` is deliberately not applied to them — the
# DuckDB session pin is the whole mechanism here, so if it ever regresses
# these are the tests that say so.
#
# Two contracts, depending on what the writer stored:
#   - a datetime written in UTC must read back in UTC
#   - a string date must read back as the same string, never silently coerced
# --------------------------------------------------------------------------
def _utc_dates(n: int = 5) -> pd.DatetimeIndex:
    return pd.date_range("2026-09-14", periods=n, freq="D", tz="UTC")


def test_liquidity_series_datetimes_read_back_in_utc(isolated_cache):
    dates = _utc_dates()
    cache.write_liquidity_series("WALCL", pd.DataFrame({"date": dates, "value": range(len(dates))}))
    out = cache.read_liquidity_series("WALCL")

    assert len(out) == len(dates)
    tz = out["date"].dt.tz
    assert tz is not None and str(tz) == "UTC", f"liquidity series read back as {tz!r}, not UTC"
    pd.testing.assert_series_equal(
        pd.to_datetime(out["date"], utc=True).reset_index(drop=True),
        pd.Series(dates).reset_index(drop=True),
        check_names=False,
    )


def test_liqtide_history_datetimes_read_back_in_utc(isolated_cache):
    day = pd.Timestamp("2026-09-14", tz="UTC")
    cache.write_liqtide_payload(
        "2026-09-14",
        pd.DataFrame([{"date": day, "net_liquidity": 1.0, "composite": 50.0}]),
    )
    out = cache.read_liqtide_history()

    assert not out.empty
    tz = out["date"].dt.tz
    assert tz is not None and str(tz) == "UTC", f"liqtide history read back as {tz!r}, not UTC"
    assert pd.to_datetime(out["date"], utc=True).iloc[0] == day


def test_narrative_series_string_dates_are_not_coerced(isolated_cache):
    """These are written as plain `YYYY-MM-DD` strings. A reader that parsed
    them into local-time datetimes would shift the day for anyone west of
    UTC — silently, and only for them."""
    cache.write_narrative_point("pytrends", "ai", "2026-09-14", 42.0)
    out = cache.read_narrative_series("pytrends", "ai")

    assert len(out) == 1
    assert out["date"].iloc[0] == "2026-09-14", (
        f"narrative date came back as {out['date'].iloc[0]!r} — it was written as a string "
        "and must not be reinterpreted on read"
    )
    assert out["raw_value"].iloc[0] == 42.0


def test_trending_snapshot_string_date_is_not_coerced(isolated_cache):
    cache.write_trending_snapshot("2026-09-14", ["BTC", "HYPE", "SOL"])
    result = cache.read_trending_snapshot()

    assert result is not None
    date, symbols = result
    assert date == "2026-09-14"
    assert symbols == ["BTC", "HYPE", "SOL"]


def test_ohlcv_last_refresh_is_tz_aware_utc(isolated_cache):
    """It is compared against `pd.Timestamp.now(tz="UTC")`; a naive or
    local-tz return makes that comparison wrong by the UTC offset."""
    daily = _utc_daily()
    cache.write_ohlcv("BTC", "1d", daily)
    last = cache.ohlcv_last_refresh("BTC", "1d")

    assert last is not None
    assert last.tzinfo is not None, "ohlcv_last_refresh returned a naive timestamp"
    assert str(last.tz) == "UTC"
    assert last == daily["timestamp"].max()
    # The comparison its caller actually performs must not raise.
    assert (pd.Timestamp.now(tz="UTC") - last).total_seconds() > 0


def test_ohlcv_last_refresh_is_none_when_nothing_is_cached(isolated_cache):
    assert cache.ohlcv_last_refresh("NOPE", "1d") is None
