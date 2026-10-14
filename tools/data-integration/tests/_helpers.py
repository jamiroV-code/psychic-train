"""Synthetic approval fixtures (tmp_path only)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

NOW = datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc)


def fixed_clock(now=NOW):
    return lambda: now


def make_record(source="example-src", tier=2, approved=NOW - timedelta(days=1), expiry=NOW + timedelta(days=30), **kw):
    from data_integration.approvals import ApprovalRecord, format_utc

    data = dict(
        id="rec-1",
        source=source,
        allowed_tier=tier,
        hosts=("a.example.test",),
        pages=("/data/",),
        rate_policy="1 request per 5 seconds",
        robots_checked="2026-01-09",
        alternatives_checked=("official api: none",),
        owner="owner-a",
        approved=format_utc(approved),
        expiry=format_utc(expiry),
        revision=1,
    )
    data.update(kw)
    return ApprovalRecord(**data)
