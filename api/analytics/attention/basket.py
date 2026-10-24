"""Basket scoring: equal mean of member coin scores, breadth, coverage, rebased series."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from api.analytics.attention import series as ser
from api.analytics.attention.score import coin_score, load_weights
from api.analytics.attention.universe import load_reference
from api.data import baskets_view
from api.models.attention import (
    AttentionResponse, BasketAttention, CoinAttention, SeriesPoint, SourceDetail,
)
from api.models.layout import Layout


def _mean(vals: list[float | None]) -> float | None:
    got = [v for v in vals if v is not None]
    return sum(got) / len(got) if got else None


def _coin(symbol, sources, weights, data, reference, day) -> CoinAttention:
    ranks = ser.coin_ranks(symbol, sources, data, reference, day)
    score, used, total = coin_score(ranks, weights)
    details = []
    for s in sources:
        sr = data[(s, symbol)]
        ok = sr.state == "ok"
        details.append(SourceDetail(
            source=s, raw=sr.points[-1][1] if ok and sr.points else None,
            ratio=ser.ratio_at(sr, day), rank=ranks[s], state=sr.state))
    return CoinAttention(symbol=symbol, score=score, sources_used=used, sources_total=total, sources=details)


def _basket(group, window, sources, weights, data, reference, universe_size, end) -> BasketAttention:
    coins = [_coin(c, sources, weights, data, reference, end) for c in group.coins]
    days = ser.days_back(end, window)
    per_day = {d: _mean([ser.coin_score_at(c, sources, weights, data, reference, d) for c in group.coins])
               for d in days}
    score = per_day[end]
    scored = sum(1 for c in coins if c.score is not None)
    coverage = f"covers {scored} of {len(coins)}"
    base = per_day[days[0]]
    if base is None:
        base = next((v for v in per_day.values() if v is not None), None)
    rebased = [SeriesPoint(date=d.isoformat(),
                           value=None if per_day[d] is None or not base else per_day[d] / base * 100.0)
               for d in days]
    change = None if score is None or base is None else score - base
    lag = end - timedelta(days=window)
    pairs = []
    for c in group.coins:
        now = ser.coin_score_at(c, sources, weights, data, reference, end)
        before = ser.coin_score_at(c, sources, weights, data, reference, lag)
        if now is not None and before is not None:
            pairs.append(now > before)
    breadth = sum(pairs) / len(pairs) if pairs else None
    if not coins:
        status, reason = "empty", "basket has no coins"
    elif score is None:
        status = "no-data"
        reason = "no usable source data for any coin" if reference else "reference-missing"
    else:
        status, reason = "ok", ""
    return BasketAttention(id=group.id, name=group.name, score=score, change=change, breadth=breadth,
                           coverage=coverage, series=rebased, coins=coins, status=status, reason=reason,
                           universe_size=universe_size)


def build_attention(window: int, *, layout: Layout, today: date, probe_path: Path | None = None,
                    weights_path: Path | None = None, universe_path: Path | None = None) -> AttentionResponse:
    """Store-only: reads parquet and config, never a provider. Scores today's membership."""
    weights = load_weights(weights_path)
    sources = list(weights)
    reference = load_reference(universe_path)
    members = baskets_view.baskets(layout)
    symbols = sorted({c for g in members for c in g.coins} | set(reference))
    data = ser.read_all(sources, symbols, today, probe_path)
    end = today - timedelta(days=1)
    universe_size = max((len(ser.reference_ratios(s, reference, data, end)) for s in sources), default=0)
    baskets = [_basket(g, window, sources, weights, data, reference, universe_size, end) for g in members]
    return AttentionResponse(window=window, as_of=end.isoformat(),
                             membership_as_of=layout.saved_at or today.isoformat(), baskets=baskets)
