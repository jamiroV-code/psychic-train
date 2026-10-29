"""SPEC Annex A.2b point 1, AC29: the Reddit item ledger. File I/O only; no network.

Every item discovered from `search.rss` (and later `new.rss` and `comments/.rss`, W8c2) is stored once by its
Reddit id (post `t3_`, comment `t1_`) with an author hash, subreddit, created time, `collected_at`, feed kind
and matched coins. A later sighting of the same id (another poll or another feed) keeps the first row and only
merges the matched coins. Rows live at `<cache>/attention/reddit_items/<created UTC day>.json` (git-ignored).

The author hash is an HMAC-SHA256 of the lower-cased username (a `/u/` or `u/` prefix dropped) under a salt
kept outside the repository (`SCREENER_REDDIT_SALT_FILE`, default `~/.screener-reddit-salt`). The username
itself is never stored, logged or kept on a row; the parser hands only the hash on.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from api.data import cache
from api.data.attention import reddit_metrics
from api.data.attention.web_queries import SUBREDDIT_RE, SYMBOL_RE

REPO_ROOT = Path(__file__).resolve().parents[3]
SALT_ENV = "SCREENER_REDDIT_SALT_FILE"
DEFAULT_SALT_NAME = ".screener-reddit-salt"  # under the owner's home folder, outside any repository
MIN_SALT_BYTES = 16
REDDIT_ID_RE = re.compile(r"t[13]_[a-z0-9]{1,16}")
FEED_KINDS = ("search", "new", "comments")
HASH_HEX = 32
_NO_AUTHOR = {"", "[deleted]", "[removed]"}


class SaltError(RuntimeError):
    """The author salt is missing, too short or inside the repository; the message never holds the path."""


def salt_path() -> Path:
    raw = os.environ.get(SALT_ENV)
    path = Path(raw).expanduser() if raw else Path.home() / DEFAULT_SALT_NAME
    resolved = path.resolve()
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        raise SaltError("the author salt must live outside the repository")
    return path


def load_salt(path: Path | None = None, *, create: bool = False) -> bytes:
    """Read the salt; with `create`, write a new random one (owner-only permissions) when none exists."""
    path = path or salt_path()
    if not path.exists():
        if not create:
            raise SaltError("author salt missing")
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as fh:
            fh.write(secrets.token_hex(32))
    salt = path.read_bytes().strip()
    if len(salt) < MIN_SALT_BYTES:
        raise SaltError("author salt too short")
    return salt


class AuthorHasher:
    def __init__(self, salt: bytes):
        if not isinstance(salt, bytes) or len(salt) < MIN_SALT_BYTES:
            raise ValueError("salt must be at least 16 bytes")
        self._salt = salt

    def __repr__(self) -> str:
        return "AuthorHasher()"

    def __call__(self, username: str | None) -> str | None:
        """The author hash, or None for a deleted or empty author."""
        name = (username or "").strip()
        for prefix in ("/u/", "u/"):
            if name.lower().startswith(prefix):
                name = name[len(prefix):]
        name = name.lower()
        if name in _NO_AUTHOR:
            return None
        return hmac.new(self._salt, name.encode("utf-8"), hashlib.sha256).hexdigest()[:HASH_HEX]


def _aware(t: datetime) -> datetime:
    if not isinstance(t, datetime) or t.tzinfo is None:
        raise ValueError("times must be timezone-aware")
    return t.astimezone(timezone.utc)


@dataclass(frozen=True)
class LedgerRow:
    id: str
    author_hash: str | None
    subreddit: str | None
    created: datetime
    collected_at: datetime
    feed_kind: str
    coins: tuple[str, ...]

    def __post_init__(self):
        if not isinstance(self.id, str) or not REDDIT_ID_RE.fullmatch(self.id):
            raise ValueError("bad Reddit id")
        if self.author_hash is not None and not re.fullmatch(rf"[0-9a-f]{{{HASH_HEX}}}", self.author_hash):
            raise ValueError("author must be a hash")
        if self.subreddit is not None and not SUBREDDIT_RE.fullmatch(self.subreddit):
            raise ValueError("bad subreddit")
        if self.feed_kind not in FEED_KINDS:
            raise ValueError("bad feed kind")
        if not all(isinstance(c, str) and SYMBOL_RE.fullmatch(c) for c in self.coins):
            raise ValueError("bad coin symbol")
        object.__setattr__(self, "created", _aware(self.created))
        object.__setattr__(self, "collected_at", _aware(self.collected_at))
        object.__setattr__(self, "coins", tuple(sorted(set(self.coins))))

    @property
    def kind(self) -> str:
        return self.id[:2]

    def to_json(self) -> dict:
        return {"id": self.id, "kind": self.kind, "author_hash": self.author_hash, "subreddit": self.subreddit,
                "created": self.created.isoformat(), "collected_at": self.collected_at.isoformat(),
                "feed_kind": self.feed_kind, "coins": list(self.coins)}

    @classmethod
    def from_json(cls, d: dict) -> LedgerRow:
        return cls(id=d["id"], author_hash=d["author_hash"], subreddit=d["subreddit"],
                   created=datetime.fromisoformat(d["created"]), collected_at=datetime.fromisoformat(d["collected_at"]),
                   feed_kind=d["feed_kind"], coins=tuple(d["coins"]))


def ledger_path(day: date) -> Path:
    return cache.CACHE_ROOT / "attention" / "reddit_items" / f"{day.isoformat()}.json"


class Ledger:
    """The item ledger; `hasher` turns the parser's usernames into hashes (required to read feeds into it)."""

    def __init__(self, hasher: AuthorHasher | None = None):
        self.hasher = hasher

    def read_day(self, day: date) -> dict[str, LedgerRow]:
        path = ledger_path(day)
        if not path.exists():
            return {}
        rows = (LedgerRow.from_json(r) for r in json.loads(path.read_text(encoding="utf-8"))["rows"])
        return {r.id: r for r in rows}

    def add(self, rows: Iterable[LedgerRow]) -> int:
        """Store new ids; a known id only gains coins. Returns the number of new ids."""
        by_day: dict[date, list[LedgerRow]] = {}
        for r in rows:
            by_day.setdefault(r.created.date(), []).append(r)
        new = 0
        for day, batch in by_day.items():
            known, changed = self.read_day(day), False
            for r in batch:
                old = known.get(r.id)
                if old is None:
                    known[r.id], changed, new = r, True, new + 1
                elif not set(r.coins) <= set(old.coins):
                    known[r.id] = LedgerRow(old.id, old.author_hash, old.subreddit, old.created, old.collected_at,
                                            old.feed_kind, old.coins + r.coins)
                    changed = True
            if changed:
                path = ledger_path(day)
                path.parent.mkdir(parents=True, exist_ok=True)
                cache._atomic_write_json({"rows": [known[k].to_json() for k in sorted(known)]}, path)
        return new


def to_items(rows: Iterable[LedgerRow]) -> list[reddit_metrics.Item]:
    return [reddit_metrics.Item(id=r.id, author_hash=r.author_hash, created=r.created, coins=r.coins) for r in rows]
