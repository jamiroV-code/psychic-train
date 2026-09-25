---
name: plan:narrative-keyword-keying
description: "Fix trigger.py reading pytrends/reddit narrative cache by category_id instead of the keyword key adapters actually wrote under"
date: 25-09-26
feature: narrative-mindshare
---

# Narrative Trigger Keyword-Keying Fix — SIMPLE Plan

Date: 25-09-26
Status: ✅ COMPLETE — EXECUTE + EVL passed (381 pytest passed/3 deselected, 75 vitest passed);
fixture confirmed byte-identical after user sign-off; archived via UPDATE PROCESS 25-09-26. See
`narrative-keyword-keying_REPORT_25-09-26.md` for the closeout packet.
Complexity: SIMPLE

## Phase Completion Rules

- This is a SIMPLE plan (single work session, no phase split). "Done" = all Implementation
  Checklist steps complete, step 7 hard-stop sign-off obtained, and both Verification Evidence
  gates green.
- Step 7 is a mandatory hard stop: EXECUTE must not proceed past it without explicit user
  sign-off on the diff report.

## Overview

`compute_narrative_categories` in `api/analytics/narrative/trigger.py` fetches pytrends/reddit
data keyed by `primary_keyword` (`cat["keywords"][0]`) but reads it back keyed by `category_id`
(`cache.read_narrative_series(source, category_id)` at line ~206). Since the adapters
(`pytrends_adapter.py:100`, `reddit_adapter.py:133`) and the backfill script
(`scripts/backfill_pytrends_history.py:146`) all write under the keyword key, every pytrends/reddit
row trigger.py writes is immediately unreadable by trigger.py itself under real (non-test-stubbed)
conditions — it always reads an empty series for those two sources. `history.py` (the sibling
read path for `/api/narrative/history`) already gets this right (`keyword = seed["keywords"][0]`,
line ~385) and even documents the convention in its own module docstring (~line 9-12). This is a
same-file reader/writer key mismatch, not a design gap — the fix is a reader-side correction plus
a shared helper so it cannot drift again.

## Goals

1. Fix trigger.py to read pytrends/reddit by the same key it fetched with (keyword), matching
   history.py's existing convention. coingecko stays keyed by category_id (unchanged — it is
   correct today).
2. Add tests that exercise the REAL keying path (no adapter/cache stubbing of the read), proving
   real keyword-keyed rows are seen and wrongly-keyed (category_id) rows are ignored.
3. Update the AC-1 contract test's `_seed_history()` to seed production-realistic (keyword-keyed)
   rows instead of category_id-keyed rows, since it currently never exercises the real bug.
4. Produce a gated before/after diff report (old trigger code vs new, both against realistic
   keyword-keyed seed data) BEFORE touching the golden contract fixture, and stop for user
   sign-off before regenerating it.
5. Record an amendment note back into the narrative-dashboard plan's AC-1 section documenting this
   fix (AC-1 assumed the byte-identical path was already exercising real data; it was actually
   exercising a stub that masked the bug).

## Scope

In scope: `api/analytics/narrative/trigger.py` read path, a small shared keying helper (optionally
reused by `history.py` if trivial — do not force it), new/updated tests, one diff-report script
run once (throwaway, not committed as a permanent tool), the golden contract fixture (only after
sign-off), and one cross-reference note added to the narrative-dashboard plan.

Out of scope: `history.py`'s own logic (already correct — read-only reference), any writer
(`pytrends_adapter.py`, `reddit_adapter.py`, `backfill_pytrends_history.py`), `cache.py` internals,
`LEGACY_COIN_CATEGORY_MAP` / `mapping.py` (frozen, option B), multi-keyword aggregation (only
`keywords[0]` is ever fetched by any code path — not this plan's problem to solve), any UI/web
change (`/screener` badge or `/regime`/`/narrative` frontend — this is a backend cache-read fix).

## Acceptance Criteria

1. `compute_narrative_categories` reads pytrends and reddit history using the same key
   (`keywords[0]`) the adapters were fetched with; coingecko continues to read by `category_id`.
2. A new automated test proves real keyword-keyed rows are read and a category_id-keyed decoy
   row is ignored (mirrors `test_history.py`'s existing pattern).
3. `test_narrative_categories_contract.py`'s `_seed_history()` seeds production-realistic
   (keyword-keyed) rows, and the AC-1 byte-identical contract still passes after the fixture is
   regenerated with explicit user sign-off.
4. A before/after diff report exists showing the real behavior change caused by the fix, produced
   BEFORE the golden fixture is touched.
5. `uv run --project api pytest api/ -q` and `pnpm --filter web test` are both green.
6. The narrative-dashboard plan's AC-1 section carries an amendment note referencing this fix.

## Architecture Decision (locked)

**Reader-side fix.** `compute_narrative_categories` will read pytrends/reddit history using the
same key it fetched with (`primary_keyword`), via a small shared helper, e.g.:

```
def _source_history_key(source: str, category_id: str, primary_keyword: str) -> str:
    return primary_keyword if source in ("pytrends", "reddit") else category_id
```

placed in `trigger.py` (or promoted to a shared module only if `history.py` needs the identical
logic without duplicating a magic tuple — decide at EXECUTE time based on how much history.py
would actually change; do not force a shared module if it only saves 2 lines).

**Rejected alternatives:**
- *Writer-side re-keying* (write pytrends/reddit under category_id instead) — rejected: would
  orphan every already-cached parquet file under the keyword key, and would break `history.py`
  and `backfill_pytrends_history.py`, which correctly read/write by keyword today. This is the
  fix that breaks working code to "fix" broken code.
- *Multi-keyword aggregation* (read/merge all of `cat["keywords"]`, not just `[0]`) — rejected:
  out of scope; no code path anywhere fetches beyond `keywords[0]`, so there is nothing to
  aggregate yet. A future enhancement, not this bug fix.

## Implementation Checklist

1. **[Added at PVL cycle 1 — resolves E1]** Before making ANY edit to `trigger.py`, snapshot the
   pre-fix source to the task folder: run
   `git show HEAD:api/analytics/narrative/trigger.py > process/features/narrative-mindshare/completed/narrative-keyword-keying_25-09-26/pre-fix-trigger_25-09-26.py`.
   This file (not git history) is what step 6's diff script loads, so the "old" comparison stays
   correct regardless of when the fix gets committed.
2. In `api/analytics/narrative/trigger.py`, add a small keying helper (module-level function or
   inline per-source key selection) that returns `primary_keyword` for `source in
   ("pytrends", "reddit")` and `category_id` for `"coingecko"`.
3. In `compute_narrative_categories`, change the `series_by_source` loop (~line 206) from
   `cache.read_narrative_series(source, category_id)` to use the new helper's key. Keep the loop
   structure and `TOTAL_SOURCES` iteration otherwise unchanged.
4. **[E4: this file already exists — add a new test class/case, do not recreate]**
   `api/tests/analytics/test_narrative_trigger.py` already has `TestComputeTrigger`,
   `TestApplyConfirmation`, and `TestPytrendsStaleness` test classes. Add a new test case there
   mirroring the pattern in `api/tests/analytics/test_history.py` (~line 46,
   `test_pytrends_and_reddit_read_by_keyword_not_category_id`): write real rows via
   `cache.write_narrative_point("pytrends", "<keyword>", ...)` and
   `cache.write_narrative_point("reddit", "<keyword>", ...)` using a seed category's actual
   `keywords[0]`, PLUS a decoy row written under the category_id key that must be ignored; call
   `compute_narrative_categories` (or the smallest function that exercises the fixed loop) and
   assert the real rows are seen (`source_status`/`n_available`/trust weight reflect them) and the
   decoy is not counted. Use an isolated cache root (same `isolated_cache`/`monkeypatch` pattern
   already used in `test_narrative_categories_contract.py` and `test_history.py`) — do not stub
   `cache.read_narrative_series` itself, since stubbing the read is what hid this bug originally.
5. Update `api/tests/routers/test_narrative_categories_contract.py`'s `_seed_history()` (~line
   40-47) to write pytrends/reddit rows keyed by each seed category's real `keywords[0]` (pull
   from `trigger.load_seed_categories()` / `SEED_IDS`) instead of the current `cat` (category_id)
   key. Keep the coingecko seeding line unchanged (category_id is correct there). Do NOT touch
   the golden fixture file yet — this step only changes what the test seeds; step 8 handles the
   fixture.
6. **[E1: diff script loads the step-1 snapshot file, not git history]** Write a small throwaway
   diff-report script (location: inside this task folder, e.g.
   `narrative-keyword-keying-diff_25-09-26.py`, or a pytest-free standalone script under
   `api/scripts/` if that is cleaner for reusing app imports — EXECUTE decides based on which is
   less friction) that:
   - loads the OLD trigger module from the step-1 snapshot file
     (`process/features/narrative-mindshare/completed/narrative-keyword-keying_25-09-26/pre-fix-trigger_25-09-26.py`)
     via `importlib.util.spec_from_file_location("old_trigger_diff", "<path to snapshot>")` +
     `importlib.util.module_from_spec(spec)` + `spec.loader.exec_module(...)`, using a module name
     distinct from `api.analytics.narrative.trigger` so it does not collide in `sys.modules`. The
     snapshot's own imports (`from api.analytics.narrative import mapping, scoring`, `from
     api.data import cache, coingecko_adapter, pytrends_adapter, reddit_adapter`) are absolute, so
     the dynamically-loaded old module automatically uses today's live `mapping`/`scoring`/`cache`
     (unchanged by this plan) — no separate old-cache or old-mapping needed,
   - seeds an isolated cache with realistic keyword-keyed pytrends/reddit rows (reusing the
     updated `_seed_history` pattern from step 5) for the same `SEED_IDS`/scenarios used in the
     contract test,
   - runs `old_module.assemble_narrative_categories(as_of=...)` for the OLD (pre-fix,
     category_id-keyed read) path and `trigger.compute_narrative_categories`/
     `assemble_narrative_categories` for the NEW (post-fix) path, then passes each `by_id` result
     into the CURRENT (unmodified) `screener_board._coin_narrative_state(symbol, categories_by_id)`
     for BTC/ETH/HYPE — `_coin_narrative_state` is pure and takes a plain
     `dict[str, NarrativeCategory]`, so no "old screener_board" copy is needed,
   - emits a markdown table per category (triggered, confirmed, trust_weight, n_available,
     per-source status) and per screener coin (narrative_state / badge), showing what changed,
   - writes the result to `narrative-keyword-keying_DIFF_25-09-26.md` inside this task folder.
   Note explicitly in the report: because the fixture seed itself moves to keyword-keyed rows,
   the golden JSON produced by the OLD code against the new realistic seed may already differ
   from the currently-committed golden file — the meaningful comparison is old-code-vs-new-code
   on identical realistic seed data, not old-fixture-vs-new-fixture.
7. **HARD STOP for EXECUTE**: after step 6's report is written, stop and return control for user
   sign-off before touching `api/tests/routers/fixtures/narrative_categories_contract.json`. Do
   not proceed to step 8 without explicit approval.
8. **[E2: concrete fixture-regeneration mechanism — no documented capture/update tool exists]**
   After sign-off: there is no discoverable existing "capture/update path" script for the golden
   fixture (checked the test file and its git history — the fixture was originally produced by
   directly calling `build_contract_snapshot()` and writing the result to `GOLDEN_PATH`). Write a
   5-line throwaway script (can live next to the diff script, e.g.
   `narrative-keyword-keying-regen-fixture_25-09-26.py` inside this task folder) that imports
   `build_contract_snapshot` from `api.tests.routers.test_narrative_categories_contract`, calls it
   against the updated `_seed_history()` and the fixed trigger code (using a real
   `pytest.MonkeyPatch()` context manager, or run as a one-off pytest with `--capture=no` and a
   temporary assertion that writes instead of compares), and writes the result to
   `api/tests/routers/fixtures/narrative_categories_contract.json`
   (`api/tests/routers/fixtures/narrative_categories_contract.json` is `GOLDEN_PATH`). Exact
   command to run this script:
   `uv run --project api python process/features/narrative-mindshare/completed/narrative-keyword-keying_25-09-26/narrative-keyword-keying-regen-fixture_25-09-26.py`.
   Do not hand-edit the JSON. This is a one-off script per the plan's own "throwaway, not
   committed as a permanent tool" scope language — same pattern as step 6's diff script.
9. Add an amendment note to
   `process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md`
   documenting: AC-1 (option B byte-identical guarantee) was validated against a test that
   stubbed away the real keyword-keying bug; this plan fixed the bug and re-baselined the golden
   fixture; note the diff-report path for reference. Do NOT alter `LEGACY_COIN_CATEGORY_MAP` or
   any AC-1 conclusion about mapping.py — this note is additive documentation only.
10. **[E3: fresh-worktree frontend dependency prerequisite]** Before running the
    `pnpm --filter web test` gate, check whether `web/node_modules` exists; if absent, run
    `pnpm install` from the repo root (this resolves the web workspace via
    `web/pnpm-workspace.yaml`) — a one-time worktree-setup step, not a plan scope change.
11. Run full gates (see Verification Evidence) and confirm both green.

## Touchpoints

- `api/analytics/narrative/trigger.py` (fix: reader key selection in `compute_narrative_categories`)
- `api/tests/analytics/test_narrative_trigger.py` — **EXISTING file** (already has
  `TestComputeTrigger`, `TestApplyConfirmation`, `TestPytrendsStaleness` classes); this plan adds a
  new test class/case, it does not create the file fresh
- `api/tests/routers/test_narrative_categories_contract.py` (`_seed_history` update)
- `api/tests/routers/fixtures/narrative_categories_contract.json` (regenerated, gated on sign-off,
  via the one-off script named in checklist step 8 — no pre-existing regeneration tool exists)
- New throwaway artifacts inside this task folder: `pre-fix-trigger_25-09-26.py` (checklist step
  1), diff script + `narrative-keyword-keying_DIFF_25-09-26.md` (checklist step 6), fixture-regen
  script (checklist step 8) — or `api/scripts/` for the scripts themselves if EXECUTE judges that
  cleaner
- `process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md`
  (amendment note only — read as reference, edit AC-1 section additively)
- `web/` workspace: `pnpm install` prerequisite only (checklist step 10) — no source files touched

Read-only references (do not modify): `api/analytics/narrative/history.py`,
`api/data/cache.py`, `api/data/pytrends_adapter.py`, `api/data/reddit_adapter.py`,
`api/data/narrative_categories.json`, `api/analytics/screener_board.py`, `mapping.py`.

## Public Contracts

- `GET /api/narrative/categories` response shape is unchanged (no schema change); only the
  underlying data values change (previously pytrends/reddit contributed nothing real; now they
  do). This is a correctness fix to an existing contract's DATA, not a shape change.
- `/screener`'s `narrative_state`/badge derivation via `LEGACY_COIN_CATEGORY_MAP` (option B) is
  unaffected in mapping logic; only the trust-weight/trigger inputs feeding
  `assemble_narrative_categories` may change values for a given `as_of`.
- No new public API surface, no new persisted schema.

## Blast Radius

Small — 1 production file changed (`trigger.py`, one function's read-key logic), 2 test files
touched (1 existing file gets a new test case, 1 modified seed helper), 1 regenerated golden
fixture (data only, gated, via a named one-off script), 3 new throwaway artifacts (pre-fix
snapshot, diff script + report, fixture-regen script), 1 documentation amendment note in a sibling
plan file, 1 one-time `pnpm install` prerequisite (no source change). No schema, no auth, no API
contract shape change, no new dependency. Risk class: none of the high-risk classes (no
auth/billing/migration/public-API-shape/container/secrets). Standard correctness-fix risk profile —
the only "risk" is the AC-1 golden-fixture re-baseline, which is why step 7 hard-stops for
sign-off.

## Dependencies / Risks

- Risk: regenerating the golden fixture without inspecting HOW it was originally generated could
  produce a fixture from the wrong code path. Mitigation: checklist step 8 names the exact
  mechanism (`build_contract_snapshot()` + one-off script) and exact run command, sourced from
  inspecting the test file's own capture path — no hand-authored JSON.
- Risk: the diff script (step 6) comparing old-vs-new code depends on capturing the pre-fix source
  BEFORE trigger.py is edited. Mitigation: checklist step 1 captures
  `pre-fix-trigger_25-09-26.py` to the task folder before any edit in step 2, so the comparison
  stays correct regardless of git commit timing.
- Risk: real pytrends/reddit data flowing into `compute_narrative_categories` for the first time
  could change trigger/confirmation outcomes non-trivially (this is the actual point of the fix,
  but it could also surface secondary bugs, e.g. in `normalize_within_source` or
  `apply_confirmation` under previously-untested non-empty series). Mitigation: the diff report in
  step 6 exists precisely to surface this before the fixture changes; if something looks wrong at
  that point, this plan should return to PLAN/RESEARCH rather than pushing through to step 8.
- Risk: `pnpm --filter web test` fails in a fresh worktree with no `web/node_modules` installed.
  Mitigation: checklist step 10 makes `pnpm install` an explicit prerequisite before the web gate.
- Dependency: `trigger.load_seed_categories()` must be importable from the test files (already is,
  per the contract test's existing import).

## Test Infra Improvement Notes

(none identified yet)

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| New unit test: real keyword-keyed pytrends/reddit rows seen, category_id-keyed decoy ignored (`api/tests/analytics/test_narrative_trigger.py`, existing file, new test case) | Fully-Automated | AC-1/AC-2: Reader now uses the correct per-source key |
| Updated `_seed_history()` in `test_narrative_categories_contract.py`, run against fixed code | Fully-Automated | AC-3: contract test now exercises the real keying path, not a masking stub |
| Diff-report script run (old-code vs new-code, same realistic seed, old code loaded from the checklist-step-1 snapshot file) — one-shot, not part of CI | Agent-Probe | AC-4: actual behavior delta is understood and acceptable before fixture re-baseline |
| Fixture-regen one-off script (checklist step 8) run: `uv run --project api python process/features/narrative-mindshare/completed/narrative-keyword-keying_25-09-26/narrative-keyword-keying-regen-fixture_25-09-26.py` | Hybrid (manual sign-off gate at step 7 + this automated regen) | AC-3/AC-6: golden fixture regenerated via a named, reproducible mechanism, not hand-edited JSON |
| `pnpm install` prerequisite check (checklist step 10), then `pnpm --filter web test` | Fully-Automated | AC-5: confirms no frontend assumption depends on the old (broken) trigger values, in a fresh worktree with no pre-installed `web/node_modules` |
| `uv run --project api pytest api/ -q` | Fully-Automated | AC-5: no regression in the broader narrative/screener test suite; baseline was 378 passed / 3 deselected before this fix |
| Golden fixture regeneration + contract test pass, post sign-off | Hybrid (manual sign-off gate + automated re-run) | AC-3/AC-6: AC-1 (option B byte-identical guarantee) still holds under corrected, realistic data |

Failing stubs (TDD red-first, for EXECUTE to start from):

```
test("should read pytrends/reddit history by keywords[0], not category_id, and ignore a category_id-keyed decoy row", () => {
  throw new Error("NOT IMPLEMENTED — TDD stub for: real keyword-keyed rows seen, wrongly-keyed decoy ignored")
})
```
(Written here in pseudocode per repo convention; actual test is Python/pytest per checklist step 4.)

## Resume and Execution Handoff

1. Selected plan file path: `process/features/narrative-mindshare/completed/narrative-keyword-keying_25-09-26/narrative-keyword-keying_PLAN_25-09-26.md`
2. Last completed phase/step: VALIDATE (PVL cycle 2 — Gate: PASS; cycle 1's PLAN-SUPPLEMENT
   folded gaps E1-E4 into the checklist, and this cycle independently re-verified each resolution
   against current source/test state). No EXECUTE steps started.
3. Validate-contract status: **PASS** — ready for EXECUTE MODE (see `## Validate Contract` below).
4. Supporting context files loaded during PLAN: `process/context/all-context.md`,
   `process/context/tests/all-tests.md`,
   `process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md`
   (AC-1 / option B section), `api/analytics/narrative/trigger.py`,
   `api/analytics/narrative/history.py` (lines ~9-20, ~375-395),
   `api/tests/routers/test_narrative_categories_contract.py` (lines 1-60),
   `api/tests/analytics/test_history.py` (lines ~40-60).
5. Next step for a fresh agent: run EXECUTE MODE through checklist steps 1-6, HARD STOP at step 7
   for user sign-off on the diff report, then proceed to steps 8-11 only after explicit sign-off.
   The former "Execute-Agent Instructions E1-E4" are folded directly into the checklist steps
   above — read the checklist itself, not a separate instructions block.

## Validate Contract

Status: PASS
Date: 25-09-26
date: 2026-09-25
generated-by: outer-pvl
supersedes: 2026-09-25 (outer-pvl) — outer PVL has current evidence (cycle 2 re-validation after
PVL-supplement cycle 1 folded E1-E4 into the checklist)

Parallel strategy: sequential
Rationale: signal score 1/7 (only S7 borderline-present: ~6-7 touchpoint files, all small,
no other signal present — no multi-package scope, no schema/API/auth surface, single locked
architecture decision, not a phase program, no explicit depth request, no high-risk class).
SIMPLE plan classification confirmed; one vc-validate-agent pass, no fan-out needed. Re-confirmed
this cycle — no signal changed.

Test gates (C3 5-column table):

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-1/AC-2 | `compute_narrative_categories` reads pytrends/reddit by `keywords[0]`, coingecko by `category_id`; category_id-keyed decoy for pytrends/reddit is ignored | Fully-Automated | `uv run --project api pytest api/tests/analytics/test_narrative_trigger.py -q` (new case added per checklist step 4) | A |
| AC-3 | Contract test's `_seed_history()` seeds production-realistic keyword-keyed rows, exercising the real (previously masked) keying path | Fully-Automated | `uv run --project api pytest api/tests/routers/test_narrative_categories_contract.py -q` | A |
| AC-4 | Old-code-vs-new-code behavior delta (per category: triggered/confirmed/trust_weight/n_available; per screener coin: narrative_state/badge) is surfaced and human-reviewed before the golden fixture is touched | Agent-Probe | One-shot diff script (checklist step 6, loading the step-1 pre-fix snapshot) producing `narrative-keyword-keying_DIFF_25-09-26.md` inside the task folder; user reviews and signs off at the step-7 HARD STOP | B |
| AC-5 (backend) | No regression in the broader narrative/screener/api suite | Fully-Automated | `uv run --project api pytest api/ -q` — baseline reconfirmed live during this VALIDATE cycle: 378 passed / 3 deselected (248.44s run) | A |
| AC-5 (frontend) | No frontend assumption depends on the old (broken, always-empty) pytrends/reddit trigger inputs | Fully-Automated | `pnpm --filter web test` (run from repo root, after the checklist-step-10 `pnpm install` prerequisite) | A |
| AC-3/AC-6 | Golden fixture `narrative_categories_contract.json` regenerated against the fixed code + realistic seed, contract test passes, post explicit sign-off | Hybrid (manual sign-off gate + automated re-run) | Manual: user sign-off at step 7 on the DIFF report. Automated: checklist step 8's named fixture-regen script, then `uv run --project api pytest api/tests/routers/test_narrative_categories_contract.py -q` | B |
| AC-6 | Amendment note added to narrative-dashboard plan's AC-1 section, documenting the fix and the byte-identical-under-a-masking-stub finding | Fully-Automated (grep-checkable) | `grep -n "keyword-keying" process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md` returns the added note | A |

gap-resolution legend:
- A — proven now (gate passes in this cycle, once EXECUTE runs the checklist)
- B — fixed in this plan (gate added by this plan's own checklist: the diff-script HARD STOP and the
  post-sign-off fixture regeneration)

C-4 reconciliation: no Known-Gap rows in this table — every developed behavior in this plan's
blast radius has a Fully-Automated, Hybrid, or Agent-Probe proving gate. No vacuously-green risk.

Legacy line form (retained so existing validate-contract consumers still parse):
- trigger.py reader fix: Fully-automated: `uv run --project api pytest api/tests/analytics/test_narrative_trigger.py -q`
- contract seed realism: Fully-automated: `uv run --project api pytest api/tests/routers/test_narrative_categories_contract.py -q`
- before/after behavior delta: Agent-probe: diff script (loads step-1 pre-fix snapshot) + human sign-off at step 7
- full backend regression: Fully-automated: `uv run --project api pytest api/ -q`
- full frontend regression: Fully-automated: `pnpm --filter web test` (needs `pnpm install` first in a fresh worktree — checklist step 10)
- golden fixture re-baseline: hybrid: manual sign-off (step 7) + fixture-regen script (checklist step 8) + `uv run --project api pytest api/tests/routers/test_narrative_categories_contract.py -q`

Dimension findings (PVL cycle 2 — fresh V1-V7 re-run against current source/test state; every
finding below is independently re-verified this cycle, not carried forward from cycle 1's text):
- Infra fit: PASS — re-verified: `web/pnpm-workspace.yaml` + `web/package.json` (`"name": "web"`)
  confirmed present; `pnpm --filter web exec pwd` run from the repo root resolves correctly to
  `web/` even with no root-level `package.json`/`pnpm-workspace.yaml`, confirming the filter
  works as the plan claims. `web/node_modules` is confirmed absent in this worktree — exactly the
  condition checklist step 10's `pnpm install` prerequisite exists to handle. `uv run --project
  api pytest api/ -q` was run live this cycle: **378 passed, 3 deselected in 248.44s** — matches
  the plan's stated baseline exactly.
- Test coverage: PASS — re-verified against live source: `api/tests/analytics/test_narrative_trigger.py`
  confirmed to already contain exactly `TestComputeTrigger`, `TestApplyConfirmation`,
  `TestPytrendsStaleness` (no more, no less), matching the E4 resolution. The pattern checklist
  step 4 asks to mirror — `test_history.py::TestCacheRoundTrip::test_pytrends_and_reddit_read_by_keyword_not_category_id`
  — is confirmed to exist and do precisely what the plan describes (real keyword-keyed rows +
  category_id decoy, isolated cache, no `read_narrative_series` stubbing). `_seed_history()` in
  `test_narrative_categories_contract.py` is confirmed to currently seed pytrends/reddit under
  `cat` (category_id) — the exact stubbing-the-bug-away condition the plan describes; checklist
  step 5's fix target is accurate. `build_contract_snapshot(monkeypatch, tmp_path)` confirmed to
  require only `monkeypatch` + `tmp_path`, both substitutable outside a raw pytest run via
  `pytest.MonkeyPatch()` as a context manager and a plain `Path` — checklist step 8's proposed
  one-off script mechanism is technically sound. Confirmed (broad, scoped grep) no separate
  fixture-regeneration script exists anywhere under `api/` — E2's "no documented regen tool"
  claim holds.
- Breaking changes: PASS — re-confirmed by reading current router/model code: `NarrativeCategory`
  response shape is unchanged; only underlying values change. No schema, no new endpoint, no
  auth/billing surface touched.
- Security surface: PASS — no auth, secrets, billing, or trust-boundary code touched; local
  cache-read logic only.
- Section — Implementation Checklist steps 2-3 (trigger.py fix): PASS — re-confirmed directly
  against current source: `pytrends_adapter.py:100` (`cache.write_narrative_point("pytrends",
  keyword, ...)`) and `reddit_adapter.py:132` (`cache.write_narrative_point("reddit",
  subreddit_or_keyword, ...)`) both write under the keyword key exactly as the plan states;
  `trigger.py:185` computes `primary_keyword = cat["keywords"][0] if cat.get("keywords") else
  category_id` and fetches with it (lines 186-187); `trigger.py:205` still reads with
  `cache.read_narrative_series(source, category_id)` for ALL sources including pytrends/reddit —
  the described mismatch is confirmed live and unfixed (no EXECUTE steps have run yet, matching
  Resume item 2). `trigger.py`'s own imports (`from api.analytics.narrative import mapping,
  scoring`, `from api.data import cache, coingecko_adapter, pytrends_adapter, reddit_adapter`) are
  confirmed absolute, exactly as the diff-script mechanism (step 6) depends on. No gaps, no
  conflicts.
- Section — Test additions (checklist steps 4-5): PASS — see Test coverage above; both target
  files and their current class/seed state confirmed to match the plan's description exactly.
- Section — Diff script + HARD STOP (checklist steps 1, 6, 7): PASS — mechanically re-verified
  VIABLE. `git status --short` confirms `trigger.py` and both target test files are clean
  (unmodified) at current HEAD, so `git show HEAD:api/analytics/narrative/trigger.py` (checklist
  step 1) will correctly capture the pre-fix source. `screener_board._coin_narrative_state`
  (lines 101-109) confirmed pure — takes a plain `dict[str, NarrativeCategory]` — so the current,
  unmodified `screener_board` function can be called directly against the OLD module's
  `assemble_narrative_categories()` output with no "old screener_board" copy needed. The ordering
  dependency (snapshot before edit) is the only material risk, and it is mitigated by checklist
  step 1 running first.
- Section — Fixture regen (checklist step 8): PASS — see Test coverage above.
- Section — Amendment note (checklist step 9): PASS — confirmed
  `narrative-dashboard_PLAN_24-09-26.md` has a live AC-1 section (multiple references, e.g. "The
  single hardest constraint in this plan is AC-1") to append the additive note to; no conflict
  with existing AC-1 text.
- Section — web install prerequisite (checklist step 10): PASS — see Infra fit above;
  `web/node_modules` confirmed absent, checklist step 10 is the correct, sufficient fix.

Open gaps: none. All 4 prior CONCERNs (Infra fit, Test coverage / fixture regeneration mechanism,
test-file naming clarity, diff-script git-timing dependency) were folded into the Implementation
Checklist/Touchpoints/Verification Evidence at PVL cycle 1, and this cycle's fresh V1-V7 pass
independently re-verified each resolution against live source/test state and the actual full
backend test run — no discrepancy found, no new gap surfaced during the numbering/cross-reference
consistency check (11 checklist steps, hard stop at step 7, all Phase Completion Rules / Resume /
Autonomous Goal Block cross-references confirmed consistent with the renumbered checklist).

What this coverage does NOT prove:
- The new unit test (AC-1/AC-2 gate) proves the reader-key fix on synthetic seeded rows; it does
  not prove real-world pytrends/reddit values (once genuinely non-empty) produce sensible
  trigger/confirmation outcomes at scale — that is exactly what the Agent-Probe diff report (AC-4)
  is for, and even that is a one-time snapshot, not an ongoing gate.
- The full backend/frontend regression gates (`pytest api/ -q`, `pnpm --filter web test`) prove no
  existing test's assertions broke; they do not prove no other UNTESTED code path silently
  depended on pytrends/reddit always returning empty (Standing Lesson: "a green suite that never
  crosses a boundary is not evidence about that boundary" — `all-tests.md` item 8). No such path
  was found during VALIDATE, but this is a scan of visible callers, not a formal proof.
- The golden fixture regeneration gate proves the contract test passes against the NEW fixture; it
  does not itself prove the NEW fixture's values are "correct" in any external sense — that
  judgment is exactly what the human sign-off at step 7 is for, on the diff report's evidence.
- Agent-Probe and Hybrid rows (AC-4, the fixture regen) are one-shot, human-reviewed events, not
  regression gates that re-run on every future change — a later change to `trigger.py` would not
  automatically re-surface this same before/after comparison.

Gate: PASS (0 FAILs, 0 CONCERNs. All 4 concerns from PVL cycle 1 were folded into the plan body
and this cycle's independent re-verification — live pytest run, live grep/read checks against
every touched file, pnpm filter resolution check — confirms each resolution is mechanically
accurate. No new gaps found. Ready for EXECUTE.)
Accepted by: session (non-interactive VALIDATE run per explicit task instruction to apply
recommended resolutions and write the contract without a menu pause). No concerns require
acceptance — gate is a clean PASS, not CONDITIONAL.

## Autonomous Goal Block

SESSION GOAL: Fix trigger.py's pytrends/reddit reader-key mismatch (reads by category_id,
adapters write by keyword) so `/api/narrative/categories` actually sees pytrends/reddit data,
with a gated before/after diff report and explicit user sign-off before the golden contract
fixture is re-baselined.
Charter + umbrella plan: N/A — single plan (no umbrella/Stable Program Goal exists for
narrative-mindshare; this plan carries its own goal block, BRANCH A).
Autonomy: standard RIPER-5 gates apply — EXECUTE requires explicit "ENTER EXECUTE MODE"; step 7
inside EXECUTE is a mandatory hard stop requiring explicit user sign-off on the diff report before
regenerating the golden fixture (steps 8-11). No autopilot/`/goal` autonomous run is active for
this plan.
Hard stop conditions / safety constraints:
- Do not touch `api/tests/routers/fixtures/narrative_categories_contract.json` before step 7's
  user sign-off on the before/after diff report.
- Do not modify `LEGACY_COIN_CATEGORY_MAP`, `mapping.py`, or any writer (`pytrends_adapter.py`,
  `reddit_adapter.py`, `backfill_pytrends_history.py`) or `history.py` — all frozen/out of scope.
- Capture the pre-fix `trigger.py` source (checklist step 1, via `git show HEAD:...` to a
  task-folder file) BEFORE editing it in step 2 — do not rely on git history after the fix is made.
Next phase: EXECUTE MODE for
`process/features/narrative-mindshare/completed/narrative-keyword-keying_25-09-26/narrative-keyword-keying_PLAN_25-09-26.md`,
checklist steps 1-6, then HARD STOP at step 7.
Validate contract: inline in this plan file, section `## Validate Contract` above.
Execute start: Fully-automated: `uv run --project api pytest api/tests/analytics/test_narrative_trigger.py -q`
and `uv run --project api pytest api/ -q` | e2e spec: none (backend-only fix, no web/e2e touched) |
probe scenario: one-shot diff script (checklist step 6) comparing old-vs-new trigger output for
BTC/ETH/HYPE, human-reviewed at step 7 | high-risk pack: no (no high-risk class present).
