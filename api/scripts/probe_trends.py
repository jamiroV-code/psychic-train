"""Read-only Google Trends probe for the owner (T100a): one anchored request plus anchor evidence.

Run from the repo root: uv run --project api --with pytrends python -m api.scripts.probe_trends
Request 1: [anchor, 4 coins] over "today 3-m". Requests 2 and 3: [Bitcoin, Ethereum, sample coins] so both
anchor candidates sit on one scale with the coins. Prints raw numbers only, no recommendation.
Writes nothing; prints an exception's class and HTTP status only. Exit 0 when a report was printed
(a failed request is evidence), 2 bad arguments or keyword file, 3 pytrends not installed.
"""
from __future__ import annotations

import argparse
import re
import statistics
import sys
import time
from datetime import date, datetime, timezone
from itertools import pairwise

from api.data.attention import trends_keywords as tk
from api.scripts.trends_cli_common import (
    PytrendsMissing,
    http_status,
    is_rate_limited,
    make_trendreq,
    missing_message,
    pytrends_version,
)

DEFAULT_COINS = ("SOL", "LINK", "AAVE", "INJ", "MORPHO")
SAMPLE_SIZE = 5
REQUEST1_COINS = 4
DEFAULT_TIMEFRAME = "today 3-m"
TIMEFRAME_RE = re.compile(r"(today [0-9]{1,2}-[my]|now [0-9]{1,2}-[dH]|[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{4}-[0-9]{2}-[0-9]{2})")
INTERVAL_SECONDS = 3.0


class ArgError(ValueError):
    pass


def _keyword_arg(value: str, flag: str) -> str:
    if not (tk.is_valid_topic(value) or tk.is_valid_term(value)):
        raise ArgError(f"{flag} must be a topic id or a safe term")
    return value


def _outcome(exc: BaseException | None) -> str:
    if exc is None:
        return "ok"
    status = http_status(exc)
    return f"{type(exc).__name__} (HTTP {status})" if status is not None else type(exc).__name__


def _fetch(client, terms: list[str], timeframe: str, clock):
    t0 = clock()
    frame, error = None, None
    try:
        client.build_payload(terms, timeframe=timeframe, geo="")
        frame = client.interest_over_time()
    except Exception as exc:  # noqa: BLE001 - the class is the evidence; the message is never printed
        error = exc
    return frame, error, clock() - t0


def _partial(value) -> bool:
    return value.strip().lower() == "true" if isinstance(value, str) else bool(value)


def _rows(frame):
    """[(date, {term: value}, partial)] in index order."""
    terms = [c for c in frame.columns if c != "isPartial"]
    has_flag = "isPartial" in frame.columns
    out = []
    for ts, row in frame.iterrows():
        values = {t: row[t] for t in terms}
        out.append((ts.date() if hasattr(ts, "date") else ts, values, _partial(row["isPartial"]) if has_flag else False))
    return out


def _step(frame) -> str:
    idx = list(frame.index)
    if len(idx) < 2:
        return "unknown (fewer than 2 rows)"
    days = [(b - a).total_seconds() / 86400 for a, b in pairwise(idx)]
    if all(d == 1 for d in days):
        return "daily"
    return f"non-daily ({min(days):g}..{max(days):g} days)"


def _fmt_row(d, values: dict, partial: bool) -> str:
    cells = " ".join(f"{t}={_num(v)}" for t, v in values.items())
    return f"  {d.isoformat() if isinstance(d, date) else d} | {cells} | partial={partial}"


def _num(v) -> str:
    try:
        return f"{float(v):g}"
    except (TypeError, ValueError):
        return "-"


def _report_frame(frame, error, latency: float, today: date, out) -> None:
    print(f"outcome: {_outcome(error)}", file=out)
    print(f"latency: {latency:.2f} s", file=out)
    if frame is None:
        print("rows: -", file=out)
        return
    rows = _rows(frame)
    print(f"rows: {len(rows)}", file=out)
    print(f"index step: {_step(frame) if rows else '-'}", file=out)
    complete = sum(1 for d, _, partial in rows if not partial and isinstance(d, date) and d < today)
    print(f"complete days: {complete}", file=out)
    print("first 5 rows:", file=out)
    for r in rows[:5]:
        print(_fmt_row(*r), file=out)
    print("last 5 rows:", file=out)
    for r in rows[-5:]:
        print(_fmt_row(*r), file=out)


def _series(frame, term: str) -> list[float] | None:
    if frame is None or term not in frame.columns:
        return None
    return [float(v) for v in frame[term].tolist()]


def _pct(a: float, b: float) -> str:
    return "n/a" if not b else f"{round(100 * a / b, 1):g}%"


def _report_evidence(frame, terms: list[str], anchors: tuple[str, str], coins: list[str], out) -> None:
    if frame is None:
        return
    series = {t: _series(frame, t) for t in terms}
    for t in terms:
        s = series[t]
        if not s:
            print(f"  {t} | missing from response", file=out)
            continue
        print(f"  {t} | days {len(s)} | min {min(s):g} | median {statistics.median(s):g} | "
              f"max {max(s):g} | last {s[-1]:g} | at 100: {sum(v == 100 for v in s)} | "
              f"at 0 or 1: {sum(v <= 1 for v in s)}", file=out)
    a, b = anchors
    med = {t: statistics.median(series[t]) for t in (a, b) if series.get(t)}
    for c in coins:
        if series.get(c):
            m = statistics.median(series[c])
            print(f"  {c}: median {_pct(m, med.get(a, 0))} of A ({a}), {_pct(m, med.get(b, 0))} of B ({b})", file=out)
    present = [series[c] for c in coins if series.get(c)]
    for tag, anchor in (("A", a), ("B", b)):
        s = series.get(anchor)
        if not s or not present:
            continue
        above = sum(1 for i, v in enumerate(s) if any(len(cs) > i and cs[i] > v for cs in present))
        crushed = sum(1 for i in range(len(s)) if all(len(cs) > i and cs[i] <= 1 for cs in present))
        print(f"  {tag} ({anchor}): a coin is above it on {above} days; every coin is at 0 or 1 on {crushed} days",
              file=out)


def _pick_coins(km: tk.KeywordMap, requested: list[str], anchors: set[str], out) -> list[str]:
    picked: list[str] = []
    seen: set[str] = set()
    for i, sym in enumerate(requested + [s for s in DEFAULT_COINS] + km.keyword_symbols()):
        if len(picked) >= SAMPLE_SIZE:
            break
        kw = km.keyword_for(sym)
        explicit = i < len(requested)
        if kw is None:
            if explicit:
                print(f"skip {sym}: no keyword (no-keyword or not in the keyword file); the next default is used", file=out)
            continue
        if kw.casefold() in anchors:
            if explicit:
                print(f"skip {sym}: same keyword as an anchor; the next default is used", file=out)
            continue
        if kw.casefold() in seen:
            continue
        seen.add(kw.casefold())
        picked.append(kw)
    return picked


def _parse(argv, km: tk.KeywordMap):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--coins", default=",".join(DEFAULT_COINS))
    ap.add_argument("--anchor-a", default=None, help="default: the BTC entry's keyword")
    ap.add_argument("--anchor-b", default=None, help="default: the ETH entry's keyword")
    ap.add_argument("--timeframe", default=DEFAULT_TIMEFRAME)
    ap.add_argument("--no-evidence", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        raise ArgError("bad arguments") if exc.code else exc
    coins = [s.strip() for s in args.coins.split(",") if s.strip()]
    if not coins or not all(tk.SYMBOL_RE.fullmatch(s) for s in coins):
        raise ArgError(f"--coins must be comma-separated symbols matching {tk.SYMBOL_RE.pattern}")
    a = _keyword_arg(args.anchor_a, "--anchor-a") if args.anchor_a is not None else km.keyword_for("BTC")
    b = _keyword_arg(args.anchor_b, "--anchor-b") if args.anchor_b is not None else km.keyword_for("ETH")
    if not a or not b:
        raise ArgError("no default anchor keyword in the keyword file; pass --anchor-a and --anchor-b")
    if not TIMEFRAME_RE.fullmatch(args.timeframe):
        raise ArgError('--timeframe must look like "today 3-m"')
    return args, coins, a, b


def main(argv: list[str] | None = None, *, trendreq_factory=make_trendreq, sleep=time.sleep, clock=time.monotonic,
         today=None, version=pytrends_version, out=None, err=None) -> int:
    out, err = out or sys.stdout, err or sys.stderr
    today = today or (lambda: datetime.now(timezone.utc).date())
    km, reason = tk.safe_load()
    if km is None:
        print(reason, file=err)
        return 2
    try:
        args, requested, anchor_a, anchor_b = _parse(argv, km)
    except ArgError as exc:
        print(str(exc), file=err)
        return 2
    except SystemExit:  # --help
        return 0
    try:
        client = trendreq_factory()
    except PytrendsMissing:
        print(missing_message("probe_trends"), file=err)
        return 3

    anchor = km.anchor_keyword()
    sample = _pick_coins(km, requested, {anchor.casefold(), anchor_a.casefold(), anchor_b.casefold()}, out)
    day = today()
    print("probe_trends: read-only, writes nothing", file=out)
    print(f"pytrends version: {version()}", file=out)

    terms1 = [anchor] + sample[:REQUEST1_COINS]
    print(f"\nrequest 1: {terms1} timeframe \"{args.timeframe}\"", file=out)
    frame, error, latency = _fetch(client, terms1, args.timeframe, clock)
    _report_frame(frame, error, latency, day, out)

    if error is not None and is_rate_limited(error):
        print("\nevidence requests: skipped after HTTP 429", file=out)
        return 0
    if args.no_evidence:
        print("\nevidence requests: skipped (--no-evidence)", file=out)
        return 0
    print(f"\nevidence: A = {anchor_a}, B = {anchor_b}; every number below is on its request's scale", file=out)
    groups = [g for g in (sample[:3], sample[3:SAMPLE_SIZE]) if g]
    for n, coins in enumerate(groups, start=2):
        sleep(INTERVAL_SECONDS)
        terms = [anchor_a, anchor_b] + coins
        print(f"\nevidence request {n}: {terms} timeframe \"{args.timeframe}\"", file=out)
        frame, error, latency = _fetch(client, terms, args.timeframe, clock)
        print(f"outcome: {_outcome(error)}", file=out)
        print(f"latency: {latency:.2f} s", file=out)
        _report_evidence(frame, terms, (anchor_a, anchor_b), coins, out)
        if error is not None and is_rate_limited(error) and n == 2 and len(groups) == 2:
            print("\nevidence request 3: skipped after HTTP 429", file=out)
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
