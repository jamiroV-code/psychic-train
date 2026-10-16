"""Refresh the attention store from Wikipedia and CoinGecko (owner PC only).

The only fetcher for the attention store; request handlers read the store.
Exit codes: 0 at least one source stored data or answered ok, 2 no source ok,
1 every source errored. A source failure never aborts the others.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

if __package__ in (None, ""):  # direct invocation
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.data import cache  # noqa: E402
from api.data.attention import coingecko_attention, registry, store, wikipedia  # noqa: E402

WIKI_ARTICLES_PATH = Path(__file__).resolve().parents[1] / "data" / "wiki_articles.json"
DEFAULT_SYMBOLS = ("BTC", "ETH")


def _symbols(arg: str | None) -> list[str]:
    if arg:
        return [s.strip().upper() for s in arg.split(",") if s.strip()]
    try:
        return list(json.loads(WIKI_ARTICLES_PATH.read_text()))
    except (OSError, ValueError):
        return list(DEFAULT_SYMBOLS)


def _run_wikipedia(symbols, client, today, sleep):
    try:
        articles = json.loads(WIKI_ARTICLES_PATH.read_text())
    except (OSError, ValueError):
        articles = {}
    return [wikipedia.fetch_series(s, articles.get(s), client=client, today=today, sleep=sleep)
            for s in symbols]


def _run_coingecko(symbols, client, today, sleep):
    top = coingecko_attention.fetch_top100(client=client, sleep=sleep)
    if top is None:
        raise RuntimeError("top100 unavailable")
    ids = {r["symbol"]: r["id"] for r in top}
    out = []
    for s in symbols:
        if s not in ids:
            continue
        out.append(coingecko_attention.fetch_series(s, ids[s], client=client, today=today, sleep=sleep))
    return out


RUNNERS = {"wikipedia": _run_wikipedia, "coingecko": _run_coingecko}


def main(argv: list[str] | None = None, *, client: httpx.Client | None = None,
         today: date | None = None, sleep=time.sleep) -> int:
    parser = argparse.ArgumentParser(description="Refresh the attention store.")
    parser.add_argument("--dry-run", action="store_true", help="print the planned fetches; no network call, write nothing")
    parser.add_argument("--sources", help="comma list; default all")
    parser.add_argument("--symbols", help="comma list; default wiki_articles.json")
    args = parser.parse_args(argv)

    names = [s.strip() for s in args.sources.split(",")] if args.sources else list(registry.FETCHERS)
    unknown = [n for n in names if n not in RUNNERS]
    if unknown:
        print(f"unknown source: {', '.join(unknown)}", file=sys.stderr)
        return 1
    today = today or datetime.now(timezone.utc).date()
    symbols = _symbols(args.symbols)
    if args.dry_run:
        for name in names:
            print(f"{name}: dry run, would fetch {len(symbols)} symbols (no network call, nothing written)")
        return 0
    own = client is None
    client = client or httpx.Client(follow_redirects=True)
    results: dict[str, str] = {}
    try:
        for name in names:
            try:
                series = RUNNERS[name](symbols, client, today, sleep)
                written = 0
                if not args.dry_run:
                    for s in series:
                        if s.state in ("ok", "insufficient-history"):
                            written += store.write_series(s, today=today)
                ok = sum(1 for s in series if s.state == "ok")
                failed = series and all(
                    s.state == "unavailable" and s.reason != "empty response" for s in series)
                results[name] = "ok" if ok else ("error" if failed else "empty")
                print(f"{name}: {ok}/{len(series)} ok, {written} rows written"
                      f"{' (dry run)' if args.dry_run else ''}")
            except Exception as exc:  # per-source isolation
                results[name] = "error"
                print(f"{name}: error {type(exc).__name__}", file=sys.stderr)
    finally:
        if own:
            client.close()
    if results and all(v == "error" for v in results.values()):
        return 1
    return 0 if any(v == "ok" for v in results.values()) else 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:
        print(f"fatal: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)
