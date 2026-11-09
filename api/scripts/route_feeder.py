"""Route source feeder (D-33, EXPERIMENT tier): keep B2 routes for the owner's experiment labels fed from free public
proxy lists. Its own process and the single writer of the route list/assignment files while enabled.

    uv run --project api --frozen python -m api.scripts.route_feeder --queries ABS_PATH (--once | --loop | --coverage)
        [--interval SECONDS] [--dry-run]

Default off: with `route_source_enabled` false it writes only its status file and exits 0. `--dry-run` probes and
plans but publishes nothing and keeps its state unchanged. `--loop` repeats every `--interval` seconds (bounded
300..86400); deploy/register-route-feeder-task.ps1 runs it at logon. `--coverage` is read-only (no network, no
write): verified exits per country from the private bank, so the owner can pick identity countries the pool has.
Output is counts and codes only, never an address, label or path.
See deploy/README.md "Route source feeder" and api/data/attention/route_source.py.
"""
from __future__ import annotations

import argparse
import ssl
import sys
import time
from pathlib import Path

from api.data.attention import route_source, x_proxy

MIN_INTERVAL, MAX_INTERVAL, DEFAULT_INTERVAL = 300, 86400, 600


def _line(result: route_source.Result) -> str:
    return (f"route_source[{route_source.TIER}] {result.state}: {result.reason} managed={result.managed} "
            f"assigned={result.assigned} spares={result.spares} replaced={result.replaced} "
            f"published={str(result.published).lower()} bank={result.bank.get('size', 0)} "
            f"live={result.bank.get('verified_live', 0)}")


def _coverage(queries: Path, deps: route_source.Deps, out) -> int:
    hours = int(route_source.LIVE_WINDOW.total_seconds() // 3600)
    try:
        counts = route_source.coverage(queries, deps)
    except (route_source.SourceError, x_proxy.ProxyFailure, ValueError, OSError, KeyError, TypeError, ssl.SSLError):
        print("route_source coverage: error (files_invalid)", file=out, flush=True)
        return 2
    print(f"route_source coverage: verified exits per country (last {hours} h)", file=out)
    for country, number in counts.items():
        print(f"{country} {number}", file=out)
    if not counts:
        print("none", file=out)
    out.flush()
    return 0


def main(argv=None, *, out=sys.stdout, deps: route_source.Deps | None = None, sleep=time.sleep, max_runs=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m api.scripts.route_feeder")
    parser.add_argument("--queries", type=Path, required=True, help="absolute private owner query file")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="one pass, then exit")
    mode.add_argument("--loop", action="store_true", help="repeat every --interval seconds")
    mode.add_argument("--coverage", action="store_true", help="read-only: verified exits per country from the bank")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL, help="loop interval, 300..86400 seconds")
    parser.add_argument("--dry-run", action="store_true", help="probe and plan only; publish nothing")
    args = parser.parse_args(argv)
    if not args.queries.is_absolute():
        parser.error("--queries must be absolute")
    if not MIN_INTERVAL <= args.interval <= MAX_INTERVAL:
        parser.error(f"--interval must be {MIN_INTERVAL}..{MAX_INTERVAL}")
    deps = deps or route_source.Deps(log=lambda message: print(message, file=sys.stderr))
    if args.coverage:
        return _coverage(args.queries, deps, out)
    runs = 0
    while True:
        result = route_source.run_once(args.queries, deps, dry_run=args.dry_run)
        print(_line(result), file=out, flush=True)
        runs += 1
        if args.once or result.state == "off" or (max_runs is not None and runs >= max_runs):
            return 2 if result.state == "error" else 0
        sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
