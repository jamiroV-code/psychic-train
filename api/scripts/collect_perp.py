"""Perp collector (RFC-001 Stage 3).

    uv run --project api python api/scripts/collect_perp.py --job hl-snapshot
    uv run --project api python api/scripts/collect_perp.py --job hl-snapshot --dry-run
    uv run --project api python api/scripts/collect_perp.py --coverage [--days N]

Exit codes (no CLI flag or exit-code meaning changes in later updates):
    0  every coin written, no problems
    1  nothing written (fetch failed, lock held, write failed)
    2  written but flagged (a coin missing, an expected key absent, a refused
       coin, a release problem after the write, or a left-behind take-over guard)
Argument errors exit 2 from argparse before any run starts. A collection run always writes
the sidecar with the exit code it produced; --dry-run and --coverage write no sidecar.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import argparse
import datetime as dt
import json

import httpx

from api.data import cache
from api.data.perp import hl_snapshot as hs
from api.data.perp import textlog
from api.data.perp.paths import hl_snapshot_path, perp_root

JOBS = ("hl-snapshot",)
EXIT_OK, EXIT_NOTHING, EXIT_FLAGGED = 0, 1, 2
_UTC = dt.timezone.utc
RUN_LOCK_STALE_SECONDS = 600
PROBLEM_GUARD_LEFT = "takeover-guard-left"


def _utc(now: dt.datetime | None) -> dt.datetime:
    if now is None:
        return dt.datetime.now(_UTC)
    if now.tzinfo is None:
        return now.replace(tzinfo=_UTC)
    return now.astimezone(_UTC)


def _stamp(when: dt.datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _sidecar_path(job: str) -> Path:
    return perp_root() / f"_last_run_{job}.json"


def _guard_state(coin: str, month: str) -> dict[str, bool]:
    path = hl_snapshot_path(coin, month)
    return {"lock": textlog.lock_path(path).exists(), "guard": textlog.guard_path(path).exists()}


def _run_data_path() -> Path:
    """The whole-run lock is the textlog lock of `_locks/hl-snapshot`, so its
    lock file is `hl-snapshot.lock` and its guard is `hl-snapshot.lock.takeover`."""
    return perp_root() / "_locks" / "hl-snapshot"


def run_target() -> Path:
    return textlog.lock_path(_run_data_path())


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Perp collector")
    parser.add_argument("--job", choices=JOBS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--coverage", action="store_true")
    parser.add_argument("--days", type=int, default=2)
    args = parser.parse_args(argv)
    if not args.coverage and args.job is None:
        parser.error("--job is required unless --coverage is given")
    return args


def coverage_report(days: int, now: dt.datetime | None = None) -> int:
    end = _utc(now).date()
    start = end - dt.timedelta(days=days - 1)
    for coin in hs.COINS:
        for day, present in hs.coverage(coin, start, end):
            print(f"{day.isoformat()} {coin} {'ok' if present else 'gap'}")
    for month in hs._months(start, end):
        for coin in hs.COINS:
            state = _guard_state(coin, month)
            print(f"{coin} {month} lock={_word(state['lock'])} guard={_word(state['guard'])}")
    run_guard = textlog.guard_path(_run_data_path())
    print(f"run-lock {run_target()} guard={_word(run_guard.exists())} guard-path={run_guard}")
    return EXIT_OK


def _word(flag: bool) -> str:
    return "present" if flag else "absent"


def _fetch_and_write(
    client: httpx.Client | None, now: dt.datetime | None, handle: textlog.Handle
) -> tuple[int, list[str], int]:
    result = hs.fetch_snapshot(client=client, now=now)
    problems = list(result.problems)
    if result.status != "ok":
        return EXIT_NOTHING, problems, 0
    written, _ = hs.write_snapshot(result, handle, problems)
    if written == 0:
        return EXIT_NOTHING, problems, 0
    if problems or written < len(hs.COINS):
        return EXIT_FLAGGED, problems, written
    return EXIT_OK, problems, written


def _collect(job: str, client: httpx.Client | None, now: dt.datetime | None) -> int:
    started = _utc(now)
    run_problems: list[str] = []
    code, problems = EXIT_NOTHING, []
    try:
        _run_data_path().parent.mkdir(parents=True, exist_ok=True)
        with textlog.locked(_run_data_path(), wait_seconds=0.0, takeover=True,
                            stale_seconds=RUN_LOCK_STALE_SECONDS) as handle:
            run_problems = handle.problems
            code, problems, _ = _fetch_and_write(client, now, handle)
    except textlog.LockHeld as held:
        code, problems = EXIT_NOTHING, [held.reason, *held.problems]
    except OSError:
        code, problems = EXIT_NOTHING, ["run-lock-failed"]
    problems.extend(run_problems)
    run_guard = textlog.guard_path(_run_data_path())
    if PROBLEM_GUARD_LEFT not in problems and run_guard.exists():
        problems.append(PROBLEM_GUARD_LEFT)
    if code == EXIT_OK and problems:
        code = EXIT_FLAGGED
    finished = _utc(now) if now is not None else dt.datetime.now(_UTC)
    month = _stamp(started)[:7]
    guard_paths = {str(textlog.guard_path(hl_snapshot_path(coin, month))): _guard_state(coin, month)
                   for coin in hs.COINS}
    guard_paths[str(run_guard)] = {"guard": run_guard.exists(), "lock": run_target().exists()}
    payload = {"job": job, "started_utc": _stamp(started), "finished_utc": _stamp(finished),
               "exit_code": code, "problems": problems, "lock_guard": guard_paths}
    try:
        path = _sidecar_path(job)
        path.parent.mkdir(parents=True, exist_ok=True)
        cache._atomic_write_json(payload, path)
    except OSError:
        print("sidecar could not be written", file=sys.stderr)
        code = max(code, EXIT_FLAGGED)
    return code


def _dry_run(client: httpx.Client | None, now: dt.datetime | None) -> int:
    result = hs.fetch_snapshot(client=client, now=now)
    print(json.dumps({
        "status": result.status,
        "collected_at_utc": result.collected_at_utc,
        "coins": result.coins,
        "problems": result.problems,
    }, indent=2, sort_keys=True))
    return EXIT_OK if result.status == "ok" else EXIT_NOTHING


def run(argv: list[str], client: httpx.Client | None = None, now: dt.datetime | None = None) -> int:
    args = _parse(argv)
    if args.coverage:
        return coverage_report(args.days, now)
    if args.dry_run:
        return _dry_run(client, now)
    return _collect(args.job, client, now)


def main(argv: list[str] | None = None) -> int:
    return run(sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
