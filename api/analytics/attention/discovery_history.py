"""Discovery history (T103 W2): the live weighted score rebuilt for each past day, point in time.

Day D is scored exactly like live scoring (`discovery._coin`) with end = D, from points dated <= D only.
Each day is scored with the weights version in force that day (`discovery.weights_for_day`, T130), so a weights
change never rescores past days. The 90-day gate is evaluated per day: a series counts on D only if it has at least `min_history_days`
points dated <= D (never the total stored length, so no availability lookahead). Each stored series is read
once and sliced by date. Days with no usable source are omitted (missing is never 0).

Trends point in time (T175, M1 option A): the live Trends series is REPLACED by each daily pull, so it is never
read here. Chart day D takes Trends from, in order: (1) the frozen signal snapshot of D for the chart's window, if
its row for the coin holds a `trends` entry (authoritative, used as recorded); (2) the pull archived on UTC date
D+1 (`trends_pulls/<D+1>.parquet`, the pull live scoring used on the run after D), only when that pull's last row
for the coin is D, gated like any series; else (3) Trends is missing on D, with a reason (`_TrendsPulls.at`), never
0 and never from a later pull. Every other source reads its store as before.

A category is a narrative (U1); an old CoinGecko category id resolves through the id map. Every day of a category
chart uses TODAY'S membership (the narratives file, dated `membership_as_of`), never a past one.
"""
from __future__ import annotations

import json
from bisect import bisect_right
from datetime import date, timedelta
from pathlib import Path
from statistics import mean

from api.analytics.attention import narratives, signal_snapshots
from api.analytics.attention.discovery import (_coin, _percentile, eligibility, load_config, series_names,
                                               weights_for_day)
from api.analytics.attention.universe import load_universe_rows
from api.data.attention import registry, store
from api.data.attention.types import SourceSeries
from api.models.discovery import (DiscoveryCategoryDay, DiscoveryCategoryHistory, DiscoveryCoinHistory,
                                  DiscoveryHistoryDay, DiscoverySource)

NO_DATA = "no-attention-data"
TRENDS = "trends"
# Why Trends is missing on a chart day (SourceSeries.reason; internal, not in the payload).
NO_PULL = "no-pull-archive"
UNREADABLE_PULL = "unreadable-pull-archive"
SYMBOL_NOT_IN_PULL = "symbol-not-in-pull"
PULL_LAST_ROW_NOT_DAY = "pull-last-row-not-day"
NOT_PROBED = "not-probed"
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


def trends_pull_date(day: date) -> date:
    """The pull that holds chart day `day`: the one made on UTC date day+1 (it stores days < pull date)."""
    return day + timedelta(days=1)


class _TrendsPulls:
    """Trends from the per-pull archive, each pull file read at most once. `at(symbol, day)` is Trends as known on
    the run after `day`: the pull of `trends_pull_date(day)`, used only when its last row is `day`."""

    def __init__(self, probed: bool, min_days: int):
        self.probed, self.min_days = probed, min_days
        self._pulls: dict[date, dict[str, list[tuple[date, float]]] | str] = {}

    def _pull(self, pull_date: date) -> dict[str, list[tuple[date, float]]] | str:
        if pull_date not in self._pulls:
            if not store.pull_archive_path(TRENDS, pull_date).exists():
                self._pulls[pull_date] = NO_PULL
            else:
                try:
                    self._pulls[pull_date] = store.read_pull_archive(TRENDS, pull_date)
                except (OSError, ValueError, KeyError, TypeError):  # truncated or not parquet: missing, never a 500
                    self._pulls[pull_date] = UNREADABLE_PULL
        return self._pulls[pull_date]

    def _points(self, symbol: str, day: date) -> tuple[list[tuple[date, float]], str]:
        if not self.probed:
            return [], NOT_PROBED
        got = self._pull(trends_pull_date(day))
        if isinstance(got, str):
            return [], got
        pts = got.get(symbol)
        if not pts:
            return [], SYMBOL_NOT_IN_PULL
        if pts[-1][0] != day:
            return [], PULL_LAST_ROW_NOT_DAY
        return pts, ""

    def count(self, symbol: str, day: date) -> int:
        return len(self._points(symbol, day)[0])

    def at(self, symbol: str, day: date) -> SourceSeries:
        pts, reason = self._points(symbol, day)
        if not pts:
            return SourceSeries(TRENDS, symbol, [], "unavailable", reason)
        if len(pts) < self.min_days:
            return SourceSeries(TRENDS, symbol, [], "insufficient-history", f"{len(pts)} days in pull")
        return SourceSeries(TRENDS, symbol, pts, "ok")


class _PulledTrends:
    """The `_Stored` interface for Trends of one coin, backed by the shared pull archive."""

    def __init__(self, pulls: _TrendsPulls, symbol: str):
        self.pulls, self.symbol = pulls, symbol

    def count(self, day: date) -> int:
        return self.pulls.count(self.symbol, day)

    def at(self, day: date) -> SourceSeries:
        return self.pulls.at(self.symbol, day)


def _load(cfg: dict, symbols: list[str], probe_path: Path | None) -> dict[tuple[str, str], _Stored | _PulledTrends]:
    probed = registry.load_probe_records(probe_path)
    min_days = int(cfg["min_history_days"])
    pulls = _TrendsPulls(TRENDS in probed, min_days)
    return {(src, sym): _PulledTrends(pulls, sym) if src == TRENDS else _Stored(src, sym, src in probed, min_days)
            for src in sorted(series_names(cfg)) for sym in symbols}


def _frozen_trends(window: int, end: date) -> dict[tuple[date, str], DiscoverySource]:
    """(day, symbol) -> the Trends entry of that day's frozen snapshot for this window, for the chart's days."""
    out = {}
    for row in signal_snapshots.read_snapshots(_days(end, window)[0], end, window):
        for src in row.get("sources") or []:
            if src.get("source") == TRENDS:
                try:
                    out[(date.fromisoformat(row["date"]), row["symbol"])] = DiscoverySource(
                        source=TRENDS, change=float(src["change"]), as_of=str(src["as_of"]))
                except (KeyError, TypeError, ValueError):
                    pass  # a malformed entry is no record: the archive decides that day
    return out


def _file_ids(paths) -> tuple:
    out = []
    for p in paths:
        try:
            st = p.stat()
            out.append((p.name, st.st_mtime_ns, st.st_size, st.st_ino))
        except OSError:
            out.append((p.name,))
    return tuple(out)


def _signature(cfg: dict, symbols: list[str], probe_path: Path | None, window: int, end: date) -> tuple:
    """Everything a result depends on besides the arguments: config, probe records, and every stored file's
    identity (mtime, size, inode), so a backfill that rewrites old points also invalidates, not just a new day.
    Includes the Trends pulls and the frozen snapshots of the chart's days."""
    probed = registry.load_probe_records(probe_path)
    files = []
    for src in sorted(series_names(cfg)):
        for sym in symbols:
            try:
                st = store.store_path(src, sym).stat()
                files.append((src, sym, st.st_mtime_ns, st.st_size, st.st_ino))
            except OSError:
                files.append((src, sym))
    days = _days(end, window)
    pulls = _file_ids(store.pull_archive_path(TRENDS, trends_pull_date(d)) for d in days)
    snaps = _file_ids(signal_snapshots.snapshot_dir() / f"{d.isoformat()}_w{window}.json" for d in days)
    return (json.dumps(cfg, sort_keys=True), tuple(sorted(probed)), tuple(files), pulls, snaps)


def _cached(key: tuple, compute):
    hit = _cache.get(key)
    if hit is None:
        hit = _cache[key] = compute()
        while len(_cache) > CACHE_MAX:
            _cache.pop(next(iter(_cache)))
    return hit.model_copy(deep=True)


def _score_day(symbol: str, day: date, cfg: dict, stored, window: int, frozen: dict):
    data = {(src, sym): s.at(day) for (src, sym), s in stored.items() if sym == symbol}
    snap = frozen.get((day, symbol))
    return _coin(symbol, cfg, data, day, int(cfg["recent_days"]), window, int(cfg["max_source_lag_days"]),
                 frozen={TRENDS: snap} if snap is not None else None)


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
    rows, reason = load_universe_rows(universe_path)
    if not rows:
        return DiscoveryCoinHistory(**base, status="no-data", reason=reason, history_days={}, days=[])
    if sym not in eligibility(cfg, rows).eligible:
        raise UnknownSubject(f"unknown symbol {symbol!r}")

    def compute():
        stored = _load(cfg, [sym], probe_path)
        frozen = _frozen_trends(window, end)
        floor = float(cfg["min_covered_weight"])
        days = []
        for day in _days(end, window):
            c = _score_day(sym, day, cfg, stored, window, frozen)
            if c is not None:
                days.append(DiscoveryHistoryDay(date=day.isoformat(), score=c[0], covered_weight=c[1],
                                                rising_weight=c[2], trigger=c[3], thin=c[1] < floor,
                                                weights_version=c[5]))
        counts = {src: s.count(end) for (src, _), s in sorted(stored.items())}
        return DiscoveryCoinHistory(**base, status="ok" if days else "no-data",
                                    reason="" if days else NO_DATA, history_days=counts, days=days)

    return _cached(("coin", sym, window, end, _signature(cfg, [sym], probe_path, window, end)), compute)


def category_history(category_id: str, window: int, *, today: date, probe_path: Path | None = None,
                     universe_path: Path | None = None, config_path: Path | None = None
                     ) -> DiscoveryCategoryHistory:
    cfg = load_config(config_path)
    doc = narratives.load_narratives()
    end = today - timedelta(days=1)
    nid = narratives.resolve_id(category_id, doc, narratives.load_id_map())
    if nid is None:
        raise UnknownSubject(f"unknown category {category_id!r}")
    base = {**_base(cfg, nid, window, end), "membership_as_of": doc["as_of"]}
    rows, reason = load_universe_rows(universe_path)
    if not rows:
        return DiscoveryCategoryHistory(**base, status="no-data", reason=reason, days=[])
    eligible = eligibility(cfg, rows).eligible
    in_narrative = {c["symbol"] for n in doc["narratives"] if n["id"] == nid for c in n["coins"]}
    coins = [s for s in eligible if s in in_narrative]

    def compute():
        stored = _load(cfg, coins, probe_path)
        frozen = _frozen_trends(window, end)
        by_coin = {s: {k: v for k, v in stored.items() if k[1] == s} for s in coins}
        pct = float(cfg["winsor_percentile"])
        days = []
        for day in _days(end, window):
            scored = [c for c in (_score_day(s, day, cfg, by_coin[s], window, frozen) for s in coins) if c is not None]
            if not scored:
                continue
            raws = [c[0] for c in scored]
            cap = _percentile(raws, pct)
            triggered = sum(c[3] for c in scored)
            days.append(DiscoveryCategoryDay(date=day.isoformat(), score=mean(min(r, cap) for r in raws),
                                             coins_used=len(scored), triggered_count=triggered,
                                             triggered_share=triggered / len(scored),
                                             weights_version=weights_for_day(cfg, day)["weights_version"]))
        return DiscoveryCategoryHistory(**base, status="ok" if days else "no-data",
                                        reason="" if days else NO_DATA, days=days)

    return _cached(("category", nid, doc["as_of"], window, end, _signature(cfg, coins, probe_path, window, end)), compute)
