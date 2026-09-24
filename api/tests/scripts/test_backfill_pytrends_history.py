"""RFC-2: pytrends backfill. pytrends is mocked; isolated_cache only."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from api.data import cache
from api.scripts import backfill_pytrends_history as bf

TODAY = date(2026, 9, 24)


def frame(keyword, start="2026-09-20", periods=5, freq="D", partial_last=True):
    idx = pd.date_range(start, periods=periods, freq=freq, name="date")
    df = pd.DataFrame({keyword: range(10, 10 + periods), "isPartial": [False] * periods}, index=idx)
    if partial_last:
        df.iloc[-1, df.columns.get_loc("isPartial")] = True
    return df


class FakeTrendReq:
    def __init__(self, df=None, exc=None):
        self.df, self.exc, self.timeframes = df, exc, []

    def build_payload(self, kw_list, timeframe):
        self.timeframes.append((kw_list, timeframe))

    def interest_over_time(self):
        if self.exc:
            raise self.exc
        return self.df


def test_window_is_269_days_daily():
    assert bf.window_timeframe(TODAY) == "2025-12-29 2026-09-24"


def test_rows_written_backfilled_partial_dropped(isolated_cache):
    fake = FakeTrendReq(frame("AI crypto"))
    out = bf.backfill_category("ai", "AI crypto", TODAY, lambda: fake)
    assert fake.timeframes == [(["AI crypto"], "2025-12-29 2026-09-24")]
    assert out.status == "ok" and out.written == 4 and out.dropped_partial == 1
    s = cache.read_narrative_series("pytrends", "AI crypto")
    assert list(s["date"].astype(str)) == ["2026-09-20", "2026-09-21", "2026-09-22", "2026-09-23"]
    assert set(s["source_status"]) == {"backfilled"}
    assert list(s["raw_value"]) == [10.0, 11.0, 12.0, 13.0]


def test_forward_written_date_is_skipped_not_overwritten(isolated_cache):
    cache.write_narrative_point("pytrends", "AI crypto", "2026-09-21", 99.0, source_status="fresh")
    out = bf.backfill_category("ai", "AI crypto", TODAY, lambda: FakeTrendReq(frame("AI crypto")))
    assert out.skipped_forward == 1 and out.written == 3
    s = cache.read_narrative_series("pytrends", "AI crypto").set_index("date")
    assert s.loc["2026-09-21", "raw_value"] == 99.0 and s.loc["2026-09-21", "source_status"] == "fresh"
    assert len(s) == 4


def test_rerun_replaces_backfilled_only(isolated_cache):
    bf.backfill_category("ai", "AI crypto", TODAY, lambda: FakeTrendReq(frame("AI crypto")))
    df2 = frame("AI crypto")
    df2["AI crypto"] = df2["AI crypto"] + 100
    out = bf.backfill_category("ai", "AI crypto", TODAY, lambda: FakeTrendReq(df2))
    assert out.written == 4 and out.skipped_forward == 0
    s = cache.read_narrative_series("pytrends", "AI crypto")
    assert len(s) == 4 and s["raw_value"].min() == 110.0


def test_weekly_granularity_rejected_never_stored_as_daily(isolated_cache):
    out = bf.backfill_category("ai", "AI crypto", TODAY, lambda: FakeTrendReq(frame("AI crypto", freq="W", partial_last=False)))
    assert out.status == "unavailable" and "non-daily" in out.reason
    assert cache.read_narrative_series("pytrends", "AI crypto").empty


@pytest.mark.parametrize("fake", [FakeTrendReq(exc=RuntimeError("429")), FakeTrendReq(df=pd.DataFrame())])
def test_fetch_failure_is_unavailable_and_writes_nothing(isolated_cache, fake):
    out = bf.backfill_category("ai", "AI crypto", TODAY, lambda: fake)
    assert out.status == "unavailable" and out.reason == "fetch-failed" and out.written == 0
    assert cache.read_narrative_series("pytrends", "AI crypto").empty


def test_run_uses_first_seed_keyword_per_category(isolated_cache):
    seen = []

    def factory():
        class F(FakeTrendReq):
            def build_payload(self, kw_list, timeframe):
                seen.append(kw_list[0])
                self.df = frame(kw_list[0])
        return F()

    outs = bf.run(today=TODAY, trendreq_factory=factory)
    assert [o.category_id for o in outs] == ["ai", "rwa", "l2s", "memecoins"]
    assert seen == ["AI crypto", "RWA crypto", "layer 2 crypto", "memecoin"]


def test_dry_run_writes_nothing(isolated_cache):
    out = bf.backfill_category("ai", "AI crypto", TODAY, lambda: FakeTrendReq(frame("AI crypto")), dry_run=True)
    assert out.written == 4
    assert cache.read_narrative_series("pytrends", "AI crypto").empty
