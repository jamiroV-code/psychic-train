"""Discovery: category momentum over the top-100 (S-F1, AC-41; weighted signal T101). Store and config only.

Per coin and weighted source: mean of the last `recent_days` completed days vs the mean of the
`window` days before them. Each source is anchored to its own newest stored day, if within `max_source_lag_days` of the window end.
A source with no usable change drops out of the coin's covered weight (never 0). Coin change =
sum(weight * change) / covered weight, winsorized at the category's p-th percentile. A source is rising
iff its raw change >= `rising_threshold_pct`; a coin triggers iff rising weight is at least `trigger_pct` percent
of covered weight and covered weight >= `min_covered_weight`. Category score = mean of coin changes, median beside.
A coin counts in each of its categories; there is no cross-category total.

Weights v2 (T130): weights need not sum to 100; weight 0 parks a source (not read, not counted). A `source_groups`
group votes once: it is rising iff its rising members hold at least half of its available weight, and then adds that
whole weight to the rising weight (covered weight and score are unchanged). A coin can only trigger when one of
`early_sources` is itself rising. The weights in force for a day come from `weights_for_day`: an older version in
`weights_history` covers the days up to its `until`, so a past day is never rescored with newer weights.

Fallback coverage only (T204, weights v3): in a version with `fallback_coverage_only`, the CoinGecko volume fallback
filling the exchange slot still counts toward covered weight and the score, but never as a rising vote: its weight is
left out of the rising weight and it cannot pass the early-source gate. A real exchange in the slot votes as before.

Categories are the narratives of `attention_narratives.json` (U1): membership comes from that file, never from
CoinGecko categories. Eligibility (U2) is `universe_classes`: class exclusion, then tradeability, then IN; the only
volume rule is that exactly zero 24h volume means no trading market (T189), and every top-N coin that is not shown
carries a reason from a closed list.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median

from api.analytics.attention import narratives, universe_classes
from api.analytics.attention.universe import load_universe_rows
from api.data.attention import registry
from api.models.discovery import (DiscoveryCategory, DiscoveryCoin, DiscoveryExcluded, DiscoveryExcludedCoin,
                                  DiscoveryHiddenNarrative, DiscoveryResponse, DiscoverySource, DiscoveryVenueList)

CONFIG_PATH = Path(__file__).resolve().parents[2] / "data" / "discovery.json"


SLOT = "exchange_activity"
WEIGHTED_SOURCES = (SLOT, "wikipedia", "trends", "reddit", "xsearch", "github_dev", "defillama")
# Exchange member -> registry series. Coinbase and Kraken have no fetcher yet (W7): not-probed, so they drop out.
EXCHANGE_SERIES = {"binance": "exchange_volume", "coinbase": "coinbase_volume", "kraken": "kraken_volume",
                   "hyperliquid": "hyperliquid_volume"}
FALLBACK_SERIES = "coingecko"
WEIGHT_SUM_TOLERANCE = 0.01
GROUP_RISING_SHARE = 0.5
# Per-version keys: top-level for the current version, and in each `weights_history` entry for older ones.
VERSION_KEYS = ("source_weights", "source_groups", "early_sources", "fallback_coverage_only")
CONFIG_KEYS = {"source_weights", "source_groups", "early_sources", "fallback_coverage_only", "weights_version",
               "weights_history",
               "exchange_sub_weights", "rising_threshold_pct", "trigger_pct", "min_covered_weight",
               "min_history_days", "winsor_percentile", "recent_days", "max_source_lag_days", "universe_rules"}
# Moved or removed by U1: a stale local config fails loudly instead of being half-read.
REMOVED_KEYS = {"categories": "categories come from attention_narratives.json",
                "min_category_coins": "moved to universe_rules.min_narrative_coins"}


def _check_weights(name: str, weights, known, sum_100: bool = True) -> None:
    if not isinstance(weights, dict) or not weights:
        raise ValueError(f"discovery config: {name} must be a non-empty object")
    for k, v in weights.items():
        if k not in known:
            raise ValueError(f"discovery config: {name} has unknown key {k!r}; known: {', '.join(known)}")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
            raise ValueError(f"discovery config: {name}[{k!r}] must be a number >= 0")
    total = sum(weights.values())
    if sum_100 and abs(total - 100.0) > WEIGHT_SUM_TOLERANCE:
        raise ValueError(f"discovery config: {name} must sum to 100 (+/- {WEIGHT_SUM_TOLERANCE}), got {total}")
    if total <= 0:
        raise ValueError(f"discovery config: {name} must give some source a weight > 0")


def _check_version(name: str, v: dict) -> None:
    """source_weights, source_groups, early_sources and fallback_coverage_only of one weights version."""
    _check_weights(f"{name}source_weights", v.get("source_weights"), WEIGHTED_SOURCES, sum_100=False)
    groups, seen = v.get("source_groups", {}), set()
    if not isinstance(groups, dict):
        raise ValueError(f"discovery config: {name}source_groups must be an object")
    for g, members in groups.items():
        if not isinstance(members, list) or not members or any(m not in WEIGHTED_SOURCES for m in members):
            raise ValueError(f"discovery config: {name}source_groups[{g!r}] must list known source ids")
        if seen & set(members):
            raise ValueError(f"discovery config: {name}source_groups: a source is in two groups")
        seen |= set(members)
    early = v.get("early_sources", [])
    if not isinstance(early, list) or any(e not in WEIGHTED_SOURCES for e in early):
        raise ValueError(f"discovery config: {name}early_sources must list known source ids")
    if not isinstance(v.get("fallback_coverage_only", False), bool):
        raise ValueError(f"discovery config: {name}fallback_coverage_only must be true or false")


def _check_history(cfg: dict) -> None:
    current = cfg.get("weights_version", 1)
    if isinstance(current, bool) or not isinstance(current, int) or current < 1:
        raise ValueError("discovery config: weights_version must be an integer >= 1")
    history = cfg.get("weights_history", [])
    if not isinstance(history, list):
        raise ValueError("discovery config: weights_history must be a list")
    prev_v, prev_until = 0, None
    for i, h in enumerate(history):
        name = f"weights_history[{i}]."
        if not isinstance(h, dict) or set(h) - {"weights_version", "until", *VERSION_KEYS}:
            raise ValueError(f"discovery config: {name[:-1]} has unknown keys")
        v = h.get("weights_version")
        try:
            until = date.fromisoformat(h.get("until"))
        except (TypeError, ValueError):
            raise ValueError(f"discovery config: {name}until must be an ISO date") from None
        if isinstance(v, bool) or not isinstance(v, int) or not prev_v < v < current:
            raise ValueError(f"discovery config: {name}weights_version must increase and stay below "
                             f"weights_version {current}")
        if prev_until is not None and until <= prev_until:
            raise ValueError(f"discovery config: {name}until must be after the previous entry's")
        _check_version(name, h)
        prev_v, prev_until = v, until


def weights_for_day(cfg: dict, day: date) -> dict:
    """The weights version scoring `day`: the first `weights_history` entry with day <= until, else the current."""
    for h in cfg.get("weights_history", []):
        if day <= date.fromisoformat(h["until"]):
            v = h
            break
    else:
        v = {**cfg, "weights_version": cfg.get("weights_version", 1)}
    return {"weights_version": v["weights_version"], "source_weights": v["source_weights"],
            "source_groups": v.get("source_groups", {}), "early_sources": v.get("early_sources", []),
            "fallback_coverage_only": v.get("fallback_coverage_only", False)}


def validate_config(cfg: dict) -> dict:
    for key, why in REMOVED_KEYS.items():
        if key in cfg:
            raise ValueError(f"discovery config: {key} is no longer read ({why})")
    _check_version("", cfg)
    _check_history(cfg)
    _check_weights("exchange_sub_weights", cfg.get("exchange_sub_weights"), tuple(EXCHANGE_SERIES))
    for key, lo, hi in (("rising_threshold_pct", None, None), ("trigger_pct", 0, 100),
                        ("min_covered_weight", 0, 100), ("min_history_days", 1, None)):
        v = cfg.get(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or (lo is not None and v < lo) or (
                hi is not None and v > hi):
            raise ValueError(f"discovery config: {key} is missing or out of range")
    rules = cfg.get("universe_rules")
    v = rules.get("min_narrative_coins") if isinstance(rules, dict) else None
    if isinstance(v, bool) or not isinstance(v, int) or v < 1:
        raise ValueError("discovery config: universe_rules.min_narrative_coins is missing or not an integer >= 1")
    universe_classes.validate_rules(cfg)   # names the keys it retired before the generic check below
    unknown = sorted(set(cfg) - CONFIG_KEYS)
    if unknown:
        raise ValueError(f"discovery config: unknown keys {', '.join(unknown)}")
    return cfg


def min_narrative_coins(cfg: dict) -> int:
    return int(cfg["universe_rules"]["min_narrative_coins"])


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


def _rising_weight(found: list[tuple[str, float, DiscoverySource]], groups: dict, thr: float) -> float:
    """Ungrouped sources count on their own; a group counts its available weight once, if half of it is rising."""
    group_of = {m: g for g, members in groups.items() for m in members}
    rising, per_group = 0.0, {}
    for src, w, s in found:
        up = _is_rising(s.change, thr)
        if src in group_of:
            tot = per_group.setdefault(group_of[src], [0.0, 0.0])
            tot[0] += w
            tot[1] += w if up else 0.0
        elif up:
            rising += w
    return rising + sum(tot for tot, up in per_group.values() if up >= GROUP_RISING_SHARE * tot)


def _coin(symbol, cfg, data, end, recent, window, max_lag, frozen=None
          ) -> tuple[float, float, float, bool, list, int] | None:
    """(raw change %, covered weight, rising weight, trigger, sources, weights version) or None when no source
    is usable. `end` is the scored day and picks the weights version. `frozen` (history only, T175): source ->
    DiscoverySource already recorded for `end`, used instead of recomputing that source from `data`."""
    wv = weights_for_day(cfg, end)
    found = []
    for src, w in wv["source_weights"].items():
        if w <= 0:
            continue
        if src == SLOT:
            s = _exchange_slot(symbol, cfg["exchange_sub_weights"], data, end, recent, window, max_lag)
            if s is None:
                s = _series_source(FALLBACK_SERIES, data, FALLBACK_SERIES, symbol, end, recent, window, max_lag)
                if s is not None and wv["fallback_coverage_only"]:
                    s.coverage_only = True
        elif frozen and src in frozen:
            s = frozen[src]
        else:
            s = _series_source(src, data, src, symbol, end, recent, window, max_lag)
        if s is not None:
            found.append((src, w, s))
    if not found:
        return None
    covered = sum(w for _, w, _ in found)
    thr = float(cfg["rising_threshold_pct"])
    voters = [f for f in found if not f[2].coverage_only]
    rising = _rising_weight(voters, wv["source_groups"], thr)
    early = wv["early_sources"]
    early_ok = not early or any(src in early and _is_rising(s.change, thr) for src, _, s in voters)
    trigger = (early_ok and rising * 100.0 >= float(cfg["trigger_pct"]) * covered
               and covered >= float(cfg["min_covered_weight"]))
    return (sum(w * s.change for _, w, s in found) / covered, covered, rising, trigger, [s for _, _, s in found],
            wv["weights_version"])


def _empty(window, as_of, cats_asof, status, reason, usize=0, esize=0, cats=None, **extra) -> DiscoveryResponse:
    return DiscoveryResponse(window=window, as_of=as_of, categories_as_of=cats_asof, status=status,
                             reason=reason, universe_size=usize, eligible_size=esize, categories=cats or [], **extra)


def series_names(cfg: dict) -> set[str]:
    """Series read for scoring: every source weighted > 0 in the current or any older weights version."""
    versions = [cfg, *cfg.get("weights_history", [])]
    weighted = {s for v in versions for s, w in v["source_weights"].items() if w > 0 and s != SLOT}
    return weighted | set(EXCHANGE_SERIES.values()) | {FALLBACK_SERIES}


def eligibility(cfg: dict, rows: list[dict], venues=None, today: date | None = None) -> universe_classes.Universe:
    """Class exclusion -> tradeability -> IN over the universe rows; `.eligible` is the IN set in universe order.
    `venues` None reads the stored venue lists as of `today`."""
    return universe_classes.build(rows, cfg["universe_rules"], venues, today)


def eligible_discovery_symbols(*, config_path: Path | None = None, universe_path: Path | None = None) -> list[str]:
    """The coins that pass into Discovery today (`eligibility` over the shipped config and universe snapshot)."""
    rows, _ = load_universe_rows(universe_path)
    return eligibility(load_config(config_path), rows).eligible if rows else []


def _excluded(u: universe_classes.Universe, nm: narratives.Memberships, shown: set[str]) -> dict:
    """Every universe coin not shown, with one reason; first match wins, so the counts are disjoint."""
    hidden_only = {s for h in nm.hidden for s in h["coins"]} - set().union(set(), *nm.visible.values())
    unassigned = set(nm.unassigned)
    coins = []
    for r in u.rows:
        s = r["symbol"]
        if s in shown:
            continue
        if s in u.out:
            reason, detail = u.out[s]
        elif s in unassigned:
            reason, detail = "unassigned", "in no narrative"
        elif s in hidden_only:
            reason, detail = "hidden-narrative", "only in hidden narratives"
        else:
            reason, detail = "no-source-data", "no source has usable data"
        coins.append(DiscoveryExcludedCoin(symbol=s, reason=reason, detail=detail))
    counts = {k: sum(c.reason == k for c in coins) for k in universe_classes.REASONS}
    legacy = DiscoveryExcluded(
        exclusion_list=sum(counts[k] for k in ("stablecoin", "wrapped-staked", "no-market", "not-tradeable-config",
                                               "not-tradeable")),
        below_volume_floor=0, no_category=counts["unassigned"] + counts["hidden-narrative"],
        no_source_data=counts["no-source-data"])
    return {"excluded_coins": coins, "excluded_counts": counts, "excluded": legacy}


def build_discovery(window: int, *, today: date, probe_path: Path | None = None,
                    weights_path: Path | None = None, universe_path: Path | None = None,
                    config_path: Path | None = None) -> DiscoveryResponse:
    cfg = load_config(config_path)
    doc = narratives.load_narratives()
    end = today - timedelta(days=1)
    as_of = end.isoformat()
    wver = weights_for_day(cfg, end)["weights_version"]
    urows, reason = load_universe_rows(universe_path)
    if not urows:
        return _empty(window, as_of, doc["as_of"], "no-data", reason, narratives_status=doc["status"],
                      weights_version=wver)
    u = eligibility(cfg, urows, today=today)
    eligible = u.eligible
    min_coins = min_narrative_coins(cfg)
    nm = narratives.memberships(eligible, min_coins, doc)
    cats_asof = nm.as_of
    flags = {"narratives_status": nm.status, "unassigned": nm.unassigned, "weights_version": wver,
             "hidden_narratives": [DiscoveryHiddenNarrative(**h) for h in nm.hidden],
             "venue_lists": [DiscoveryVenueList(venue=v.venue, status=v.state, as_of=v.as_of)
                             for v in u.venues.values()],
             "tradeability_data_suspect": u.data_suspect}

    series = series_names(cfg)
    data = {(src, sym): registry.read_series(src, sym, today, probe_path) for src in series for sym in eligible}
    recent, max_lag = int(cfg["recent_days"]), int(cfg["max_source_lag_days"])
    coins = {s: _coin(s, cfg, data, end, recent, window, max_lag) for s in eligible}
    if not any(coins.values()):
        return _empty(window, as_of, cats_asof, "no-data", "no-attention-data", len(urows), len(eligible), **flags,
                      **_excluded(u, nm, set()))

    out = []
    for nid, in_narrative in nm.visible.items():
        used = [(s, coins[s]) for s in eligible if s in in_narrative and coins[s]]
        raws = [c[0] for _, c in used]
        cap = _percentile(raws, float(cfg["winsor_percentile"])) if raws else None
        rows = [DiscoveryCoin(symbol=s, change=min(c[0], cap), raw_change=c[0], covered_weight=c[1],
                              rising_weight=c[2], trigger=c[3], sources=c[4], primary=nm.primary.get(s) == nid,
                              volume_24h=u.volume[s], thin_volume=u.thin[s], tradeability=u.tradeability[s])
                for s, c in used]
        rows.sort(key=lambda r: r.change, reverse=True)
        changes = [r.change for r in rows]
        out.append(DiscoveryCategory(
            id=nid, name=nm.names[nid], score=mean(changes) if changes else None,
            median=median(changes) if changes else None, coins_used=len(rows),
            gaining_count=sum(r.trigger for r in rows), ranked=len(rows) >= min_coins, coins=rows))
    out.sort(key=lambda c: (not c.ranked, c.score is None, -(c.score or 0.0)))
    shown = {r.symbol for c in out for r in c.coins}
    return _empty(window, as_of, cats_asof, "ok", "", len(urows), len(eligible), out, shown_size=len(shown),
                  tradeability_unknown=sum(u.tradeability[s] == "unverified" for s in shown),
                  **_excluded(u, nm, shown),
                  min_category_coins=min_coins, rising_threshold_pct=float(cfg["rising_threshold_pct"]),
                  min_covered_weight=float(cfg["min_covered_weight"]), **flags)
