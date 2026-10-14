"""The closed set of fetch/pipeline statuses. Extend only here."""
from __future__ import annotations

OK = "ok"
REFUSED = "refused"
ROBOTS_BLOCKED = "robots_blocked"
TIMEOUT = "timeout"
CONNECTION_FAILED = "connection_failed"
HTTP_ERROR = "http_error"
CHALLENGE_PAGE = "challenge_page"
CHANGED = "changed"
UNCERTAIN = "uncertain"
INVALID = "invalid"
CACHE_HIT = "cache_hit"

ALL_STATUSES: frozenset[str] = frozenset(
    {OK, REFUSED, ROBOTS_BLOCKED, TIMEOUT, CONNECTION_FAILED, HTTP_ERROR, CHALLENGE_PAGE, CHANGED, UNCERTAIN, INVALID, CACHE_HIT}
)


def is_status(value: str) -> bool:
    return value in ALL_STATUSES
