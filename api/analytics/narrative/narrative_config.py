"""Unified, user-editable narrative config (narrative-v2 RFC-2, ADR-2).

`api/data/narratives.json` is the ONE place to add, rename, remove or
re-coin a narrative for `/api/narrative/history`, the `/narrative` page, the
nightly snapshot and the pytrends backfill. It replaces the old two-file
split (`narrative_categories.json` seeds + `narrative_category_map.json`
coins) for those paths only. `/api/narrative/categories`, `/screener` and
`trigger.py` are NOT driven by this file — they stay on the frozen legacy
seed file and `mapping.LEGACY_COIN_CATEGORY_MAP`.

Behaviour:
- Re-read whenever the file's mtime changes (no restart needed).
- Bad entries are skipped with a warning naming them; the rest still load.
- A structurally invalid file (not JSON, not an object, no "narratives"
  list, or missing) falls back to the last-known-good copy loaded from the
  same path in this process, or an empty list if there never was one.

History keying (AC-7): archived history is keyed by narrative `id` (and, for
pytrends/reddit, by the narrative's first keyword) — never by `label`.
Renaming a `label` is cosmetic. Removing an entry, or setting
`"enabled": false`, only hides the narrative; its archived rows stay on disk
under the old id and reappear unchanged if the entry is re-added.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import re
import threading
from pathlib import Path

from api.analytics.narrative.mapping import LEGACY_COIN_CATEGORY_MAP

logger = logging.getLogger(__name__)

NARRATIVES_PATH = Path(__file__).resolve().parents[2] / "data" / "narratives.json"
# Override for tests/E2E (narrative-v2 RFC-7), mirroring PAIRS_UNIVERSE_PATH in
# api/data/pairs_universe.py. Read on every call; unset = the real file above.
NARRATIVES_PATH_ENV = "NARRATIVES_PATH"


def default_narratives_path() -> Path:
    """The config file to read when no explicit path is passed: the
    `NARRATIVES_PATH` env override when set, else `api/data/narratives.json`."""
    override = os.environ.get(NARRATIVES_PATH_ENV)
    return Path(override) if override else NARRATIVES_PATH

# ids are used to build cache file paths, so keep them to a safe slug.
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

_lock = threading.Lock()
_cache: dict[str, object] = {"key": None, "narratives": []}
_last_good: dict[str, list[dict]] = {}


class _Malformed(Exception):
    pass


def _mtime(path: Path) -> int | None:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None


def _validate_entry(raw: object, index: int) -> dict | None:
    where = f"entry #{index}"
    if not isinstance(raw, dict):
        logger.warning("narratives: skipping %s (not an object)", where)
        return None
    nid = raw.get("id")
    if not isinstance(nid, str) or not _ID_RE.match(nid):
        logger.warning("narratives: skipping %s id=%r (id must be a non-empty lowercase slug)", where, nid)
        return None
    where = f"{where} id={nid!r}"
    label = raw.get("label")
    if not isinstance(label, str) or not label.strip():
        logger.warning("narratives: skipping %s (label must be a non-empty string)", where)
        return None
    keywords = raw.get("keywords")
    if (not isinstance(keywords, list) or not keywords
            or not all(isinstance(k, str) and k.strip() for k in keywords)):
        logger.warning("narratives: skipping %s (keywords must be a non-empty list of non-empty strings)", where)
        return None
    enabled = raw.get("enabled", True)
    if not isinstance(enabled, bool):
        logger.warning("narratives: skipping %s (enabled must be true or false)", where)
        return None
    raw_coins = raw.get("coins", [])
    if not isinstance(raw_coins, list):
        logger.warning("narratives: %s coins is not a list; treating as no coins", where)
        raw_coins = []
    coins: list[str] = []
    for sym in raw_coins:
        if not isinstance(sym, str) or not sym or sym != sym.strip() or sym != sym.upper():
            logger.warning("narratives: %s skipping coin %r (must be a non-empty UPPERCASE ticker)", where, sym)
            continue
        if sym not in coins:
            coins.append(sym)
    return {"id": nid, "label": label.strip(), "keywords": [k.strip() for k in keywords],
            "coins": coins, "enabled": enabled}


def _parse(path: Path) -> list[dict]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError as exc:
        raise _Malformed(f"{path} not found") from exc
    except (OSError, ValueError) as exc:
        raise _Malformed(f"could not parse {path} ({exc})") from exc
    if not isinstance(data, dict):
        raise _Malformed(f"{path} top level is not an object")
    entries = data.get("narratives")
    if not isinstance(entries, list):
        raise _Malformed(f"{path} has no \"narratives\" list")
    out: list[dict] = []
    seen_ids: dict[str, int] = {}
    seen_labels: dict[str, str] = {}
    for i, raw in enumerate(entries):
        entry = _validate_entry(raw, i)
        if entry is None:
            continue
        if entry["id"] in seen_ids:
            logger.warning("narratives: skipping entry #%d (duplicate id %r; entry #%d wins)",
                           i, entry["id"], seen_ids[entry["id"]])
            continue
        seen_ids[entry["id"]] = i
        label_key = entry["label"].casefold()
        if label_key in seen_labels:
            logger.warning("narratives: ids %r and %r share label %r (allowed; labels are cosmetic)",
                           seen_labels[label_key], entry["id"], entry["label"])
        else:
            seen_labels[label_key] = entry["id"]
        out.append(entry)
    return out


def load_all_narratives(path: Path | None = None) -> list[dict]:
    """Every valid entry, including disabled ones, in file order."""
    path = default_narratives_path() if path is None else path
    key = (str(path), _mtime(path))
    with _lock:
        if _cache["key"] == key:
            return copy.deepcopy(_cache["narratives"])  # type: ignore[arg-type]
        try:
            loaded = _parse(path)
            _last_good[str(path)] = loaded
        except _Malformed as exc:
            fallback = _last_good.get(str(path))
            if fallback is None:
                logger.warning("narratives: %s; no last-known-good copy, loading no narratives", exc)
                loaded = []
            else:
                logger.warning("narratives: %s; keeping last-known-good configuration", exc)
                loaded = fallback
        _cache["key"], _cache["narratives"] = key, loaded
        return copy.deepcopy(loaded)


def load_narratives(path: Path | None = None) -> list[dict]:
    """Enabled narratives only, in file order. Each dict has
    `id`, `label`, `keywords` (non-empty), `coins`, `enabled`."""
    return [n for n in load_all_narratives(path) if n["enabled"]]


def primary_keyword(narrative: dict) -> str:
    """The key pytrends/reddit history is archived under (ADR-2)."""
    return narrative["keywords"][0]


def coins_for(narrative_id: str, path: Path | None = None) -> list[tuple[str, bool]]:
    """Sorted `(symbol, narrative_only)` for an enabled narrative.
    `narrative_only` is True when the coin is absent from the frozen legacy
    map that drives /categories and /screener (same meaning as v1)."""
    for n in load_narratives(path):
        if n["id"] == narrative_id:
            return [(s, s not in LEGACY_COIN_CATEGORY_MAP) for s in sorted(n["coins"])]
    return []


def narratives_for_coin(symbol: str, path: Path | None = None) -> list[str]:
    """Ids of every enabled narrative listing `symbol` (a coin may belong to
    more than one). Unlisted coin → `[]`."""
    key = symbol.upper().strip()
    return [n["id"] for n in load_narratives(path) if key in n["coins"]]
