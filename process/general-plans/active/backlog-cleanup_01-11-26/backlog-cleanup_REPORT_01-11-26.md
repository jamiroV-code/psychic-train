## 1 Task ID
backlog-cleanup (branch `claude/backlog-cleanup`, worktree `C:/Users/jamir/.herdr/worktrees/my_site/wt-backlog-cleanup`, draft PR #216)

## 2 Outcome
done

## 3 Summary
Changes are docs and comments only. No behaviour change.

| # | Item | Result |
|---|---|---|
| 1 | trigger.py comments (exchange_attention.py:5, snapshot_narrative.py:17-18, 23-25, ~145) | FIXED. exchange_attention.py:5 was already accurate ("are removed"); its wording only got "in P5" added. In snapshot_narrative.py the docstring also had a stale `trigger.compute_narrative_categories` reference at 23-25, so that was reworded too. |
| 2 | screener_board.py:184 "adapter's own verdict" | FIXED. Now reads "adapter's reported data status". |
| 3 | pytrends note cron | FIXED. `17 18` corrected to `47 12 * * *` after reading the workflow. Added the status line and updated the TL;DR. |
| 4 | all-context Open Questions | FIXED. Removed the tripwire line: the coverage now exists at test_mapping.py:64-68 and test_no_narrative_verdict_fields.py:36-39. Rewrote the crons line with the observed evidence. Added a note to the pytrends line saying the partial-hour fix exists in code and that it was not re-checked whether this fix explains the l2s/rwa zeros. The routing block is untouched. |
| 5 | cron-firing note | FIXED. Added a status line: all 6 workflows ran from 27 to 31 Oct, all success, created 4.5-7 h after their slot. The 10 h budget is NOT evidenced beyond about 7 h. |
| 6 | SANDBOX NOTE in ScreenerBoard/DrillDownView tests | FIXED. The note's condition is met: CI vitest is green on main and on #216, and the files pass locally 19/19. The blocks are replaced by one dated "verified" line, and the note status is set to RESOLVED for those two files. |

## 4 Files changed
api/analytics/narrative/exchange_attention.py, api/scripts/snapshot_narrative.py, api/analytics/screener_board.py (comments only); web/components/screener/__tests__/ScreenerBoard.test.tsx, DrillDownView.test.tsx (comments only); process/context/all-context.md (Open Questions lines 180-184 only); process/general-plans/backlog/{pytrends-partial-hour-zeros_NOTE_27-09-26, pipeline-cron-firing-confirmation_NOTE_01-10-26, sandbox-note-reconciliation_19-09-26}.md; this task folder (validate-contract, report).

## 5 Commits
On `claude/backlog-cleanup` from origin/main e98e05c1: 8cff1196 (contract), 8177de79 (api comments), cf83cd41 (test comments + sandbox note), e87f00b2 (notes + all-context), plus this report commit.

## 6 Tests run
- `UV_FROZEN=1 uv run --project api pytest -q api/tests/analytics/{test_exchange_attention,test_mapping,test_no_narrative_verdict_fields,test_history}.py api/tests/scripts/test_snapshot_narrative.py api/tests/routers/{test_screener,test_screener_freshness_payload,test_screener_gain_contract,test_screener_no_verdict_contract,test_screener_rsi,test_spaghetti}.py`: 117 passed before the edits and 117 passed after (2026-11-01 ~15:20-15:30 UTC, local Windows).
- `pnpm exec vitest run` on the 2 test files: 19/19 before. `pnpm test` (web) after: 595/596; the only failure is the known local quirk in plot-ink.test.ts.
- `node .claude/skills/vc-audit-plans/scripts/validate-backlog-notes.mjs process/general-plans/backlog`: output is byte-identical before and after. The 3 edited notes each fail 3 frontmatter checks that already failed on main (`status`/`item`/`reason`). So the result is not worse, but those notes are still invalid against the validator.
- CI on #216 head: "api — pytest" pass (5m6s), "web — vitest, tsc, island build" pass (1m1s).
- Fact checks: `gh run list --workflow <file> --event schedule -L 5` for all 6 workflows; read the cron lines in .github/workflows/*.yml (read only).

## 7 Tests NOT run
Full api suite locally. CI on Linux covers it, and the change touches comments only.

## 8 Deviations
- The removed tripwire Open Question was not moved into context-changelog.md (minimal-edit instruction).
- Delay evidence: the envelope said 4-6 h. Measured `createdAt` minus the cron slot is 4.5-6.2 h for the five snapshots and 6.3-7.0 h for attention-refresh (07:23 slot). The notes give the measured figures.

## 9 Blockers
None. Registry update request: backlog-cleanup -> review (CI green, owner merge pending).

## 10 Follow-up
- api/scripts/backfill_pytrends_history.py:18 still says "the same one `trigger.py` passes". It is the same kind of stale comment but was outside this envelope, so it was left alone.
- The 3 edited notes (and others) have no frontmatter fields matching validate-backlog-notes.mjs. Reconciling them needs its own task.
- Other files in web/components/screener/__tests__/ may still carry SANDBOX NOTEs. They were not audited.

## 11 Context cost
About 15 files read in part; roughly 40k tokens. Tools: read/edit/write/bash/grep/glob, gh CLI.
