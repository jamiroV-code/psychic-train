"""Sources status (T106): what each Discovery input has stored, read from files and config only (no network).

Per series it reads only the `date` column of each eligible coin's file, cached per file by (mtime, size),
so a repeated call costs a stat per file. A coin counts as having data like live scoring does: the
registry's history gate (MIN_HISTORY_DAYS) and the source's newest day within `max_source_lag_days`.
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from api.analytics.attention.discovery import (EXCHANGE_SERIES, FALLBACK_SERIES, SLOT, eligibility, load_config)
from api.analytics.attention import narratives
from api.analytics.attention.universe import load_universe_rows
from api.data.attention import registry, store, trends_keywords, universe_store
from api.data.attention.types import MIN_HISTORY_DAYS
from api.models.discovery import (DiscoveryKeywordGap, DiscoverySourceRow, DiscoverySourcesResponse,
                                  DiscoveryTrendsKeyword)

LABELS = {
    "wikipedia": "Wikipedia pageviews", "trends": "Google Trends", "reddit": "Reddit", "xsearch": "X search",
    "github_dev": "GitHub dev activity", "defillama": "DefiLlama", SLOT: "Exchange activity",
    "binance": "Binance volume", "coinbase": "Coinbase volume", "kraken": "Kraken volume",
    "hyperliquid": "Hyperliquid volume", FALLBACK_SERIES: "CoinGecko (volume fallback)",
    "universe": "Top-100 universe", "narratives": "Narratives file",
}

_file_cache: dict[str, tuple[int, int, int, date | None]] = {}   # path -> (mtime_ns, size, days, newest)


def clear_cache() -> None:
    _file_cache.clear()


def _scan(source: str, symbol: str) -> tuple[int, date | None]:
    """(stored days, newest date) of one file; (0, None) when missing or unreadable."""
    path = store.store_path(source, symbol)
    try:
        st = path.stat()
    except OSError:
        return 0, None
    hit = _file_cache.get(str(path))
    if hit and hit[:2] == (st.st_mtime_ns, st.st_size):
        return hit[2], hit[3]
    try:
        dates = pd.read_parquet(path, columns=["date"])["date"]
        days, newest = len(dates), (pd.Timestamp(dates.max()).date() if len(dates) else None)
    except Exception:   # unreadable file: report it as no data, never a 500
        days, newest = 0, None
    _file_cache[str(path)] = (st.st_mtime_ns, st.st_size, days, newest)
    return days, newest


class _Series:
    def __init__(self, source: str, coins: list[str], end: date, max_lag: int):
        scans = {c: _scan(source, c) for c in coins}
        self.history_days = max((n for n, _ in scans.values()), default=0)
        stored = [d for _, d in scans.values() if d is not None]
        self.newest = max(stored, default=None)
        self.usable = {c for c, (n, d) in scans.items()
                       if n >= MIN_HISTORY_DAYS and d is not None and (end - d).days <= max_lag}
        self.stale = bool(stored) and self.history_days >= MIN_HISTORY_DAYS and not self.usable


def _state(sid: str, s: _Series, probed: bool, x_live: bool) -> tuple[str, str]:
    if sid == "xsearch" and not x_live:
        return "off", "X search is off (X_LIVE not set): dry run only"
    if not probed:
        return "not-probed", "not probed yet"
    if s.usable:
        return "ok", ""
    if s.stale:
        return "unavailable", f"stale: newest {s.newest}"
    if s.history_days:
        return "insufficient-history", f"insufficient history {s.history_days}/{MIN_HISTORY_DAYS}"
    return "unavailable", "no stored data"


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _helper(sid: str, snap: dict | None, key: str, what: str) -> DiscoverySourceRow:
    rows = (snap or {}).get(key, [])
    ok = bool(snap) and bool(rows)
    return DiscoverySourceRow(id=sid, label=LABELS[sid], kind="helper", weight=None,
                              state="ok" if ok else "unavailable", newest=str(snap["date"]) if snap and snap.get("date") else None,
                              history_days=0, coins_with_data=len(rows), eligible_size=0,
                              note="" if ok else f"{what} not downloaded yet")


def _narratives_row() -> DiscoverySourceRow:
    """Helper row (U2): the narratives file that Discovery membership comes from; `ok` when it loads."""
    try:
        doc = narratives.load_narratives()
    except (OSError, ValueError) as exc:
        return DiscoverySourceRow(id="narratives", label=LABELS["narratives"], kind="helper", weight=None,
                                  state="unavailable", newest=None, history_days=0, coins_with_data=0,
                                  eligible_size=0, note=f"narratives file invalid: {exc}")
    coins = {c["symbol"] for n in doc["narratives"] for c in n["coins"]}
    return DiscoverySourceRow(id="narratives", label=LABELS["narratives"], kind="helper", weight=None, state="ok",
                              newest=doc["as_of"], history_days=0, coins_with_data=len(coins), eligible_size=0,
                              note="status proposed" if doc["status"] == "proposed" else "")


def _trends_keyword(eligible: list[str]) -> DiscoveryTrendsKeyword:
    """Read from the keyword file with the runner's own rule (`keyword_status`), so the two cannot disagree."""
    km, _ = trends_keywords.safe_load()
    cov = trends_keywords.coverage(km, eligible)
    return DiscoveryTrendsKeyword(eligible_size=cov.eligible, with_keyword=cov.with_keyword,
                                  missing=[DiscoveryKeywordGap(symbol=s, detail=st) for s, st in cov.missing])


def build_sources(today: date, *, probe_path: Path | None = None, universe_path: Path | None = None,
                  config_path: Path | None = None) -> DiscoverySourcesResponse:
    cfg = load_config(config_path)
    end = today - timedelta(days=1)
    max_lag = int(cfg["max_source_lag_days"])
    rows, _ = load_universe_rows(universe_path)
    eligible = eligibility(cfg, rows).eligible if rows else []
    probed = registry.load_probe_records(probe_path)
    x_live = os.environ.get("X_LIVE") == "1"
    n = len(eligible)

    def series(sid: str, name: str) -> tuple[_Series, str, str]:
        s = _Series(name, eligible, end, max_lag)
        return (s, *_state(sid, s, name in probed, x_live))

    def row(sid, kind, weight, s, state, note) -> DiscoverySourceRow:
        return DiscoverySourceRow(id=sid, label=LABELS[sid], kind=kind, weight=weight, state=state,
                                  newest=_iso(s.newest), history_days=s.history_days,
                                  coins_with_data=len(s.usable), eligible_size=n, note=note)

    out: list[DiscoverySourceRow] = []
    members: dict[str, tuple] = {m: series(m, ser) for m, ser in EXCHANGE_SERIES.items()}
    fallback = series(FALLBACK_SERIES, FALLBACK_SERIES)
    for sid, w in cfg["source_weights"].items():
        if w <= 0:   # parked (T130): not fetched, not failing, not counted
            out.append(DiscoverySourceRow(id=sid, label=LABELS[sid], kind="weighted", weight=w, state="off",
                                          newest=None, history_days=0, coins_with_data=0, eligible_size=n,
                                          note="parked: weight 0, not fetched"))
            continue
        if sid != SLOT:
            out.append(row(sid, "weighted", w, *series(sid, sid)))
            continue
        every = [members[m][0] for m in EXCHANGE_SERIES]
        agg = _Series.__new__(_Series)   # per coin: any exchange, else the CoinGecko fallback (as live scoring does)
        agg.usable = set().union(*(e.usable for e in every), fallback[0].usable)
        agg.history_days = max(e.history_days for e in every + [fallback[0]])
        agg.newest = max((e.newest for e in every + [fallback[0]] if e.newest), default=None)
        agg.stale = False
        via_fallback = fallback[0].usable - set().union(*(e.usable for e in every))
        note = (f"{len(via_fallback)} of {len(agg.usable)} coins use the CoinGecko volume fallback"
                if via_fallback else "" if agg.usable else "no exchange or CoinGecko volume data")
        out.append(row(SLOT, "weighted", w, agg, "ok" if agg.usable else "unavailable", note))
    for m in EXCHANGE_SERIES:
        out.append(row(m, "exchange-member", cfg["exchange_sub_weights"].get(m), *members[m]))
    out.append(row(FALLBACK_SERIES, "fallback", None, *fallback))
    out.append(_helper("universe", universe_store.read_latest(), "coins", "top-100 snapshot"))
    out.append(_narratives_row())

    weighted = [r for r in out if r.kind == "weighted" and (r.weight or 0) > 0]
    live = [r for r in weighted if r.state == "ok"]
    return DiscoverySourcesResponse(
        as_of=end.isoformat(), universe_size=len(rows), eligible_size=n, live_sources=len(live),
        total_sources=len(weighted), live_weight=sum(r.weight or 0 for r in live),
        newest=max((r.newest for r in live if r.newest), default=None), sources=out,
        trends_keyword=_trends_keyword(eligible))
