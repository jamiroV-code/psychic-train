"""A recipe is a small JSON file of data: no code, no includes. Every field is checked before use."""
from __future__ import annotations

import json
import math
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from data_integration.approvals import valid_source

MAX_BYTES = 16 * 1024
MAX_URL = 2048
MAX_SELECTOR = 500
TIMEFRAMES = ("15m", "1h", "4h", "1d", "1w")
_SYMBOL = r"[A-Z0-9][A-Z0-9-]{0,31}"
_DEVICES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
_TOP_KEYS = {"schema_version", "source", "tier", "url", "selector", "dataset", "min_rows", "politeness"}
_REQUIRED = _TOP_KEYS - {"politeness"}
_POLITE_DEFAULTS = {"min_delay": 1.0, "max_concurrent": 2, "max_per_host": 1}


class RecipeError(ValueError):
    """The recipe file is not acceptable. The message never contains a path."""


@dataclass(frozen=True)
class Recipe:
    source: str
    tier: int
    url: str
    selector: str
    symbol: str
    timeframe: str
    min_rows: int
    politeness: dict | None = None
    schema_version: int = 1


def _no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise RecipeError("duplicate key in recipe")
        out[key] = value
    return out


def _no_constant(_name):
    raise RecipeError("NaN and Infinity are not allowed")


def _is_int(value) -> bool:
    return type(value) is int


def _is_number(value) -> bool:
    return type(value) in (int, float)


def _text(value, label: str, limit: int) -> str:
    if not isinstance(value, str) or not value or len(value) > limit:
        raise RecipeError(f"{label} must be a non-empty string up to {limit} characters")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise RecipeError(f"{label} must not contain control characters")
    return value


def _url(value) -> str:
    _text(value, "url", MAX_URL)
    if any(ord(c) <= 32 or ord(c) > 126 for c in value):
        raise RecipeError("url must be plain ASCII without spaces")
    try:
        parts = urlsplit(value)
        parts.port  # noqa: B018 - raises ValueError on a bad port
    except ValueError:
        raise RecipeError("url is not valid") from None
    if parts.scheme not in ("http", "https") or not parts.hostname or "@" in parts.netloc:
        raise RecipeError("url must be http or https with a host and no user info")
    return value


def _dataset(value) -> tuple[str, str]:
    if not isinstance(value, dict) or set(value) != {"symbol", "timeframe"}:
        raise RecipeError("dataset needs exactly symbol and timeframe")
    symbol, timeframe = value["symbol"], value["timeframe"]
    if not isinstance(symbol, str) or re.fullmatch(_SYMBOL, symbol) is None:
        raise RecipeError("symbol must be 1-32 characters of A-Z, 0-9 and -, starting with a letter or digit")
    if symbol.split(".")[0] in _DEVICES:
        raise RecipeError("symbol is a reserved device name")
    if not isinstance(timeframe, str) or timeframe not in TIMEFRAMES:
        raise RecipeError("timeframe must be one of " + ", ".join(TIMEFRAMES))
    return symbol, timeframe


def _politeness(value) -> dict:
    if not isinstance(value, dict) or not value or not set(value) <= set(_POLITE_DEFAULTS):
        raise RecipeError("politeness needs min_delay, max_concurrent or max_per_host")
    out = dict(_POLITE_DEFAULTS)
    if "min_delay" in value:
        delay = value["min_delay"]
        if not _is_number(delay) or not math.isfinite(delay) or not 1.0 <= delay <= 3600:
            raise RecipeError("min_delay must be a finite number from 1.0 to 3600")
        out["min_delay"] = float(delay)
    if "max_concurrent" in value:
        if not _is_int(value["max_concurrent"]) or not 1 <= value["max_concurrent"] <= 2:
            raise RecipeError("max_concurrent must be an integer from 1 to 2")
        out["max_concurrent"] = value["max_concurrent"]
    if "max_per_host" in value:
        if not _is_int(value["max_per_host"]) or value["max_per_host"] != 1:
            raise RecipeError("max_per_host must be 1")
        out["max_per_host"] = 1
    return out


def parse_recipe(raw: bytes) -> Recipe:
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates, parse_constant=_no_constant)
    except RecipeError:
        raise
    except (ValueError, RecursionError):
        raise RecipeError("recipe is not valid UTF-8 JSON") from None
    if not isinstance(data, dict):
        raise RecipeError("recipe must be a JSON object")
    unknown = set(data) - _TOP_KEYS
    if unknown:
        raise RecipeError("unknown key in recipe")
    if _REQUIRED - set(data):
        raise RecipeError("recipe is missing a required key")
    if not _is_int(data["schema_version"]) or data["schema_version"] != 1:
        raise RecipeError("schema_version must be 1")
    if not valid_source(data["source"]):
        raise RecipeError("source is not a valid approval name")
    if not _is_int(data["tier"]) or data["tier"] not in (1, 2, 3):
        raise RecipeError("tier must be 1, 2 or 3")
    if not _is_int(data["min_rows"]) or not 2 <= data["min_rows"] <= 100000:
        raise RecipeError("min_rows must be an integer from 2 to 100000")
    symbol, timeframe = _dataset(data["dataset"])
    polite = _politeness(data["politeness"]) if "politeness" in data else None
    return Recipe(
        source=data["source"], tier=data["tier"], url=_url(data["url"]),
        selector=_text(data["selector"], "selector", MAX_SELECTOR), symbol=symbol, timeframe=timeframe,
        min_rows=data["min_rows"], politeness=polite,
    )


def load_recipe(path) -> Recipe:
    p = Path(path)
    try:
        info = p.stat()
    except OSError:
        raise RecipeError("recipe file cannot be read") from None
    if not stat.S_ISREG(info.st_mode):
        raise RecipeError("recipe must be a regular file")
    if info.st_size > MAX_BYTES:
        raise RecipeError("recipe is larger than 16 KiB")
    try:
        raw = p.read_bytes()
    except OSError:
        raise RecipeError("recipe file cannot be read") from None
    if len(raw) > MAX_BYTES:
        raise RecipeError("recipe is larger than 16 KiB")
    return parse_recipe(raw)
