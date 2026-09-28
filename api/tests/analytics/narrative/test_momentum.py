"""Narrative-v2 RFC-4 (ADR-4): momentum maths, basis fallback, insufficiency."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from api.analytics.narrative import momentum
from api.data import cache

D0 = date(2026, 9, 1)


def _pts(values: list[float]) -> list[tuple[str, float]]:
    return [((D0 + timedelta(days=i)).isoformat(), v) for i, v in enumerate(values)]


def test_momentum_golden_rising_then_flattening():
    # days 0..14: rises 0.0 -> 0.7 over week one, then only 0.7 -> 0.8 in week two.
    values = [0.1 * i for i in range(8)] + [0.7 + (0.1 / 7) * i for i in range(1, 8)]
    m = momentum.momentum_from_points(_pts(values))
    assert m is not None
    assert (m.as_of, m.baseline_date, m.prior_baseline_date) == ("2026-09-15", "2026-09-08", "2026-09-01")
    # hand-computed: change = 0.8 - 0.7 = 0.1; prev = 0.7 - 0.0 = 0.7; accel = 0.1 - 0.7 = -0.6
    assert m.change == pytest.approx(0.1)
    assert m.prev_change == pytest.approx(0.7)
    assert m.acceleration == pytest.approx(-0.6)
    assert momentum.classify(m.change, m.acceleration) == ("up", "decelerating")


def test_momentum_golden_falling_then_reversing():
    # 0.9 at day 0, 0.3 at day 7 (falling fast), 0.2 at day 14 (falling slowly).
    values = [0.9] + [0.5] * 6 + [0.3] + [0.25] * 6 + [0.2]
    m = momentum.momentum_from_points(_pts(values))
    assert m is not None
    # hand-computed: change = 0.2 - 0.3 = -0.1; prev = 0.3 - 0.9 = -0.6; accel = -0.1 - -0.6 = +0.5
    assert m.change == pytest.approx(-0.1)
    assert m.prev_change == pytest.approx(-0.6)
    assert m.acceleration == pytest.approx(0.5)
    assert momentum.classify(m.change, m.acceleration) == ("down", "decelerating")
    # and a fall that is speeding up
    assert momentum.classify(-0.3, -0.1) == ("down", "accelerating")
    assert momentum.classify(0.3, 0.1) == ("up", "accelerating")


def test_window_tolerance_uses_latest_point_7_to_9_days_back():
    pts = [("2026-09-01", 0.1), ("2026-09-06", 0.4), ("2026-09-08", 0.5), ("2026-09-15", 0.6)]
    # base1 in [09-06, 09-08] -> 09-08; base2 in [08-30, 09-01] -> 09-01
    m = momentum.momentum_from_points(pts)
    assert (m.baseline_date, m.prior_baseline_date) == ("2026-09-08", "2026-09-01")


def test_ranking_is_cross_sectional_and_insufficient_last():
    mk = lambda cid, ch, st="ok": momentum.MomentumEntry(  # noqa: E731
        cid, cid, "composite" if st == "ok" else "insufficient", None, None, ch, None, None, None, None,
        None, None, st, None)
    ranked = momentum.rank_entries([mk("a", 0.1), mk("z", None, "insufficient"), mk("b", 0.3), mk("c", 0.1)])
    assert [(e.category_id, e.rank) for e in ranked] == [("b", 1), ("a", 2), ("c", 2), ("z", None)]


# --- through the real cache boundary --------------------------------------


def _write_days(source, key, values, today):
    for i, v in enumerate(values):
        d = today - timedelta(days=len(values) - 1 - i)
        cache.write_narrative_point(source, key, d.isoformat(), float(v))


@pytest.fixture
def one_narrative(monkeypatch):
    from api.analytics.narrative import narrative_config
    monkeypatch.setattr(narrative_config, "load_narratives",
                        lambda *a, **k: [{"id": "ai", "label": "AI", "keywords": ["AI crypto", "AI agents"]}])


def test_momentum_basis_uses_blended_when_mature(isolated_cache, one_narrative):
    today = date.today()
    _write_days("pytrends-blended", "ai", [10 + i for i in range(15)], today)
    [e] = momentum.build_momentum(today).entries
    assert e.momentum_basis == "pytrends-blended" and e.status == "ok" and e.rank == 1
    assert e.direction == "up" and e.trend == "steady"


def test_momentum_basis_falls_back_to_composite_when_pytrends_insufficient(isolated_cache, one_narrative):
    today = date.today()
    _write_days("pytrends-blended", "ai", [10, 20, 30], today)  # provisional (<5 points)
    _write_days("pytrends", "AI crypto", [i for i in range(15)], today)
    _write_days("reddit", "AI crypto", [i for i in range(15)], today)
    [e] = momentum.build_momentum(today).entries
    assert e.momentum_basis == "composite"
    assert e.status == "ok" and e.change is not None and e.reason is None


def test_momentum_insufficient_history_explicit_state(isolated_cache, one_narrative):
    today = date.today()
    # mature blended (6 points) but only 6 days of history: windows unresolvable
    _write_days("pytrends-blended", "ai", [1, 2, 3, 4, 5, 6], today)
    [e] = momentum.build_momentum(today).entries
    assert e.status == "insufficient" and e.momentum_basis == "insufficient"
    assert e.change is None and e.acceleration is None and e.rank is None and e.direction is None
    assert e.reason.startswith("not enough history for momentum yet")


def test_momentum_no_data_at_all_is_insufficient_not_zero(isolated_cache, one_narrative):
    [e] = momentum.build_momentum(date.today()).entries
    assert e.status == "insufficient" and e.change is None
    assert e.reason == momentum.REASON_NO_MATURE_BASIS
