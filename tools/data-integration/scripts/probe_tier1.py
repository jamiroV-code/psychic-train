"""AC-16 owner probe: tier-1 fetch -> parse -> store, against the loopback fixture server only.

Run: uv run --project tools/data-integration python tools/data-integration/scripts/probe_tier1.py
Creates its own temp approval record and temp cache; prints PASS or FAIL. No real site is contacted.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
from data_integration import paths  # noqa: E402

REPO_ROOT = paths._repo_root()
sys.path.insert(0, str(HERE.parent / "tests"))


def main() -> int:
    from datetime import datetime, timedelta, timezone

    from data_integration import status
    from data_integration.approvals import ApprovalRecord, ApprovalStore, format_utc
    from data_integration.fetch_tier1 import fetch
    from data_integration.gate import FetchPass, request_access
    from data_integration.parse import parse_table
    from data_integration.politeness import Politeness
    from data_integration.response_cache import ResponseCache
    from fixture_server import FixtureServer

    now = datetime.now(timezone.utc)
    server = FixtureServer().start()
    try:
        with tempfile.TemporaryDirectory(prefix="dit-probe1-") as tmp:
            store = ApprovalStore(Path(tmp) / "approvals")
            store.write(ApprovalRecord(
                id="probe-1", source="probe-src", allowed_tier=1, hosts=("example.test",), pages=("/data/",),
                rate_policy="probe", robots_checked=now.date().isoformat(), alternatives_checked=("probe: none",),
                owner="probe", approved=format_utc(now - timedelta(days=1)), expiry=format_utc(now + timedelta(days=1)),
                revision=1))
            pass_ = request_access("probe-src", 1, store, lambda: now)
            if not isinstance(pass_, FetchPass):
                print(f"FAIL: approval refused: {pass_}")
                return 1
            cache = ResponseCache(Path(tmp) / "cache", tier=1)
            out = fetch("http://example.test/data/ok", pass_, cache=cache, proxy=server.proxy_url,
                        politeness=Politeness(min_delay=0))
            if out.status != status.OK:
                print(f"FAIL: fetch status {out.status} ({out.detail})")
                return 1
            table = parse_table(out.body)
            cached = cache.get("http://example.test/data/ok")
            if table.rows != (("2026-01-01", "1"),) or cached is None or cached.body != out.body:
                print("FAIL: parse or cache round trip differs")
                return 1
    finally:
        server.stop()
    print(f"PASS: tier-1 fetch/parse/store ok (repo root {REPO_ROOT.name}, rows={len(table.rows)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
