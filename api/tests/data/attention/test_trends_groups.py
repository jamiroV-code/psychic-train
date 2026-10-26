"""T196: pure term-group metrics. Synthetic series only; no network, no store."""
from __future__ import annotations

import ast
import math
from datetime import date, timedelta
from pathlib import Path

import pytest

from api.data.attention import trends
from api.data.attention import trends_groups as g
from api.tests.trends_fixtures import TODAY, daily_frame

N = trends.TRENDS_RANGE_DAYS
YESTERDAY = TODAY - timedelta(days=1)
DATES = [YESTERDAY - timedelta(days=N - 1 - i) for i in range(N)]


def flat(v: float, n: int = N) -> list[float]:
    return [float(v)] * n


def rise(base: float, last: float, n: int = N) -> list[float]:
    """`base` every day, then the last 7 days at `last`."""
    return [float(base)] * (n - 7) + [float(last)] * 7


def wave(n: int = N, period: int = 20, amp: float = 5, mid: float = 20, phase: float = 0) -> list[float]:
    return [mid + amp * math.sin(2 * math.pi * (i + phase) / period) for i in range(n)]


# --- group series, per-term stats, shares ---

def test_group_stats_count_distinct_values():
    assert g.analyze({"a": [1.0, 2.0, 2.0] * 33 + [3.0]}, DATES).group.distinct == 3


def test_group_series_sums_and_keeps_each_term():
    grp = g.group_series({"a": [1, 2, 3], "b": [0, 5, 1]})
    assert grp.total == [1, 7, 4]
    assert grp.terms == {"a": [1, 2, 3], "b": [0, 5, 1]}
    with pytest.raises(ValueError):
        g.group_series({"a": [1, 2], "b": [1]})
    with pytest.raises(ValueError):
        g.group_series({})


def test_term_stats_and_shares():
    st = g.term_stats([0, 0, 4, 6, 10])
    assert st.median == 4 and st.zero_pct == 40.0
    grp = g.group_series({"a": [1, 1, 2], "b": [3, 3, 6]})
    assert g.shares(grp) == {"a": 0.25, "b": 0.75}
    assert g.shares(g.group_series({"a": [0, 0], "b": [0, 0]})) == {"a": None, "b": None}


# --- usable verdict reuses the daily rule ---

def test_verdict_uses_the_daily_rule():
    assert g.analyze({"a": flat(10)}, DATES).verdict == "ok"
    assert g.analyze({"a": flat(2)}, DATES).verdict == trends.TOO_LITTLE_INTEREST
    zero_heavy = [0.0] * 45 + [20.0] * 55  # median 20 but 45% zero days
    assert g.analyze({"a": zero_heavy}, DATES).verdict == trends.TOO_LITTLE_INTEREST
    surge = [0.0] * 50 + [1.0] * 43 + [10.0] * 7
    assert g.analyze({"a": surge}, DATES).verdict == trends.QUIET_THEN_SURGE
    # the group (sum) can be usable while each term alone is not
    m = g.analyze({"a": flat(2), "b": flat(2)}, DATES)
    assert m.verdict == "ok" and m.group.median == 4


# --- rising measure ---

def test_rising_ratio_and_days_above_baseline():
    r = g.rising(rise(10, 20))
    assert r.ratio == 2.0 and r.days_above == 7
    r = g.rising(flat(10))
    assert r.ratio == 1.0 and r.days_above == 0
    r = g.rising(flat(0))
    assert r.ratio is None and r.days_above is None and "baseline median 0" in r.reason
    r = g.rising(flat(10, n=30))
    assert r.ratio is None and "35" in r.reason


def test_one_day_spike_is_not_a_sustained_rise():
    spike = flat(10)
    spike[-1] = 100.0
    m = g.analyze({"a": spike}, DATES)
    assert m.rising.days_above == 1 and m.rising.ratio == 1.0
    assert m.clean is False
    sustained = g.analyze({"a": rise(10, 13)}, DATES)
    assert sustained.rising.days_above == 7 and sustained.rising.ratio == 1.3
    assert sustained.clean is True


# --- one-term spike ---

def test_dominant_but_steady_term_is_not_a_spike():
    # T201: a term that is most of the searches and carries the same share of the rise is not flagged
    m = g.analyze({"a": rise(90, 99), "b": rise(10, 11)}, DATES)
    assert m.spike_share == pytest.approx(0.9) and m.spike_base_share == pytest.approx(0.9) and m.spike is False
    near = g.analyze({"a": rise(65, 69), "b": rise(35, 36)}, DATES)   # 80% of the rise, 65% of the baseline
    assert near.spike_share == pytest.approx(0.8) and near.spike is False


def test_term_that_suddenly_takes_over_is_a_spike():
    m = g.analyze({"a": rise(10, 40), "b": rise(90, 91)}, DATES)
    assert m.spike_base_share == pytest.approx(0.1) and m.spike_share > 0.95 and m.spike is True
    assert any("one-term spike" in r for r in m.reasons) and m.clean is False
    assert g.SPIKE_SHARE == 0.8 and g.SPIKE_TAKEOVER == 0.2


def test_one_term_dominance_flags_spike():
    m = g.analyze({"a": rise(10, 30), "b": rise(10, 11)}, DATES)
    assert m.spike_share == pytest.approx(20 / 21)
    assert m.spike is True and m.clean is False
    assert any("one-term spike" in r for r in m.reasons)
    even = g.analyze({"a": rise(10, 15), "b": rise(10, 15)}, DATES)
    assert even.spike_share == 0.5 and even.spike is False


def test_spike_boundary_and_falling_term():
    # T201: the share of the rise must be >= SPIKE_SHARE (was >) and >= the baseline share + SPIKE_TAKEOVER
    at = g.analyze({"a": rise(10, 14), "b": rise(10, 11)}, DATES)   # increases 28 and 7: exactly 80%, base 50%
    assert at.spike_share == pytest.approx(0.8) and at.spike_base_share == pytest.approx(0.5) and at.spike is True
    below = g.analyze({"a": rise(10, 13), "b": rise(10, 11)}, DATES)   # 21 of 28: 75%
    assert below.spike_share == pytest.approx(0.75) and below.spike is False
    # a falling term adds no increase (floored at 0), so the rising term carries all of it
    m = g.analyze({"a": rise(10, 15), "b": rise(10, 5)}, DATES)
    assert m.spike_share == 1.0 and m.spike is True


def test_spike_share_missing_without_increase_and_single_term_not_flagged():
    m = g.analyze({"a": flat(10), "b": flat(10)}, DATES)
    assert m.spike_share is None and m.spike is False
    one = g.analyze({"a": rise(10, 20)}, DATES)
    assert one.spike_share is None and one.spike is False and "one term" in one.spike_reason


# --- correlations ---

def test_correlated_vs_unrelated_terms():
    a = wave()
    b = [2 * v + 1 for v in wave()]           # same shape: r = 1
    c = wave(phase=10)                         # opposite phase: r = -1
    m = g.analyze({"a": a, "b": b, "c": c}, DATES)
    assert m.best_term == "b"                  # largest share of the group total
    assert m.correlations["a"] == pytest.approx(1.0)
    assert m.correlations["c"] == pytest.approx(-1.0)
    assert m.moves_alone == ["c"]
    assert "b" not in m.correlations


def test_uncorrelated_term_moves_alone():
    m = g.analyze({"a": wave(mid=30), "q": wave(phase=5)}, DATES)   # a quarter period apart: about 0
    assert -g.MOVES_ALONE_CORR < m.correlations["q"] < g.MOVES_ALONE_CORR
    assert m.moves_alone == ["q"]


def test_correlation_missing_for_flat_series():
    m = g.analyze({"a": wave(mid=30), "b": flat(5)}, DATES)
    assert m.correlations == {"b": None} and m.moves_alone == []
    assert g.pearson([1, 2, 3], [5, 5, 5]) is None
    assert g.pearson([1], [1]) is None
    assert g.pearson([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)


def test_smooth_is_trailing_seven_day_mean():
    assert g.smooth(list(range(10))) == [3.0, 4.0, 5.0, 6.0]
    assert g.smooth([1, 2]) == []


# --- identity vs stored volume ---

def _volume(values, dates=DATES):
    return list(zip(dates, values))


def test_identity_tracks_volume():
    vals = wave(mid=30)
    vol = _volume([math.expm1(v) for v in vals])  # log1p(volume) is the same wave, shifted by the smoothing
    smoothed_vol = _volume([math.expm1(v) for v in [0.0] * 6 + g.smooth(vals)])
    m = g.analyze({"a": vals}, DATES, smoothed_vol)
    assert m.identity.days == N - 6 and m.identity.corr == pytest.approx(1.0)
    m = g.analyze({"a": vals}, DATES, vol)
    assert m.identity.corr is not None and m.identity.days == N - 6


def test_identity_short_overlap_is_na_and_never_blocks():
    vals = rise(10, 13)
    short = _volume([100.0] * 30, DATES[-30:])
    m = g.analyze({"a": vals}, DATES, short)
    assert m.identity.corr is None and "no stored volume" in m.identity.reason and "need 60" in m.identity.reason
    assert m.clean is True
    none = g.analyze({"a": vals}, DATES, None)
    assert none.identity.corr is None and none.identity.reason == "n/a: no stored volume"


def test_identity_low_correlation_blocks_clean_rising():
    vals = [v + (3 if i >= N - 7 else 0) for i, v in enumerate(wave(mid=20, amp=1))]
    anti = _volume([math.expm1(40 - v) for v in vals])
    m = g.analyze({"a": vals}, DATES, anti)
    assert m.identity.corr is not None and m.identity.corr < g.IDENTITY_MIN_CORR
    assert m.clean is False and any("volume" in r for r in m.reasons)


# --- clean rising verdict ---

def test_clean_rising_needs_every_condition():
    at_bound = g.analyze({"a": rise(10, 11)}, DATES)                      # ratio 11/10 = 1.10 holds
    assert at_bound.rising.ratio == pytest.approx(1.1) and at_bound.clean is True
    low = g.analyze({"a": rise(2, 2.1)}, DATES)
    assert low.verdict != "ok" and low.clean is False and any("not usable" in r for r in low.reasons)
    four = flat(10)
    four[-4:] = [14.0] * 4
    m = g.analyze({"a": four}, DATES)
    assert m.rising.days_above == 4 and m.rising.ratio == 1.4 and m.clean is True
    three = flat(10)
    three[-3:] = [14.0] * 3
    m = g.analyze({"a": three}, DATES)
    assert m.rising.days_above == 3 and m.clean is False


def test_clean_rising_at_ratio_boundary():
    vals = flat(100)
    vals[-7:] = [110.0] * 7
    m = g.analyze({"a": [v / 10 for v in vals]}, DATES)
    assert m.rising.ratio == pytest.approx(1.1) and m.clean is (m.rising.ratio >= g.MIN_RISE_RATIO)
    vals[-7:] = [109.0] * 7
    assert g.analyze({"a": [v / 10 for v in vals]}, DATES).clean is False


def test_constants_are_the_envelope_placeholders():
    assert (g.MAX_TERMS, g.SMOOTH_DAYS, g.RECENT_DAYS, g.BASELINE_DAYS) == (5, 7, 7, 28)
    assert (g.MIN_RISE_RATIO, g.MIN_DAYS_ABOVE, g.SPIKE_SHARE) == (1.10, 4, 0.80)
    assert (g.MOVES_ALONE_CORR, g.IDENTITY_MIN_DAYS, g.IDENTITY_MIN_CORR) == (0.2, 60, 0.2)


# --- fail-closed frame check (same rules as fetch_alone) ---

def _frame(terms, **kw):
    kw.setdefault("days", N)
    return daily_frame(terms, **kw)


def test_frame_check_accepts_a_good_frame():
    series, dates, reason = g.check_group_frame(_frame(["a", "b"]), ["a", "b"], TODAY)
    assert reason == "" and dates == DATES and set(series) == {"a", "b"} and len(series["a"]) == N
    # a partial row for today is dropped, as in fetch_alone
    series, dates, reason = g.check_group_frame(_frame(["a"], days=N + 1, partial_last=True, end=TODAY), ["a"], TODAY)
    assert reason == "" and dates == DATES


@pytest.mark.parametrize("frame,reason", [
    (None, "empty response"),
    (_frame(["a"]), "missing-column"),
    (_frame(["a", "b"], days=90), "rows"),
    (_frame(["a", "b"], days=N, end=YESTERDAY - timedelta(days=1)), trends.NOT_CURRENT),
    (_frame(["a", "b"], days=N, end=TODAY), trends.OUT_OF_RANGE),
    (_frame(["a", "b"], partial_last=True), trends.NOT_CURRENT),
    (_frame(["a", "b"], values={"a": [101] * N}), "bad-value"),
    (_frame(["a", "b"], values={"a": [float("nan")] + [5] * (N - 1)}), "gap"),
    (_frame(["a", "b"], values={"a": [True] * N}), "bad-value"),
    (_frame(["a", "b"], values={"a": ["x"] * N}), "parse-failed: TypeError"),
])
def test_frame_check_fails_closed(frame, reason):
    series, dates, got = g.check_group_frame(frame, ["a", "b"], TODAY)
    assert series is None and dates == [] and got.startswith(reason)


def test_frame_check_rejects_weekly_frame():
    from api.tests.trends_fixtures import weekly_frame
    assert g.check_group_frame(weekly_frame(["a"]), ["a"], TODAY)[2] == "non-daily"


def test_frame_check_rejects_a_frame_starting_before_the_range():
    frame = _frame(["a"], days=N + 1)
    assert g.check_group_frame(frame, ["a"], TODAY)[2].startswith(trends.OUT_OF_RANGE)


# --- ranking ---

def test_rank_usable_then_clean_then_median():
    usable_flat = g.analyze({"a": flat(50)}, DATES)
    clean_low = g.analyze({"a": rise(5, 8)}, DATES)
    unusable = g.analyze({"a": flat(1)}, DATES)
    ranked = sorted([unusable, usable_flat, clean_low], key=g.rank_key)
    assert ranked == [clean_low, usable_flat, unusable]


def test_rank_never_compares_medians_across_groups():
    # T201: each group is its own request on its own 0-100 scale; a higher median is never a reason to rank first
    zeros_high = g.analyze({"a": [0.0] * 10 + [100.0] * (N - 10)}, DATES)   # median 100, 10% zero days
    low_steady = g.analyze({"a": flat(5)}, DATES)   # median 5, no zero day
    assert zeros_high.verdict == low_steady.verdict == "ok" and not zeros_high.clean and not low_steady.clean
    assert sorted([zeros_high, low_steady], key=g.rank_key) == [low_steady, zeros_high]
    varied = g.analyze({"a": wave(mid=10)}, DATES)
    assert varied.group.distinct > low_steady.group.distinct == 1
    assert min([g.analyze({"a": flat(90)}, DATES), varied], key=g.rank_key) is varied


def test_rank_values_order_and_identity_last():
    rv = g.rank_values
    assert rv("ok", True, 50, 1, None) < rv("ok", False, 0, 99, 0.9)
    assert rv("ok", False, 50, 1, None) < rv("too-little-interest", True, 0, 99, 0.9)
    assert rv("ok", False, 10, 1, None) < rv("ok", False, 20, 99, 0.9)
    assert rv("ok", False, 10, 9, None) < rv("ok", False, 10, 8, 0.9)
    assert rv("ok", False, 10, 9, 0.5) < rv("ok", False, 10, 9, 0.1) < rv("ok", False, 10, 9, None)


def test_metrics_record_is_small_and_json_ready():
    import json
    m = g.analyze({"a": rise(10, 14), "b": rise(10, 11)}, DATES)
    rec = g.metrics_record(m)
    json.dumps(rec, allow_nan=False)
    assert rec["verdict"] == "ok" and rec["clean"] is False and rec["spike"] is True
    assert rec["distinct"] == m.group.distinct and rec["zero_pct"] == 0 and rec["median"] == m.group.median
    assert set(rec["shares"]) == {"a", "b"} and rec["identity_corr"] is None
    assert not any(isinstance(v, list) and len(v) > 10 for v in rec.values())   # no series stored


# --- purity ---

def test_module_has_no_network_import():
    tree = ast.parse(Path(g.__file__).read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
    banned = ("pytrends", "requests", "httpx", "urllib", "socket", "http", "aiohttp", "pandas", "store", "cache")
    assert not [n for n in names for b in banned if b in n.split(".")], names


def test_dates_cover_100_days():
    assert DATES[-1] == YESTERDAY and len(DATES) == N and isinstance(DATES[0], date)


def test_spike_from_an_all_zero_baseline_is_a_takeover():
    m = g.analyze({"a": rise(0, 10), "b": rise(0, 1)}, DATES)
    assert m.spike_base_share == 0.0 and m.spike is True
