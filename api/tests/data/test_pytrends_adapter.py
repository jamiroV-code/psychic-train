"""narrative-v2 RFC-3 (ADR-3): anchor-chained pytrends batching, plus
pytrends_adapter._fetch_live's isPartial row handling. No network.

`pytrends` is not installed in the api env, so a fake `pytrends.request`
module is injected via sys.modules for the isPartial tests. Synthetic
frames only, no network.
"""
from __future__ import annotations

import sys
import types

import pandas as pd
import pytest

from api.data import pytrends_adapter
from api.data import pytrends_adapter as pa

TODAY = "2026-09-28"


def _frame(values: dict, day: str = TODAY) -> pd.DataFrame:
    return pd.DataFrame({k: [v] for k, v in values.items()}, index=pd.DatetimeIndex([day], name="date"))


def test_batch_5_terms_per_request():
    kws = [f"k{i}" for i in range(30)]  # 15 narratives x 2 keywords
    batches = pa.plan_batches(kws, "k0")
    assert all(len(b) <= 5 for b in batches)
    assert all(b[0] == "k0" for b in batches)
    assert batches[0] == ["k0", "k1", "k2", "k3", "k4"]
    assert batches[1] == ["k0", "k5", "k6", "k7", "k8"]
    covered = [k for b in batches for k in b[1:]]
    assert sorted(covered + ["k0"]) == sorted(kws) and len(covered) == len(set(covered))
    assert len(batches) == 8  # worst case: ceil(29 / 4)


def test_plan_batches_dedupes_and_single_keyword():
    assert pa.plan_batches(["a", "a"]) == [["a"]]
    assert pa.plan_batches([]) == []


def test_anchor_chaining_rescales_second_batch():
    # hand-computed: scale = anchor_b0 / anchor_b1 = 40 / 80 = 0.5
    batches = [["A", "x"], ["A", "y"]]
    out = pa.chain_batches([{"A": 40.0, "x": 100.0}, {"A": 80.0, "y": 60.0}], batches, "A")
    assert out["A"].value == 40.0 and out["x"].value == 100.0
    assert out["y"].value == pytest.approx(30.0) and out["y"].status == "ok"


def test_zero_anchor_marks_batch_insufficient_not_fabricated_ratio():
    batches = [["A", "x"], ["A", "y", "z"]]
    out = pa.chain_batches([{"A": 40.0, "x": 10.0}, {"A": 0.5, "y": 60.0, "z": 5.0}], batches, "A")
    assert out["x"].status == "ok"
    for k in ("y", "z"):
        assert out[k].status == "insufficient" and out[k].value is None
        assert out[k].reason == "anchor-below-epsilon"


def test_zero_reference_anchor_marks_every_batch_insufficient():
    batches = [["A", "x"], ["A", "y"]]
    out = pa.chain_batches([{"A": 0.0, "x": 10.0}, {"A": 50.0, "y": 60.0}], batches, "A")
    assert all(v.status == "insufficient" and v.value is None for v in out.values())


def test_failed_batch_is_unavailable_others_unaffected():
    batches = [["A", "x"], ["A", "y"]]
    out = pa.chain_batches([{"A": 40.0, "x": 10.0}, None], batches, "A")
    assert out["x"].status == "ok" and out["y"].status == "unavailable"


def test_fetch_trends_batched_end_to_end(monkeypatch):
    calls = []

    def fake(terms, timeframe="now 7-d"):
        calls.append(list(terms))
        base = {"A": 40.0} if "x" in terms else {"A": 80.0}
        return _frame({**base, **{t: 60.0 for t in terms if t != "A"}})
    monkeypatch.setattr(pa, "_fetch_batch_live", fake)
    res = pa.fetch_trends_batched(["A", "x", "b", "c", "d", "y"], "A")
    assert calls == [["A", "x", "b", "c", "d"], ["A", "y"]] and res.requests == 2
    assert res.as_of == TODAY
    assert res.values["x"].value == 60.0 and res.values["y"].value == pytest.approx(30.0)


def test_batch_with_different_timestamp_is_not_chained(monkeypatch):
    def fake(terms, timeframe="now 7-d"):
        return _frame({t: 50.0 for t in terms}, TODAY if "x" in terms else "2026-09-27")
    monkeypatch.setattr(pa, "_fetch_batch_live", fake)
    res = pa.fetch_trends_batched(["A", "x", "b", "c", "d", "y"], "A")
    assert res.values["x"].status == "ok" and res.values["y"].status == "unavailable"


def test_blend_is_simple_mean():
    assert pa.blend([10.0, 20.0, 30.0]) == 20.0


def test_single_keyword_fetch_trend_untouched():
    # the legacy single-keyword surface still exists with its original signature
    import inspect
    assert list(inspect.signature(pa.fetch_trend).parameters) == ["keyword"]
    assert list(inspect.signature(pa._fetch_live).parameters) == ["keyword"]


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
