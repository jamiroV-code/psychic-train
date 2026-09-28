"""Unit tests for pytrends_adapter._fetch_live's isPartial row handling.

`pytrends` is not installed in the api env, so a fake `pytrends.request`
module is injected via sys.modules. Synthetic frames only, no network.
"""
from __future__ import annotations

import sys
import types

import pandas as pd

from api.data import pytrends_adapter

KEYWORD = "memecoin"


def _install_fake_pytrends(monkeypatch, frame: pd.DataFrame) -> None:
    class FakeTrendReq:
        def __init__(self, *args, **kwargs):
            pass

        def build_payload(self, *args, **kwargs):
            pass

        def interest_over_time(self):
            return frame

    fake_pkg = types.ModuleType("pytrends")
    fake_request = types.ModuleType("pytrends.request")
    fake_request.TrendReq = FakeTrendReq
    fake_pkg.request = fake_request
    monkeypatch.setitem(sys.modules, "pytrends", fake_pkg)
    monkeypatch.setitem(sys.modules, "pytrends.request", fake_request)


def _index() -> pd.DatetimeIndex:
    return pd.DatetimeIndex(
        ["2026-09-26 22:00", "2026-09-27 23:00", "2026-09-28 00:00"], name="date"
    )


def test_fetch_live_drops_partial_hour_row(monkeypatch):
    frame = pd.DataFrame(
        {KEYWORD: [30, 42, 0], "isPartial": [False, False, True]}, index=_index()
    )
    _install_fake_pytrends(monkeypatch, frame)
    assert pytrends_adapter._fetch_live(KEYWORD) == (42.0, "2026-09-27")


def test_fetch_live_all_rows_partial_returns_none(monkeypatch):
    frame = pd.DataFrame(
        {KEYWORD: [30, 42, 0], "isPartial": [True, True, True]}, index=_index()
    )
    _install_fake_pytrends(monkeypatch, frame)
    assert pytrends_adapter._fetch_live(KEYWORD) == (None, None)


def test_fetch_live_no_ispartial_column_unchanged(monkeypatch):
    frame = pd.DataFrame({KEYWORD: [30, 42, 7]}, index=_index())
    _install_fake_pytrends(monkeypatch, frame)
    assert pytrends_adapter._fetch_live(KEYWORD) == (7.0, "2026-09-28")
