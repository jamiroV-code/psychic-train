"""SPEC AC45, AC54, Annex A.1b point 4: the X raw page archive, retention, re-parse and the X evidence rows.

Every raw page the reader returns is stored gzipped under the git-ignored cache
(`<cache>/attention/xsearch_raw/<date>/<SYMBOL>/r<run>_a<attempt>_p<page>.json.gz`) with `collected_at`, the parser
and reader versions, the timeline entry ids and the rate-limit numbers. Header values other than the two
rate-limit numbers are never stored, keys that could hold a cookie or token are removed from the body, and the
account's real screen name and id are replaced by its label anywhere in the body (whole tokens, case-folded), so
no real account name is written. The archive keeps entries the parser dropped (they exist nowhere else) and the
entries' own timestamps when the reader exposes them.

A unit that produced a value is marked complete (`_complete.json`: run, attempt, account label, attempts, restarts,
fallback events, setup overhead). `reparse` rebuilds the X evidence row of the first completed run from its raw pages
only, so the same parser version gives an identical row. X evidence rows live at
`<cache>/attention/xsearch_web/_xmeta/<SYMBOL>.json`, one per (date, parser version), first write wins: a new parser
version adds a row and never overwrites one. The re-parse applies the same cursor rule as the live run
(`x_window.cursor_end`: a repeated id or an empty page after a full one is a stall) and the canary evidence the
unit recorded (`canary_ok`, never assumed). Pure file I/O; no network.
"""
from __future__ import annotations

import gzip
import json
import os
import re
from collections.abc import Callable, Mapping
from datetime import date, datetime, timezone
from pathlib import Path

from api.data import cache
from api.data.attention import x_density, x_filters, x_window
from api.data.attention.web_evidence import SYMBOL_RE
from api.data.attention.web_queries import CollectorConfig

RAW_DIR = "xsearch_raw"
RATE_HEADERS = {"x-rate-limit-remaining": "rate_limit_remaining", "x-rate-limit-limit": "rate_limit_limit"}
# Body keys never archived (case-folded); any key holding "cookie" is dropped as well.
SCRUB_KEYS = frozenset({"auth_token", "ct0", "authorization", "x-csrf-token", "x-guest-token", "headers", "password",
                        "email", "set-cookie"})
_PAGE_RE = re.compile(r"r([0-9]{1,12})_a([0-9]{1,2})_p([0-9]{2})\.json\.gz")
COMPLETE = "_complete.json"


def _symbol(symbol: str) -> str:
    sym = symbol.upper()
    if not SYMBOL_RE.fullmatch(sym):
        raise ValueError("bad symbol")
    return sym


def raw_root() -> Path:
    return cache.CACHE_ROOT / "attention" / RAW_DIR


def raw_dir(day: date, symbol: str) -> Path:
    return raw_root() / day.isoformat() / _symbol(symbol)


def _name_pattern(names: Mapping[str, str]) -> re.Pattern | None:
    keys = sorted((str(k) for k in names if str(k)), key=len, reverse=True)
    if not keys:
        return None
    return re.compile(r"(?<![0-9A-Za-z_])(" + "|".join(re.escape(k) for k in keys) + r")(?![0-9A-Za-z_])",
                      re.IGNORECASE)


def scrub(value, names: Mapping[str, str] | None = None):
    """A copy of a JSON body without keys that could carry a cookie, token or header, and with every whole-token
    occurrence of a configured account name or id (`names`: real value to label) replaced by the label."""
    folded = {str(k).casefold(): v for k, v in (names or {}).items()}
    pattern = _name_pattern(names or {})

    def walk(v):
        if isinstance(v, dict):
            return {k: walk(x) for k, x in v.items()
                    if not (str(k).casefold() in SCRUB_KEYS or "cookie" in str(k).casefold())}
        if isinstance(v, list):
            return [walk(x) for x in v]
        if pattern is None or isinstance(v, bool) or v is None:
            return v
        if isinstance(v, int):
            return folded.get(str(v), v)
        if isinstance(v, str):
            return pattern.sub(lambda m: folded[m.group(1).casefold()], v)
        return v

    return walk(value)


def _rate_numbers(headers: Mapping) -> dict:
    out = dict.fromkeys(RATE_HEADERS.values())
    for k, v in (headers or {}).items():
        name = RATE_HEADERS.get(str(k).casefold())
        if name is not None:
            try:
                out[name] = int(str(v).strip())
            except ValueError:
                out[name] = None
    return out


def _atomic_bytes(data: bytes, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def run_id(collected_at: datetime) -> int:
    if collected_at.tzinfo is None:
        raise ValueError("collected_at must be timezone-aware")
    return int(collected_at.timestamp())


def write_page(symbol: str, day: date, *, attempt: int, page: int, body: dict, entry_ids, retries: int,
               headers: Mapping, collected_at: datetime, parser_version: str, reader_version: str,
               reader_commit: str | None = None, backend: str = "default",
               scrub_names: Mapping[str, str] | None = None, entry_times=()) -> Path:
    if not (isinstance(attempt, int) and 1 <= attempt <= 99 and isinstance(page, int) and 0 <= page <= 99):
        raise ValueError("bad attempt or page")
    ids = [str(e) for e in entry_ids]
    rec = {"symbol": _symbol(symbol), "day": day.isoformat(), "attempt": attempt, "page": page,
           "collected_at": collected_at.astimezone(timezone.utc).isoformat(), "parser_version": parser_version,
           "reader_version": reader_version, "reader_commit": reader_commit, "backend": backend,
           "entries": len(ids), "entry_ids": ids, "retries": int(retries), **_rate_numbers(headers),
           "entry_times": sorted(t.astimezone(timezone.utc).isoformat() for t in entry_times),
           "body": scrub(body, scrub_names)}
    path = raw_dir(day, symbol) / f"r{run_id(collected_at)}_a{attempt}_p{page:02d}.json.gz"
    _atomic_bytes(gzip.compress(json.dumps(rec, sort_keys=True).encode("utf-8"), mtime=0), path)
    return path


def _page_files(symbol: str, day: date) -> list[tuple[int, int, int, Path]]:
    d = raw_dir(day, symbol)
    if not d.exists():
        return []
    out = []
    for p in d.iterdir():
        m = _PAGE_RE.fullmatch(p.name)
        if m:
            out.append((int(m.group(1)), int(m.group(2)), int(m.group(3)), p))
    return sorted(out)


def read_pages(symbol: str, day: date, *, run: int | None = None, attempt: int | None = None) -> list[dict]:
    return [json.loads(gzip.decompress(p.read_bytes()).decode("utf-8")) for r, a, _pg, p in _page_files(symbol, day)
            if (run is None or r == run) and (attempt is None or a == attempt)]


def mark_complete(symbol: str, day: date, meta: dict, *, run: int | None = None) -> None:
    """Record that the pages of (run, attempt) produced the unit's value; `run` None means the newest run."""
    files = _page_files(symbol, day)
    if run is None:
        run = max((r for r, a, _pg, _p in files if a == meta["attempt"]), default=None)
    if run is None:
        raise ValueError("no raw pages for that attempt")
    path = raw_dir(day, symbol) / COMPLETE
    done = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    done.append({**meta, "run": run})
    cache._atomic_write_json(done, path)


def prune(*, now: datetime, retention_days: int) -> int:
    """Delete date folders older than `retention_days`; a folder that is not a date is never touched."""
    if not isinstance(retention_days, int) or isinstance(retention_days, bool) or retention_days < 1:
        raise ValueError("retention must be at least one day")
    root, today, removed = raw_root(), now.astimezone(timezone.utc).date(), 0
    if not root.exists():
        return 0
    for d in root.iterdir():
        try:
            day = date.fromisoformat(d.name)
        except ValueError:
            continue
        if d.is_dir() and (today - day).days > retention_days:
            for f in sorted(d.rglob("*"), reverse=True):
                f.unlink() if f.is_file() else f.rmdir()
            d.rmdir()
            removed += 1
    return removed


def reparse(symbol: str, day: date, *, parse: Callable[[dict], list[x_filters.Tweet]], coin: x_filters.Coin,
            cfg: CollectorConfig, parser_version: str, policy: x_filters.FilterPolicy | None = None) -> dict | None:
    """The X evidence row rebuilt from the first completed run's raw pages, or None when no run completed."""
    path = raw_dir(day, symbol) / COMPLETE
    if not path.exists():
        return None
    meta = json.loads(path.read_text(encoding="utf-8"))[0]
    recs = read_pages(symbol, day, run=meta["run"], attempt=meta["attempt"])
    if not recs:
        return None
    read, seen, n_read, last, end, raw_times = [], set(), 0, None, None, []
    for rec in recs:
        end = x_window.cursor_end(rec["entry_ids"], seen=seen, last_entries=last, page_size=x_window.PAGE_ENTRIES)
        if end:
            break
        seen.update(rec["entry_ids"])
        read += parse(rec["body"])
        n_read += rec["entries"]
        last = rec["entries"]
        raw_times += [datetime.fromisoformat(t) for t in rec.get("entry_times", [])]
    oldest = x_density.oldest_read(read, min(raw_times, default=None))
    stop = x_window.stop_reason(pages=len(recs), entries_read=n_read, oldest_read=oldest, day=day,
                                sample_n=cfg.x_sample_n, page_cap=cfg.x_page_cap,
                                exhausted=end == "cursor_exhausted", stalled=end == x_window.STALLED)
    collected_at = datetime.fromisoformat(recs[0]["collected_at"])
    canary_ok = meta.get("canary_ok") is True
    s = x_density.summarize(day, read, n_read=n_read, window_start_reached=stop in x_window.COMPLETE_STOPS,
                            page_cap_hit=stop == "page_cap", canary_ok=canary_ok, coin=coin,
                            policy=policy or x_filters.FilterPolicy.from_config(cfg), n_target=cfg.x_sample_n,
                            n_min=cfg.x_sample_min, now=collected_at, cursor_exhausted=stop == "cursor_exhausted",
                            cursor_stalled=stop == x_window.STALLED, raw_oldest=min(raw_times, default=None))
    r, last = s.result, recs[-1]
    return {
        "date": day.isoformat(), "value": None if r is None else r.value, "n": None if r is None else r.n,
        "span_hours": None if r is None else r.span_hours, "capped": None if r is None else r.capped,
        "pagecap": None if r is None else r.pagecap, "stop": stop, "missing_reason": s.missing_reason, "n_read": s.n_read, "n_counted": s.n_counted,
        "exclusions": s.exclusions, "unique_authors": s.unique_authors, "top_author_share": s.top_author_share,
        "engagement": s.engagement, "median_views": s.median_views, "read_age_hours": s.read_age_hours,
        "pages": sum(1 + rec["retries"] for rec in recs), "window_syntax": cfg.x_window_syntax,
        "parser_version": parser_version, "reader_version": last["reader_version"],
        "reader_commit": last["reader_commit"], "rate_limit_remaining": last["rate_limit_remaining"],
        "rate_limit_limit": last["rate_limit_limit"], "collected_at": recs[0]["collected_at"],
        "account": meta["label"], "attempts": meta["attempts"], "restarts": meta["restarts"],
        "backend_events": meta["backend_events"], "overhead_requests": meta["overhead_requests"],
        "canary_ok": canary_ok,
    }


def x_evidence_path(symbol: str) -> Path:
    return cache.CACHE_ROOT / "attention" / "xsearch_web" / "_xmeta" / f"{_symbol(symbol)}.json"


def read_x_rows(symbol: str) -> list[dict]:
    path = x_evidence_path(symbol)
    return json.loads(path.read_text(encoding="utf-8"))["rows"] if path.exists() else []


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cache._atomic_write_json({"rows": rows}, path)


def write_x_row(symbol: str, row: dict) -> bool:
    """Append the row unless one for the same (date, parser version) exists; True when written."""
    rows = read_x_rows(symbol)
    if any(r["date"] == row["date"] and r["parser_version"] == row["parser_version"] for r in rows):
        return False
    rows.append(row)
    rows.sort(key=lambda r: r["date"])
    _write_rows(x_evidence_path(symbol), rows)
    return True


def mark_suspect(label: str, since: datetime) -> int:
    """Flag every stored row of the account `label` with `suspect_since` (first flag kept); the rows stay."""
    root = cache.CACHE_ROOT / "attention" / "xsearch_web" / "_xmeta"
    if not root.exists():
        return 0
    flagged = 0
    for path in sorted(root.glob("*.json")):
        rows = json.loads(path.read_text(encoding="utf-8"))["rows"]
        hit = [r for r in rows if r.get("account") == label and not r.get("suspect_since")]
        for r in hit:
            r["suspect_since"] = since.astimezone(timezone.utc).isoformat()
        if hit:
            _write_rows(path, rows)
            flagged += len(hit)
    return flagged
