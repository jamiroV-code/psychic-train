"""Coin -> narrative-category mapping (item 58).

Curated lookup, never inferred/fuzzy-matched from a coin's name or
description — an unmapped coin returns an explicit no-mapping sentinel
(`None`), never silently treated as belonging to whatever category happens
to be triggered. ADR-4 treats `unmapped` as a distinct, non-failure
`narrative_state`, not folded into `rotated-out` or any other value — a
false mapping would let an unrelated coin's price action masquerade as
corroborating narrative evidence for a category it has nothing to do with,
which is exactly the silent-wrongness this plan's "numbers never silently
wrong" rule forbids.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

# FROZEN legacy map (narrative-dashboard RFC-1, option B, user-approved
# 2026-09-24). This is what `/api/narrative/categories` (the trigger's
# CoinGecko trending count) and `/screener`'s `narrative_state` use, and it
# must NOT be widened: AC-1 requires both stay byte-identical, proven by
# api/tests/routers/test_narrative_categories_contract.py. To change the
# narrative map shown on /history and /narrative, edit
# api/data/narrative_category_map.json instead.
LEGACY_COIN_CATEGORY_MAP: dict[str, str] = {
    "BTC": "store-of-value",
    "ETH": "l2s",
    "HYPE": "l2s",
}
# Backward-compatible alias — existing imports keep working.
COIN_CATEGORY_MAP = LEGACY_COIN_CATEGORY_MAP


def map_coin_to_category(symbol: str) -> str | None:
    """Returns the curated category_id for `symbol`, or `None` if this coin
    has no curated mapping yet. Callers must treat `None` as an explicit,
    valid state (ADR-4's `unmapped`) — never as a signal to exclude the
    coin from anything, and never as a fallback that treats it as
    vacuously aligned with whatever category is currently triggered.
    """
    return LEGACY_COIN_CATEGORY_MAP.get(symbol.upper())


# --- Curated, user-editable narrative map (RFC-1) --------------------------
#
# Drives ONLY /api/narrative/history and the /narrative page. Hand-edited
# JSON, re-read whenever its mtime changes (no restart needed). Validated on
# load: bad entries are skipped with a warning naming them, never a crash.

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CATEGORY_MAP_PATH = _DATA_DIR / "narrative_category_map.json"
SEED_CATEGORIES_PATH = _DATA_DIR / "narrative_categories.json"

# Non-seed category ids allowed only for these exact legacy entries.
GRANDFATHERED_ENTRIES: dict[str, str] = {"BTC": "store-of-value"}

_cache_lock = threading.Lock()
_cache: dict[str, object] = {"key": None, "map": {}}


def _seed_category_ids(path: Path) -> set[str]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return {c["id"] for c in data.get("seed_categories", []) if isinstance(c, dict) and "id" in c}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        logger.warning("narrative map: could not read seed categories %s (%s)", path, exc)
        return set()


def _validate(raw_map: object, seed_ids: set[str]) -> dict[str, str]:
    if not isinstance(raw_map, dict):
        logger.warning("narrative map: \"map\" is not an object; loading empty map")
        return {}
    valid: dict[str, str] = {}
    for symbol, category_id in raw_map.items():
        entry = f"{symbol!r} -> {category_id!r}"
        if not isinstance(symbol, str) or not symbol or symbol != symbol.upper() or symbol != symbol.strip():
            logger.warning("narrative map: skipping %s (symbol must be a non-empty UPPERCASE ticker)", entry)
            continue
        if not isinstance(category_id, str):
            logger.warning("narrative map: skipping %s (category id must be a string)", entry)
            continue
        if category_id not in seed_ids and GRANDFATHERED_ENTRIES.get(symbol) != category_id:
            logger.warning("narrative map: skipping %s (unknown category id; not a seed category)", entry)
            continue
        valid[symbol] = category_id
    return valid


def _load_uncached(path: Path, seeds_path: Path) -> dict[str, str]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.warning("narrative map: %s not found; loading empty map", path)
        return {}
    except (OSError, ValueError) as exc:
        logger.warning("narrative map: could not parse %s (%s); loading empty map", path, exc)
        return {}
    if not isinstance(data, dict):
        logger.warning("narrative map: %s top level is not an object; loading empty map", path)
        return {}
    # "_comment" and any other top-level key besides "map" are ignored.
    return _validate(data.get("map", {}), _seed_category_ids(seeds_path))


def _mtime(path: Path) -> int | None:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None


def load_category_map(path: Path | None = None, seeds_path: Path | None = None) -> dict[str, str]:
    """Returns the validated curated map. Re-reads when either file's mtime
    (or the paths) change, so hand edits take effect without a restart."""
    path = CATEGORY_MAP_PATH if path is None else path
    seeds_path = SEED_CATEGORIES_PATH if seeds_path is None else seeds_path
    key = (str(path), _mtime(path), str(seeds_path), _mtime(seeds_path))
    with _cache_lock:
        if _cache["key"] == key:
            return dict(_cache["map"])  # type: ignore[arg-type]
        loaded = _load_uncached(path, seeds_path)
        _cache["key"], _cache["map"] = key, loaded
        return dict(loaded)


def map_coin_to_narrative_category(symbol: str) -> tuple[str | None, bool]:
    """Curated lookup for /history and /narrative ONLY. Returns
    `(category_id, narrative_only)`: `narrative_only` is True when the coin
    is mapped in the curated JSON but not in the frozen legacy map — the UI
    labels those "narrative-only" so /history and /categories never appear
    to disagree silently. Unmapped → `(None, False)`.
    """
    key = symbol.upper().strip()
    category_id = load_category_map().get(key)
    if category_id is None:
        return None, False
    return category_id, key not in LEGACY_COIN_CATEGORY_MAP
