"""Owner probe for the PC-side X and Reddit collectors (PLAN R-1): argument parser and reporting helpers.

Run from the repo root:
  uv run --project api python -m api.scripts.probe_pc_sources --source reddit --symbol SOL --feed-depth
W8b ships the parser and the print helpers only; the Reddit modes arrive in W8c and W8c2, the X modes in W8d.
Until then every mode prints "not built yet" and exits 2 without sending anything. Output is numbers, statuses
and exception class names only, never a URL, header, cookie, query or body.
Exit codes: 0 a report was printed, 2 bad arguments or a mode not built yet.
"""
from __future__ import annotations

import argparse
import math
import re
import sys

from api.data.attention.pc_adapter import describe_error

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


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    mode = next((m for m in MODES if getattr(args, m)), "default")
    print(report_line("probe", built=False) + f" source={args.source} mode={mode}: not built yet (W8b core only)")
    return 2


if __name__ == "__main__":
    sys.exit(main())
