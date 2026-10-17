"""Trends source wraps pytrends_adapter; fixtures only, no live call."""
from datetime import timedelta

from api.data import pytrends_adapter
from api.data.attention import registry, trends
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
