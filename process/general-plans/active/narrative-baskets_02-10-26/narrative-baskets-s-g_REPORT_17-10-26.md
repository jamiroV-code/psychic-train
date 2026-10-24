# T81 S-G agent part report

## 1 Task ID
T81 (P5 S-G agent part), branch claude/t81-p5-s-g-probe-recorder.

## 2 Outcome
done. Draft PR against main; not merged.

## 3 Summary
- `api/scripts/record_probe.py`: reads the attention store only (no fetch), counts completed UTC days per source, writes `probe_records.json` atomically (`cache._atomic_write_json`) with state, coins_checked, coins_ok, max_days, as_of. `--dry-run` writes nothing; `--state SOURCE=STATE` records a hand-observed state (not-probed removes the record). Existing records are kept. No keys, tokens or IPs are written or printed.
- Tests: `api/tests/scripts/test_record_probe.py`, 10 tests, tmp_path only; real cache tree and real probe_records.json hashed before/after.
- Owner guide (3,3xx B, ASCII): `narrative-baskets-owner-guide_17-10-26.md`.
- Known limits: state is derived from the store, so `no-article` and `capped` are only recorded via `--state`; `universe` and `categories` snapshots are not probed; the per-source "comparable across coins / terms" probes stay owner judgement; real `probe_records.json` stays `{}` until the owner runs it.

## 4 Files changed
api/scripts/record_probe.py; api/tests/scripts/test_record_probe.py; the owner guide; this report.

## 5 Commits
Red tests commit, then implementation, guide and report commit.

## 6 Tests run
- Red: `UV_FROZEN=1 uv run --project api pytest api/tests/scripts/test_record_probe.py -q` -> collection error (script missing), 10 tests unrunnable.
- Baseline origin/main: `UV_FROZEN=1 uv run --project api pytest api/ -q` -> 1377 passed, 1 skipped, 5 deselected.
- After: same command -> 1387 passed, 1 skipped, 5 deselected (baseline + 10). UTC 2026-10-17.
- Four tracked coingecko parquet files restored before commit.

## 7 Tests NOT run
Any live provider or live refresh (forbidden).

## 8 Deviations
None. The red commit's tests were later adjusted for a fixture directory (records file in its own subdir) before the implementation commit.

## 9 Blockers
None.

## 10 Follow-up
Owner runs the guide; planner decides whether `universe`/`categories` need a probe record.

## 11 Context cost
CLAUDE.md, envelope, plan ranges, registry/store/refresh_attention/xsearch greps, report headings; within cap.
