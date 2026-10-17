"""Freshness rule for the attention-refresh workflow verifier (pure, no I/O).

A source is stale when its latest stored completed UTC day is older than
today minus its allowed lag. A rerun that adds no newer day is not a failure.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import NamedTuple

MAX_LAG_DAYS = {"wikipedia": 3, "coingecko": 2,  # Wikipedia pageviews lag 1-2 days
                "exchange_volume": 2, "hyperliquid_volume": 2, "reddit": 2, "trends": 3}


class Verdict(NamedTuple):
    ok: bool
    threshold: str
    reason: str


def judge(source: str, latest: str | None, today: date) -> Verdict:
    """`latest` is the newest stored completed day (ISO) or None; ok iff latest >= today - lag."""
    threshold = (today - timedelta(days=MAX_LAG_DAYS[source])).isoformat()
    if not latest:
        return Verdict(False, threshold, "no data stored")
    if latest < threshold:
        return Verdict(False, threshold, f"stale: latest day {latest} older than {threshold}")
    return Verdict(True, threshold, "fresh")
