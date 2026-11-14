"""Print an owner-applied narrative placement; writes nothing and calls no provider."""
from __future__ import annotations

import argparse
import json
import sys

from api.analytics.attention import narratives
from api.data.attention import onboarding_store, trends_keywords, web_queries


def main(argv: list[str] | None = None, *, out=None, err=None) -> int:
    out, err = out or sys.stdout, err or sys.stderr
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbol")
    parser.add_argument("narrative")
    args = parser.parse_args(argv)
    if not narratives.SYMBOL_RE.fullmatch(args.symbol) or not narratives.ID_RE.fullmatch(args.narrative):
        print("refused: invalid symbol or narrative", file=err)
        return 2
    try:
        document = narratives.load_narratives()
        if args.narrative not in {n["id"] for n in document["narratives"]}:
            raise ValueError("unknown narrative")
        if args.symbol in {c["symbol"] for n in document["narratives"] for c in n["coins"]}:
            raise ValueError("already placed")
        ledger, _ = onboarding_store.read_ledger()
        if ledger is None or not any(e["symbol"] == args.symbol and e["state"] == "member"
                                     for e in ledger["coins"].values()):
            raise ValueError("membership required")
        queries = web_queries.load_merged(placed_symbols=[args.symbol])
        keywords = trends_keywords.load_merged()
        if args.symbol not in queries.coins or trends_keywords.keyword_status(keywords, args.symbol) not in ("topic", "term"):
            raise ValueError("source entries required")
    except (OSError, ValueError):
        print("refused: valid narrative, unplaced member, queries and usable keyword required", file=err)
        return 2
    print(f"Paste into the coins list of {args.narrative} in attention_narratives.json.", file=out)
    print("Property checks: test_narratives, test_web_queries, test_trends_keywords; no count-pin edit needed.", file=out)
    print(json.dumps({"symbol": args.symbol, "primary": True}), file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
