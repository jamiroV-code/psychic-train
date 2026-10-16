"""Attention ratio: mean of the last 7 daily values over the mean of the last 90."""
from __future__ import annotations

from datetime import date

SHORT = 7
LONG = 90


def attention_ratio(points: list[tuple[date, float]]) -> float | None:
    """None when fewer than 90 daily points or a non-positive 90-day mean."""
    vals = [v for _, v in sorted(points, key=lambda p: p[0])]
    if len(vals) < LONG:
        return None
    long_mean = sum(vals[-LONG:]) / LONG
    if long_mean <= 0:
        return None
    return (sum(vals[-SHORT:]) / SHORT) / long_mean
