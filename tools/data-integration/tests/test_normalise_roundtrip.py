"""normalise.py + store_writer.py: exact OHLCV_COLUMNS, round trip through the cache read functions."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from api.data import cache
from data_integration.normalise import normalise
from data_integration.parse import parse_table
from data_integration.store_writer import TargetNotEmpty, write_series

FIX = Path(__file__).parent / "fixtures"


def _df(name="ok.html"):
    return normalise(parse_table((FIX / name).read_text(), "table.prices"), "synthetic")


def test_columns_are_exactly_ohlcv_columns():
    df = _df()
    assert list(df.columns) == cache.OHLCV_COLUMNS
    assert str(df["timestamp"].dt.tz) == "UTC"
    assert (df["source"] == "synthetic").all()
    assert df["close"].dtype.kind == "f"


def test_round_trip_through_cache_read():
    df = _df()
    write_series("BTC-HIST", "1d", df)
    back = cache.read_ohlcv("BTC-HIST", "1d")
    assert list(back.columns) == cache.OHLCV_COLUMNS
    assert len(back) == 4
    pd.testing.assert_frame_equal(back.reset_index(drop=True), df.reset_index(drop=True), check_dtype=False)


def test_non_empty_key_refused_without_replace():
    write_series("BTC-HIST", "1d", _df())
    with pytest.raises(TargetNotEmpty):
        write_series("BTC-HIST", "1d", _df("ok_v2.html"))
    assert cache.read_ohlcv("BTC-HIST", "1d")["close"].iloc[-1] == 111


def test_replace_true_replaces_series():
    write_series("BTC-HIST", "1d", _df())
    write_series("BTC-HIST", "1d", _df("ok_v2.html"), replace=True)
    assert cache.read_ohlcv("BTC-HIST", "1d")["close"].iloc[-1] == 113
