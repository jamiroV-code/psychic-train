"""The D-3 reference universe: top-100 by market cap minus stablecoins, wrapped and exchange tokens.

Source: a non-empty `reference` in attention_universe.json overrides; otherwise the latest
stored top-100 snapshot. Nothing usable = ([], "reference-missing"), never a guess.
"""
from __future__ import annotations

import json
from pathlib import Path

from api.data.attention import universe_store

UNIVERSE_PATH = Path(__file__).resolve().parents[2] / "data" / "attention_universe.json"
TOP_N = 100
MISSING = "reference-missing"


def _cap(row: dict) -> float:
    cap = row.get("market_cap")
    return float(cap) if isinstance(cap, (int, float)) else float("-inf")


def load_universe(path: Path | None = None) -> tuple[list[str], str]:
    try:
        data = json.loads((path or UNIVERSE_PATH).read_text())
        excluded = {str(s).upper() for k in ("stablecoins", "wrapped", "exchange_tokens")
                    for s in data.get(k, [])}
        override = data.get("reference") or []
    except (OSError, ValueError, AttributeError, TypeError):
        return [], MISSING
    if override:
        candidates, reason = [str(s) for s in override], "override"
    else:
        snap = universe_store.read_latest()
        rows = sorted((r for r in (snap or {}).get("coins", []) if isinstance(r, dict) and r.get("symbol")),
                      key=_cap, reverse=True)[:TOP_N]
        candidates, reason = [str(r["symbol"]) for r in rows], "snapshot"
    symbols: list[str] = []
    for s in candidates:
        sym = s.upper()
        if sym not in excluded and sym not in symbols:
            symbols.append(sym)
    return (symbols, reason) if symbols else ([], MISSING)


def load_reference(path: Path | None = None) -> list[str]:
    return load_universe(path)[0]


def load_universe_rows(path: Path | None = None) -> tuple[list[dict], str]:
    """Discovery universe (U2): the top-N snapshot ROWS (symbol, id, market_cap, volume_24h), cap order, with
    none of the three lists dropped; classes decide what is OUT (`universe_classes`). A non-empty `reference`
    override gives symbol-only rows (no volume). Baskets keeps `load_universe`/`load_reference` (Q-V1)."""
    try:
        override = json.loads((path or UNIVERSE_PATH).read_text()).get("reference") or []
    except (OSError, ValueError, AttributeError, TypeError):
        return [], MISSING
    if override:
        rows, reason = [{"symbol": str(s)} for s in override], "override"
    else:
        snap = universe_store.read_latest()
        rows = sorted((r for r in (snap or {}).get("coins", []) if isinstance(r, dict) and r.get("symbol")),
                      key=_cap, reverse=True)[:TOP_N]
        reason = "snapshot"
    out, seen = [], set()
    for r in rows:
        sym = str(r["symbol"]).upper()
        if sym not in seen:
            seen.add(sym)
            out.append({**r, "symbol": sym})
    return (out, reason) if out else ([], MISSING)
