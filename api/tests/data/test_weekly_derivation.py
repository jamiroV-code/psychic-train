"""Golden-value tests for `1w` weekly OHLC derivation (ADR-5, week anchor).

Closes `process/general-plans/backlog/weekly-ohlc-golden-values_19-09-26.md`.

Why this file exists: Hyperliquid publishes no native weekly candle, so every
`1w` reading in the product comes from `_derive_weekly_from_daily`. Its
arithmetic had never been checked against known-good values — it could not
have been, because the EXECUTE sandbox shimmed ccxt and the OHLCV cache was
empty until RFC-005. This is exactly the failure class
`process/context/tests/all-tests.md` flags as highest-value: output that can
be wrong and still look entirely plausible on a chart.

What the investigation found, and what these tests therefore pin:

1. A bare `resample("W")` is `W-SUN`, closed="right", label="right". The
   Monday..Sunday *grouping* was already right; the *label* was the week's
   close date, six days after the exchange convention of labelling a weekly
   candle with its open. So no indicator over the close sequence was ever
   wrong — chart placement and cross-timeframe date joins were.
2. The trailing partial week was consequently stamped with a Sunday that had
   not happened yet: a bar dated in the future.

Every expected value below is hand-computed from the fixture, not read back
from the implementation.
"""
from __future__ import annotations

import pandas as pd
import pytest

from api.data import cache, ccxt_adapter


# --------------------------------------------------------------------------
# Fixture — three weeks of daily bars, the last one still forming.
#
#   week 1  Mon 2026-08-31 .. Sun 2026-09-06   (7 days, closed)
#   week 2  Mon 2026-09-07 .. Sun 2026-09-13   (7 days, closed)
#   week 3  Mon 2026-09-14 .. Sat 2026-09-19   (6 days, still forming)
#
# Day i (0-based from 2026-08-31) carries deliberately distinguishable
# values so that first / max / min / last / sum each pick a different number
# and a transposed aggregation cannot pass by coincidence:
#
#   open = 100 + i   high = 105 + i   low = 95 + i   close = 101 + i   volume = 10 + i
# --------------------------------------------------------------------------
FIRST_DAY = "2026-08-31"
LAST_DAY = "2026-09-19"


def _daily_fixture() -> pd.DataFrame:
    idx = pd.date_range(FIRST_DAY, LAST_DAY, freq="D", tz="UTC")
    i = range(len(idx))
    return pd.DataFrame(
        {
            "timestamp": idx,
            "open": [100 + n for n in i],
            "high": [105 + n for n in i],
            "low": [95 + n for n in i],
            "close": [101 + n for n in i],
            "volume": [10 + n for n in i],
            "source": ["fixture"] * len(idx),
        }
    )


# Hand-computed from the fixture above. Do not derive these from the code.
#
#   week 1  days 0..6   open 100  high 105+6 =111  low 95      close 101+6 =107  vol 10..16 = 91
#   week 2  days 7..13  open 107  high 105+13=118  low 95+7 =102  close 101+13=114  vol 17..23 = 140
#   week 3  days 14..19 open 114  high 105+19=124  low 95+14=109  close 101+19=120  vol 24..29 = 159
GOLDEN_WEEKS = [
    {"timestamp": "2026-08-31", "open": 100, "high": 111, "low": 95, "close": 107, "volume": 91},
    {"timestamp": "2026-09-07", "open": 107, "high": 118, "low": 102, "close": 114, "volume": 140},
    {"timestamp": "2026-09-14", "open": 114, "high": 124, "low": 109, "close": 120, "volume": 159},
]


@pytest.fixture
def weekly() -> pd.DataFrame:
    return ccxt_adapter._derive_weekly_from_daily(_daily_fixture(), source="fixture")


# --------------------------------------------------------------------------
# Golden values — the arithmetic itself.
# --------------------------------------------------------------------------
def test_weekly_ohlcv_matches_hand_computed_golden_values(weekly):
    assert len(weekly) == len(GOLDEN_WEEKS), (
        f"expected {len(GOLDEN_WEEKS)} weekly bars from {FIRST_DAY}..{LAST_DAY}, got {len(weekly)}"
    )
    for row, expected in zip(weekly.itertuples(index=False), GOLDEN_WEEKS):
        stamp = pd.Timestamp(expected["timestamp"], tz="UTC")
        assert row.timestamp == stamp, f"week label {row.timestamp} != {stamp}"
        assert row.open == expected["open"], f"{stamp:%Y-%m-%d} open"
        assert row.high == expected["high"], f"{stamp:%Y-%m-%d} high"
        assert row.low == expected["low"], f"{stamp:%Y-%m-%d} low"
        assert row.close == expected["close"], f"{stamp:%Y-%m-%d} close"
        assert row.volume == expected["volume"], f"{stamp:%Y-%m-%d} volume"


def test_weekly_open_is_mondays_open_and_close_is_sundays_close(weekly):
    """Spelled out separately from the golden table: this is the property a
    reader checks against TradingView, and it is the one a transposed agg
    (`open: "last"`) would break while still producing plausible numbers."""
    daily = _daily_fixture().set_index("timestamp")
    first_closed = weekly.iloc[0]
    assert first_closed["open"] == daily.loc["2026-08-31", "open"]
    assert first_closed["close"] == daily.loc["2026-09-06", "close"]


# --------------------------------------------------------------------------
# The anchor decision (ADR-5). These are the regression tests for the bug.
# --------------------------------------------------------------------------
def test_every_weekly_bar_is_labelled_with_a_monday(weekly):
    weekdays = weekly["timestamp"].dt.dayofweek.unique().tolist()
    assert weekdays == [0], (
        "weekly bars must be stamped with their Monday open, not their Sunday "
        f"close — got weekday(s) {weekdays}. A bare resample('W') is W-SUN "
        "right-labelled and reintroduces this."
    )


def test_bare_resample_W_is_not_equivalent_and_stays_rejected():
    """Pins the defect rather than the fix, so the reason the anchor is
    explicit survives in the suite. If a future pandas makes 'W' mean
    Monday-open, this test fails loudly and ADR-5 gets revisited — it does
    not silently become a no-op."""
    daily = _daily_fixture().set_index("timestamp")
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    naive = daily.resample("W").agg(agg).dropna(subset=["close"])
    anchored = daily.resample(
        ccxt_adapter.WEEK_ANCHOR, closed=ccxt_adapter.WEEK_CLOSED, label=ccxt_adapter.WEEK_LABEL
    ).agg(agg).dropna(subset=["close"])

    # Same buckets, same values — only the label moves. This is why no
    # indicator over the close sequence was ever wrong.
    assert naive.reset_index(drop=True).equals(anchored.reset_index(drop=True))
    # ...and the labels really do differ, by exactly six days.
    assert (naive.index - anchored.index).unique().tolist() == [pd.Timedelta(days=6)]


def test_no_weekly_bar_is_stamped_in_the_future(weekly):
    """The concrete symptom of the old anchor: on any day before Sunday the
    newest bar carried a label that had not happened yet."""
    newest = weekly["timestamp"].max()
    assert newest <= pd.Timestamp(LAST_DAY, tz="UTC"), (
        f"newest weekly bar {newest} is stamped after the last daily bar {LAST_DAY}"
    )


# --------------------------------------------------------------------------
# Partial trailing week — kept, by decision (ADR-5), not by accident.
# --------------------------------------------------------------------------
def test_forming_week_is_kept_and_labelled_like_any_other_bar(weekly):
    last = weekly.iloc[-1]
    assert last["timestamp"] == pd.Timestamp("2026-09-14", tz="UTC")
    assert last["close"] == 120, "forming week must close on the newest daily bar (Sat 2026-09-19)"


def test_forming_week_volume_is_only_the_days_elapsed(weekly):
    """Explicit so nobody reads the trailing bar as a full week. Six days of
    volume, not seven — the bar is live, and Standing Rule 4's immutability
    guarantee does not cover it."""
    # days 14..19 = 24+25+26+27+28+29 = 159. The seventh day (Sun, volume 30)
    # has not happened, so a full week would read 189.
    assert weekly.iloc[-1]["volume"] == 159
    assert weekly.iloc[-1]["volume"] != 189, "trailing bar must not already read as a full week"


def test_a_complete_week_closes_the_forming_bar_without_moving_earlier_ones(weekly):
    """Adding Sunday 2026-09-20 must finish week 3 and leave weeks 1-2 byte
    identical — the immutability half of ADR-5's carve-out."""
    daily = _daily_fixture()
    sunday = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2026-09-20", tz="UTC")],
            "open": [120], "high": [125], "low": [115], "close": [121],
            "volume": [30], "source": ["fixture"],
        }
    )
    extended = ccxt_adapter._derive_weekly_from_daily(
        pd.concat([daily, sunday], ignore_index=True), source="fixture"
    )
    assert len(extended) == 3, "a Sunday bar must complete week 3, not open a fourth"
    pd.testing.assert_frame_equal(extended.iloc[:2].reset_index(drop=True), weekly.iloc[:2].reset_index(drop=True))
    assert extended.iloc[-1]["close"] == 121
    assert extended.iloc[-1]["volume"] == 159 + 30


# --------------------------------------------------------------------------
# Edges.
# --------------------------------------------------------------------------
def test_a_missing_daily_bar_does_not_shift_week_membership():
    """A gap inside a week must shrink that week's aggregate, never push days
    into a neighbouring bucket."""
    daily = _daily_fixture()
    gapped = daily[daily["timestamp"] != pd.Timestamp("2026-09-09", tz="UTC")]
    weekly = ccxt_adapter._derive_weekly_from_daily(gapped, source="fixture")
    assert weekly["timestamp"].tolist() == [
        pd.Timestamp(w["timestamp"], tz="UTC") for w in GOLDEN_WEEKS
    ]
    wk2 = weekly.iloc[1]
    assert wk2["open"] == 107 and wk2["close"] == 114, "week 2 boundaries must not move"
    assert wk2["volume"] == 140 - 19, "only the missing day's volume should be absent"


def test_a_week_with_a_single_daily_bar_still_produces_one_weekly_bar():
    one = _daily_fixture().iloc[[0]]
    weekly = ccxt_adapter._derive_weekly_from_daily(one, source="fixture")
    assert len(weekly) == 1
    row = weekly.iloc[0]
    assert row["timestamp"] == pd.Timestamp("2026-08-31", tz="UTC")
    assert row["open"] == 100 and row["close"] == 101
    assert row["high"] == 105 and row["low"] == 95 and row["volume"] == 10


def test_empty_daily_returns_the_empty_schema_not_a_crash():
    empty = pd.DataFrame(columns=cache.OHLCV_COLUMNS)
    out = ccxt_adapter._derive_weekly_from_daily(empty, source="fixture")
    assert out.empty
    assert list(out.columns) == cache.OHLCV_COLUMNS


def test_output_carries_the_cache_schema_and_the_source_label(weekly):
    assert list(weekly.columns) == cache.OHLCV_COLUMNS
    assert weekly["source"].unique().tolist() == ["fixture"]


# --------------------------------------------------------------------------
# End to end through the adapter, against an isolated cache.
# --------------------------------------------------------------------------
class _DailyExchange:
    """Serves the daily fixture as if it were Hyperliquid."""

    id = "fixture-exchange"

    def load_markets(self):
        return {"BTC/USDC:USDC": {"swap": True, "spot": False, "base": "BTC", "baseName": "BTC", "active": True}}

    @property
    def markets(self):
        return self.load_markets()

    def fetch_ohlcv(self, symbol, timeframe="1d", since=None, limit=None):
        df = _daily_fixture()
        return [
            [int(r.timestamp.timestamp() * 1000), float(r.open), float(r.high), float(r.low), float(r.close), float(r.volume)]
            for r in df.itertuples(index=False)
        ]


def test_fetch_ohlcv_1w_writes_monday_labelled_bars_to_the_cache(isolated_cache):
    result = ccxt_adapter.fetch_ohlcv("BTC", "1w", exchange=_DailyExchange())
    assert not result.df.empty, "1w path returned nothing — check the daily leg"
    assert result.df["timestamp"].dt.dayofweek.unique().tolist() == [0]

    on_disk = cache.read_ohlcv("BTC", "1w")
    assert on_disk["timestamp"].dt.dayofweek.unique().tolist() == [0], (
        "the cached file, not just the in-memory frame, must carry Monday labels"
    )
