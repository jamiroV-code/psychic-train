"""Discovery: category momentum over the top-100 (S-F1, AC-41; weighted signal T101). Store and config only.

Per coin and weighted source: mean of the last `recent_days` completed days vs the mean of the
`window` days before them. Each source is anchored to its own newest stored day, if within `max_source_lag_days` of the window end.
A source with no usable change drops out of the coin's covered weight (never 0). Coin change =
sum(weight * change) / covered weight, winsorized at the category's p-th percentile. A source is rising
iff its raw change >= `rising_threshold_pct`; a coin triggers iff rising weight is at least `trigger_pct` percent
of covered weight and covered weight >= `min_covered_weight`. Category score = mean of coin changes, median beside.
A coin counts in each of its categories; there is no cross-category total.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median

from api.analytics.attention.universe import load_universe
from api.data.attention import categories_store, registry, universe_store
from api.models.discovery import DiscoveryCategory, DiscoveryCoin, DiscoveryExcluded, DiscoveryResponse, DiscoverySource

CONFIG_PATH = Path(__file__).resolve().parents[2] / "data" / "discovery.json"


SLOT = "exchange_activity"
WEIGHTED_SOURCES = (SLOT, "wikipedia", "trends", "reddit", "xsearch", "github_dev", "defillama")
# Exchange member -> registry series. Coinbase and Kraken have no fetcher yet (W7): not-probed, so they drop out.
EXCHANGE_SERIES = {"binance": "exchange_volume", "coinbase": "coinbase_volume", "kraken": "kraken_volume",
                   "hyperliquid": "hyperliquid_volume"}
FALLBACK_SERIES = "coingecko"
WEIGHT_SUM_TOLERANCE = 0.01


def _check_weights(name: str, weights, known) -> None:
    if not isinstance(weights, dict) or not weights:
        raise ValueError(f"discovery config: {name} must be a non-empty object")
    for k, v in weights.items():
        if k not in known:
            raise ValueError(f"discovery config: {name} has unknown key {k!r}; known: {', '.join(known)}")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
            raise ValueError(f"discovery config: {name}[{k!r}] must be a number >= 0")
    total = sum(weights.values())
    if abs(total - 100.0) > WEIGHT_SUM_TOLERANCE:
        raise ValueError(f"discovery config: {name} must sum to 100 (+/- {WEIGHT_SUM_TOLERANCE}), got {total}")


def validate_config(cfg: dict) -> dict:
    _check_weights("source_weights", cfg.get("source_weights"), WEIGHTED_SOURCES)
    _check_weights("exchange_sub_weights", cfg.get("exchange_sub_weights"), tuple(EXCHANGE_SERIES))
    for key, lo, hi in (("rising_threshold_pct", None, None), ("trigger_pct", 0, 100),
                        ("min_covered_weight", 0, 100), ("min_history_days", 1, None)):
        v = cfg.get(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or (lo is not None and v < lo) or (
                hi is not None and v > hi):
            raise ValueError(f"discovery config: {key} is missing or out of range")
    v = cfg.get("min_category_coins")
    if isinstance(v, bool) or not isinstance(v, int) or v < 1:
        raise ValueError("discovery config: min_category_coins is missing or not an integer >= 1")
    return cfg


def load_config(path: Path | None = None) -> dict:
    return validate_config(json.loads((path or CONFIG_PATH).read_text()))


def _percentile(vals: list[float], pct: float) -> float:
    """Linear interpolation between closest ranks."""
    s = sorted(vals)
    pos = (len(s) - 1) * pct / 100.0
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def _source_change(points: list[tuple[date, float]], end: date, recent: int, window: int,
                   max_lag: int) -> float | None:
    """Anchored to the source's own newest stored day; None when that is more than `max_lag` days before `end`."""
    if not points:
        return None
    last = max(d for d, _ in points)
    if (end - last).days > max_lag:
        return None
    end = min(end, last)
    cut = end - timedelta(days=recent)
    now = [v for d, v in points if cut < d <= end]
    base = [v for d, v in points if cut - timedelta(days=window) < d <= cut]
    if len(now) < recent or len(base) < max(window // 2, 1):
        return None
    base_mean = mean(base)
    if base_mean <= 0:
        return None
    return (mean(now) / base_mean - 1.0) * 100.0


def _is_rising(change: float, threshold_pct: float) -> bool:
    return change >= threshold_pct


def _as_of(points: list[tuple[date, float]], end: date) -> str:
    return min(end, max(d for d, _ in points)).isoformat()


def _series_source(label, data, series, symbol, end, recent, window, max_lag) -> DiscoverySource | None:
    sr = data[(series, symbol)]
    if sr.state != "ok":
        return None
    c = _source_change(sr.points, end, recent, window, max_lag)
    return None if c is None else DiscoverySource(source=label, change=c, as_of=_as_of(sr.points, end))


def _exchange_slot(symbol, sub_weights, data, end, recent, window, max_lag) -> DiscoverySource | None:
    """Sub-weighted mean of each exchange's own change over exchanges with data, rescaled; never sums volumes."""
    members = []
    for name, sw in sub_weights.items():
        m = _series_source(name, data, EXCHANGE_SERIES[name], symbol, end, recent, window, max_lag)
        if m is not None and sw > 0:
            members.append((sw, m))
    if not members:
        return None
    total = sum(sw for sw, _ in members)
    return DiscoverySource(source=SLOT, change=sum(sw * m.change for sw, m in members) / total,
                           as_of=max(m.as_of for _, m in members), members=[m for _, m in members])


def _coin(symbol, cfg, data, end, recent, window, max_lag) -> tuple[float, float, float, bool, list] | None:
    """(raw change %, covered weight, rising weight, trigger, sources) or None when no source is usable."""
    weights = cfg["source_weights"]
    found = []
    for src, w in weights.items():
        if w <= 0:
            continue
        if src == SLOT:
            s = _exchange_slot(symbol, cfg["exchange_sub_weights"], data, end, recent, window, max_lag)
            if s is None:
                s = _series_source(FALLBACK_SERIES, data, FALLBACK_SERIES, symbol, end, recent, window, max_lag)
        else:
            s = _series_source(src, data, src, symbol, end, recent, window, max_lag)
        if s is not None:
            found.append((w, s))
    if not found:
        return None
    covered = sum(w for w, _ in found)
    thr = float(cfg["rising_threshold_pct"])
    rising = sum(w for w, s in found if _is_rising(s.change, thr))
    trigger = rising * 100.0 >= float(cfg["trigger_pct"]) * covered and covered >= float(cfg["min_covered_weight"])
    return sum(w * s.change for w, s in found) / covered, covered, rising, trigger, [s for _, s in found]


def _empty(window, as_of, cats_asof, status, reason, usize=0, esize=0, cats=None, **extra) -> DiscoveryResponse:
    return DiscoveryResponse(window=window, as_of=as_of, categories_as_of=cats_asof, status=status,
                             reason=reason, universe_size=usize, eligible_size=esize, categories=cats or [], **extra)


def series_names(cfg: dict) -> set[str]:
    return {s for s in cfg["source_weights"] if s != SLOT} | set(EXCHANGE_SERIES.values()) | {FALLBACK_SERIES}


def _volumes() -> dict:
    return {str(r.get("symbol", "")).upper(): r.get("volume_24h")
            for r in (universe_store.read_latest() or {}).get("coins", []) if isinstance(r, dict)}


def _excluded_symbols(cfg: dict, members: dict[str, set[str]]) -> set[str]:
    excluded = {str(s).upper() for s in cfg.get("exclude", [])}
    for cid in cfg.get("exclude_category_ids", []):
        excluded |= members.get(cid, set())
    return excluded - ({str(s).upper() for s in cfg.get("include_despite_category", [])} - {
        str(s).upper() for s in cfg.get("exclude", [])})


def _members(cats: dict) -> dict[str, set[str]]:
    return {c["id"]: {str(s).upper() for s in c.get("symbols", [])} for c in cats["categories"]}


def eligibility(cfg: dict, symbols: list[str], cats: dict) -> tuple[list[str], dict[str, set[str]]]:
    """(eligible symbols in universe order, category id -> member symbols)."""
    vols = _volumes()
    floor = float(cfg["min_volume_24h_usd"])
    members = _members(cats)
    excluded = _excluded_symbols(cfg, members)
    eligible = [s for s in symbols if s not in excluded
                and isinstance(vols.get(s), (int, float)) and vols[s] >= floor]
    return eligible, members


def _excluded_counts(cfg: dict, symbols: list[str], eligible: list[str], members: dict[str, set[str]],
                     shown: set[str]) -> DiscoveryExcluded:
    """Why each top-N coin is not shown; the first matching reason wins, so the counts are disjoint."""
    excluded = _excluded_symbols(cfg, members)
    listed = set().union(*(members.get(c["id"], set()) for c in cfg["categories"]))
    ok = set(eligible)
    out = {"exclusion_list": 0, "below_volume_floor": 0, "no_category": 0, "no_source_data": 0}
    for s in symbols:
        if s in shown:
            continue
        if s in excluded:
            out["exclusion_list"] += 1
        elif s not in ok:
            out["below_volume_floor"] += 1
        elif s not in listed:
            out["no_category"] += 1
        else:
            out["no_source_data"] += 1
    return DiscoveryExcluded(**out)


def build_discovery(window: int, *, today: date, probe_path: Path | None = None,
                    weights_path: Path | None = None, universe_path: Path | None = None,
                    config_path: Path | None = None) -> DiscoveryResponse:
    cfg = load_config(config_path)
    end = today - timedelta(days=1)
    as_of = end.isoformat()
    symbols, reason = load_universe(universe_path)
    if not symbols:
        return _empty(window, as_of, "", "no-data", reason)
    cats = categories_store.read_latest()
    if not cats or not cats.get("categories"):
        return _empty(window, as_of, "", "no-data", "categories-missing", len(symbols))
    cats_asof = str(cats["date"])

    eligible, members = eligibility(cfg, symbols, cats)

    series = series_names(cfg)
    data = {(src, sym): registry.read_series(src, sym, today, probe_path) for src in series for sym in eligible}
    recent, max_lag = int(cfg["recent_days"]), int(cfg["max_source_lag_days"])
    coins = {s: _coin(s, cfg, data, end, recent, window, max_lag) for s in eligible}
    if not any(coins.values()):
        return _empty(window, as_of, cats_asof, "no-data", "no-attention-data", len(symbols), len(eligible))

    min_coins = int(cfg["min_category_coins"])
    out = []
    for spec in cfg["categories"]:
        used = [(s, coins[s]) for s in eligible if s in members.get(spec["id"], set()) and coins[s]]
        raws = [c[0] for _, c in used]
        cap = _percentile(raws, float(cfg["winsor_percentile"])) if raws else None
        rows = [DiscoveryCoin(symbol=s, change=min(c[0], cap), raw_change=c[0], covered_weight=c[1],
                              rising_weight=c[2], trigger=c[3], sources=c[4]) for s, c in used]
        rows.sort(key=lambda r: r.change, reverse=True)
        changes = [r.change for r in rows]
        out.append(DiscoveryCategory(
            id=spec["id"], name=spec["name"], score=mean(changes) if changes else None,
            median=median(changes) if changes else None, coins_used=len(rows),
            gaining_count=sum(r.trigger for r in rows), ranked=len(rows) >= min_coins, coins=rows))
    out.sort(key=lambda c: (not c.ranked, c.score is None, -(c.score or 0.0)))
    shown = {r.symbol for c in out for r in c.coins}
    return _empty(window, as_of, cats_asof, "ok", "", len(symbols), len(eligible), out, shown_size=len(shown),
                  excluded=_excluded_counts(cfg, symbols, eligible, members, shown), min_category_coins=min_coins,
                  rising_threshold_pct=float(cfg["rising_threshold_pct"]),
                  min_covered_weight=float(cfg["min_covered_weight"]))
