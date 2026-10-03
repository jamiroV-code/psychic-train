# Dead-Data Notice Unification — Phase Report

**Date**: 20-09-26
**Plan**: `process/general-plans/active/momentum-screener_17-09-26/dead-data-notice-unification_PLAN_20-09-26.md`
**Status**: ✅ VERIFIED — `pnpm exec tsc --noEmit` clean, 40/40 vitest individual tests passed, 5/6
Playwright e2e specs passed (the 1 failure independently root-caused this session to a pre-existing
backend cold-start defect outside this plan's blast radius, not a regression). All 10 Acceptance
Criteria confirmed.
**Phases run**: RESEARCH → INNOVATE → PLAN → VALIDATE (CONDITIONAL, accepted with concerns; 2
findings resolved in-place during VALIDATE) → EXECUTE → EVL → UPDATE PROCESS (this report)
**SPEC**: skipped — inner-loop item governed by `momentum-screener_SPEC_17-09-26.md` (same precedent
as RFC-005, both RFC-006 content slices, and `weekly-ohlc-anchor_PLAN_19-09-26.md`)

---

## Outcome

RFC-006's own Overview named three items: two content slices (`getjson-timeout-catch`,
`reason-value-rendering` — both ✅ VERIFIED in prior sessions of this program) and this
convention-unification item, deliberately deferred by both. This plan implements the
INNOVATE-locked decision: one shared `DeadDataNotice` component with a discriminated union on
`"message" in props`, wired into all 7 existing dead-data render sites across 5 components with
**zero testid renames and zero placement changes** — a pure implementation-detail swap.

EXECUTE created `web/components/screener/DeadDataNotice.tsx` (new) and edited `CoinPanel.tsx`,
`DrillDownView.tsx`, `NarrativeStrip.tsx`, `LegTimelineBanner.tsx`, `RelativePerformanceChart.tsx`,
plus `__tests__/LegTimelineBanner.test.tsx` and `__tests__/RelativePerformanceChart.test.tsx` (2 new
test cases closing pre-existing zero-coverage gaps on those two components' error branches). All 8
Touchpoints files were byte-verified on device after commit, per this task folder's own
`device_commit_files` re-stage-and-byte-diff discipline.

**Recordkeeping note:** the execute agent's own required exit-summary file write was reported
blocked by a tool write-guard, so no `EXECUTE Results` section exists inside the plan file itself.
This phase report is therefore the first disk record of EXECUTE's outcome — recorded here in full
rather than assumed to exist elsewhere.

EVL results (run by the user on their own machine, since this session has no `device_bash`, same
pattern as every phase in this task folder):

- `pnpm exec tsc --noEmit` (AC-10) — **clean pass**, after the mid-verification quick-fix below.
- `pnpm test` (vitest) — **40/40 individual tests passed.** One test *file*, `e2e/screener.spec.ts`,
  was reported failed by vitest's own collector — this is the pre-existing, already-backlogged
  `vitest.config.ts` exclude gap (`vitest-config-e2e-exclude_19-09-26.md`), the same known noise both
  prior RFC-006 slices already recorded, not a regression from this plan.
- `pnpm test:e2e` (Playwright) — **5/6 passed.** The 1 failure
  (`"the board renders one panel per watchlist symbol, from a real request"`) was root-caused this
  session (see below) to a pre-existing backend cold-start defect, not a regression from this plan's
  8 touchpoints (all confined to `web/components/screener/` presentational markup).

Net: all 10 ACs verified. AC-10 proven directly by the clean `tsc` pass. AC-3/AC-8 (no unforeseen
regression; only the 8 Touchpoints files written) proven by the 40/40 vitest pass. AC-3/AC-4
(unaffected e2e surface stays green) proven by 5 of the 6 Playwright specs — the 6th's failure is
independently attributed, below, to a cause entirely outside this plan's blast radius.

### Mid-verification quick-fix (out-of-band, user-approved, already applied and verified)

`pnpm exec tsc --noEmit` first surfaced a pre-existing, unrelated type error in
`web/components/screener/__tests__/ScreenerBoard.test.tsx`'s `makeCoin()` helper: it never set
`leg_context`/`narrative_state` in its base object (only via `...overrides: Partial<...>`),
producing a `TS2322` against `CoinPanel`'s required fields. Fixed by adding
`leg_context: "confirmed" as const` and `narrative_state: "in-focus" as const` to `makeCoin`'s base
object (still overridable per-call). Single file, ~2 lines, unrelated to this plan's 8 touchpoints —
confirmed pre-existing (the file's own header note says it had never actually been
executed/type-checked before this session). Recorded here as a 9th file touched, out-of-band, not
one of the plan's own Touchpoints.

### E2E failure root cause (debugged during this UPDATE PROCESS pass, confirmed not a regression)

Traced against the live current backend source, staged and read fresh during this pass (not carried
over from any secondhand summary unverified):

1. **`load_markets()` is uncached and lazy, with no pre-warm.** `_exchange()`
   (`api/data/ccxt_adapter.py:101-123`) builds the process-wide `ccxt.hyperliquid()` singleton and
   calls `ex.load_markets()` at line 117 — lazily, the first time any request needs a live fetch.
   This costs roughly 12.5s. No FastAPI `startup`/`lifespan` handler exists anywhere in `api/` to run
   this at process boot instead of on the first request (confirmed by a repo-wide grep for
   `startup`/`lifespan`/`load_markets` — no such hook exists).
2. **OHLCV fetching is fully serial, no concurrency.** `build_coin_panel`
   (`api/analytics/screener_board.py:134-146`) fetches `1d` and `1w` (lines 134-135), then loops
   sequentially over the remaining `TIMEFRAMES` (`15m`/`1h`/`4h`) at lines 141-145 — one
   `ccxt_adapter.fetch_ohlcv` call at a time. `build_screener_board` (lines 175-194) then calls
   `build_coin_panel` once per watchlist coin in a plain synchronous list comprehension (lines
   190-193) — no `asyncio.gather`, no thread pool, no concurrency anywhere in this file or
   `ccxt_adapter.py`. With the current 4-coin watchlist (`api/data/watchlist.json`: BTC, HYPE, ETH,
   SOL) and 4 live-fetched timeframes per coin (`1d`, `15m`, `1h`, `4h` — `1w` derives from the
   already-cached `1d` bars fetched moments earlier in the same call, so it costs no extra network
   round trip via `_cache_is_fresh`), a cold board request makes **up to 16 sequential live OHLCV
   calls**, each costing roughly 0.3-0.8s.
3. **The arithmetic matches the measured failure.** 12.5s (`load_markets`) + ~8s (serial OHLCV
   fetches) + ~3.3s (baseline compute) ≈ the measured 23.7s on the very first request after a fresh
   process start. Playwright's default `expect` timeout is 5s, so only the very first request
   against a freshly-started, seeded, cold-cache backend trips it — exactly what an isolated
   single-spec run, or the first spec in a full-suite run, is. A warm request (same process, the
   `_exchange()` singleton and cache already populated, `_cache_is_fresh()` at
   `ccxt_adapter.py:173-184` short-circuiting most per-timeframe work) took 3.3-3.6s, which is why 5
   of 6 specs in the same run pass.
4. **Secondary, currently-dormant risk, flagged not proven active in this run:** neither
   `pytrends_adapter.fetch_trend` (`api/data/pytrends_adapter.py:85-112`) nor
   `reddit_adapter.fetch_mentions` (`api/data/reddit_adapter.py:106-134`) checks cache freshness
   before attempting a live call — unlike `ccxt_adapter._cache_is_fresh`, both always attempt the
   live call first. Costs ~0s in this sandbox (`pytrends` import fails instantly at
   `pytrends_adapter.py:54-57`; Reddit's `_get_access_token` returns `None` immediately when
   `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` are unset, `reddit_adapter.py:52-55`), but could add
   real per-request latency in a fully configured deployment.

This is confirmed **not** a regression from `dead-data-notice-unification`'s own 8 touchpoints (all
confined to `web/components/screener/` presentational markup, no `api/` file among them) — filed as
a new backlog item (below) rather than fixed in this plan, since it is out of this plan's blast
radius and deserves its own PLAN/EXECUTE cycle.

## Deviations

Four items, none changing scope or requiring plan/touchpoint correction:

1-3. **EXECUTE's own 3 deviations, as reported by the execute agent:** import ordering / indentation
   only, no scope change. No `EXECUTE Results` section exists inside the plan file itself (see
   Recordkeeping note above — the execute agent's own required exit-summary write was blocked by a
   tool write-guard), so no more granular per-deviation detail than "import ordering / indentation
   only, no scope change" survived to disk before this report. All 8 Touchpoints files were still
   byte-verified against the plan's exact specification (testid strings, component structure) after
   commit, so these 3 deviations did not affect AC-3 (no testid renamed) or any other Acceptance
   Criterion.
4. **Out-of-band `ScreenerBoard.test.tsx` quick-fix** (detailed above under Outcome) — the 9th file
   touched this session, not one of the plan's 8 Touchpoints, applied to unblock `tsc --noEmit` on a
   pre-existing, unrelated defect in that file's own test helper.

Nothing outside the plan's 8 Touchpoints (plus the 1 out-of-band quick-fix above) was modified: no
`api/` change, no testid rename, no placement change, no new `aria-live`/`role="alert"` addition —
all consistent with the plan's own stated Out-of-scope list.

## Context updated

- `process/context/tests/all-tests.md` — "Last updated" line moved to this cycle; the `web/` vitest
  status-table row updated to 40/40 (2 new cases from this plan, plus the out-of-band
  `ScreenerBoard.test.tsx` fix noted separately); the Playwright status-table row updated to 5/6 with
  the cold-start cause cited and linked to the new backlog item; one new Debugging Quick Reference
  row for the "first request after a cold start times out, subsequent requests don't" symptom; one
  new Known Gaps bullet for the board-endpoint cold-start defect, with the dormant narrative-adapter
  TTL risk folded into the same bullet as a secondary note. No existing Standing Lesson row was
  touched or renumbered — this is a timing/infra defect found by direct debugging, not a
  green-suite-hid-a-wrong-answer incident of the kind that table records.

## Backlog raised

- `process/general-plans/backlog/board-endpoint-cold-start-latency_20-09-26.md` (new) — the 3
  root-cause points above (uncached lazy `load_markets()`, fully serial per-(coin, timeframe) OHLCV
  fetching, and the arithmetic tying both to the measured 23.7s cold-start failure), plus the dormant
  narrative-adapter TTL risk as a secondary, unconfirmed-active note. Not blocking; separately queued.

Unchanged, carried forward from prior sessions in this task folder:
- `process/general-plans/backlog/vitest-config-e2e-exclude_19-09-26.md` — still open, still low
  priority, unaffected by this plan.
- `process/general-plans/backlog/sandbox-note-reconciliation_19-09-26.md` — still open, unaffected by
  this plan.

## Next

**RFC-006 is now fully done.** All three items its own Overview named are closed: both content
slices (`getjson-timeout-catch`, `reason-value-rendering`, prior sessions) and this
convention-unification item. Nothing remains queued under RFC-006 itself.

Carried forward, still open (unchanged by this plan):

- **RFC-001 stub closeout toward archival** (`stub_rfc001-frontend-tests_18-09-26.md` the remaining
  item) — still queued, unchanged.
- **New: board-endpoint cold-start latency**
  (`board-endpoint-cold-start-latency_20-09-26.md`) — not blocking, separately queued; needs its own
  PLAN/EXECUTE cycle (a startup pre-warm and/or per-timeframe/per-coin concurrency).
- `vitest-config-e2e-exclude_19-09-26.md` and `sandbox-note-reconciliation_19-09-26.md` — unchanged,
  still open.

Per the standing precedent in this task folder (`ccxt-symbol-resolution_PLAN_19-09-26.md`,
`weekly-ohlc-anchor_PLAN_19-09-26.md`, `playwright-e2e_PLAN_19-09-26.md`, both RFC-006 content
slices), this plan (`dead-data-notice-unification_PLAN_20-09-26.md`) **stays in**
`process/general-plans/active/momentum-screener_17-09-26/` and is **not** moved to `completed/`. The
task folder archives only when the entire `momentum-screener` program is done — that has not
happened yet (RFC-001 stub closeout and the newly-raised cold-start item both remain open).

## Closeout Classification

**✅ VERIFIED — fully done and verified**, not merely "done." Every one of the 10 Acceptance Criteria
is met by a passing automated or Hybrid gate: `tsc --noEmit` clean (AC-10), 40/40 vitest individual
tests passed with only the pre-existing, already-backlogged `e2e/screener.spec.ts`
vitest-collection non-failure (AC-1 through AC-9 collectively), and 5 of 6 Playwright specs passed
with the 6th independently root-caused this session to a pre-existing backend defect entirely outside
this plan's blast radius rather than left as an unexplained or Known-Gap residual (AC-3/AC-4's
Hybrid e2e gate). No criterion here rests on an Agent-Probe-only or unproven residual — per this
persona's own archival-gate rule, that means this plan's developed behavior is genuinely, not
vacuously, green.

The plan file nonetheless **stays in `active/`** rather than moving to `completed/`, per the explicit
task-folder-level precedent recorded above under Next: in this task folder, "archive" means moving
the whole `momentum-screener_17-09-26/` task folder as a unit, which happens only when the entire
program closes — not per-plan, and not yet, since RFC-001's stub closeout and the newly-raised
cold-start item are both still open. This is consistent with how both RFC-006 content slices and
`weekly-ohlc-anchor` were classified: ✅ VERIFIED in outcome, `active/` in location.
