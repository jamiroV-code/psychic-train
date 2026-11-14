"""Symbol suggestions for the add-coin / add-ticker boxes: type part of a symbol or a name, get matching candidates.

Two indexes, both best effort and never raising:

* `coin`: the symbols the screener can actually chart (Hyperliquid markets, then the fallback exchanges Gate.io, MEXC,
  KuCoin plus the pinned LEO and PEARL providers), named from CoinGecko's coin list. Several CoinGecko coins share a
  symbol (SHIB: Shiba Inu, a Binance-Peg copy, a Wormhole copy), so each symbol takes the best candidate: a top-100
  universe coin first, then one that is not a bridged or pegged copy, then the shortest id.
* `ticker`: US stock tickers and company names from the SEC's public `company_tickers.json`; tickers Hyperliquid lists
  as `XYZ-<TICKER>` perps are flagged.

The slow parts (exchange market lists, two public downloads) run once in a background thread and are saved under
`cache/symbols/` as JSON, refreshed after `MAX_AGE_SECONDS`, so a restart serves from disk at once and a request never
waits on the network. Until the first build finishes a request gets what is ready, and `ready` says so.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field

import httpx

from api.data import cache, ccxt_adapter

MAX_AGE_SECONDS = 24 * 3600
COINGECKO_LIST = "https://api.coingecko.com/api/v3/coins/list"
SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
# The SEC rejects (HTTP 403) automated clients whose User-Agent carries no contact address. Set SEC_CONTACT_EMAIL to yours.
USER_AGENT_FMT = "my_site/1.0 personal-use {contact}"
COIN_VENUES = ("gate", "mexc", "kucoin")
# Exchange leveraged tokens (SHIB3L, BTC5S): tradable, but never what someone searching for a coin wants.
_LEVERAGED = re.compile(r"^[A-Z0-9]+\d[LS]$")
_COPY_WORDS = re.compile(r"peg|wormhole|bridged|wrapped|portal|\(.*\)|\bbsc\b|\bpoly\b|\bibc\b", re.IGNORECASE)
LIMIT_MAX = 25


def _dir():
    return cache.CACHE_ROOT / "symbols"


def _read(name: str) -> tuple[dict | None, float]:
    path = _dir() / name
    try:
        return json.loads(path.read_text(encoding="utf-8")), path.stat().st_mtime
    except (OSError, ValueError):
        return None, 0.0


def _write(name: str, payload: dict) -> None:
    _dir().mkdir(parents=True, exist_ok=True)
    cache._atomic_write_json(payload, _dir() / name)


@dataclass
class Index:
    rows: list[dict] = field(default_factory=list)  # {symbol, name, venues, rank}
    ready: bool = False


def _universe_ranks() -> dict[str, int]:
    """CoinGecko id -> market-cap rank in the newest top-100 snapshot."""
    try:
        from api.data.attention import universe_store
        snap = universe_store.read_latest() or {}
        coins = sorted((c for c in snap.get("coins", []) if isinstance(c, dict)), key=lambda c: -(c.get("market_cap") or 0))
        return {str(c.get("id")): i for i, c in enumerate(coins) if c.get("id")}
    except Exception:  # noqa: BLE001 - ranks only break ties
        return {}


def _best_names(listing: list[dict], ranks: dict[str, int]) -> dict[str, tuple[str, int]]:
    """symbol -> (name, universe rank or 10_000) choosing one CoinGecko coin per symbol."""
    best: dict[str, tuple[tuple, str, int]] = {}
    for coin in listing:
        sym, name, cid = str(coin.get("symbol", "")).upper(), str(coin.get("name", "")), str(coin.get("id", ""))
        if not sym or not name:
            continue
        rank = ranks.get(cid, 10_000)
        key = (rank, bool(_COPY_WORDS.search(name)), len(cid))
        if sym not in best or key < best[sym][0]:
            best[sym] = (key, name, rank)
    return {s: (v[1], v[2]) for s, v in best.items()}


def _tradable_coin_venues() -> dict[str, list[str]]:
    """symbol -> venues that can chart it. Loads exchange markets, so only the background builder calls this."""
    venues: dict[str, list[str]] = {}
    hl = ccxt_adapter._exchange()
    if hl is not None:
        for market in (hl.markets or {}).values():
            base = str(market.get("baseName") or market.get("base") or "").upper()
            # HIP-3 stock perps (`XYZ-NVDA`) and other prefixed bases are not screener coins.
            if base.isalnum() and market.get("active") is not False and (market.get("swap") or market.get("spot")):
                venues.setdefault(base, [])
                if "Hyperliquid" not in venues[base]:
                    venues[base].append("Hyperliquid")
    for name in COIN_VENUES:
        ex = ccxt_adapter._fallback_exchange(name)
        if ex is None:
            continue
        for market in (ex.markets or {}).values():
            base = str(market["base"]).upper()
            if market.get("spot") and market.get("quote") == "USDT" and market.get("active") is not False and not _LEVERAGED.match(base):
                venues.setdefault(base, []).append(name)
    for ticker, (provider, _market) in ccxt_adapter.COIN_PROVIDERS.items():
        venues.setdefault(ticker, []).append(provider)
    return venues


def build_coins(client: httpx.Client) -> list[dict]:
    venues = _tradable_coin_venues()
    resp = client.get(COINGECKO_LIST, timeout=30)
    resp.raise_for_status()
    names = _best_names(resp.json(), _universe_ranks())
    rows = []
    for sym, where in venues.items():
        name, rank = names.get(sym, ("", 10_000))
        rows.append({"symbol": sym, "name": name, "venues": where, "rank": rank})
    return rows


# Not in the SEC stock list but wanted on the Equities page. Indices come from Hyperliquid's `XYZ-` perps (SP500,
# XYZ100, JP225, KR200) or are rebuilt (DXY); ETFs are plain LSE tickers (SPY is verified in the LSE study, the rest are
# the usual US index/dollar/gold/bond funds and read as an unknown symbol if LSE lacks them).
CURATED = {
    "SP500": "S&P 500 index (Hyperliquid perp)",
    "SPY": "SPDR S&P 500 ETF Trust",
    "DXY": "US Dollar Index (reconstructed from ECB rates)",
    "XYZ100": "Nasdaq-100 style index (Hyperliquid perp)",
    "QQQ": "Invesco QQQ Trust (Nasdaq-100 ETF)",
    "DIA": "SPDR Dow Jones Industrial Average ETF",
    "IWM": "iShares Russell 2000 ETF",
    "UUP": "Invesco DB US Dollar Index Bullish Fund",
    "GLD": "SPDR Gold Shares",
    "TLT": "iShares 20+ Year Treasury Bond ETF",
    "JP225": "Nikkei 225 index (Hyperliquid perp)",
    "KR200": "KOSPI 200 index (Hyperliquid perp)",
    "GOLD": "Gold (Hyperliquid perp)",
    "BRENTOIL": "Brent crude oil (Hyperliquid perp)",
    "COPPER": "Copper (Hyperliquid perp)",
    "EUR": "Euro vs US dollar (Hyperliquid perp)",
    "GBP": "British pound vs US dollar (Hyperliquid perp)",
    "JPY": "Japanese yen vs US dollar (Hyperliquid perp)",
}


def build_tickers(client: httpx.Client) -> list[dict]:
    resp = client.get(SEC_TICKERS, timeout=30, headers={"User-Agent": USER_AGENT_FMT.format(contact=os.environ.get("SEC_CONTACT_EMAIL", "owner@example.com"))})
    resp.raise_for_status()
    hl = ccxt_adapter._exchange()
    on_hl = {m.split("/")[0][4:] for m in (hl.markets if hl is not None else {}) if m.startswith("XYZ-")}
    seen: set[str] = set()
    rows = []
    for sym, name in CURATED.items():
        seen.add(sym)
        rows.append({"symbol": sym, "name": name, "venues": ["Hyperliquid"] if sym in on_hl else [], "rank": -1})
    for sym in sorted(on_hl - seen):  # every other active XYZ market has no SEC name; list it so it can be found
        seen.add(sym)
        rows.append({"symbol": sym, "name": "Hyperliquid perp", "venues": ["Hyperliquid"], "rank": 20_000})
    for i, item in enumerate(resp.json().values()):  # the SEC file is ordered by market cap
        sym = str(item.get("ticker", "")).upper()
        if sym and sym not in seen:
            seen.add(sym)
            rows.append({"symbol": sym, "name": str(item.get("title", "")).title(), "venues": ["Hyperliquid"] if sym in on_hl else [], "rank": i})
    return rows


_lock = threading.Lock()
_indexes: dict[str, Index] = {"coin": Index(), "ticker": Index()}
_building = False
_BUILDERS = {"coin": ("coins.json", build_coins), "ticker": ("tickers.json", build_tickers)}


def _load_from_disk() -> dict[str, float]:
    ages = {}
    for kind, (file, _build) in _BUILDERS.items():
        payload, mtime = _read(file)
        if payload and isinstance(payload.get("rows"), list) and payload["rows"]:
            _indexes[kind] = Index(rows=payload["rows"], ready=True)
            ages[kind] = mtime
    return ages


def _build_all() -> None:
    global _building
    try:
        with httpx.Client(follow_redirects=True) as client:
            for kind, (file, build) in _BUILDERS.items():
                try:
                    rows = build(client)
                except Exception:  # noqa: BLE001 - keep serving the old index
                    continue
                if rows:
                    _write(file, {"built_at": time.time(), "rows": rows})
                    with _lock:
                        _indexes[kind] = Index(rows=rows, ready=True)
    finally:
        with _lock:
            _building = False


def ensure_built() -> None:
    """Load the saved indexes, and start the one background refresh when any is missing or older than a day."""
    global _building
    with _lock:
        if _building:
            return
        ages = _load_from_disk()
        now = time.time()
        if all(now - ages.get(kind, 0.0) < MAX_AGE_SECONDS for kind in _BUILDERS):
            return
        _building = True
    threading.Thread(target=_build_all, name="symbol-index", daemon=True).start()


def _score(row: dict, q: str) -> int | None:
    sym, name = row["symbol"].lower(), row["name"].lower()
    if sym == q:
        return 0
    if sym.startswith(q):
        return 1
    if any(w.startswith(q) for w in re.split(r"[\s\-_.()/&,]+", name) if w):
        return 2
    if q in name:
        return 3
    if q in sym:
        return 4
    return None


def suggest(kind: str, query: str, limit: int = 8) -> dict:
    """`{ready, suggestions: [{symbol, name, venues}]}` best matches first; never raises."""
    ensure_built()
    q = query.strip().lower()
    index = _indexes.get(kind, Index())
    if not q:
        return {"ready": index.ready, "suggestions": []}
    scored = [(s, r["rank"], r["symbol"], r) for r in index.rows if (s := _score(r, q)) is not None]
    scored.sort(key=lambda t: t[:3])
    top = [{"symbol": r["symbol"], "name": r["name"], "venues": r["venues"]} for *_k, r in scored[: max(1, min(limit, LIMIT_MAX))]]
    return {"ready": index.ready, "suggestions": top}
