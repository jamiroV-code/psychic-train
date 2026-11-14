"""Reverse one automatic onboarding name (T223 O4, D-31). Owner tool; no network.

Run from the repo root: uv run --project api python -m api.scripts.onboarding_reverse SYMBOL SOURCE
SOURCE is one of wikipedia, trends, reddit_x. Removes that symbol's entry from the bot overlay, appends a
`reversed` line to today's onboarding log, and prints a paste-ready `blocked_sources` value for
api/data/coin_onboarding.json so the resolver never re-applies it (the owner applies it; bot files never carry
owner edits). A coin placed in a narrative is refused: its loaders need an entry, so move the name into the owner
file instead. A stored series pulled with the old name is not purged (first write wins in the store).
Exit 0 done, 1 nothing to reverse, 2 bad argument or placed coin.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from api.data.attention import onboarding_settings, onboarding_store, trends_keywords, web_queries

OVERLAYS = {"wikipedia": "wiki_articles_auto.json", "trends": trends_keywords.OVERLAY_NAME,
            "reddit_x": web_queries.OVERLAY_NAME}


def main(argv: list[str] | None = None, *, out=None, err=None, today: str | None = None) -> int:
    out, err = out or sys.stdout, err or sys.stderr
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("symbol")
    ap.add_argument("source")
    args = ap.parse_args(argv)
    sym, source = args.symbol, args.source
    if not trends_keywords.SYMBOL_RE.fullmatch(sym) or source not in OVERLAYS:
        print(f"bad argument: SYMBOL must match {trends_keywords.SYMBOL_RE.pattern}, SOURCE one of "
              f"{', '.join(OVERLAYS)}", file=err)
        return 2
    if sym in web_queries.placed_symbols():
        print("refused: the coin is placed in a narrative; copy its name into the owner file instead", file=err)
        return 2
    doc = onboarding_store.read_json(OVERLAYS[source]) or {"entries": {}}
    previous = (doc.get("entries") or {}).pop(sym, None)
    if previous is None:
        print("nothing to reverse: no automatic entry for this symbol and source", file=err)
        return 1
    day = today or datetime.now(timezone.utc).date().isoformat()
    onboarding_store.write_json(OVERLAYS[source], doc)
    onboarding_store.append_log(day, [{"source": source, "action": "reversed", "symbol": sym, "previous": previous}])
    settings, _ = onboarding_settings.safe_load()
    blocked = dict(settings.blocked_sources) if settings else {}
    blocked[sym] = sorted({*blocked.get(sym, ()), source})
    print("reversed; paste this value as \"blocked_sources\" in api/data/coin_onboarding.json:", file=out)
    print(json.dumps({k: list(v) for k, v in sorted(blocked.items())}), file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
