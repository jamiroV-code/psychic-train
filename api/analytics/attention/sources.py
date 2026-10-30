"""Sources status (T106): what each Discovery input has stored, read from files and config only (no network).

Per series it reads only the `date` column of each eligible coin's file, cached per file by (mtime, size),
so a repeated call costs a stat per file. A coin counts as having data like live scoring does: the
registry's history gate (MIN_HISTORY_DAYS) and the source's newest day within `max_source_lag_days`.

W8f: a weighted source reports the store `source_impl` selects (the first with usable coins, else the first with
data, else the first); X in rotation mode is gated by `x_rotation_points` stored points and
`x_rotation_max_lag_days`. Each row carries a closed `reason` code beside its note; a failed or stale series is
`unavailable`, a short one `insufficient-history`.

W8e2: optional worker health is read from atomic state/completeness snapshots only. Collection-day counts
are distinct coin-days, excluding canaries, pages and account retries. The text separately labels the target
UTC day. Older files without attempt or scheduling evidence report unknown, never inferred zero.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd

from api.analytics.attention.discovery import (EXCHANGE_SERIES, FALLBACK_SERIES, SLOT, X_SOURCE, eligibility,
                                               load_config, source_impls, weights_for_day, x_setting)
from api.analytics.attention import narratives
from api.analytics.attention.universe import load_universe_rows
from api.data import cache
from api.data.attention import pc_pace, registry, store, trends_keywords, universe_store, web_queries, x_pool
from api.data.attention import pc_adapter as pa
from api.data.attention.types import MIN_HISTORY_DAYS
from api.models.discovery import (DiscoveryAccountHealth, DiscoveryKeywordGap, DiscoverySourceHealth,
                                  DiscoverySourceRow, DiscoverySourcesResponse, DiscoveryTrendsKeyword)

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


PC_STORES = frozenset({"xsearch_web", "reddit_web"})


def _json_file(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def _timestamp(value) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.astimezone(UTC) if parsed.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def _collector():
    try:
        return web_queries.load().config
    except (OSError, ValueError):
        return None


def _accounts(now: datetime, health: DiscoverySourceHealth) -> None:
    """Reuse the pool's read-only loader and lock semantics, never its mutating methods or account DBs."""
    cfg = _collector()
    path = cache.CACHE_ROOT / "attention" / "_pc_state" / "x_pool.json"
    if cfg is None or not cfg.x_accounts:
        return
    ages = _json_file(Path(cfg.x_accounts_db_path) / "cookie_ages.json") if cfg.x_accounts_db_path else None
    if not path.exists():
        return
    try:
        pool = x_pool.XPool(list(cfg.x_accounts), clock=lambda: now)
        snapshot = pool.health()
    except x_pool.XPoolStateError:
        health.paused, health.pause_reason, health.pause_until = True, "state_error", None
        return
    health.accounts_active, health.accounts_total = snapshot["active"], snapshot["total"]
    for account in snapshot["accounts"]:
        refreshed = _timestamp((ages or {}).get(account["label"]))
        health.accounts.append(DiscoveryAccountHealth(
            **account, cookie_age_days=max(0, (now - refreshed).days) if refreshed else None))
    if snapshot["pause_reason"]:
        # One loaded snapshot: do not re-read a file that the producer may replace concurrently.
        health.paused, health.pause_reason = True, snapshot["pause_reason"]
        health.pause_until = None if pool._s["stopped"] else pool._s["pause_until"]


def _completeness(store_id: str, day: date, now: datetime, health: DiscoverySourceHealth) -> None:
    directory = cache.CACHE_ROOT / "attention" / store_id / "_meta" / "_completeness"
    today_attempted = today_fetched = 0
    known_today = directory.exists()
    target = None
    for path in sorted(directory.glob("*.json")):
        doc = _json_file(path)
        coins = doc.get("coins") if doc else None
        if not isinstance(coins, dict) or not all(isinstance(c, dict) for c in coins.values()):
            known_today = False
            continue
        if path.stem == day.isoformat():
            target = coins
        for coin in coins.values():
            collected = _timestamp(coin.get("collected_at"))
            if collected and collected.date() == now.date():
                if coin.get("attempted") is None:
                    known_today = False
                else:
                    today_attempted += coin.get("attempted") is True
                    today_fetched += coin.get("reason") == "fetched"
    if known_today:
        health.attempted, health.fetched = today_attempted, today_fetched
    if target is None:
        return
    reasons = Counter()
    times = []
    fetched = capped = attempted = 0
    attempts_known = True
    for coin in target.values():
        reason = coin.get("reason")
        if not isinstance(reason, str) or not re.fullmatch(r"[a-z_]{1,40}", reason):
            reason = "invalid_evidence"
        if reason == "fetched":
            fetched += 1
            capped += coin.get("capped") is True
        else:
            reasons[reason] += 1
        attempts_known &= isinstance(coin.get("attempted"), bool)
        attempted += coin.get("attempted") is True
        collected = _timestamp(coin.get("collected_at"))
        if collected:
            times.append(collected)
    health.completeness_attempted = attempted if attempts_known else None
    health.completeness_fetched, health.capped = fetched, capped
    health.missing, health.missing_reasons = sum(reasons.values()), dict(sorted(reasons.items()))
    health.newest_age_hours = round(max(0, (now - max(times)).total_seconds()) / 3600, 1) if times else None


def _health(store_id: str, day: date, now: datetime) -> DiscoverySourceHealth | None:
    path = pc_pace.state_path(store_id)
    if not path.exists():
        return None
    h = DiscoverySourceHealth(collection_day=now.date().isoformat(), completeness_day=day.isoformat(),
                              completeness="")
    state = _json_file(path)
    if not pc_pace._valid_state(state):
        h.paused, h.pause_reason, h.completeness = True, "state_error", "worker state unreadable"
        return h
    h.last_unit_at = state["last_unit_at"]
    until = _timestamp(state["pause_until"])
    if state["pause_reason"] in pa.OWNER_ACTION_REASONS or (state["pause_reason"] and until and now < until):
        h.paused, h.pause_reason, h.pause_until = True, state["pause_reason"], state["pause_until"]
    h.budget_used = state["used"] if state["budget_day"] == h.collection_day else 0
    h.effective_budget = state["effective"]
    h.budget_spent = state["spent_day"] == h.collection_day or h.budget_used >= h.effective_budget
    schedule = _json_file(path.with_name(f"{store_id}_health.json")) or {}
    gap = schedule.get("expected_gap_s")
    if (schedule.get("mode") in ("baseline", "degraded") and isinstance(gap, (int, float))
            and not isinstance(gap, bool) and math.isfinite(gap) and gap > 0):
        h.mode, h.expected_gap_s = schedule["mode"], gap
        last = _timestamp(h.last_unit_at)
        h.stale = last is None or (now - last).total_seconds() > 2 * gap
    if store_id == "xsearch_web":
        _accounts(now, h)
    _completeness(store_id, day, now, h)
    count = lambda value: "unknown" if value is None else str(value)
    h.completeness = (f"{day.isoformat()}: attempted {count(h.completeness_attempted)}, "
                      f"fetched {count(h.completeness_fetched)}, missing {count(h.missing)}")
    if h.missing_reasons:
        h.completeness += " (" + ", ".join(f"{k} {v}" for k, v in h.missing_reasons.items()) + ")"
    h.completeness += f", capped {count(h.capped)}, newest "
    h.completeness += f"{h.newest_age_hours:g}h old" if h.newest_age_hours is not None else "unknown"
    if h.stale:
        h.completeness += "; stale"
    try:
        h.free_disk_bytes = shutil.disk_usage(cache.CACHE_ROOT).free
    except OSError:
        pass
    return h


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
                  config_path: Path | None = None, now: datetime | None = None) -> DiscoverySourcesResponse:
    cfg = load_config(config_path)
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(UTC)
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
                                  impl=impl, health=_health(impl, end, now) if impl in PC_STORES else None)

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
