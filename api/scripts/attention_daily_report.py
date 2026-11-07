"""S-Report CLI (AC14): build day D's daily collection report from its durable facts.

    uv run --project api python -m api.scripts.attention_daily_report [--day YYYY-MM-DD] [--print]

D defaults to yesterday (UTC); only completed UTC days are accepted. Offline and read-only over the evidence: writes
`<cache>/attention/_reports/daily_report_<D>.json|txt` (a new revision only when D's inputs changed). Exit 0 on
success, 2 on a refused day.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone

from api.analytics.attention import daily_report as dr


def main(argv=None, *, out=sys.stdout, now: datetime | None = None, selector=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m api.scripts.attention_daily_report")
    parser.add_argument("--day", type=date.fromisoformat, help="completed UTC day (default: yesterday)")
    parser.add_argument("--print", action="store_true", help="print the text report")
    args = parser.parse_args(argv)
    now = now or datetime.now(timezone.utc)
    day = args.day or now.date() - timedelta(days=1)
    try:
        report = dr.rebuild(day, now=now, selector=selector)
    except ValueError as exc:
        print(f"error: {exc}", file=out)
        return 2
    if args.print:
        out.write(dr.render(report))
    else:
        js, txt = dr.report_paths(day)
        print(f"daily report {day.isoformat()} revision {report['revision']}: {js} {txt}", file=out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
