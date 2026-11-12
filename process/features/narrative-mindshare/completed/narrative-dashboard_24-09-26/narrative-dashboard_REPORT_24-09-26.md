---
name: report:narrative-dashboard-update-process-closeout
description: "UPDATE PROCESS closeout for the narrative-dashboard program (RFC-1..6) — code-complete, EVL-confirmed, two review decisions + AC-3/AC-12 pending on user's PC"
date: 24-09-26
metadata:
  node_type: memory
  type: report
  feature: narrative-mindshare
  phase: UPDATE-PROCESS
phase: update-process
status: COMPLETE
feature: narrative-mindshare
plan: process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md
---

# UPDATE PROCESS Closeout — narrative-dashboard (RFC-1..6)

## Closeout Packet

1. **Selected plan path**: `process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md`

2. **Closeout classification**: **Keep in active/testing.** All 6 RFCs are code-complete and
   EVL-confirmed, but two manual-first risk-pack review decisions are `PENDING`, and AC-3
   (cron actually firing) / AC-12 (real-cache walkthrough) require the user's own machine (this
   container's egress proxy blocks Google Trends, Reddit, CoinGecko, and Hyperliquid). The plan is
   NOT archived this session — it stays in `active/`.

3. **What was finished**: Data foundation (curated, user-editable coin-to-category map under
   "option B" — legacy map frozen for `/categories`/`/screener`, new map for `/history`/`/narrative`
   only); the Hyperliquid exchange-attention adapter + pytrends historical backfill script;
   `GET /api/narrative/history` (composite/comparison/change-in-attention maths, read-only, proven
   separate from `/categories`); the nightly `narrative-snapshot.yml` forward-archive workflow; the
   `/narrative` page (history panels, comparison view, change-in-attention view, data-quality
   caveat, personal-use badges); and the end-to-end proof (`web/e2e/narrative.spec.ts`, 14
   scenarios), which found and fixed a real product bug (a pandas `None`→`NaN` coercion 500ing
   `/history` from day 2 of the nightly archive onward). All work is committed and pushed
   (branch `claude/kind-tesla-tat3vo`, HEAD `7ef8eb3`, 58 files, +5536/-4).
   This UPDATE PROCESS session additionally reconciled the plan, SPEC, feature guide, and four
   context docs against what was actually built (see items 8-9 below) — no source files were
   touched.

4. **Verified vs still unverified**:
   - Verified: `pytest api/ -q` 392 passed / 3 deselected; `pnpm --filter web test` 110 passed (16
     files); `pnpm --filter web exec tsc --noEmit` exit 0; `cd web && pnpm test:e2e` 26/26 passed,
     run twice; `git diff` on `trigger.py`/`screener_board.py`/`NarrativeStrip.tsx`/
     `liqtide-snapshot.yml` empty (AC-1 + workflow isolation both hold mechanically).
   - Unverified: real Hyperliquid payload shape, real pytrends backfill output, Hyperliquid's terms
     of redistribution, the nightly cron actually firing on GitHub Actions (AC-3), the real-cache
     user walkthrough (AC-12), and both manual-first risk-pack review decisions (RFC-3's new public
     API surface, RFC-4's new `contents: write` scheduled workflow). All six are user-PC-only per
     this container's egress block — see the plan's amended Resume and Execution Handoff for the
     exact 9-step checklist.

4b. **Validate-contract compliance**: Present. `## Validate Contract` in the plan, `Gate: PASS`,
    `generated-by: outer-pvl`, dated 24-09-26 (PVL cycle 1 re-validate). No re-validate was
    triggered during EXECUTE — all 6 RFCs stayed within the validated blast radius, with deviations
    documented as within-blast-radius plan-text corrections (see the plan's new
    `## Post-EXECUTE Amendments` section), not contract-breaking changes.

5. **Cleanup done vs still needed**:
   - Done this session: plan Status Strip + Current Status + Resume/Handoff updated; a full
     `## Post-EXECUTE Amendments` section added to the plan documenting every RFC-report-flagged
     plan-text deviation (ADR-2/6/7 corrections, §11 response shape, §12b storage schema, cache
     keying by keyword not category id, Reddit `no-archived-data` vs. the original ADR-8 design,
     §19 Ops Runbook `--with pytrends` + secrets-need-a-workflow-edit corrections, report naming);
     SPEC amended with a `## Post-EXECUTE Amendment` recording how OQ-1/2/3 actually resolved and
     confirming every AC's disposition, without narrowing any AC; `_GUIDE.md` updated (real source
     files, code-complete status); `all-context.md` given a new "Changes Since Last Update" entry,
     Repository Structure updates (9th adapter, second workflow, narrative route), two new Open
     Questions (the `/categories` keying bug, Hyperliquid terms), and an amended Scan Metadata;
     `data-sources/all-data-sources.md` given a new Hyperliquid subsection, the pytrends
     backfill scale caveat, and the Reddit-in-CI two-step-gate stance; `tests/all-tests.md` given
     updated counts (392/110/26 vs. the regime dashboard's same-day 294/75/12), the seeder
     description, and two new Standing Lesson rows (pandas `None`→`NaN`, mutation-testing finding
     one missing render-branch assertion).
   - Still needed: the 9-step user-PC checklist in the plan's Resume and Execution Handoff (merge
     to `main`, first `workflow_dispatch`, local snapshot sanity, Hyperliquid integration test,
     pytrends backfill, Hyperliquid terms check, real-cache walkthrough, both review decisions,
     optional Reddit secrets+workflow edit). A separate follow-up plan should be queued (not part of
     this program) for the pre-existing `/categories` keying bug found at RFC-3 — it needs its own
     deliberate AC-1 re-baseline and user sign-off, explicitly out of scope here.

6. **Single best next valid state**: Keep the plan active and continue validation on the same
   selected plan — the user completes the 9-step checklist in the plan's Resume and Execution
   Handoff on their own machine, then re-enters UPDATE PROCESS to archive
   `narrative-dashboard_24-09-26/` to `process/features/narrative-mindshare/completed/`.

7. **Commit-checkpoint recommendation**: **Process commit belongs after UPDATE PROCESS.** The
   source/test commit for all 6 RFCs is already made and pushed (`7ef8eb3`) — that ship happened
   before this session. This session's changes are plan/SPEC/context/report artifacts only
   (`process/features/narrative-mindshare/...`, `process/context/{all-context.md,
   data-sources/all-data-sources.md, tests/all-tests.md}`); route these through a separate process
   commit, invoked by the orchestrator, not bundled with any further source change.

8. **Regression status**: N/A (not a phase-program with prior-phase overlapping surfaces to
   regression-check) — but the equivalent check was made directly: `git diff` on
   `trigger.py`/`screener_board.py`/`NarrativeStrip.tsx`/`liqtide-snapshot.yml` is empty across the
   full 6-RFC commit, confirming zero regression on the pre-existing `/screener`/`/categories`
   surface and the pre-existing LiqTide workflow. Full api/vitest/e2e suites (including the
   pre-existing regime and screener specs) all passed alongside the new narrative coverage.

9. **SPEC achievement** (`narrative-dashboard_SPEC_24-09-26.md`, 12 ACs):

| AC | Criterion | Status | Evidence |
|---|---|---|---|
| AC-1 | `/categories` + `/screener` byte-identical | **met** | contract snapshot test (incl. newly-mapped-coin-in-trending scenario); `git diff` on `trigger.py`/`screener_board.py`/`NarrativeStrip.tsx` empty |
| AC-2 | Real, growing per-category history chart | **met** | `test_history.py` real cache round-trip; e2e scenario 2 |
| AC-3 | Nightly scheduled forward-archive | **met (automated portion)** — cron-firing portion is Agent-Probe, user-PC pending | `test_snapshot_narrative.py` 10 tests; live cron confirmation is a backlog/user-PC item, not a gap in this plan's own contract (declared Agent-Probe from the start) |
| AC-4 | pytrends' own history seeds day one | **met** | `test_backfill_pytrends_history.py`; e2e scenario 4 |
| AC-5 | Sectors comparable side by side | **met** | `test_history.py` rank golden values; e2e scenario 9 |
| AC-6 | Change-in-attention view | **met** | `test_history.py` delta golden values; e2e scenario 10 |
| AC-7 | Exchange proxy fails safely | **met** | `test_hyperliquid_narrative_adapter.py`, `test_exchange_attention.py`; e2e scenario 11 |
| AC-8 | Wider coin map, explicit unmapped state | **met** | `test_mapping.py` extended; e2e scenario 7 (narrative-only label) |
| AC-9 | One source down never blanks the rest | **met** | `test_narrative_history.py`; e2e scenario 12 (Reddit down, others render) |
| AC-10 | No raw cross-source level comparison | **met** | `test_history.py`/`test_exchange_attention.py` normalisation-boundary tests; e2e scenario 5-6 (mixed_scale, legacy-excluded) |
| AC-11 | Visible data-quality caveat on every view | **met** | vitest `__tests__/*`; e2e scenario 1 |
| AC-12 | Real-cache user walkthrough | **met (E2E portion)** — live-provider portion is Agent-Probe, user-PC pending | `web/e2e/narrative.spec.ts` 26/26 x2; live walkthrough is step 7 of the user-PC checklist, declared Agent-Probe from the start, not a plan gap |

No unmet criteria. AC-3 and AC-12's live-provider portions were never Fully-Automated in this
plan's own Validate Contract — they were declared Hybrid/Agent-Probe from PLAN onward and are
proceeding exactly as scoped, not slipping. No backlog NOTE is needed for either; the plan's own
Resume and Execution Handoff already tracks them as the user-PC checklist.

## Drift Signal Scoring

- (a) Files touched this UPDATE PROCESS session: 6 (`narrative-dashboard_PLAN_24-09-26.md`,
  `narrative-dashboard_SPEC_24-09-26.md`, `_GUIDE.md`, `all-context.md`,
  `data-sources/all-data-sources.md`, `tests/all-tests.md`) + this report = **+1** (≥1 file), not
  +2 (<10 files)
- (b1) `.claude/`/`.codex/`/agent-harness files changed: none = **+0**
- (b2) `README.md`/`AGENTS.md`/`CLAUDE.md`/`process/development-protocols/` changed: none = **+0**
- (c) 3+ memory-worthy observations: yes — the pandas `None`→`NaN` lesson, the mutation-testing
  missing-branch lesson, the `/categories` keying bug, the option-B map-split mechanism, the
  Reddit-no-row-vs-explicit-unavailable design change = **+1**
- (d) Feature-folder structural change (new task folder / backlog note / archive move): no task
  folder created or archived this session (stays in `active/`) = **+0**
- (e) Validate-contract deviation (execution diverged from the contract/blast radius): no — every
  RFC-report deviation was classified "within blast radius" by its own execute-agent, confirmed
  during this reconciliation = **+0**

**Total: 2 signals → MEDIUM.**

"Recommend UPDATE PROCESS -- significant changes detected."

(This UPDATE PROCESS session itself is now complete for the narrative-dashboard program; the score
above reflects the underlying EXECUTE session's scope, consistent with `vc-generate-closeout`'s
scoring intent.)

## TL;DR

All 6 narrative-dashboard RFCs are code-complete, EVL-confirmed, and committed/pushed
(`7ef8eb3`). Plan/SPEC/context fully reconciled with what shipped — no source files touched this
session. Plan stays in `active/`: two manual-first review decisions and AC-3/AC-12's live-provider
checks are pending on the user's own PC (proxy blocks this container). Next: user completes the
9-step checklist in the plan's Resume and Execution Handoff, then re-enter UPDATE PROCESS to
archive.
