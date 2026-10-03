---
phase: rfc-006-tests-e2e-handoff
date: 2026-09-27
status: COMPLETE
feature: onchain-activity
plan: process/features/onchain-activity/completed/chain-growth_25-09-26/chain-growth_PLAN_25-09-26.md
---

# RFC-6 — seeded E2E proof + AC-14 handoff: report

**TL;DR:** RFC-6 is built to the Stage 0 report and decisions D1–D5 (2026-09-27).
- A seeded `/onchain` fixture, 5 seeder pytests and a 16-scenario Playwright spec are in place, and all gates are green:
  - **pytest 516 passed / 5 deselected**
  - **vitest 138 / 19 files**
  - **tsc exit 0**
  - **e2e 42/42, run twice** (26 existing + 16 new)
- No product code changed and no bug was found.
- The real `api/data/cache/` is unchanged.
- Not committed.
- The plan is now CODE DONE on AC-1..AC-13. AC-14 needs you (checklist below).

## What Was Done
| File | Change |
|---|---|
| `api/scripts/seed_e2e_cache.py` | Additive. `ONCHAIN_*` constants, `_ONCHAIN_SHAPES`, `build_onchain_fixture` (pure) and `seed_onchain` (writes **only** via `cache.merge_onchain_series`). `main()` seeds it, times it, and writes `manifest["onchain"]`. Also `import time`. |
| `api/tests/scripts/test_seed_onchain_fixture.py` | New, 5 tests: fixture purity; round-trip through the real reader; the real `build_growth_response` for both metrics against the manifest (including **Arbitrum floor 2026-03-01 / ramp 2026-04-14** and **Robinhood gate 2027-01-10**); the router echoing `?start=`. |
| `web/e2e/onchain.spec.ts` | New, 16 scenarios. Every expectation is read from the manifest. |

### Fixture as built (seeded "today" 2026-09-26, fixed; decision D1)
- Series dates are fixed. Only `first_seen_utc`/`as_of_utc` use the real clock. Optimism is stamped with real now − 10 days, so it is stale.
- There are pre-launch points on all 6 chains (D2); Ethereum starts at 2015-07-01.
- There are 4,077 post-launch days for Ethereum, about 11.6k active-address rows in total, plus transactions and L2BEAT rows.
- **Seeding time: 0.24 s and 0.27 s** in the two E2E runs.

| Chain | Expected (verified by the real builder) |
|---|---|
| ethereum | `neutral`, 0 events |
| base | `floor`, 0 events, gap 2026-05-10..14 → `gap_before` on 2026-05-15, L2BEAT +2.0% |
| arbitrum | `ramping`, 1 event: floor 2026-03-01 → ramp 2026-04-14, L2BEAT +2.0% |
| optimism | `floor`, **stale** (10 days) |
| polygon | `floor`. **No transactions archive** (D3) → `no-archived-data` card on the tx metric |
| robinhood | `not-enough-history`, 88 days, gate 2027-01-10, `rebased_late` (2026-07-01) |
| solana / bnb / tron | unavailable from `chains.json` (`source-unavailable`) |

- Default comparison start: 2025-09-26.
- 2Y start: 2024-09-26.

### Spec scenarios → ACs
| # | Scenario | AC |
|---|---|---|
| 1 | Loads from a real request; method note shows the EMA/N/R/M/gate params | AC-1, AC-2 |
| 2 | 6 panels, each with "Source: growthepie · Method: …" | AC-1, AC-2 |
| 3 | Pre-launch label on all 6 | AC-4 (D2) |
| 4 | Markers only on Arbitrum; API events equal the manifest | AC-3 (code half) |
| 5 | State labels match the manifest (Near floor / Not enough history) | AC-5 |
| 6 | Robinhood limited-history note contains "from 2027-01-10" | AC-6 |
| 7 | Comparison: index + log by default; pct forces linear and disables the log toggle | AC-3, AC-13 |
| 8 | "late start (2026-07-01)" appears only on Robinhood | AC-3 |
| 9 | The 2Y click sends `start=2024-09-26`; `data-visible-range` covers 2024-09-26 → 2026-09-26 | AC-7 |
| 10 | Metric switch: `metric=transactions`; L2BEAT note on base/arbitrum; **Polygon becomes an unavailable card while the other 5 render** | AC-8, AC-9, AC-12 |
| 11 | Stale badge + banner say "10 days ago" | AC-10 |
| 12 | 3 unavailable cards; no "0" in the card text | AC-11, AC-12 |
| 13 | Attribution text is verbatim; link href is correct; shown once | AC-2 / E6 |
| 14 | Home link → `/onchain` | AC-1 |
| 15 | The gap breaks the Base line; other charts have 0 gaps | AC-4 |
| 16 | Hover moves the Arbitrum raw-value readout to a grid date; EMA28 shown (D5) | drill-down |

## Test Gate Outcomes
| Gate | Result |
|---|---|
| `uv run --project api pytest api/ -q` | **516 passed, 5 deselected** (511 + 5 new) |
| `pnpm --filter web test` | **138 passed, 19 files** (unchanged) |
| `pnpm --filter web exec tsc --noEmit` | **exit 0**; `web/tsconfig.tsbuildinfo` restored with `git checkout` |
| `cd web && PLAYWRIGHT_CHROMIUM_PATH=… pnpm test:e2e` run 1 | **42 passed** (1.7 min) |
| same, run 2 | **42 passed** (1.6 min) |
| Real-cache guard | md5 of all 16 files under `api/data/cache/onchain/` is identical before and after (`ef73d2d6…`); `git status api/data/cache` is clean |

- D5: the hover scenario passed in both runs, so it is kept.
- No interference: the other 26 specs are unchanged and green in both runs.

## Plan Deviations
None beyond the Stage 0 renames (conflict table below). No product code was changed and no bug was found.

## What Was Skipped or Deferred
- **Context docs:** deferred to UPDATE PROCESS (D4). They need the `data-sources` provider section (growthepie, L2BEAT; Dune recorded as NOT-VIABLE) and the `all-context.md` routing row plus a change entry.
- **AC-14:** this needs you on your own PC (checklist below).
- The PENDING review decisions in `harness/rfc-003/` and `harness/rfc-004/` also need you.

## AC-14 user-PC checklist (replaces the plan's Resume §5 text; no Dune)
1. Merge the PR to `main`, then `git pull` on your PC. You get the code and the nightly `api/data/cache/onchain/` archive.
2. Start the api (`uv run --project api uvicorn api.main:app`) and web (`cd web && pnpm dev`) against the **real** cache, with no `SCREENER_CACHE_ROOT` set. Open `http://localhost:3000/onchain`, or use the home-page link.
3. Check:
   - [ ] 6 panels (Ethereum, Base, Arbitrum, Optimism, Polygon, Robinhood Chain) and 3 unavailable cards (Solana, BNB, Tron). No zeros anywhere for those three.
   - [ ] With range **All** and **active addresses**, Ethereum shows ▲/● at **2022-06-30 / 2022-08-08**, **2023-07-29 / 2024-03-15** and **2024-09-26 / 2024-12-19**. Base shows **2025-04-23 / 2025-05-24**.
   - [ ] Switch to **transactions**: Arbitrum shows **2023-09-17 / 2023-11-27** and **2026-05-31 / 2026-07-09**.
   - [ ] State labels are plausible: Polygon "Near floor" on both metrics as of RFC-4; newer nights may have moved things, so note any change rather than treating it as a failure.
   - [ ] Comparison overlay: index/log is readable, the "% above 180-day low" toggle works, and the 6 colours are easy for you to tell apart. The table view works.
   - [ ] Robinhood Chain shows "Limited history — floor/ramp markers from 2027-01-10" and a "late start" tag.
   - [ ] Transactions metric: the L2BEAT cross-check notes (base/arbitrum/optimism/robinhood) look sensible, roughly under 5%.
   - [ ] Hover a panel: the raw daily number for one or two dates matches growthepie.com.
   - [ ] The footer reads "Source: growthepie, https://www.growthepie.com." with a working link.
   - [ ] No stale banner, unless the nightly job has missed more than 3 days.
   - [ ] Forced-failure half (AC-12 + AC-14):
     1. Stop the api.
     2. Rename `api/data/cache/onchain/growthepie/base/active_addresses.parquet` to `.bak`.
     3. Restart the api and reload the page.
     4. Base should show as an unavailable card ("no archived data") while the other 5 still render.
     5. Rename the file back and confirm `git status` is clean.
4. Record the review decisions: in `harness/rfc-003/review-decision.json` and `harness/rfc-004/review-decision.json`, set `decision` (APPROVE/REJECT), `rationale` and `timestamp`.
5. Reply "AC-14 OK", or list the issues. The plan then goes to ✅ VERIFIED and can be archived.

## Plan-text conflicts for UPDATE PROCESS (the reports win)
| Plan says | Built / true |
|---|---|
| `build_chain_growth_fixture` / `seed_chain_growth` via `cache.write_*` | `build_onchain_fixture` / `seed_onchain` via `merge_onchain_series` |
| `web/e2e/onchain-activity.spec.ts`, route `/onchain-activity` | `web/e2e/onchain.spec.ts`, `/onchain` (RFC-5 Q1) |
| 9 chains × 3 metrics, Dune, `DUNE_API_KEY` revoke test | Fallback scope (E4): 6 live + 3 unavailable, 2 metrics, no Dune. The forced failure is a missing archive (D3 in the E2E; a file rename in AC-14). |
| Separate drill-down component/check | Folded into the hover readout (RFC-5); E2E scenario 16 |
| pytest baseline 395/3, vitest 110/16 | 516/5, 138/19 |
| Resume §5 AC-14 steps (Dune-based) | Replace with the checklist above |
| RFC-6 edits `process/context/` | Deferred to UPDATE PROCESS (D4) |
| Plan Status row RFC-6 "NOT STARTED" | 🔨 CODE DONE; ✅ VERIFIED waits on AC-14 |

## Test Infra Gaps Found
- None new. Canvas visuals (log axis look, shading colour, marker placement) remain an Agent-Probe matter, covered by AC-14.

## Closeout Packet
- Plan: `process/features/onchain-activity/completed/chain-growth_25-09-26/chain-growth_PLAN_25-09-26.md`
- Finished: RFC-6 (the last RFC).
- Verified: all automated gates above, e2e twice.
- Unverified: AC-14 (real archive, on your PC), and the RFC-3/RFC-4 review decisions.
- Remaining cleanup: the context docs, the plan-text reconciliation, and a commit, all at UPDATE PROCESS.
- Classification: **Keep in active/testing** (CODE DONE; waits on AC-14). Next state: UPDATE PROCESS for docs and reconciliation, then the user's AC-14.

## Forward Preview
### Test Infra Found
- `manifest["onchain"]` in `web/e2e/.fixture-manifest.json` is the source for any future onchain E2E.
- `seed_onchain(now=…)` takes an explicit clock for tests.
### Blast Radius Changes
- `api/scripts/seed_e2e_cache.py` (additive), plus 2 new test files.
### Commands to Stay Green
- `uv run --project api pytest api/ -q`
- `pnpm --filter web test`
- `pnpm --filter web exec tsc --noEmit`, then `git checkout web/tsconfig.tsbuildinfo`
- `cd web && PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome pnpm test:e2e` (×2)
### Dependency Changes
- None.
