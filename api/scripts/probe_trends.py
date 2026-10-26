"""Read-only Google Trends probe for the owner (T100a): one anchored request plus anchor evidence.

Run from the repo root: uv run --project api --with pytrends python -m api.scripts.probe_trends
Request 1: [anchor, 4 coins] over "today 3-m". Requests 2 and 3: [Bitcoin, Ethereum, sample coins] so both
anchor candidates sit on one scale with the coins. Prints raw numbers only, no recommendation.
Writes nothing; prints an exception's class and HTTP status only. Exit 0 when a report was printed
(a failed request is evidence), 1 the Trends session cannot start, 2 bad arguments or keyword file,
3 pytrends not installed. Starting the session sends one cookie request to Google, outside the 3 data
requests counted above. PowerShell: quote comma lists, e.g. --coins 'SOL,LINK,AAVE,INJ,MORPHO'.
--alone 'LINK,AAVE' (T100b, probe P-RES): instead of the requests above, one request per coin with only its
keyword, by default over the daily run's explicit 100-day range ending yesterday; prints days, min, median, max, days at 0 and at 0 or 1, distinct values, zero share and the verdict of
the daily run's too-little-interest rule. Stops at the first HTTP 429.
--try 'SYM=term1|term2' (T196, repeatable, at most 12): one request per term group (1 to 5 topic ids or terms, all on
one 0-100 scale) over the same explicit range; prints per-term and group numbers, the daily usable rule, a rising
measure (last 7 days vs the prior 28), one-term spike and correlation flags, a volume identity hint, a clean-rising
verdict, a ranked summary per coin and a paste-ready JSON suggestion (written nowhere). Requests go 3 s apart plus
up to 1 s jitter; the run stops at the first HTTP 429 or after 3 failed requests in a row (exit 4, no retry), and
Ctrl-C prints the partial summary (exit 130). Example:
  uv run --project api --with pytrends python -m api.scripts.probe_trends --try 'GRAM=toncoin crypto|ton coin'
"""
from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
import time
from datetime import date, datetime, timezone
from itertools import pairwise

from api.data.attention import store, trends
from api.data.attention import trends_groups as tg
from api.data.attention import trends_keywords as tk
from api.scripts.trends_cli_common import (
    http_status,
    is_rate_limited,
    make_trendreq,
    pytrends_version,
    start_client,
)

DEFAULT_COINS = ("SOL", "LINK", "AAVE", "INJ", "MORPHO")
SAMPLE_SIZE = 5
REQUEST1_COINS = 4
DEFAULT_TIMEFRAME = "today 3-m"
TIMEFRAME_RE = re.compile(r"(today [0-9]{1,2}-[my]|now [0-9]{1,2}-[dH]|[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{4}-[0-9]{2}-[0-9]{2})")
INTERVAL_SECONDS = 3.0
# --try (T196)
MAX_GROUPS = 12
TRY_JITTER_SECONDS = 1.0
MAX_CONSECUTIVE_FAILURES = 3
STOPPED_EXIT = 4
INTERRUPTED_EXIT = 130
VOLUME_SOURCE = "exchange_volume"
# Looser than the loader's TERM_RE so bare words and '+' or ':' can be tried; never '|', quotes, shell or control
# characters. Each term is still flagged with the real loader check.
LOOSE_TERM_RE = re.compile(r"[\w .'&+:-]{2,60}")


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


def _alone_stats(sym: str, kw: str, frame, day: date, out) -> None:
    points, reason = trends.complete_days(frame, kw)
    if points is None:
        print(f"  {sym} ({kw}) | {reason}", file=out)
        return
    vals = [v for d, v in points if d < day]
    if not vals:
        print(f"  {sym} ({kw}) | step {_step(frame)} | days 0 | verdict: {trends.TOO_LITTLE_INTEREST}", file=out)
        return
    zeros = sum(v == 0 for v in vals)
    print(f"  {sym} ({kw}) | step {_step(frame)} | days {len(vals)} | min {min(vals):g} | "
          f"median {statistics.median(vals):g} | max {max(vals):g} | at 0: {zeros} | "
          f"at 0 or 1: {sum(v <= 1 for v in vals)} | distinct {len(set(vals))} | "
          f"zero share {round(100 * zeros / len(vals), 1):g}% | verdict: {trends.interest_verdict(vals)}", file=out)


def _run_alone(client, km: tk.KeywordMap, symbols: list[str], timeframe: str, day: date, sleep, clock, out) -> int:
    """--alone: one request per symbol with only its keyword (owner probe P-RES); stops at the first HTTP 429."""
    print(f"alone: one request per coin, timeframe \"{timeframe}\"; rule: median >= {trends.TRENDS_MIN_MEDIAN} "
          f"and zero share < {trends.TRENDS_MAX_ZERO_DAY_PCT}%", file=out)
    sent = False
    for n, sym in enumerate(symbols):
        kw = km.keyword_for(sym)
        if kw is None:
            print(f"\n{sym}: no keyword (no-keyword or not in the keyword file)", file=out)
            continue
        if sent:
            sleep(INTERVAL_SECONDS)
        sent = True
        risk = " (bare name-risk term: the daily run skips it until a topic or qualified term is set)" if (
            sym in trends.NAME_RISK_SYMBOLS and not tk.is_valid_topic(kw) and not trends.is_qualified_term(kw)) else ""
        print(f"\nalone request: {sym} [{kw}]{risk}", file=out)
        frame, error, latency = _fetch(client, [kw], timeframe, clock)
        print(f"outcome: {_outcome(error)}", file=out)
        print(f"latency: {latency:.2f} s", file=out)
        if error is not None:
            if is_rate_limited(error):
                for rest in symbols[n + 1:]:
                    print(f"{rest}: skipped after HTTP 429", file=out)
                break
            continue
        _alone_stats(sym, kw, frame, day, out)
    return 0


def _loose_term_ok(term: str) -> bool:
    return tk.is_valid_topic(term) or (LOOSE_TERM_RE.fullmatch(term) is not None and term == term.strip())


def _try_arg(value: str) -> tuple[str, list[str]]:
    sym, sep, rest = value.partition("=")
    if not sep or not tk.SYMBOL_RE.fullmatch(sym):
        raise ArgError(f"--try must be SYM=term1|term2 with SYM matching {tk.SYMBOL_RE.pattern}")
    terms = [t.strip() for t in rest.split("|")]
    if not 1 <= len(terms) <= tg.MAX_TERMS:
        raise ArgError(f"--try takes 1 to {tg.MAX_TERMS} terms per group")
    if not all(_loose_term_ok(t) for t in terms):
        raise ArgError("--try terms must be topic ids or 2-60 letters, digits, space . ' & + : -")
    if len({t.casefold() for t in terms}) != len(terms):
        raise ArgError("--try terms must differ within a group")
    return sym, terms


def loader_flag(sym: str, term: str) -> str:
    """The daily runner's own check: a topic or safe term, and a name-risk coin's term needs a qualifier word."""
    if tk.is_valid_topic(term):
        return "loader-valid"
    if not tk.is_valid_term(term):
        return "not loader-safe (length or characters)"
    if sym in trends.NAME_RISK_SYMBOLS and not trends.is_qualified_term(term):
        return "needs qualifier word"
    return "loader-valid"


def _stored_volume(sym: str, day: date):
    """The coin's stored daily exchange volume on completed days (read only); (None, reason) when absent."""
    try:
        pts = [(d, v) for d, v in store.read_points(VOLUME_SOURCE, sym) if d < day]
    except store.StoreReadError:
        return None, "n/a: stored volume unreadable"
    return (pts, "") if pts else (None, "n/a: no stored volume")


def _pct0(x: float) -> str:
    return f"{round(100 * x, 1):g}%"


def _print_metrics(m: tg.GroupMetrics, out) -> None:
    print("  term | median | zero % | share of group", file=out)
    for t, st in m.terms.items():
        share = m.shares[t]
        print(f"  {t} | {st.median:g} | {round(st.zero_pct, 1):g}% | "
              f"{_pct0(share) if share is not None else 'missing: group total 0'}", file=out)
    gs = m.group
    print(f"  group | days {gs.days} | min {gs.min:g} | median {gs.median:g} | max {gs.max:g} | "
          f"zero {round(gs.zero_pct, 1):g}% | verdict: {m.verdict}", file=out)
    r = m.rising
    ratio = f"last7/prior28 {r.ratio:.3g} | days above baseline {r.days_above}/{tg.RECENT_DAYS}" if (
        r.ratio is not None) else f"last7/prior28 {r.reason}"
    spike = (f"{'yes' if m.spike else 'no'} (largest share {_pct0(m.spike_share)})" if m.spike_share is not None
             else m.spike_reason)
    print(f"  rising | {ratio} | one-term spike: {spike}", file=out)
    if m.correlations:
        cells = " | ".join(f"{t} {'missing: flat series' if c is None else f'{c:.2f}'}"
                           f"{' moves alone' if t in m.moves_alone else ''}" for t, c in m.correlations.items())
        print(f"  correlation (7-day smoothed) vs best term '{m.best_term}' | {cells}", file=out)
    else:
        print("  correlation | n/a: one term", file=out)
    ident = m.identity
    if ident.corr is None:
        text = ident.reason
    else:
        flag = " does not track this coin's volume" if ident.corr < tg.IDENTITY_MIN_CORR else ""
        text = f"vs log(1+stored daily volume) over {ident.days} days: {ident.corr:.2f}{flag}"
    print(f"  identity | {text} (a hint, not proof)", file=out)
    print(f"  clean rising: {'yes' if m.clean else 'no (' + '; '.join(m.reasons) + ')'}", file=out)


def _run_try(client, groups, day: date, sleep, clock, jitter, volume_reader, out) -> int:
    """--try: one request per group; stops at the first HTTP 429 or MAX_CONSECUTIVE_FAILURES failures in a row."""
    timeframe = trends.explicit_timeframe(day)
    print(f"try: {len(groups)} group(s), one request each, timeframe \"{timeframe}\"; {INTERVAL_SECONDS:g} s apart "
          f"plus up to {TRY_JITTER_SECONDS:g} s jitter; stops at the first HTTP 429 or after "
          f"{MAX_CONSECUTIVE_FAILURES} failed requests in a row", file=out)
    print(f"usable: median >= {trends.TRENDS_MIN_MEDIAN} and zero share < {trends.TRENDS_MAX_ZERO_DAY_PCT}% "
          f"(the daily rule); clean rising: usable, last7/prior28 >= {tg.MIN_RISE_RATIO:g}, >= {tg.MIN_DAYS_ABOVE} "
          f"of the last {tg.RECENT_DAYS} days above the prior-{tg.BASELINE_DAYS}-day median, no one-term spike "
          f"(> {tg.SPIKE_SHARE:.0%}), volume correlation >= {tg.IDENTITY_MIN_CORR:g} when available", file=out)
    results: list[tuple[str, list[str], tg.GroupMetrics | None, str]] = []
    streak, code, stop = 0, 0, ""
    try:
        for n, (sym, terms) in enumerate(groups):
            if n:
                sleep(INTERVAL_SECONDS + jitter())
            print(f"\ngroup {n + 1}/{len(groups)}: {sym} [{' | '.join(terms)}]", file=out)
            for t in terms:
                print(f"  term {t}: {loader_flag(sym, t)}", file=out)
            frame, error, latency = _fetch(client, terms, timeframe, clock)
            print(f"outcome: {_outcome(error)}", file=out)
            print(f"latency: {latency:.2f} s", file=out)
            if error is not None:
                results.append((sym, terms, None, "missing: request failed"))
                print("  missing: request failed", file=out)
                streak += 1
                if is_rate_limited(error) or streak >= MAX_CONSECUTIVE_FAILURES:
                    stop = ("stopped after HTTP 429" if is_rate_limited(error)
                            else f"stopped after {MAX_CONSECUTIVE_FAILURES} failed requests in a row")
                    code = STOPPED_EXIT
                    break
                continue
            streak = 0
            series, dates, reason = tg.check_group_frame(frame, terms, day)
            if series is None:
                results.append((sym, terms, None, f"missing: frame rejected ({reason})"))
                print(f"  missing: frame rejected ({reason})", file=out)
                continue
            volume, _ = volume_reader(sym, day)
            m = tg.analyze(series, dates, volume)
            results.append((sym, terms, m, ""))
            _print_metrics(m, out)
    except KeyboardInterrupt:
        stop, code = "interrupted (Ctrl-C)", INTERRUPTED_EXIT
    if stop:
        print(f"\n{stop}", file=out)
        for sym, terms in groups[len(results):]:  # after Ctrl-C the group in flight has no result either
            results.append((sym, terms, None, f"not run ({stop})"))
            print(f"{sym} [{' | '.join(terms)}]: not run ({stop})", file=out)
    _print_summary(results, out)
    return code


def _print_summary(results, out) -> None:
    print("\n--- ranked summary (best first: usable, then clean rising, then highest median; every group is on its "
          "own request's 0-100 scale) ---", file=out)
    suggestion: dict[str, dict] = {}
    none: list[str] = []
    for sym in dict.fromkeys(r[0] for r in results):
        print(sym, file=out)
        mine = [r for r in results if r[0] == sym]
        ranked = sorted((r for r in mine if r[2] is not None), key=lambda r: tg.rank_key(r[2]))
        for i, (_, terms, m, _) in enumerate(ranked, start=1):
            print(f"  {i}. [{' | '.join(terms)}] | verdict {m.verdict} | clean rising {'yes' if m.clean else 'no'} | "
                  f"median {m.group.median:g}", file=out)
        for _, terms, _, reason in (r for r in mine if r[2] is None):
            print(f"  -  [{' | '.join(terms)}] | {reason}", file=out)
        best = next((terms for _, terms, m, _ in ranked if m.verdict == "ok"
                     and all(loader_flag(sym, t) == "loader-valid" for t in terms)), None)
        if best is None:
            none.append(sym)
        else:
            suggestion[sym] = {"terms": best}
    print("\n--- paste-ready JSON (best loader-valid usable group per coin; informational, written nowhere) ---",
          file=out)
    print(json.dumps(suggestion, indent=2), file=out)
    for sym in none:
        print(f"{sym}: no loader-valid usable group", file=out)


def _parse(argv, km: tk.KeywordMap):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--coins", default=",".join(DEFAULT_COINS))
    ap.add_argument("--anchor-a", default=None, help="default: the BTC entry's keyword")
    ap.add_argument("--anchor-b", default=None, help="default: the ETH entry's keyword")
    ap.add_argument("--timeframe", default=None, help=f'default "{DEFAULT_TIMEFRAME}"; with --alone the daily '
                    "run's explicit 100-day range ending yesterday")
    ap.add_argument("--no-evidence", action="store_true")
    ap.add_argument("--alone", default=None, help="comma list of symbols: one request per coin, only its keyword")
    ap.add_argument("--try", dest="groups", action="append", default=None,
                    help="SYM=term1|term2 (repeatable, at most 12): one request per term group")
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
    if args.alone is not None:
        alone = [s.strip() for s in args.alone.split(",") if s.strip()]
        if not alone or not all(tk.SYMBOL_RE.fullmatch(s) for s in alone):
            raise ArgError(f"--alone must be comma-separated symbols matching {tk.SYMBOL_RE.pattern}")
        args.alone = list(dict.fromkeys(alone))
    if args.groups is not None:
        if args.alone is not None or args.timeframe is not None:
            raise ArgError("--try cannot be combined with --alone or --timeframe")
        if len(args.groups) > MAX_GROUPS:
            raise ArgError(f"--try takes at most {MAX_GROUPS} groups per run")
        args.groups = [_try_arg(v) for v in args.groups]
        return args, coins, a, b
    if args.timeframe is None and args.alone is None:
        args.timeframe = DEFAULT_TIMEFRAME
    if args.timeframe is not None and not TIMEFRAME_RE.fullmatch(args.timeframe):
        raise ArgError('--timeframe must look like "today 3-m"')
    return args, coins, a, b


def main(argv: list[str] | None = None, *, trendreq_factory=make_trendreq, sleep=time.sleep, clock=time.monotonic,
         today=None, version=pytrends_version, out=None, err=None,
         jitter=lambda: random.uniform(0, TRY_JITTER_SECONDS), volume_reader=_stored_volume) -> int:
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
    client, code = start_client(trendreq_factory, "probe_trends", err)
    if client is None:
        return code

    if args.groups is not None:
        print("probe_trends: read-only, writes nothing", file=out)
        print(f"pytrends version: {version()}", file=out)
        return _run_try(client, args.groups, today(), sleep, clock, jitter, volume_reader, out)

    if args.alone is not None:
        print("probe_trends: read-only, writes nothing", file=out)
        print(f"pytrends version: {version()}", file=out)
        day = today()
        return _run_alone(client, km, args.alone, args.timeframe or trends.explicit_timeframe(day), day, sleep,
                          clock, out)

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
