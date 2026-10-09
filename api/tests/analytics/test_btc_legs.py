"""T38 / S7: the BTC leg chart (C7) and the D-14 estimate.

Most tests build `LegInputs` by hand, so the boundaries, confirmations and
BTC bars are exactly the ones the assertion is about; the composite builders
and the exchange are never reached.
"""
from __future__ import annotations

import re
import typing

import numpy as np
import pandas as pd
import pytest

from api.analytics.regime import btc_legs, leg_boundary
from api.analytics.regime.leg_boundary import BoundaryCandidate, BoundaryConfirmation, LegInputs
from api.models.regime import AgeLabel, CompositeChangeLabel

NOW = pd.Timestamp("2026-10-09T12:00:00Z")
_ZFORM = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _ts(day: str) -> pd.Timestamp:
    return pd.Timestamp(day, tz="UTC")


def _btc(start: str = "2026-01-01", end: str = "2026-10-08") -> object:
    stamps = pd.date_range(start, end, freq="D", tz="UTC")
    df = pd.DataFrame({"timestamp": stamps, "close": np.linspace(100.0, 200.0, len(stamps))})

    class _Ohlcv:  # the legs path reads only `.df`
        pass

    out = _Ohlcv()
    out.df = df
    return out


class _Composite:
    def __init__(self, series: pd.DataFrame | None, available: bool = True):
        self.series = series if series is not None else pd.DataFrame(columns=["date", "composite"])
        self.available = available


def _composite_series(values, start: str = "2026-01-01") -> pd.DataFrame:
    return pd.DataFrame(
        {"date": pd.date_range(start, periods=len(values), freq="D", tz="UTC"), "composite": list(values)}
    )


def _inputs(candidates, confirmed_days, composite=None, btc=None) -> LegInputs:
    """`candidates` = [(day, z)]; `confirmed_days` = the candidate days that are confirmed."""
    cands = [BoundaryCandidate(date=_ts(d), z_score=z) for d, z in candidates]
    confs = [
        BoundaryConfirmation(
            candidate_date=c.date,
            confirmed=c.date.date().isoformat() in confirmed_days,
            confirmed_date=(c.date + pd.Timedelta(days=2)) if c.date.date().isoformat() in confirmed_days else None,
        )
        for c in cands
    ]
    return LegInputs(
        variant="reduced",
        composite=composite or _Composite(_composite_series(np.linspace(0, 1, 60))),
        candidates=cands,
        confirmations=confs,
        btc=btc or _btc(),
    )


def _chart(*args, **kwargs):
    return btc_legs.assemble_btc_leg_chart(_inputs(*args, **kwargs), NOW)


def test_legs_run_from_confirmed_boundary_to_next_confirmed_boundary():
    body = _chart([("2026-02-01", 1.6), ("2026-03-15", -1.8), ("2026-06-01", 2.0)], {"2026-02-01", "2026-03-15", "2026-06-01"})
    assert [(l.start, l.end, l.days, l.is_current) for l in body.legs] == [
        ("2026-02-01", "2026-03-15", 42, False),
        ("2026-03-15", "2026-06-01", 78, False),
        ("2026-06-01", None, 129, True),
    ]
    assert [b.date for b in body.boundaries] == ["2026-02-01", "2026-03-15", "2026-06-01"]
    assert body.boundaries[0].confirmed_date == "2026-02-03"


def test_stretch_before_first_confirmed_boundary_is_not_a_leg():
    body = _chart([("2026-04-01", 1.7)], {"2026-04-01"})
    assert body.first_bar_ts == "2026-01-01T00:00:00Z"
    assert len(body.legs) == 1
    assert body.legs[0].start == "2026-04-01"
    assert all(l.start >= "2026-04-01" for l in body.legs)


def test_unconfirmed_candidates_never_start_a_leg():
    body = _chart([("2026-02-01", 1.6), ("2026-03-01", 1.9), ("2026-05-01", -1.7)], {"2026-02-01", "2026-05-01"})
    assert [l.start for l in body.legs] == ["2026-02-01", "2026-05-01"]
    assert [b.date for b in body.boundaries] == ["2026-02-01", "2026-05-01"]
    # The unconfirmed candidate is still visible as the latest candidate when it is the newest.
    body = _chart([("2026-02-01", 1.6), ("2026-09-01", 1.9)], {"2026-02-01"})
    assert [l.start for l in body.legs] == ["2026-02-01"]
    assert body.current_leg.latest_candidate.model_dump() == {"date": "2026-09-01", "z_score": 1.9, "confirmed": False}


def test_current_leg_runs_to_last_btc_bar_with_days_golden():
    body = _chart([("2026-08-01", 1.6)], {"2026-08-01"}, btc=_btc(end="2026-09-30"))
    assert body.last_bar_ts == "2026-09-30T00:00:00Z"
    assert body.bar_count == 273  # 2026-01-01 .. 2026-09-30 inclusive
    assert [p.timestamp for p in body.btc][-1] == body.last_bar_ts
    cur = body.current_leg
    assert cur.start_date == "2026-08-01"
    assert cur.days_in_leg == 60  # Aug 31 + Sep 29
    assert cur.last_boundary_z == 1.6
    assert cur.composite_variant == "reduced"
    assert body.legs[-1].end is None and body.legs[-1].days == 60


def test_age_label_early_mid_late_at_exact_thirds_of_the_median():
    earlier = [30, 30, 30]  # median 30: thirds at 10 and 20
    assert btc_legs.age_estimate(9, earlier).label == "early"
    assert btc_legs.age_estimate(10, earlier).label == "mid"  # 3 x 10 == 30 is not < 30
    assert btc_legs.age_estimate(19, earlier).label == "mid"
    assert btc_legs.age_estimate(20, earlier).label == "late"  # 3 x 20 == 60 is not < 60
    # An even count gives a half-day median; the comparison stays exact in integers.
    est = btc_legs.age_estimate(7, [20, 21, 22, 23])  # median 21.5: 3 x 7 = 21 < 21.5
    assert (est.label, est.median_days, est.ratio) == ("early", 21.5, round(7 / 21.5, 4))
    assert btc_legs.age_estimate(8, [20, 21, 22, 23]).label == "mid"  # 24 >= 21.5, < 43


def test_median_uses_only_completed_earlier_legs_and_needs_three():
    days = ["2026-01-05", "2026-01-15", "2026-02-04", "2026-03-06", "2026-09-28"]
    body = _chart([(d, 1.6) for d in days], set(days))
    age = body.estimate.age
    assert age.earlier_lengths_days == [10, 20, 30, 206]
    assert age.earlier_legs == 4
    assert age.median_days == 25.0  # the open current leg (10 days) is not in the median
    assert age.age_days == 10 and age.label == "mid"

    two = _chart([(d, 1.6) for d in days[:3]], set(days[:3]))
    assert two.estimate.age.label is None
    assert two.estimate.age.earlier_legs == 2
    assert "2 earlier" in two.estimate.age.reason and "at least 3" in two.estimate.age.reason


def test_composite_change_is_the_14_point_roc_and_labels_rising_falling_flat_at_the_threshold():
    values = list(np.sin(np.arange(40) / 3.0))
    base = btc_legs.composite_estimate(_composite_series(values))
    changes = _composite_series(values)["composite"].diff(periods=leg_boundary.ROC_WINDOW_DAYS).dropna()
    assert base.change_14d == pytest.approx(values[-1] - values[-1 - 14])
    assert base.n_changes == len(changes) == 40 - 14
    t = base.threshold

    assert t > 0

    def with_last_change(change: float):
        vals = list(values)
        vals[-1] = vals[-1 - 14] + change
        return btc_legs.composite_estimate(_composite_series(vals))

    for change, expected in ((10.0, "rising"), (-10.0, "falling"), (0.0, "flat")):
        assert with_last_change(change).label == expected
    # At the threshold: the latest change is part of the history T is taken
    # from, so iterate to the change that equals its own +T / -T.
    for sign, expected in ((1, "rising"), (-1, "falling")):
        change = sign * t
        for _ in range(60):
            change = sign * with_last_change(change).threshold
        est = with_last_change(change)
        assert abs(abs(est.change_14d) - est.threshold) < 1e-9
        assert est.label == expected


def test_flat_threshold_is_half_the_std_of_historical_changes_and_is_reported():
    values = [0.0, 0.3, -0.2, 0.5, 0.1, 0.9, -0.4, 0.2, 0.0, 0.7, 0.3, -0.1, 0.6, 0.4, 0.8, 0.2, 1.1, -0.3, 0.5, 0.9]
    est = btc_legs.composite_estimate(_composite_series(values))
    changes = pd.Series(values).diff(periods=14).dropna()
    assert est.n_changes == 6
    assert est.history_std == pytest.approx(changes.std(ddof=1))
    assert est.history_std != pytest.approx(changes.std(ddof=0))
    assert est.threshold == pytest.approx(0.5 * changes.std(ddof=1))
    assert est.composite_as_of == "2026-01-20"
    assert "ddof 1" in est.rule and "0.5" in est.rule


def test_no_confirmed_boundary_means_no_current_leg_and_no_estimate():
    body = _chart([("2026-02-01", 1.6), ("2026-05-01", 1.8)], set())
    assert body.available is True
    assert body.legs == [] and body.boundaries == []
    assert body.current_leg is None and body.estimate is None
    assert body.bar_count > 0


def test_unavailable_composite_makes_composite_part_na_never_flat():
    # No composite at all.
    est = btc_legs.composite_estimate(None)
    assert est.label is None and "no composite" in est.reason
    # One historical change: the sample std is NaN.
    one = btc_legs.composite_estimate(_composite_series(np.linspace(0, 1, 15)))
    assert one.n_changes == 1 and one.label is None and one.history_std is None
    assert "at least 2" in one.reason
    # A std of 0 (T = 0) is N/A too, never rising, falling or flat.
    zero = btc_legs.composite_estimate(_composite_series([0.0] * 30))
    assert zero.history_std == 0 and zero.label is None and "0" in zero.reason
    # Inside the chart: a short composite keeps the age part and makes the composite part N/A.
    days = ["2026-01-05", "2026-01-15", "2026-02-04", "2026-03-06", "2026-09-28"]
    body = _chart([(d, 1.6) for d in days], set(days), composite=_Composite(_composite_series([0.1] * 10)))
    assert body.estimate.age.label == "mid"
    assert body.estimate.composite.label is None and body.estimate.composite.reason
    # The whole composite unavailable: no boundaries can exist, and the payload says why.
    gone = btc_legs.assemble_btc_leg_chart(
        LegInputs(variant="full", composite=_Composite(None, available=False), candidates=[], confirmations=[], btc=_btc()),
        NOW,
    )
    assert gone.available is True and gone.legs == [] and gone.estimate is None
    assert "composite unavailable" in gone.reason


def test_unavailable_btc_history_is_unavailable_not_zero_legs():
    empty = _btc()
    empty.df = empty.df.iloc[0:0]
    body = _chart([("2026-02-01", 1.6)], {"2026-02-01"}, btc=empty)
    assert body.available is False
    assert body.reason
    assert body.bar_count == 0 and body.btc == [] and body.legs == []
    assert body.current_leg is None and body.estimate is None
    assert body.first_bar_ts is None and body.last_bar_ts is None
    none_read = btc_legs.assemble_btc_leg_chart(
        LegInputs(variant="reduced", composite=_Composite(None, available=False), candidates=[], confirmations=[], btc=None),
        NOW,
    )
    assert none_read.available is False and none_read.reason


def test_estimate_heading_is_exact_labels_are_closed_enums_and_every_input_is_in_the_payload():
    days = ["2026-01-05", "2026-01-15", "2026-02-04", "2026-03-06", "2026-09-28"]
    body = _chart([(d, 1.6) for d in days], set(days))
    est = body.estimate.model_dump()
    assert est["heading"] == "Estimate (rule over the numbers shown)"
    assert set(typing.get_args(AgeLabel)) == {"early", "mid", "late"}
    assert set(typing.get_args(CompositeChangeLabel)) == {"rising", "falling", "flat"}
    assert est["age"]["label"] in typing.get_args(AgeLabel)
    assert est["composite"]["label"] in typing.get_args(CompositeChangeLabel)
    for key in ("age_days", "median_days", "ratio", "earlier_legs", "earlier_lengths_days", "rule"):
        assert est["age"][key] is not None, key
    for key in ("change_14d", "threshold", "history_std", "n_changes", "composite_as_of", "rule"):
        assert est["composite"][key] is not None, key
    assert est["age"]["ratio"] == pytest.approx(est["age"]["age_days"] / est["age"]["median_days"], abs=1e-4)
    assert body.server_time == "2026-10-09T12:00:00Z"
    assert all(_ZFORM.match(p.timestamp) for p in body.btc)
