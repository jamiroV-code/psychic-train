"""Watchlist persistence — a single local JSON file (ADR-5).

No database table: the project has no auth/multi-tenancy in scope, and a
JSON file a human can hand-edit is the proportionate choice at this stage.
This module owns all reads/writes so the storage mechanism is a one-file
swap later if ever needed (ADR-5 Future Work).

RFC-005 EXECUTE, Deviation #1 (19-09-26) — path resolution moved from
import time to call time.

Every public function previously wrote `path: Path = DEFAULT_WATCHLIST_PATH`.
Python binds default arguments ONCE, when the `def` statement executes at
import, so `monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH",
tmp)` — which is exactly what `tests/routers/test_watchlist.py`'s `client`
fixture does — rebound the module attribute while leaving the already-bound
defaults pointing at the real file.

The isolation was therefore fictional: the watchlist router tests read and
WROTE `api/data/watchlist.json`, the developer's actual watchlist. This went
unnoticed while that file happened to be empty (the tests' expectations
assume an empty list, so they passed against the real file and left it empty
again). The moment a real watchlist existed, four tests failed and
`test_remove_coin` deleted a live entry as a side effect.

Resolving the path at call time makes the module honestly patchable and
stops the suite touching user data. Signatures stay backward-compatible:
callers passing an explicit path are unaffected.
"""
from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path

# Overridable for the same reason as `cache.CACHE_ROOT`: the Playwright E2E
# runs a real API and must control the symbol set without touching — or
# rewriting — the developer's actual watchlist. Read at import (when the
# uvicorn process starts); still a plain module attribute, still resolved at
# call time by every function, per the Deviation #1 note above.
_WATCHLIST_ENV = "SCREENER_WATCHLIST_PATH"
DEFAULT_WATCHLIST_PATH = (
    Path(os.environ[_WATCHLIST_ENV])
    if os.environ.get(_WATCHLIST_ENV)
    else Path(__file__).resolve().parent / "watchlist.json"
)


# T40 / S5a (C5): the screener holds at most 30 coins. A file already over
# the cap is kept as is; only a NEW symbol is refused.
MAX_COINS = 30
CAP_MESSAGE = "Screener is full: 30 coins maximum. Remove a coin to add another."
SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,14}$")

# One read-modify-write at a time: without it, concurrent adds lose coins
# and the cap check races.
_LOCK = threading.Lock()


class WatchlistFullError(Exception):
    """Raised when adding a new symbol to a list that holds MAX_COINS or more."""


class InvalidSymbolError(Exception):
    """Raised when a symbol does not match SYMBOL_RE after normalizing."""


def normalize_symbol(symbol: str) -> str:
    """Strip and upper-case; raises `InvalidSymbolError` when the result is
    not a plausible ticker."""
    norm = str(symbol).strip().upper()
    if not SYMBOL_RE.match(norm):
        raise InvalidSymbolError(symbol)
    return norm


class SymbolNotFoundError(Exception):
    """Raised when removing a symbol that isn't on the watchlist — the
    router maps this to an explicit 404, never a silent no-op."""


def _resolve(path: Path | None) -> Path:
    """Read the module attribute at CALL time, not at def time, so tests
    that patch `DEFAULT_WATCHLIST_PATH` actually redirect the store."""
    return DEFAULT_WATCHLIST_PATH if path is None else path


def _load_raw(path: Path) -> dict:
    if not path.exists():
        return {"coins": []}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("coins", [])
    return data


def _save_raw(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def read_watchlist(path: Path | None = None) -> list[str]:
    return list(_load_raw(_resolve(path))["coins"])


def add_coin(symbol: str, path: Path | None = None) -> list[str]:
    """Idempotent add — adding an already-present symbol is a no-op, not a
    duplicate entry or an error. Raises `InvalidSymbolError` for a malformed
    symbol and `WatchlistFullError` for a new symbol at MAX_COINS or more."""
    path = _resolve(path)
    symbol = normalize_symbol(symbol)
    with _LOCK:
        data = _load_raw(path)
        if symbol not in data["coins"]:
            if len(data["coins"]) >= MAX_COINS:
                raise WatchlistFullError(symbol)
            data["coins"].append(symbol)
            _save_raw(path, data)
        return list(data["coins"])


def remove_coin(symbol: str, path: Path | None = None) -> list[str]:
    """Raises `SymbolNotFoundError` if `symbol` isn't present — never a
    silent no-op (Public Contracts / API Surface: 404 on remove-missing)."""
    path = _resolve(path)
    symbol = symbol.upper().strip()
    with _LOCK:
        data = _load_raw(path)
        if symbol not in data["coins"]:
            raise SymbolNotFoundError(symbol)
        data["coins"].remove(symbol)
        _save_raw(path, data)
        return list(data["coins"])
