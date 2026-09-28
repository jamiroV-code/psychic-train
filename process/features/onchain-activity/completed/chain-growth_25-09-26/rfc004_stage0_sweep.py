"""RFC-4 Stage 0 throwaway analysis: floor/ramp rule sweep on the real archived series.

Run from repo root:  cd api && uv run python ../process/features/onchain-activity/completed/chain-growth_25-09-26/rfc004_stage0_sweep.py
Not production code. Reads the cache via api.data.cache.read_onchain_series only.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from api.data.cache import read_onchain_series  # noqa: E402

LAUNCH = {"ethereum": None, "polygon": None, "arbitrum": "2021-08-31", "optimism": "2021-12-16",
          "base": "2023-08-09", "robinhood": "2026-07-01"}
CHAINS = list(LAUNCH)
METRICS = ["active_addresses", "transactions"]


def load(chain: str, metric: str, trim_launch: bool = True) -> pd.Series:
    df = read_onchain_series("growthepie", chain, metric)
    s = pd.Series(df["value"].to_numpy(float), index=pd.to_datetime(df["date"]))
    s = s.asfreq("D")  # gaps stay NaN (never filled for display)
    if trim_launch and LAUNCH[chain]:
        s = s[s.index >= LAUNCH[chain]]
    return s


def smooth(s: pd.Series, span: int) -> pd.Series:
    # EMA over observed points only; gaps are skipped not zero-filled.
    return s.ewm(span=span, adjust=False, ignore_na=True).mean().where(s.notna() | s.ffill().notna())


def detect(s: pd.Series, n: int, r: float, m: int, spacing: int, span: int = 28):
    """Causal zig-zag: floor = lowest EMA point that is also the trailing-N-day low;
    confirmed (ramp) once EMA stays >= floor*(1+r) for m consecutive days.
    After a confirmed ramp, a new floor is only searched once EMA has fallen r below
    the post-ramp peak. Floors closer than `spacing` days to the previous one are merged."""
    e = smooth(s, span).dropna()
    if len(e) < n + m:
        return [], "not-enough-history"
    roll_low = e.rolling(n, min_periods=n).min()
    events = []
    mode = "seek_floor"
    cand_d, cand_v, streak, peak_v = None, None, 0, None
    for d, v in e.items():
        if pd.isna(roll_low[d]):
            continue
        if mode == "seek_floor":
            if v <= roll_low[d] and (cand_v is None or v <= cand_v):
                cand_d, cand_v, streak = d, v, 0
            elif cand_v is not None and v >= cand_v * (1 + r):
                streak += 1
                if streak >= m:
                    if events and (cand_d - events[-1]["floor"]).days < spacing:
                        if cand_v < events[-1]["floor_v"]:
                            events[-1].update(floor=cand_d, floor_v=cand_v, ramp=d)
                    else:
                        events.append({"floor": cand_d, "floor_v": cand_v, "ramp": d})
                    mode, peak_v = "ramping", v
            else:
                streak = 0
        else:
            peak_v = max(peak_v, v)
            if v <= peak_v * (1 - r):
                mode, cand_d, cand_v, streak = "seek_floor", None, None, 0
    # current state
    last_v, last_low = e.iloc[-1], roll_low.iloc[-1]
    off = last_v / last_low - 1
    ema7 = smooth(s, 7).dropna().iloc[-1]
    if mode == "ramping":
        state = "ramping" if ema7 >= last_v else "neutral"
    elif off < r:
        state = "floor"
    elif ema7 < last_v:
        state = "declining"
    else:
        state = "neutral"
    return events, state


GRID = {"n": [90, 180, 365], "r": [0.15, 0.25, 0.40], "m": [7, 14], "spacing": [90, 180]}


def main() -> None:
    data = {(c, m): load(c, m) for c in CHAINS for m in METRICS}
    out = {}
    summary = []
    for n, r, m, sp in itertools.product(*GRID.values()):
        key = f"N{n}_R{int(r*100)}_M{m}_S{sp}"
        res = {}
        total = 0
        for (c, met), s in data.items():
            ev, st = detect(s, n, r, m, sp)
            res[f"{c}/{met}"] = {"state": st, "events": [
                {"floor": e["floor"].date().isoformat(), "ramp": e["ramp"].date().isoformat(),
                 "lag_days": (e["ramp"] - e["floor"]).days} for e in ev]}
            total += len(ev)
        out[key] = res
        summary.append((key, total))
    Path(__file__).with_name("rfc004_stage0_sweep_output.json").write_text(json.dumps(out, indent=1))
    for k, t in summary:
        print(k, "total_events", t)


if __name__ == "__main__":
    main()
