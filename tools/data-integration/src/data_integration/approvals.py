"""Approval records and the machine-local store (one <source>.approval.json per source)."""
from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

SOURCE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
SUFFIX = ".approval.json"
DEFAULT_TTL_DAYS = 90
MAX_TTL_DAYS = 366  # a record whose expiry is further out than this is never honoured


class StoreError(Exception):
    pass


class StoreMissing(StoreError):
    """The approvals directory does not exist."""


class RecordMissing(StoreError):
    """The directory exists but holds no record for this source."""


class StoreCorrupt(StoreError):
    """The record exists but is unreadable or malformed."""


def valid_source(name: object) -> bool:
    return isinstance(name, str) and SOURCE_RE.fullmatch(name) is not None and name not in _RESERVED


def format_utc(dt: datetime) -> str:
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("naive datetime")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(text: object) -> datetime:
    if not isinstance(text, str) or not text.endswith("Z"):
        raise ValueError("expected UTC ISO-8601 with Z")
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class ApprovalRecord:
    id: str
    source: str
    allowed_tier: int
    hosts: tuple[str, ...]
    pages: tuple[str, ...]
    rate_policy: str
    robots_checked: str
    alternatives_checked: tuple[str, ...]
    owner: str
    approved: str
    expiry: str
    revision: int = 1
    owner_statement: str = ""

    @property
    def approved_dt(self) -> datetime:
        return parse_utc(self.approved)

    @property
    def expiry_dt(self) -> datetime:
        return parse_utc(self.expiry)


def _str_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not all(isinstance(v, str) for v in value):
        raise ValueError("expected list of strings")
    return tuple(value)


def _from_dict(data: object, source: str) -> ApprovalRecord:
    if not isinstance(data, dict):
        raise ValueError("not an object")
    tier = data.get("allowed_tier")
    rev = data.get("revision")
    if type(tier) is not int or tier not in (1, 2, 3) or type(rev) is not int or rev < 1:
        raise ValueError("bad tier or revision")
    texts = {k: data.get(k) for k in ("id", "source", "rate_policy", "robots_checked", "owner", "approved", "expiry")}
    if not all(isinstance(v, str) for v in texts.values()) or texts["source"] != source:
        raise ValueError("bad fields")
    statement = data.get("owner_statement", "")
    if not isinstance(statement, str):
        raise ValueError("bad owner_statement")
    hosts, pages = _str_tuple(data.get("hosts")), _str_tuple(data.get("pages"))
    if not hosts or not pages:
        raise ValueError("no hosts or pages")
    rec = ApprovalRecord(
        allowed_tier=tier, hosts=hosts, pages=pages, alternatives_checked=_str_tuple(data.get("alternatives_checked")),
        revision=rev, owner_statement=statement, **texts,
    )
    if rec.expiry_dt > rec.approved_dt + timedelta(days=MAX_TTL_DAYS):
        raise ValueError("expiry outside the allowed window")  # loaded as StoreCorrupt
    return rec


class ApprovalStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def path_for(self, source: str) -> Path:
        if not valid_source(source):
            raise ValueError("invalid source name")
        return self.root / f"{source}{SUFFIX}"

    def list_sources(self) -> list[str]:
        if not self.root.is_dir():
            return []
        names = (p.name[: -len(SUFFIX)] for p in self.root.iterdir() if p.name.endswith(SUFFIX))
        return sorted(n for n in names if valid_source(n))

    def read(self, source: str) -> ApprovalRecord:
        path = self.path_for(source)
        if not self.root.is_dir():
            raise StoreMissing(source)
        if not path.is_file():
            raise RecordMissing(source)
        try:
            with path.open("r", encoding="utf-8") as fh:
                return _from_dict(json.load(fh), source)
        except (OSError, ValueError, TypeError):
            try:
                os.replace(path, path.with_name(path.name + ".bad"))
            except OSError:
                pass
            raise StoreCorrupt(source) from None

    def write(self, record: ApprovalRecord) -> ApprovalRecord:
        """Atomic write; revision becomes previous revision + 1 (1 for a new record)."""
        path = self.path_for(record.source)
        revision = 1
        try:
            revision = self.read(record.source).revision + 1
        except StoreError:
            pass
        data = asdict(record)
        data["revision"] = revision
        _from_dict(json.loads(json.dumps(data)), record.source)  # validate before touching disk
        self.root.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
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
        return _from_dict(data, record.source)
