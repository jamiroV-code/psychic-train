# S-T11 report (T67)

1. Task ID: T67 (S-T11), Amendment A5 (AC-37..AC-39). Branch claude/t67-dit-s-t11-table-headers.

2. Outcome: done. All gates green; draft PR opened, not merged.

3. Summary
- `parse.table_outline` / `render_table_outline` (pure, never raise): tables matched, columns, data rows, up to 12 headers (allow-list, 24 chars, `(+K more)`).
- Both call sites (`pipeline.run`, `cli._preview`) build the outline when `problems[0]` starts with `missing columns:`, wrapped in try/except Exception. `cli._result` prints it under `table outline (nothing stored, only header names are shown):`. Exit 5, one fetch, nothing written.
- Docs: one sentence reworded in "New dataset workflow" (+2 B over 3477 B baseline; an older test caps the block at 3500 B).
- Known limits: odd headers show reduced (non-allow-list characters are dropped, e.g. `$`, accents, so `Price ($)` shows as `Price ()`; ESC is removed but the printable rest such as `[31m` stays); only the first matched table is described; CHANGED path is covered by reusing the rich selector-miss page, since a missing-columns page fails validation before the baseline check.

4. Files changed: parse.py, pipeline.py, cli.py (tools/data-integration/src/data_integration); tests test_table_outline.py, test_cli_table_outline.py, fixtures_table_outline/*.html; api/tests/tooling_guards/test_table_outline_guard.py; all-data-sources.md (one sentence); this report.

5. Commits: two commits on the branch (see PR).

6. Tests run (UTC 2026-10-16, base abd78e8)
- Baseline on untouched main: tooling 635 passed; guards 59; API 1202 passed / 1 skipped / 5 deselected.
- Red first: test_table_outline collection error (import), test_cli_table_outline 9 failed / 2 passed, guard 2 failed.
- After (14:46Z): tooling `pytest tools/data-integration/tests` 651 passed / 3 deselected; guards 61 passed; API 1204 passed / 1 skipped / 5 deselected. New: 16 tooling tests, 2 guard tests.
- Follow-up commit (planner clarifications: headers from parsed columns, 200-char pre-filter cut, O(n) stop at 12, 10,000-cell and 5,000-char tests): tooling 652 passed, guards 61 passed; full API suite not re-run (1204 passed before it; the change is tooling-only).
- `git diff --exit-code api/uv.lock api/pyproject.toml` clean; `git diff --check` clean.

7. Tests NOT run: any real fetch, scrape, browser or REA (forbidden).

8. Deviations: first docs edit (+57 B) broke the existing `test_docs_ac27` 3500 B cap; reworded instead (+2 B). Docs baseline is 3477 B, not A4's 3397 B.

9. Blockers: none.

10. Follow-up: the owner can re-run the digrin preview to see the real headers. Planner checklist items (README line, MASTER-PLAN P9 T67, SPEC AC-37..39) are not done here (forbidden files).

11. Context cost: read CLAUDE.md, A5, parse.py, pipeline/cli excerpts, docs section, plus test_cli_outline.py and test_outline_guard.py as templates; test_approval_cli_cloud.py excerpt.
