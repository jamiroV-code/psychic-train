"""Floor/ramp rule, smoothing and the minimum-history gate (chain-growth RFC-4).

Pure functions over a daily `pd.Series` (DatetimeIndex, float values). No I/O.

Constants were chosen on the real archive (commit 7143733) by a 36-set sweep,
not asserted: see
`process/features/onchain-activity/completed/chain-growth_25-09-26/chain-growth_RFC-004-stage0_REPORT_25-09-26.md`
§2 and `rfc004_stage0_sweep_output.json` in the same folder. N and R drive the
result (M and S move the event count by <= 4); N=180/R=25% keeps the lows a
trader would name (ETH 2022-06-30, Arbitrum tx 2023-09-17, Base 2025-04-23)
and drops the 2020-21 micro-dips N=90 marks, without N=365's misses. The
middle of both ranges was picked, no per-chain tuning. User-approved
2026-09-26 (decision D1). `FLOOR_STATE_PCT` is decision D3 (tightened from R).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

# D1 — sweep-validated floor/ramp constants.
EMA_SPAN = 28  # base smoothing for the rule and the comparison
EMA_FAST_SPAN = 7  # display + current-state direction only
WINDOW_DAYS = 180  # N: a floor must be the trailing N-day low of the EMA
RECOVERY_PCT = 0.25  # R: ramp = EMA >= floor * (1 + R) ...
SUSTAIN_DAYS = 14  # M: ... for M consecutive days
SPACING_DAYS = 180  # S: floors closer than this are merged (lower one kept)
# D3 — current-state `floor` label: within 10% of the N-day low. Separate from R.
FLOOR_STATE_PCT = 0.10
# ADR-4 — the gate falls out of the rule's own preconditions.
MIN_HISTORY_DAYS = WINDOW_DAYS + SUSTAIN_DAYS  # 194

STATES = ("not-enough-history", "floor", "ramping", "declining", "neutral")


@dataclass(frozen=True)
class FloorRampEvent:
    floor_date: date
    ramp_date: date


@dataclass(frozen=True)
class FloorRampResult:
    state: str
    events: list[FloorRampEvent] = field(default_factory=list)
    history_days: int = 0
    gate_met_on: date | None = None  # first day the gate is (or will be) met


def to_daily(values: pd.Series) -> pd.Series:
    """Sorted daily series; missing days stay NaN (never filled)."""
    s = pd.Series(values.to_numpy(float), index=pd.DatetimeIndex(values.index)).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    if s.empty:
        return s
    return s.asfreq("D")


def post_launch(s: pd.Series, launch_date: str | date | None) -> pd.Series:
    """D2: pre-launch points are excluded from all analytics (one rule, all chains)."""
    if launch_date is None or s.empty:
        return s
    return s[s.index >= pd.Timestamp(launch_date)]


def ema(s: pd.Series, span: int) -> pd.Series:
    """EMA that skips missing days (never zero-fills). Days before the first
    observation stay NaN; gap days carry the last EMA value forward."""
    if s.empty:
        return s.copy()
    return s.ewm(span=span, adjust=False, ignore_na=True).mean()


def history_days(s: pd.Series) -> int:
    """Calendar days from the first to the last observed point, inclusive."""
    obs = s.dropna()
    if obs.empty:
        return 0
    return (obs.index[-1] - obs.index[0]).days + 1


def gate_met_on(s: pd.Series) -> date | None:
    obs = s.dropna()
    if obs.empty:
        return None
    return (obs.index[0] + timedelta(days=MIN_HISTORY_DAYS - 1)).date()


def detect_floor_ramp(s: pd.Series) -> FloorRampResult:
    """Run the rule on a daily post-launch series (see module docstring).

    Causal zig-zag on EMA28: a floor candidate is the lowest EMA point that is
    also the trailing-N-day low; it is confirmed (ramp) once EMA stays >=
    floor*(1+R) for M consecutive days. After a ramp, a new floor is searched
    only once EMA falls R below its post-ramp peak (re-arm). Floors < S days
    apart are merged, keeping the lower one.
    """
    days = history_days(s)
    gate = gate_met_on(s)
    if days < MIN_HISTORY_DAYS:
        return FloorRampResult("not-enough-history", [], days, gate)

    e = ema(s, EMA_SPAN).dropna()
    roll_low = e.rolling(WINDOW_DAYS, min_periods=WINDOW_DAYS).min()
    events: list[dict] = []
    mode = "seek_floor"
    cand_d = cand_v = peak_v = None
    streak = 0
    for d, v in e.items():
        low = roll_low[d]
        if pd.isna(low):
            continue
        if mode == "seek_floor":
            if v <= low and (cand_v is None or v <= cand_v):
                cand_d, cand_v, streak = d, v, 0
            elif cand_v is not None and v >= cand_v * (1 + RECOVERY_PCT):
                streak += 1
                if streak >= SUSTAIN_DAYS:
                    if events and (cand_d - events[-1]["floor"]).days < SPACING_DAYS:
                        if cand_v < events[-1]["floor_v"]:
                            events[-1].update(floor=cand_d, floor_v=cand_v, ramp=d)
                    else:
                        events.append({"floor": cand_d, "floor_v": cand_v, "ramp": d})
                    mode, peak_v = "ramping", v
            else:
                streak = 0
        else:
            peak_v = max(peak_v, v)
            if v <= peak_v * (1 - RECOVERY_PCT):
                mode, cand_d, cand_v, streak = "seek_floor", None, None, 0

    last_v = e.iloc[-1]
    last_low = roll_low.iloc[-1]
    fast = ema(s, EMA_FAST_SPAN).dropna().iloc[-1]
    if mode == "ramping":
        state = "ramping" if fast >= last_v else "neutral"
    elif not pd.isna(last_low) and last_low > 0 and last_v / last_low - 1 < FLOOR_STATE_PCT:
        state = "floor"
    elif fast < last_v:
        state = "declining"
    else:
        state = "neutral"
    out = [FloorRampEvent(ev["floor"].date(), ev["ramp"].date()) for ev in events]
    return FloorRampResult(state, out, days, gate)
