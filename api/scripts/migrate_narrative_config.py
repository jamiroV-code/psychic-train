"""One-time migration (narrative-v2 RFC-2, ADR-2): merge
`api/data/narrative_categories.json` (seed narratives) and
`api/data/narrative_category_map.json` (coin -> narrative) into
`api/data/narratives.json`. Run once; the output is committed. Not a runtime
step. Refuses to overwrite an existing narratives.json unless --force.

    uv run --project api python api/scripts/migrate_narrative_config.py

Coins mapped to a category that is not a seed (the grandfathered
BTC -> store-of-value legacy entry) are reported and dropped — they never
appeared on /history, which only lists seed categories.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"

COMMENT = (
    "How to edit narratives: this file is the ONLY place to add, rename, remove or re-coin a narrative "
    "for /api/narrative/history, the /narrative page, the nightly snapshot and the pytrends backfill. "
    "Each entry: id (lowercase slug, the permanent key archived history is stored under), label "
    "(display name, safe to rename), keywords (non-empty; the FIRST keyword is the pytrends/reddit "
    "archive key), coins (UPPERCASE tickers), enabled (true/false). No restart needed: the API re-reads "
    "this file when it changes on disk. Invalid entries (empty label, duplicate id, bad id) are skipped "
    "with a logged warning; a broken file keeps the last-known-good version. Renaming a label never "
    "affects history. Removing an entry or setting enabled=false hides it but keeps its archived history "
    "under the old id; re-adding the same id brings it back. This file does NOT affect "
    "/api/narrative/categories or /screener (frozen legacy map in api/analytics/narrative/mapping.py)."
)


def migrate(categories_path: Path, map_path: Path) -> tuple[dict, list[str]]:
    seeds = json.loads(categories_path.read_text(encoding="utf-8"))["seed_categories"]
    cmap = json.loads(map_path.read_text(encoding="utf-8"))["map"]
    seed_ids = [s["id"] for s in seeds]
    dropped = [f"{sym} -> {cid}" for sym, cid in cmap.items() if cid not in seed_ids]
    narratives = [
        {
            "id": s["id"],
            "label": s["label"],
            "keywords": list(s["keywords"]),
            "coins": [sym for sym, cid in cmap.items() if cid == s["id"]],
            "enabled": True,
        }
        for s in seeds
    ]
    return {"_comment": COMMENT, "version": 2, "narratives": narratives}, dropped


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, default=DATA / "narratives.json")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)
    if args.out.exists() and not args.force:
        print(f"{args.out} already exists; pass --force to overwrite")
        return 1
    doc, dropped = migrate(DATA / "narrative_categories.json", DATA / "narrative_category_map.json")
    args.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}: {len(doc['narratives'])} narratives, "
          f"{sum(len(n['coins']) for n in doc['narratives'])} coins")
    for d in dropped:
        print(f"dropped (not a seed category): {d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
