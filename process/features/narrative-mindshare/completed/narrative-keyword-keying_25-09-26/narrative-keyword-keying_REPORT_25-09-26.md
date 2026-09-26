---
name: report:narrative-keyword-keying-closeout
description: "UPDATE PROCESS closeout for the narrative trigger keyword-keying reader fix"
date: 25-09-26
metadata:
  node_type: memory
  type: report
  feature: narrative-mindshare
---

# Narrative Keyword-Keying Fix — Closeout Packet

1. **Selected plan path:** `process/features/narrative-mindshare/completed/narrative-keyword-keying_25-09-26/narrative-keyword-keying_PLAN_25-09-26.md`

2. **Closeout classification:** Ready for UPDATE PROCESS archival

3. **What was finished:**
   - `api/analytics/narrative/trigger.py`: added `_source_history_key(source, category_id, primary_keyword)` and `KEYWORD_KEYED_SOURCES`; `compute_narrative_categories` now reads pytrends/reddit history under `keywords[0]` (matching what the adapters write) and coingecko under `category_id` (unchanged).
   - `api/tests/analytics/test_narrative_trigger.py`: new `TestHistoryKeying` class (3 tests) proving real keyword-keyed rows are read and a category_id-keyed decoy is ignored, without stubbing `cache.read_narrative_series` itself.
   - `api/tests/routers/test_narrative_categories_contract.py`: `_seed_history()` now seeds pytrends/reddit under each category's real `keywords[0]` instead of `category_id`.
   - Before/after diff report (`narrative-keyword-keying_DIFF_25-09-26.md`) generated pre-fixture-touch, showing the real production effect: `trust_weight` 0.4→0.6 and `n_available` 1→3 for all 4 seed categories in both scenarios; no screener badge/`narrative_state` changes in the fixture scenarios (BTC/ETH/HYPE unaffected).
   - User signed off on the diff report; golden fixture `narrative_categories_contract.json` was regenerated and is **byte-identical** to the pre-fix version (confirmed via `git status --short` showing no diff on that file).
   - Amendment note added to `narrative-dashboard_PLAN_24-09-26.md`'s AC-1 section documenting that AC-1's byte-identical guarantee was originally validated against a stubbed path that masked this bug.

4. **Verified vs still unverified:**
   - Verified: full backend suite (381 passed / 3 deselected), full frontend suite (75 passed, 12 files, 0 failed), targeted trigger test, targeted contract test, fixture-unchanged check, mapping-unchanged check (`LEGACY_COIN_CATEGORY_MAP` untouched).
   - Unverified / not applicable: no known gaps recorded (`closeout_classification: CLEAN` per EVL handoff). The diff report itself is a one-shot, human-reviewed artifact, not a regression gate — a future change to `trigger.py` will not automatically re-surface this same before/after comparison (documented in the plan's own "What this coverage does NOT prove").

4b. **Validate-contract compliance:** VALIDATE was run. `## Validate Contract` section is present in the plan file (PVL cycle 2, `Gate: PASS`, `generated-by: outer-pvl`). One PVL supplement cycle ran (cycle 1, CONDITIONAL → gaps folded into checklist) before cycle 2 reached PASS. EVL confirmation run also passed on first attempt (see `results.tsv` row 3).

5. **Cleanup done vs still needed:**
   - Done (this session): closeout packet written, plan status marked complete, task folder archived, `process/context/tests/all-tests.md` and `process/context/all-context.md` updated with the new counts/notes, Tier-1 audits run.
   - Deviation noted for future plans: `pnpm install` from the repo root does not work in this repo (no root `package.json`) — must run `pnpm install --frozen-lockfile` inside `web/`. Now captured in `all-tests.md`.
   - No outstanding TODOs, no uncommitted-but-forgotten files, no stale references identified.

6. **Single best next valid state:** `ENTER UPDATE PROCESS MODE` is this session — after archival, the orchestrator should invoke `vc-git-manager` for the execution commit (trigger.py fix + tests + fixture regen + amendment note), then a separate process commit for the archived task folder + context doc updates.

7. **Commit-checkpoint recommendation:** Execution commit recommended before this process commit — implementation + test changes (`trigger.py`, both test files, the amendment note in the sibling plan) are well-tested (381 backend + 75 frontend passing) and ready for a logical commit. This UPDATE PROCESS session's own changes (task-folder archival, context doc edits, this report) belong in a separate process commit. Per the calling instruction, this agent does NOT commit — the orchestrator commits after this report.

8. **Regression status:** N/A — not a phase program. Full-suite regression run as part of Verification Evidence (AC-5) is the applicable equivalent: `uv run --project api pytest api/ -q` (381 passed/3 deselected) and `pnpm --filter web test` (75 passed) both green, confirming no regression against the rest of the narrative/screener/api surface.

9. **SPEC achievement:** This plan has no separate locked `*_SPEC_*.md` (it is a SIMPLE plan with acceptance criteria inline in the plan file, not a SPEC-governed feature). Scoring against the plan's own Acceptance Criteria instead:
   - AC-1/AC-2 (reader reads pytrends/reddit by `keywords[0]`, coingecko by `category_id`) — **met** (Fully-Automated, `test_narrative_trigger.py::TestHistoryKeying`, part of the 381-pass backend suite).
   - AC-3 (contract test seeds realistic keyword-keyed rows; AC-1 byte-identical guarantee still holds) — **met** (Fully-Automated, `test_narrative_categories_contract.py`, part of the 381-pass suite; fixture confirmed byte-identical).
   - AC-4 (before/after diff report produced before fixture touched) — **met** (Agent-Probe, `narrative-keyword-keying_DIFF_25-09-26.md`, human-reviewed and signed off at the step-7 hard stop).
   - AC-5 (both full suites green) — **met** (Fully-Automated, 381 passed/3 deselected backend; 75 passed/12 files frontend).
   - AC-6 (amendment note in narrative-dashboard plan's AC-1 section) — **met** (Fully-Automated/grep-checkable, confirmed present at narrative-dashboard_PLAN_24-09-26.md:42).
   - No unmet criteria; no backlog NOTEs required for this plan.

**Drift signal scoring:**
- (a) Files touched: 4 tracked files modified + 1 new task folder with several artifacts → +1 (≥1 file), not +2 (well under 10 tracked files)
- (b1) `.claude/`/`.codex`/agent harness file changed: no → +0
- (b2) `README.md`/`AGENTS.md`/`CLAUDE.md`/`process/development-protocols/` changed: no → +0
- (c) 3+ memory-worthy observations: yes (reader/writer key-mismatch pattern, `pnpm install` root-vs-web deviation, PVL supplement→PASS cycle) → +1
- (d) Feature-folder structural change (new task folder created, now archived): yes → +1
- (e) Validate-contract deviation from declared blast radius: no, execution matched the plan exactly → +0

**Total: 3 signals → MEDIUM band.**
"Recommend UPDATE PROCESS -- significant changes detected."

**Next valid state:** `ENTER UPDATE PROCESS MODE` (this session, in progress) → after archival and context updates, orchestrator invokes `vc-git-manager` for the execution commit, then a process commit for this session's artifacts.
