"""The single access gate. Standard library only; no HTTP client is ever created here."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import unquote, urlsplit

from data_integration.approvals import (
    ApprovalStore, RecordMissing, StoreCorrupt, StoreMissing, format_utc, valid_source,
)

_TOKEN = object()
_DEFAULT_PORTS = {"http": 80, "https": 443}


@dataclass(frozen=True)
class Refused:
    reason: str  # missing|expired|tier_too_low|store_missing|store_corrupt|bad_clock
    source: object
    tier_asked: object
    tier_allowed: int | None = None
    expiry: str | None = None


class FetchPass:
    """Proof of approval, bound to hosts and pages. Only request_access can build one."""

    __slots__ = ("source", "tier", "hosts", "pages", "approval_id", "approval_revision", "approved", "expires")

    def __init__(self, token=None, *, source=None, tier=None, hosts=(), pages=(), approval_id=None,
                 approval_revision=None, approved=None, expires=None):
        if token is not _TOKEN:
            raise TypeError("FetchPass can only be created by request_access")
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "tier", tier)
        object.__setattr__(self, "hosts", tuple(h.lower() for h in hosts))
        object.__setattr__(self, "pages", tuple(pages))
        object.__setattr__(self, "approval_id", approval_id)
        object.__setattr__(self, "approval_revision", approval_revision)
        object.__setattr__(self, "approved", approved)
        object.__setattr__(self, "expires", expires)

    def __setattr__(self, name, value):
        raise AttributeError("FetchPass is immutable")

    def permits(self, url: object) -> bool:
        if not isinstance(url, str) or "\\" in url:
            return False
        try:
            parts = urlsplit(url)
            port = parts.port
        except ValueError:
            return False
        scheme = parts.scheme.lower()
        if scheme not in _DEFAULT_PORTS or "@" in parts.netloc or not parts.hostname:
            return False
        if port is not None and port != _DEFAULT_PORTS[scheme]:
            return False
        if parts.hostname.lower() not in self.hosts:
            return False
        path = parts.path or "/"
        decoded = unquote(path)
        if ".." in decoded.split("/") or "\\" in decoded:
            return False
        return any(path == p or (p.endswith("/") and path.startswith(p)) for p in self.pages)


def _refuse(reason, source, tier, rec=None):
    return Refused(reason, source, tier, rec.allowed_tier if rec else None, rec.expiry if rec else None)


def request_access(source, tier, store: ApprovalStore, clock) -> FetchPass | Refused:
    try:
        now = clock()
    except Exception:
        return _refuse("bad_clock", source, tier)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        return _refuse("bad_clock", source, tier)
    if not valid_source(source):
        return _refuse("missing", source, tier)
    try:
        rec = store.read(source)
    except StoreMissing:
        return _refuse("store_missing", source, tier)
    except RecordMissing:
        return _refuse("missing", source, tier)
    except StoreCorrupt:
        return _refuse("store_corrupt", source, tier)
    if rec.approved_dt > now:
        return _refuse("bad_clock", source, tier, rec)
    if now >= rec.expiry_dt:
        return _refuse("expired", source, tier, rec)
    if type(tier) is not int or tier < 1 or tier > rec.allowed_tier:
        return _refuse("tier_too_low", source, tier, rec)
    return FetchPass(_TOKEN, source=source, tier=tier, hosts=rec.hosts, pages=rec.pages, approval_id=rec.id,
                     approval_revision=rec.revision, approved=rec.approved, expires=rec.expiry)
