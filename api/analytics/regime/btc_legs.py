"""T38 / S7: the BTC leg chart behind `GET /api/regime/btc-legs` (C7, C8).

A leg runs from a confirmed boundary's `date` to the next confirmed
boundary; the current leg runs to the last cached BTC `1d` bar. The stretch
before the first confirmed boundary is not a leg, and an unconfirmed
candidate never starts one.

The D-14 estimate is two independent labels, never merged, each computed by
a rule written out below and shipped in the payload next to every number it
used:

- AGE: `age_days` of the current leg against the median length of the
  earlier completed legs, compared in integers.
- COMPOSITE: the latest 14-point change of the composite against a
  threshold of half the sample standard deviation of all its historical
  14-point changes.

Nothing here says what BTC will do next; the labels describe the numbers
shown and nothing else.
"""
from __future__ import annotations

import math

import pandas as pd

from api.analytics.regime import leg_boundary
from api.data import freshness
from api.models.regime import (
    AgeEstimate,
    BtcLeg,
    BtcLegBoundary,
    BtcLegChartResponse,
    CompositeEstimate,
    CurrentLeg,
    LatestCandidate,
    LegEstimate,
)
from api.models.screener import ChartBar

ESTIMATE_HEADING = "Estimate (rule over the numbers shown)"
MIN_EARLIER_LEGS = 3
THRESHOLD_STD_FACTOR = 0.5

AGE_RULE = (
    "early when 3 x age_days < median_days; mid when 3 x age_days < 2 x median_days; "
    "late otherwise. median_days is the median length of the earlier completed confirmed legs "
    f"(at least {MIN_EARLIER_LEGS} needed)."
)
COMPOSITE_RULE = (
    "rising when change_14d >= +T; falling when change_14d <= -T; flat otherwise. "
    f"T = {THRESHOLD_STD_FACTOR} x the sample standard deviation (ddof 1) of all historical "
    f"{leg_boundary.ROC_WINDOW_DAYS}-point changes of the composite."
)


def _day(ts) -> pd.Timestamp:
    return freshness.as_utc(ts).normalize()


def _iso_date(ts) -> str:
    return _day(ts).date().isoformat()


def build_legs(boundary_dates: list[pd.Timestamp], last_bar: pd.Timestamp) -> list[BtcLeg]:
    """One leg per confirmed boundary, oldest first; the last one is open
    and runs to `last_bar`."""
    days = sorted({_day(d) for d in boundary_dates})
    legs: list[BtcLeg] = []
    for i, start in enumerate(days):
        current = i == len(days) - 1
        end = _day(last_bar) if current else days[i + 1]
        legs.append(
            BtcLeg(
                start=start.date().isoformat(),
                end=None if current else end.date().isoformat(),
                days=int((end - start).days),
                is_current=current,
            )
        )
    return legs


def age_estimate(age_days: int, earlier_lengths_days: list[int]) -> AgeEstimate:
    """AGE label, integer comparisons only. With `2m` = twice the median
    (an integer for integer lengths), `3a < m` is `6a < 2m` and `3a < 2m`
    is `6a < 4m`."""
    lengths = [int(x) for x in earlier_lengths_days]
    n = len(lengths)
    base = dict(age_days=int(age_days), earlier_legs=n, earlier_lengths_days=lengths, rule=AGE_RULE)
    if n < MIN_EARLIER_LEGS:
        return AgeEstimate(
            **base,
            reason=f"N/A: {n} earlier completed confirmed legs, at least {MIN_EARLIER_LEGS} needed",
        )

    ordered = sorted(lengths)
    mid = n // 2
    twice_median = 2 * ordered[mid] if n % 2 else ordered[mid - 1] + ordered[mid]
    if twice_median <= 0:
        return AgeEstimate(**base, median_days=twice_median / 2, reason="N/A: the median leg length is 0 days")

    six_age = 6 * int(age_days)
    if six_age < twice_median:
        label = "early"
    elif six_age < 2 * twice_median:
        label = "mid"
    else:
        label = "late"
    median_days = twice_median / 2
    return AgeEstimate(
        **base,
        label=label,
        median_days=median_days,
        ratio=round(int(age_days) / median_days, 4),
    )


def composite_estimate(series: pd.DataFrame | None) -> CompositeEstimate:
    """COMPOSITE label from the composite's `ROC_WINDOW_DAYS`-point changes
    (the same `diff` `detect_candidate_boundaries` uses). A missing
    composite, fewer than 2 historical changes (NaN std) or a zero std is
    N/A with a reason, never `flat`."""
    if series is None or series.empty:
        return CompositeEstimate(n_changes=0, rule=COMPOSITE_RULE, reason="N/A: no composite is available")

    df = series.sort_values("date").reset_index(drop=True)
    roc = df["composite"].diff(periods=leg_boundary.ROC_WINDOW_DAYS)
    changes = roc.dropna()
    n = int(len(changes))
    as_of = _iso_date(df["date"].iloc[-1])
    std = float(changes.std()) if n else math.nan
    latest = float(roc.iloc[-1]) if pd.notna(roc.iloc[-1]) else None
    base = dict(
        change_14d=latest,
        n_changes=n,
        composite_as_of=as_of,
        rule=COMPOSITE_RULE,
        history_std=None if math.isnan(std) else std,
    )

    if math.isnan(std):
        return CompositeEstimate(
            **base, reason=f"N/A: {n} historical changes, at least 2 needed for a standard deviation"
        )
    threshold = THRESHOLD_STD_FACTOR * std
    if std == 0:
        return CompositeEstimate(
            **base, threshold=threshold, reason="N/A: the standard deviation of the historical changes is 0"
        )
    if latest is None:
        return CompositeEstimate(
            **base, threshold=threshold, reason="N/A: the latest composite point has no 14-point change"
        )

    if latest >= threshold:
        label = "rising"
    elif latest <= -threshold:
        label = "falling"
    else:
        label = "flat"
    return CompositeEstimate(**base, threshold=threshold, label=label)


def assemble_btc_leg_chart(inputs: leg_boundary.LegInputs, now: pd.Timestamp) -> BtcLegChartResponse:
    """Pure assembly of the response from one `LegInputs` read."""
    server_time = freshness.iso_z(now)
    variant = inputs.variant
    btc_df = inputs.btc.df if inputs.btc is not None else None

    if btc_df is None or btc_df.empty:
        return BtcLegChartResponse(
            available=False,
            reason="no BTC 1d bars in the cache",
            server_time=server_time,
            composite_variant=variant,
            bar_count=0,
            btc=[],
            boundaries=[],
            legs=[],
        )

    bars = btc_df.sort_values("timestamp").reset_index(drop=True)
    btc = [ChartBar(timestamp=freshness.iso_z(t), close=float(c)) for t, c in zip(bars["timestamp"], bars["close"])]
    first_bar, last_bar = bars["timestamp"].iloc[0], bars["timestamp"].iloc[-1]

    composite_ok = bool(getattr(inputs.composite, "available", False))
    confirmed = {c.candidate_date: c for c in inputs.confirmations if c.confirmed}
    confirmed_candidates = sorted((c for c in inputs.candidates if c.date in confirmed), key=lambda c: c.date)
    boundaries = [
        BtcLegBoundary(
            date=_iso_date(c.date),
            z_score=c.z_score,
            confirmed_date=(
                _iso_date(confirmed[c.date].confirmed_date) if confirmed[c.date].confirmed_date is not None else None
            ),
        )
        for c in confirmed_candidates
    ]
    legs = build_legs([c.date for c in confirmed_candidates], last_bar)

    reason = None if composite_ok else "composite unavailable: no boundaries can be detected"
    current_leg = None
    estimate = None
    if legs:
        current = legs[-1]
        series = inputs.composite.series if composite_ok else None
        comp = composite_estimate(series)
        composite_value = None
        if series is not None and not series.empty:
            last_value = series.sort_values("date")["composite"].iloc[-1]
            composite_value = float(last_value) if pd.notna(last_value) else None
        latest = max(inputs.candidates, key=lambda c: c.date) if inputs.candidates else None
        current_leg = CurrentLeg(
            start_date=current.start,
            days_in_leg=current.days,
            composite_value=composite_value,
            composite_as_of=comp.composite_as_of,
            change_14d=comp.change_14d,
            last_boundary_z=confirmed_candidates[-1].z_score,
            latest_candidate=(
                LatestCandidate(date=_iso_date(latest.date), z_score=latest.z_score, confirmed=latest.date in confirmed)
                if latest is not None
                else None
            ),
            composite_variant=variant,
        )
        estimate = LegEstimate(
            heading=ESTIMATE_HEADING,
            age=age_estimate(current.days, [leg.days for leg in legs[:-1]]),
            composite=comp,
        )

    return BtcLegChartResponse(
        available=True,
        reason=reason,
        server_time=server_time,
        composite_variant=variant,
        first_bar_ts=freshness.iso_z(first_bar),
        last_bar_ts=freshness.iso_z(last_bar),
        bar_count=len(btc),
        btc=btc,
        boundaries=boundaries,
        legs=legs,
        current_leg=current_leg,
        estimate=estimate,
    )


def build_btc_leg_chart(as_of: pd.Timestamp | None = None) -> BtcLegChartResponse:
    """The BTC leg chart for `as_of` (default now). The caller decides
    whether the BTC read is cache-only (the router wraps it)."""
    now = as_of or pd.Timestamp.now(tz="utc")
    return assemble_btc_leg_chart(leg_boundary._leg_inputs(now, always_read_btc=True), now)
