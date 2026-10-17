"""Refresh the attention store from Wikipedia and CoinGecko (owner PC only).

The only fetcher for the attention store; request handlers read the store.
Exit codes: 0 at least one source stored data or answered ok, 2 no source ok,
1 every source errored. A source failure never aborts the others.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

if __package__ in (None, ""):  # direct invocation
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.data import cache  # noqa: E402
from api.data.attention.http_retry import describe_exc  # noqa: E402
from api.data.attention import (  # noqa: E402
    coingecko_attention, exchange_volume, reddit, registry, store, trends, universe_store, categories_store, wikipedia,
    xsearch)

WIKI_ARTICLES_PATH = Path(__file__).resolve().parents[1] / "data" / "wiki_articles.json"
DEFAULT_SYMBOLS = ("BTC", "ETH")
# Volume and Trends are opt-in (--sources): they reach ccxt/pytrends, and are not-probed until G.
DEFAULT_SOURCES = ("wikipedia", "coingecko", "universe")
# Consecutive rate-limited series after which the rest of a source is skipped (no more requests).
CIRCUIT_BREAKER_AFTER = 5
OUTCOME_ORDER = ("ok", "no-article", "rate-limited", "http-error", "insufficient-history", "other")


def _outcome(s) -> str:
    if s.state == "capped":
        return "rate-limited"
    if s.state == "unavailable":
        m = re.fullmatch(r"HTTP (\d{3})", s.reason or "")
        return f"http-error({m.group(1)})" if m else "other"
    return s.state if s.state in ("ok", "no-article", "insufficient-history") else "other"


def outcome_summary(series) -> str:
    """'ok 20, no-article 45, rate-limited 38': counts by outcome so 'N/M ok' explains the rest."""
    counts: dict[str, int] = {}
    for s in series:
        counts[_outcome(s)] = counts.get(_outcome(s), 0) + 1
    rank = lambda k: (OUTCOME_ORDER.index(k.split("(")[0]), k)  # noqa: E731
    return ", ".join(f"{k} {counts[k]}" for k in sorted(counts, key=rank))


def reason_summary(series, limit: int = 3) -> str:
    """Top distinct reasons of the failed series (class and HTTP status only), so a block is diagnosable."""
    counts: dict[str, int] = {}
    for s in series:
        if s.state != "ok" and s.reason:
            counts[s.reason] = counts.get(s.reason, 0) + 1
    top = sorted(counts, key=lambda k: (-counts[k], k))[:limit]
    return "; ".join(f"{k} x{counts[k]}" for k in top)


def _collect(symbols, fetch):
    """Run fetch(symbol) per symbol; after CIRCUIT_BREAKER_AFTER rate-limited in a row, skip the rest."""
    from api.data.attention.types import SourceSeries
    out, streak = [], 0
    for s in symbols:
        if streak >= CIRCUIT_BREAKER_AFTER:
            out.append(SourceSeries(out[-1].source, s.upper(), [], "capped", "skipped after repeated HTTP 429"))
            continue
        item = fetch(s)
        if item is None:
            continue
        streak = streak + 1 if item.state == "capped" else 0
        out.append(item)
    return out


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
    return _collect(symbols, lambda s: wikipedia.fetch_series(
        s, articles.get(s), client=client, today=today, sleep=sleep))


def _run_coingecko(symbols, client, today, sleep):
    top = coingecko_attention.fetch_top100(client=client, sleep=sleep)
    if top is None:
        raise RuntimeError(f"top100 unavailable: {coingecko_attention.LAST_FAILURE}")
    ids = {r["symbol"]: r["id"] for r in top}
    return _collect(symbols, lambda s: coingecko_attention.fetch_series(
        s, ids[s], client=client, today=today, sleep=sleep) if s in ids else None)


def _run_exchange_volume(symbols, client, today, sleep):
    ex = exchange_volume.make_binance()
    return [exchange_volume.fetch_binance_series(s, exchange=ex, today=today) for s in symbols]


def _run_hyperliquid_volume(symbols, client, today, sleep):
    from api.data import ccxt_adapter
    ex = ccxt_adapter._exchange()
    return [exchange_volume.fetch_hyperliquid_series(s, exchange=ex, today=today) for s in symbols]


def _run_trends(symbols, client, today, sleep):
    return [trends.fetch_series(s, s.lower(), today=today) for s in symbols]


def _run_universe(symbols, client, today, sleep):
    """Write today's top-100 snapshot; a failed fetch raises, leaving the old file untouched."""
    rows = coingecko_attention.fetch_top100_markets(client=client, sleep=sleep)
    if not rows:
        raise RuntimeError(f"markets unavailable: {coingecko_attention.LAST_FAILURE}")
    universe_store.write_snapshot(today.isoformat(), rows)
    return []


def _run_reddit(symbols, client, today, sleep):
    return [reddit.fetch_series(s, client=client, today=today) for s in symbols]


def _run_xsearch(symbols, client, today, sleep):
    if not xsearch.limits().live:
        e = xsearch.estimate(symbols, today=today)
        print(f"xsearch dry run: {e.planned_reads} reads, {e.usd:.2f} USD planned (X_LIVE off)")
    run = xsearch.RunBudget()
    return [xsearch.fetch_series(s, client=client, today=today, run=run) for s in symbols]


def _run_categories(symbols, client, today, sleep):
    """Write today's category snapshot (opt-in: --sources categories); a failed fetch raises."""
    from api.analytics.attention import discovery
    cfg = discovery.load_config()
    ids = [c["id"] for c in cfg["categories"]] + [i for i in cfg["exclude_category_ids"]]
    names = {c["id"]: c["name"] for c in cfg["categories"]}
    got = coingecko_attention.fetch_categories(ids, client=client, sleep=sleep)
    if not got:
        raise RuntimeError(f"categories unavailable: {coingecko_attention.LAST_FAILURE}")
    categories_store.write_snapshot(today.isoformat(), [
        {"id": k, "name": names.get(k, k), "symbols": v} for k, v in got.items()])
    return []


RUNNERS = {"universe": _run_universe, "wikipedia": _run_wikipedia, "coingecko": _run_coingecko,
           "exchange_volume": _run_exchange_volume, "hyperliquid_volume": _run_hyperliquid_volume,
           "trends": _run_trends, "reddit": _run_reddit, "xsearch": _run_xsearch,
           "categories": _run_categories}


def main(argv: list[str] | None = None, *, client: httpx.Client | None = None,
         today: date | None = None, sleep=time.sleep) -> int:
    parser = argparse.ArgumentParser(description="Refresh the attention store.")
    parser.add_argument("--dry-run", action="store_true", help="print the planned fetches; no network call, write nothing")
    parser.add_argument("--sources", help="comma list; default wikipedia,coingecko,universe")
    parser.add_argument("--symbols", help="comma list; default wiki_articles.json")
    args = parser.parse_args(argv)

    names = [s.strip() for s in args.sources.split(",")] if args.sources else list(DEFAULT_SOURCES)
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
                if name in ("universe", "categories"):
                    results[name] = "ok"
                    print(f"{name}: snapshot written")
                    continue
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
                      f"{' (dry run)' if args.dry_run else ''} [{outcome_summary(series)}]"
                      f"{' reasons: ' + reason_summary(series) if not ok and series else ''}")
            except Exception as exc:  # per-source isolation
                results[name] = "error"
                print(f"{name}: error {describe_exc(exc)}", file=sys.stderr)
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
        print(f"fatal: {describe_exc(exc)}", file=sys.stderr)
        sys.exit(1)
