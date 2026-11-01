# backlog-cleanup validate-contract (01-11-26)

Direct-lane worker, docs/comments only. No behaviour change, no data files, no .github/, no dependency files.

Gates:
- G1 Scope: diff touches only comments/docstrings in api/analytics/narrative/exchange_attention.py,
  api/scripts/snapshot_narrative.py, api/analytics/screener_board.py; comment blocks in
  web/components/screener/__tests__/{ScreenerBoard,DrillDownView}.test.tsx; the listed backlog notes;
  the Open Questions lines of process/context/all-context.md (routing block untouched).
- G2 No behaviour change: same pytest set before/after (baseline 117 passed) and vitest on the two
  test files before/after (baseline 19 passed); full `pnpm test` after.
- G3 validate-backlog-notes.mjs not worse on edited notes.
- G4 Facts cited are re-verified (workflow crons read, `gh run list` schedule runs, test line refs).
- G5 Draft PR on claude/backlog-cleanup; Linux CI green.
