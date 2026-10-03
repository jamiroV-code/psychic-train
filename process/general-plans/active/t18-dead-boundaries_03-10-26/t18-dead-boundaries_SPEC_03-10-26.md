---
name: spec:t18-dead-boundaries
description: "Worker brief T18 (proposed, not approved): remove dead write/read_confirmed_boundaries and confirmed_boundaries_path from api/data/cache.py after proving no runtime caller (RT3)"
date: 03-10-26
feature: general
---

# T18 - remove dead `write_confirmed_boundaries` / `read_confirmed_boundaries` (worker brief)

**TL;DR:** `cache.py` still holds three legs helpers that no runtime code calls. Prove that again at the start, delete them and the tests that only exercise them, keep everything else green. Status `proposed`: no worker may start until the user approves this task and VALIDATE passes.

Registry row: T18 in `process/MASTER-PLAN.md` (workers do not edit it). Envelope is written after VALIDATE and approval (`t18-dead-boundaries_REF_03-10-26.md`).

## Evidence so far (planner, read-only grep on `5676ceb`, 03-10-26)

- Defined in `api/data/cache.py`: `confirmed_boundaries_path`, `write_confirmed_boundaries`, `read_confirmed_boundaries` (section "RFC-002: confirmed leg boundaries"; the section comment goes too).
- Runtime callers in `api/` (outside tests): none. `api/routers/regime.py` and `api/models/regime.py` use a *field* called `confirmed_boundaries` on `CurrentLegState`, a different thing; `api/scripts/backtest_leg_boundaries.py` uses a dict key of the same name, not the functions. Keep all three.
- Test callers (must go with the functions): `api/tests/data/test_cache_atomic_writes.py` (parametrised entry `write_confirmed_boundaries` near line 205; `test_round_trip_confirmed_boundaries` near line 301) and `api/tests/data/test_cache_timezone.py` (`test_confirmed_boundaries_datetimes_read_back_in_utc` near line 201).
- Documentation mention (NOT owned here): `deploy/README.md` lines ~104-105 and `api/tests/deploy/test_deploy_config_shape.py::test_readme_migration_says_legs_cache_is_not_needed` assert the names appear in README text. They do not import the functions, so they stay green after removal. Record the stale wording in the report for R12 (owner of both files) to reword.
- Static search misses dynamic use (`getattr`, string dispatch): the worker also greps `api/`, `web/`, `deploy/`, `.github/` for the bare strings `confirmed_boundaries_path` and `legs/confirmed`.

## Scope

1. Re-run the proof greps first; if any non-test caller appears, STOP at `review` and report.
2. Delete the three functions and their section comment from `cache.py`; delete only the three test items named above (keep the other parametrised cases and tests untouched).
3. Do not touch the cache data directory `api/data/cache/legs/` (data, forbidden).

## Acceptance

- The three names are absent from `api/data/` and from the two test files; the grep proof output is in the report.
- `uv run --project api pytest api/ -q` passes with the pre-change count minus the removed tests (state both numbers); contract snapshots unmodified.

## Ownership

- Owned: `api/data/cache.py`, `api/tests/data/test_cache_atomic_writes.py`, `api/tests/data/test_cache_timezone.py`, this task folder.
- Forbidden: everything else, notably `deploy/**`, `api/tests/deploy/**`, `api/data/cache/**`, `CLAUDE.md`, `AGENTS.md`, `README.md`, `.claude/**`, `.github/**`, `process/MASTER-PLAN.md`, validators.
- Overlap check: no other registry task owns these files (T21 `cache.py` refactor is `proposed`, depends on everything merged; do not run both).

## Tests

Tier RT3 (operating-instructions.md: `cache.py` is shared logic): `uv run --project api pytest api/ -q`; `pnpm --filter web test`; `pnpm --filter web exec tsc --noEmit`; `cd web && pnpm build:islands`. Full-suite budget 2. Quick pre-check: `uv run --project api pytest api/tests/data -q`.

## Stop and report at `review` if

A non-test caller is found, any test outside the three named items fails, or the diff touches an unowned file.
