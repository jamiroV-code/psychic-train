"""Venue lists for Discovery tradeability (T189): read-only over stored files, no network.

Owner rule (26-10-26): a coin the owner cannot trade has NO TRADING MARKET and is excluded. Tracked venues are
Binance and Hyperliquid, spot or perpetual. Per symbol:
- `tradeable`: a loaded, fresh venue list has it with 24h volume above zero (or listed, volume not stored);
- `not_tradeable` (detail ZERO_VOLUME): its snapshot 24h volume is exactly 0 and no fresh list shows volume;
- `not_tradeable` (detail NO_MARKET): every tracked list is loaded and fresh and none has it with volume;
- `unknown`: anything else. A list that is missing, failed or stale (older than STALE_AFTER_DAYS) proves
  nothing either way, so a coin is never excluded on a missing source (fail-closed toward keeping coins).

Inputs, the newest file dated on or before `today`:
- `attention/markets/{venue}/{YYYY-MM-DD}.json`, the store a later `markets` runner writes (MARKETS_DIR):
  {"venue": "binance", "as_of": "YYYY-MM-DD", "status": "ok" | "failed", "reason": "...",
   "markets": [{"symbol": "1000PEPE", "kind": "spot" | "perp", "volume_24h": 123.4 | null}]}
  `symbol` is the venue's own base name; ALIASES maps scaled names to the universe symbol.
- Hyperliquid, while that store has no file: the narrative job's perp name list
  (`narrative/exchange/markets/{date}.json`, names only) with 24h volume from the `hyperliquid_volume` store.
Binance has no stored list yet, so today it is `missing` and only the zero-volume rule can exclude.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from api.data import cache
from api.data.attention import store

TRACKED_VENUES = ("binance", "hyperliquid")
VENUE_NAMES = {"binance": "Binance", "hyperliquid": "Hyperliquid"}
STALE_AFTER_DAYS = 2
MARKETS_DIR = ("attention", "markets")
HL_VOLUME_SOURCE = "hyperliquid_volume"
ZERO_VOLUME = "zero 24h volume"
NO_MARKET = "no listed market on Binance or Hyperliquid"
# Reviewed alias table: a venue's scaled contract name -> the universe symbol. Explicit entries only: a generic
# prefix strip would turn KAS into AS and KAITO into AITO. Hyperliquid names are from the stored perp list
# (2026-10-25); Binance names follow its USD-M naming and are confirmed by the owner probe P-VEN.
ALIASES = {
    "KPEPE": "PEPE", "KSHIB": "SHIB", "KBONK": "BONK", "KFLOKI": "FLOKI", "KNEIRO": "NEIRO", "KLUNC": "LUNC",
    "1000PEPE": "PEPE", "1000SHIB": "SHIB", "1000BONK": "BONK", "1000FLOKI": "FLOKI", "1000LUNC": "LUNC",
    "1000SATS": "SATS", "1000RATS": "RATS", "1000CAT": "CAT", "1000CHEEMS": "CHEEMS", "1000XEC": "XEC",
    "1MBABYDOGE": "BABYDOGE", "1000000MOG": "MOG",
}

VenueState = Literal["ok", "missing", "failed", "stale"]
Status = Literal["tradeable", "not_tradeable", "unknown"]


@dataclass(frozen=True)
class VenueList:
    venue: str
    state: VenueState
    as_of: str | None = None
    # universe symbol -> best 24h volume over its markets; None = listed, volume not stored
    volumes: dict[str, float | None] = field(default_factory=dict)


@dataclass(frozen=True)
class Verdict:
    status: Status
    detail: str = ""


def canonical(name: str) -> str:
    s = str(name).strip().upper()
    return ALIASES.get(s, s)


def _best(a: float | None, b: float | None) -> float | None:
    """Positive wins; then not-stored (None); then 0."""
    if (a or 0) > 0 or (b or 0) > 0:
        return max(a or 0.0, b or 0.0)
    return None if a is None or b is None else 0.0


def _volume(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        return None
    return float(value)


def _newest(folder: Path, today: date) -> tuple[date, Path] | None:
    dated = []
    for p in folder.glob("*.json") if folder.is_dir() else ():
        try:
            d = date.fromisoformat(p.stem)
        except ValueError:
            continue
        if d <= today:
            dated.append((d, p))
    return max(dated) if dated else None


def _stale(as_of: date, today: date) -> bool:
    return (today - as_of).days > STALE_AFTER_DAYS


def _from_store(venue: str, today: date) -> VenueList | None:
    """The `markets` store file for `venue`, or None when the store has none (the caller may fall back)."""
    found = _newest(cache.CACHE_ROOT.joinpath(*MARKETS_DIR, venue), today)
    if found is None:
        return None
    day, path = found
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("status") != "ok" or not isinstance(doc.get("markets"), list):
            return VenueList(venue, "failed", day.isoformat())
        volumes: dict[str, float | None] = {}
        for m in doc["markets"]:
            sym = canonical(m["symbol"])
            vol = _volume(m.get("volume_24h"))
            volumes[sym] = _best(volumes[sym], vol) if sym in volumes else vol
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return VenueList(venue, "failed", day.isoformat())
    return VenueList(venue, "stale" if _stale(day, today) else "ok", day.isoformat(), volumes)


def _hl_volume(symbol: str, day: date) -> float | None:
    """Newest stored Hyperliquid 24h volume within STALE_AFTER_DAYS of the list date, else None (not stored)."""
    try:
        points = store.read_points(HL_VOLUME_SOURCE, symbol)
    except store.StoreReadError:
        return None
    recent = [(d, v) for d, v in points if timedelta(0) <= day - d <= timedelta(days=STALE_AFTER_DAYS)]
    return _volume(max(recent)[1]) if recent else None


def _hyperliquid_perps(today: date, symbols) -> VenueList:
    found = _newest(cache.CACHE_ROOT / "narrative" / "exchange" / "markets", today)
    if found is None:
        return VenueList("hyperliquid", "missing")
    day, path = found
    try:
        names = json.loads(path.read_text(encoding="utf-8"))
        listed = {canonical(n) for n in names}
    except (OSError, ValueError, TypeError, AttributeError):
        return VenueList("hyperliquid", "failed", day.isoformat())
    wanted = listed if symbols is None else listed & {canonical(s) for s in symbols}
    volumes = {s: _hl_volume(s, day) for s in sorted(wanted)}
    return VenueList("hyperliquid", "stale" if _stale(day, today) else "ok", day.isoformat(), volumes)


def load_venues(today: date | None = None, symbols=None) -> dict[str, VenueList]:
    """One VenueList per tracked venue, point in time at `today`. `symbols` (optional) limits the Hyperliquid
    volume reads to those coins; the listing itself is never limited."""
    today = today or datetime.now(timezone.utc).date()
    out = {}
    for venue in TRACKED_VENUES:
        got = _from_store(venue, today)
        if got is None:
            got = _hyperliquid_perps(today, symbols) if venue == "hyperliquid" else VenueList(venue, "missing")
        out[venue] = got
    return out


def tradeability(symbol: str, venues: dict[str, VenueList], volume_24h: float | None = None) -> Verdict:
    """See the module docstring. `volume_24h` is the universe snapshot's 24h volume (None = not known)."""
    s = canonical(symbol)
    fresh = [v for v in venues.values() if v.state == "ok"]
    if any(s in v.volumes and (v.volumes[s] is None or v.volumes[s] > 0) for v in fresh):
        return Verdict("tradeable")
    if _volume(volume_24h) == 0.0:
        return Verdict("not_tradeable", ZERO_VOLUME)
    if all(venues.get(name) is not None and venues[name].state == "ok" for name in TRACKED_VENUES):
        return Verdict("not_tradeable", NO_MARKET)
    gaps = [f"{VENUE_NAMES.get(n, n)} list {venues[n].state if n in venues else 'missing'}"
            for n in TRACKED_VENUES if n not in venues or venues[n].state != "ok"]
    return Verdict("unknown", "; ".join(gaps))
