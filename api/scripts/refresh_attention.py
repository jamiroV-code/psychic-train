"""Refresh the attention store from Wikipedia and CoinGecko (owner PC only).

The only fetcher for the attention store; request handlers read the store.
Exit codes: 0 at least one source stored data or answered ok, 2 no source ok,
1 every source errored. A source failure never aborts the others.
"""
from __future__ import annotations

import argparse
import json
import random
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
    coingecko_attention, exchange_volume, reddit, registry, store, trends, trends_keywords, trends_runs,
    universe_store,
    categories_store, coin_ledger, onboarding_settings, onboarding_store, wikipedia, xsearch)
from api.scripts.attention_extra import reason_kind  # noqa: E402
from api.scripts.trends_cli_common import PytrendsMissing, make_trendreq  # noqa: E402

WIKI_ARTICLES_PATH = Path(__file__).resolve().parents[1] / "data" / "wiki_articles.json"
DEFAULT_SYMBOLS = ("BTC", "ETH")
# Volume and Trends are opt-in (--sources): they reach ccxt/pytrends, and are not-probed until G.
# T223: `ledger` follows `universe` (it reads today's snapshot) and never decides the exit code (see main()).
DEFAULT_SOURCES = ("wikipedia", "coingecko", "universe", "ledger", "signals")
LEDGER_EVENTS = ("entered", "joined", "inactive", "returned", "removed")
# Consecutive rate-limited series after which the rest of a source is skipped (no more requests).
CIRCUIT_BREAKER_AFTER = 5
# Soft wall-clock per opt-in source (workflow step timeout is 8 min): stop cleanly, keep what was fetched.
SOURCE_TIME_BUDGET_S = 360
_clock = time.monotonic
# Trends (T100b): one request per coin, TRENDS_INTERVAL_S plus 0-2 s jitter apart; on HTTP 429 wait 30, 60, 120 s
# for the same coin, then it is capped; TRENDS_BREAKER_AFTER capped coins in a row stop the source. Its own budget:
# up to 75 coins do not fit SOURCE_TIME_BUDGET_S.
TRENDS_INTERVAL_S = 3.0
TRENDS_BACKOFF_S = (30, 60, 120)
# The breaker still bounds the loss if the budget or the waits change (T203: with the 780 s budget three coins of
# full backoff, 3 x 210 s = 630 s, can now trip it before the budget does).
TRENDS_BREAKER_AFTER = 3
# T203: 540 -> 780 s so about 92 keyworded coins at about 4 s per request are not cut (quality over speed). The workflow
# step limit is 18 min: 780 s + install ~60 s + one in-flight request ~60 s + store/archive/run-record ~60 s = ~960 s.
TRENDS_TIME_BUDGET_S = 780
# T197/T200: an `empty response` (an empty frame, not a 429 or an error) is retried once, AFTER the whole main pass
# (healthy coins are never sacrificed for retries), 10 s plus jitter apart, while the budget has room, at most
# TRENDS_MAX_RETRIES_PER_RUN per run.
TRENDS_EMPTY_RETRY_WAIT_S = 10
TRENDS_MAX_RETRIES_PER_RUN = 20
TRENDS_OUTCOMES = ("ok", "too-little-interest", "quiet-then-surge", "skipped-unqualified", "no-keyword", "non-daily",
                   "rate-limited", "insufficient-history", "time-budget")
TRENDS_RUN_OUTCOMES = ("ok", "too-little-interest", "quiet-then-surge", "no-keyword", "skipped-unqualified", "failed",
                       "capped", "time-budget")
_TRENDS_REASON_OUTCOME = {trends.TOO_LITTLE_INTEREST: "too-little-interest",
                          trends.QUIET_THEN_SURGE: "quiet-then-surge",
                          trends.WAITING_APPROVAL: "skipped-unqualified", "no keyword mapped": "no-keyword",
                          # pre-stage-2 run files and stored reasons keep reading as skipped-unqualified
                          "name-ambiguous: needs topic or qualified term": "skipped-unqualified",
                          "non-daily": "non-daily"}
# trends_keywords.keyword_status of a coin with no usable keyword -> its Trends reason (T180: existing strings kept).
MISSING_KEYWORD_REASON = {"no-entry": "no keyword mapped", "no-keyword": "no keyword mapped",
                          "skipped-unqualified": trends.WAITING_APPROVAL}
# Store mode per source; every source not listed keeps first-write-wins.
WRITE_MODES = {"trends": "replace-series"}
TRENDREQ_FACTORY = make_trendreq  # pytrends is imported on first use only; tests inject a fake
_jitter = lambda: random.uniform(0.0, 2.0)  # noqa: E731
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


def _band_member_ids() -> set[str]:
    """Coin ids the onboarding ledger holds as `member`; empty when there is no usable ledger."""
    led, _ = onboarding_store.read_ledger()
    return {cid for cid, e in led["coins"].items() if e["state"] == "member"} if led else set()


def _universe_rows() -> list[dict]:
    """Rows of the latest universe snapshot minus stablecoins and wrapped coins; [] when there is no snapshot.
    T223 cap: rank 1-100 plus ledger members at rank 101 to the exit band, so the 120-row snapshot does not add
    20 coins to every provider call. Rows without a rank (snapshots older than T223) are all kept."""
    snap = universe_store.read_latest()
    rows = snap.get("coins") if snap else None
    if not isinstance(rows, list):
        return []
    skip = coingecko_attention.STABLECOIN_SYMBOLS | coingecko_attention.WRAPPED_SYMBOLS
    settings, _ = onboarding_settings.safe_load()
    band = settings.exit_band_rank if settings else coin_ledger.TOP
    members: set[str] | None = None
    out = []
    for r in rows:
        if not (isinstance(r, dict) and r.get("symbol") and str(r["symbol"]).upper() not in skip):
            continue
        rank = r.get("rank")
        if isinstance(rank, int) and not isinstance(rank, bool) and rank > coin_ledger.TOP:
            if rank > band:
                continue
            members = _band_member_ids() if members is None else members
            if r.get("id") not in members:
                continue
        out.append(r)
    return out


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


def _wiki_articles() -> dict:
    """T223: the owner's wiki_articles.json plus the resolver overlay (the owner entry always wins); never raises."""
    from api.data.attention import onboarding_resolver
    try:
        owner = json.loads(WIKI_ARTICLES_PATH.read_text())
    except (OSError, ValueError):
        owner = {}
    return onboarding_resolver.merge_wiki(owner, onboarding_store.read_json(WIKI_OVERLAY))[0]


def _run_wikipedia(symbols, client, today, sleep):
    articles = _wiki_articles()
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


def _trends_outcome(s) -> str:
    if s.state in ("ok", "insufficient-history"):
        return s.state
    if s.state == "capped":
        return "time-budget" if s.reason == "time budget reached" else "rate-limited"
    r = s.reason or ""
    if r in _TRENDS_REASON_OUTCOME:
        return _TRENDS_REASON_OUTCOME[r]
    m = re.match(r"fetch-failed: (\w+)", r)
    return f"failed({m.group(1) if m else r})"


def trends_summary(series) -> str:
    """'ok 40, too-little-interest 3, ...' in TRENDS_OUTCOMES order, then the failures."""
    counts: dict[str, int] = {}
    for s in series:
        k = _trends_outcome(s)
        counts[k] = counts.get(k, 0) + 1
    order = lambda k: (TRENDS_OUTCOMES.index(k) if k in TRENDS_OUTCOMES else len(TRENDS_OUTCOMES), k)  # noqa: E731
    return ", ".join(f"{k} {counts[k]}" for k in sorted(counts, key=order))


def _trends_fetch_once(sym, term, client, today, calls, stats):
    calls[0] += 1
    return trends.fetch_alone(sym, term, client, today=today, stats=stats)


def _trends_fetch_429(sym, term, client, today, sleep, deadline, calls, stats):
    """fetch_alone with the 429 backoff: TRENDS_BACKOFF_S waits for the same coin, then `capped`. A wait that would
    end after `deadline` (the source's time budget) is not started: the coin is capped "time budget reached".
    `calls` (a one-item list) counts the requests sent; `stats` receives the last pull's series_stats."""
    from api.data.attention.types import SourceSeries
    item = _trends_fetch_once(sym, term, client, today, calls, stats)
    for wait in TRENDS_BACKOFF_S:
        if item.state != "capped":
            break
        if _clock() + wait > deadline:
            return SourceSeries("trends", sym, [], "capped", "time budget reached")
        sleep(wait)
        item = _trends_fetch_once(sym, term, client, today, calls, stats)
    return item


def _trends_fetch_coin(sym, term, client, today, sleep, deadline):
    """One coin of the main pass: the 429 backoff, no empty-response retry (that is deferred, see
    _trends_retry_empty). Returns (series, meta) with meta = attempts (requests sent), retried, stats."""
    calls, stats = [0], {}
    item = _trends_fetch_429(sym, term, client, today, sleep, deadline, calls, stats)
    return item, {"attempts": calls[0], "retried": False, "stats": dict(stats)}


def _trends_retry_empty(todo, out, metas, client, today, sleep, deadline):
    """The deferred pass: each coin of the main pass left at `empty response`, in main-pass order, is retried once
    with a single request (no 429 backoff), TRENDS_EMPTY_RETRY_WAIT_S plus jitter after the previous step. The
    budget is checked before each retry including its wait: one that does not fit is not started and the coin keeps
    `empty response` with meta["retry_skipped"] "retry-skipped-budget"; beyond TRENDS_MAX_RETRIES_PER_RUN it is
    "retry-skipped-cap". A 429 answer is recorded for that coin and ends the pass ("retry-skipped-rate-limit" for
    the rest)."""
    retries, ended = 0, False
    for s, kw in todo:
        item = out[s]
        if item.state != "unavailable" or item.reason != "empty response":
            continue
        if ended:
            metas[s]["retry_skipped"] = "retry-skipped-rate-limit"
        elif retries >= TRENDS_MAX_RETRIES_PER_RUN:
            metas[s]["retry_skipped"] = "retry-skipped-cap"
        else:
            wait = TRENDS_EMPTY_RETRY_WAIT_S + _jitter()
            if _clock() + wait > deadline:
                metas[s]["retry_skipped"] = "retry-skipped-budget"
                continue
            sleep(wait)
            retries += 1
            calls, stats = [metas[s]["attempts"]], {}
            retry = _trends_fetch_once(s, kw, client, today, calls, stats)
            metas[s].update({"attempts": calls[0], "retried": True, "stats": dict(stats)})
            out[s] = retry
            ended = retry.state == "capped"


_RUN_OUTCOME = {"rate-limited": "capped", "non-daily": "failed", "insufficient-history": "failed"}
_REASON_KEEP = re.compile(r"[^\w ():.,\-]")


def _run_coin_record(item, meta) -> dict:
    """One coin of the run file. The reason is the series reason (an exception class / HTTP status or a fixed
    label by construction), cleaned and cut to 80 characters as a second guard against any message text."""
    outcome = _trends_outcome(item)
    outcome = "failed" if outcome.startswith("failed(") else _RUN_OUTCOME.get(outcome, outcome)
    reason = item.reason or ""
    reason = reason.removeprefix("fetch-failed: ")
    if item.state == "insufficient-history":
        reason = "insufficient-history"
    reason = re.sub(r":{2,}", ":", _REASON_KEEP.sub("", reason))[:80] if outcome != "ok" else ""
    st = meta.get("stats") or {}
    return {"outcome": outcome, "reason": reason or None, "keyword_kind": meta.get("kind", "none"),
            "median": st.get("median"), "zero_share_pct": st.get("zero_share_pct"),
            "last7_vs_prior28_ratio": st.get("last7_vs_prior28_ratio"),
            "attempts": meta.get("attempts", 0), "retried": bool(meta.get("retried")),
            "retry_skipped": meta.get("retry_skipped"), "keyword": meta.get("keyword")}


def _pytrends_version() -> str | None:
    try:
        from importlib.metadata import version
        return version("pytrends")
    except Exception:  # noqa: BLE001 - evidence only: absent or unreadable metadata is just null
        return None


_utcnow = lambda: datetime.now(timezone.utc)
_stamp = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")
# Why the run file could not be written in the last _run_trends call (class only); main() turns it into the
# `store-failed` last line. None when it was written.
trends_run_error: str | None = None


def _run_trends(symbols, client, today, sleep):
    """One request per coin with only its keyword; writes the per-pull archive and the per-run outcome file
    (T197); the store write (replace-series) is done by main(). No-keyword, bare (unqualified) name-risk terms
    and a bad keyword file cost no request."""
    global trends_run_error
    from api.data.attention.types import SourceSeries
    trends_run_error = None
    started = _utcnow()
    km, bad = trends_keywords.safe_load_merged()
    out: dict[str, SourceSeries] = {}
    metas: dict[str, dict] = {}
    todo: list[tuple[str, str]] = []
    for s in dict.fromkeys(x.upper() for x in symbols):  # a repeated symbol costs one request
        status = trends_keywords.keyword_status(km, s)
        if status in ("topic", "term"):
            todo.append((s, km.keyword_for(s)))
            metas[s] = {"kind": status, "keyword": km.keyword_for(s)}   # D5: the keyword assigned and attempted
        else:
            out[s] = SourceSeries("trends", s, [], "unavailable", MISSING_KEYWORD_REASON.get(status, bad))
            metas[s] = {"kind": "term" if status == "skipped-unqualified" else "none"}
    if todo:
        start = today.toordinal() % len(todo)  # rotate so a budget stop does not always starve the same coins
        todo = todo[start:] + todo[:start]
        trendreq, why = None, "session-failed: no client"
        try:
            trendreq = TRENDREQ_FACTORY()
        except PytrendsMissing:
            why = "pytrends not installed"
        except Exception as exc:  # noqa: BLE001 - the class is reported, never the message
            why = f"session-failed: {trends.error_class(exc)}"
        if trendreq is None:
            for s, _ in todo:
                out[s] = SourceSeries("trends", s, [], "unavailable", why)
            todo = []
        t0, streak, stop, sent = _clock(), 0, None, False
        deadline = t0 + TRENDS_TIME_BUDGET_S
        for s, kw in todo:
            if stop is None and _clock() - t0 >= TRENDS_TIME_BUDGET_S:
                stop = "time budget reached"
            if stop is None and streak >= TRENDS_BREAKER_AFTER:
                stop = "skipped after repeated HTTP 429"
            if stop:
                out[s] = SourceSeries("trends", s, [], "capped", stop)
                continue
            if sent:
                sleep(TRENDS_INTERVAL_S + _jitter())
            sent = True
            item, meta = _trends_fetch_coin(s, kw, trendreq, today, sleep, deadline)
            metas[s].update(meta)
            if item.reason == "time budget reached":
                stop = item.reason
            streak = streak + 1 if item.state == "capped" else 0
            out[s] = item
        if trendreq is not None:
            _trends_retry_empty(todo, out, metas, trendreq, today, sleep, deadline)
    series = [out[s] for s in dict.fromkeys(x.upper() for x in symbols)]
    try:
        store.write_pull_archive("trends", today, series)
    except Exception as exc:  # the archive must not cost the live series
        print(f"trends archive: not written {trends.error_class(exc)}", file=sys.stderr)
    coins = {s.symbol: _run_coin_record(s, metas[s.symbol]) for s in series}
    retried = sum(1 for c in coins.values() if c["retried"])
    recovered = sum(1 for c in coins.values() if c["retried"] and c["outcome"] == "ok")
    skipped = sum(1 for c in coins.values() if c["retry_skipped"])
    try:  # evidence only: a failed write must not cost the live series (main() ends the source red)
        totals = {k: sum(1 for c in coins.values() if c["outcome"] == k) for k in TRENDS_RUN_OUTCOMES}
        trends_runs.append_run(today, {
            "run_started_utc": _stamp(started), "run_finished_utc": _stamp(_utcnow()),
            "pytrends_version": _pytrends_version(), "budget_s": TRENDS_TIME_BUDGET_S, "coins": coins,
            "totals": {**totals, "coins": len(coins), "retried": retried, "recovered": recovered,
                       "retry_skipped": skipped}})
    except Exception as exc:  # noqa: BLE001 - class only, never the message
        trends_run_error = trends.error_class(exc)
    retry_note = f", retried {retried} (recovered {recovered}, skipped {skipped})" if retried or skipped else ""
    print(f"trends detail: {trends_summary(series)}{retry_note}")
    return series


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
    category ids of the narrative id map (a seeding hint; nothing scores or excludes from them since U2)."""
    from api.analytics.attention import narratives
    id_map = narratives.load_id_map()
    ids = list(id_map)
    names = {k: v["name"] for k, v in id_map.items()}
    got = coingecko_attention.fetch_categories(ids, client=client, sleep=sleep)
    if not got:
        raise RuntimeError(f"categories unavailable: {coingecko_attention.LAST_FAILURE}")
    categories_store.write_snapshot(today.isoformat(), [
        {"id": k, "name": names.get(k, k), "symbols": v} for k, v in got.items()])
    led, _ = onboarding_store.read_ledger()
    if led is not None:
        from api.data.attention import narrative_proposals
        narrative_proposals.refresh(led)
    return []


def _run_signals(symbols, client, today, sleep):
    """Freeze today's Discovery signal (opt-in/last default). Never raises into the run: see main()."""
    from api.analytics.attention import signal_snapshots
    return signal_snapshots.take_snapshot(today)


def _run_ledger(symbols, client, today, sleep) -> str:
    """T223: advance the onboarding ledger from today's snapshot (seed it once when absent). No network call.
    Returns the fixed-token status after `ledger: `; never a name or id (those go to the sanitized log only)."""
    settings, _ = onboarding_settings.safe_load()
    if settings is None:
        return "unavailable settings"
    snap = universe_store.read_latest()
    if not snap:
        return "unavailable no snapshot"
    if snap.get("date") != today.isoformat():
        return "skipped, stale snapshot"
    if coin_ledger.band_rows(snap, settings.exit_band_rank) is None:
        return "unavailable short snapshot"
    led, state = onboarding_store.read_ledger()
    if state == "corrupt":
        return "unavailable corrupt ledger"
    day = snap["date"]
    if led is None:
        lost = onboarding_store.has_log_history()
        res = coin_ledger.seed(snap, settings)
        onboarding_store.write_ledger(res.ledger)
        onboarding_store.append_log(day, [{"source": "ledger", "action": "seeded", "coins": len(res.ledger["coins"]),
                                           "lost_progress": lost}])
        from api.data.attention import narrative_proposals
        narrative_proposals.refresh(res.ledger)
        if lost:
            print("ledger: warning re-seeded, probation progress lost", file=sys.stderr)
        return f"ok seeded {len(res.ledger['coins'])}"
    res = coin_ledger.advance(led, snap, settings)
    if res.status == "same-date":
        return "ok same-date, nothing changed"
    onboarding_store.write_ledger(res.ledger)
    coins = res.ledger["coins"]
    onboarding_store.append_log(day, [
        {"source": "ledger", "action": ev, "coin_id": cid,
         "symbol": coins.get(cid, led["coins"].get(cid, {})).get("symbol")} for ev, cid in res.events])
    from api.data.attention import narrative_proposals
    narrative_proposals.refresh(res.ledger)
    counts = {k: sum(1 for ev, _ in res.events if ev == k) for k in LEDGER_EVENTS}
    return "ok advanced" + "".join(f", {k} {n}" for k, n in counts.items() if n)


def _owner_rules() -> dict:
    from api.analytics.attention import discovery
    return discovery.load_config()["universe_rules"]


def _run_classify(symbols, client, today, sleep) -> str:
    """T223 O3: class for ledger coins whose class is unknown (watching first), at most classify_max_coins_per_run,
    paced like every CoinGecko call; stops at the first HTTP 429. Owner lists and confirmed classes are applied
    without a request. Only derived numbers are stored; stdout carries counts only."""
    from api.data.attention import coin_class
    settings, _ = onboarding_settings.safe_load()
    if settings is None:
        return "unavailable settings"
    led, state = onboarding_store.read_ledger()
    if led is None:
        return f"unavailable {'corrupt' if state == 'corrupt' else 'no'} ledger"
    rules = _owner_rules()
    day, log, coins = today.isoformat(), [], led["coins"]
    for cid, e in coins.items():
        cls, src = coin_class.resolve(e["symbol"], e["class"], rules, settings)
        if src != "auto" and (cls, src) != (e["class"], e["class_source"]):
            e.update({"class": cls, "class_source": src, "updated": day})
            log.append({"source": "classify", "action": "applied", "coin_id": cid, "symbol": e["symbol"],
                        "class": cls, "class_source": src})
        elif src == "auto" and e["class_source"] != "auto" and not (e["seeded"] and (e["class"], e["class_source"])
                                                                    == ("normal", "owner")):
            # The owner removed the list entry or confirmation: the old class is no longer trusted. A seeded coin
            # returns to its seed baseline (O7: normal, owner); any other coin is reclassified from scratch.
            restored = ("normal", "owner") if e["seeded"] else ("unknown", "auto")
            log.append({"source": "classify", "action": "pending" if restored[0] == "unknown" else "applied",
                        "coin_id": cid, "symbol": e["symbol"], "class": restored[0],
                        "previous": {"class": e["class"], "class_source": e["class_source"]}})
            e.update({"class": restored[0], "class_source": restored[1], "class_evidence": {}, "updated": day})
    todo = sorted((cid for cid, e in coins.items() if e["class"] == "unknown" and e["class_source"] == "auto"
                   and e["state"] in ("watching", "member")),
                  key=lambda c: (coins[c]["state"] != "watching", str(coins[c]["class_evidence"].get("checked") or ""), c))
    tried = known = 0
    stopped = False
    deadline = _clock() + ONBOARDING_TIME_BUDGET_S
    budget_stop = False
    for cid in todo[:settings.classify_max_coins_per_run]:
        if _clock() >= deadline:
            budget_stop = True
            break
        detail, st = coingecko_attention.fetch_coin_detail(cid, client=client, sleep=sleep)
        prices, pst = (None, "skipped") if detail is None else coingecko_attention.fetch_price_stats(
            cid, client=client, sleep=sleep)
        if "capped" in (st, pst):
            stopped = True
            break
        tried += 1
        evidence = ({**detail, "prices": prices} if detail and pst == "ok"
                    else {"categories": None, "error": st if detail is None else pst})
        cls, summary = coin_class.classify(coins[cid]["symbol"], evidence, settings)
        known += cls != "unknown"
        coins[cid].update({"class": cls, "class_evidence": {**summary, "checked": day}, "class_source": "auto",
                           "updated": day})
        log.append({"source": "classify", "action": "applied" if cls != "unknown" else "pending", "coin_id": cid,
                    "symbol": coins[cid]["symbol"], "class": cls})
    if log:
        onboarding_store.write_ledger(led)
        onboarding_store.append_log(day, log)
        from api.data.attention import narrative_proposals
        narrative_proposals.refresh(led)
    return f"ok {known}/{tried}" + (", stopped on HTTP 429" if stopped else ", time budget reached" if budget_stop else "")


WIKI_OVERLAY, QUERIES_OVERLAY, PENDING_FILE = "wiki_articles_auto.json", "attention_queries_auto.json", "pending.json"
ONBOARDING_TIME_BUDGET_S = 180  # per network step; three steps fit the owner-applied 12-minute workflow step


def _onboarding_document(name: str, key: str) -> dict:
    doc = onboarding_store.read_json(name) or {}
    return doc if isinstance(doc.get(key), dict) else {key: {}}


def _drop_overlay_entries(doc, dropped, source, led, pending, log, day) -> set[str]:
    """Only the refresh writer quarantines collisions. Read-only loaders never write. Returns the quarantined
    symbols so the same run does not resolve them again and overwrite their pending evidence."""
    from api.data.attention.onboarding_resolver import Verdict
    ids = {entry["symbol"]: cid for cid, entry in led["coins"].items()}
    for symbol, reason in dropped:
        previous = doc["entries"].pop(symbol, None)
        verdict = Verdict("pending", reason=reason)
        if symbol in ids:
            _record(led, pending, log, ids[symbol], source, verdict, day, previous)
        else:
            pending.setdefault("coins", {}).setdefault(symbol, {})[source] = {"reason": reason, "at": day}
            log.append({"symbol": symbol, "source": source, "action": "pending", "reason": reason,
                        "previous": previous})
    return {symbol for symbol, _ in dropped}


def _resolver_context(source: str):
    """(settings, ledger, {coin id: snapshot name}, candidate coin ids) or a fixed-token reason string."""
    settings, _ = onboarding_settings.safe_load()
    if settings is None:
        return "unavailable settings"
    led, state = onboarding_store.read_ledger()
    if led is None:
        return f"unavailable {'corrupt' if state == 'corrupt' else 'no'} ledger"
    snap = universe_store.read_latest() or {}
    names = {r.get("id"): r.get("name") for r in snap.get("coins") or [] if isinstance(r, dict)}
    coins = led["coins"]
    todo = sorted((cid for cid, e in coins.items() if e["state"] in ("watching", "member")
                   and e["class"] in ("normal", "unknown") and not settings.blocked(e["symbol"], source)),
                  key=lambda c: (coins[c]["state"] != "watching",
                                 str((coins[c].get("resolver") or {}).get(source, {}).get("at") or ""), c))
    return settings, led, names, todo


def _record(led, pending, log, cid, source, verdict, day, previous=None) -> None:
    """One resolver outcome: the ledger keeps the state and reason (missing is never 0), pending keeps the evidence,
    the log keeps everything (sanitized and capped by the store)."""
    e = led["coins"][cid]
    e.setdefault("resolver", {})[source] = {"state": verdict.action, "reason": verdict.reason, "at": day}
    if verdict.action == "pending":
        pending.setdefault("coins", {}).setdefault(e["symbol"], {})[source] = {
            "reason": verdict.reason, "evidence": verdict.evidence, "at": day}
    else:
        pending.setdefault("coins", {}).get(e["symbol"], {}).pop(source, None)
    log.append({"source": source, "action": verdict.action, "coin_id": cid, "symbol": e["symbol"],
                "value": verdict.value, "reason": verdict.reason, "evidence": verdict.evidence,
                "previous": previous})


def _overlay_put(doc: dict, symbol: str, value: dict, day: str) -> None:
    doc.setdefault("entries", {})[symbol] = {**value, "source": "auto", "resolved_at": day}


def _resolver_save(led, pending, overlays: dict, log, day) -> None:
    for name, doc in overlays.items():
        onboarding_store.write_json(name, doc)
    onboarding_store.write_json(PENDING_FILE, pending)
    onboarding_store.write_ledger(led)
    onboarding_store.append_log(day, log)


def _run_resolve_wiki(symbols, client, today, sleep) -> str:
    """T223 O4: Wikipedia title (strict checks) and the Reddit/X cashtag-only entry for unnamed ledger coins, at most
    resolver_max_coins_per_run, stopping at the first HTTP 429. Writes only the bot overlays, pending and the log."""
    from api.data.attention import onboarding_resolver as res, onboarding_sources as osrc, web_queries
    ctx = _resolver_context("wikipedia")
    if isinstance(ctx, str):
        return ctx
    settings, led, names, todo = ctx
    day, log = today.isoformat(), []
    pending = _onboarding_document(PENDING_FILE, "coins")
    wiki_doc = _onboarding_document(WIKI_OVERLAY, "entries")
    q_doc = _onboarding_document(QUERIES_OVERLAY, "entries")
    try:
        owner_wiki = json.loads(WIKI_ARTICLES_PATH.read_text())
    except (OSError, ValueError):
        return "unavailable wiki file"
    try:
        owner_q = web_queries.load().coins
    except Exception:  # noqa: BLE001 - a bad owner file means no Reddit/X entries this run
        owner_q = None
    merged, dropped = res.merge_wiki(owner_wiki, wiki_doc)
    held = _drop_overlay_entries(wiki_doc, dropped, "wikipedia", led, pending, log, day)
    if owner_q is not None:
        q_owner = web_queries.load()
        _, q_dropped = web_queries.merge_overlay(q_owner, q_doc, [])
        held |= _drop_overlay_entries(q_doc, q_dropped, "reddit_x", led, pending, log, day)
    taken = {res.title_key(t): s for s, t in merged.items() if t}
    todo = [cid for cid in todo if led["coins"][cid]["symbol"] not in held
            and (led["coins"][cid]["symbol"] not in merged
                 or (owner_q is not None and led["coins"][cid]["symbol"] not in owner_q
                     and led["coins"][cid]["symbol"] not in q_doc["entries"]))]
    deadline = _clock() + ONBOARDING_TIME_BUDGET_S
    budget_stop = False
    counts = {"applied": 0, "pending": 0, "none": 0}
    stopped = False
    for cid in todo[:settings.resolver_max_coins_per_run]:
        if _clock() >= deadline:
            budget_stop = True
            break
        e = led["coins"][cid]
        sym, name = e["symbol"], names.get(cid)
        if owner_q is not None and sym not in owner_q and sym not in q_doc["entries"] and not settings.blocked(
                sym, "reddit_x"):
            v = res.reddit_x_verdict(sym, name)
            if v.action == "applied":
                _overlay_put(q_doc, sym, v.value, day)
            _record(led, pending, log, cid, "reddit_x", v, day)
        if sym in merged:
            continue
        page, st = osrc.fetch_wiki_page(name, client=client) if name else (None, "none")
        days, pst = (0, "ok")
        if page is not None and st == "ok":
            days, pst = osrc.fetch_pageview_days(sym, page["canonical"], client=client, today=today, sleep=sleep)
        if "capped" in (st, pst):
            stopped = True
            _record(led, pending, log, cid, "wikipedia",
                    res.Verdict("pending", reason="rate limited; retry next run"), day)
            break
        v = res.wiki_verdict(sym, name, page, taken=taken, pageview_days=days, min_days=settings.wiki_min_days)
        if v.action == "none" and st == "unavailable":
            v.reason = "request failed"
        if v.action == "applied":
            _overlay_put(wiki_doc, sym, v.value, day)
            taken[res.title_key(v.value["title"])] = sym
        counts[v.action] += 1
        _record(led, pending, log, cid, "wikipedia", v, day)
    _resolver_save(led, pending, {WIKI_OVERLAY: wiki_doc, QUERIES_OVERLAY: q_doc}, log, day)
    return (f"ok applied {counts['applied']}, pending {counts['pending']}, none {counts['none']}"
            + (", stopped on HTTP 429" if stopped else ", time budget reached" if budget_stop else ""))


def _run_resolve_trends(symbols, client, today, sleep) -> str:
    """T223 O4: Google Trends topic for unnamed ledger coins under the strict rule only (suggestions, the topic's own
    series, and the identity check against the stored CoinGecko volume), at most resolver_max_coins_per_run, one
    request every TRENDS_INTERVAL_S, stopping at the first HTTP 429."""
    from api.data.attention import onboarding_resolver as res, onboarding_sources as osrc
    ctx = _resolver_context("trends")
    if isinstance(ctx, str):
        return ctx
    settings, led, names, todo = ctx
    km, _ = trends_keywords.safe_load_merged()
    if km is None:
        return "unavailable keyword file"
    try:
        trendreq = TRENDREQ_FACTORY()
    except PytrendsMissing:
        return "unavailable pytrends not installed"
    except Exception as exc:  # noqa: BLE001 - class only
        return f"unavailable session {trends.error_class(exc)}"
    day, log = today.isoformat(), []
    pending = _onboarding_document(PENDING_FILE, "coins")
    doc = _onboarding_document(trends_keywords.OVERLAY_NAME, "entries")
    owner = trends_keywords.load()
    km, dropped = trends_keywords.merge_overlay(owner, doc)
    held = _drop_overlay_entries(doc, dropped, "trends", led, pending, log, day)
    taken = {e["topic"] for e in km.entries.values() if "topic" in e} | (
        {km.anchor["topic"]} if "topic" in km.anchor else set())
    counts = {"applied": 0, "pending": 0, "none": 0}
    stopped, sent = False, False
    todo = [cid for cid in todo if led["coins"][cid]["symbol"] not in set(km.entries) | held]
    deadline = _clock() + ONBOARDING_TIME_BUDGET_S
    budget_stop = False
    for cid in todo[:settings.resolver_max_coins_per_run]:
        if _clock() >= deadline:
            budget_stop = True
            break
        e = led["coins"][cid]
        sym, name = e["symbol"], names.get(cid)
        if sym in km.entries:
            continue
        if sent:
            sleep(TRENDS_INTERVAL_S)
        cands, st = osrc.fetch_suggestions(trendreq, name) if name else (None, "ok")
        sent = sent or bool(name)
        if st == "capped":
            stopped = True
            _record(led, pending, log, cid, "trends",
                    res.Verdict("pending", reason="rate limited; retry next run"), day)
            break
        v = res.trends_pick(sym, name, cands, taken_topics=taken)
        if st == "unavailable":
            v = res.Verdict("none", reason="request failed")
        if v.action == "candidate":
            sleep(TRENDS_INTERVAL_S)
            points, sst = osrc.fetch_topic_series(sym, v.value["topic"], trendreq, today=today)
            if sst == "capped":
                stopped = True
                _record(led, pending, log, cid, "trends",
                        res.Verdict("pending", reason="rate limited; retry next run"), day)
                break
            corr, overlap = osrc.identity(points, store.read_points("coingecko", sym), min_days=settings.identity_min_days)
            v = res.trends_confirm(v, series_state=sst, corr=corr, overlap_days=overlap, settings=settings)
        if v.action == "applied":
            _overlay_put(doc, sym, v.value, day)
            taken.add(v.value["topic"])
        counts[v.action] += 1
        _record(led, pending, log, cid, "trends", v, day)
    _resolver_save(led, pending, {trends_keywords.OVERLAY_NAME: doc}, log, day)
    return (f"ok applied {counts['applied']}, pending {counts['pending']}, none {counts['none']}"
            + (", stopped on HTTP 429" if stopped else ", time budget reached" if budget_stop else ""))


RUNNERS = {"universe": _run_universe, "wikipedia": _run_wikipedia, "coingecko": _run_coingecko,
           "exchange_volume": _run_exchange_volume, "hyperliquid_volume": _run_hyperliquid_volume,
           "trends": _run_trends, "reddit": _run_reddit, "xsearch": _run_xsearch,
           "categories": _run_categories, "signals": _run_signals, "ledger": _run_ledger, "classify": _run_classify,
           "resolve_wiki": _run_resolve_wiki, "resolve_trends": _run_resolve_trends}
# T223: onboarding steps print one fixed-token line each and never decide the exit code.
ONBOARDING_STEPS = ("ledger", "classify", "resolve_wiki", "resolve_trends")


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
            if name in ONBOARDING_STEPS:
                print(f"{name}: dry run, nothing fetched or written")
                continue
            if name == "signals":
                print("signals: dry run, would snapshot windows 7,30,90 (no network call, nothing written)")
                continue
            print(f"{name}: dry run, would fetch {len(symbols)} symbols (no network call, nothing written)")
        return 0
    own = client is None
    client = client or httpx.Client(follow_redirects=True)
    results: dict[str, str] = {}
    onboarding_rate_limited = False
    try:
        for name in names:
            if name in ONBOARDING_STEPS:   # never decides the exit code; one explicit fixed-token line
                if name != "ledger" and onboarding_rate_limited:
                    print(f"{name}: unavailable rate-limit")
                    continue
                if name == "ledger" and results.get("universe") == "error":
                    print("ledger: skipped, universe step failed")
                    continue
                try:
                    status = RUNNERS[name](symbols, client, today, sleep)
                    onboarding_rate_limited = onboarding_rate_limited or "HTTP 429" in status
                    print(f"{name}: {status}")
                except Exception as exc:  # noqa: BLE001 - class only, never the message
                    print(f"{name}: unavailable error {type(exc).__name__}")
                continue
            if name == "signals":
                _snapshot_signals(RUNNERS[name], symbols, client, today, sleep)
                continue
            try:
                series = RUNNERS[name](symbols, client, today, sleep)
                if name in ("universe", "categories"):
                    results[name] = "ok"
                    print(f"{name}: snapshot written")
                    continue
                written, store_failed = 0, []
                if not args.dry_run:
                    for i, s in enumerate(series):
                        if s.state in ("ok", "insufficient-history"):
                            mode = WRITE_MODES.get(name)
                            try:  # one failed write must not stop the others (a Trends pull costs minutes)
                                written += (store.write_series(s, today=today, mode=mode) if mode
                                            else store.write_series(s, today=today))
                            except Exception as exc:  # noqa: BLE001 - class only, never the message
                                from api.data.attention.types import SourceSeries
                                why = f"store-failed: {trends.error_class(exc)}"
                                store_failed.append(why)
                                series[i] = SourceSeries(s.source, s.symbol, [], "unavailable", why)
                if name == "trends" and trends_run_error:  # the run file is evidence, but a failed write is red
                    store_failed.append(f"store-failed: {trends_run_error}")
                ok = sum(1 for s in series if s.state == "ok")
                failed = series and all(
                    s.state == "unavailable" and s.reason != "empty response" for s in series)
                results[name] = "ok" if ok else ("error" if failed else "empty")
                print(f"{name}: {ok}/{len(series)} ok, {written} rows written"
                      f"{' (dry run)' if args.dry_run else ''} [{outcome_summary(series)}]"
                      f"{' reasons: ' + reason_summary(series) if (not ok or store_failed) and series else ''}")
                if store_failed:  # the last line the verifier reads: a store failure is a code failure, red
                    results[name] = "error"
                    counts = {k: store_failed.count(k) for k in dict.fromkeys(store_failed)}
                    # Same stream as the summary, so it stays last when stdout is block-buffered (CI pipes 2>&1).
                    print(f"{name}: error {'; '.join(f'{k} x{n}' for k, n in counts.items())}", flush=True)
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
