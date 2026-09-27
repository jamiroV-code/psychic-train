"""Build the GET /api/onchain/growth and /chains responses (chain-growth RFC-4).

Read-only: reads the archived series via `cache.read_onchain_series` and the
chain list via `load_chains`. Never calls an adapter, never writes.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pandas as pd

from api.analytics.onchain import growth
from api.analytics.onchain.comparison import (
    ALTERNATIVE_METHOD,
    DEFAULT_RANGE_DAYS,
    LOG_SCALE_DEFAULT,
    NORMALIZATION_METHOD,
    build_comparison_series,
)
from api.data import cache, growthepie_adapter, l2beat_adapter
from api.data.chain_growth_config import ChainConfig, load_chains
from api.models.onchain_activity import (
    ChainGrowth,
    ChainInfo,
    ChainMetricInfo,
    Comparison,
    ComparisonSeriesModel,
    CrossCheck,
    FloorRamp,
    FloorRampEventModel,
    GrowthParams,
    GrowthPoint,
    GrowthSeries,
    OnchainChainsResponse,
    OnchainGrowthResponse,
)

METRICS = ("active_addresses", "transactions")
STALE_AFTER_DAYS = 3  # a series whose last fetch is older than this is `stale`
MAX_GAP_DAYS = 1  # daily series: any missing day breaks the line
CROSS_CHECK_WINDOW_DAYS = 90
NO_ARCHIVE_REASON = "no-archived-data"

METHODS = {
    "active_addresses": "unique addresses active per UTC day (growthepie daa)",
    "transactions": "transactions per UTC day (growthepie txcount)",
}
# L2BEAT only publishes transaction counts.
CROSS_CHECK_METRICS = frozenset({"transactions"})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _series(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=float)
    return pd.Series(df["value"].to_numpy(float), index=pd.to_datetime(df["date"]))


def _last_as_of(df: pd.DataFrame) -> str | None:
    vals = df["as_of_utc"].dropna() if not df.empty else []
    return max(vals) if len(vals) else None


def is_stale(last_as_of_utc: str | None, now: datetime) -> bool:
    """Stale when the most recent fetch is more than STALE_AFTER_DAYS old."""
    if last_as_of_utc is None:
        return True
    ts = pd.Timestamp(last_as_of_utc)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return (now - ts.to_pydatetime()) > timedelta(days=STALE_AFTER_DAYS)


def _round(v: float) -> float | None:
    return None if pd.isna(v) else round(float(v), 4)


def _points(raw: pd.Series, launch_date: str | None) -> list[GrowthPoint]:
    daily = growth.to_daily(raw)
    post = growth.post_launch(daily, launch_date)
    e7 = growth.ema(post, growth.EMA_FAST_SPAN)
    e28 = growth.ema(post, growth.EMA_SPAN)
    launch = pd.Timestamp(launch_date) if launch_date else None
    out: list[GrowthPoint] = []
    prev = None
    for d, v in raw.sort_index().items():
        pre = launch is not None and d < launch
        out.append(GrowthPoint(
            date=d.date().isoformat(),
            value=float(v),
            ema7=None if pre else _round(e7.get(d, float("nan"))),
            ema28=None if pre else _round(e28.get(d, float("nan"))),
            gap_before=prev is not None and (d - prev).days > MAX_GAP_DAYS,
            pre_launch=pre,
        ))
        prev = d
    return out


def cross_check_summary(primary: pd.Series, check: pd.Series) -> CrossCheck:
    """(primary - check) / check, in %. Display-only."""
    base = CrossCheck(source="l2beat", redistributable=l2beat_adapter.REDISTRIBUTABLE)
    j = pd.concat([primary, check], axis=1, join="inner").dropna()
    j = j[j.iloc[:, 1] > 0]
    if j.empty:
        return base
    j = j[j.index >= j.index.max() - pd.Timedelta(days=CROSS_CHECK_WINDOW_DAYS - 1)]
    div = (j.iloc[:, 0] - j.iloc[:, 1]) / j.iloc[:, 1] * 100.0
    return base.model_copy(update={
        "latest_common_date": j.index.max().date().isoformat(),
        "latest_divergence_pct": round(float(div.iloc[-1]), 4),
        "median_abs_divergence_pct_90d": round(float(div.abs().median()), 4),
    })


def _unavailable(chain: ChainConfig, reason: str) -> ChainGrowth:
    return ChainGrowth(
        id=chain.id, label=chain.label, launch_date=chain.launch_date,
        limited_history=chain.limited_history, status="unavailable", unavailable_reason=reason,
    )


def build_growth_response(
    metric: str,
    start: date | None = None,
    now: datetime | None = None,
    chains: list[ChainConfig] | None = None,
) -> OnchainGrowthResponse:
    now = now or _utcnow()
    chains = [c for c in (load_chains() if chains is None else chains) if c.enabled]

    entries: list[tuple[ChainConfig, pd.Series | None, ChainGrowth]] = []
    grid: set[str] = set()
    for chain in chains:
        src = chain.metric(metric)
        if src is None or src.source != "growthepie":
            reason = (src.unavailable_reason if src else None) or "source-unavailable"
            entries.append((chain, None, _unavailable(chain, reason)))
            continue
        df = cache.read_onchain_series("growthepie", chain.id, metric)
        raw = _series(df).dropna()
        if raw.empty:
            entries.append((chain, None, _unavailable(chain, NO_ARCHIVE_REASON)))
            continue
        grid.update(d.date().isoformat() for d in raw.index)
        post = growth.post_launch(growth.to_daily(raw), chain.launch_date)
        fr = growth.detect_floor_ramp(post)
        last_as_of = _last_as_of(df)
        cc = None
        if chain.cross_check is not None and metric in CROSS_CHECK_METRICS:
            cdf = cache.read_onchain_series(chain.cross_check.source, chain.id, metric)
            cc = cross_check_summary(raw, _series(cdf).dropna())
        obs_post = post.dropna()
        item = ChainGrowth(
            id=chain.id, label=chain.label, launch_date=chain.launch_date,
            limited_history=chain.limited_history,
            status="stale" if is_stale(last_as_of, now) else "ok",
            history_start_date=obs_post.index[0].date().isoformat() if not obs_post.empty else None,
            series=GrowthSeries(
                source="growthepie", method=METHODS[metric],
                attribution=growthepie_adapter.ATTRIBUTION,
                redistributable=growthepie_adapter.REDISTRIBUTABLE,
                max_gap_days=MAX_GAP_DAYS, last_as_of_utc=last_as_of,
                points=_points(raw, chain.launch_date),
            ),
            floor_ramp=FloorRamp(
                state=fr.state,
                events=[FloorRampEventModel(floor_date=e.floor_date.isoformat(), ramp_date=e.ramp_date.isoformat()) for e in fr.events],
                min_history_days=growth.MIN_HISTORY_DAYS,
                history_days=fr.history_days,
                gate_met_on=fr.gate_met_on.isoformat() if fr.gate_met_on else None,
            ),
            cross_check=cc,
        )
        entries.append((chain, post, item))

    grid_dates = sorted(grid)
    if start is None:
        start = (date.fromisoformat(grid_dates[-1]) if grid_dates else now.date()) - timedelta(days=DEFAULT_RANGE_DAYS)
    comp = []
    for chain, post, _ in entries:
        if post is None:
            continue
        cs = build_comparison_series(chain.id, post, start, grid_dates)
        comp.append(ComparisonSeriesModel(
            chain_id=cs.chain_id,
            rebase_date=cs.rebase_date.isoformat() if cs.rebase_date else None,
            rebased_late=cs.rebased_late,
            index_values=[None if v is None else round(v, 4) for v in cs.index_values],
            pct_above_low_values=[None if v is None else round(v, 4) for v in cs.pct_above_low_values],
        ))

    return OnchainGrowthResponse(
        generated_utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        metric=metric,
        grid_dates=grid_dates,
        attribution=growthepie_adapter.ATTRIBUTION,
        params=GrowthParams(
            ema_span=growth.EMA_SPAN, ema_fast_span=growth.EMA_FAST_SPAN,
            window_days=growth.WINDOW_DAYS, recovery_pct=growth.RECOVERY_PCT,
            sustain_days=growth.SUSTAIN_DAYS, spacing_days=growth.SPACING_DAYS,
            floor_state_pct=growth.FLOOR_STATE_PCT, min_history_days=growth.MIN_HISTORY_DAYS,
            stale_after_days=STALE_AFTER_DAYS,
        ),
        chains=[item for _, _, item in entries],
        comparison=Comparison(
            normalization_method=NORMALIZATION_METHOD, alternative_method=ALTERNATIVE_METHOD,
            start_date=start.isoformat(), log_scale_default=LOG_SCALE_DEFAULT, series=comp,
        ),
    )


def build_chains_response(chains: list[ChainConfig] | None = None) -> OnchainChainsResponse:
    chains = load_chains() if chains is None else chains
    return OnchainChainsResponse(chains=[
        ChainInfo(
            id=c.id, label=c.label, enabled=c.enabled, launch_date=c.launch_date,
            limited_history=c.limited_history,
            metrics=[ChainMetricInfo(metric=name, source=m.source, unavailable_reason=m.unavailable_reason) for name, m in c.metrics],
            cross_check_source=c.cross_check.source if c.cross_check else None,
        )
        for c in chains
    ])
