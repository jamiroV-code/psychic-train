"""Trends source wraps pytrends_adapter; fixtures only, no live call."""
from datetime import timedelta

import pytest

from api.data import pytrends_adapter
from api.data.attention import registry, store, trends
from api.tests import trends_fixtures as fx

from .conftest import TODAY

Y = (TODAY - timedelta(days=1)).isoformat()


def _fake(value=42.0, as_of=Y, status="ok"):
    calls = []

    def f(keyword):
        calls.append(keyword)
        return pytrends_adapter.TrendResult(keyword=keyword, value=value, as_of=as_of, status=status)
    f.calls = calls
    return f


def test_ok_single_completed_point():
    f = _fake()
    s = trends.fetch_series("btc", "bitcoin", fetch=f, today=TODAY)
    assert f.calls == ["bitcoin"] and s.source == "trends" and s.symbol == "BTC"
    assert s.state == "insufficient-history" and s.points == [(TODAY - timedelta(days=1), 42.0)]


def test_partial_current_day_row_dropped():
    s = trends.fetch_series("BTC", "bitcoin", fetch=_fake(as_of=TODAY.isoformat()), today=TODAY)
    assert s.points == [] and s.state == "unavailable"


def test_empty_and_unavailable():
    s = trends.fetch_series("BTC", "bitcoin", fetch=_fake(None, None, "unavailable"), today=TODAY)
    assert s.state == "unavailable" and s.points == []


def test_presumed_dead_and_rate_limit_error_never_raise():
    s = trends.fetch_series("BTC", "bitcoin", fetch=_fake(None, Y, "presumed-dead"), today=TODAY)
    assert s.state == "unavailable" and "presumed-dead" in s.reason

    def boom(keyword):
        raise RuntimeError("429 key=secret")
    s = trends.fetch_series("BTC", "bitcoin", fetch=boom, today=TODAY)
    assert s.state == "unavailable" and "secret" not in s.reason and "RuntimeError" in s.reason


def test_no_keyword():
    f = _fake()
    s = trends.fetch_series("BTC", "", fetch=f, today=TODAY)
    assert s.state == "unavailable" and f.calls == []


def test_not_probed_and_no_probe_row(tmp_path):
    assert "trends" in registry.FETCHERS
    probe = tmp_path / "probe.json"
    probe.write_text("{}")
    assert registry.read_series("trends", "BTC", today=TODAY, probe_path=probe).state == "not-probed"


# --- T100b: one coin per request (fetch_alone), interest rule, name-risk list. Fake TrendReq only. ---

def _alone(values=None, days=100, term="Aave", end=None, partial_last=False):
    end = end or fx.TODAY - timedelta(days=1)
    return fx.daily_frame([term], days=days, end=end, values={term: values} if values is not None else None,
                          partial_last=partial_last)


def _fetch(*frames, term="Aave"):
    client = fx.FakeTrendReq(frames=list(frames))
    return trends.fetch_alone("aave", term, client, today=fx.TODAY), client


def test_fetch_alone_builds_single_term_payload():
    s, client = _fetch(_alone())
    assert client.payloads == [(["Aave"], "2026-07-13 2026-10-20")]
    assert trends.explicit_timeframe(fx.TODAY) == "2026-07-13 2026-10-20"  # 100 complete days, ends yesterday
    assert s.source == "trends" and s.symbol == "AAVE" and s.state == "ok"


def test_fetch_alone_drops_partial_and_today():
    s, _ = _fetch(fx.frame_with_today(["Aave"], days=101))
    assert len(s.points) == 100 and all(d < fx.TODAY for d, _ in s.points)
    s, _ = _fetch(_alone(days=101, partial_last=True))
    assert len(s.points) == 100 and s.points[-1][0] == fx.TODAY - timedelta(days=2)
    s, _ = _fetch(_alone(days=102, end=fx.TODAY + timedelta(days=1)))  # today and tomorrow not flagged partial
    assert len(s.points) == 100 and s.points[-1][0] == fx.TODAY - timedelta(days=1)


def test_fetch_alone_rejects_non_daily_step():
    s, _ = _fetch(fx.weekly_frame(["Aave"], weeks=20))
    assert (s.state, s.reason, s.points) == ("unavailable", "non-daily", [])
    frame = _alone(days=101)
    s, _ = _fetch(frame.drop(frame.index[50]))  # one missing day inside the range
    assert (s.state, s.reason) == ("unavailable", "non-daily")


def test_fetch_alone_missing_column_unavailable():
    s, _ = _fetch(_alone(term="Other"))
    assert (s.state, s.reason, s.points) == ("unavailable", "missing-column", [])
    s, _ = _fetch(_alone().iloc[0:0])
    assert (s.state, s.reason) == ("unavailable", "empty response")


def test_fetch_alone_under_90_days_insufficient_history():
    s, _ = _fetch(_alone(days=89))
    assert s.state == "insufficient-history" and s.points == [] and s.reason == "89 days"


def test_fetch_alone_100_rows_ok():
    vals = [(7 * i) % 100 + 1 for i in range(100)]
    s, _ = _fetch(_alone(vals))
    assert s.state == "ok" and [v for _, v in s.points] == [float(v) for v in vals]
    assert all(isinstance(v, float) for _, v in s.points)
    assert [d for d, _ in s.points] == [fx.TODAY - timedelta(days=100 - i) for i in range(100)]


def test_all_zero_series_too_little_interest():
    s, _ = _fetch(_alone(0))
    assert (s.state, s.reason, s.points) == ("unavailable", trends.TOO_LITTLE_INTEREST, [])


def test_low_median_too_little_interest():
    vals = [2] * 99 + [100]  # median 2 < TRENDS_MIN_MEDIAN 3, no zero day
    s, _ = _fetch(_alone(vals))
    assert (s.state, s.reason) == ("unavailable", trends.TOO_LITTLE_INTEREST)
    s, _ = _fetch(_alone([3] * 99 + [100]))
    assert s.state == "ok"
    assert trends.TRENDS_MIN_MEDIAN == 3 and trends.TRENDS_MAX_ZERO_DAY_PCT == 40


def test_many_zero_days_too_little_interest():
    s, _ = _fetch(_alone([0] * 40 + [50] * 60))  # 40 % zero days: at the limit
    assert (s.state, s.reason) == ("unavailable", trends.TOO_LITTLE_INTEREST)
    s, _ = _fetch(_alone([0] * 39 + [50] * 61))
    assert s.state == "ok"


def test_interest_rule_never_writes_zero(isolated_cache):
    s, _ = _fetch(_alone([0] * 98 + [1, 100]))
    assert s.points == [] and s.state == "unavailable"
    assert store.write_series(s, today=fx.TODAY, mode="replace-series") == 0
    assert not store.store_path("trends", "AAVE").exists()


def test_percent_change_invariant_to_series_scale():
    from api.analytics.attention import discovery
    end = fx.TODAY - timedelta(days=1)
    pts = [(end - timedelta(days=99 - i), float((37 * i) % 89 + 5 + (i > 92) * 40)) for i in range(100)]
    for window in (7, 30, 90):
        base = discovery._source_change(pts, end, 7, window, 3)
        assert base is not None
        for k in (0.5, 3.7):
            scaled = [(d, v * k) for d, v in pts]
            assert discovery._source_change(scaled, end, 7, window, 3) == pytest.approx(base, abs=1e-9)


def test_fetch_alone_exception_reports_class_only():
    s, _ = _fetch(RuntimeError("boom " + fx.SECRET))
    assert (s.state, s.reason) == ("unavailable", "fetch-failed: RuntimeError")
    s, _ = _fetch(fx.forbidden())
    assert s.reason == "fetch-failed: ResponseError(HTTP 403)" and fx.SECRET not in s.reason


def test_http_429_reason_has_status():
    s, _ = _fetch(fx.too_many())
    assert s.state == "capped" and s.reason == "rate-limited: TooManyRequestsError(HTTP 429)" and s.points == []
    assert all(f not in s.reason for f in fx.FORBIDDEN_IN_OUTPUT)


def test_name_risk_symbols_match_t125_list():
    assert trends.NAME_RISK_SYMBOLS == frozenset(
        {"TRX", "ONDO", "MORPHO", "ICP", "SHIB", "PEPE", "BNB", "CRO", "HBAR", "LINK", "APT", "SOL"})
