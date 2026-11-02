"""CoinGecko attention source: top-100 reference list and daily volume series.

Thin fetchers kept here; `coingecko_adapter` is wrapped (trending), never edited.
Daily 24h-volume from `market_chart` is the stored attention proxy (completed
UTC days only; the store drops today).
"""
from __future__ import annotations

import re
import time
from datetime import date, datetime, timezone
from urllib.parse import quote

import httpx

from api.data import coingecko_adapter
from api.data.attention.http_retry import Pacer, describe_exc, get_with_retry
from api.data.attention.types import MIN_HISTORY_DAYS, SourceSeries

MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
CHART_URL = "https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
DETAIL_URL = "https://api.coingecko.com/api/v3/coins/{coin_id}"
PRICE_DAYS = 30
MAX_RETRIES = 3  # retries after the first attempt, on HTTP 429 only
BACKOFF_BASE_SECONDS = 5.0  # 5, 10, 20 s (+ jitter) when no Retry-After is sent
TIMEOUT_SECONDS = 10.0
MIN_INTERVAL_SECONDS = 6.0  # public tier allows about 5-15 calls/min
RETRY_AFTER_CAP_SECONDS = 90.0
USER_AGENT = ("psychic-train-attention/1.0 (https://github.com/jamirov-code/psychic-train; "
              "research dashboard) python-httpx")
PACER = Pacer(MIN_INTERVAL_SECONDS)
# Why the last fetch_* call returned None (redacted, short); read by the refresh script.
LAST_FAILURE = ""
CATEGORY_PAUSE_SECONDS = 2.0
# T223: the markets snapshot holds the exit band too (rank 101-120); scoring still takes the first 100.
MARKETS_ROWS = 120
# Snapshot identities use the same symbol alphabet as the owner files.
SNAPSHOT_SYMBOL_RE = re.compile(r"[A-Z0-9_]{1,24}")
SNAPSHOT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,99}$")
_NAME_UNSAFE = re.compile("[\x00-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")
NAME_MAX = 100

# Excluded from the D-3 reference universe (stablecoins, wrapped/staked wrappers).
STABLECOIN_SYMBOLS = frozenset({"USDT", "USDC", "DAI", "USDE", "FDUSD", "TUSD", "USDD", "PYUSD", "USDS", "USD1"})
WRAPPED_SYMBOLS = frozenset({"WBTC", "WETH", "STETH", "WSTETH", "WEETH", "CBBTC", "WBETH", "BSC-USD", "WBNB"})


def _get(client: httpx.Client, url: str, params: dict, sleep) -> httpx.Response:
    return get_with_retry(client, url, sleep=sleep, retries=MAX_RETRIES, base=BACKOFF_BASE_SECONDS,
                          timeout=TIMEOUT_SECONDS, pacer=PACER, params=params,
                          headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                          retry_after_cap=RETRY_AFTER_CAP_SECONDS)


def _fail(reason: str) -> None:
    global LAST_FAILURE
    LAST_FAILURE = reason
    return None


def _status_failure(resp: httpx.Response) -> None:
    return _fail(f"HTTP {resp.status_code}")


def fetch_top100(*, client: httpx.Client, sleep=time.sleep) -> list[dict] | None:
    """Top-100 by market cap, minus stablecoins and wrapped coins. None on failure."""
    _fail("")
    try:
        resp = _get(client, MARKETS_URL, {"vs_currency": "usd", "order": "market_cap_desc",
                                          "per_page": 100, "page": 1}, sleep)
        if resp.status_code >= 400:
            return _status_failure(resp)
        rows = []
        for r in resp.json():
            sym = str(r["symbol"]).upper()
            if sym in STABLECOIN_SYMBOLS or sym in WRAPPED_SYMBOLS:
                continue
            rows.append({"id": r["id"], "symbol": sym, "market_cap": r.get("market_cap")})
        return rows
    except Exception as exc:
        return _fail(describe_exc(exc))


def fetch_top100_markets(*, client: httpx.Client, sleep=time.sleep) -> list[dict] | None:
    """Top MARKETS_ROWS by market cap, unfiltered: {id, symbol, name, rank, market_cap, volume_24h}. None on failure.

    `rank` is the position in the cap-ordered answer (1-based). A row whose symbol or id fails the snapshot
    patterns is dropped (its rank stays unused, so the ledger sees the gap and fails closed). The markets
    endpoint carries no category tags, so none are kept.
    """
    _fail("")
    try:
        resp = _get(client, MARKETS_URL, {"vs_currency": "usd", "order": "market_cap_desc",
                                          "per_page": MARKETS_ROWS, "page": 1}, sleep)
        if resp.status_code >= 400:
            return _status_failure(resp)
        out = []
        for i, r in enumerate(resp.json()):
            sym, cid = str(r["symbol"]).upper(), r["id"]
            if not (isinstance(cid, str) and SNAPSHOT_ID_RE.fullmatch(cid) and SNAPSHOT_SYMBOL_RE.fullmatch(sym)):
                continue
            name = _NAME_UNSAFE.sub("", str(r.get("name") or ""))[:NAME_MAX] or None
            out.append({"id": cid, "symbol": sym, "name": name, "rank": i + 1, "market_cap": r.get("market_cap"),
                        "volume_24h": r.get("total_volume")})
        return out
    except Exception as exc:
        return _fail(describe_exc(exc))


def fetch_categories(category_ids: list[str], *, client: httpx.Client,
                     sleep=time.sleep) -> dict[str, list[str]] | None:
    """{category id: [SYMBOL]} from the markets endpoint's `category` filter (no key).

    The markets snapshot carries no tags, so membership is fetched per public category.
    All or nothing: one failed category returns None so the caller keeps its old file.
    """
    out: dict[str, list[str]] = {}
    _fail("")
    try:
        for i, cid in enumerate(category_ids):
            if i:
                sleep(CATEGORY_PAUSE_SECONDS)
            resp = _get(client, MARKETS_URL, {"vs_currency": "usd", "category": cid, "order": "market_cap_desc",
                                              "per_page": 100, "page": 1}, sleep)
            if resp.status_code >= 400:
                return _status_failure(resp)
            out[cid] = [str(r["symbol"]).upper() for r in resp.json()]
        return out
    except Exception as exc:
        return _fail(describe_exc(exc))


def fetch_series(symbol: str, coin_id: str, *, client: httpx.Client,
                 today: date | None = None, sleep=time.sleep) -> SourceSeries:
    sym = symbol.upper()
    today = today or datetime.now(timezone.utc).date()
    try:
        resp = _get(client, CHART_URL.format(coin_id=quote(str(coin_id), safe="")),
                    {"vs_currency": "usd", "days": 100, "interval": "daily"}, sleep)
        if resp.status_code == 429:
            return SourceSeries("coingecko", sym, [], "capped", "HTTP 429")
        if resp.status_code >= 400:
            return SourceSeries("coingecko", sym, [], "unavailable", f"HTTP {resp.status_code}")
        raw = resp.json().get("total_volumes") or []
        pts = sorted(
            (datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date(), float(v)) for ms, v in raw
        )
    except Exception as exc:
        return SourceSeries("coingecko", sym, [], "unavailable", type(exc).__name__)
    pts = [p for p in pts if p[0] < today]
    if not pts:
        return SourceSeries("coingecko", sym, [], "unavailable", "empty response")
    if len(pts) < MIN_HISTORY_DAYS:
        return SourceSeries("coingecko", sym, pts, "insufficient-history", f"{len(pts)} days")
    return SourceSeries("coingecko", sym, pts, "ok", "")


def fetch_trending_symbols() -> list[str]:
    """Wrap the existing adapter (snapshot, not stored as a daily series)."""
    return coingecko_adapter.fetch_trending().symbols


def _coin_url(template: str, coin_id: str) -> str:
    return template.format(coin_id=quote(str(coin_id), safe=""))


def _onboarding_get(client, url, params, sleep):
    """One paced request: a refusal stops onboarding until the next scheduled run."""
    return get_with_retry(client, url, sleep=sleep, retries=0, base=BACKOFF_BASE_SECONDS,
                          timeout=TIMEOUT_SECONDS, pacer=PACER, params=params,
                          headers={"User-Agent": USER_AGENT, "Accept": "application/json"})


def fetch_coin_detail(coin_id: str, *, client: httpx.Client, sleep=time.sleep) -> tuple[dict | None, str]:
    """T223 classifier evidence: ({categories, name, asset_platform_id}, "ok"), or (None, "capped" | "unavailable").
    Never raises; nothing else of the answer is kept. The live shape is UNVERIFIED until probe P-O0."""
    try:
        resp = _onboarding_get(client, _coin_url(DETAIL_URL, coin_id),
                    {"localization": "false", "tickers": "false", "market_data": "false", "community_data": "false",
                     "developer_data": "false", "sparkline": "false"}, sleep)
        if resp.status_code == 429:
            return None, "capped"
        if resp.status_code >= 400:
            return None, "unavailable"
        body = resp.json()
        if not isinstance(body, dict) or not isinstance(body.get("categories"), list):
            return None, "unavailable"
        platform = body.get("asset_platform_id")
        return {"categories": [c for c in body["categories"] if isinstance(c, str)],
                "name": str(body.get("name") or ""), "asset_platform_id": platform if isinstance(platform, str)
                else None}, "ok"
    except Exception:  # noqa: BLE001 - fail closed; the caller records `unknown`
        return None, "unavailable"


def fetch_price_stats(coin_id: str, *, client: httpx.Client, sleep=time.sleep) -> tuple[dict | None, str]:
    """T223: derived daily price numbers over PRICE_DAYS days ({price_min, price_max, n_days, last_price}, "ok");
    the series itself is never returned. (None, "capped" | "unavailable") otherwise; never raises."""
    from api.data.attention.coin_class import price_stats
    try:
        resp = _onboarding_get(client, _coin_url(CHART_URL, coin_id),
                    {"vs_currency": "usd", "days": PRICE_DAYS, "interval": "daily"}, sleep)
        if resp.status_code == 429:
            return None, "capped"
        if resp.status_code >= 400:
            return None, "unavailable"
        body = resp.json()
        stats = price_stats(body.get("prices") if isinstance(body, dict) else None)
        return (stats, "ok") if stats else (None, "unavailable")
    except Exception:  # noqa: BLE001 - fail closed
        return None, "unavailable"
