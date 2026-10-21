"""W8b AC3/AC4: evidence sidecar and the day commit (first write wins, completed days only). Pure; no network."""
from __future__ import annotations

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
    return density.DayResult(value=value, n=int(value), span_hours=24.0, capped=False, pagecap=False)


def test_evidence_row_has_all_fields(attention_cache):
    assert ev.commit_day(SRC, "SOL", DAY, result(), now=NOW, method="xsearch_web-a1-v1") is True
    names = {f.name for f in fields(ev.EvidenceRow)}
    assert names == {"date", "n", "span_hours", "capped", "pagecap", "spike", "method", "collected_at", "backfilled"}
    row = ev.read_rows(SRC, "SOL")[DAY]
    assert row.n == 12 and row.span_hours == 24.0 and row.method == "xsearch_web-a1-v1"
    assert row.collected_at == NOW and row.backfilled is False and row.spike is False
    assert store.read_points(SRC, "SOL") == [(DAY, 12.0)]


def test_evidence_lives_under_cache_meta(attention_cache):
    ev.commit_day(SRC, "SOL", DAY, result(), now=NOW, method="m1")
    assert ev.evidence_path(SRC, "SOL") == attention_cache / "attention" / SRC / "_meta" / "SOL.json"
    assert ev.evidence_path(SRC, "SOL").exists()


def test_failed_collection_stores_nothing(attention_cache):
    assert ev.commit_day(SRC, "SOL", DAY, None, now=NOW, method="m1") is False
    assert store.read_points(SRC, "SOL") == []
    assert ev.read_rows(SRC, "SOL") == {}


def test_second_collection_does_not_change_day(attention_cache):
    ev.commit_day(SRC, "SOL", DAY, result(12), now=NOW, method="m1")
    later = NOW + timedelta(days=2)
    assert ev.commit_day(SRC, "SOL", DAY, result(99), now=later, method="m2", backfilled=True) is False
    assert store.read_points(SRC, "SOL") == [(DAY, 12.0)]
    row = ev.read_rows(SRC, "SOL")[DAY]
    assert row.n == 12 and row.method == "m1" and row.collected_at == NOW


def test_today_never_stored(attention_cache):
    today = NOW.date()
    assert ev.commit_day(SRC, "SOL", today, result(), now=NOW, method="m1") is False
    before_end = datetime(2026, 10, 20, 23, 59, tzinfo=timezone.utc)
    assert ev.commit_day(SRC, "SOL", DAY, result(), now=before_end, method="m1") is False
    assert store.read_points(SRC, "SOL") == [] and ev.read_rows(SRC, "SOL") == {}


def test_backfilled_and_spike_flags_kept(attention_cache):
    ev.commit_day(SRC, "ETH", DAY - timedelta(days=3), result(500), now=NOW, method="m1", backfilled=True,
                  trailing_median=20.0)
    row = ev.read_rows(SRC, "ETH")[DAY - timedelta(days=3)]
    assert row.backfilled is True and row.spike is True


def test_bad_symbol_rejected(attention_cache):
    with pytest.raises(ValueError):
        ev.evidence_path(SRC, "../x")
    with pytest.raises(ValueError):
        ev.evidence_path("../src", "SOL")
