"""Owner CLI for approvals: `status` and `add`. Never prints the real store path."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

from data_integration import paths
from data_integration.approvals import (
    DEFAULT_TTL_DAYS, MAX_TTL_DAYS, ApprovalRecord, ApprovalStore, StoreCorrupt, StoreError, format_utc, valid_source,
)

PLACEHOLDER = "%LOCALAPPDATA%\\my_site\\approvals"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _status(clock) -> int:
    store = ApprovalStore(paths.approvals_dir())
    active = "active" if os.environ.get("DIT_APPROVALS_DIR") else "inactive"
    print(f"approvals folder: {PLACEHOLDER} (override: {active})")
    sources = store.list_sources()
    bad = sorted(p.name[: -len(".approval.json")] for p in store.root.glob("*.approval.json")) if store.root.is_dir() else []
    if not sources and not bad:
        print("no approvals")
        return 0
    now = clock()
    print(f"{'source':<24}{'tier':<6}{'expiry':<24}days_left")
    for name in sorted(set(sources) | set(bad)):
        try:
            rec = store.read(name)
        except StoreCorrupt:
            print(f"{name:<24}{'-':<6}{'-':<24}corrupt")
            continue
        except StoreError:
            continue
        left = (rec.expiry_dt - now).days if now < rec.expiry_dt else None
        print(f"{name:<24}{rec.allowed_tier:<6}{rec.expiry:<24}{'expired' if left is None else left}")
    return 0


def _add(args, clock, isatty, input_fn) -> int:
    if not isatty:
        print("refused: add needs an interactive terminal")
        return 2
    if not valid_source(args.source) or args.tier not in (1, 2, 3):
        print("refused: invalid source name or tier")
        return 2
    if not 1 <= args.days <= MAX_TTL_DAYS:
        print(f"refused: --days must be between 1 and {MAX_TTL_DAYS}")
        return 2
    typed = input_fn(f"Type the source name ({args.source}) to confirm: ")
    if typed != args.source:
        print("refused: source name did not match")
        return 2
    now = clock()
    rec = ApprovalRecord(
        id=f"{args.source}-{now.strftime('%Y%m%d')}", source=args.source, allowed_tier=args.tier,
        hosts=tuple(args.host), pages=tuple(args.page), rate_policy=args.rate, robots_checked=args.robots_checked,
        alternatives_checked=tuple(args.alternative), owner=args.owner, approved=format_utc(now),
        expiry=format_utc(now + timedelta(days=args.days)),
    )
    saved = ApprovalStore(paths.approvals_dir()).write(rec)
    print(f"saved approval for {saved.source} (revision {saved.revision}, expires {saved.expiry})")
    return 0


def main(argv=None, *, clock=_now, isatty=None, input_fn=input) -> int:
    p = argparse.ArgumentParser(prog="approval_cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    a = sub.add_parser("add")
    a.add_argument("--source", required=True)
    a.add_argument("--tier", type=int, required=True)
    a.add_argument("--host", action="append", required=True)
    a.add_argument("--page", action="append", required=True)
    a.add_argument("--owner", required=True)
    a.add_argument("--rate", required=True)
    a.add_argument("--robots-checked", required=True)
    a.add_argument("--alternative", action="append", default=[])
    a.add_argument("--days", type=int, default=DEFAULT_TTL_DAYS)
    args = p.parse_args(argv)
    if args.cmd == "status":
        return _status(clock)
    tty = sys.stdin.isatty() if isatty is None else isatty
    return _add(args, clock, tty, input_fn)


if __name__ == "__main__":
    raise SystemExit(main())
