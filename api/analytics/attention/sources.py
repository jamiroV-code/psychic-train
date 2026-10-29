"""Sources status (T106): what each Discovery input has stored, read from files and config only (no network).

Per series it reads only the `date` column of each eligible coin's file, cached per file by (mtime, size),
so a repeated call costs a stat per file. A coin counts as having data like live scoring does: the
registry's history gate (MIN_HISTORY_DAYS) and the source's newest day within `max_source_lag_days`.

W8f: a weighted source reports the store `source_impl` selects (the first with usable coins, else the first with
data, else the first); X in rotation mode is gated by `x_rotation_points` stored points and
`x_rotation_max_lag_days`. Each row carries a closed `reason` code beside its note; a failed or stale series is
`unavailable`, a short one `insufficient-history`.
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from api.analytics.attention.discovery import (EXCHANGE_SERIES, FALLBACK_SERIES, SLOT, X_SOURCE, eligibility,
                                               load_config, source_impls, weights_for_day, x_setting)
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
COVERAGE_ONLY_LABEL = "CoinGecko volume (coverage only)"   # T204: the fallback no longer votes

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
    def __init__(self, source: str, coins: list[str], end: date, max_lag: int, gate: int = MIN_HISTORY_DAYS):
        scans = {c: _scan(source, c) for c in coins}
        self.gate = gate
        self.history_days = max((n for n, _ in scans.values()), default=0)
        stored = [d for _, d in scans.values() if d is not None]
        self.newest = max(stored, default=None)
        self.usable = {c for c, (n, d) in scans.items()
                       if n >= gate and d is not None and (end - d).days <= max_lag}
        self.stale = bool(stored) and self.history_days >= gate and not self.usable


def _state(store_id: str, s: _Series, probed: bool, x_live: bool) -> tuple[str, str, str]:
    """(state, note, reason) of one store; `store_id` is the official X store only when X_LIVE applies."""
    if store_id == "xsearch" and not x_live:
        return "off", "X search is off (X_LIVE not set): dry run only", "x_live_off"
    if not probed:
        return "not-probed", "not probed yet", "not_probed"
    if s.usable:
        return "ok", "", ""
    if s.stale:
        return "unavailable", f"stale: newest {s.newest}", "stale"
    if s.history_days:
        return "insufficient-history", f"insufficient history {s.history_days}/{s.gate}", "insufficient_history"
    return "unavailable", "no stored data", "no_stored_data"


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _helper(sid: str, snap: dict | None, key: str, what: str) -> DiscoverySourceRow:
    rows = (snap or {}).get(key, [])
    ok = bool(snap) and bool(rows)
    return DiscoverySourceRow(id=sid, label=LABELS[sid], kind="helper", weight=None,
                              state="ok" if ok else "unavailable", newest=str(snap["date"]) if snap and snap.get("date") else None,
                              history_days=0, coins_with_data=len(rows), eligible_size=0,
                              note="" if ok else f"{what} not downloaded yet", reason="" if ok else "no_stored_data")


def _narratives_row() -> DiscoverySourceRow:
    """Helper row (U2): the narratives file that Discovery membership comes from; `ok` when it loads."""
    try:
        doc = narratives.load_narratives()
    except (OSError, ValueError) as exc:
        return DiscoverySourceRow(id="narratives", label=LABELS["narratives"], kind="helper", weight=None,
                                  state="unavailable", newest=None, history_days=0, coins_with_data=0,
                                  eligible_size=0, note=f"narratives file invalid: {exc}", reason="invalid_file")
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
    coverage_only = weights_for_day(cfg, end)["fallback_coverage_only"]

    def series(sid: str, name: str, lag: int = max_lag, gate: int = MIN_HISTORY_DAYS) -> tuple:
        s = _Series(name, eligible, end, lag, gate)
        return (s, *_state(name, s, name in probed or name in registry.PC_STORES, x_live))

    def weighted_series(sid: str) -> tuple[tuple, str]:
        """(series tuple, store) of the `source_impl` store this row reports."""
        lag, gate = max_lag, MIN_HISTORY_DAYS
        if sid == X_SOURCE and x_setting(cfg, "x_discovery_mode") == "rotation":
            lag, gate = int(x_setting(cfg, "x_rotation_max_lag_days")), int(x_setting(cfg, "x_rotation_points"))
        found = [(series(sid, m, lag, gate), m) for m in impls[sid]]
        return next((f for f in found if f[0][0].usable), None) or next(
            (f for f in found if f[0][0].history_days), found[0])

    def row(sid, kind, weight, s, state, note, reason, impl=None) -> DiscoverySourceRow:
        return DiscoverySourceRow(id=sid, label=LABELS[sid], kind=kind, weight=weight, state=state,
                                  newest=_iso(s.newest), history_days=s.history_days,
                                  coins_with_data=len(s.usable), eligible_size=n, note=note, reason=reason,
                                  impl=impl)

    impls = source_impls(cfg)

    out: list[DiscoverySourceRow] = []
    members: dict[str, tuple] = {m: series(m, ser) for m, ser in EXCHANGE_SERIES.items()}
    fallback = series(FALLBACK_SERIES, FALLBACK_SERIES)
    for sid, w in cfg["source_weights"].items():
        if w <= 0:   # parked (T130): not fetched, not failing, not counted
            out.append(DiscoverySourceRow(id=sid, label=LABELS[sid], kind="weighted", weight=w, state="off",
                                          newest=None, history_days=0, coins_with_data=0, eligible_size=n,
                                          note="parked: weight 0, not fetched", reason="parked"))
            continue
        if sid != SLOT:
            found, impl = weighted_series(sid)
            out.append(row(sid, "weighted", w, *found, impl=impl))
            continue
        every = [members[m][0] for m in EXCHANGE_SERIES]
        agg = _Series.__new__(_Series)   # per coin: any exchange, else the CoinGecko fallback (as live scoring does)
        agg.usable = set().union(*(e.usable for e in every), fallback[0].usable)
        agg.history_days = max(e.history_days for e in every + [fallback[0]])
        agg.newest = max((e.newest for e in every + [fallback[0]] if e.newest), default=None)
        agg.stale = False
        via_fallback = fallback[0].usable - set().union(*(e.usable for e in every))
        note = (f"{len(via_fallback)} of {len(agg.usable)} coins use the CoinGecko volume fallback"
                + (" (coverage only, never a rising vote)" if coverage_only else "")
                if via_fallback else "" if agg.usable else "no exchange or CoinGecko volume data")
        out.append(row(SLOT, "weighted", w, agg, "ok" if agg.usable else "unavailable", note,
                       "" if agg.usable else "no_stored_data"))
    for m in EXCHANGE_SERIES:
        out.append(row(m, "exchange-member", cfg["exchange_sub_weights"].get(m), *members[m]))
    fb = row(FALLBACK_SERIES, "fallback", None, *fallback)
    out.append(fb.model_copy(update={"label": COVERAGE_ONLY_LABEL}) if coverage_only else fb)
    out.append(_helper("universe", universe_store.read_latest(), "coins", "top-100 snapshot"))
    out.append(_narratives_row())

    weighted = [r for r in out if r.kind == "weighted" and (r.weight or 0) > 0]
    live = [r for r in weighted if r.state == "ok"]
    return DiscoverySourcesResponse(
        as_of=end.isoformat(), universe_size=len(rows), eligible_size=n, live_sources=len(live),
        total_sources=len(weighted), live_weight=sum(r.weight or 0 for r in live),
        newest=max((r.newest for r in live if r.newest), default=None), sources=out,
        trends_keyword=_trends_keyword(eligible))
