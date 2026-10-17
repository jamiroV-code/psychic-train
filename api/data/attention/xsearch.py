"""X (Twitter) recent-search counts source, budgeted and dry-run by default.

The bearer token is read from the environment at call time and used only in
the Authorization header: it is never kept in a module attribute, dataclass,
cache file, log line, exception text or repr. Failures log the exception type
name only. Safe defaults: `X_LIVE` off (dry run); caps via X_MAX_READS_PER_RUN,
X_MAX_READS_PER_DAY, X_MAX_USD_PER_DAY, X_USD_PER_READ. A read is one request,
counted before it is sent. Only the last completed day is returned per run, so
the store holds X's own daily rows (insufficient-history until 90).
"""
from __future__ import annotations

import json
import logging
import os
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

from api.data import cache
from api.data.attention.types import SourceSeries

SOURCE = "xsearch"
WEIGHT = 0.25  # below the other sources
COUNTS_URL = "https://api.x.com/2/tweets/counts/recent"
TIMEOUT_SECONDS = 10.0
SPAM_SPIKE_RATIO = 10.0

log = logging.getLogger(__name__)


def _num(name: str, default: float) -> float:
    try:
        v = float(os.environ.get(name, ""))
        return v if v >= 0 else default
    except ValueError:
        return default


@dataclass
class Limits:
    live: bool
    max_run: int
    max_day: int
    max_usd_day: float
    usd_per_read: float


def limits() -> Limits:
    return Limits(
        live=os.environ.get("X_LIVE") == "1",
        max_run=int(_num("X_MAX_READS_PER_RUN", 10)),
        max_day=int(_num("X_MAX_READS_PER_DAY", 50)),
        max_usd_day=_num("X_MAX_USD_PER_DAY", 1.0),
        usd_per_read=_num("X_USD_PER_READ", 0.01),
    )


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def usage_path(today: date) -> Path:
    return cache.CACHE_ROOT / "xsearch_usage" / f"{today.isoformat()}.json"


def reads_today(today: date) -> int:
    try:
        return int(json.loads(usage_path(today).read_text()).get("reads", 0))
    except (OSError, ValueError, AttributeError):
        return 0


def _bump(today: date) -> None:
    p = usage_path(today)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"reads": reads_today(today) + 1}))


@dataclass
class RunBudget:
    reads: int = 0


@dataclass
class Estimate:
    planned_reads: int
    usd: float
    live: bool
    capped: bool


def _allowed_reads(lim: Limits, used_day: int, used_run: int) -> int:
    by_usd = int((lim.max_usd_day + 1e-9) // lim.usd_per_read) - used_day if lim.usd_per_read > 0 else 10**9
    return max(0, min(lim.max_run - used_run, lim.max_day - used_day, by_usd))


def estimate(symbols, today: date | None = None) -> Estimate:
    """Planned reads and USD; no network, no writes."""
    lim, today = limits(), today or _utc_today()
    n = min(len(list(symbols)), _allowed_reads(lim, reads_today(today), 0))
    return Estimate(n, n * lim.usd_per_read, lim.live, n < len(list(symbols)))


def _flag_spam(counts: list[float]) -> str:
    med = statistics.median(counts) if counts else 0
    if med > 0 and max(counts) > SPAM_SPIKE_RATIO * med:
        return "spam-flag: spike over 10x median"
    return ""


def fetch_series(symbol: str, *, client: httpx.Client | None = None, today: date | None = None,
                 run: RunBudget | None = None) -> SourceSeries:
    today, run = today or _utc_today(), run if run is not None else RunBudget()
    lim = limits()
    if not lim.live:
        return SourceSeries(SOURCE, symbol, [], "unavailable", "dry-run (X_LIVE off)")
    token = os.environ.get("X_BEARER_TOKEN")
    if not token:
        return SourceSeries(SOURCE, symbol, [], "unavailable", "no bearer token")
    if _allowed_reads(lim, reads_today(today), run.reads) < 1:
        return SourceSeries(SOURCE, symbol, [], "capped", "read or spend cap reached")
    run.reads += 1
    _bump(today)
    own = client is None
    client = client or httpx.Client()
    try:
        resp = client.get(
            COUNTS_URL,
            params={"query": f"${symbol} -is:retweet -is:reply", "granularity": "day"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        rows = [(r["start"][:10], float(r["tweet_count"])) for r in resp.json()["data"]]
    except Exception as exc:
        log.warning("xsearch read failed: %s", type(exc).__name__)
        return SourceSeries(SOURCE, symbol, [], "unavailable", "read failed")
    finally:
        if own:
            client.close()
    done = [(d, v) for d, v in rows if d < today.isoformat()]
    if not done:
        return SourceSeries(SOURCE, symbol, [], "unavailable", "no completed day")
    last_day = date.fromisoformat(done[-1][0])
    return SourceSeries(SOURCE, symbol, [(last_day, done[-1][1])], "ok",
                        _flag_spam([v for _, v in done]))
