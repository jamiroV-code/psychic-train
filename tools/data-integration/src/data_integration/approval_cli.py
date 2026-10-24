"""Owner CLI for approvals: `status` and `add`. Never prints the real store path."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

from data_integration import paths
from data_integration.approvals import (
    DEFAULT_TTL_DAYS, MAX_TTL_DAYS, ApprovalRecord, ApprovalStore, StoreCorrupt, StoreError, check_resource_hosts, format_utc,
    valid_source,
)

PLACEHOLDER = "%LOCALAPPDATA%\\my_site\\approvals"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _status(clock) -> int:
    try:
        store = ApprovalStore(paths.approvals_dir())
    except paths.PathInRepo as exc:
        print(f"refused: {exc}")
        return 2
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


STATEMENT_MIN, STATEMENT_MAX = 20, 500


def _statement_problem(args, isatty) -> str:
    """Why the owner-statement path is refused ("" when it may proceed)."""
    text = args.owner_statement
    if isatty:
        return "--owner-statement is for non-interactive runs only"
    if not os.environ.get("DIT_APPROVALS_DIR"):
        return "--owner-statement needs DIT_APPROVALS_DIR to be set"
    if not (STATEMENT_MIN <= len(text) <= STATEMENT_MAX) or not text.isascii() or not text.isprintable():
        return f"statement must be {STATEMENT_MIN}-{STATEMENT_MAX} printable ASCII characters"
    if args.source not in text or any(h not in text for h in (*args.host, *args.resource_host)):
        return "statement must name the source and every host"
    return ""


def _add(args, clock, isatty, input_fn) -> int:
    statement = args.owner_statement
    if statement is None and args.resource_host:
        print("refused: --resource-host needs --owner-statement")
        return 2
    if statement is not None:
        problem = _statement_problem(args, isatty)
        if problem:
            print(f"refused: {problem}")
            return 2
    elif not isatty:
        print("refused: add needs an interactive terminal")
        return 2
    if not valid_source(args.source) or args.tier not in (1, 2, 3):
        print("refused: invalid source name or tier")
        return 2
    try:
        check_resource_hosts(tuple(args.resource_host), args.tier)
    except ValueError as exc:
        print(f"refused: {exc}")
        return 2
    if not 1 <= args.days <= MAX_TTL_DAYS:
        print(f"refused: --days must be between 1 and {MAX_TTL_DAYS}")
        return 2
    if statement is None:
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
        owner_statement=statement or "", resource_hosts=tuple(args.resource_host),
    )
    try:
        saved = ApprovalStore(paths.approvals_dir()).write(rec)
    except paths.PathInRepo as exc:
        print(f"refused: {exc}")
        return 2
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
    a.add_argument("--owner-statement", default=None)
    a.add_argument("--resource-host", action="append", default=[])
    a.add_argument("--days", type=int, default=DEFAULT_TTL_DAYS)
    args = p.parse_args(argv)
    if args.cmd == "status":
        return _status(clock)
    tty = sys.stdin.isatty() if isatty is None else isatty
    return _add(args, clock, tty, input_fn)


if __name__ == "__main__":
    raise SystemExit(main())
