---
name: plan:data-integration-tooling-amendment-a5
description: "Amendment A5 (S-T11, T67): table header outline when required columns are missing"
date: 16-10-26
feature: data-integration-tooling
---

# Amendment A5 (S-T11 table header outline on missing columns, T67)

Follows A4. No "Gate" stamp; PVL covers it.

**Why.** Owner decision 16-10-26: a real digrin.com preview ended `invalid: missing columns: open, high, low, close, volume` and said nothing about the table. Show its headers. Needs T66. Cost 1.5-3 USD (about 103 of 130 spent).

## S-T11: header outline of the selected table (RT2)

**A. Where.** On main missing columns is NOT an exception: `validate_table` returns `["missing columns: ..."]` and `pipeline.run` / `cli._preview` make it INVALID. No new exception; `validate.py` untouched. Both sites detect `problems[0].startswith("missing columns:")`. `parse.py`: ADD pure `table_outline(content, selector, table) -> TableOutline` (frozen; matched, headers, rows, cols; `scrapling.parser` only; no I/O; never raises) and `render_table_outline(o) -> tuple[str, ...]`. `PipelineResult.outline` (exists) is set at that INVALID return from the held `outcome.body`; `_preview` builds the same lines; `_result` prints them under `table outline (nothing stored, only header names are shown):`. Exit 5 unchanged; one fetch; tiers 1-3 all use `outcome.body`; other invalid reasons print none.

**B. Content, bounded.** Built from an allow-list (never filtered after; `_safe` strips no control characters): `tables matched: N` (matches of the selector); for the first match `columns: N`, `rows: N` (data rows) and `headers:` at most 12 cell texts, each built from `[A-Za-z0-9 _./%()-]`, whitespace collapsed, <= 24 chars, empty ones dropped, `(+K more)` for extras. Nothing else: no data rows, no other page text. Bounds as A4 (2 MB, depth); lines go through `_safe`. Limit: odd headers show reduced.
**Guarded:** `try/except Exception`, empty fallback, at BOTH call sites.

**Owned:** `tools/data-integration/src/data_integration/{parse,pipeline,cli}.py` (`validate.py` only if strictly needed: needs_input); new `tools/data-integration/tests/{test_table_outline,test_cli_table_outline}.py`, `tools/data-integration/tests/fixtures_table_outline/*.html`, `api/tests/tooling_guards/test_table_outline_guard.py` (NEW; A4 guard unedited); ONLY the preview line(s) of "New dataset workflow" in `process/context/data-sources/all-data-sources.md`: measure the section on origin/main first, then <= +120 B over that baseline, naming the table outline. **Forbidden:** as A4.

**ACs (all Fully-Automated).**
- AC-37 (`test_table_outline`): fixtures give matched, headers, rows, cols; bounds 12/13 headers, 24/25 chars.
- AC-38 (same): hostile headers (control chars, ESC, long, unicode) never appear raw; lines ASCII; no data row or other page text.
- AC-39 (`test_cli_table_outline` + guard): fake registry per tier; `--preview` and real `run` print the outline, exit 5, one fetch, nothing written; other invalid reasons and CHANGED print none; forced outline error still 5; no I/O names, boundary guard green, forbidden files and old tests unchanged, docs delta <= +120 B.

**Tests.** Red-first; baselines MEASURED on untouched origin/main (expect API >= 1202/1/5, tooling >= 635, guards >= 59); no network. Rollback: revert the PR.

**Planner checklist.** README one line; MASTER-PLAN P9 add T67; SPEC AC-37..39.
