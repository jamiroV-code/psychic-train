---
name: plan:data-integration-tooling-amendment-a4
description: "Amendment A4 (S-T10, T66): page outline printed when a selector matches nothing; separate file because the planner shell failed"
date: 16-10-26
feature: data-integration-tooling
---

# Amendment A4 (S-T10 page outline on selector miss, T66)

Companion to data-integration-tooling_PLAN_14-10-26.md (Amendments A1-A3 live there). No "Gate" stamp here; PVL 009 covers it.

**Why.** Owner decision 16-10-26. Two real previews ended `invalid: selector matched nothing: table` and showed nothing about the page. W10; needs T59, T62, T65. Cost 2-4 USD (total 103.8-105.8 of 130).

## S-T10: outline of the fetched page (RT2)

**A. Where.** `parse.py`: `SelectorMatchedNothing(ParseError)` raised at line 25 (message unchanged); pure `outline(content, page_host=None) -> PageOutline` (frozen plain tuples/ints; `scrapling.parser` only; no I/O; never raises) and `render_outline(o) -> tuple[str, ...]`. No second fetch: `PipelineResult.outline: tuple[str, ...] = ()`, set ONLY at the line-58 INVALID return when `isinstance(exc, SelectorMatchedNothing)`, from the `outcome.body` already held. `cli.py`: `_result(st, detail, outline=())` prints `page outline (nothing stored, page text is not shown):` plus lines; `_preview` calls `outline` on `outcome.body` in its ParseError branch; `_run` passes `result.outline`. Statuses and exit codes unchanged (INVALID 5). Tiers 1-3 all reach parse via `outcome.body`. None for other invalid reasons or the baseline CHANGED/UNCERTAIN branch. Line numbers come from a possibly stale checkout: the worker re-counts on origin/main.

**B. Content, bounded.** Title (printable ASCII, <= 120). Counts: table pre ul ol canvas svg iframe form script img. <= 10 external script/iframe HOST NAMES (lowercase `[a-z0-9.-]`, no path/query). <= 10 same-host links ending .csv/.json/.xlsx/.txt (path only, `[A-Za-z0-9_./-]`, no leading slash so `_safe` keeps them). <= 15 candidates `tag#id` or `tag.class` (token `[A-Za-z0-9_-]{1,40}`) for elements with >= 20 numeric-looking tokens (`^[+-]?[$]?\d[\d,]*(\.\d+)?%?[kKmMbB]?$`): tag, token, count, never text; html/body skipped; an ancestor with the same count as a candidate descendant is dropped. Total body bytes. Cap: 2,000 id/class elements, 20,000 chars of text each. Every line through `_safe`.

**C. Limits.** Counts and candidates are heuristics; page text is deliberately not shown, so odd pages may still need a browser look.

**Owned:** `tools/data-integration/src/data_integration/{parse,pipeline,cli}.py`; new `tools/data-integration/tests/{test_page_outline,test_cli_outline}.py`, `tools/data-integration/tests/fixtures_outline/*.html`, `api/tests/tooling_guards/test_outline_guard.py`; ONLY 1-2 preview lines of "New dataset workflow" in `process/context/data-sources/all-data-sources.md` (delta <= +200 B, section <= 3,500 B; little room after A3: shorten own wording, else `needs_input`). **Forbidden:** all else, esp. `types.py`, `status.py`, `validate.py`, `adaptive.py`, `gate.py`, `fetch_tier*.py`, existing tests (one failing: `needs_input`), `CLAUDE.md`, `.claude/`, `.github/`, `deploy/`, `decisions.md`, `process/MASTER-PLAN.md`.

**ACs.** AC-33 (`test_page_outline`; Fully-Automated): fixtures give title, counts, hosts, links, candidates, size; exact bounds: 10 hosts of 10 and of 11, same for links, 15 candidates of 16, 20 tokens listed and 19 not. AC-34 (same; Fully-Automated): hostile ids, classes, titles, hosts, paths never appear raw; all lines ASCII; page text and other attribute values never appear. AC-35 (`test_cli_outline`; Fully-Automated): fake registry per tier, `--preview` and real `run` on a selector miss print the outline, exit 5, one fetch, nothing written by the outline; other invalid reasons and CHANGED print none (5/6); a forced outline error still gives 5. AC-36 (guard, git diff, docs; Fully-Automated): outline code has no I/O or network names, import-boundary guard green, forbidden files unchanged, docs <= 3,500 B and name the outline.

**Tests.** Red-first; baselines MEASURED on untouched origin/main (expect API >= 1199/1/5, tooling >= 601, guards >= 56); no network. **Risks.** Element cap bounds time; sanitised tokens only. Rollback: revert the PR.

**Planner checklist.** README one line; MASTER-PLAN P9 add T66; SPEC AC-33..36.

**Envelope hint.** Read about 31,000 B: CLAUDE.md 13,443; envelope; Common 58-75 of the main plan; this file; `parse.py`; `pipeline.py` 20-24, 46-65; `cli.py` 54-62, 117-121, 142-161, 211-221; docs preview line.
