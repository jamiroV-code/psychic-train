"""Nightly chain-growth archive (chain-growth RFC-3).

Run by `.github/workflows/chain-growth-snapshot.yml` once a day. For every
live chain in `api/data/chains.json` it fetches the FULL history from
growthepie (active_addresses, transactions) and, where configured, the L2BEAT
`range=max` transactions cross-check, then merges each series into
`api/data/cache/onchain/{source}/{chain_id}/{metric}.parquet` with the
revision window in `cache.merge_onchain_series`. Because every run fetches the
full series, the first run is the backfill; there is no separate backfill
script (`--only` refills chosen chains by hand).

Chains whose metrics have `source: "none"` (solana, bnb, tron) are skipped
before any fetch and never get a file. Requests are spaced by
REQUEST_SPACING_SECONDS (injectable `sleep`, stubbed in tests). Each
(source, chain, metric) series is isolated: a failure prints its own line and
never aborts the run.

Exit codes: 0 = at least one series ok; 2 = every attempted series
unavailable (workflow warns); 1 = unexpected crash.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from api.data import cache, growthepie_adapter, l2beat_adapter
from api.data.chain_growth_config import load_chains

REQUEST_SPACING_SECONDS = 6.0
GROWTHEPIE_METRICS = ("active_addresses", "transactions")
L2BEAT_METRIC = "transactions"


@dataclass
class SeriesSummary:
    source: str
    chain_id: str
    metric: str
    ok: bool
    reason: str | None = None
    inserted: int = 0
    revised: int = 0
    drift: int = 0
    rows: int = 0
    first: str | None = None
    last: str | None = None

    @property
    def key(self) -> str:
        return f"{self.source}/{self.chain_id}/{self.metric}"

    def line(self) -> str:
        if not self.ok:
            return f"{self.key}: unavailable ({self.reason or 'unknown'})"
        return (f"{self.key}: ok inserted={self.inserted} revised={self.revised} drift={self.drift}"
                f" rows={self.rows} first={self.first or '-'} last={self.last or '-'}")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _merge(source: str, chain_id: str, metric: str, points: list[tuple[str, float]],
           today: str, now_iso: str, window_days: int) -> SeriesSummary:
    res = cache.merge_onchain_series(source, chain_id, metric, points, today=today,
                                     now_utc=now_iso, window_days=window_days)
    stored = cache.read_onchain_series(source, chain_id, metric)
    return SeriesSummary(
        source, chain_id, metric, ok=True, inserted=res.inserted, revised=res.revised,
        drift=res.out_of_window_drift, rows=len(stored),
        first=str(stored["date"].min()) if len(stored) else None,
        last=str(stored["date"].max()) if len(stored) else None,
    )


def run_snapshot(*, now: datetime | None = None, only: set[str] | None = None,
                 window_days: int = cache.ONCHAIN_REVISION_WINDOW_DAYS,
                 sleep: Callable[[float], None] = time.sleep,
                 spacing: float = REQUEST_SPACING_SECONDS) -> tuple[list[SeriesSummary], list[str]]:
    """Returns (series summaries, skipped-chain lines)."""
    now = (now or utc_now()).astimezone(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    summaries: list[SeriesSummary] = []
    skipped: list[str] = []
    requests_made = 0

    def spaced() -> None:
        nonlocal requests_made
        if requests_made:
            sleep(spacing)
        requests_made += 1

    for chain in load_chains():
        if only is not None and chain.id not in only:
            continue
        if not chain.enabled:
            skipped.append(f"{chain.id}: skipped (disabled)")
            continue
        live = False
        for metric in GROWTHEPIE_METRICS:
            spec = chain.metric(metric)
            if spec is None:
                continue
            if spec.source != "growthepie":
                skipped.append(f"{chain.id}/{metric}: skipped ({spec.unavailable_reason or 'source-unavailable'})")
                continue
            live = True
            try:
                spaced()
                series = growthepie_adapter.fetch_chain_metric(spec.source_key, metric)
                if series.status != "ok" or not series.points:
                    summaries.append(SeriesSummary("growthepie", chain.id, metric, ok=False,
                                                   reason=series.reason or series.status))
                    continue
                summaries.append(_merge("growthepie", chain.id, metric, series.points, today, now_iso, window_days))
            except Exception as exc:  # per-series isolation
                summaries.append(SeriesSummary("growthepie", chain.id, metric, ok=False, reason=f"error: {exc!r}"))
        if chain.cross_check is not None and live:
            try:
                spaced()
                act = l2beat_adapter.fetch_activity(chain.cross_check.source_key, "max")
                if act.status != "ok" or not act.points:
                    summaries.append(SeriesSummary("l2beat", chain.id, L2BEAT_METRIC, ok=False,
                                                   reason=act.reason or act.status))
                else:
                    pts = [(p.date, float(p.count)) for p in act.points]
                    summaries.append(_merge("l2beat", chain.id, L2BEAT_METRIC, pts, today, now_iso, window_days))
            except Exception as exc:
                summaries.append(SeriesSummary("l2beat", chain.id, L2BEAT_METRIC, ok=False, reason=f"error: {exc!r}"))
    return summaries, skipped


def exit_code(summaries: list[SeriesSummary]) -> int:
    return 0 if any(s.ok for s in summaries) else 2


def verify_report() -> list[str]:
    root = cache.CACHE_ROOT / "onchain"
    lines: list[str] = []
    for p in sorted(root.glob("*/*/*.parquet")) if root.exists() else []:
        source, chain_id, metric = p.parent.parent.name, p.parent.name, p.stem
        df = cache.read_onchain_series(source, chain_id, metric)
        if df.empty:
            lines.append(f"{source}/{chain_id}/{metric}: rows=0")
            continue
        lines.append(f"{source}/{chain_id}/{metric}: rows={len(df)} first={df['date'].min()} "
                     f"last={df['date'].max()} revised={int(df['revised'].sum())} "
                     f"last_as_of={df['as_of_utc'].max()}")
    return lines or ["(no chain-growth archive rows)"]


def main(argv: list[str] | None = None, *, sleep: Callable[[float], None] = time.sleep) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch into a temporary copy of the cache; the real cache is never written")
    parser.add_argument("--verify-only", action="store_true",
                        help="print per-series rows / first / last / revised; no fetch")
    parser.add_argument("--only", default=None, help="comma-separated chain ids to run (e.g. ethereum,base)")
    parser.add_argument("--window-days", type=int, default=cache.ONCHAIN_REVISION_WINDOW_DAYS,
                        help="revision window in days (default %(default)s)")
    args = parser.parse_args(argv)
    if args.window_days < 0:
        parser.error("--window-days must be >= 0")

    if args.verify_only:
        for line in verify_report():
            print(line)
        return 0

    only = {c.strip() for c in args.only.split(",") if c.strip()} if args.only else None

    tmp_root: Path | None = None
    real_root = cache.CACHE_ROOT
    if args.dry_run:
        tmp_root = Path(tempfile.mkdtemp(prefix="chain-growth-dry-run-"))
        if (real_root / "onchain").exists():
            shutil.copytree(real_root / "onchain", tmp_root / "onchain")
        cache.CACHE_ROOT = tmp_root
    try:
        summaries, skipped = run_snapshot(only=only, window_days=args.window_days, sleep=sleep)
    finally:
        if tmp_root is not None:
            cache.CACHE_ROOT = real_root
            shutil.rmtree(tmp_root, ignore_errors=True)

    prefix = "[dry-run] " if args.dry_run else ""
    for line in skipped:
        print(prefix + line)
    for s in summaries:
        print(prefix + s.line())
    return exit_code(summaries)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # pragma: no cover
        print(f"snapshot_chain_growth: fatal: {exc!r}", file=sys.stderr)
        sys.exit(1)
