"""Discovery history (T103 W2): the live weighted score rebuilt for each past day, point in time.

Day D is scored exactly like live scoring (`discovery._coin`) with end = D, from points dated <= D only.
The 90-day gate is evaluated per day: a series counts on D only if it has at least `min_history_days`
points dated <= D (never the total stored length, so no availability lookahead). Each stored series is read
once and sliced by date. Days with no usable source are omitted (missing is never 0).
"""
from __future__ import annotations

import json
from bisect import bisect_right
from datetime import date, timedelta
from pathlib import Path
from statistics import mean

from api.analytics.attention.discovery import (_coin, _percentile, eligibility, load_config, series_names)
from api.analytics.attention.universe import load_universe
from api.data.attention import categories_store, registry, store
from api.data.attention.types import SourceSeries
from api.models.discovery import (DiscoveryCategoryDay, DiscoveryCategoryHistory, DiscoveryCoinHistory,
                                  DiscoveryHistoryDay)

NO_DATA = "no-attention-data"
CACHE_MAX = 64
_cache: dict[tuple, object] = {}   # key -> response; see `_cached`


def clear_cache() -> None:
    _cache.clear()


class UnknownSubject(LookupError):
    """The symbol or category id is not known; the router answers 404."""


class _Stored:
    """One stored series, read once. `at(day)` is the series as known on `day`, gated per AC-W13."""

    def __init__(self, source: str, symbol: str, probed: bool, min_days: int):
        self.source, self.symbol, self.min_days = source, symbol, min_days
        self.points: list[tuple[date, float]] = []
        if probed:
            try:
                self.points = sorted(store.read_points(source, symbol))
            except store.StoreReadError:
                self.points = []
        self.dates = [d for d, _ in self.points]

    def count(self, day: date) -> int:
        return bisect_right(self.dates, day)

    def at(self, day: date) -> SourceSeries:
        n = self.count(day)
        if n < self.min_days:
            return SourceSeries(self.source, self.symbol, [], "insufficient-history" if n else "unavailable")
        return SourceSeries(self.source, self.symbol, self.points[:n], "ok")


def _load(cfg: dict, symbols: list[str], probe_path: Path | None) -> dict[tuple[str, str], _Stored]:
    probed = registry.load_probe_records(probe_path)
    min_days = int(cfg["min_history_days"])
    return {(src, sym): _Stored(src, sym, src in probed, min_days)
            for src in sorted(series_names(cfg)) for sym in symbols}


def _signature(cfg: dict, symbols: list[str], probe_path: Path | None) -> tuple:
    """Everything a result depends on besides the arguments: config, probe records, and every stored file's
    identity (mtime, size, inode), so a backfill that rewrites old points also invalidates, not just a new day."""
    probed = registry.load_probe_records(probe_path)
    files = []
    for src in sorted(series_names(cfg)):
        for sym in symbols:
            try:
                st = store.store_path(src, sym).stat()
                files.append((src, sym, st.st_mtime_ns, st.st_size, st.st_ino))
            except OSError:
                files.append((src, sym))
    return (json.dumps(cfg, sort_keys=True), tuple(sorted(probed)), tuple(files))


def _cached(key: tuple, compute):
    hit = _cache.get(key)
    if hit is None:
        hit = _cache[key] = compute()
        while len(_cache) > CACHE_MAX:
            _cache.pop(next(iter(_cache)))
    return hit.model_copy(deep=True)


def _score_day(symbol: str, day: date, cfg: dict, stored, window: int):
    data = {(src, sym): s.at(day) for (src, sym), s in stored.items() if sym == symbol}
    return _coin(symbol, cfg, data, day, int(cfg["recent_days"]), window, int(cfg["max_source_lag_days"]))


def _days(end: date, window: int) -> list[date]:
    return [end - timedelta(days=window - 1 - i) for i in range(window)]


def _base(cfg: dict, subject: str, window: int, end: date) -> dict:
    return {"id": subject, "window": window, "as_of": end.isoformat(), "min_history_days": int(cfg["min_history_days"]),
            "min_covered_weight": float(cfg["min_covered_weight"])}


def coin_history(symbol: str, window: int, *, today: date, probe_path: Path | None = None,
                 universe_path: Path | None = None, config_path: Path | None = None) -> DiscoveryCoinHistory:
    cfg = load_config(config_path)
    end = today - timedelta(days=1)
    sym = symbol.strip().upper()
    base = _base(cfg, sym, window, end)
    symbols, reason = load_universe(universe_path)
    if not symbols:
        return DiscoveryCoinHistory(**base, status="no-data", reason=reason, history_days={}, days=[])
    if sym not in symbols:
        raise UnknownSubject(f"unknown symbol {symbol!r}")

    def compute():
        stored = _load(cfg, [sym], probe_path)
        floor = float(cfg["min_covered_weight"])
        days = []
        for day in _days(end, window):
            c = _score_day(sym, day, cfg, stored, window)
            if c is not None:
                days.append(DiscoveryHistoryDay(date=day.isoformat(), score=c[0], covered_weight=c[1],
                                                rising_weight=c[2], trigger=c[3], thin=c[1] < floor))
        counts = {src: s.count(end) for (src, _), s in sorted(stored.items())}
        return DiscoveryCoinHistory(**base, status="ok" if days else "no-data",
                                    reason="" if days else NO_DATA, history_days=counts, days=days)

    return _cached(("coin", sym, window, end, _signature(cfg, [sym], probe_path)), compute)


def category_history(category_id: str, window: int, *, today: date, probe_path: Path | None = None,
                     universe_path: Path | None = None, config_path: Path | None = None
                     ) -> DiscoveryCategoryHistory:
    cfg = load_config(config_path)
    end = today - timedelta(days=1)
    base = _base(cfg, category_id, window, end)
    if category_id not in {c["id"] for c in cfg["categories"]}:
        raise UnknownSubject(f"unknown category {category_id!r}")
    symbols, reason = load_universe(universe_path)
    if not symbols:
        return DiscoveryCategoryHistory(**base, status="no-data", reason=reason, days=[])
    cats = categories_store.read_latest()
    if not cats or not cats.get("categories"):
        return DiscoveryCategoryHistory(**base, status="no-data", reason="categories-missing", days=[])
    eligible, members = eligibility(cfg, symbols, cats)
    coins = [s for s in eligible if s in members.get(category_id, set())]

    def compute():
        stored = _load(cfg, coins, probe_path)
        by_coin = {s: {k: v for k, v in stored.items() if k[1] == s} for s in coins}
        pct = float(cfg["winsor_percentile"])
        days = []
        for day in _days(end, window):
            scored = [c for c in (_score_day(s, day, cfg, by_coin[s], window) for s in coins) if c is not None]
            if not scored:
                continue
            raws = [c[0] for c in scored]
            cap = _percentile(raws, pct)
            triggered = sum(c[3] for c in scored)
            days.append(DiscoveryCategoryDay(date=day.isoformat(), score=mean(min(r, cap) for r in raws),
                                             coins_used=len(scored), triggered_count=triggered,
                                             triggered_share=triggered / len(scored)))
        return DiscoveryCategoryHistory(**base, status="ok" if days else "no-data",
                                        reason="" if days else NO_DATA, days=days)

    return _cached(("category", category_id, window, end, _signature(cfg, coins, probe_path)), compute)
