"""Daily FROZEN snapshot of the Discovery signal (T105, W9). Store only; no network.

Why: a later calibration of source weights must be judged on what the signal said on each day, never on
recomputed or revised data (backtesting traps in the weighted-signal SPEC). `take_snapshot(today)` runs the live
scorer (`discovery.build_discovery`, not a copy of its maths) for windows 7, 30 and 90 for the latest completed
UTC day (`today - 1`) and writes ONE immutable record per (date, window) to
`<cache>/attention/signals/<date>_w<window>.json`. The workflow's `git add -f api/data/cache/attention/` already
commits that directory; it is not a source (no parquet, not in the registry, not a Discovery series).

A record holds one row per coin (date, window, symbol, category ids, score = raw weighted change, covered_weight,
rising_weight, trigger, per-source {source, change, as_of}), the per-category summary, `categories_as_of`, and the
FULL config used that day plus its `config_hash`, so a later weights change never rewrites history.
First write wins: a re-run never overwrites. If a record exists and the current config hashes differently
(a weights change mid-day) the result status is `config-changed` and the caller logs it; nothing is rewritten.
A day with no usable result (`no-data`) is not written, so a later run the same day can still freeze it.

Lookahead: every series is read with `today` as the exclusive cut (`registry.read_series`), so day D uses points
dated on or before D. The universe and categories snapshots are the latest stored at run time (as for the live
view); `categories_as_of` records which one.

Narratives (U1): new records store narrative ids in `category_ids`, the marker `membership_definition` and the
narratives file's sha256 prefix `narratives_sha`, which is folded into the stored hash (a membership edit is a
config change). Records written before U1 hold CoinGecko category ids; `read_snapshots` maps them to narrative ids
through the id map ON READ (`narrative_ids`, unmapped ones in `retired_ids`) and never rewrites a file.

Weights versions (T130): new records carry `weights_version`, the version scoring that day
(`discovery.weights_for_day`). Records written before carry none and read back as version 1 (in memory only).
`config` is the WHOLE config of the run, so its top-level `source_weights` is the current version even on a day an
older version scored; new records (T150) also store `weights`, the version actually used, to say so explicitly.

LIMITATION: the snapshot is taken at the end of the `refresh` job, so it cannot include sources fed later the same
day by `refresh-extra` (Binance, Hyperliquid, Trends, Reddit), nor the category snapshot refreshed after the
default run (the previous day's categories are used). Those sources are therefore missing or one day lagged in
the frozen record. Fix (follow-up, not here): an in-API worker or a `.github/` step that snapshots after
refresh-extra.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

from api.analytics.attention import discovery, narratives
from api.data import cache

WINDOWS = (7, 30, 90)


def snapshot_dir() -> Path:
    return cache.CACHE_ROOT / "attention" / "signals"


def _path(day: date, window: int) -> Path:
    return snapshot_dir() / f"{day.isoformat()}_w{window}.json"


def config_hash(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def snapshot_hash(cfg: dict, narratives_sha: str) -> str:
    """The stored `config_hash`: the config plus the narratives file it was scored with."""
    return config_hash({"config": cfg, "narratives_sha": narratives_sha})


def _record(res, day: date, window: int, cfg: dict, h: str, nsha: str) -> dict:
    used = discovery.weights_for_day(cfg, day)
    coins: dict[str, dict] = {}
    for cat in res.categories:
        for c in cat.coins:
            row = coins.setdefault(c.symbol, {
                "date": day.isoformat(), "window": window, "symbol": c.symbol, "category_ids": [],
                "score": c.raw_change, "covered_weight": c.covered_weight, "rising_weight": c.rising_weight,
                "trigger": c.trigger,
                "sources": [{"source": s.source, "change": s.change, "as_of": s.as_of} for s in c.sources]})
            row["category_ids"].append(cat.id)
    for row in coins.values():
        row["category_ids"].sort()
    return {"date": day.isoformat(), "window": window, "categories_as_of": res.categories_as_of,
            "config_hash": h, "config": cfg, "membership_definition": narratives.DEFINITION, "narratives_sha": nsha,
            "weights_version": used["weights_version"], "weights": used,
            "categories": [{"id": c.id, "score": c.score, "median": c.median, "coins_used": c.coins_used,
                            "gaining_count": c.gaining_count} for c in res.categories],
            "rows": [coins[s] for s in sorted(coins)]}


def _write_new(path: Path, rec: dict) -> bool:
    """Atomic create-if-absent: False when the record already exists (first write wins)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".part")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(rec, f, sort_keys=True)
        try:
            os.link(tmp, path)
        except FileExistsError:
            return False
        return True
    finally:
        os.unlink(tmp)


def _stored_hash(path: Path) -> str | None:
    try:
        return json.loads(path.read_text()).get("config_hash")
    except (OSError, ValueError, AttributeError):
        return None


def take_snapshot(today: date) -> list[dict]:
    """One result per window: {window, date, status, ...}; status is written | exists | config-changed |
    unreadable | no-data. Never overwrites."""
    cfg = discovery.load_config()
    nsha = narratives.file_sha()
    h = snapshot_hash(cfg, nsha)
    day = today - timedelta(days=1)
    out = []
    for window in WINDOWS:
        path = _path(day, window)
        base = {"window": window, "date": day.isoformat(), "current_hash": h}
        if path.exists():
            stored = _stored_hash(path)
            status = "unreadable" if stored is None else ("exists" if stored == h else "config-changed")
            out.append({**base, "status": status, "stored_hash": stored})
            continue
        res = discovery.build_discovery(window, today=today)
        if res.status != "ok":
            out.append({**base, "status": "no-data", "reason": res.reason})
            continue
        written = _write_new(path, _record(res, day, window, cfg, h, nsha))
        out.append({**base, "status": "written" if written else "exists", "stored_hash": h})
    return out


def _with_narrative_ids(rec: dict, id_map: dict[str, dict]) -> list[dict]:
    """Rows of one record plus `narrative_ids` and `retired_ids` (in memory only; the file is never rewritten)."""
    old = rec.get("membership_definition") is None
    wv = rec.get("weights_version", 1)
    out = []
    for r in rec["rows"]:
        ids = r.get("category_ids", [])
        if not old:
            out.append({**r, "narrative_ids": list(ids), "retired_ids": [], "weights_version": wv})
            continue
        mapped = {c: (id_map.get(c) or {}).get("narrative") for c in ids}
        out.append({**r, "weights_version": wv, "narrative_ids": sorted({n for n in mapped.values() if n}),
                    "retired_ids": sorted(c for c, n in mapped.items() if not n)})
    return out


def read_snapshots(start: date, end: date, window: int | None = None) -> list[dict]:
    """Flat coin rows for days start..end inclusive (optionally one window), oldest first. Unreadable records skipped.
    Each row carries `narrative_ids` (old category ids mapped through the id map) next to the raw `category_ids`."""
    id_map = narratives.load_id_map()
    rows = []
    for p in sorted(snapshot_dir().glob("*_w*.json")):
        try:
            d, w = p.stem.split("_w")
            day, win = date.fromisoformat(d), int(w)
        except ValueError:
            continue
        if not start <= day <= end or (window is not None and win != window):
            continue
        try:
            rows.extend(_with_narrative_ids(json.loads(p.read_text()), id_map))
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
    return rows


def summarize(rows: list[dict]) -> dict:
    """Days covered, distinct coins, and triggered coins per day (for later calibration)."""
    per_day: dict[str, int] = {}
    for r in rows:
        per_day[r["date"]] = per_day.get(r["date"], 0) + bool(r["trigger"])
    return {"days": len(per_day), "coins": len({r["symbol"] for r in rows}),
            "triggers_per_day": dict(sorted(per_day.items()))}
