"""Bot-written onboarding files under `<cache>/attention/onboarding/` (T223, D-31).

`ledger.json` (atomic write, size cap; a corrupt file is refused and kept), the append-only daily log
`log/<UTC date>.json`, and small JSON helpers for the overlay, pending and proposal files. Every string written is
stripped of control and bidi characters and capped at MAX_TEXT. Paths are resolved from `cache.CACHE_ROOT` at call
time so tests redirect them. Owner edits never live here (they live in `coin_onboarding.json`).
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from api.data import cache
from api.data.attention import coin_ledger

MAX_TEXT = 200
MAX_LEDGER_BYTES = 2_000_000
MAX_FILE_BYTES = 1_000_000
MAX_LOG_ENTRIES = 2_000
# C0/C1 controls, DEL, and the bidi / zero-width format characters.
_UNSAFE = re.compile("[\x00-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")


def root() -> Path:
    return cache.CACHE_ROOT / "attention" / "onboarding"


def ledger_path() -> Path:
    return root() / "ledger.json"


def sanitize(value):
    """Strings stripped of control and bidi characters and capped; containers walked; other scalars kept."""
    if isinstance(value, str):
        return _UNSAFE.sub("", value)[:MAX_TEXT]
    if isinstance(value, dict):
        return {sanitize(str(k)): sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(v) for v in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return sanitize(str(value))


def _valid_ledger(doc) -> bool:
    if not isinstance(doc, dict) or not isinstance(doc.get("coins"), dict):
        return False
    for e in doc["coins"].values():
        if not isinstance(e, dict) or set(coin_ledger.ENTRY_KEYS) - set(e) or e["state"] not in coin_ledger.STATES:
            return False
    return all(doc.get(k) is None or isinstance(doc.get(k), str) for k in ("last_advanced_date", "seeded_at"))


def read_ledger() -> tuple[dict | None, str]:
    """(doc, "ok"), (None, "absent") or (None, "corrupt"); a corrupt file is left on disk untouched."""
    p = ledger_path()
    if not p.exists():
        return None, "absent"
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, "corrupt"
    return (doc, "ok") if _valid_ledger(doc) else (None, "corrupt")


def _write(doc, path: Path, cap: int) -> None:
    if len(json.dumps(doc, sort_keys=True)) > cap:
        raise ValueError(f"onboarding store: {path.name} over the size cap")
    path.parent.mkdir(parents=True, exist_ok=True)
    cache._atomic_write_json(doc, path)


def write_ledger(doc: dict) -> None:
    _write(sanitize(doc), ledger_path(), MAX_LEDGER_BYTES)


def read_json(name: str) -> dict | None:
    """A bot JSON object file under the onboarding root; None when absent or unreadable (never raises)."""
    try:
        doc = json.loads((root() / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def write_json(name: str, doc: dict) -> None:
    _write(sanitize(doc), root() / name, MAX_FILE_BYTES)


def _log_path(day: str) -> Path:
    date.fromisoformat(day)   # raises ValueError on anything that is not a plain ISO date
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise ValueError("onboarding log: bad date")
    return root() / "log" / f"{day}.json"


def read_log(day: str) -> dict:
    try:
        doc = json.loads(_log_path(day).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"entries": [], "dropped": 0}
    if not isinstance(doc, dict) or not isinstance(doc.get("entries"), list):
        return {"entries": [], "dropped": 0}
    return {"entries": doc["entries"], "dropped": int(doc.get("dropped") or 0)}


def append_log(day: str, entries: list[dict]) -> None:
    """Append-only; beyond MAX_LOG_ENTRIES per day new entries are dropped and counted."""
    path = _log_path(day)
    doc = read_log(day)
    for e in entries:
        if len(doc["entries"]) >= MAX_LOG_ENTRIES:
            doc["dropped"] += 1
        else:
            doc["entries"].append(sanitize(e))
    _write(doc, path, MAX_FILE_BYTES * 2)


def has_log_history() -> bool:
    d = root() / "log"
    return d.is_dir() and any(d.glob("*.json"))
