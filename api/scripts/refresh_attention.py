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
from api.scripts.attention_extra import reason_kind  # noqa: E402

WIKI_ARTICLES_PATH = Path(__file__).resolve().parents[1] / "data" / "wiki_articles.json"
DEFAULT_SYMBOLS = ("BTC", "ETH")
# Volume and Trends are opt-in (--sources): they reach ccxt/pytrends, and are not-probed until G.
DEFAULT_SOURCES = ("wikipedia", "coingecko", "universe", "signals")
# Consecutive rate-limited series after which the rest of a source is skipped (no more requests).
CIRCUIT_BREAKER_AFTER = 5
# Soft wall-clock per opt-in source (workflow step timeout is 8 min): stop cleanly, keep what was fetched.
SOURCE_TIME_BUDGET_S = 360
_clock = time.monotonic
OUTCOME_ORDER = ("ok", "no-article", "no-id", "rate-limited", "http-error", "insufficient-history", "other")


def _outcome(s) -> str:
    if s.state == "capped":
        return "rate-limited"
    if s.state == "unavailable":
        if s.reason == "no-id":
            return "no-id"
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


def _is_block(item) -> bool:
    """A provider block (HTTP status, provider class, rate limit, token/search failure); not a code error or data outcome."""
    return item.state == "unavailable" and reason_kind(item.reason or "") == "provider"


def _collect_guarded(symbols, fetch, source: str, *, budget: float | None = None):
    """Like _collect for the opt-in sources: after CIRCUIT_BREAKER_AFTER provider blocks in a row, or once the soft
    time budget is spent, the rest are marked capped (rate-limited, never 0, never fetched); fetched series are kept."""
    from api.data.attention.types import SourceSeries
    budget = SOURCE_TIME_BUDGET_S if budget is None else budget
    start, out, streak, why = _clock(), [], 0, None
    for s in symbols:
        if why is None and _clock() - start >= budget:
            why = "time budget reached"
        if why is None and streak >= CIRCUIT_BREAKER_AFTER:
            why = "skipped after repeated provider failures"
        if why:
            out.append(SourceSeries(source, s.upper(), [], "capped", why))
            continue
        item = fetch(s)
        if item is None:
            continue
        if _is_block(item):
            streak += 1
        elif item.state in ("ok", "insufficient-history"):
            streak = 0
        out.append(item)
    return out


def _universe_rows() -> list[dict]:
    """Rows of the latest universe snapshot minus stablecoins and wrapped coins; [] when there is no snapshot."""
    snap = universe_store.read_latest()
    rows = snap.get("coins") if snap else None
    if not isinstance(rows, list):
        return []
    skip = coingecko_attention.STABLECOIN_SYMBOLS | coingecko_attention.WRAPPED_SYMBOLS
    return [r for r in rows if isinstance(r, dict) and r.get("symbol") and str(r["symbol"]).upper() not in skip]


def _symbols(arg: str | None) -> list[str]:
    """--symbols wins; else the universe snapshot; else the wiki_articles.json keys; else DEFAULT_SYMBOLS."""
    if arg:
        return [s.strip().upper() for s in arg.split(",") if s.strip()]
    rows = _universe_rows()
    if rows:
        return list(dict.fromkeys(str(r["symbol"]).upper() for r in rows))
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
    """Ids from the universe snapshot rows (today's top 100 only when there is no snapshot); no id = counted no-id."""
    from api.data.attention.types import SourceSeries
    rows = _universe_rows()
    if not rows:
        rows = coingecko_attention.fetch_top100(client=client, sleep=sleep)
        if rows is None:
            raise RuntimeError(f"top100 unavailable: {coingecko_attention.LAST_FAILURE}")
    ids: dict[str, str] = {}
    for r in rows:
        ids.setdefault(str(r["symbol"]).upper(), r.get("id"))
    return _collect(symbols, lambda s: coingecko_attention.fetch_series(
        s, ids[s], client=client, today=today, sleep=sleep) if ids.get(s) else SourceSeries(
        "coingecko", s, [], "unavailable", "no-id"))


def _run_exchange_volume(symbols, client, today, sleep):
    ex = exchange_volume.make_binance()
    return [exchange_volume.fetch_binance_series(s, exchange=ex, today=today) for s in symbols]


def _run_hyperliquid_volume(symbols, client, today, sleep):
    from api.data import ccxt_adapter
    from api.data import hyperliquid_narrative_adapter as hl
    snap = hl.fetch_daily_market_snapshot(ccxt_adapter._exchange())  # one fetch_tickers for every symbol
    return [exchange_volume.fetch_hyperliquid_series(s, today=today, snapshot=lambda _ex: snap) for s in symbols]


def _run_trends(symbols, client, today, sleep):
    return _collect_guarded(symbols, lambda s: trends.fetch_series(s, s.lower(), today=today), "trends")


def _run_universe(symbols, client, today, sleep):
    """Write today's top-100 snapshot; a failed fetch raises, leaving the old file untouched."""
    rows = coingecko_attention.fetch_top100_markets(client=client, sleep=sleep)
    if not rows:
        raise RuntimeError(f"markets unavailable: {coingecko_attention.LAST_FAILURE}")
    universe_store.write_snapshot(today.isoformat(), rows)
    return []


def _run_reddit(symbols, client, today, sleep):
    session = reddit.Session()  # one OAuth token per run
    return _collect_guarded(
        symbols, lambda s: reddit.fetch_series(s, client=client, today=today, session=session), "reddit")


def _run_xsearch(symbols, client, today, sleep):
    if not xsearch.limits().live:
        e = xsearch.estimate(symbols, today=today)
        print(f"xsearch dry run: {e.planned_reads} reads, {e.usd:.2f} USD planned (X_LIVE off)")
    run = xsearch.RunBudget()
    return [xsearch.fetch_series(s, client=client, today=today, run=run) for s in symbols]


def _run_categories(symbols, client, today, sleep):
    """Write today's category snapshot (opt-in: --sources categories); a failed fetch raises. The ids are the old
    category ids of the narrative id map (a seeding hint; nothing scores from them) plus `exclude_category_ids`."""
    from api.analytics.attention import discovery, narratives
    cfg = discovery.load_config()
    id_map = narratives.load_id_map()
    ids = list(id_map) + [i for i in cfg["exclude_category_ids"] if i not in id_map]
    names = {k: v["name"] for k, v in id_map.items()}
    got = coingecko_attention.fetch_categories(ids, client=client, sleep=sleep)
    if not got:
        raise RuntimeError(f"categories unavailable: {coingecko_attention.LAST_FAILURE}")
    categories_store.write_snapshot(today.isoformat(), [
        {"id": k, "name": names.get(k, k), "symbols": v} for k, v in got.items()])
    return []


def _run_signals(symbols, client, today, sleep):
    """Freeze today's Discovery signal (opt-in/last default). Never raises into the run: see main()."""
    from api.analytics.attention import signal_snapshots
    return signal_snapshots.take_snapshot(today)


RUNNERS = {"universe": _run_universe, "wikipedia": _run_wikipedia, "coingecko": _run_coingecko,
           "exchange_volume": _run_exchange_volume, "hyperliquid_volume": _run_hyperliquid_volume,
           "trends": _run_trends, "reddit": _run_reddit, "xsearch": _run_xsearch,
           "categories": _run_categories, "signals": _run_signals}


def _snapshot_signals(run, symbols, client, today, sleep) -> None:
    """One `signals:` line; a failure is logged and swallowed. It is not counted in `results`, so the exit code
    is the same with or without it (a stale snapshot is not worth a red refresh). The workflow verify step only
    parses lines of the sources it lists, so this line cannot turn the job red."""
    try:
        res = run(symbols, client, today, sleep)
    except Exception as exc:
        print(f"signals: error {describe_exc(exc)}", file=sys.stderr)
        return
    counts: dict[str, int] = {}
    for r in res:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"signals: {', '.join(f'{n} {k}' for k, n in counts.items())}")
    for r in res:
        if r["status"] == "config-changed":
            print(f"signals: warning window {r['window']} config changed since the stored snapshot "
                  f"({r['stored_hash']} -> {r['current_hash']}); stored record kept", file=sys.stderr)


def main(argv: list[str] | None = None, *, client: httpx.Client | None = None,
         today: date | None = None, sleep=time.sleep) -> int:
    parser = argparse.ArgumentParser(description="Refresh the attention store.")
    parser.add_argument("--dry-run", action="store_true", help="print the planned fetches; no network call, write nothing")
    parser.add_argument("--sources", help="comma list; default wikipedia,coingecko,universe,signals")
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
            if name == "signals":
                print("signals: dry run, would snapshot windows 7,30,90 (no network call, nothing written)")
                continue
            print(f"{name}: dry run, would fetch {len(symbols)} symbols (no network call, nothing written)")
        return 0
    own = client is None
    client = client or httpx.Client(follow_redirects=True)
    results: dict[str, str] = {}
    try:
        for name in names:
            if name == "signals":
                _snapshot_signals(RUNNERS[name], symbols, client, today, sleep)
                continue
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
    if not results:  # signals only: never fails the run
        return 0
    if results and all(v == "error" for v in results.values()):
        return 1
    return 0 if any(v == "ok" for v in results.values()) else 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:
        print(f"fatal: {describe_exc(exc)}", file=sys.stderr)
        sys.exit(1)
