"""Contract D (collector-identity-pool finish plan): durable nonsecret daily facts.

Append-only event files `<cache>/attention/_facts/events_<day>.jsonl`, one per UTC event day. An event is keyed by
the UTC day of its own timestamp and a file is never rewritten, so the first charge of a new day cannot overwrite
yesterday's figures (the pool's `reads_used` reset does; facts are the durable source). Every kind and field is
allowlisted, strings are short identifier-like tokens and no field name may look like a secret, so no cookie,
token or credential can be written. The first event of each day, and any later event whose optional-switch values
differ from the last recorded ones, is preceded by a `switch_provenance` event holding the effective switch values.

Appends are serialized by a thread lock plus an OS lock on the adjacent `<file>.lock`, and each append is one
`O_APPEND` write followed by fsync; a torn tail (crash mid-write) is skipped by the reader and the next append starts
on a fresh line. Files are bounded by `MAX_FILE_BYTES`: an append that would exceed it is refused (returns False).
`prune` deletes whole days older than the retention. `write_universe_snapshot` records the daily report's universe
once per source per UTC day. Pure file I/O; no network; no call sites here.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import threading
import time
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from api.data import cache

SCHEMA_VERSION = 1
FACTS_DIR = "_facts"
MAX_FILE_BYTES = 8 * 1024 * 1024
MIN_RETENTION_DAYS = 30
LOCK_TIMEOUT_S = 5.0

_TOKEN_RE = re.compile(r"[A-Za-z0-9_.:\-]{1,64}")
_KEY_RE = re.compile(r"[a-z][a-z0-9_]{0,63}")
_SYMBOL_RE = re.compile(r"[A-Z0-9]{1,20}")
_FILE_RE = re.compile(r"events_(\d{4}-\d{2}-\d{2})\.jsonl")
_SECRET_PARTS = ("cookie", "token", "ct0", "password", "passwd", "secret", "auth", "credential", "bearer",
                 "session_id", "api_key", "apikey", "private_key")

_STR, _INT, _OPT_STR = "str", "int", "opt_str"
# kind -> field -> type, or a frozenset of allowed values.
KINDS: dict[str, dict[str, object]] = {
    "unit_completed": {"source": _STR, "account": _STR, "coin": _STR, "coin_day": _STR, "reads": _INT,
                       "pages": _INT, "raw_results": _INT},
    "handoff": {"source": _STR, "from_account": _STR, "to_account": _OPT_STR, "reason": _STR},
    "account_state": {"source": _STR, "account": _STR,
                      "state": frozenset({"loss", "pause", "lock", "quarantine", "resume"}), "reason": _STR},
    "challenge": {"source": _STR, "account": _STR, "class": frozenset({"challenge", "login_required"})},
    "cooldown": {"source": _STR, "account": _STR, "action": frozenset({"set", "cleared"}), "until": _OPT_STR},
    "session_check": {"source": _STR, "account": _STR, "result_class": _STR, "cookie_age_class": _STR},
    "queryid_state": {"operation": _STR, "from_state": _OPT_STR, "to_state": _STR, "reason": _STR},
    "mixed_call": {"source": _STR, "account": _STR, "target": _STR, "reads": _INT},
    "poll_result": {"source": _STR, "method": _STR, "account": _OPT_STR, "navigations": _INT, "lanes": _INT,
                    "stop_reason": _STR},
    "request_counter": {"source": _STR, "method": _STR, "requests": _INT},
}
# Written only by this module.
INTERNAL_KINDS = frozenset({"switch_provenance", "universe_snapshot"})
_OPTIONAL_FIELDS = {"until"}  # may be omitted entirely; other _OPT_STR fields must be present (value may be None)

_thread_lock = threading.Lock()


def facts_dir() -> Path:
    return cache.CACHE_ROOT / "attention" / FACTS_DIR


def events_path(day: date) -> Path:
    return facts_dir() / f"events_{day.isoformat()}.jsonl"


def _utc(now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ValueError("now must be an aware UTC datetime")
    return now.astimezone(timezone.utc)


def _token(value: object, what: str) -> str:
    if not isinstance(value, str) or not _TOKEN_RE.fullmatch(value):
        raise ValueError(f"bad {what}")
    return value


def _check_key(key: object) -> str:
    if not isinstance(key, str) or not _KEY_RE.fullmatch(key) or any(p in key for p in _SECRET_PARTS):
        raise ValueError("bad or secret-like field name")
    return key


def _validate_event(event: Mapping[str, object]) -> dict[str, object]:
    kind = event.get("kind")
    if kind not in KINDS:
        raise ValueError("event kind not allowlisted")
    spec = KINDS[kind]
    out: dict[str, object] = {"kind": kind}
    for key, value in event.items():
        if key == "kind":
            continue
        if key not in spec:  # the allowlist is the field-name guard (`cookie_age_class` is a class, not a cookie)
            raise ValueError(f"field {key} not allowed for {kind}")
        rule = spec[key]
        if isinstance(rule, frozenset):
            if value not in rule:
                raise ValueError(f"bad {key}")
        elif rule == _INT:
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"bad {key}")
        elif rule == _OPT_STR and value is None:
            pass
        else:
            _token(value, key)
        out[key] = value
    missing = set(spec) - set(out) - _OPTIONAL_FIELDS
    if missing:
        raise ValueError(f"missing fields {sorted(missing)}")
    return out


def _validate_switches(switches: Mapping[str, object]) -> dict[str, object]:
    def scalar(v: object) -> object:
        if v is None or isinstance(v, (bool, int, float)):
            return v
        return _token(v, "switch value")

    def value(v: object, depth: int) -> object:
        if isinstance(v, (list, tuple)):
            if depth > 1:
                raise ValueError("switch value too deep")
            return [value(x, depth + 1) for x in v]
        if isinstance(v, Mapping):
            if depth > 0:
                raise ValueError("switch value too deep")
            return {_check_key(k): value(x, depth + 1) for k, x in v.items()}
        return scalar(v)

    if not isinstance(switches, Mapping):
        raise ValueError("switches must be a mapping")
    return {_check_key(k): value(v, 0) for k, v in sorted(switches.items())}


def _line(record: dict[str, object]) -> bytes:
    return (json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


def _parse(data: bytes) -> list[dict]:
    events = []
    for raw in data.split(b"\n"):
        if not raw.strip():
            continue
        try:
            ev = json.loads(raw)
        except ValueError:
            continue  # torn tail from an interrupted append
        if isinstance(ev, dict) and isinstance(ev.get("kind"), str):
            events.append(ev)
    return events


@contextlib.contextmanager
def _locked(path: Path):
    """Thread lock plus an exclusive OS lock on the adjacent `<path>.lock` (bounded wait)."""
    lock_path = Path(str(path) + ".lock")
    with _thread_lock:
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        stream = os.fdopen(fd, "r+b", buffering=0)
        acquired = False
        try:
            if os.fstat(stream.fileno()).st_size == 0:
                stream.write(b"0")
            deadline = time.monotonic() + LOCK_TIMEOUT_S
            while not acquired:
                try:
                    stream.seek(0)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("facts lock") from None
                    time.sleep(0.02)
            yield
        finally:
            if acquired:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            stream.close()


def _append_records(day: date, records: list[dict[str, object]], switches: dict[str, object],
                    once_key: tuple[str, str] | None = None) -> bool:
    path = events_path(day)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _locked(path):
        existing = path.read_bytes() if path.exists() else b""
        events = _parse(existing)
        if once_key is not None and any(e.get("kind") == once_key[0] and e.get("source") == once_key[1]
                                        for e in events):
            return False
        last = next((e.get("switches") for e in reversed(events) if e.get("kind") == "switch_provenance"), None)
        payload = b"" if not existing or existing.endswith(b"\n") else b"\n"
        if last != switches:
            payload += _line({"kind": "switch_provenance", "ts": records[0]["ts"], "v": SCHEMA_VERSION,
                              "switches": switches})
        payload += b"".join(_line(r) for r in records)
        if len(existing) + len(payload) > MAX_FILE_BYTES:
            return False
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o600)
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
    return True


def _stamp(now: datetime) -> str:
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def append(event: Mapping[str, object], *, now: datetime, switches: Mapping[str, object]) -> bool:
    """Append one allowlisted event to its UTC event day's file; False when the day's size bound is reached."""
    now = _utc(now)
    record = _validate_event(event)
    record.update(ts=_stamp(now), v=SCHEMA_VERSION)
    return _append_records(now.date(), [record], _validate_switches(switches))


def read_events(day: date) -> list[dict]:
    path = events_path(day)
    return _parse(path.read_bytes()) if path.exists() else []


def prune(*, now: datetime, retention_days: int) -> int:
    """Delete event files whose day is older than `retention_days` before today's UTC day; returns files removed."""
    if isinstance(retention_days, bool) or not isinstance(retention_days, int) \
            or retention_days < MIN_RETENTION_DAYS:
        raise ValueError("retention_days must be an int >= 30")
    cutoff = _utc(now).date() - timedelta(days=retention_days)
    directory = facts_dir()
    if not directory.is_dir():
        return 0
    removed = 0
    for path in directory.iterdir():
        m = _FILE_RE.fullmatch(path.name)
        if not m:
            continue
        try:
            day = date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if day < cutoff:
            with _locked(path):
                path.unlink(missing_ok=True)
            Path(str(path) + ".lock").unlink(missing_ok=True)
            removed += 1
    return removed


def _symbols(values: Iterable[object], what: str) -> list[str]:
    out = list(values)
    if any(not isinstance(s, str) or not _SYMBOL_RE.fullmatch(s) for s in out) or len(set(out)) != len(out):
        raise ValueError(f"bad {what}")
    return out


def write_universe_snapshot(day: date, source: str, *, eligible_symbols: Iterable[str],
                            ambiguous_symbols: Iterable[str], method_order: Iterable[str], now: datetime,
                            switches: Mapping[str, object]) -> bool:
    """Record the day's universe for `source` once; False when already recorded (or the size bound is reached)."""
    now = _utc(now)
    if day != now.date():
        raise ValueError("snapshot day must be the current UTC day")
    methods = list(method_order)
    if any(not isinstance(m, str) or not _KEY_RE.fullmatch(m) for m in methods) or len(set(methods)) != len(methods):
        raise ValueError("bad method_order")
    record = {"kind": "universe_snapshot", "ts": _stamp(now), "v": SCHEMA_VERSION, "day": day.isoformat(),
              "source": _check_key(source), "eligible_symbols": _symbols(eligible_symbols, "eligible_symbols"),
              "ambiguous_symbols": _symbols(ambiguous_symbols, "ambiguous_symbols"), "method_order": methods}
    return _append_records(day, [record], _validate_switches(switches), once_key=("universe_snapshot", source))


_SNAPSHOT_FIELDS = ("day", "source", "eligible_symbols", "ambiguous_symbols", "method_order")


def read_universe_snapshot(day: date, source: str) -> dict | None:
    """The day's universe snapshot for `source`, or None (the report then says "no data", never recomputes)."""
    for ev in read_events(day):
        if ev.get("kind") == "universe_snapshot" and ev.get("source") == source:
            return {k: ev.get(k) for k in _SNAPSHOT_FIELDS}
    return None


def summarize(events: Iterable[Mapping[str, object]]) -> dict:
    """Pure per-day summary: kind counts, per source/account unit totals, request counters, reason histogram,
    switch provenance in order and universe snapshots per source."""
    kinds: dict[str, int] = {}
    accounts: dict[str, dict[str, dict[str, int]]] = {}
    requests: dict[str, dict[str, int]] = {}
    reasons: dict[str, int] = {}
    switches: list[dict] = []
    universe: dict[str, dict] = {}
    for ev in events:
        kind = ev.get("kind")
        if not isinstance(kind, str):
            continue
        kinds[kind] = kinds.get(kind, 0) + 1
        if kind == "unit_completed":
            acct = accounts.setdefault(str(ev.get("source")), {}).setdefault(
                str(ev.get("account")), {"units": 0, "reads": 0, "pages": 0, "raw_results": 0})
            acct["units"] += 1
            for f in ("reads", "pages", "raw_results"):
                acct[f] += int(ev.get(f) or 0)
        elif kind == "request_counter":
            per = requests.setdefault(str(ev.get("source")), {})
            per[str(ev.get("method"))] = per.get(str(ev.get("method")), 0) + int(ev.get("requests") or 0)
        elif kind == "account_state":
            reason = str(ev.get("reason"))
            reasons[reason] = reasons.get(reason, 0) + 1
        elif kind == "switch_provenance":
            switches.append(dict(ev.get("switches") or {}))
        elif kind == "universe_snapshot":
            universe.setdefault(str(ev.get("source")), {k: ev.get(k) for k in _SNAPSHOT_FIELDS})
    return {"kinds": kinds, "accounts": accounts, "requests": requests, "reasons": reasons, "switches": switches,
            "universe": universe}
