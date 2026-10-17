"""Record observed source states into probe_records.json (owner PC, after a live refresh).

Reads the attention store only; it never fetches. Per source it stores the
state, coin counts, longest completed-day history and the UTC date observed.
No keys, tokens or addresses are written. `--dry-run` prints and writes nothing.
Exit codes: 0 done, 1 bad argument.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

if __package__ in (None, ""):  # direct invocation
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.data import cache  # noqa: E402
from api.data.attention import registry, store  # noqa: E402
from api.data.attention.types import MIN_HISTORY_DAYS  # noqa: E402

DEFAULT_SOURCES = ("wikipedia", "coingecko")
STATES = ("ok", "unavailable", "insufficient-history", "no-article", "capped", "not-probed")
SERIES_SOURCES = tuple(registry.FETCHERS)


def _symbols(arg: str | None) -> list[str]:
    if arg:
        return [s.strip().upper() for s in arg.split(",") if s.strip()]
    from api.scripts import refresh_attention
    return refresh_attention._symbols(None)


def observe(source: str, symbols: list[str], today: date) -> dict:
    """Summarise what the store holds for one source (completed UTC days only)."""
    days = [len([1 for d, _ in store.read_points(source, s) if d < today]) for s in symbols]
    top = max(days, default=0)
    ok = sum(1 for n in days if n >= MIN_HISTORY_DAYS)
    state = "ok" if ok else ("insufficient-history" if top else "unavailable")
    return {"state": state, "coins_checked": len(symbols), "coins_ok": ok,
            "max_days": top, "as_of": today.isoformat()}


def main(argv: list[str] | None = None, *, records_path: Path | None = None,
         today: date | None = None) -> int:
    p = argparse.ArgumentParser(description="Record observed source states (no fetching).")
    p.add_argument("--sources", help="comma list; default wikipedia,coingecko")
    p.add_argument("--symbols", help="comma list; default wiki_articles.json")
    p.add_argument("--state", action="append", default=[], metavar="SOURCE=STATE",
                   help="set a state you observed by hand (e.g. xsearch=capped); not-probed removes the record")
    p.add_argument("--dry-run", action="store_true", help="print the summary; write nothing")
    args = p.parse_args(argv)

    names = [s.strip() for s in args.sources.split(",") if s.strip()] if args.sources else list(DEFAULT_SOURCES)
    manual: dict[str, str] = {}
    for item in args.state:
        src, _, st = item.partition("=")
        if src not in SERIES_SOURCES or st not in STATES:
            print(f"bad --state: {item!r}", file=sys.stderr)
            return 1
        manual[src] = st
    bad = [n for n in names if n not in SERIES_SOURCES]
    if bad:
        print(f"unknown source: {', '.join(bad)}", file=sys.stderr)
        return 1

    today = today or datetime.now(timezone.utc).date()
    path = records_path or registry.PROBE_RECORDS_PATH
    records = registry.load_probe_records(path)
    symbols = _symbols(args.symbols)
    lines = []
    for name in names:
        records[name] = rec = observe(name, symbols, today)
        lines.append(f"{name}: {rec['state']} ({rec['coins_ok']}/{rec['coins_checked']} coins with "
                     f"{MIN_HISTORY_DAYS}+ days, max {rec['max_days']} days)")
    for name, st in manual.items():
        if st == "not-probed":
            records.pop(name, None)
            lines.append(f"{name}: record removed (not-probed)")
        else:
            records[name] = {"state": st, "as_of": today.isoformat(), "note": "set by hand"}
            lines.append(f"{name}: {st} (set by hand)")
    print("\n".join(lines))
    if args.dry_run:
        print("dry run: nothing written")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    cache._atomic_write_json(records, path)
    print(f"wrote {len(records)} source records")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:
        print(f"fatal: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)
