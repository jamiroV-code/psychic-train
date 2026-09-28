"""Nightly narrative forward-archive (narrative dashboard RFC-4).

Run by `.github/workflows/narrative-snapshot.yml` once a day. For every
seed category it archives one point per source:

  pytrends/{keywords[0]}           Google Trends, "now 7-d" last point,
                                   separate UNBATCHED single-keyword top-up
                                   fetch (pre-RFC-3 scale, what /categories
                                   reads) — never the batched value
  pytrends-blended/{narrative id}  mean of ALL the narrative's chained
                                   keywords (v2 RFC-3, 2+ keywords only)
  reddit/{keywords[0]}             1-day mention count (skipped, no row,
                                   when REDDIT_CLIENT_ID/SECRET are unset —
                                   ADR-8 / Stage 0 decision C1)
  coingecko-narrative/{category}   trending count via the CURATED map
                                   (RFC-3 decision D1). The legacy
                                   `coingecko/{category}` series written by
                                   trigger.py is never touched here.
  exchange/...                     Hyperliquid snapshot via
                                   exchange_attention.run_daily() (already
                                   append-only)

It deliberately does NOT call `trigger.compute_narrative_categories`, so it
never writes the legacy CoinGecko count or trigger state; `/categories` only
sees more history on the keyword-keyed series it already reads.

Idempotency (decision C2, first observation wins): before every write the
script reads the target series and skips if a row for that date already
exists — including `backfilled` pytrends rows. `write_narrative_point`'s own
keep-last semantics are unchanged. pytrends is fetched via the adapter's
fetch helper (not `fetch_trend`, which writes internally) so the date check
can happen before the write: the primary keyword row comes from
`pytrends_adapter._fetch_live` (one unbatched call per keyword, same scale as
before RFC-3); the blended series comes from `fetch_trends_batched` (every
keyword, including each keywords[0], stays in the anchor-chained batch).

Every source is isolated: one provider failing prints its own summary line
and never aborts the run.

Exit codes: 0 = ran (some sources may be degraded); 2 = every source
unavailable (workflow warns); 1 = unexpected crash.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from api.analytics.narrative import exchange_attention, narrative_config
from api.data import cache, coingecko_adapter, pytrends_adapter, reddit_adapter

SOURCES = ("pytrends", "reddit", "coingecko-narrative", "exchange")
COINGECKO_NARRATIVE_SOURCE = "coingecko-narrative"


@dataclass
class SourceSummary:
    source: str
    written: int = 0
    skipped_existing: int = 0
    failed: int = 0
    total: int = 0
    reason: str | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return self.written > 0 or self.skipped_existing > 0

    def line(self) -> str:
        state = "ok" if self.available else "unavailable"
        text = f"{self.source}: {state}"
        if self.reason:
            text += f" ({self.reason})"
        text += (f" written={self.written} skipped-existing={self.skipped_existing}"
                 f" failed={self.failed} of {self.total}")
        return text


def utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def has_row(source: str, key: str, date: str) -> bool:
    existing = cache.read_narrative_series(source, key)
    return not existing.empty and (existing["date"].astype(str) == date).any()


def reddit_credentials_configured() -> bool:
    return bool(os.environ.get("REDDIT_CLIENT_ID")) and bool(os.environ.get("REDDIT_CLIENT_SECRET"))


def _keyword(cat: dict) -> str:
    kws = cat.get("keywords") or []
    return kws[0] if kws else cat["id"]


BLENDED_SOURCE = "pytrends-blended"


def _all_keywords(categories: list[dict]) -> list[str]:
    return [kw for cat in categories for kw in (cat.get("keywords") or [cat["id"]])]


def snapshot_pytrends_sources(categories: list[dict], today: str) -> list[SourceSummary]:
    """narrative-v2 RFC-3 (ADR-3): one anchor-chained batched fetch covering
    EVERY keyword of every narrative (5 terms per request, anchor reused).

    Writes, first-observation-wins:
      pytrends/{keywords[0]}           primary keyword (ADR-2 backward-compat key),
                                       from an unbatched `_fetch_live` top-up
      pytrends-blended/{narrative id}  mean of all the narrative's chained
                                       keyword values (2+ keywords only; only
                                       when every keyword is `ok` that day)
    """
    prim = SourceSummary("pytrends", total=len(categories))
    multi = [c for c in categories if len(c.get("keywords") or []) >= 2]
    blend_s = SourceSummary(BLENDED_SOURCE, total=len(multi))
    try:
        need_prim = [c for c in categories if not has_row("pytrends", _keyword(c), today)]
        need_blend = [c for c in multi if not has_row(BLENDED_SOURCE, c["id"], today)]
    except Exception as exc:
        prim.failed, blend_s.failed = len(categories), len(multi)
        prim.errors.append(repr(exc))
        return [prim, blend_s]
    prim.skipped_existing = len(categories) - len(need_prim)
    blend_s.skipped_existing = len(multi) - len(need_blend)
    if not need_prim and not need_blend:
        return [prim, blend_s]
    try:
        anchor = _keyword(categories[0]) if categories else None
        res = pytrends_adapter.fetch_trends_batched(_all_keywords(categories), anchor)
    except Exception as exc:
        prim.failed, blend_s.failed = len(need_prim), len(need_blend)
        prim.errors.append(repr(exc))
        return [prim, blend_s]
    as_of = res.as_of

    # Primary rows: separate unbatched top-up per keyword so pytrends/{kw}
    # keeps its pre-RFC-3 single-keyword scale (trigger.py / /categories
    # reads this key). A failed top-up skips the row — never falls back to
    # the batched, anchor-rescaled value.
    for cat in need_prim:
        kw = _keyword(cat)
        try:
            value, top_as_of = pytrends_adapter._fetch_live(kw)
            if value is None or top_as_of is None:
                prim.failed += 1
                prim.errors.append(f"{kw}: fetch-failed")
                continue
            if has_row("pytrends", kw, top_as_of):  # first wins; protects backfilled dates
                prim.skipped_existing += 1
                continue
            cache.write_narrative_point("pytrends", kw, top_as_of, float(value), source_status="fresh")
            prim.written += 1
        except Exception as exc:  # per-key isolation
            prim.failed += 1
            prim.errors.append(f"{kw}: {exc!r}")

    for cat in need_blend:
        try:
            cvs = [res.values.get(kw) for kw in cat["keywords"]]
            if as_of is None or any(cv is None or cv.status != "ok" for cv in cvs):
                blend_s.failed += 1
                bad = [kw for kw, cv in zip(cat["keywords"], cvs) if cv is None or cv.status != "ok"]
                blend_s.errors.append(f"{cat['id']}: not blended, keyword(s) not ok: {bad}")
                continue
            if has_row(BLENDED_SOURCE, cat["id"], as_of):
                blend_s.skipped_existing += 1
                continue
            value = pytrends_adapter.blend([cv.value for cv in cvs])
            cache.write_narrative_point(BLENDED_SOURCE, cat["id"], as_of, value, source_status="fresh")
            blend_s.written += 1
        except Exception as exc:
            blend_s.failed += 1
            blend_s.errors.append(f"{cat['id']}: {exc!r}")
    return [prim, blend_s]


def snapshot_reddit(categories: list[dict], today: str) -> SourceSummary:
    s = SourceSummary("reddit", total=len(categories))
    if not reddit_credentials_configured():
        s.reason = "credentials-not-configured"
        return s
    for cat in categories:
        kw = _keyword(cat)
        try:
            if has_row("reddit", kw, today):
                s.skipped_existing += 1
                continue
            result = reddit_adapter.fetch_mentions(kw)
            if result.status == "ok" and result.as_of == today:
                s.written += 1
            else:
                s.failed += 1
        except Exception as exc:
            s.failed += 1
            s.errors.append(f"{kw}: {exc!r}")
    return s


def snapshot_coingecko_narrative(categories: list[dict], today: str) -> SourceSummary:
    s = SourceSummary(COINGECKO_NARRATIVE_SOURCE, total=len(categories))
    try:
        trending = coingecko_adapter.fetch_trending()
    except Exception as exc:
        s.failed = len(categories)
        s.errors.append(repr(exc))
        return s
    # Only a live fetch dated today counts — a stale cached snapshot must
    # never be archived as today's observation.
    if trending.status != "ok" or trending.as_of != today:
        s.failed = len(categories)
        s.reason = f"trending-{trending.status}"
        return s
    counts: dict[str, int] = {cat["id"]: 0 for cat in categories}
    for symbol in trending.symbols:
        for cat_id in narrative_config.narratives_for_coin(symbol):
            if cat_id in counts:
                counts[cat_id] += 1
    for cat_id, count in counts.items():
        try:
            if has_row(COINGECKO_NARRATIVE_SOURCE, cat_id, today):
                s.skipped_existing += 1
                continue
            cache.write_narrative_point(COINGECKO_NARRATIVE_SOURCE, cat_id, today, float(count))
            s.written += 1
        except Exception as exc:
            s.failed += 1
            s.errors.append(f"{cat_id}: {exc!r}")
    return s


def snapshot_exchange(categories: list[dict], today: str) -> SourceSummary:
    s = SourceSummary("exchange", total=len(categories))
    try:
        before = {c["id"]: has_exchange_row(c["id"], today) for c in categories}
        result = exchange_attention.run_daily()
    except Exception as exc:
        s.failed = len(categories)
        s.errors.append(repr(exc))
        return s
    if result.status != "ok":
        s.failed = len(categories)
        s.reason = "snapshot-unavailable"
        return s
    for c in categories:
        if before[c["id"]]:
            s.skipped_existing += 1
        elif has_exchange_row(c["id"], today):
            s.written += 1
        else:
            s.failed += 1
    return s


def has_exchange_row(cat_id: str, date: str) -> bool:
    existing = cache.read_exchange_series(cat_id)
    return not existing.empty and (existing["date"].astype(str) == date).any()


RUNNERS = {
    "reddit": snapshot_reddit,
    "coingecko-narrative": snapshot_coingecko_narrative,
    "exchange": snapshot_exchange,
}


def run_snapshot(today: str | None = None) -> list[SourceSummary]:
    today = today or utc_today()
    cache.bootstrap_cache_dirs()
    categories = narrative_config.load_narratives()
    summaries: list[SourceSummary] = []
    try:
        summaries.extend(snapshot_pytrends_sources(categories, today))
    except Exception as exc:  # never abort the run for one source
        summaries.append(SourceSummary("pytrends", failed=len(categories), total=len(categories),
                                       errors=[repr(exc)]))
    for name in SOURCES:
        if name == "pytrends":
            continue
        try:
            summaries.append(RUNNERS[name](categories, today))
        except Exception as exc:  # belt-and-braces: never abort the run for one source
            summaries.append(SourceSummary(name, failed=len(categories), total=len(categories),
                                           errors=[repr(exc)]))
    return summaries


def exit_code(summaries: list[SourceSummary]) -> int:
    return 0 if any(s.available for s in summaries) else 2


def verify_report() -> list[str]:
    lines = []
    root = cache.CACHE_ROOT / "narrative"
    for src in ("pytrends", BLENDED_SOURCE, "reddit", COINGECKO_NARRATIVE_SOURCE):
        d = root / src
        for p in sorted(d.glob("*.parquet")) if d.exists() else []:
            df = cache.read_narrative_series(src, p.stem)
            latest = str(df["date"].max()) if not df.empty else "-"
            lines.append(f"{src}/{p.stem}: rows={len(df)} latest={latest}")
    d = root / "exchange"
    for p in sorted(d.glob("*.parquet")) if d.exists() else []:
        df = cache.read_exchange_series(p.stem)
        latest = str(df["date"].max()) if not df.empty else "-"
        lines.append(f"exchange/{p.stem}: rows={len(df)} latest={latest}")
    return lines or ["(no narrative archive rows)"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch into a temporary copy of the cache; the real cache is never written")
    parser.add_argument("--verify-only", action="store_true",
                        help="print per-series row counts and latest dates; no fetch")
    args = parser.parse_args(argv)

    if args.verify_only:
        for line in verify_report():
            print(line)
        return 0

    tmp_root: Path | None = None
    real_root = cache.CACHE_ROOT
    if args.dry_run:
        tmp_root = Path(tempfile.mkdtemp(prefix="narrative-dry-run-"))
        if (real_root / "narrative").exists():
            shutil.copytree(real_root / "narrative", tmp_root / "narrative")
        cache.CACHE_ROOT = tmp_root
    try:
        summaries = run_snapshot()
    finally:
        if tmp_root is not None:
            cache.CACHE_ROOT = real_root
            shutil.rmtree(tmp_root, ignore_errors=True)

    prefix = "[dry-run] " if args.dry_run else ""
    for s in summaries:
        print(prefix + s.line())
        for err in s.errors:
            print(f"{prefix}  {s.source} error: {err}")
    return exit_code(summaries)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # pragma: no cover
        print(f"snapshot_narrative: fatal: {exc!r}", file=sys.stderr)
        sys.exit(1)
