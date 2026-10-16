"""Per-day coin scores from the stored series (data up to that day only)."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from api.analytics.attention.rank import percentile
from api.analytics.attention.ratio import attention_ratio
from api.analytics.attention.score import coin_score
from api.data.attention import registry
from api.data.attention.types import SourceSeries


def read_all(sources: list[str], symbols: list[str], today: date,
             probe_path: Path | None) -> dict[tuple[str, str], SourceSeries]:
    return {(s, sym): registry.read_series(s, sym, today, probe_path) for s in sources for sym in symbols}


def ratio_at(series: SourceSeries, day: date) -> float | None:
    """Ratio from data up to `day`; only an `ok` series feeds a ratio."""
    if series.state != "ok":
        return None
    return attention_ratio([p for p in series.points if p[0] <= day])


def reference_ratios(source: str, reference: list[str],
                     data: dict[tuple[str, str], SourceSeries], day: date) -> list[float]:
    out = [ratio_at(data[(source, sym)], day) for sym in reference]
    return [r for r in out if r is not None]


def coin_ranks(symbol: str, sources: list[str], data: dict[tuple[str, str], SourceSeries],
               reference: list[str], day: date) -> dict[str, float | None]:
    ranks: dict[str, float | None] = {}
    for s in sources:
        ratio = ratio_at(data[(s, symbol)], day)
        ranks[s] = None if ratio is None else percentile(ratio, reference_ratios(s, reference, data, day))
    return ranks


def coin_score_at(symbol: str, sources: list[str], weights: dict[str, float],
                  data: dict[tuple[str, str], SourceSeries], reference: list[str], day: date) -> float | None:
    return coin_score(coin_ranks(symbol, sources, data, reference, day), weights)[0]


def days_back(end: date, window: int) -> list[date]:
    return [end - timedelta(days=window - i) for i in range(window + 1)]
