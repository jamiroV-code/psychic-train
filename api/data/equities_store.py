"""Equity ticker store for the LSE adapter (S3) — a single local JSON file.

`{"tickers": [...]}` in `api/data/equities.json`, kept separate from the crypto
watchlist (`watchlist.py`): equities are a different universe with their own
30-ticker cap, counted apart from the crypto 30 (S9A). A file already over the
cap is kept as is; only a NEW ticker is refused.

The path is resolved at CALL time, never bound at import or as a default
argument (see `watchlist.py`'s RFC-005 Deviation #1 for the incident that rule
comes from): `SCREENER_EQUITIES_PATH` overrides it, so tests and E2E never
touch the developer's real file.

Writes are atomic: temp file in the same directory, flushed and fsynced, then
`os.replace`; an interrupted write leaves the previous file intact and removes
the temp file.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from pathlib import Path

_EQUITIES_ENV = "SCREENER_EQUITIES_PATH"
DEFAULT_EQUITIES_PATH = Path(__file__).resolve().parent / "equities.json"

TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")

MAX_TICKERS = 30
CAP_MESSAGE = "Equities list is full: 30 tickers maximum. Remove a ticker to add another."

# One read-modify-write at a time (as `watchlist.py`): without it, concurrent
# adds lose tickers and the cap check races.
_LOCK = threading.Lock()


class TickerLimitError(Exception):
    """Raised when adding a NEW ticker to a list holding MAX_TICKERS or more."""


class InvalidTickerError(ValueError):
    """Raised for a ticker outside `TICKER_RE` (after upper-casing)."""


class TickerNotFoundError(Exception):
    """Raised when removing a ticker that isn't stored — never a silent no-op."""


def equities_path() -> Path:
    override = os.environ.get(_EQUITIES_ENV)
    return Path(override) if override else DEFAULT_EQUITIES_PATH


def normalize_ticker(ticker: str) -> str:
    """Upper-case and validate; raises `InvalidTickerError`."""
    norm = ticker.strip().upper() if isinstance(ticker, str) else ""
    if not TICKER_RE.match(norm):
        raise InvalidTickerError("invalid ticker")
    return norm


def load_tickers() -> list[str]:
    path = equities_path()
    if not path.exists():
        return []
    raw = json.loads(path.read_text() or "{}")
    return [t for t in raw.get("tickers", []) if isinstance(t, str)]


def _write(tickers: list[str]) -> None:
    path = equities_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump({"tickers": tickers}, fh, indent=2)
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


def add_ticker(ticker: str) -> list[str]:
    """Add `ticker` (idempotent). Returns the stored list. Raises
    `TickerLimitError` for a new ticker when MAX_TICKERS are already stored."""
    norm = normalize_ticker(ticker)
    with _LOCK:
        tickers = load_tickers()
        if norm not in tickers:
            if len(tickers) >= MAX_TICKERS:
                raise TickerLimitError(norm)
            tickers.append(norm)
            _write(tickers)
        return tickers


def remove_ticker(ticker: str) -> list[str]:
    """Remove `ticker`; raises `TickerNotFoundError` when it isn't stored."""
    norm = normalize_ticker(ticker)
    with _LOCK:
        tickers = load_tickers()
        if norm not in tickers:
            raise TickerNotFoundError(norm)
        tickers.remove(norm)
        _write(tickers)
        return tickers
