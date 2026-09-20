# Phase Report — Playwright E2E

**Date**: 19-09-26
**Plan**: `process/general-plans/active/momentum-screener_17-09-26/playwright-e2e_PLAN_19-09-26.md`
**Status**: ✅ VERIFIED — 6 passed (`pnpm test:e2e`), reported directly by the user
**Phases run**: RESEARCH → INNOVATE → PLAN → EXECUTE → DEBUG → EVL → UPDATE PROCESS (this report)
**SPEC**: skipped — inner-loop item under `momentum-screener_SPEC_17-09-26.md`

---

## Outcome

First real run of the frontend/backend boundary this project has ever had. Before this, seven
vitest suites all passed fakes to `ScreenerBoard`'s `fetchBoard`/`fetchScalp` props — the real
client (`web/lib/api/screener.ts`), real CORS, real FastAPI routing and the FastAPI↔TypeScript
response shape had never been executed by any test.

| | Before | After |
|---|---|---|
| Frontend/backend boundary coverage | none | 6 specs, real API + real browser |
| First E2E run | 5 of 6 failed | — |
| Root cause | one line in `seed_e2e_cache.py`: bare JSON array where `watchlist.py` expects `{"coins": [...]}` | fixed |
| Second E2E run | — | 6 of 6 passed |
| Board request against the seeded fixture | 500, every timeframe | 200 |

---

## The finding that matters most

**All five failures were one defect, and it was outside this plan's own Touchpoints table.**

`watchlist.py::_load_raw` is pre-existing code, unmodified by this plan: `json.load(f)` then
`data.setdefault("coins", [])`, expecting the file to be a JSON object. `seed_e2e_cache.py` — new
code, written for this plan — wrote `json.dumps(WATCHLIST)`, a bare array. `json.load` on that
returns a `list`; `list.setdefault` doesn't exist. `AttributeError`, raised on `read_watchlist()`'s
first line, which is also `build_screener_board()`'s first line — before any per-coin or
per-timeframe logic runs.

That is why every spec failed identically regardless of what it was actually asserting: the 1d
default board load (specs 1, 2, 4, 6, all via the browser), and the explicit 1w request (spec 3,
via Playwright's `request` fixture, bypassing the browser). The browser-based specs never saw the
500 as a 500 — Starlette's CORS middleware does not attach `Access-Control-Allow-Origin` to a
response an unhandled exception generated, so the browser's `fetch()` sees a CORS-header-less 500
and throws a generic `TypeError: Failed to fetch`. Only spec 3, using `request` directly (no CORS
layer in the way), surfaced the actual status code.

**Found without a traceback.** The user was asked for one; before it arrived, the fix was found by
statically tracing `build_screener_board`'s full call graph outward from the router — every adapter
it reaches (`ccxt_adapter`, `fred_adapter`, `defillama_adapter`, `pytrends_adapter`,
`reddit_adapter`, `coingecko_adapter`, `liqtide_adapter`, `leg_boundary`, `benchmark`,
`narrative.trigger`, `narrative.mapping`, `confidence.badge`, `indicators.momentum`,
`indicators.trend`) — and confirming each one is defensively typed (`status: ok | unavailable |
stale | bad_symbol`, never raising past its own boundary), narrowing the search to the one module
that isn't defensive in that way: `watchlist.py`, which trusts its file's shape unconditionally.
Placing `watchlist.example.json` (`{"coins": [...]}`) next to what the seed script actually wrote
made the defect visible without running anything.

## Why the specs' own defenses didn't catch this at design time

Named risk 4 in the plan predicted "fixture drift" — golden *values* disagreeing between the seed
script and the specs — and built `.fixture-manifest.json` specifically to prevent it (specs read
golden values from the manifest, never retyped). That mechanism worked exactly as designed; it
simply didn't cover this defect. The watchlist file isn't a golden value at all, it's a raw
hand-off to a *pre-existing* reader (`watchlist.py`) that this plan never touched and whose parsing
contract was never looked up before writing to it. The risk that materialized was shape drift
against an unmodified consumer, one layer outside where the plan was looking.

## Process failures, recorded

1. **The Touchpoints table's own "blast radius" claim was almost right, and the exception is the
   whole story.** It called the three API changes "additive fallbacks... behaviour is
   byte-identical to today" absent the env vars — true for `cache.py`, `watchlist.py`'s env
   override, and `main.py`. It said nothing about the *new* file, `seed_e2e_cache.py`, because a
   new file has no "before" to be identical to. The bug lived in the one touchpoint exempt from the
   blast-radius argument by construction, not in one of the ones the argument covered.
2. **No format check against `watchlist.py` before writing to its file.** The seed script hand-
   rolled the watchlist JSON instead of calling `watchlist_store.add_coin` in a loop or reading
   `watchlist.example.json` first — either would have surfaced the shape immediately. Recorded as
   Standing Lesson #8.

## Deviations

1. **Session had no execution surface**, same constraint as every prior cycle today: no
   `device_bash`, cloud sandbox pypi/npm blocked. Every gate was written unrun, the first failure
   diagnosed statically (no traceback obtained or needed), the fix applied via the device-file
   bridge (stage → edit → commit), and both runs executed by the user.
2. **`device_commit_files` reported success without persisting**, on the fix itself, for the first
   attempt — the same hazard recorded in prior cycles today. Caught by the standing verify pattern
   (re-stage + diff after every commit): the re-staged copy still showed the original bare-array
   line, so the commit was retried and confirmed on the second attempt.
3. **RIPER-5 phases run inline by the orchestrator** — `vc-*` subagents not spawnable in this Cowork
   session, same recorded deviation as every prior cycle.

## Context updated

- `process/context/tests/all-tests.md` — third runner row filled in (was scaffolded, unrun);
  backend count 165; Known Gap "No E2E/browser suite" closed; eighth Standing Lesson row; a
  debugging row for the CORS-hides-500 symptom.
- This plan (`playwright-e2e_PLAN_19-09-26.md`) — EVL section added; stale pre-execution
  Verification section removed; Named risk 4 annotated with what actually materialized; the spec-5
  VALIDATE question resolved.

## Residuals carried forward

1. **`api/ -q` not re-run against the final state.** Last reported count (165 passed, 1 deselected)
   predates this cycle's own last edit (the `seed_e2e_cache.py` watchlist-shape fix) — that edit
   touches no code path pytest exercises, so no regression is expected, but it is unconfirmed rather
   than verified.
2. **Fixture drift risk, narrowed but not closed.** The manifest mechanism prevents *value* drift.
   Nothing yet prevents a future *shape* drift the same way — no test asserts `seed_e2e_cache.py`'s
   output against `watchlist.py`'s actual reader, only against what a human eye expects it to be.
3. All residuals from `weekly-ohlc-anchor_19-09-26-phase-report.md` are unaffected by this cycle and
   remain open there (week-anchor convention asserted not measured; `isolated_cache` opt-in; four
   non-OHLCV cache readers' tz contract).

## Next

- Nothing blocking. E2E suite is green end to end.
- **Cheap and not done**: re-run `uv run --project api pytest api/ -q` to confirm 165 still holds
  against the final `seed_e2e_cache.py` state (residual 1 above).
- Queued, unchanged: RFC-006 (frontend `reason` rendering, `getJson` timeout + catch, unify the
  three dead-data renderings — spec 5 now gives it a concrete before/after); RFC-001 stub closeout
  toward archival.
