"""DefiLlama daily fees per coin, for the Discovery `defillama` source (DeFi, L1 and L2 coins only).

The series is the daily fees (USD) users paid to the coin's protocol or chain: a deliberate on-chain act, so a rising
line reads as rising use. Fees, not TVL, because TVL moves with the coin's own price. Keyless public API
(`api.llama.fi`).

A coin is matched on its CoinGecko id, which the Discovery universe rows carry and DefiLlama lists as `gecko_id` on
both protocols (`/protocols`) and chains (`/v2/chains`). A coin can match several (Aave has v2, v3 and a parent), so
the candidate with the most fees over its last 30 completed days wins, and that choice is saved in
`attention/defillama_map.json` so a coin never switches series (and scales) halfway through its history. Delete the
file to resolve again. A coin with no match, or whose matches paid no fees in 30 days, is `no protocol`: a fact about
the coin, not an outage. Fetchers never raise.
"""
from __future__ import annotations

import json
import re
import threading
import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

import httpx

from api.data import cache
from api.data.attention.types import MIN_HISTORY_DAYS, SourceSeries

SOURCE = "defillama"
BASE = "https://api.llama.fi"
TIMEOUT = 30.0
DIRECTORY_TTL_SECONDS = 6 * 3600
MAX_CANDIDATES = 4
RECENT_DAYS = 30

_lock = threading.Lock()
_directory_cache: tuple[float, dict, dict] | None = None
_ids_cache: dict[str, str] | None = None


def map_path():
    return cache.CACHE_ROOT / "attention" / "defillama_map.json"


def _failure_reason(exc: Exception) -> str:
    m = re.search(r"\b([45]\d\d)\b", str(exc))
    return f"fetch-failed: {type(exc).__name__}" + (f" HTTP {m.group(1)}" if m else "")


def _day(ts: float) -> date:
    return datetime.fromtimestamp(ts, tz=timezone.utc).date()


def _directory(client: httpx.Client) -> tuple[dict, dict]:
    """(protocols by gecko_id, chains by gecko_id), cached for `DIRECTORY_TTL_SECONDS`."""
    global _directory_cache
    with _lock:
        if _directory_cache and time.monotonic() - _directory_cache[0] < DIRECTORY_TTL_SECONDS:
            return _directory_cache[1], _directory_cache[2]
    protocols: dict[str, list[str]] = {}
    for p in sorted(_get_json(client, "/protocols"), key=lambda p: -(p.get("tvl") or 0)):
        if p.get("gecko_id") and p.get("slug"):
            protocols.setdefault(p["gecko_id"], []).append(p["slug"])
    chains: dict[str, str] = {}
    for c in _get_json(client, "/v2/chains"):
        if c.get("gecko_id") and c.get("name"):
            chains.setdefault(c["gecko_id"], c["name"])
    with _lock:
        _directory_cache = (time.monotonic(), protocols, chains)
    return protocols, chains


def _get_json(client: httpx.Client, path: str):
    resp = client.get(BASE + path, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _coin_ids() -> dict[str, str]:
    """symbol -> CoinGecko id, from the Discovery universe rows."""
    global _ids_cache
    if _ids_cache is None:
        from api.analytics.attention.universe import load_universe_rows

        rows, _ = load_universe_rows()
        _ids_cache = {str(r["symbol"]).upper(): r["id"] for r in rows if r.get("id")}
    return _ids_cache


def _fees_path(kind: str, name: str) -> str:
    return f"/summary/fees/{quote(name)}" if kind == "protocol" else f"/overview/fees/{quote(name)}"


def _fees(client: httpx.Client, kind: str, name: str) -> list[tuple[date, float]]:
    """Daily fees for a protocol slug or chain name; [] when DefiLlama has none (HTTP 4xx)."""
    resp = client.get(BASE + _fees_path(kind, name), params={"dataType": "dailyFees"}, timeout=TIMEOUT)
    if 400 <= resp.status_code < 500:
        return []
    resp.raise_for_status()
    chart = resp.json().get("totalDataChart") or []
    return [(_day(ts), float(v)) for ts, v in chart if v is not None]


def _recent(points: list[tuple[date, float]], today: date) -> float:
    start = today - timedelta(days=RECENT_DAYS)
    return sum(v for d, v in points if start <= d < today)


def _read_map() -> dict:
    try:
        data = json.loads(map_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_choice(sym: str, choice: dict | None) -> None:
    saved = _read_map()
    saved[sym] = choice
    map_path().parent.mkdir(parents=True, exist_ok=True)
    cache._atomic_write_json(saved, map_path())


def fetch_series(sym: str, client: httpx.Client, today: date) -> SourceSeries:
    sym = sym.upper()
    try:
        saved = _read_map()
        choice = saved.get(sym)
        if sym in saved and choice is None:
            return SourceSeries(SOURCE, sym, [], "unavailable", "no protocol")
        if choice is not None:
            points = _fees(client, choice["kind"], choice["name"])
        else:
            gecko = _coin_ids().get(sym)
            protocols, chains = _directory(client)
            candidates = [("protocol", s) for s in protocols.get(gecko, [])[:MAX_CANDIDATES]]
            if gecko in chains:
                candidates.append(("chain", chains[gecko]))
            best: tuple[float, tuple[str, str], list] | None = None
            for kind, name in candidates:
                pts = _fees(client, kind, name)
                total = _recent(pts, today)
                if total > 0 and (best is None or total > best[0]):
                    best = (total, (kind, name), pts)
            if best is None:
                _save_choice(sym, None)
                return SourceSeries(SOURCE, sym, [], "unavailable", "no protocol")
            choice = {"kind": best[1][0], "name": best[1][1]}
            _save_choice(sym, choice)
            points = best[2]
    except Exception as exc:  # noqa: BLE001 - classified, never raised
        return SourceSeries(SOURCE, sym, [], "unavailable", _failure_reason(exc))
    pts = sorted({d: v for d, v in points if d < today and v == v and v >= 0}.items())
    if not pts:
        return SourceSeries(SOURCE, sym, [], "unavailable", "empty response")
    ok = len(pts) >= MIN_HISTORY_DAYS
    return SourceSeries(SOURCE, sym, pts, "ok" if ok else "insufficient-history", "" if ok else f"{len(pts)} days")
