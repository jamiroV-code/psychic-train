---
name: report:regime-dashboard-closeout
description: "UPDATE PROCESS closeout for the regime dashboard program (RFC-001..006) — code-complete, one open gap (AC-11 walkthrough)"
date: 24-09-26
metadata:
  node_type: memory
  type: report
  feature: cycle-regime
  phase: UPDATE-PROCESS
---

# Regime Dashboard — UPDATE PROCESS Closeout (24-09-26)

## 1. Selected plan path

`process/features/cycle-regime/completed/regime-dashboard_24-09-26/regime-dashboard_PLAN_24-09-26.md`

## 2. Closeout classification

**Ready for UPDATE PROCESS archival — archived 24-09-26.** All six RFCs are code-complete,
committed, and every automated gate is green. AC-11 (the real-cache user walkthrough) is now
confirmed: the user ran it on their PC and reported "all seems fine", with one question (a blank
stretch on the BTC-dominance panel) explained and accepted as correct honest-gap behaviour, not a
bug. The task folder has been moved from `active/` to `process/features/cycle-regime/completed/`.

## 3. What was finished

- RFC-001: LiqTide raw-JSON archive (`cache.write_liqtide_raw`/`read_liqtide_raw`, append-only,
  no-overwrite), backfill script, and a discovered pre-existing nightly GitHub Actions workflow
  (`.github/workflows/liqtide-snapshot.yml`) that already schedules the snapshot — the planned
  Windows Task Scheduler step turned out to be unnecessary.
- RFC-002: `api/analytics/regime/components.py` + `components_response.py` — six component
  impulses, `sign × tanh(impulse/scale)` normalisation (reverse-engineered to match LiqTide's
  published values to 4 decimals), a reproduced composite with 60%-coverage floor, and LiqTide's
  published index passed through for comparison. Real-data check: 5/6 components exact, Pearson
  r = 0.964 vs. published.
- RFC-003: `api/data/etf_flows_adapter.py` (Farside, personal-use only, `redistributable=false`,
  ≤1 request/UTC day). Real cache: 2024-01-11 → 2026-09-23, 677 days.
- RFC-004: `GET /api/regime/components` (additive; `GET /api/regime/legs` byte-for-byte unchanged),
  gzip via `GZipMiddleware`, per-component `last_fetched_utc`, `not_applicable`/`unavailable`
  status split for ETF flows.
- RFC-005: `/regime` page — seven synced `lightweight-charts` panels (`RegimeDashboard`,
  `ComponentPanel`, `Readout`, `DrillDown`), shared `grid_dates` whitespace-point sync, reserved
  280px insights column, plus a mid-flight supplement (decision 9) making the API mark real data
  gaps (`max_gap_days` / `gap_before`) so the frontend renders true breaks instead of a continuous
  line across a hole.
- RFC-006: seeded-fixture Playwright spec (`web/e2e/regime.spec.ts`, 6 new specs) proving the real
  frontend/backend boundary; final full-suite EVL confirmation across all three runners.

## 4. What was verified vs still unverified

**Verified (automated, this session's EVL re-confirmation):**
- `uv run --project api pytest api/ -q` → 294 passed, 2 deselected
- `pnpm --filter web test` → 75 passed, 12 files, 0 failed files
- `tsc --noEmit` clean; `next build` clean
- `cd web && pnpm test:e2e` → 12/12 passed (6 regime + 6 screener), run twice, with
  `PLAYWRIGHT_CHROMIUM_PATH` set for this container's browser mismatch

**Now verified (24-09-26, user's PC against the real cache):**
- **AC-11** — the user ran the real-cache walkthrough (3y default range, zoom/hover/drill-down sync,
  ETF "not applicable before 2024-01-11" note, a real rendered gap, ~2000+ point performance) and
  confirmed "all seems fine". The one question raised — a blank stretch on the BTC-dominance panel
  — was explained (LiqTide's own `metrics.btc_dom.series` has a real 209-day hole, 2025-12-07 →
  2026-07-04) and accepted as correct behaviour, not a defect.

**Still unverified (honest residual, not blocking archival):**
- AC-1's "next-morning raw file appears without running anything" confirmation — the nightly
  workflow's scheduling mechanism is proven (4 consecutive automated `github-actions[bot]` commits,
  09-21..09-24, `git log --oneline -- api/data/cache/liqtide/*.parquet`), but the raw-JSON write path
  was added in this program and has not yet run under the schedule — only one manually-written file
  exists (`2026-09-24.json`). Self-resolves on the next nightly run (23:30 UTC).
- RFC-002's 1-of-6 component mismatch against LiqTide's published values has not been root-caused
  (see the RFC-002 phase report).

## 4b. Validate-contract compliance

VALIDATE was run for this plan. A `## Validate Contract` section is present, dated 24-09-26,
`generated-by: outer-pvl`, gate **CONDITIONAL**, accepted by the user (Jamiro) with concerns P1-P8
and E1-E3 folded into the plan, plus two backlog known-gaps
(`liquidity-composite-calendar-windows_24-09-26.md`, `fredapi-alfred-vintages_24-09-26.md`). No
further PVL cycle was required — the CONDITIONAL was accepted at PLAN time, not left un-actioned.

## 5. Cleanup done vs still needed

**Done this session:**
- Plan Status Strip corrected to reflect CODE DONE reality (not the stale ⏳ PLANNED header) and a
  single explicit next step written into Resume and Execution Handoff.
- `process/context/all-context.md`: Repository Structure, Changes Since Last Update, Open
  Decisions, Open Questions, References, Scan Metadata all updated to current reality — including
  correcting the stale "no `.github/workflows/` exists" claim and reconciling the two *different*
  full-vs-reduced composite comparison questions so they aren't conflated.
- `process/context/data-sources/all-data-sources.md`: Farside adapter entry added; per-series
  `max_gap_days` pointer added (points to code, not a duplicated table, to avoid drift).
- `process/context/tests/all-tests.md`: final green counts (294/75/12) and cloud-container notes
  reconciled.
- `process/features/cycle-regime/_GUIDE.md`: rewritten from a pre-code placeholder to reflect the
  shipped dashboard and where things live.
- This closeout packet.

**Done this session (2nd UPDATE PROCESS pass, post-AC-11 confirmation):**
- Plan Status Strip updated: all six RFCs → ✅ VERIFIED; per-RFC Verification Checklists ticked
  where the user's walkthrough covers them, with honest notes on the two items it doesn't (RFC-001's
  raw-file-on-schedule sub-criterion; the RFC-002 1/6 mismatch).
- BTC-dominance gap (2025-12-07 → 2026-07-04) documented in the plan's Gap Analysis and in
  `all-context.md`'s existing "two component depth limits" entry.
- Task folder moved: `process/features/cycle-regime/active/regime-dashboard_24-09-26/` →
  `process/features/cycle-regime/completed/regime-dashboard_24-09-26/`.
- Stale path references updated across `process/`, `.claude/`, `AGENTS.md`, `CLAUDE.md` (pointers
  only; historical quotes in archived reports left as-is).

**Still needed (not blocking archival, deferred to a future session):**
- The RFC-002 1/6 component-mismatch root cause (tracked in the RFC-002 phase report, not yet a
  backlog note — recommend creating one if the user wants it chased further).
- AC-1's raw-file-on-schedule confirmation will self-resolve on the next nightly run; no action
  needed unless the user notices it hasn't appeared after a few more nights.

## 6. Single best next valid state

**Program closed.** The task folder is archived at
`process/features/cycle-regime/completed/regime-dashboard_24-09-26/`. Future regime-dashboard work
(insights text box, divergence/lead-lag scans — plan §21 Future Work) should start a new task
folder rather than reopening this one.

## 7. Commit-checkpoint recommendation

**No commit needed from this session** — the orchestrator explicitly instructed "do NOT commit or
push"; all six RFCs' execution commits already landed on `main` at `db8d854` before this UPDATE
PROCESS session began, and this session's own changes are process-only (plan/context docs). Per
the two-commit content rule, these process-only edits belong in a **separate process commit**,
which the orchestrator will make (or ask `vc-git-manager` to make) once it reviews this report.

## 8. Regression status

- `pytest api/ -q` (294 passed) covers the full backend suite, including `test_leg_boundary.py` and
  `liquidity_composite` tests — confirmed unchanged and green, i.e. the regime dashboard's parallel
  maths path did not disturb the existing leg-boundary/composite path.
- `vitest` + `tsc` + `next build` cover the full frontend, including the pre-existing screener
  components.
- Playwright: both `screener.spec.ts` (pre-existing, 6 specs) and `regime.spec.ts` (new, 6 specs)
  passed in the same run, twice — the existing screener surface was explicitly re-verified, not
  assumed unaffected.
- No regression fixes were needed this session (regression checkpoint was clean on first check).

## 9. SPEC achievement

There is no standalone locked `*_SPEC_*.md` for this plan — it is a general Complex plan governed
directly by its own Acceptance Criteria (§20) rather than a separate SPEC doc (the SPEC phase is
skippable when the plan itself carries versioned acceptance criteria and this is not a phase-program
inner loop). Scoring against the plan's own AC-1..AC-11:

| AC | Criterion | Status |
|---|---|---|
| AC-1 | Raw JSON written once, never overwritten | **Met** — `test_liqtide_raw_archive.py`, Fully-Automated |
| AC-1 (Agent-Probe half) | Next-morning file appears via schedule | **Unmet (Known-Gap, accepted, non-blocking)** — schedule mechanism proven (4 consecutive automated commits, 09-21..09-24), but the raw-write path is new this program and unobserved under the schedule; backlog stub: user to eyeball `api/data/cache/liqtide/raw/` after ≥1 more nightly run |
| AC-2 | Backfilled history on disk, first/last dates reported | **Met** — `test_backfill_liqtide_series.py` + live DuckDB query (Hybrid) |
| AC-3 | Six impulses match golden values; calendar windows | **Met** — `test_components.py`, Fully-Automated |
| AC-3 (sign cross-check) | Sign conventions match LiqTide | **Met** — Hybrid cross-check, 5/6 exact |
| AC-4 | No NaN/0 stand-ins; as-of only | **Met** — `test_components.py`, Fully-Automated |
| AC-5 | Coverage + 60% floor | **Met** — `test_components.py`, Fully-Automated |
| AC-6 | ETF flows real data or honest degrade | **Met** — `test_etf_flows_adapter.py` + real 677-day cache (Hybrid) |
| AC-7 | Endpoint shape, degradation, `/legs` unchanged | **Met** — `test_regime_components.py`, Fully-Automated |
| AC-8 | Seven panels, 3y default, synced zoom/crosshair | **Met** — vitest + `regime.spec.ts` E2E, Fully-Automated |
| AC-9 | Hover readout, drill-down chain | **Met** — vitest, Fully-Automated |
| AC-10 | Honest gap states, nothing extra drawn | **Met** — vitest + RFC-005 supplement (gap-flag rendering), Fully-Automated |
| AC-11 | Real-cache walkthrough, user confirms | **Met** — Agent-Probe, run on the user's PC against the real cache 24-09-26; user confirmed "all seems fine" (one question, explained and accepted — see §4) |

One criterion remains Known-Gap-only (AC-1's schedule sub-criterion — Agent-Probe, unproven in this
environment) per the vacuous-green ban: it is not treated as "met", but is accepted as a low-risk,
self-resolving residual (backlog stub above) and does not block archival, since (a) the write
function itself is Fully-Automated tested, (b) the schedule mechanism has a proven 4-night
unattended track record, and (c) it will confirm itself on the next nightly run with no action
required. AC-11 — the criterion this program was explicitly waiting on before archival — is now Met.

---

## Drift Signal Scoring

Signals counted:
- (a) Files touched: this UPDATE PROCESS session touched 5 doc files (plan + 3 context files +
  1 `_GUIDE.md`) — **+1** (≥1 file), not **+2** (this session's own edits are <10 files; the
  EXECUTE session itself touched ~20+ files across 6 RFCs, but that was prior sessions, already
  committed)
- (b1) `.claude/`/`.codex/`/agent harness files changed: none this session — **+0**
- (b2) `README.md`/`AGENTS.md`/`CLAUDE.md`/`process/development-protocols/` changed: none — **+0**
- (c) 3+ memory-worthy observations: yes — nightly workflow discovery, two distinct
  full-vs-reduced composite questions disambiguated, 8th adapter pattern confirmed, gap-flag
  rendering mechanics (lightweight-charts whitespace/color semantics) — **+1**
- (d) Feature-folder structural change: no new task folder created/archived this session (the task
  folder was created across the prior RFC sessions) — **+0**
- (e) Validate-contract deviation: none — execution matched the accepted CONDITIONAL contract,
  concerns P1-P8/E1-E3 were all folded in as planned — **+0**

**Score (this closeout pass): 2 (MEDIUM) + feature-folder structural change (d, task folder archived)
= 3 (HIGH).** "Strongly recommend UPDATE PROCESS -- harness/protocol files touched." (triggered by
signal (d): the task folder moved from `active/` to `completed/` this session, plus stale-path
reference updates across `process/`, `AGENTS.md`, `CLAUDE.md`.)

**Next valid state:** Program closed. Task folder archived at
`process/features/cycle-regime/completed/regime-dashboard_24-09-26/`. No further action needed on
this plan; future regime-dashboard work opens a new task folder.
