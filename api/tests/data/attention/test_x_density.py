"""W8d1 AC42 (sample definition), AC54 (read entries are the sample unit): read-sample density. Pure; no network."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from api.data.attention import x_density as xd
from api.data.attention import x_filters as xf

DAY = date(2026, 10, 20)
START = datetime(2026, 10, 20, tzinfo=timezone.utc)
END = START + timedelta(days=1)


def times(k: int, newest: datetime = END - timedelta(minutes=1), step_min: float = 10) -> list[datetime]:
    return [newest - timedelta(minutes=step_min * i) for i in range(k)]


def value(**kw):
    base = {"n_target": 40, "n_min": 20, "page_cap_hit": False, "window_start_reached": False, "canary_ok": True}
    return xd.read_sample_value(DAY, **{**base, **kw})


def outcome(**kw):
    base = {"n_target": 40, "n_min": 20, "page_cap_hit": False, "window_start_reached": False, "canary_ok": True}
    return xd.read_sample_outcome(DAY, **{**base, **kw})


def test_read_sample_density_exact_when_window_reached():
    r = value(n_read=33, counted_times=times(12), oldest_read=START - timedelta(minutes=5),
              window_start_reached=True)
    assert (r.value, r.n, r.capped, r.pagecap) == (12.0, 12, False, False)
    # Exact even when the read entries reached N on the same page (all of the day was read).
    r = value(n_read=45, counted_times=times(12), oldest_read=START - timedelta(minutes=5),
              window_start_reached=True)
    assert (r.value, r.capped) == (12.0, False)
    zero = value(n_read=3, counted_times=[], oldest_read=START - timedelta(hours=1), window_start_reached=True)
    assert zero.value == 0.0  # the zero rule (AC3) is applied later by density.finalize


def test_read_sample_density_capped_24_k_over_span():
    oldest = END - timedelta(hours=6)
    r = value(n_read=40, counted_times=times(10), oldest_read=oldest)
    # k = counted (10), span = window end minus the oldest READ tweet (6 h), not the oldest counted one.
    assert r.value == pytest.approx(24 * 10 / 6) and r.span_hours == pytest.approx(6) and r.capped
    assert not r.pagecap and r.n == 10
    # Page cap with N_min <= read < N: same formula, pagecap flag.
    r = value(n_read=25, counted_times=times(5), oldest_read=oldest, page_cap_hit=True)
    assert r.value == pytest.approx(20.0) and r.capped and r.pagecap
    # Page cap with fewer than N_min read: missing, never 0.
    assert value(n_read=19, counted_times=times(5), oldest_read=oldest, page_cap_hit=True) is None
    # Neither the window start nor N nor the page cap: missing.
    assert value(n_read=30, counted_times=times(5), oldest_read=oldest) is None


def test_span_floor_quarter_hour():
    r = value(n_read=40, counted_times=times(2, step_min=1), oldest_read=END - timedelta(minutes=3))
    assert r.span_hours == 0.25 and r.value == pytest.approx(24 * 2 / 0.25)


def test_counted_times_outside_window_ignored_and_bad_args_refused():
    r = value(n_read=40, counted_times=times(3) + [END + timedelta(minutes=1)], oldest_read=END - timedelta(hours=2))
    assert r.n == 3
    with pytest.raises(ValueError):
        value(n_read=40, counted_times=[], oldest_read=END - timedelta(hours=1), n_min=41)
    with pytest.raises(ValueError):
        value(n_read=-1, counted_times=[], oldest_read=END)


def test_summarize_uses_filters_and_read_entries():
    u = xf.XUser(1, datetime(2024, 1, 1, tzinfo=timezone.utc), 100, 100, "https://img/a.jpg", False)
    read = [xf.Tweet(i, END - timedelta(hours=1 + i), f"Solana {i}", xf.XUser(i, u.created, 100, 100, "p", False),
                     "en", ("SOL",), like=i) for i in range(5)]
    read.append(xf.Tweet(99, END - timedelta(hours=2), "rt", u, "en", ("SOL",), retweeted_id=1))
    s = xd.summarize(DAY, read, n_read=40, window_start_reached=False, page_cap_hit=False, canary_ok=True,
                     coin=xf.Coin("SOL", "Solana"), policy=xf.FilterPolicy(), n_target=40, n_min=20,
                     now=END + timedelta(hours=2))
    assert s.n_read == 40 and s.n_counted == 5 and s.exclusions["retweet"] == 1
    assert s.result.capped and s.result.span_hours == pytest.approx(5.0)
    assert s.result.value == pytest.approx(24 * 5 / 5.0)
    assert s.engagement == pytest.approx(sum(__import__("math").log1p(i) for i in range(5)))


# --- T187 review fixes (M1, M3, M10) ------------------------------------------------------------------------

def test_all_read_tweets_after_window_end_is_missing_window_not_reached():
    after = END + timedelta(minutes=30)
    assert outcome(n_read=60, counted_times=[], oldest_read=after, page_cap_hit=True) == (None, "window_not_reached")
    assert outcome(n_read=40, counted_times=[], oldest_read=after) == (None, "window_not_reached")
    assert outcome(n_read=40, counted_times=[], oldest_read=END) == (None, "window_not_reached")  # end is outside
    assert outcome(n_read=0, counted_times=[], oldest_read=None, page_cap_hit=True) == (None, "window_not_reached")
    # One second inside the window is enough to use the capped formula.
    r, why = outcome(n_read=40, counted_times=[END - timedelta(seconds=1)], oldest_read=END - timedelta(seconds=1))
    assert why is None and r.capped and r.n == 1


def test_sparse_coin_exact_count_below_n_min_when_window_reached():
    before = START - timedelta(minutes=1)
    for k in (1, 19):  # 19 = N_min - 1
        r, why = outcome(n_read=k + 1, counted_times=times(k, step_min=1), oldest_read=before, window_start_reached=True)
        assert why is None and (r.value, r.n, r.capped) == (float(k), k, False)


def test_zero_exact_needs_canary_else_missing_zero_without_canary():
    before = START - timedelta(minutes=1)
    r, why = outcome(n_read=1, counted_times=[], oldest_read=before, window_start_reached=True)
    assert why is None and r.value == 0.0
    assert outcome(n_read=1, counted_times=[], oldest_read=before, window_start_reached=True,
                   canary_ok=False) == (None, "zero_without_canary")
    assert outcome(n_read=0, counted_times=[], oldest_read=None, window_start_reached=True,
                   canary_ok=False) == (None, "zero_without_canary")
    # A nonzero exact count needs no canary.
    assert outcome(n_read=2, counted_times=times(1), oldest_read=before, window_start_reached=True,
                   canary_ok=False)[0].value == 1.0


def test_page_cap_boundary_at_n_min():
    oldest = END - timedelta(hours=4)
    r, why = outcome(n_read=20, counted_times=times(8), oldest_read=oldest, page_cap_hit=True)
    assert why is None and r.pagecap and r.value == 24 * 8 / 4
    assert outcome(n_read=19, counted_times=times(8), oldest_read=oldest, page_cap_hit=True) == (None, "short_result")
    # read_sample_value is the value part of the outcome.
    assert value(n_read=19, counted_times=times(8), oldest_read=oldest, page_cap_hit=True) is None
