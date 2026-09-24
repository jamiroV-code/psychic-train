"""Check the regime dashboard's reproduction of LiqTide against LiqTide itself
(regime dashboard RFC-002, Hybrid gate for AC-3).

Two comparisons per archived raw payload (`cache/liqtide/raw/*.json`):

1. **Normalisation** — apply our `normalise()` to LiqTide's own `signals`
   impulses and compare with its published `tide_index.components`. Isolates
   the tanh/scale formula from any input differences.
2. **Inputs** — our component contribution computed from primary series (as of
   the payload date) against the same published component. Differences here
   come from input data (e.g. DefiLlama's coin set vs LiqTide's).

Then the coverage table (first/last date, points, status) for every component
and the published-vs-reproduced agreement stats. Reads the cache only.

Run:
  uv run --project api python api/scripts/check_component_reproduction.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd

from api.analytics.regime import components as comp
from api.data import cache

# LiqTide `signals` key holding each component's raw impulse (confirmed on
# the 2026-09-24 payload).
SIGNAL_KEYS = {
    "net_liquidity": "netliq_d4w",
    "stablecoin_supply": "stables_pct7",
    "broad_dollar": "dollar_pct1m",
    "rrp_release": "rrp_d4w",
    "etf_flows": "etf_flow5",
    "btc_dominance": "btc_dom_d30",
}
# LiqTide `metrics` entry whose `as_of` date its component was computed on.
# Comparing on that date (not the payload date) avoids e.g. DefiLlama's
# still-moving intraday point for "today".
AS_OF_KEYS = {
    "net_liquidity": "net_liquidity",
    "stablecoin_supply": "stables",
    "broad_dollar": "dollar",
    "rrp_release": "rrp",
    "etf_flows": "etf_flows",
    "btc_dominance": "btc_dom",
}
TOLERANCE = 0.0005  # published components carry 4 decimals


def _on(points: pd.DataFrame, day: pd.Timestamp) -> float | None:
    if points.empty:
        return None
    hit = points[points["date"] == day]
    return None if hit.empty else float(hit.iloc[-1]["contribution"])


def _as_of(raw: dict, cid: str) -> pd.Timestamp | None:
    entry = (raw.get("metrics") or {}).get(AS_OF_KEYS[cid])
    as_of = entry.get("as_of") if isinstance(entry, dict) else None
    return pd.Timestamp(as_of[:10]) if isinstance(as_of, str) else None


def check_normalisation(raw: dict) -> list[tuple[str, float | None, float | None]]:
    signals = raw.get("signals") or {}
    published = (raw.get("tide_index") or {}).get("components") or {}
    rows = []
    for spec in comp.COMPONENTS:
        impulse = signals.get(SIGNAL_KEYS[spec.id])
        ours = comp.normalise(float(impulse), spec) if isinstance(impulse, (int, float)) else None
        rows.append((spec.id, ours, published.get(spec.liqtide_key)))
    return rows


def main() -> int:
    result = comp.build_regime_components()
    by_id = {c.spec.id: c for c in result.components}
    problems = 0

    print("Coverage")
    for c in result.components:
        print(f"  {c.spec.id:<18} status={c.status:<11} points={len(c.points):<6} "
              f"first={c.first_date} last={c.last_date}" + (f"  ({c.reason})" if c.reason else ""))
    print(f"  reproduced index   points={len(result.reproduced)}")
    print(f"  published index    points={len(result.published)}")
    print(f"  agreement          {result.agreement}")

    for day in cache.list_liqtide_raw_dates():
        raw = cache.read_liqtide_raw(day)
        if raw is None:
            continue
        print(f"\nPayload {day} (generated {raw.get('generated_utc')})")
        print(f"  {'component':<18} {'as_of':<11} {'published':>10} {'norm(signal)':>13} {'from inputs':>12}")
        for cid, from_signal, published in check_normalisation(raw):
            c = by_id[cid]
            as_of = _as_of(raw, cid)
            from_inputs = _on(c.points, as_of) if as_of is not None else None
            fmt = lambda v: f"{v:.4f}" if isinstance(v, (int, float)) else "—"  # noqa: E731
            as_of_txt = as_of.strftime("%Y-%m-%d") if as_of is not None else "—"
            flag = ""
            if isinstance(published, (int, float)) and from_signal is not None and abs(from_signal - published) > TOLERANCE:
                flag = "  <-- normalisation mismatch"
                problems += 1
            print(f"  {cid:<18} {as_of_txt:<11} {fmt(published):>10} {fmt(from_signal):>13} {fmt(from_inputs):>12}{flag}")

    if problems:
        print(f"\nWARN: {problems} normalisation mismatch(es) — LiqTide may have changed its scales.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
