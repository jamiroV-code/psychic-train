"""One-time probe (item 32): does DefiLlama's aggregate stablecoin-supply
endpoint have enough history to cover the 2017/2020-21 backtest cycles
(ADR-2's conditional clause for including stablecoin-supply in the reduced
composite)? Not a recurring test — run once; the RESULT is recorded inline
below, per item 32's own instruction ("record result inline as a code
comment... not a recurring test").

RESULT (RFC-002 Stage 0, checked against the live endpoint,
2026-09-18): `https://stablecoins.llama.fi/stablecoincharts/all` is
keyless, returns JSON, and its earliest data point is **2017-11-29** —
comfortably deep enough for both the 2017 and 2020-21 backtest cycles.
Per ADR-2, stablecoin-supply IS therefore included as the reduced
composite's 4th component (`api/data/defillama_adapter.py`, wired into
`api/analytics/regime/liquidity_composite.py::build_reduced_composite`).
See also Test Infra Improvement Notes in the plan file for this same
result recorded at the plan level.

Run manually: `uv run python -m api.scripts.probe_stablecoin_history`
"""
from __future__ import annotations

import datetime

import httpx

from api.data.defillama_adapter import STABLECOIN_CHARTS_URL

SUFFICIENT_DEPTH_CUTOFF = "2018-01-01"  # need coverage before this to span the 2017 cycle


def probe() -> None:
    try:
        with httpx.Client() as client:
            resp = client.get(STABLECOIN_CHARTS_URL, timeout=20.0)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # pragma: no cover - manual/one-time script
        print(f"PROBE FAILED: {exc!r} — treat stablecoin-supply as unavailable until re-run.")
        return

    if not isinstance(data, list) or not data:
        print("PROBE RESULT: no usable data returned — treat stablecoin-supply as unavailable.")
        return

    dates = [int(entry["date"]) for entry in data if "date" in entry]
    if not dates:
        print("PROBE RESULT: response had no dated points — treat stablecoin-supply as unavailable.")
        return

    earliest = min(dates)
    earliest_str = datetime.datetime.fromtimestamp(earliest, tz=datetime.timezone.utc).date().isoformat()
    print(f"PROBE RESULT: {len(data)} points, earliest date {earliest_str}.")
    if earliest_str <= SUFFICIENT_DEPTH_CUTOFF:
        print("Sufficient depth for both the 2017 and 2020-21 backtest cycles.")
    else:
        print("NOT sufficient depth for the 2017 cycle — re-check ADR-2's conditional inclusion.")


if __name__ == "__main__":
    probe()
