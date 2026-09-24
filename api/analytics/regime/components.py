"""Regime dashboard: the six LiqTide components, reproduced from primary
series, plus the reproduced and published tide index (RFC-002).

Every number here is computed from the local cache — FRED and DefiLlama via
their cache-first adapters, LiqTide only from its archive — never from a live
LiqTide call (VALIDATE P1).

Reproduction (RFC-002 Stage 0, verified on the 2026-09-24 live payload):

- Each component is ``sign * tanh(impulse / scale)``. LiqTide does not
  publish this, but all six published components match it to 4 decimals with
  the round scales in ``COMPONENTS`` below.
- Composite ``score = sum(w_i * x_i)``; published index ``value =
  round(50 + 50 * score)``. With a component missing, this module renormalises
  over the weights present and reports the coverage (ADR-5).
- Impulses use calendar-day as-of lookups — "the latest observation on or
  before date - N days" — never a row count (VALIDATE P4). Business-day FRED
  rows made the older `liquidity_composite._roc` windows longer than their
  names (see backlog `liquidity-composite-calendar-windows_24-09-26.md`).
- Net liquidity is WALCL - WDTGAL - RRPONTSYD*1000 on the Wednesday (H.4.1)
  grid, which matches LiqTide's published series exactly. It stays weekly: no
  value is carried onto days between releases.

Nothing is zero-filled or interpolated. A date without an input simply has
no point; each component's `status`/`reason` says why.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from api.data import cache, defillama_adapter, etf_flows_adapter, fred_adapter, liqtide_adapter

ETF_LAUNCH_DATE = pd.Timestamp("2024-01-11")
AVAILABILITY_WEIGHT_THRESHOLD = 0.60  # same floor and rationale as liquidity_composite
MIN_COMPOSITE_COMPONENTS = 1


@dataclass(frozen=True)
class ComponentSpec:
    id: str
    liqtide_key: str  # key in LiqTide's `tide_index.components`
    label: str
    weight: float
    sign: int  # +1, or -1 for the inverted components
    scale: float  # impulse units per tanh unit
    window_days: int
    max_lag_days: int  # how stale the "N days ago" lookup may be
    fresh_days: int  # how old the latest value may be and still enter the composite
    frequency: str
    source: str
    transform: str
    unit: str
    # First date the component can exist at all (RFC-004 decision 1). Before
    # it the component is `not_applicable`, which is a different state from
    # `unavailable` (the source failed) and `no_data` (history too short).
    applicable_from: pd.Timestamp | None = None


COMPONENTS: tuple[ComponentSpec, ...] = (
    ComponentSpec(
        "net_liquidity", "net_liquidity_4w", "Net liquidity (4-week change)", 0.30, +1, 150e9, 28, 3, 10,
        "weekly (Wednesday, H.4.1)", "FRED: WALCL − WDTGAL − RRPONTSYD×1000",
        "level(t) − level(t − 28 days); contribution = tanh(Δ / $150bn)", "USD",
    ),
    ComponentSpec(
        "stablecoin_supply", "stablecoin_7d", "Stablecoin supply (7-day change)", 0.25, +1, 0.01, 7, 3, 3,
        "daily", "DefiLlama: total circulating USD-pegged supply",
        "level(t) / level(t − 7 days) − 1; contribution = tanh(Δ% / 1%)", "fraction",
    ),
    ComponentSpec(
        "broad_dollar", "dollar_1m", "Broad dollar, inverted (1-month change)", 0.15, -1, 0.02, 30, 5, 10,
        "daily (business days)", "FRED: DTWEXBGS",
        "level(t) / level(t − 30 days) − 1; contribution = −tanh(Δ% / 2%)", "fraction",
    ),
    ComponentSpec(
        "rrp_release", "rrp_release_4w", "ON-RRP release (4-week change)", 0.10, -1, 75e9, 28, 5, 5,
        "daily (business days)", "FRED: RRPONTSYD",
        "level(t) − level(t − 28 days); contribution = −tanh(Δ / $75bn)", "USD",
    ),
    ComponentSpec(
        "etf_flows", "etf_flow_5d", "Spot-BTC ETF net flows (5-day sum)", 0.10, +1, 1e9, 5, 9, 5,
        "daily (trading days)", "Farside `Total` column (US$m; personal use only), LiqTide `metrics.etf_flows` archive for dates Farside lacks",
        "sum of the last 5 daily net flows; contribution = tanh(Σ / $1bn)", "USD",
        ETF_LAUNCH_DATE,
    ),
    ComponentSpec(
        "btc_dominance", "rotation_30d", "BTC dominance, inverted (30-day change)", 0.10, -1, 2.0, 30, 5, 3,
        "daily (thinned before archive start)", "LiqTide `metrics.btc_dom` archive (CoinGecko upstream)",
        "level(t) − level(t − 30 days), percentage points; contribution = −tanh(Δ / 2pp)", "percentage points",
    ),
)
SPEC_BY_ID = {spec.id: spec for spec in COMPONENTS}


@dataclass
class ComponentSeries:
    spec: ComponentSpec
    # columns: date (tz-naive Timestamp), value (impulse), raw (level), contribution
    points: pd.DataFrame
    status: str  # ok | stale | unavailable | no_data | not_applicable (see status_for_range)
    reason: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def first_date(self) -> str | None:
        return None if self.points.empty else self.points["date"].min().strftime("%Y-%m-%d")

    @property
    def last_date(self) -> str | None:
        return None if self.points.empty else self.points["date"].max().strftime("%Y-%m-%d")


@dataclass
class RegimeComponentsResult:
    components: list[ComponentSeries]
    reproduced: pd.DataFrame  # date, value, coverage, components_present
    published: pd.DataFrame  # date, value, label
    agreement: dict
    grid_dates: list[str]


# ---------------------------------------------------------------- helpers


def normalise(impulse: float, spec: ComponentSpec) -> float:
    """LiqTide's per-component normalisation: sign * tanh(impulse / scale)."""
    return spec.sign * math.tanh(impulse / spec.scale)


def _clean(df: pd.DataFrame) -> pd.Series:
    """`date, value` frame -> tz-naive, date-normalised, sorted Series."""
    if df is None or df.empty:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    out = df[["date", "value"]].dropna().copy()
    dates = pd.to_datetime(out["date"], utc=True, errors="coerce")
    out["date"] = dates.dt.tz_localize(None).dt.normalize()
    out = out.dropna(subset=["date"]).drop_duplicates(subset="date", keep="last").sort_values("date")
    return out.set_index("date")["value"].astype(float)


def asof_lookup(series: pd.Series, dates: pd.DatetimeIndex, lag_days: int, max_lag_days: int) -> pd.Series:
    """Value of `series` as of (date - lag_days): the latest observation on or
    before that day, provided it is no more than `max_lag_days` older.
    Otherwise NaN. Calendar-based, never a row offset."""
    if series.empty:
        return pd.Series(np.nan, index=dates)
    targets = pd.DataFrame({"target": dates - pd.Timedelta(days=lag_days)}, index=dates).sort_values("target")
    src = pd.DataFrame({"obs_date": series.index, "value": series.values}).sort_values("obs_date")
    merged = pd.merge_asof(targets, src, left_on="target", right_on="obs_date", direction="backward")
    stale = (merged["target"] - merged["obs_date"]) > pd.Timedelta(days=max_lag_days)
    merged.loc[stale, "value"] = np.nan
    return pd.Series(merged["value"].to_numpy(), index=targets.index).reindex(dates)


def _finish(spec: ComponentSpec, level: pd.Series, impulse: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame({"date": impulse.index, "value": impulse.values, "raw": level.reindex(impulse.index).values})
    df = df.dropna(subset=["value"]).reset_index(drop=True)
    df["contribution"] = [normalise(v, spec) for v in df["value"]]
    return df


def change_component(spec: ComponentSpec, level: pd.Series, relative: bool) -> pd.DataFrame:
    """Impulse = level(t) − level(t − N days)  (or ratio − 1 when relative)."""
    if level.empty:
        return pd.DataFrame(columns=["date", "value", "raw", "contribution"])
    prior = asof_lookup(level, level.index, spec.window_days, spec.max_lag_days)
    impulse = (level / prior - 1.0) if relative else (level - prior)
    impulse = impulse.replace([np.inf, -np.inf], np.nan)
    return _finish(spec, level, impulse)


def rolling_sum_component(spec: ComponentSpec, flows: pd.Series, n: int = 5) -> pd.DataFrame:
    """Impulse = sum of the last `n` daily observations, only when those `n`
    observations span at most `spec.max_lag_days` calendar days (so a gap in
    the record never silently widens the window)."""
    if len(flows) < n:
        return pd.DataFrame(columns=["date", "value", "raw", "contribution"])
    sums = flows.rolling(n).sum()
    span_days = pd.Series(flows.index, index=flows.index).diff(n - 1).dt.days
    sums[span_days > spec.max_lag_days] = np.nan
    return _finish(spec, flows, sums)


def _status(adapter_status: str, points: pd.DataFrame) -> tuple[str, str | None]:
    if points.empty:
        if adapter_status == "unavailable":
            return "unavailable", "source unavailable and nothing cached"
        return "no_data", "not enough history for the change window yet"
    if adapter_status == "stale":
        return "stale", "latest refresh failed; showing cached data"
    return "ok", None


# ---------------------------------------------------------------- builders


def build_net_liquidity() -> ComponentSeries:
    spec = SPEC_BY_ID["net_liquidity"]
    walcl = fred_adapter.fetch_series(fred_adapter.WALCL)
    tga = fred_adapter.fetch_series(fred_adapter.TGA_WEDNESDAY)
    rrp = fred_adapter.fetch_series(fred_adapter.RRP)
    statuses = {walcl.status, tga.status, rrp.status}
    adapter_status = "unavailable" if "unavailable" in statuses else ("stale" if "stale" in statuses else "ok")

    w, t, r = _clean(walcl.df), _clean(tga.df), _clean(rrp.df)
    if w.empty or t.empty or r.empty:
        return ComponentSeries(spec, pd.DataFrame(columns=["date", "value", "raw", "contribution"]),
                               "unavailable", "WALCL, WDTGAL or RRPONTSYD unavailable")
    # Wednesday grid = dates where both H.4.1 Wednesday levels exist. RRP is
    # daily; take that Wednesday's value (or the latest within 3 days).
    grid = w.index.intersection(t.index)
    rrp_on_grid = asof_lookup(r, grid, 0, 3)
    level_musd = w.reindex(grid) - t.reindex(grid) - rrp_on_grid * fred_adapter.RRP_BILLIONS_TO_MILLIONS
    level = (level_musd * 1e6).dropna()  # millions -> USD
    points = change_component(spec, level, relative=False)
    status, reason = _status(adapter_status, points)
    return ComponentSeries(spec, points, status, reason)


def _utc_today() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()


def build_stablecoin_supply() -> ComponentSeries:
    spec = SPEC_BY_ID["stablecoin_supply"]
    result = defillama_adapter.fetch_stablecoin_supply()
    level = _clean(result.df)
    # DefiLlama's point for the current UTC day is a live, still-moving
    # total; LiqTide computes on the last complete day (its `stables.as_of`
    # was 2026-09-23 in the 2026-09-24 payload). Using the partial day moved
    # the component from 0.6113 to 0.4346 on that date.
    level = level[level.index < _utc_today()]
    points = change_component(spec, level, relative=True)
    status, reason = _status(result.status, points)
    notes = ["DefiLlama's total runs ~0.5% below LiqTide's own stablecoin total (different coin set); "
             "the 7-day change matched to within 0.002 percentage points on 2026-09-23."]
    return ComponentSeries(spec, points, status, reason, notes)


def build_broad_dollar() -> ComponentSeries:
    spec = SPEC_BY_ID["broad_dollar"]
    result = fred_adapter.fetch_series(fred_adapter.BROAD_DOLLAR)
    points = change_component(spec, _clean(result.df), relative=True)
    status, reason = _status(result.status, points)
    return ComponentSeries(spec, points, status, reason)


def build_rrp_release() -> ComponentSeries:
    spec = SPEC_BY_ID["rrp_release"]
    result = fred_adapter.fetch_series(fred_adapter.RRP)
    level = _clean(result.df) * 1e9  # billions -> USD
    points = change_component(spec, level, relative=False)
    status, reason = _status(result.status, points)
    notes = ["The ON-RRP facility drained to under $1bn during 2025, so this component sits near zero since."]
    return ComponentSeries(spec, points, status, reason, notes)


def _history(key: str, history: pd.DataFrame) -> pd.Series:
    if history is None or history.empty:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    return _clean(history[history["series_key"] == key][["date", "value"]])


def farside_flows(result: etf_flows_adapter.EtfFlowsResult) -> pd.Series:
    """Farside daily totals (US$m) -> USD Series on the component's date index."""
    if result is None or result.df is None or result.df.empty:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    df = result.df.rename(columns={"net_flow_usd_m": "value"})
    return _clean(df) * 1e6


def build_etf_flows(history: pd.DataFrame, farside: etf_flows_adapter.EtfFlowsResult | None = None) -> ComponentSeries:
    """5-day sum of daily net flows. Farside (RFC-003) is the primary daily
    record; the LiqTide archive only fills dates Farside does not have."""
    spec = SPEC_BY_ID["etf_flows"]
    liqtide = _history("etf_flows", history)
    primary = farside_flows(farside)
    flows = pd.concat([primary, liqtide[~liqtide.index.isin(primary.index)]]).sort_index()
    flows = flows[flows.index >= ETF_LAUNCH_DATE]
    points = rolling_sum_component(spec, flows)
    farside_status = farside.status if farside is not None else "unavailable"
    farside_reason = (farside.reason if farside is not None else None) or "Farside adapter not queried"
    if points.empty:
        if flows.empty:
            status, reason = "unavailable", f"no ETF flow history: Farside {farside_status} ({farside_reason})"
        else:
            status, reason = "no_data", "fewer than 5 daily flows so far"
    elif farside_status == "stale" and not primary.empty:
        status, reason = "stale", farside_reason
    else:
        status, reason = "ok", None
    notes = [f"Not applicable before {ETF_LAUNCH_DATE.date()} (US spot-BTC ETFs launched that day)."]
    if primary.empty:
        notes.append(f"Farside {farside_status}: {farside_reason}; LiqTide archive only.")
    else:
        notes.append("Farside data is personal use only (not redistributable).")
    return ComponentSeries(spec, points, status, reason, notes)


def build_btc_dominance(history: pd.DataFrame) -> ComponentSeries:
    spec = SPEC_BY_ID["btc_dominance"]
    level = _history("btc_dom", history)
    points = change_component(spec, level, relative=False)
    status, reason = _status("ok" if not level.empty else "unavailable", points)
    notes = ["No free, keyless deep BTC-dominance history exists; this series starts where LiqTide's "
             "history does (2025-06-10) and grows with the daily archive."]
    if not level.empty:
        notes.append(f"No data before {level.index.min().date()}.")
    return ComponentSeries(spec, points, status, reason, notes)


def status_for_range(component: ComponentSeries, end: pd.Timestamp | None) -> tuple[str, str | None]:
    """Status/reason for a component over a requested range (RFC-004 decision 1).

    One status per component (plan §11). The rule:

    - If the spec has an ``applicable_from`` date and the requested ``end`` is
      before it, the component cannot exist anywhere in the range, so it is
      ``not_applicable`` — whatever the builder reported. Example: spot-BTC
      ETF flows with ``end`` before 2024-01-11.
    - Otherwise the builder's own status stands. In particular, when there is
      no ETF data at all the status stays ``unavailable`` with a reason naming
      the Farside status (RFC-003); the component's notes still say
      pre-launch dates are not applicable.

    Range-dependent, so it lives beside the builders rather than inside them:
    the builders stay range-agnostic.
    """
    start_of_life = component.spec.applicable_from
    if start_of_life is not None and end is not None and end < start_of_life:
        return "not_applicable", (
            f"not applicable before {start_of_life.date()}; the requested range ends before that date")
    return component.status, component.reason


# --------------------------------------------------------------- composite


def build_reproduced(components: list[ComponentSeries]) -> pd.DataFrame:
    """Reproduced tide index on the union of component dates. For each date
    each component contributes its latest value as of that date (within its
    `fresh_days`: FRED's H.10 dollar index and H.4.1 balance sheet are
    published with a lag of about a week, as LiqTide's own `as_of` dates show)."""
    cols = ["date", "value", "coverage", "components_present"]
    dates = sorted({d for c in components for d in c.points["date"]})
    if not dates:
        return pd.DataFrame(columns=cols)
    grid = pd.DatetimeIndex(dates)
    contrib = {}
    for c in components:
        if c.points.empty:
            continue
        series = c.points.set_index("date")["contribution"]
        contrib[c.spec.id] = asof_lookup(series, grid, 0, c.spec.fresh_days)
    frame = pd.DataFrame(contrib, index=grid)
    weights = pd.Series({cid: SPEC_BY_ID[cid].weight for cid in frame.columns})
    present = frame.notna()
    weight_present = present.mul(weights, axis=1).sum(axis=1)
    weighted = frame.fillna(0.0).mul(weights, axis=1).sum(axis=1)  # absent terms excluded via weight_present
    score = weighted / weight_present.replace(0, np.nan)
    out = pd.DataFrame({
        "date": grid,
        "value": 50 + 50 * score,
        "coverage": weight_present,
        "components_present": [",".join(c for c in frame.columns if present.loc[d, c]) for d in grid],
    })
    out = out[out["coverage"] >= AVAILABILITY_WEIGHT_THRESHOLD - 1e-9].dropna(subset=["value"])
    return out.reset_index(drop=True)[cols]


def build_published(history: pd.DataFrame) -> pd.DataFrame:
    """LiqTide's own 0-100 index: weekly `tide_series` history plus one point
    per archived day. The label is shown only where LiqTide published it."""
    cols = ["date", "value", "label"]
    frames = []
    weekly = _history(liqtide_adapter.TIDE_SERIES_KEY, history)
    if not weekly.empty:
        frames.append(pd.DataFrame({"date": weekly.index, "value": weekly.values, "label": None}))
    archive = cache.read_liqtide_history()
    if archive is not None and not archive.empty and "tide_value" in archive.columns:
        a = archive.dropna(subset=["tide_value"])
        if not a.empty:
            frames.append(pd.DataFrame({
                "date": pd.to_datetime(a["date"]).dt.normalize(),
                "value": a["tide_value"].astype(float).values,
                "label": a["tide_label"].values if "tide_label" in a.columns else None,
            }))
    if not frames:
        return pd.DataFrame(columns=cols)
    out = pd.concat(frames, ignore_index=True).sort_values("date")
    return out.drop_duplicates(subset="date", keep="last").reset_index(drop=True)[cols]


def agreement_stats(reproduced: pd.DataFrame, published: pd.DataFrame) -> dict:
    """Numbers only: overlap size, Pearson r, mean absolute difference."""
    empty = {"overlap_days": 0, "pearson_r": None, "mean_abs_diff": None}
    if reproduced.empty or published.empty:
        return empty
    merged = pd.merge(published[["date", "value"]], reproduced[["date", "value", "coverage"]],
                      on="date", suffixes=("_published", "_reproduced"))
    merged = merged.dropna(subset=["value_published", "value_reproduced"])
    if merged.empty:
        return empty
    diff = (merged["value_reproduced"] - merged["value_published"]).abs()
    r = None
    if len(merged) >= 3 and merged["value_published"].std() > 0 and merged["value_reproduced"].std() > 0:
        r = float(np.corrcoef(merged["value_published"], merged["value_reproduced"])[0, 1])
    full = merged[merged["coverage"] >= 0.999]
    return {
        "overlap_days": int(len(merged)),
        "pearson_r": r,
        "mean_abs_diff": float(diff.mean()),
        "full_coverage_days": int(len(full)),
        "full_coverage_mean_abs_diff": float((full["value_reproduced"] - full["value_published"]).abs().mean())
        if not full.empty else None,
    }


def build_regime_components() -> RegimeComponentsResult:
    history = liqtide_adapter.read_history_series()
    components = [
        build_net_liquidity(),
        build_stablecoin_supply(),
        build_broad_dollar(),
        build_rrp_release(),
        build_etf_flows(history, etf_flows_adapter.fetch_btc_spot_flows()),
        build_btc_dominance(history),
    ]
    reproduced = build_reproduced(components)
    published = build_published(history)
    all_dates = set()
    for c in components:
        all_dates.update(c.points["date"])
    all_dates.update(reproduced["date"])
    all_dates.update(published["date"])
    grid = sorted(d.strftime("%Y-%m-%d") for d in all_dates)
    return RegimeComponentsResult(
        components=components,
        reproduced=reproduced,
        published=published,
        agreement=agreement_stats(reproduced, published),
        grid_dates=grid,
    )
