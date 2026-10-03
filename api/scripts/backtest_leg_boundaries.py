"""Leg-boundary backtest (item 40, Hybrid verification gate): reconstructs
the reduced composite over the 2017 and 2020-21 cycles, runs candidate
detection + price-structure confirmation, and writes a dated report
artifact for manual review against the known ~3-leg structure.

Deep BTC daily price history is needed for the confirmation step
(`leg_boundary.confirm_boundaries`) reaching back to 2017 — `ccxt_adapter`
is Hyperliquid-only (RFC-001 Stage 0) and Hyperliquid does not have price
history that old, so this script pulls BTC daily OHLC from
CryptoDataDownload instead (`data-sources/all-data-sources.md`: "Since
2017... use it for a one-time historical backfill"), per the plan's own
item 40 instruction.

CAVEAT (documented, not silently assumed — could not be fully verified from
this sandbox, which has no network access to third-party hosts beyond a
small allowlist): the exact CSV URL below follows CryptoDataDownload's
long-standing public `cdd/{Exchange}_{PAIR}_d.csv` naming convention. If it
404s, open https://www.cryptodatadownload.com/data/gemini/ (or /binance/)
in a browser, copy the real daily-BTC/USD CSV link, and update
`BTC_HISTORY_CSV_URL` below — this script fails loudly with that exact
instruction rather than silently falling back to a shorter series.

Known composite-input gap for these cycles (see `liquidity_composite.py`
module docstring, ADR-1 precedent): the reduced composite's BTC-dominance
component has no free deep-history source and is only populated from
whatever LiqTide history has accumulated locally since ~2024 — for both
the 2017 and 2020-21 cycles this composite therefore runs on
net-liquidity + dollar-strength + stablecoin-supply only. This is exactly
why the result is a Hybrid gate (manually reviewed against known cycle
structure), not a pass/fail assertion.

Run manually (from inside `api/`): `uv run python scripts/backtest_leg_boundaries.py --cycle 2017`
                                   `uv run python scripts/backtest_leg_boundaries.py --cycle 2020-21`
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Standalone-script bootstrap: unlike pytest (which gets the project root on
# sys.path via api/pyproject.toml's `[tool.pytest.ini_options] pythonpath`),
# a plain `python scripts/backtest_leg_boundaries.py` invocation has no such
# mechanism — Python only puts this script's own directory on sys.path, so
# `from api...` fails with ModuleNotFoundError regardless of cwd. Insert the
# project root (parent of `api/`) explicitly so this script runs correctly
# with a bare `uv run python scripts/backtest_leg_boundaries.py --cycle ...`
# from inside `api/`, with no PYTHONPATH gymnastics required.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import httpx
import pandas as pd

from api.analytics.regime import leg_boundary, liquidity_composite

BTC_HISTORY_CSV_URL = "https://www.cryptodatadownload.com/cdd/Gemini_BTCUSD_d.csv"

CYCLE_WINDOWS: dict[str, tuple[str, str]] = {
    "2017": ("2017-01-01", "2018-03-01"),
    "2020-21": ("2020-01-01", "2021-12-31"),
}

REPORT_DIR = Path(__file__).resolve().parents[2] / "process" / "general-plans" / "completed" / "momentum-screener_17-09-26"


def _fetch_btc_history_csv() -> pd.DataFrame | None:
    try:
        with httpx.Client(follow_redirects=True) as client:
            resp = client.get(BTC_HISTORY_CSV_URL, timeout=30.0)
            resp.raise_for_status()
            text = resp.text
    except Exception as exc:
        print(f"BTC history fetch failed ({exc!r}). Update BTC_HISTORY_CSV_URL — see module docstring.")
        return None

    try:
        # CryptoDataDownload CSVs conventionally have a one-line disclaimer
        # header before the real header row.
        lines = text.splitlines()
        start = 1 if lines and not lines[0].lower().startswith(("unix", "date")) else 0
        df = pd.read_csv(io.StringIO("\n".join(lines[start:])))
        cols = {c.lower(): c for c in df.columns}
        date_col = cols.get("date") or cols.get("unix timestamp")
        df["timestamp"] = pd.to_datetime(df[date_col], utc=True, errors="coerce")
        # CryptoDataDownload's actual header has no bare "Volume" column —
        # it splits volume into "Volume BTC" and "Volume USD" (confirmed
        # live 19-09-26). `leg_boundary.confirm_boundaries` doesn't consume
        # volume at all, so this is carried along for completeness only;
        # prefer USD-denominated, fall back to BTC-denominated, then to a
        # NaN column so the file still round-trips if a future export drops
        # both (rather than crashing here).
        volume_col = cols.get("volume") or cols.get("volume usd") or cols.get("volume btc")
        df = df.rename(columns={cols.get("open", "open"): "open", cols.get("high", "high"): "high",
                                  cols.get("low", "low"): "low", cols.get("close", "close"): "close"})
        df["volume"] = df[volume_col] if volume_col else pd.NA
        df = df.dropna(subset=["timestamp", "high", "low", "close"]).sort_values("timestamp")
        return df[["timestamp", "open", "high", "low", "close", "volume"]]
    except Exception as exc:
        print(f"BTC history CSV parse failed ({exc!r}). Update BTC_HISTORY_CSV_URL / parsing — see module docstring.")
        return None


_UNKNOWN_COVERAGE = {"n_components": None, "components_present": None}


def _coverage_lookup(series: pd.DataFrame) -> dict[str, dict]:
    """date-string -> that date's component coverage, for annotating each
    detected boundary with the inputs it was actually built from (the thing
    a human needs beside each boundary at the Hybrid gate).
    """
    if "n_components" not in series.columns:
        return {}
    return {
        row["date"].date().isoformat():
            {"n_components": int(row["n_components"]), "components_present": row["components_present"]}
        for _, row in series.iterrows()
    }


def _coverage_summary(series: pd.DataFrame) -> dict:
    """Window-level coverage picture: min/max components seen, plus the dates
    where the SET of present components changes. Change points (rather than
    one entry per day) keep this readable for a 400+ day window while still
    showing, e.g., stablecoin supply joining in late 2017 or BTC dominance
    joining in 2024.
    """
    if "n_components" not in series.columns or series.empty:
        return {"min_n_components": None, "max_n_components": None, "coverage_change_points": []}

    change_points = []
    previous = None
    for _, row in series.iterrows():
        present = row["components_present"]
        if present != previous:
            change_points.append({"date": row["date"].date().isoformat(),
                                  "n_components": int(row["n_components"]),
                                  "components_present": present})
            previous = present

    return {
        "min_n_components": int(series["n_components"].min()),
        "max_n_components": int(series["n_components"].max()),
        "coverage_change_points": change_points,
    }


def run_backtest(cycle: str) -> dict:
    if cycle not in CYCLE_WINDOWS:
        raise ValueError(f"unknown cycle {cycle!r} — choose one of {list(CYCLE_WINDOWS)}")
    start_str, end_str = CYCLE_WINDOWS[cycle]
    start, end = pd.Timestamp(start_str, tz="utc"), pd.Timestamp(end_str, tz="utc")

    composite = liquidity_composite.build_reduced_composite(date_range=(start, end))
    btc_df = _fetch_btc_history_csv()
    if btc_df is not None:
        btc_df = btc_df[(btc_df["timestamp"] >= start) & (btc_df["timestamp"] <= end)]

    result = {
        "cycle": cycle,
        "window": [start_str, end_str],
        "composite_available": composite.available,
        "composite_points": int(len(composite.series)),
        "btc_history_available": btc_df is not None and not btc_df.empty,
        "btc_history_points": int(len(btc_df)) if btc_df is not None else 0,
        "candidate_boundaries": [],
        "confirmed_boundaries": [],
    }

    if not composite.available:
        result["note"] = "reduced composite unavailable for this window — cannot run detection (see caveats above)."
        return result

    candidates = leg_boundary.detect_candidate_boundaries(composite.series)
    confirmations = (
        leg_boundary.confirm_boundaries(candidates, btc_df) if btc_df is not None and not btc_df.empty else
        [leg_boundary.BoundaryConfirmation(candidate_date=c.date, confirmed=False, confirmed_date=None) for c in candidates]
    )
    confirmed_by_date = {c.candidate_date: c for c in confirmations if c.confirmed}

    coverage_by_date = _coverage_lookup(composite.series)
    result["composite_component_coverage"] = _coverage_summary(composite.series)

    result["candidate_boundaries"] = [
        {"date": c.date.date().isoformat(), "z_score": c.z_score, "confirmed": c.date in confirmed_by_date,
         **coverage_by_date.get(c.date.date().isoformat(), _UNKNOWN_COVERAGE)}
        for c in candidates
    ]
    result["confirmed_boundaries"] = [
        {"date": conf.candidate_date.date().isoformat(),
         "confirmed_date": conf.confirmed_date.date().isoformat() if conf.confirmed_date is not None else None,
         **coverage_by_date.get(conf.candidate_date.date().isoformat(), _UNKNOWN_COVERAGE)}
        for conf in confirmations if conf.confirmed
    ]
    if btc_df is None or btc_df.empty:
        result["note"] = "BTC price history unavailable — candidates detected but none could be confirmed this run."
    return result


def write_report(results: list[dict]) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"leg-boundary-backtest-report-{ts}.json"
    # Atomic write: a process death mid-`write_text` can leave a truncated
    # report sitting at the real report name (already happened once — a
    # 298-byte stub is in the committed baseline). Write to a sibling temp
    # file, then `Path.replace`, which is atomic on Windows too (unlike a
    # bare os.rename onto an existing path). A partial write can then only
    # ever exist under the .tmp name, never as a report.
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(results, indent=2))
    tmp_path.replace(path)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Leg-boundary backtest (item 40)")
    parser.add_argument("--cycle", choices=list(CYCLE_WINDOWS) + ["all"], default="all")
    args = parser.parse_args()

    cycles = list(CYCLE_WINDOWS) if args.cycle == "all" else [args.cycle]
    results = [run_backtest(c) for c in cycles]
    path = write_report(results)
    print(f"Backtest report written to {path}")
    for r in results:
        print(f"  {r['cycle']}: {len(r['candidate_boundaries'])} candidates, "
              f"{len(r['confirmed_boundaries'])} confirmed "
              f"(composite_available={r['composite_available']}, btc_history_available={r['btc_history_available']})")
    print("Hybrid gate: manually compare the above against the known ~3-leg cycle structure before accepting.")


if __name__ == "__main__":
    main()
