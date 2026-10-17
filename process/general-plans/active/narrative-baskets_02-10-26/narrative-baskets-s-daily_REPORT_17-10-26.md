# T84 report: P5 daily attention refresh

## 1 Task ID
T84 (P5 daily refresh), branch `claude/t84-p5-daily-refresh`.

## 2 Outcome
Done. One new workflow plus a guard test; full api suite green.

## 3 Summary
`.github/workflows/attention-refresh.yml` runs daily at 07:23 UTC (and via workflow_dispatch). Steps: checkout, setup-uv (same pins as narrative-snapshot), `uv sync`, record store state, `refresh_attention.py` (default sources), `--sources categories`, optional X, verify, commit. Permissions `contents: write` only; concurrency group `attention-refresh`, no cancel.

Fail loudly: the verify step prints one `summary <source>: ...` line per source and exits 1 if any default source (or categories) errored or shows 0 ok series, or if wikipedia/coingecko stored no new completed UTC day. The commit step still runs after a failure so partial good data is kept. X is optional: runs only if secret `X_BEARER_TOKEN` exists and repo variable `ATTENTION_X_LIVE=1`; the secret appears only in the gate and X steps' env and is never echoed. record_probe.py is not run.

Known limits:
- A manual re-run on the same UTC day fails the "new completed day" check by design.
- `api/data/cache/*` is gitignored, so the commit step uses `git add -f api/data/cache/attention/` (no .gitignore edit).
- The verify step was exercised offline on a fake failing log only; the workflow itself was never run.
- dispatch input `categories` defaults to true; schedule always runs categories.

Owner must do once: (1) merge the PR; (2) run the workflow once via Actions > Attention daily refresh > Run workflow and check the summary lines; (3) optional X: add repo secret `X_BEARER_TOKEN` and repo variable `ATTENTION_X_LIVE=1` (leave unset until 90 own days).

## 4 Files changed
- .github/workflows/attention-refresh.yml (new)
- api/tests/tooling_guards/test_attention_workflow_guard.py (new, 11 tests)
- this report

## 5 Commits
One commit on the task branch (see PR).

## 6 Tests run
- `UV_FROZEN=1 uv run --project api pytest api/ -q`: 1398 passed, 1 skipped, 5 deselected (baseline 1387 + 11 new; the new tests were red first: 10 failed before the workflow existed). 2026-10-17, base origin/main.
- Guard test alone: 11 passed.
- Gates below run before commit.

## 7 Tests NOT run
Live workflow, live refresh_attention.py, any network call.

## 8 Deviations
`git add -f` instead of a .gitignore change. Baseline not measured separately on untouched main (derived: total minus new tests).

## 9 Blockers
None.

## 10 Follow-up
- record_probe.py skipped: it is non-interactive but writes the owner's `api/data/attention/probe_records.json` (outside the cache dir), so auto-recording daily would overwrite hand-set states. Decide separately.
- Consider un-ignoring `api/data/cache/attention/` in .gitignore so the force-add is unnecessary.

## 11 Context cost
About 25 KB of files read (within the 36,000 B cap), no subagents.
