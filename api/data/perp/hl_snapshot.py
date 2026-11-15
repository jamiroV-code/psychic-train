"""Hyperliquid `metaAndAssetCtxs` snapshot adapter (RFC-001 Stage 2).

Forward-only: the endpoint is a rolling "now" snapshot. Each context is stored
verbatim (AD-2). `prevDayPx`, `dayNtlVlm` and `dayBaseVlm` are rolling 24-hour
values and are never treated as closed UTC days. Shape is pinned by the Stage 0
report (VA-55): a top-level list of 2, `[0]` holds `universe`, `[1]` the contexts
by position; coins are found by `universe[i].name`, never by a fixed index.
"""
from __future__ import annotations

import datetime as dt
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from api.data.perp import textlog
from api.data.perp.paths import hl_snapshot_path

INFO_URL = "https://api.hyperliquid.xyz/info"
COINS = ("BTC", "ETH")
# Bounded retry schedule within the 180-second hard deadline.
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 1.0
TIMEOUT_SECONDS = 10.0
RUN_DEADLINE_SECONDS = 180.0
EXPECTED_KEYS = (
    "funding", "openInterest", "prevDayPx", "dayNtlVlm", "premium",
    "oraclePx", "markPx", "midPx", "impactPxs", "dayBaseVlm",
)
_UTC = dt.timezone.utc
_STAMP = "%Y-%m-%dT%H:%M:%SZ"


@dataclass
class SnapshotResult:
    status: str  # "ok" | "unavailable"
    collected_at_utc: str
    coins: dict[str, dict] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    server_date: str | None = None


def _as_utc(now: dt.datetime | None) -> dt.datetime:
    if now is None:
        return dt.datetime.now(_UTC)
    if now.tzinfo is None:
        return now.replace(tzinfo=_UTC)
    return now.astimezone(_UTC)


def _parse_body(body: object) -> tuple[dict[str, dict], list[str]] | None:
    """Return (coins, problems), or None when the shape is not the pinned one."""
    if not isinstance(body, list) or len(body) != 2:
        return None
    meta, contexts = body
    if not isinstance(meta, dict) or not isinstance(meta.get("universe"), list):
        return None
    if not isinstance(contexts, list) or len(contexts) != len(meta["universe"]):
        return None
    names = [u.get("name") if isinstance(u, dict) else None for u in meta["universe"]]
    coins: dict[str, dict] = {}
    problems: list[str] = []
    for coin in COINS:
        if coin not in names:
            problems.append(f"coin-missing:{coin}")
            continue
        ctx = contexts[names.index(coin)]
        if not isinstance(ctx, dict):
            return None
        for key in EXPECTED_KEYS:
            if key not in ctx:
                problems.append(f"key-absent:{coin}:{key}")
        for key, value in ctx.items():
            if value is None:
                problems.append(f"null-value:{coin}:{key}")  # preserved as null and flagged (exit 2 via the run)
        coins[coin] = dict(ctx)  # verbatim: strings stay strings, null stays null
    return coins, problems


def _post_with_retry(client: httpx.Client, started: float) -> tuple[httpx.Response | None, list[str]]:
    """Retry 429/5xx/transport errors until MAX_RETRIES or the run deadline.

    Attempt problems are returned only when every attempt failed; a recovered
    fetch is clean.
    """
    problems: list[str] = []
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.post(INFO_URL, json={"type": "metaAndAssetCtxs"}, timeout=TIMEOUT_SECONDS)
        except httpx.TransportError:
            problems.append("transport-error")
        except httpx.HTTPError:
            problems.append("http-client-error")
        else:
            if resp.status_code == 429 or 500 <= resp.status_code <= 599:
                problems.append(f"http-{resp.status_code}")
            else:
                return resp, []
        if attempt == MAX_RETRIES - 1 or time.monotonic() - started >= RUN_DEADLINE_SECONDS:
            return None, problems
        time.sleep(min(BACKOFF_BASE_SECONDS * (2**attempt),
                       max(0.0, RUN_DEADLINE_SECONDS - (time.monotonic() - started))))
    return None, problems


def fetch_snapshot(client: httpx.Client | None = None, now: dt.datetime | None = None) -> SnapshotResult:
    """One fetch. Never raises. Nothing is invented: failures return `unavailable`."""
    started = time.monotonic()
    own = client is None
    if client is None:
        client = httpx.Client()
    try:
        resp, problems = _post_with_retry(client, started)
        # Stamp at response receipt, not job start; `now` is a test seam only.
        stamp = _as_utc(now).strftime(_STAMP) if now is not None else dt.datetime.now(_UTC).strftime(_STAMP)
        if resp is None:
            return SnapshotResult("unavailable", stamp, problems=problems or ["no-response"])
        server_date = resp.headers.get("Date")
        if resp.status_code != 200:
            problems.append(f"http-{resp.status_code}")
            return SnapshotResult("unavailable", stamp, problems=problems, server_date=server_date)
        try:
            body = resp.json()
        except ValueError:
            problems.append("bad-json")
            return SnapshotResult("unavailable", stamp, problems=problems, server_date=server_date)
        parsed = _parse_body(body)
        if parsed is None:
            problems.append("shape-drift")
            return SnapshotResult("unavailable", stamp, problems=problems, server_date=server_date)
        coins, shape_problems = parsed
        problems.extend(shape_problems)
        status = "ok" if coins else "unavailable"
        return SnapshotResult(status, stamp, coins=coins, problems=problems, server_date=server_date)
    finally:
        if own:
            client.close()


def write_snapshot(result: SnapshotResult, handle: textlog.Handle,
                   problems: list[str]) -> tuple[int, dict[str, textlog.AppendResult]]:
    """Write each coin only while the run lock still carries our token.

    Appends never wait (VA-30). A coin whose directory cannot be created is recorded
    as `not-written:<COIN>` and the other coins still write. Nothing is written for
    an unavailable result.
    """
    writes: dict[str, textlog.AppendResult] = {}
    if result.status != "ok":
        return 0, writes
    month = result.collected_at_utc[:7]
    written = 0
    for coin, context in result.coins.items():
        if not handle.owns():
            problems.append("run-lock-token-lost")
            break
        path = hl_snapshot_path(coin, month)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            problems.append(f"not-written:{coin}")
            continue
        line = json.dumps({"collected_at_utc": result.collected_at_utc, "coin": coin,
                           "context": context,
                           **({"server_date": result.server_date} if result.server_date is not None else {})},
                          separators=(",", ":"))
        result_write = textlog.append_line(path, line, wait_seconds=0.0)
        writes[coin] = result_write
        if result_write.written:
            written += 1
        else:
            problems.append(f"not-written:{coin}")
        problems.extend(result_write.problems)
    return written, writes


def _parse_stamp(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, _STAMP).replace(tzinfo=_UTC)


def _months(start: dt.date, end: dt.date) -> list[str]:
    months: list[str] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return months


def read_snapshots(coin: str, start: dt.date, end: dt.date) -> list[dict]:
    """Rows with `start <= collected_at < end` (UTC midnights), in time order."""
    lo = dt.datetime.combine(start, dt.time(0), tzinfo=_UTC)
    hi = dt.datetime.combine(end, dt.time(0), tzinfo=_UTC)
    rows: list[dict] = []
    seen_lines: set[str] = set()
    for month in _months(start, end):
        path = hl_snapshot_path(coin, month)
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8", errors="replace").split("\n"):
            if not raw:
                continue
            try:
                row = json.loads(raw)
                when = _parse_stamp(row["collected_at_utc"])
                if raw in seen_lines:
                    continue
                seen_lines.add(raw)
            except (ValueError, KeyError, TypeError):
                continue  # torn or foreign line: skipped, the reader never raises
            if lo <= when < hi:
                rows.append(row)
    rows.sort(key=lambda r: r["collected_at_utc"])
    return rows


def _close_window(day: dt.date) -> tuple[dt.datetime, dt.datetime]:
    """AD-2 close window: open on the left at 23:00 UTC, closed on the right at next 00:00."""
    hi = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(0), tzinfo=_UTC)
    return hi - dt.timedelta(hours=1), hi


def close_value(coin: str, day: dt.date, field_name: str) -> object | None:
    """Latest snapshot inside the close window of `day`, or None (gap or null field)."""
    lo, hi = _close_window(day)
    rows = read_snapshots(coin, day, day + dt.timedelta(days=2))
    inside = [r for r in rows if lo < _parse_stamp(r["collected_at_utc"]) <= hi]
    if not inside:
        return None
    return inside[-1]["context"].get(field_name)


def coverage(coin: str, start: dt.date, end: dt.date) -> list[tuple[dt.date, bool]]:
    """Per UTC day in [start, end]: True when a close-window snapshot exists."""
    rows = read_snapshots(coin, start, end + dt.timedelta(days=2))
    stamps = [_parse_stamp(r["collected_at_utc"]) for r in rows]
    out: list[tuple[dt.date, bool]] = []
    day = start
    while day <= end:
        lo, hi = _close_window(day)
        out.append((day, any(lo < s <= hi for s in stamps)))
        day += dt.timedelta(days=1)
    return out
