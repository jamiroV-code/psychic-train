"""W8b AC3/AC4: evidence sidecar and the day commit (first write wins, completed days only). Pure; no network."""
from __future__ import annotations

import math
from dataclasses import fields
from datetime import date, datetime, timedelta, timezone

import pytest

from api.data.attention import density, store
from api.data.attention import web_evidence as ev

DAY = date(2026, 10, 20)
NOW = datetime(2026, 10, 21, 1, 30, tzinfo=timezone.utc)
SRC = "xsearch_web"


@pytest.fixture(autouse=True)
def _isolated(attention_cache):
    """Every test here writes state or evidence: keep it out of the real cache root."""
    return attention_cache


def result(value: float = 12.0) -> density.DayResult:
    n = int(value) if math.isfinite(value) and value >= 0 else 0
    return density.DayResult(value=value, n=n, span_hours=24.0, capped=False, pagecap=False)


def commit(symbol="SOL", day=DAY, res=None, *, canary_ok=True, trailing_median=None, now=NOW, method="m1",
           backfilled=False):
    return ev.commit_day(SRC, symbol, day, result() if res is None else res, canary_ok=canary_ok,
                         trailing_median=trailing_median, now=now, method=method, backfilled=backfilled)


def nothing_stored(symbol="SOL") -> bool:
    return store.read_points(SRC, symbol) == [] and ev.read_rows(SRC, symbol) == {}


def test_evidence_row_has_all_fields():
    assert commit(method="xsearch_web-a1-v1") is True
    names = {f.name for f in fields(ev.EvidenceRow)}
    assert names == {"date", "value", "n", "span_hours", "capped", "pagecap", "spike", "method", "collected_at",
                     "backfilled"}
    row = ev.read_rows(SRC, "SOL")[DAY]
    assert row.value == 12.0 and row.n == 12 and row.span_hours == 24.0 and row.method == "xsearch_web-a1-v1"
    assert row.collected_at == NOW and row.backfilled is False and row.spike is False
    assert store.read_points(SRC, "SOL") == [(DAY, 12.0)]


def test_evidence_lives_under_cache_meta(attention_cache):
    commit()
    assert ev.evidence_path(SRC, "SOL") == attention_cache / "attention" / SRC / "_meta" / "SOL.json"
    assert ev.evidence_path(SRC, "SOL").exists()


def test_failed_collection_stores_nothing():
    assert ev.commit_day(SRC, "SOL", DAY, None, canary_ok=True, trailing_median=None, now=NOW, method="m1") is False
    assert nothing_stored()


def test_rejected_zero_is_not_stored_joint_finalize_and_commit():
    """AC3 through the one storing call: a zero needs canary data and a trailing median below 5."""
    zero = density.day_value(DAY, [], n_target=40, n_min=20, window_start_reached=True)
    assert zero.value == 0
    assert commit(res=zero, canary_ok=False, trailing_median=1.0) is False and nothing_stored()
    assert commit(res=zero, canary_ok=True, trailing_median=5.0) is False and nothing_stored()
    assert commit(res=zero, canary_ok=True, trailing_median=None) is False and nothing_stored()
    assert commit(res=zero, canary_ok=True, trailing_median=2.0) is True
    assert store.read_points(SRC, "SOL") == [(DAY, 0.0)] and ev.read_rows(SRC, "SOL")[DAY].value == 0.0


def test_stored_number_comes_only_from_finalize(monkeypatch):
    monkeypatch.setattr(ev.density, "finalize", lambda *a, **k: None)
    assert commit(res=result(12)) is False and nothing_stored()
    monkeypatch.setattr(ev.density, "finalize", lambda *a, **k: 7.0)
    assert commit(res=result(12)) is True
    assert store.read_points(SRC, "SOL") == [(DAY, 7.0)] and ev.read_rows(SRC, "SOL")[DAY].value == 7.0


def test_commit_day_cannot_skip_the_zero_rule():
    with pytest.raises(TypeError):
        ev.commit_day(SRC, "SOL", DAY, result(), now=NOW, method="m1")  # no canary_ok / trailing_median
    with pytest.raises(TypeError):
        ev.commit_day(SRC, "SOL", DAY, result(), canary_ok=True, trailing_median=None, now=NOW, method="m1",
                      value=3.0)


def test_non_finite_and_negative_values_never_stored():
    for bad in (float("nan"), float("inf"), float("-inf"), -1.0):
        assert density.finalize(result(bad), canary_ok=True, trailing_median=1.0) is None
        assert commit(res=result(bad), canary_ok=True, trailing_median=1.0) is False and nothing_stored()


def test_second_collection_does_not_change_day():
    commit(res=result(12))
    later = NOW + timedelta(days=2)
    assert commit(res=result(99), now=later, method="m2", backfilled=True) is False
    assert store.read_points(SRC, "SOL") == [(DAY, 12.0)]
    row = ev.read_rows(SRC, "SOL")[DAY]
    assert row.n == 12 and row.method == "m1" and row.collected_at == NOW


def test_evidence_is_written_before_the_value_and_repairs_a_missing_value(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError

    # A scoped patch: undoing the whole `monkeypatch` would also undo the fixture's cache redirect.
    with monkeypatch.context() as m:
        m.setattr(ev.store, "write_series", boom)
        with pytest.raises(RuntimeError):
            commit(res=result(12))
    assert ev.read_rows(SRC, "SOL")[DAY].value == 12.0 and store.read_points(SRC, "SOL") == []
    assert commit(res=result(99), method="m2", now=NOW + timedelta(hours=3)) is True
    assert store.read_points(SRC, "SOL") == [(DAY, 12.0)]      # the frozen evidence value, not the new one
    row = ev.read_rows(SRC, "SOL")[DAY]
    assert row.n == 12 and row.method == "m1" and row.collected_at == NOW
    assert commit(res=result(99)) is False


def test_today_never_stored():
    assert commit(day=NOW.date()) is False
    assert commit(now=datetime(2026, 10, 20, 23, 59, tzinfo=timezone.utc)) is False
    assert nothing_stored()


def test_backfilled_and_spike_flags_kept():
    commit("ETH", DAY - timedelta(days=3), result(500), backfilled=True, trailing_median=20.0)
    row = ev.read_rows(SRC, "ETH")[DAY - timedelta(days=3)]
    assert row.backfilled is True and row.spike is True


def test_bad_symbol_rejected():
    with pytest.raises(ValueError):
        ev.evidence_path(SRC, "../x")
    with pytest.raises(ValueError):
        ev.evidence_path("../src", "SOL")
