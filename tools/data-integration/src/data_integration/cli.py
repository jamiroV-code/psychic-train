"""`python -m data_integration`: approvals, rea, run. Plain output, no tracebacks, no absolute paths or IPv4."""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlsplit

from data_integration import approval_cli, paths, status
from data_integration.approvals import ApprovalStore, StoreError
from data_integration.gate import Refused, request_access
from data_integration.politeness import Politeness
from data_integration.recipe import RecipeError, load_recipe
from data_integration.response_cache import ResponseCache

EXIT_CODES = {
    status.OK: 0, status.CACHE_HIT: 0, status.ROBOTS_BLOCKED: 4, status.TIMEOUT: 4, status.CONNECTION_FAILED: 4,
    status.HTTP_ERROR: 4, status.CHALLENGE_PAGE: 4, status.INVALID: 5, status.CHANGED: 6, status.UNCERTAIN: 6,
    status.REFUSED: 7,
}
STATUS_MESSAGES = {
    status.OK: "data checked and stored",
    status.CACHE_HIT: "the stored data is already the same, nothing changed",
    status.ROBOTS_BLOCKED: "the site's robots.txt does not allow this page, nothing was fetched",
    status.TIMEOUT: "the site did not answer in time",
    status.CONNECTION_FAILED: "could not connect to the site",
    status.HTTP_ERROR: "the site answered with an error status",
    status.CHALLENGE_PAGE: "the site showed a challenge page instead of data, nothing was stored",
    status.INVALID: "the page or table failed the checks, nothing was stored",
    status.CHANGED: "the page layout changed, nothing was stored",
    status.UNCERTAIN: "no trusted baseline for this selector, nothing was stored (first run: use --accept-baseline)",
    status.REFUSED: "the request was refused, nothing was stored",
}
GATE_MESSAGES = {
    "missing": "no approval record for this source",
    "expired": "the approval has expired",
    "tier_too_low": "the approval does not allow this tier",
    "store_missing": "the approvals folder does not exist",
    "store_corrupt": "the approval record cannot be read",
    "bad_clock": "the clock or the approval dates are not usable",
    "url_not_approved": "the recipe url is outside the approved hosts and pages",
}
EVIDENCE_PLACEHOLDER = "%LOCALAPPDATA%\\my_site\\evidence"
_PATH_RES = (r"(?<![\w])[A-Za-z]:[\\/][^\s'\"]*", r"(?<![\w/:.%\\-])/(?:[\w.~+-]+/)*[\w.~+-]+")
_IPV4 = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe(text: object) -> str:
    out = str(text)
    for pattern in _PATH_RES:
        out = re.sub(pattern, "<path>", out)
    return re.sub(_IPV4, "<ip>", out)


def _say(text: object = "") -> None:
    print(_safe(text))


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m data_integration", allow_abbrev=False)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("approvals", allow_abbrev=False, help="status | add (see approvals --help)")
    r = sub.add_parser("rea", allow_abbrev=False, help="rea <command> [--confirm-source N] [--findings F] [-- args]")
    r.add_argument("command")
    r.add_argument("--confirm-source")
    r.add_argument("--findings")
    run = sub.add_parser("run", allow_abbrev=False, help="run a recipe")
    run.add_argument("recipe")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--preview", action="store_true")
    run.add_argument("--refresh", action="store_true")
    run.add_argument("--replace", action="store_true")
    run.add_argument("--accept-baseline", action="store_true")
    return p


def _default_registry() -> dict:
    from data_integration import fetch_tier1, fetch_tier2, fetch_tier3

    return {1: fetch_tier1.fetch, 2: fetch_tier2.fetch, 3: fetch_tier3.fetch}


class _Adapter:
    """Gives a tier's fetch function the Fetcher shape; a response-cache hit counts as ok."""

    def __init__(self, fn, **options):
        self._fn, self._options = fn, options

    def fetch(self, url, pass_):
        out = self._fn(url, pass_, **self._options)
        return dataclasses.replace(out, status=status.OK) if out.status == status.CACHE_HIT else out


def _has_baseline(rec) -> bool:
    from data_integration import adaptive

    return adaptive.assess(b"<html></html>", rec.selector, url=rec.url).has_baseline


def _rate(store: ApprovalStore, source: str) -> str:
    try:
        return store.read(source).rate_policy
    except StoreError:
        return "unavailable"


def _approval_line(pass_) -> str:
    return f"approval: id={pass_.approval_id} revision={pass_.approval_revision} expires={pass_.expires}"


def _result(st: str, detail: str = "", outline: tuple = ()) -> int:
    _say(f"result: {st} - {STATUS_MESSAGES.get(st, 'unknown status')}")
    if detail:
        _say(f"detail: {detail}")
    if outline:
        _say("page outline (nothing stored, page text is not shown):")
        for line in outline:
            _say(f"  {line}")
    return EXIT_CODES.get(st, 5)


def _refuse_gate(reason: str, refused: Refused | None = None) -> int:
    _say(f"refused ({reason}): {GATE_MESSAGES.get(reason, 'not allowed')}")
    if refused is not None and refused.expiry and reason in ("expired", "tier_too_low"):
        _say(f"approval allows tier {refused.tier_allowed} until {refused.expiry}")
    return 3


def _show_rows(table) -> None:
    rows = table.rows
    _say(f"rows: {len(rows)}")
    _say("columns: " + ", ".join(table.columns))
    shown = [("first", rows[:3]), ("last", rows[-3:])] if len(rows) > 6 else [("all", rows)]
    for label, part in shown:
        _say(f"{label}:")
        for row in part:
            _say("  " + " | ".join(str(c) for c in row))


def _preview(rec, pass_, fn, politeness) -> int:
    from data_integration import parse as parse_mod
    from data_integration.parse import ParseError, SelectorMatchedNothing, parse_table
    from data_integration.validate import validate_table

    outcome = _Adapter(fn, cache=None, refresh=False, politeness=politeness).fetch(rec.url, pass_)
    _say("preview: nothing is stored")
    if outcome.status != status.OK:
        return _result(outcome.status, outcome.detail)
    try:
        table = parse_table(outcome.body, rec.selector)
    except ParseError as exc:
        lines: tuple = ()
        if isinstance(exc, SelectorMatchedNothing):
            try:
                lines = parse_mod.render_outline(parse_mod.outline(outcome.body, urlsplit(rec.url).hostname))
            except Exception:
                lines = ()
        return _result(status.INVALID, str(exc), lines)
    problems = validate_table(table, rec.min_rows)
    if problems:
        return _result(status.INVALID, "; ".join(problems[:5]))
    _result(status.OK)
    _show_rows(table)
    _say(f"response_sha256: {outcome.body_sha256 or hashlib.sha256(outcome.body).hexdigest()}")
    _say(f"baseline: {'present' if _has_baseline(rec) else 'none'}")
    return 0


def _run(args, clock, registry) -> int:
    if args.dry_run and args.preview:
        _say("usage: --dry-run and --preview cannot be combined")
        return 2
    if (args.dry_run or args.preview) and (args.replace or args.accept_baseline):
        _say("usage: --dry-run and --preview cannot be combined with --replace or --accept-baseline")
        return 2
    try:
        rec = load_recipe(args.recipe)
    except RecipeError as exc:
        _say(f"bad recipe: {exc}")
        return 2
    store = ApprovalStore(paths.approvals_dir())
    pass_ = request_access(rec.source, rec.tier, store, clock)
    if isinstance(pass_, Refused):
        return _refuse_gate(pass_.reason, pass_)
    permitted = pass_.permits(rec.url)
    if args.dry_run:
        _say("dry run: nothing is fetched")
        _say(f"request: tier {rec.tier} GET {rec.url} (source {rec.source})")
        _say(_approval_line(pass_))
        _say(f"rate: {_rate(store, rec.source)}")
        _say(f"permitted: {'yes' if permitted else 'no'}")
        _say(f"baseline: {'present' if _has_baseline(rec) else 'none'}")
        return 0 if permitted else _refuse_gate("url_not_approved")
    if not permitted:
        return _refuse_gate("url_not_approved")
    if args.replace:
        from data_integration import provenance

        try:
            has_records = bool(provenance.read_records(rec.symbol, rec.timeframe))
        except (OSError, ValueError):
            _say("--replace needs a readable provenance file")
            return 2
        if not has_records:
            _say("--replace is only allowed when this dataset already has provenance records")
            return 2
    if args.accept_baseline and _has_baseline(rec):
        _say("--accept-baseline is only for a selector without a baseline; a baseline already exists")
        return 2
    fn = (registry if registry is not None else _default_registry())[rec.tier]
    politeness = Politeness(**rec.politeness) if rec.politeness else None
    if args.preview:
        return _preview(rec, pass_, fn, politeness)
    from data_integration import pipeline

    adapter = _Adapter(fn, cache=ResponseCache(tier=rec.tier), refresh=args.refresh, politeness=politeness)
    result = pipeline.run(
        adapter, pass_, url=rec.url, selector=rec.selector, symbol=rec.symbol, timeframe=rec.timeframe,
        min_rows=rec.min_rows, replace=args.replace, accept_baseline=args.accept_baseline, clock=clock,
    )
    code = _result(result.status, result.detail, result.outline)
    if result.rows:
        _say(f"rows: {result.rows}")
    _say(_approval_line(pass_))
    _say(f"rate: {_rate(store, rec.source)}")
    return code


def _rea(args, forwarded, runner) -> int:
    from data_integration.rea import wrapper

    res = wrapper.run_rea(args.command, forwarded, confirm_source=args.confirm_source, findings=args.findings,
                          runner=runner)
    if isinstance(res, wrapper.Refusal):
        _say(f"refused ({res.reason}): {res.detail}")
        return 2
    if res.status == status.OK:
        _say(f"rea: done. evidence: {EVIDENCE_PLACEHOLDER}\\{res.evidence_path.parent.name}\\{res.evidence_path.name}")
        return 0
    if res.detail == "FileNotFoundError":
        _say("REA could not start: Node.js or npx was not found. Install Node.js and try again.")
    elif res.detail == "TimeoutExpired":
        _say("REA timed out and was stopped.")
    else:
        _say("REA failed.")
    return 5


def _dispatch(argv, clock, registry, rea_runner, isatty, input_fn) -> int:
    if argv and argv[0] == "approvals":
        return approval_cli.main(argv[1:], clock=clock, isatty=isatty, input_fn=input_fn)
    forwarded: list[str] = []
    if argv and argv[0] == "rea" and "--" in argv:
        cut = argv.index("--")
        argv, forwarded = argv[:cut], argv[cut + 1:]
    args = _parser().parse_args(argv)
    if args.cmd == "rea":
        return _rea(args, forwarded, rea_runner)
    if args.cmd == "approvals":
        return approval_cli.main([], clock=clock, isatty=isatty, input_fn=input_fn)
    return _run(args, clock, registry)


def main(argv=None, *, clock=_now, registry=None, rea_runner=None, isatty=None, input_fn=input) -> int:
    items = list(sys.argv[1:] if argv is None else argv)
    try:
        return _dispatch(items, clock, registry, rea_runner, isatty, input_fn)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 2)
    except Exception as exc:  # the type name only: messages can carry paths or addresses
        print(f"error: {type(exc).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
