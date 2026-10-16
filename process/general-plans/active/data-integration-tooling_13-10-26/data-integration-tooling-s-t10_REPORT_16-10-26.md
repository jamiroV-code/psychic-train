---
name: report:data-integration-tooling-s-t10
description: "Worker report T66 (S-T10): page outline on selector miss"
date: 16-10-26
---

# Report T66 (S-T10)

## 1 Task ID
T66, slice S-T10, branch claude/t66-dit-s-t10-outline, base origin/main cbb1e1b.

## 2 Outcome
Complete; all gates green. Draft PR opened against main; not merged.

## 3 Summary
- parse.py: `SelectorMatchedNothing(ParseError)` raised at the old site (same message); pure `outline(content, page_host=None)` and `render_outline` (allow-list built, bounds as in A4 B).
- pipeline.py: `PipelineResult.outline` (last field, default `()`), set only at the INVALID return for a selector miss, from `outcome.body`; call wrapped in try/except Exception.
- cli.py: `_result(st, detail, outline=())` prints the header plus indented lines; `_preview` and `_run` pass them; preview call wrapped in try/except Exception. Exit codes unchanged.
- Docs: one line in "New dataset workflow", section 3397 B on origin/main, now 3477 B (+80 B). The existing test_docs_ac27 caps that block at 3500 B, so the real headroom was +102 B, tighter than the +200 B in A4.
- Known limits: counts and numeric-heavy candidates are heuristics; page text is deliberately not shown, so odd pages may still need a browser look. Only the first 2 MB is parsed. The forbidden-file diff is a worker gate, not a test.

## 4 Files changed
tools/data-integration/src/data_integration/{parse,pipeline,cli}.py; tests/{test_page_outline,test_cli_outline}.py; tests/fixtures_outline/{rich,hostile,plain}.html; api/tests/tooling_guards/test_outline_guard.py; process/context/data-sources/all-data-sources.md; this report.

## 5 Commits
One commit on the task branch (SHA in the PR).

## 6 Tests run (UTC 2026-10-16, base SHA cbb1e1b)
- Base, untouched origin/main: tooling 601 passed, 3 deselected; guards 56 passed; API 1199 expected (full API baseline not run separately: the run after my change gave 1202 = 1199 + 3 new guards, no failures).
- Red-first (tests present, src stashed): test_page_outline collection error (import of the new names); test_cli_outline 9 failed, 3 passed; guard file 2 failed, 1 passed.
- After: tooling `pytest tools/data-integration/tests -q`: 635 passed, 3 deselected (601 + 34 new). Guards: 59 passed (56 + 3). API full: 1202 passed, 1 skipped, 5 deselected (1199 + 3).
- `git diff --exit-code api/uv.lock api/pyproject.toml`: clean. `git diff --check origin/main...HEAD`: clean. Forbidden files: no diff.

## 7 Tests NOT run
No real scrape, no network, no npx/REA, no scrapling or playwright install, no approval record written to a real store.

## 8 Deviations
- Docs headroom bound by the existing 3500 B test (see 3), not +200 B.
- `PageOutline` has an `ok` flag; `render_outline` returns `()` when it is false.
- hostile.html contains one non-ASCII character on purpose (title test).
- Full API baseline was not measured separately on untouched main (see 6).

## 9 Blockers
None.

## 10 Follow-up
Planner checklist: README line, MASTER-PLAN P9 add T66, SPEC AC-33..36. Owner re-runs the two real previews to see the outline.

## 11 Context cost
About 31,000 B of the named files, plus the docs section (3.4 KB) and the existing docs test, read to resolve the 3500 B cap.
