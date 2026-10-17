"""Discovery: category momentum over the top-100 (S-F1, AC-41). Store and config only.

Per coin and source: mean of the last `recent_days` completed days vs the mean of the
`window` days before them. A coin is "gaining" iff at least `min_independent_sources`
independent source groups rise. Coin change = mean of its per-source changes (percent),
winsorized at the category's p-th percentile. Category score = mean of those, median beside.
A coin counts in each of its categories; there is no cross-category total.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median

from api.analytics.attention.score import load_weights
from api.analytics.attention.universe import load_universe
from api.data.attention import categories_store, registry, universe_store
from api.models.discovery import DiscoveryCategory, DiscoveryCoin, DiscoveryResponse

CONFIG_PATH = Path(__file__).resolve().parents[2] / "data" / "discovery.json"


def load_config(path: Path | None = None) -> dict:
    return json.loads((path or CONFIG_PATH).read_text())


def _percentile(vals: list[float], pct: float) -> float:
    """Linear interpolation between closest ranks."""
    s = sorted(vals)
    pos = (len(s) - 1) * pct / 100.0
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def _source_change(points: list[tuple[date, float]], end: date, recent: int, window: int) -> float | None:
    cut = end - timedelta(days=recent)
    now = [v for d, v in points if cut < d <= end]
    base = [v for d, v in points if cut - timedelta(days=window) < d <= cut]
    if len(now) < recent or len(base) < max(window // 2, 1):
        return None
    base_mean = mean(base)
    if base_mean <= 0:
        return None
    return (mean(now) / base_mean - 1.0) * 100.0


def _coin(symbol, sources, groups, data, end, recent, window, need) -> tuple[float, int, int, bool] | None:
    """(raw change %, sources used, sources gaining, gaining) or None with under 2 usable sources."""
    changes = []
    for s in sources:
        sr = data[(s, symbol)]
        c = _source_change(sr.points, end, recent, window) if sr.state == "ok" else None
        if c is not None:
            changes.append((s, c))
    if len(changes) < need:
        return None
    rising = {groups.get(s, s) for s, c in changes if c > 0}
    return mean(c for _, c in changes), len(changes), len(rising), len(rising) >= need


def _empty(window, as_of, cats_asof, status, reason, usize=0, esize=0, cats=None) -> DiscoveryResponse:
    return DiscoveryResponse(window=window, as_of=as_of, categories_as_of=cats_asof, status=status,
                             reason=reason, universe_size=usize, eligible_size=esize, categories=cats or [])


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

    vols = {str(r.get("symbol", "")).upper(): r.get("volume_24h")
            for r in (universe_store.read_latest() or {}).get("coins", []) if isinstance(r, dict)}
    floor = float(cfg["min_volume_24h_usd"])
    excluded = {str(s).upper() for s in cfg.get("exclude", [])}
    members = {c["id"]: {str(s).upper() for s in c.get("symbols", [])} for c in cats["categories"]}
    for cid in cfg.get("exclude_category_ids", []):
        excluded |= members.get(cid, set())
    eligible = [s for s in symbols if s not in excluded
                and isinstance(vols.get(s), (int, float)) and vols[s] >= floor]

    sources = list(load_weights(weights_path))
    data = {(src, sym): registry.read_series(src, sym, today, probe_path) for src in sources for sym in eligible}
    need, recent = int(cfg["min_independent_sources"]), int(cfg["recent_days"])
    groups = cfg.get("source_groups", {})
    coins = {s: _coin(s, sources, groups, data, end, recent, window, need) for s in eligible}
    if not any(coins.values()):
        return _empty(window, as_of, cats_asof, "no-data", "no-attention-data", len(symbols), len(eligible))

    out = []
    for spec in cfg["categories"]:
        used = [(s, coins[s]) for s in eligible if s in members.get(spec["id"], set()) and coins[s]]
        raws = [c[0] for _, c in used]
        cap = _percentile(raws, float(cfg["winsor_percentile"])) if raws else None
        rows = [DiscoveryCoin(symbol=s, change=min(c[0], cap), raw_change=c[0], gaining=c[3],
                              sources_used=c[1], sources_gaining=c[2]) for s, c in used]
        rows.sort(key=lambda r: r.change, reverse=True)
        changes = [r.change for r in rows]
        out.append(DiscoveryCategory(
            id=spec["id"], name=spec["name"], score=mean(changes) if changes else None,
            median=median(changes) if changes else None, coins_used=len(rows),
            gaining_count=sum(r.gaining for r in rows), coins=rows))
    out.sort(key=lambda c: (c.score is None, -(c.score or 0.0)))
    return _empty(window, as_of, cats_asof, "ok", "", len(symbols), len(eligible), out)
