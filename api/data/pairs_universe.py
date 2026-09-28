"""Pair-screener coin universe (cointegration-screener RFC-001).

Reads `api/data/pairs_universe.json` - a hand-editable `{"coins": [...]}`
file that is physically and logically separate from the momentum screener's
watchlist (AC-9). This module deliberately does NOT import
`api.data.watchlist`; a test asserts that.

The path is resolved at CALL time, never bound at import (the RFC-005
watchlist incident was a default argument binding the real path at import).
"""
from __future__ import annotations

import json
import os
import warnings
from itertools import combinations
from pathlib import Path

UNIVERSE_FILENAME = "pairs_universe.json"
# Override for tests/E2E (RFC-005), mirroring SCREENER_WATCHLIST_PATH. Read on
# every call so an env change is honoured without re-importing this module.
UNIVERSE_PATH_ENV = "PAIRS_UNIVERSE_PATH"

# Pegged stablecoins. A pair containing one is meaningless for cointegration
# (near-constant log price), so the loader warns if one appears.
KNOWN_STABLECOINS = frozenset({"USDT", "USDC", "DAI", "USDE", "FDUSD", "TUSD", "PYUSD", "USDS"})


class UniverseFileError(ValueError):
    """The universe file is missing or not shaped `{"coins": [str, ...]}`."""


def real_universe_path() -> Path:
    """The repo's own universe file, ignoring any override."""
    return Path(__file__).resolve().parent / UNIVERSE_FILENAME


def default_universe_path() -> Path:
    override = os.environ.get(UNIVERSE_PATH_ENV)
    if override:
        return Path(override)
    return real_universe_path()


def load_universe(path: Path | str | None = None) -> list[str]:
    """Return the universe tickers, uppercased, de-duplicated in file order.

    Warns (does not fail) on duplicate or known-stablecoin tickers. Raises
    `UniverseFileError` on a missing/malformed file - a broken universe must
    be loud, not an empty screener.
    """
    resolved = Path(path) if path is not None else default_universe_path()
    try:
        with open(resolved, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError as exc:
        raise UniverseFileError(f"universe file not found: {resolved}") from exc
    except json.JSONDecodeError as exc:
        raise UniverseFileError(f"universe file is not valid JSON: {resolved}: {exc}") from exc

    if not isinstance(data, dict) or not isinstance(data.get("coins"), list):
        raise UniverseFileError(f'universe file must be {{"coins": [...]}}: {resolved}')

    coins: list[str] = []
    for raw in data["coins"]:
        if not isinstance(raw, str) or not raw.strip():
            raise UniverseFileError(f"universe entry is not a non-empty string: {raw!r}")
        ticker = raw.strip().upper()
        if ticker in coins:
            warnings.warn(f"duplicate universe ticker ignored: {ticker}", stacklevel=2)
            continue
        if ticker in KNOWN_STABLECOINS:
            warnings.warn(f"stablecoin ticker in pairs universe: {ticker}", stacklevel=2)
        coins.append(ticker)
    return coins


def enumerate_pairs(coins: list[str]) -> list[tuple[str, str]]:
    """All unordered pairs - C(n, 2) of them, no self-pairs, no duplicates."""
    return list(combinations(coins, 2))
