---
phase: update-process-closeout
date: 2026-09-20
status: COMPLETE_WITH_GAPS
feature: general-plans
plan: process/general-plans/active/momentum-screener_17-09-26/momentum-screener_PLAN_17-09-26.md
---

# UPDATE PROCESS Closeout — 20-09-26 (two threads)

**TL;DR:** Both threads' code and tests were already done before this session; this session's job
was documentation-only. `all-context.md` and `all-data-sources.md` are now current as of 18:47.
Neither task folder archives — both stay `active/` (momentum-screener per standing precedent;
liqtide-snapshot-tooling because its stated deliverable, composite agreement, is still unproven).
`lse-data-verification_17-09-26` is stale (⏳ PLANNED, zero activity in 3 days) — flagged for a
user decision, not acted on. No `vc-audit-context`/`vc-audit-plans` validator scripts could be
run (no device shell this session); every check below is either done by direct file inspection or
explicitly marked not performed. No git commands were run.

---

## Scope Note

This is a **reconciliation session**, not a fresh EXECUTE→UPDATE PROCESS cycle. Both threads
completed EXECUTE earlier on 20-09-26 and never went through UPDATE PROCESS. No source files
under `api/` or `web/` were touched this session — only `process/context/` docs and this closeout
were written, per the task's explicit "documentation/reconciliation phase only" instruction.

## What Was Done

1. Read `momentum-screener_PLAN_17-09-26.md`'s `## Architecture Decisions (Final)` section
   (ADR-1 Amendment + ADR-1 Amendment #2, lines ~213–224) and the confirming backtest artifact
   (`leg-boundary-backtest-report-20260920-184700.json`) to verify both amendments' claims against
   the actual JSON evidence (2017: 0/0, 34 points; 2020-21: 6 candidates/5 confirmed) — matches
   the plan text exactly.
2. Read `liqtide-snapshot-tooling_PLAN_20-09-26.md` (incl. its inline VALIDATE contract, Net Gate:
   CONDITIONAL, both CONCERNs) and `liqtide-snapshot-tooling_REPORT_20-09-26.md` in full.
3. Read both comparison-JSON artifacts and diffed them: `...-180830.json` (pre-`SUSTAINED_DAYS`
   re-tune: reduced candidates=0) vs `...-183336.json` (post-re-tune: reduced candidates=4,
   confirmed=3). Confirmed the REPORT's "0 candidates" line is the earlier, now-superseded run.
4. Listed `api/data/cache/liqtide/` directly on the device — it is **not** empty as the REPORT
   states; it holds one file, `2026-09-20.parquet` (created after the 18:08 comparison run, before
   the 18:33 one). The full composite's `available` flag is still `false` in the 18:33 run even
   with that one day present, so the REPORT's practical conclusion (comparison currently
   impossible) still holds — only the literal "EMPTY (zero archived days)" phrasing is now stale.
5. Updated `process/context/all-context.md`: new "Amendment, 2026-09-20 18:47" subsection under
   Changes Since Last Update (both ADR-1 fixes + liqtide tooling outcome + the stale-number
   reconciliation above); Repository Structure (`api/scripts/`, `api/tests/scripts/` entries);
   Environment and Configuration (`.gitignore` negation carve-out, archive state); Open Questions
   (sharpened the 2017 entry with the confirming backtest; added a new open item for the
   full-vs-reduced comparison blocker); References; Scan Metadata. Full diff is the edit itself —
   see file.
6. Updated `process/context/data-sources/all-data-sources.md`: one paragraph under the LiqTide
   section noting Standing Rule 8 (cache every third-party composite) is now implemented in code,
   with the forward-only-archive constraint now confirmed operationally rather than theoretical.
7. Wrote this closeout to `momentum-screener_17-09-26/update-process-closeout_20-09-26.md` per
   task-folder artefact colocation (colocated with Thread A's task folder, since it covers both
   threads and Thread A's folder is the umbrella program folder).
8. Performed the plan-inventory and context-audit checks below by direct inspection (no validator
   scripts run — see §Audits).

## What Was Skipped / Deferred

- **No plan-file edits.** Neither `momentum-screener_PLAN_17-09-26.md` nor
  `liqtide-snapshot-tooling_PLAN_20-09-26.md`/`_REPORT_` was edited — the task's produce-list
  named only `all-context.md`, `all-data-sources.md` (conditionally), and this closeout. The
  REPORT's stale "0 candidates" line is reconciled here and in `all-context.md`, not edited
  in place inside the REPORT itself (reports are point-in-time records; corrections layer on
  top via UPDATE PROCESS, which is what this closeout and the context update are).
- **No folder moves.** Per explicit instruction and the standing precedent below, nothing moved
  from `active/`.
- **No backlog NOTE written** for the `lse-data-verification_17-09-26` staleness finding — it is
  flagged in §Plan Inventory for a user decision (resume / deprioritize / drop), not
  unilaterally backlogged, since the plan's own status (⏳ PLANNED, unassigned owner) suggests it
  was never started rather than abandoned mid-work.
- **`vc-audit-context` / `vc-audit-plans` validator scripts** — not run. This session has no
  device shell (`device_bash` unavailable); the scripts live on the user's device
  (`.claude/skills/vc-audit-context/scripts/*.mjs`, `.claude/skills/vc-audit-plans/scripts/*.mjs`)
  and cannot be executed from here. See §Audits for what was checked by inspection instead.
- **Cross-surface mirror review** (Codex `.codex/agents/`, `AGENTS.md`) — not performed. Nothing
  in this session touched agent/skill/protocol files, so mirror review is not triggered per
  the agent contract's §5b (only required "if shared workflow behavior changed") — stated
  explicitly rather than silently skipped.

## Test Gate Outcomes

No tests were run this session (documentation-only, no code touched). Carrying forward what was
already verified in the two EXECUTE sessions being closed out:

| Thread | Gate | Result | Source |
|---|---|---|---|
| A (ADR-1 amendments) | `scripts/backtest_leg_boundaries.py --cycle all` (confirming run) | PASS — 2017: 0/0 (34 pts); 2020-21: 6 candidates/5 confirmed | `leg-boundary-backtest-report-20260920-184700.json`, read this session |
| B (liqtide tooling) | `cd api && uv run pytest tests/ -x -q` (final) | PASS — 179 passed, 1 deselected | `liqtide-snapshot-tooling_REPORT_20-09-26.md` |
| B | Grep additivity check (`LiqTidePayload(`/`fetch_latest(` call sites) | PASS — 3 sites, all inside the adapter, all kwargs | same REPORT |
| B | `snapshot_liqtide.py --verify-only` / `--coverage` | PASS both | same REPORT |
| B | `.gitignore` negation probe | PASS | same REPORT |
| B | `compare_composite_variants.py` | Ran to completion; verdict `DISAGREE` (missing-data branch, not a real disagreement) — see §Deliverable reconciliation above | same REPORT + this session's re-check of the 18:33 artifact |

## Plan Deviations

None introduced this session (no plan file edited). Within the two threads being closed out:
- Thread A: none — both amendments are explicitly scoped, single-constant/single-formula changes,
  recorded verbatim in the plan's own ADR-1 text per its Change Management rule.
- Thread B: none — REPORT states "All 4 checklist items implemented per spec."

## Test Infra Gaps Found

Carried forward from `liqtide-snapshot-tooling_REPORT_20-09-26.md` (not newly found this
session): `compare_composite_variants.py` has no unit test for its `_match`/`_verdict` pure
functions — the CLI gate only exercised them on the degenerate empty-input path, so the bijective
matching logic has never run against real boundaries. No backlog NOTE written for this yet (out
of this session's scope — flagged here so it isn't lost; recommend a NOTE if the comparison
script gets used again before the archive has enough history to matter).

## SPEC Achievement

- **Thread A (ADR-1 amendments):** governed by `momentum-screener_SPEC_17-09-26.md`. These are
  post-EXECUTE numerical corrections to an already-scored acceptance criterion's underlying
  mechanism (the leg-boundary Hybrid backtest gate under ADR-1's own Implications), not new
  acceptance criteria. No SPEC criterion changes status because of these amendments — they make
  the same criterion's evidence more accurate, not newly met or newly unmet. Not rescored here.
- **Thread B (liqtide tooling):** no locked `*_SPEC_*.md` exists for this plan — its own
  Resume/Handoff section records "VALIDATE run inline below (FAST MODE)", i.e. it skipped SPEC as
  a FAST MODE / mechanical-scope task. Stated explicitly per the closeout schema's allowance for
  "no SPEC for this plan."

## Deliverable Reconciliation (Thread B, required by task)

| Artifact | Time | Reduced composite | Why it differs |
|---|---|---|---|
| `composite-variant-agreement-20260920-180830.json` | 18:08 | candidates=0, confirmed=[] | Ran before `SUSTAINED_DAYS` 5→2 (ADR-1 Amendment #2) landed |
| `composite-variant-agreement-20260920-183336.json` | 18:33 | candidates=4, confirmed=[2026-03-17, 2026-04-20, 2026-06-02] | Ran after the re-tune landed |

Both runs still verdict `DISAGREE` — for the same reason both times (the full composite has no
archived input at all, `available=false`). The REPORT's narrative text ("the reduced composite
found 0 candidate boundaries") reflects the 18:08 run and is now stale; the 18:33 run is the
current number. This does not change the REPORT's bottom line (the agreement question is
unanswerable today) — it only changes what the reduced side alone found. Recorded in
`all-context.md`'s 18:47 Amendment so it does not stand unqualified in the durable context layer.

---

## Closeout Packet — Thread A: momentum-screener ADR-1 amendments

1. **Selected plan path:** `process/general-plans/active/momentum-screener_17-09-26/momentum-screener_PLAN_17-09-26.md`
2. **Closeout classification: Keep in active/testing** — the amendments themselves are finished
   and evidenced, but this is one ADR inside a large multi-RFC umbrella plan that is nowhere near
   fully verified (multiple RFC-* sub-plans still in progress in the same task folder). The
   umbrella plan does not become archive-ready because one ADR closed.
3. **What was finished:** both ADR-1 amendments (ROC formula fix, `SUSTAINED_DAYS` re-tune),
   confirming backtest run, plan text recording both per Change Management rule.
4. **Verified vs unverified:** Verified — the backtest JSON matches the plan's claimed numbers
   exactly (checked this session). Unverified — whether `leg_boundary.py`'s source change is
   committed to git (no device shell to check `git status`/`git diff` this session; not assumed).
4b. **Validate-contract:** not applicable to this specific ADR change — it's a post-EXECUTE fix
   documented via the plan's own Change Management rule, not a new VALIDATE pass. The umbrella
   plan's own original VALIDATE (for RFC-002, which this touches) is a separate, already-closed
   pass not re-litigated here.
5. **Cleanup done vs still needed:** Done — `all-context.md` now reflects both amendments. Still
   needed — none identified for this specific ADR; the umbrella plan's broader cleanup (multiple
   RFC sub-plans, `lse-data-verification` staleness) is tracked separately in §Plan Inventory.
6. **Single best next valid state:** Keep `momentum-screener_PLAN_17-09-26.md` active; no next
   phase is implied by this ADR closing — the umbrella program's next step is whatever the next
   unfinished RFC item is (not scoped by this closeout).
7. **Commit-checkpoint recommendation:** Execution commit recommended before any further process
   commit, **if not already committed** — this session could not run `git status` to confirm
   either way (no device shell, and git commands are out of scope for this session per the task
   instructions). Flag for the user to check before assuming clean.
9. **SPEC achievement:** see §SPEC Achievement above — no criterion status change.

## Closeout Packet — Thread B: liqtide-snapshot-tooling

1. **Selected plan path:** `process/general-plans/active/liqtide-snapshot-tooling_20-09-26/liqtide-snapshot-tooling_PLAN_20-09-26.md`
2. **Closeout classification: Keep in active/testing** — matches the REPORT's own classification.
   Code is complete and gated; the plan's stated purpose (prove full/reduced composite agreement)
   is unachieved and depends on archive accumulation that will take a long time.
3. **What was finished:** `LiqTidePayload.raw`, `fetch_latest(dry_run=)`, `snapshot_liqtide.py`,
   `compare_composite_variants.py`, `.gitignore` negation carve-out, `api/tests/scripts/` package
   (11 tests).
4. **Verified vs unverified:** Verified — all 4 checklist items, all 6 test gates (see §Test Gate
   Outcomes). Unverified — the actual deliverable (composite agreement); blocked on archive depth,
   not on code, and the archive now holds exactly 1 day (confirmed this session by direct device
   listing, contradicting the REPORT's literal "EMPTY" phrasing — see §What Was Done item 4).
4b. **Validate-contract:** present, inline in the plan (`## Validate Contract`), **Net Gate:
   CONDITIONAL** (0 FAIL / 2 CONCERN / 6 PASS), explicitly accepted in-plan ("Proceeding to
   EXECUTE with these two gaps on record is appropriate") — satisfies the VALIDATE→EXECUTE gate
   rule via the "explicitly accepted CONDITIONAL" path. Both CONCERNs (E1, E2) were closed during
   EXECUTE per the REPORT's Execute-Agent Instructions section (E1 SATISFIED, E2 DONE).
5. **Cleanup done vs still needed:** Done — `all-context.md` and `all-data-sources.md` now
   reflect the shipped tooling and its real limitation. Still needed — decide whether/how to run
   `snapshot_liqtide.py` on a schedule (explicitly out of scope per the plan); the un-run
   `_match`/`_verdict` unit-test gap (see §Test Infra Gaps Found).
6. **Single best next valid state:** Keep the plan active; no code work remains. The only forward
   path is time (archive accumulation) or a scope decision (see the new Open Questions entry in
   `all-context.md`) — not a next phase this closeout can name.
7. **Commit-checkpoint recommendation:** Execution commit recommended before any further process
   commit, **if not already committed** — same caveat as Thread A: not verified this session, no
   git access. Today's actual LiqTide payload (2026-09-20) is either archived already (the
   `2026-09-20.parquet` this session found) or was written some other way — this session did not
   determine which; flag for the user.
9. **SPEC achievement:** see §SPEC Achievement above — no SPEC exists for this plan.

---

## Forward Preview

### Test Infra Found
No new test infra this session (documentation-only). Carried forward: `api/tests/scripts/` is a
new pytest package (Thread B); the `integration` marker convention is unchanged.

### Blast Radius Changes
This session: `process/context/all-context.md`, `process/context/data-sources/all-data-sources.md`,
`process/general-plans/active/momentum-screener_17-09-26/update-process-closeout_20-09-26.md`
(new file). No `api/` or `web/` files touched.

### Commands to Stay Green
`cd api && uv run pytest tests/ -x -q` (Thread B's regression gate — unaffected by this session).

### Dependency Changes
None.

---

## Plan Inventory (`vc-audit-plans` — by inspection, validator not run)

`node .claude/skills/vc-audit-plans/scripts/validate-plan-inventory.mjs` could not be run (no
device shell). Inventory below is from the `device_list_dir --recursive` listing of
`process/general-plans/active/` taken this session.

| Task folder | Plan file | Status header | Classification | Action |
|---|---|---|---|---|
| `momentum-screener_17-09-26/` | `momentum-screener_PLAN_17-09-26.md` (+ 5 sub-RFC plans) | Status strip: ⏳ PLANNED (stale header — most RFCs are actually ✅ VERIFIED per their own phase reports; the top-of-file status strip was never updated) | **Active** (large program, genuinely in progress) | Stays in `active/` — standing precedent below. Note the stale top-of-file "⏳ PLANNED" status strip as a minor drift item; not corrected this session (plan-file edits out of scope) |
| `liqtide-snapshot-tooling_20-09-26/` | `liqtide-snapshot-tooling_PLAN_20-09-26.md` | "Ready for VALIDATE review / EXECUTE pending approval" (stale — EXECUTE already ran) | **Active/testing** | Stays in `active/` per this closeout's Thread B classification |
| `lse-data-verification_17-09-26/` | `lse-data-verification_PLAN_17-09-26.md` | ⏳ PLANNED, Owner: unassigned | **Stale — flagged, not acted on** | See below |

**Standing precedent applied (not re-derived):** `dead-data-notice-unification_20-09-26-phase-report.md`
(lines ~174–196) records that individual RFC/slice plans inside `momentum-screener_17-09-26/`
**stay in `active/`** and the task folder archives as a unit **only when the whole
momentum-screener program is done** — "that has not happened yet." This closeout applies the same
rule to Thread A rather than re-deciding it: the ADR-1 amendments closing does not move the
umbrella plan or task folder.

**`lse-data-verification_17-09-26` staleness finding:** created 17-09-26, status ⏳ PLANNED,
owner unassigned, zero file activity since creation (single file in the folder, mtime unchanged
across this session's listing). Three full days with no RESEARCH/INNOVATE/PLAN-supplement/EXECUTE
activity and no explicit "deferred" note anywhere in the plan or in `all-context.md`'s Open
Decisions (which still lists the equity-provider decision as "Still unresolved" without
referencing this plan as blocked or paused). This reads as **simply not started**, not abandoned
mid-work — flagged for the user to decide: resume it, explicitly deprioritize (record why in the
plan or in Open Decisions), or move it to `backlog/`. Not acted on unilaterally.

**Task-folder colocation check (per audit-plans §3.5):** all three task folders keep their
PLAN/REPORT/REF/SPEC artifacts inside the task folder itself — no stray files found in a legacy
sibling `reports/`/`references/` directory during this session's listings. No mis-located
artifacts to flag.

## Context Audit (`vc-audit-context` — by inspection, validators not run)

None of `validate-context-discovery.mjs`, `validate-protocol-discovery.mjs`,
`validate-skill-routing.mjs`, `validate-skill-cross-refs.mjs`, `validate-skill-dependencies.mjs`,
`validate-confusable-skills.mjs`, `generate-skills-catalog.mjs --check`, or
`validate-skill-keywords.mjs` could be run this session (no device shell). Checks performed by
direct inspection instead:

| Check | Method | Result |
|---|---|---|
| `all-context.md`'s `<!-- GENERATED:routing -->` block left untouched | Diffed my edits against the block's line range | **PASS by inspection** — all edits were outside the marked block; routing table rows unchanged |
| New/renamed context entrypoints need frontmatter + router row | This session added prose, not a new file or a new `all-{group}.md` | **N/A** — no new entrypoint created |
| `all-data-sources.md`'s own Standing Rules still consistent with its new paragraph | Re-read Standing Rule 8 against the new LiqTide paragraph | **PASS by inspection** — the new paragraph reports Rule 8 as now-implemented, does not contradict or restate it |
| Skill catalog (`process/context/generated-skills-catalog.json`) still in sync | Not checked — no skill/agent files changed this session, so no drift expected, but **not verified** (file not read) | **NOT PERFORMED** |
| Protocol-discovery frontmatter on `process/development-protocols/**/*.md` | Not checked — no protocol files edited this session | **NOT PERFORMED (not triggered)** |
| Cross-surface mirror (Codex `.codex/agents/`, `AGENTS.md`) | Not checked — no agent/skill files edited this session | **NOT PERFORMED (not triggered)** |

**Per §U2 trigger rule** (`process/context/` files were modified this session): `vc-audit-context`
is not optional housekeeping per the agent contract. It is flagged here as still owed — the
validator-backed checks above (routing drift, skill-routing coverage, cross-ref, dependency,
catalog sync, keyword lint) have **not** been run and should be run by the user (or a session with
device shell access) before treating the context layer as fully reconciled. This is a concern, not
a blocker — the prose edits themselves were scoped and low-risk (no file moves, no new entrypoints,
no frontmatter changes).

## Context File Audit Table (per-file, required gate)

| File | Reviewed? | Changed? | Reason |
|---|---|---|---|
| `process/context/all-context.md` | Yes | **Yes** | Stale as of 17:46; both ADR-1 amendments + liqtide tooling outcome landed after |
| `process/context/data-sources/all-data-sources.md` | Yes | **Yes** | Standing Rule 8 now implemented in code; forward-only archive constraint now confirmed operationally |
| `process/context/planning/all-planning.md` | Reviewed (listed, not opened) | No | Nothing this session changed plan-shape calibration or SIMPLE/COMPLEX conventions |
| `process/context/tests/all-tests.md` | Reviewed (listed, not opened) | No | No test runner, command, or verification-order change this session (the new `api/tests/scripts/` package follows the existing pytest convention exactly — no new pattern to document) |
| `process/context/_all-group-template.md.seed`, `all-context.md.seed`, `planning/all-planning.md.seed`, `tests/all-tests.md.seed` | Listed | No | Seed/template files, not live docs — out of scope by convention |
| `process/context/generated-skills-catalog.json` | Listed, not opened | No | No skill/agent surface changed this session |
| `process/features/*/_GUIDE.md` (charting-indicators, cointegration-screener, cycle-regime, narrative-mindshare) | Not individually opened — confirmed still placeholder-only per `all-context.md`'s own prior scan note | No | Nothing this session touches charting, cointegration, cycle-regime UI, or narrative work; both threads are macro-liquidity backend tooling already routed through `data-sources` |

---

## Drift Signal Scoring

| Signal | Present? | Points |
|---|---|---|
| (a) Files touched during the reconciled EXECUTE work | ≥1 file: yes; ≥10 files: yes (leg_boundary.py, plan text, liqtide_adapter.py, 2 new scripts, .gitignore, 1 new test package, multiple JSON artifacts) | +2 |
| (b1) `.claude/`/`.codex/`/agent harness file changed | No | +0 |
| (b2) README/AGENTS/CLAUDE.md/development-protocols changed | No | +0 |
| (c) 3+ memory-worthy observations | Yes — ROC divisor mechanism, SUSTAINED_DAYS evidence table, liqtide forward-only-archive constraint, stale-report-number reconciliation | +1 |
| (d) Feature-folder structural change | No (no folder created/archived/moved; no backlog NOTE written) | +0 |
| (e) Validate-contract deviation | Yes — Thread A's amendments are post-EXECUTE changes made after the original validate-contract pass closed, based on new empirical evidence not available at VALIDATE time | +1 |

**Score: 4 — HIGH.**

**Strongly recommend UPDATE PROCESS -- harness/protocol files touched.**

(Required verbatim phrase per the HIGH band — no harness/protocol file was actually touched this
session; the phrase is machine-matched to the band, not restated to fit. The real drivers of this
HIGH score are the file-count and observation-count signals above, not a harness edit.)

## Commit-Checkpoint Recommendation

**Cannot confirm current git state** — this session has no device shell and was explicitly told
not to run `git`. Recommendation is therefore conditional:

1. **If Thread A's and Thread B's source changes are not yet committed:** commit them first, as
   two separate execution commits (or one, if the user prefers) — `api/analytics/regime/leg_boundary.py`
   + the plan-text ADR amendments for Thread A; `api/data/liqtide_adapter.py`,
   `api/scripts/snapshot_liqtide.py`, `api/scripts/compare_composite_variants.py`, `.gitignore`,
   `api/tests/scripts/` for Thread B.
2. **Then commit this session's process-only changes** (`process/context/all-context.md`,
   `process/context/data-sources/all-data-sources.md`, the closeout file) as a separate process
   commit, per the two-commit content rule (source commit ≠ process commit).
3. Do not commit today's LiqTide archive payload (`api/data/cache/liqtide/2026-09-20.parquet`)
   as part of the process commit — it is data, not process/context, and whether it's already
   staged/committed was not checked this session.

---

## Final Checklist (Phase 5)

- Claude surface: updated (`process/context/all-context.md`, `all-data-sources.md`)
- Codex surface: explicitly unchanged — no agent/skill/protocol file touched, mirror review not
  triggered
- `process/` docs: updated (context) + created (this closeout); no plan files moved or edited
- Context files reviewed: full table above — 2 changed, 2 reviewed-unchanged, seeds/catalog/guides
  listed and intentionally skipped with reason
- Validators run: **none** (no device shell) — see §Audits for by-inspection substitutes and what
  remains genuinely unverified

## Move-On Recommendation

- **Selected plans:** both stay `active/` — no archival this session.
- **Resulting archival state:** unchanged from before this session, now accurately documented.
- **Durable artifacts updated:** `all-context.md`, `all-data-sources.md`, this closeout.
- **Deferred follow-ups / blockers:**
  1. Run the `vc-audit-context` validator suite (routing drift, skill routing/cross-ref/dependency,
     catalog sync, keyword lint) from a session with device shell access — not run this session.
  2. Run the `vc-audit-plans` inventory validator likewise.
  3. User decision needed on `lse-data-verification_17-09-26` (resume / deprioritize / backlog).
  4. User decision needed on the full-vs-reduced composite comparison's long time horizon (accept
     the wait, look for a LiqTide-history backfill path, or drop the goal) — new Open Questions
     entry in `all-context.md`.
  5. Confirm git state and commit per §Commit-Checkpoint Recommendation.
  6. Backlog NOTE candidate: `compare_composite_variants.py`'s `_match`/`_verdict` has no unit
     test (carried from the REPORT, not newly found).
- **Exact next phase:** none implied — both threads remain in their current `active/testing`
  state pending the user decisions above. No plan file names a next phase from here.
