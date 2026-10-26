"""Per-run Trends outcome file (T197): api/data/cache/attention/trends_runs/<UTC run date>.json.

Read-only evidence for the owner: which coin got which outcome and why. No store reader, registry or series
logic reads it. A second run on the same UTC day is appended (the file then holds `runs`), never overwritten.
Reasons are exception classes / HTTP status only, never a message or a response body.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from api.data import cache


def run_path(run_date: date) -> Path:
    return cache.CACHE_ROOT / "attention" / "trends_runs" / f"{run_date.isoformat()}.json"


def append_run(run_date: date, record: dict) -> Path:
    """Write `record` for `run_date`: a first run is the file's top level, a later run turns the file into
    {"runs": [earlier..., record]}. Atomic (temp + rename). An unreadable earlier file raises: its data is kept."""
    path = run_path(run_date)
    doc: dict = record
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(old, dict):
            raise ValueError("unreadable trends run file")
        doc = {"runs": [*old["runs"], record]} if isinstance(old.get("runs"), list) else {"runs": [old, record]}
    path.parent.mkdir(parents=True, exist_ok=True)
    cache._atomic_write_json(doc, path)
    return path
