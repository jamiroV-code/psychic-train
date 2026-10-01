"""Cache warmer for the 5 primary FRED series (ADR-2 / RFC-002).

Fetches full history for WALCL, TGA, RRP, RESERVES and BROAD_DOLLAR through
the existing keyless `fredgraph.csv` path and writes each to
`cache/liquidity/{series_id}.parquet`. Idempotent: `fred_adapter.fetch_series`
is cache-first (6h TTL) and overwrites the series file per refresh, so running
this repeatedly is safe — an unchanged series rewrites byte-identical content.

No CLI arguments: the CSV export always returns FULL history (there is no
date filtering to expose), and FRED is the only source here.

Exit codes: 0 = at least one series `ok` (`stale`/`unavailable` do NOT
count); 2 = ran but nothing was ok (workflow warns); 1 = unexpected crash,
or every series raised.

Run: `uv run --project api python -m api.scripts.backfill_primaries`
"""
from __future__ import annotations

# Scripts are run as files (`python api/scripts/<name>.py`), so `sys.path[0]`
# is this directory, not the repo root, and `import api.*` cannot resolve.
# `pythonpath = [".."]` in pyproject.toml is a pytest setting and does not
# apply here. Put the repo root on the path before importing anything from
# `api`, so the script works from any working directory.
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import argparse  # noqa: E402
import time  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from typing import Callable  # noqa: E402

from api.data import fred_adapter  # noqa: E402

PRIMARY_SERIES = {
    "walcl": fred_adapter.WALCL,
    "tga": fred_adapter.TGA,
    "rrp": fred_adapter.RRP,
    "reserves": fred_adapter.RESERVES,
    "dollar_broad": fred_adapter.BROAD_DOLLAR,
}

# No rate tuning in this plan; kept injectable so tests stay instant.
REQUEST_SPACING_SECONDS = 0.0


@dataclass
class SeriesSummary:
    label: str
    series_id: str
    ok: bool
    status: str
    rows: int = 0
    first: str = "n/a"
    last: str = "n/a"

    def line(self) -> str:
        return (
            f"{self.label:<13} {self.series_id:<10} status={self.status:<11} "
            f"rows={self.rows:<6} first={self.first:<10} last={self.last}"
        )


def _coverage(df) -> tuple[str, str]:
    if df.empty:
        return "n/a", "n/a"
    return str(df["date"].min().date()), str(df["date"].max().date())


def run_backfill(
    *,
    sleep: Callable[[float], None] = time.sleep,
    spacing: float = REQUEST_SPACING_SECONDS,
) -> list[SeriesSummary]:
    """Fetch every primary series. Per-series isolated: an exception records
    `status="error"` and the run continues."""
    summaries: list[SeriesSummary] = []
    for label, series_id in PRIMARY_SERIES.items():
        try:
            result = fred_adapter.fetch_series(series_id)
        except Exception as exc:  # per-series isolation (C3)
            summaries.append(SeriesSummary(label, series_id, ok=False, status="error"))
            print(f"{label:<13} {series_id:<10} status=error      {exc!r}", file=sys.stderr)
        else:
            first, last = _coverage(result.df)
            summaries.append(SeriesSummary(
                label, series_id, ok=result.status == "ok", status=result.status,
                rows=len(result.df), first=first, last=last,
            ))
        if spacing:
            sleep(spacing)
    return summaries


def exit_code(summaries: list[SeriesSummary]) -> int:
    if summaries and all(s.status == "error" for s in summaries):
        return 1
    if any(s.ok for s in summaries):
        return 0
    return 2


def backfill_all() -> list[SeriesSummary]:
    """Thin back-compat wrapper (no importers today; keeps the old name)."""
    return run_backfill()


def main(argv: list[str] | None = None, *, sleep: Callable[[float], None] = time.sleep) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # `[] if argv is None else argv` so a bare `main()` under pytest never
    # consumes pytest's own sys.argv (C5).
    parser.parse_args([] if argv is None else argv)
    summaries = run_backfill(sleep=sleep)
    for s in summaries:
        print(s.line())
    return exit_code(summaries)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # pragma: no cover
        print(f"backfill_primaries: fatal: {exc!r}", file=sys.stderr)
        sys.exit(1)
