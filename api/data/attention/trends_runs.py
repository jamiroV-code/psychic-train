"""Per-run Trends outcome file (T197): api/data/cache/attention/trends_runs/<UTC run date>.json.

Read-only evidence for the owner: which coin got which outcome and why. No store reader, registry or series
logic reads it; the readers are the campaign (`probe_trends --all-eligible` / `--report`, via
api/scripts/trends_campaign.py) and the waking-up watch list on the Sources panel (`watch_list`, stage 2, D-30),
which is shown only and never scored. A second run on the same UTC day is appended (the file then holds `runs`),
never overwritten. Reasons are exception classes / HTTP status only, never a message or a response body.
"""
from __future__ import annotations

import json
import re
import stat
from datetime import date
from pathlib import Path

from api.data import cache

RUN_FILE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\.json")
RUN_OUTCOMES = frozenset({"ok", "too-little-interest", "quiet-then-surge", "no-keyword", "skipped-unqualified",
                          "failed", "capped", "time-budget"})  # the daily run's own outcome strings (T197)
MAX_RUN_FILE_BYTES = 5_000_000
# Waking-up watch list (stage 2): newest files only, small files only, a bounded answer.
WATCH_MAX_FILES = 30
WATCH_MAX_FILE_BYTES = 1_000_000
WATCH_MAX_COINS = 100
WATCH_OUTCOME = "quiet-then-surge"
WATCH_NEUTRAL = frozenset({"failed", "capped", "time-budget"})   # transient: neither extend nor break a streak
_SYMBOL_RE = re.compile(r"[A-Z0-9_]{1,24}")   # same pattern as trends_keywords.SYMBOL_RE


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


def _latest_run(doc) -> dict | None:
    """The newest run of one file: a single run is the document itself, a second run on the same UTC day turns the
    file into {"runs": [...]} (oldest first). None for any other shape."""
    if isinstance(doc, dict) and isinstance(doc.get("runs"), list):
        doc = doc["runs"][-1] if doc["runs"] else None
    return doc if isinstance(doc, dict) and isinstance(doc.get("coins"), dict) else None


def _read_small(path: Path) -> dict | None:
    """The latest run of a regular, non-symlink file of at most WATCH_MAX_FILE_BYTES; None otherwise."""
    try:
        st = path.lstat()
        if not stat.S_ISREG(st.st_mode) or st.st_size > WATCH_MAX_FILE_BYTES:
            return None
        return _latest_run(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, ValueError, RecursionError):
        return None


def watch_list(today: date | None = None) -> list[dict]:
    """Coins waking up in the daily pulls: [{symbol, days_held}], days_held the count of `quiet-then-surge` days in
    the streak ending at the newest run file (files dated after `today` are ignored). failed, capped, time-budget
    and a missing date are neutral; any other outcome, or a keyword change between two days that both carry one,
    ends the streak. At most WATCH_MAX_FILES files (days_held == WATCH_MAX_FILES reads "30+"). Never raises: a
    corrupt newest file gives []. The path is taken from cache.CACHE_ROOT at call time."""
    folder = cache.CACHE_ROOT / "attention" / "trends_runs"
    try:
        names = sorted((f.name for f in folder.iterdir() if RUN_FILE_RE.fullmatch(f.name)), reverse=True)
    except OSError:
        return []
    if today is not None:
        names = [n for n in names if n[:10] <= today.isoformat()]
    names = names[:WATCH_MAX_FILES]
    if not names:
        return []
    runs = [_read_small(folder / n) for n in names]
    newest = runs[0]
    if newest is None:
        return []
    out = []
    for sym in newest["coins"]:
        if not (isinstance(sym, str) and _SYMBOL_RE.fullmatch(sym)):
            continue
        held, keyword = 0, None
        for run in runs:
            if run is None:
                continue   # an unreadable older file is skipped like a missing date
            rec = run["coins"].get(sym)
            if not isinstance(rec, dict):
                break
            outcome, kw = rec.get("outcome"), rec.get("keyword")
            if isinstance(kw, str):
                if keyword is not None and kw != keyword:
                    break
                keyword = kw
            if outcome == WATCH_OUTCOME:
                held += 1
            elif outcome not in WATCH_NEUTRAL:
                break
        if held:
            out.append({"symbol": sym, "days_held": int(held)})
    out.sort(key=lambda x: (-x["days_held"], x["symbol"]))
    return out[:WATCH_MAX_COINS]
