"""T40 / S5a: screener layout store, one local JSON file (C2, C3).

`{"version": 1, "sections": {"crypto": {"revision", "saved_at", "groups",
"hidden_lines"}}}`. The path is `SCREENER_LAYOUT_PATH`, else `layout.json`
next to the watchlist file, resolved at CALL time (see `watchlist.py`'s
RFC-005 Deviation #1), so anything that redirects the watchlist redirects
the layout too.

Membership stays in `watchlist.json`; every read reconciles the stored
grouping against it. A read never writes. An unreadable file reads as the
default with `source="recovered"` and is moved to `layout.json.bad` by the
next write. Writes are atomic (temp file in the same directory, fsync,
`os.replace`) and serialized by one process lock; nothing is cached.
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

from api.data import freshness
from api.data import watchlist as watchlist_store
from api.models.layout import MAX_GROUP_NAME, MAX_GROUPS, Layout, LayoutGroup, LayoutUpdate

logger = logging.getLogger(__name__)

_LAYOUT_ENV = "SCREENER_LAYOUT_PATH"
LAYOUT_VERSION = 1
# Sections are a registry; any other name is refused.
SECTIONS: tuple[str, ...] = ("crypto",)
# Spaghetti reference lines: they may stay hidden whether or not they are
# on the watchlist.
REFERENCE_SYMBOLS: tuple[str, ...] = ("BTC", "HYPE")
DEFAULT_GROUP_ID = "main"
DEFAULT_GROUP_NAME = "Main"
GROUP_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")

_LOCK = threading.RLock()


class UnknownSectionError(Exception):
    """The section name is not in SECTIONS (HTTP 404)."""


class StaleRevisionError(Exception):
    """The update's revision is not the stored one (HTTP 409)."""


class InvalidLayoutError(ValueError):
    """The update breaks a layout rule (HTTP 422)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def layout_path() -> Path:
    override = os.environ.get(_LAYOUT_ENV)
    if override:
        return Path(override)
    return Path(watchlist_store.DEFAULT_WATCHLIST_PATH).parent / "layout.json"


def _bad_path(path: Path) -> Path:
    return path.with_name(path.name + ".bad")


def _check_section(section: str) -> None:
    if section not in SECTIONS:
        raise UnknownSectionError(section)


def _valid_section(raw) -> bool:
    if not isinstance(raw, dict) or not isinstance(raw.get("revision"), int):
        return False
    groups, hidden = raw.get("groups"), raw.get("hidden_lines", [])
    if not isinstance(groups, list) or not isinstance(hidden, list):
        return False
    for group in groups:
        if not isinstance(group, dict):
            return False
        if not isinstance(group.get("id"), str) or not isinstance(group.get("name"), str):
            return False
        coins = group.get("coins")
        if not isinstance(coins, list) or not all(isinstance(c, str) for c in coins):
            return False
    return all(isinstance(h, str) for h in hidden)


def _load(path: Path) -> tuple[dict | None, bool]:
    """(data, corrupt). A missing file is (None, False)."""
    if not path.exists():
        return None, False
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None, True
    if (
        not isinstance(data, dict)
        or data.get("version") != LAYOUT_VERSION
        or not isinstance(data.get("sections"), dict)
        or not all(_valid_section(s) for s in data["sections"].values())
    ):
        return None, True
    return data, False


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _load_for_write(path: Path) -> dict:
    """The stored document, or an empty one; an unreadable file is first
    moved aside to `.bad` (replacing an older one)."""
    data, corrupt = _load(path)
    if corrupt:
        os.replace(path, _bad_path(path))
        logger.warning("unreadable layout moved to %s", _bad_path(path))
    if data is None:
        data = {"version": LAYOUT_VERSION, "sections": {}}
    return data


def _reconcile(groups: list[dict], hidden: list[str], coins: list[str]) -> tuple[list[dict], list[str]]:
    members = set(coins)
    placed: set[str] = set()
    out = []
    for group in groups:
        kept = []
        for coin in group["coins"]:
            if coin in members and coin not in placed:
                kept.append(coin)
                placed.add(coin)
        out.append({"id": group["id"], "name": group["name"], "coins": kept})
    if not out:
        out.append({"id": DEFAULT_GROUP_ID, "name": DEFAULT_GROUP_NAME, "coins": []})
    out[-1]["coins"].extend(c for c in coins if c not in placed)
    seen: set[str] = set()
    kept_hidden = []
    for symbol in hidden:
        if (symbol in members or symbol in REFERENCE_SYMBOLS) and symbol not in seen:
            kept_hidden.append(symbol)
            seen.add(symbol)
    return out, kept_hidden


def _layout(section: str, stored: dict | None, source: str) -> Layout:
    coins = watchlist_store.read_watchlist()
    if stored is None:
        groups, hidden = _reconcile([], [], coins)
        revision, saved_at = 0, None
    else:
        groups, hidden = _reconcile(stored["groups"], stored.get("hidden_lines", []), coins)
        revision, saved_at = stored["revision"], stored.get("saved_at")
    return Layout(
        version=LAYOUT_VERSION,
        section=section,
        revision=revision,
        saved_at=saved_at,
        source=source,
        groups=[LayoutGroup(**g) for g in groups],
        hidden_lines=hidden,
    )


def _store_section(path: Path, data: dict, section: str, groups: list[dict], hidden: list[str]) -> dict:
    old = data["sections"].get(section)
    stored = {
        "revision": (old["revision"] if old else 0) + 1,
        "saved_at": freshness.iso_z(_now()),
        "groups": groups,
        "hidden_lines": hidden,
    }
    data["sections"][section] = stored
    _write(path, data)
    return stored


def read_layout(section: str) -> Layout:
    _check_section(section)
    with _LOCK:
        data, corrupt = _load(layout_path())
    if corrupt:
        return _layout(section, None, "recovered")
    stored = (data or {}).get("sections", {}).get(section)
    return _layout(section, stored, "file" if stored else "default")


def _validate(update: LayoutUpdate) -> tuple[list[dict], list[str]]:
    if not update.groups:
        raise InvalidLayoutError("a layout needs at least one group")
    if len(update.groups) > MAX_GROUPS:
        raise InvalidLayoutError(f"at most {MAX_GROUPS} groups")
    ids: set[str] = set()
    names: set[str] = set()
    coins: set[str] = set()
    groups = []
    for group in update.groups:
        if not GROUP_ID_RE.match(group.id):
            raise InvalidLayoutError(f"invalid group id: {group.id!r}")
        if group.id in ids:
            raise InvalidLayoutError(f"repeated group id: {group.id!r}")
        ids.add(group.id)
        name = group.name.strip()
        if not 1 <= len(name) <= MAX_GROUP_NAME:
            raise InvalidLayoutError(f"group names are 1-{MAX_GROUP_NAME} characters")
        if name.casefold() in names:
            raise InvalidLayoutError(f"repeated group name: {name!r}")
        names.add(name.casefold())
        members = []
        for coin in group.coins:
            symbol = coin.strip().upper()
            if symbol in coins:
                raise InvalidLayoutError(f"coin in more than one place: {symbol}")
            coins.add(symbol)
            members.append(symbol)
        groups.append({"id": group.id, "name": name, "coins": members})
    return groups, [h.strip().upper() for h in update.hidden_lines]


def save_layout(section: str, update: LayoutUpdate) -> Layout:
    _check_section(section)
    groups, hidden = _validate(update)
    path = layout_path()
    with _LOCK:
        data, _corrupt = _load(path)
        current = ((data or {}).get("sections", {}).get(section) or {}).get("revision", 0)
        if update.revision != current:
            raise StaleRevisionError(section)
        data = _load_for_write(path)
        groups, hidden = _reconcile(groups, hidden, watchlist_store.read_watchlist())
        stored = _store_section(path, data, section, groups, hidden)
    return _layout(section, stored, "file")


def reset_layout(section: str) -> Layout:
    """Drop only `section`; the file goes when no section remains."""
    _check_section(section)
    path = layout_path()
    with _LOCK:
        if path.exists():
            data = _load_for_write(path)
            if path.exists() and data["sections"].pop(section, None) is not None:
                if data["sections"]:
                    _write(path, data)
                else:
                    path.unlink()
    return _layout(section, None, "default")


def place_coin(section: str, symbol: str, group_id: str) -> bool:
    """Move `symbol` (already on the watchlist) into group `group_id`, saving
    the default layout first when no file exists. False when no such group."""
    _check_section(section)
    path = layout_path()
    with _LOCK:
        data = _load_for_write(path)
        current = _layout(section, data["sections"].get(section), "file")
        groups = [g.model_dump() for g in current.groups]
        target = next((g for g in groups if g["id"] == group_id), None)
        if target is None:
            return False
        for group in groups:
            if symbol in group["coins"]:
                group["coins"].remove(symbol)
        target["coins"].append(symbol)
        _store_section(path, data, section, groups, current.hidden_lines)
    return True


def drop_coin(section: str, symbol: str) -> bool:
    """Remove `symbol` from the groups and hidden lines (references stay
    hidden), only when a saved section exists. True when it wrote."""
    _check_section(section)
    path = layout_path()
    with _LOCK:
        data, corrupt = _load(path)
        if corrupt or data is None or section not in data["sections"]:
            return False
        stored = data["sections"][section]
        groups = [
            {**g, "coins": [c for c in g["coins"] if c != symbol]} for g in stored["groups"]
        ]
        hidden = [h for h in stored.get("hidden_lines", []) if h != symbol or h in REFERENCE_SYMBOLS]
        groups, hidden = _reconcile(groups, hidden, watchlist_store.read_watchlist())
        _store_section(path, data, section, groups, hidden)
    return True
