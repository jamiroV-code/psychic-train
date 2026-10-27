"""Owner probe for the PC-side X and Reddit collectors (PLAN R-1): argument parser, reporting helpers, Reddit modes.

Run from the repo root:
  uv run --project api python -m api.scripts.probe_pc_sources --source reddit --symbol SOL --feed-depth
  uv run --project api python -m api.scripts.probe_pc_sources --source reddit --symbol SOL --compare-scope
W8c ships the Reddit modes (P-R2 `--feed-depth`: one `search.rss` request over the subreddit set; P-R5
`--compare-scope`: the set, then one minute later the first subreddit alone). `--stream-status` arrives in W8c2,
the X modes in W8d; those print "not built yet" and exit 2 without sending anything. The probe keeps no budget
or pause state and stores nothing. Output is numbers, statuses and exception class names only, never a URL,
header, cookie, query, username or body.
Exit codes: 0 a report was printed, 2 bad arguments, a coin that is not collected, or a mode not built yet.
"""
from __future__ import annotations

import argparse
import math
import re
import sys
import time
from datetime import datetime, timezone

from api.data.attention import density, reddit_web, web_queries
from api.data.attention.pc_adapter import CollectorError, describe_error

SOURCES = ("reddit", "x")
SYMBOL_RE = re.compile(r"[A-Z0-9_]{1,24}")
LABEL_RE = re.compile(r"[a-z][a-z0-9_-]{0,30}")
MODES = ("feed_depth", "compare_scope", "stream_status")


def _symbol(text: str) -> str:
    sym = text.strip().upper()
    if not SYMBOL_RE.fullmatch(sym):
        raise argparse.ArgumentTypeError("symbol must be 1-24 letters, digits or _")
    return sym


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="probe_pc_sources", description="PC-side collector probe (numbers only).")
    p.add_argument("--source", required=True, choices=SOURCES)
    p.add_argument("--symbol", type=_symbol, default=None)
    p.add_argument("--feed-depth", action="store_true", help="Reddit: entries and age span of one feed (W8c)")
    p.add_argument("--compare-scope", action="store_true", help="Reddit: subreddit set against one subreddit (W8c)")
    p.add_argument("--stream-status", action="store_true", help="Reddit: stream polls and coverage (W8c2)")
    return p


def _fmt(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and math.isfinite(value):
        return f"{value:g}"
    if value is None:
        return "none"
    raise TypeError("report values must be numbers, booleans or None")


def report_line(label: str, **numbers) -> str:
    """`<label> k=v ...` with numeric, boolean or None values only; anything else is refused."""
    if not LABEL_RE.fullmatch(label):
        raise ValueError("label must be a short lower-case word")
    for key in numbers:
        if not LABEL_RE.fullmatch(key):
            raise ValueError("keys must be short lower-case words")
    return " ".join([label] + [f"{k}={_fmt(v)}" for k, v in numbers.items()])


def report_error(label: str, exc: BaseException, status: object = None) -> None:
    if not LABEL_RE.fullmatch(label):
        raise ValueError("label must be a short lower-case word")
    print(f"{label} error={describe_error(exc, status)}")


def _hours(a: datetime, b: datetime) -> float:
    return round((a - b).total_seconds() / 3600.0, 2)


def _feed_report(label: str, client, url: str, now: datetime, q, symbol: str) -> None:
    """One request; prints counts, ages in hours and the A.2 result for yesterday, or the error class and status.

    The probe sends no canary: the yesterday value is the one a run with a successful canary would store.
    """
    try:
        entries = reddit_web.parse_feed(reddit_web.fetch_feed(client, url), reddit_web.ephemeral_hasher())
    except CollectorError as exc:
        report_error(label, exc)
        return
    times = [e.created for e in entries]
    day = density.completed_day(now)
    start, end = density.window(day)
    c = q.config
    result, missing, tally = reddit_web.count_day(
        day, entries, coin=reddit_web.reddit_metrics.coin_term(q, symbol), sample_min=c.reddit_sample_min,
        author_cap=c.reddit_author_cap, canary_ok=True,
        searched_from=reddit_web.searched_from(now, c.reddit_search_time_filter))
    print(report_line(
        label, status=200, entries=len(entries),
        newest_age_h=_hours(now, max(times)) if times else None, oldest_age_h=_hours(now, min(times)) if times else None,
        span_h=_hours(max(times), min(times)) if times else None,
        reaches_window_start=bool(times) and min(times) < start,
        yesterday_entries=sum(1 for t in times if start <= t < end), matched=tally.matched, counted=tally.counted,
        yesterday_value=round(result.value, 2) if result else None, capped=bool(result and result.capped),
        missing=missing is not None))


def _reddit(args, client, clock, sleep) -> int:
    if args.stream_status or not (args.feed_depth or args.compare_scope):
        mode = "stream_status" if args.stream_status else "default"
        print(report_line("probe", built=False) + f" source=reddit mode={mode}: not built yet (W8c2)")
        return 2
    if args.symbol is None:
        print(report_line("probe", built=True) + " source=reddit: --symbol is required")
        return 2
    q = web_queries.load()
    terms = reddit_web.search_terms(q, args.symbol)
    if terms is None:
        print(report_line("probe", built=True) + " source=reddit: coin skipped (ambiguous or not in the query file)")
        return 2
    t = q.config.reddit_search_time_filter
    own = client is None
    client = client or reddit_web.make_client()
    try:
        if args.feed_depth:
            _feed_report("feed", client, reddit_web.search_url(q.subreddits, terms, t), clock(), q, args.symbol)
        else:
            _feed_report("scope_set", client, reddit_web.search_url(q.subreddits, terms, t), clock(), q, args.symbol)
            sleep(max(60, q.config.reddit_request_delay_min_s))
            _feed_report("scope_one", client, reddit_web.search_url(q.subreddits[:1], terms, t), clock(), q,
                         args.symbol)
    finally:
        if own:
            client.close()
    return 0


def main(argv: list[str] | None = None, *, client=None, clock=None, sleep=None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    if args.source == "reddit":
        return _reddit(args, client, clock or (lambda: datetime.now(timezone.utc)), sleep or time.sleep)
    mode = next((m for m in MODES if getattr(args, m)), "default")
    print(report_line("probe", built=False) + f" source={args.source} mode={mode}: not built yet (W8d)")
    return 2


if __name__ == "__main__":
    sys.exit(main())
