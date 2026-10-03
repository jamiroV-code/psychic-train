---
name: spec:t29-backtest-report-dir
description: "Worker brief T29 (approved 03-10-26): point REPORT_DIR in api/scripts/backtest_leg_boundaries.py at completed/ instead of active/ (RT2, one path segment)"
date: 03-10-26
feature: general
---

# T29 - backtest script report dir: `active` -> `completed` (worker brief)

**TL;DR:** T19 moved `momentum-screener_17-09-26` to `process/general-plans/completed/`. `api/scripts/backtest_leg_boundaries.py` line 68 still writes its report into the `active/` path and would recreate a stray `active/momentum-screener_17-09-26/` folder on the next manual run. Change that one path segment and nothing else.

Registry row: T29 in `process/MASTER-PLAN.md` (workers do not edit it). Approved by the user 03-10-26. Envelope: `t29-backtest-report-dir_REF_03-10-26.md`.

## Evidence (planner, 03-10-26, main `487fa65`)

- Line 68: `REPORT_DIR = Path(__file__).resolve().parents[2] / "process" / "general-plans" / "active" / "momentum-screener_17-09-26"`. Used at lines 206-207 (`mkdir(parents=True, exist_ok=True)`, then the atomic write of `leg-boundary-backtest-report-<ts>.json`).
- Nothing calls the script (manual run only: `uv run python scripts/backtest_leg_boundaries.py --cycle 2017`); no test imports it (`git grep -ln backtest_leg -- api/tests` is empty). The only other textual hit for the name is a comment at `api/scripts/compare_composite_variants.py:156` (allowed; any import, call, test or workflow hit means STOP).
- Not in scope: `api/scripts/compare_composite_variants.py` points at `liqtide-snapshot-tooling_20-09-26`, which is still in `active/`. The 18 files that still name the old momentum-screener path stay as history (user decision 03-10-26).

## Scope

Replace the segment `"active"` with `"completed"` on line 68. No other line changes.

## Acceptance

- `git diff origin/main..HEAD -- api/scripts/backtest_leg_boundaries.py` shows exactly one changed line (line 68), `active` -> `completed`.
- The file still parses; `git grep -n 'general-plans" / "active"' -- api/scripts/backtest_leg_boundaries.py` is empty.
- `git grep -n 'momentum-screener_17-09-26' -- api` lists only line 68 (with `completed`).
- Full api pytest unchanged: pass count equal before and after.

## Ownership

Owned: `api/scripts/backtest_leg_boundaries.py`, this task folder. Forbidden: everything else, notably CLAUDE.md, AGENTS.md, README.md, `.claude/**`, `.github/**`, `deploy/**`, `web/**`, `api/data/cache/**`, `process/MASTER-PLAN.md`, `process/context/**`, `process/archive/**`, `process/development-protocols/**`, other `api/scripts/*`.

## Tests

Tier RT2 (operating-instructions.md: one module in `api/`; no test file exists for the script, so no touched-test run). Gates: (1) syntax: `uv run --project api python -c "import ast; ast.parse(open('api/scripts/backtest_leg_boundaries.py').read())"`; (2) grep proofs above; (3) `uv run --project api pytest api/ -q` once after the edit, count equal to a count read from CI or an optional baseline; (4) CI green on head. Web gates not required at RT2. Full-suite budget 1.

## Stop and report at `review` if

The line is not as described, a test or caller references the script, the diff touches a second line or an unowned file.
