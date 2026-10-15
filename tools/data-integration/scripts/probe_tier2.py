"""AC-17 owner probe: tier-2 browser fetch of a JS-rendered loopback page, then parse and store.

Run (needs a browser: `scrapling install` once, or set DIT_BROWSER_EXECUTABLE to a Chromium):
  uv run --project tools/data-integration python tools/data-integration/scripts/probe_tier2.py
Creates its own temp approval record and temp cache; loopback only; prints PASS/FAIL, size hints and timing.
"""
from __future__ import annotations

import sys
import tempfile
import time
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
    from data_integration.fetch_tier2 import fetch
    from data_integration.gate import FetchPass, request_access
    from data_integration.parse import parse_table
    from data_integration.politeness import Politeness
    from data_integration.response_cache import ResponseCache
    from fixture_server import JS_PAGE_BODY, FixtureServer

    now = datetime.now(timezone.utc)
    server = FixtureServer().start()
    try:
        with tempfile.TemporaryDirectory(prefix="dit-probe2-") as tmp:
            store = ApprovalStore(Path(tmp) / "approvals")
            store.write(ApprovalRecord(
                id="probe-2", source="probe-src", allowed_tier=2, hosts=("example.test",), pages=("/js/",),
                rate_policy="probe", robots_checked=now.date().isoformat(), alternatives_checked=("probe: none",),
                owner="probe", approved=format_utc(now - timedelta(days=1)), expiry=format_utc(now + timedelta(days=1)),
                revision=1))
            pass_ = request_access("probe-src", 2, store, lambda: now)
            if not isinstance(pass_, FetchPass):
                print(f"FAIL: approval refused: {pass_}")
                return 1
            cache = ResponseCache(Path(tmp) / "cache", tier=2)
            started = time.monotonic()
            out = fetch("http://example.test/js/table", pass_, cache=cache, proxy=server.proxy_url, timeout=60.0,
                        politeness=Politeness(min_delay=0))
            elapsed = time.monotonic() - started
            if out.status != status.OK:
                print(f"FAIL: fetch status {out.status} ({out.detail})")
                return 1
            table = parse_table(out.body)
            if table.rows != (("2026-01-01", "1"), ("2026-01-02", "2")) or cache.get("http://example.test/js/table") is None:
                print("FAIL: JS table missing or cache round trip differs")
                return 1
    finally:
        server.stop()
    print(f"PASS: tier-2 rendered {len(table.rows)} rows from JS (repo root {REPO_ROOT.name})")
    print(f"size hints: source page {len(JS_PAGE_BODY)} bytes, rendered DOM {len(out.body)} bytes; elapsed {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
