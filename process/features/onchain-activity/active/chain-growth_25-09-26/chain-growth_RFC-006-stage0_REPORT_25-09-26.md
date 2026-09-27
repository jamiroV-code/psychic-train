---
phase: rfc-006-stage0
date: 2026-09-27
status: COMPLETE
feature: onchain-activity
plan: process/features/onchain-activity/active/chain-growth_25-09-26/chain-growth_PLAN_25-09-26.md
---

# RFC-6 Stage 0 — seeded E2E proof + AC-14 handoff (proposal, no code written)

**TL;DR:**
- The seeding is feasible without network access.
- Use a **fixed seeded date (2026-09-26)** for all series dates. Only `as_of_utc` uses the real clock. The API has no injectable "today"; it uses the real clock only for staleness and for rejecting a future `?start=`.
- A scratch run through the real detector confirms the designed chain (Arbitrum) produces exactly one event: **floor 2026-03-01, ramp 2026-04-14**, state `ramping`.
- The `onchain/` cache subtree is read only by the onchain router. The other three specs cannot be affected.
- Five decisions for you are listed at the end. Nothing has been edited except this report.

## 0. Entry state
- RFC-4 and RFC-5 are green on their own gates:
  - api: 511 passed / 5 deselected
  - web: 138 passed / 19 files
  - `tsc` exit 0
  - e2e: 26/26 per the handoff
- Branch: `claude/kind-tesla-tat3vo`. RFC-3..5 work is uncommitted. RFC-6's exit gates re-run all of it.
- Reports read: all RFC-001..005 reports, the Stage 0 reports, and the RFC-5 data-testid list. Where they disagree with the plan text, the reports win (see §5).

## 1. Seeding proposal (`api/scripts/seed_e2e_cache.py`, additive only)

### How "today" works (from `api/analytics/onchain/response.py` + router)
| Behaviour | Clock used | Consequence for seeding |
|---|---|---|
| `status: stale` | real `now` − max(`as_of_utc`) > 3 days | Write `now_utc` = the real seeding time. For the stale chain, use real now − 10 days. |
| Default comparison `start` | last grid date − 365 | Fixed by the seeded data: 2025-09-26. |
| `?start=` validation | rejects start > real today | Never hit with a fixed past date. |
| Floor/ramp, gate, pre-launch | data dates + fixed `launch_date` in `chains.json` | Deterministic when series dates are fixed. |
| `merge_onchain_series(today=…)` | drops dates > `today` | Pass `today="2026-09-26"`. |

Why a fixed date and not "now" (unlike the regime/narrative seeders):
- `chains.json` launch dates are fixed and cannot be overridden: there is no env path, `CHAINS_PATH` is a module constant, and the E2E must use the real file.
- With now-anchored dates, Robinhood would pass its 194-day gate on 2027-01-10, and the "limited history / not enough history" scenario would silently flip.
- A fixed date also lets the manifest hold literal dates.
- Nothing onchain needs "fresh" bars; the endpoint never fetches from a provider.

### `build_onchain_fixture(seed_today)` (pure) + `seed_onchain(seed_today=SEED_TODAY, now_utc=None)`
- Writes **only** via `cache.merge_onchain_series(source, chain_id, metric, points, today=…, now_utc=…)`.
- Both metrics are written for every live chain. Transactions use the same shape scaled ×10, so the floor/ramp dates are the same.

| Chain (launch) | Seeded span | Pre-launch pts | Shape / purpose | Expected (active_addresses) |
|---|---|---|---|---|
| ethereum (2015-07-30) | 2015-07-01 → 2026-09-26 | 29 | Slow steady rise, no ≥25% dip | 0 events; state pinned by pytest (target `neutral`) |
| base (2023-08-09) | 2023-07-10 → 2026-09-26 | 30 | Mild wave plus a **5-day gap 2026-05-10..05-14** | `gap_before=true` on 2026-05-15; 0 events |
| arbitrum (2021-08-31) | 2021-08-01 → 2026-09-26 | 30 | **Designed:** flat 1000, decline to 400 over 120d, flat 400 for 60d, ramp to 900 over 90d, flat 900 for 120d | **1 event: floor 2026-03-01, ramp 2026-04-14; state `ramping`** (verified by a scratch run of the real `detect_floor_ramp`) |
| optimism (2021-12-16) | 2021-11-16 → 2026-09-26 | 30 | Flat with a wave; **stale** (all rows `as_of_utc` = real now − 10d) | `status: stale`, banner "last updated 10 days ago" |
| polygon (2020-05-30) | 2020-05-01 → 2026-09-26 | 29 | Long decline into a flat bottom | state `floor` (the D3 real-cache precedent) |
| robinhood (2026-07-01) | 2026-06-20 → 2026-09-26 | 11 | Short rising series | `not-enough-history`, history_days 88, **gate_met_on 2027-01-10**, `rebased_late=true` (rebase 2026-07-01) |
| solana / bnb / tron | not seeded | — | From `chains.json` `source: none` | Unavailable cards, `data-reason=source-unavailable` |

- **L2BEAT cross-check:** base and arbitrum transactions are also written under source `l2beat`, as growthepie ÷ 1.02. Expected `latest_divergence_pct` = +2.0 and the 90-day median = 2.0.
  - Robinhood/optimism get no L2BEAT rows, so the "no cross-check data" path is exercised too.
- **Manifest:** `manifest["onchain"]` holds `seed_today`, `default_start` (2025-09-26), per-chain expected states, events, the gap date, the stale chain and its days, Robinhood's gate date, the cross-check chains and divergence, the unavailable ids, and the attribution string. The spec reads all of these from the manifest and never retypes them.
- **`main()`:** adds `onchain = seed_onchain()` plus one print line. `bootstrap_cache_dirs` is untouched; the merge helper does its own `mkdir`.

### Seeder pytest: `api/tests/scripts/test_seed_onchain_fixture.py` (same pattern as `test_seed_narrative_fixture.py`, `isolated_cache`)
1. Fixture purity: no network; only growthepie/l2beat sources; no rows after `seed_today`; solana/bnb/tron absent.
2. Round-trip through the real reader: `read_onchain_series` row counts, pre-launch counts, the gap hole, and stale `as_of_utc`.
3. `build_growth_response("active_addresses", now=fixed)`:
   - Arbitrum events == [(2026-03-01, 2026-04-14)] and state `ramping`.
   - Robinhood `not-enough-history` / 2027-01-10 / `rebased_late`.
   - Optimism `stale`.
   - `gap_before` on 2026-05-15.
   - 3 unavailable ids.
   - Divergence ≈ 2.0.
   - `comparison.start_date == 2025-09-26`.
   - Every state equals the manifest.
4. The same check for `transactions`.
5. The router via `TestClient`: `/api/onchain/growth?start=2024-09-26` → `start_date` echoes the requested date.

## 2. Interference with the existing specs — none by construction
- The seeder writes only `CACHE_ROOT/onchain/{growthepie,l2beat}/…`.
- `read_onchain_series` is imported only by `api/analytics/onchain/response.py`, which serves only `/api/onchain/*`. No regime, narrative or screener module reads the `onchain/` subtree.
- `main()` still `rmtree`s the temp root first, so the onchain seed runs after the regime and narrative seeds and cannot overwrite their files.
- `/onchain` never fetches from a provider or writes to the cache, unlike `/screener`'s NarrativeStrip. The spec's ordering is therefore free.
- Proof: the existing 26 specs must stay 26/26 in both exit runs.

## 3. `web/e2e/onchain.spec.ts` — scenarios → ACs (RFC-5 testids; values from the manifest)
| # | Scenario | Key assertions | AC |
|---|---|---|---|
| 1 | Page loads | `onchain-dashboard[data-metric=active_addresses]`; `onchain-method-note` contains the EMA/N/R/M/S params; real `/api/onchain/growth` response captured | AC-1, AC-2 |
| 2 | 6 panels | `onchain-panel-{6 ids}`; each `-source` shows "growthepie" + method text | AC-1, AC-2 |
| 3 | Pre-launch shading | `onchain-panel-{id}-prelaunch` text "before launch (date)" for chains with pre-launch points | AC-4 (D2) |
| 4 | Floor/ramp markers | `onchain-chart-arbitrum[data-marker-count=2]`; API events == manifest; other chains 0 markers | AC-3 (code half) |
| 5 | Current-state label | `onchain-panel-arbitrum-state[data-state=ramping]`, polygon `floor`, robinhood not-enough-history | AC-5 |
| 6 | Robinhood limited history | `-limited-history` visible, contains "2027-01-10" | AC-6 |
| 7 | Comparison view | `onchain-comparison[data-mode=index][data-log-scale=true]`; click `-mode-pct` → `data-mode=pct`, `data-log-scale=false`, log toggle disabled; legend lists 6 | AC-3, AC-13 |
| 8 | rebased_late | `onchain-rebased-late-robinhood` visible "late start (2026-07-01)"; none for arbitrum | AC-3 |
| 9 | Range picker | click `onchain-range-2y` → request URL has `start=2024-09-26`; `aria-checked`; `onchain-comparison-chart[data-visible-range]` starts at 2024-09-26 | AC-7 |
| 10 | Metric switch | click `onchain-metric-transactions` → request `metric=transactions`; `data-metric` flips; `-crosscheck` now shown for base/arbitrum with divergence ~2.0% | AC-8, AC-9 |
| 11 | Stale | `onchain-panel-optimism-stale` + `onchain-stale-banner` "10 days" | AC-10 |
| 12 | Unavailable | `onchain-unavailable-{solana,bnb,tron}`; body text never shows "0" as a value for them | AC-11, AC-12 |
| 13 | Attribution | `onchain-attribution-text` == manifest string verbatim (E6); link href `https://www.growthepie.com` | AC-2 / E6 |
| 14 | Home link | `/` → `home-link-onchain` → URL `/onchain` | AC-1 |
| 15 | Gap break | `onchain-chart-base[data-gap-dates]` contains 2026-05-15 | AC-4 |
| 16 | Hover readout (optional) | hover chart → `-readout` shows the date and raw value; canvas hover in headless mode may be flaky, so drop it if flaky rather than retrying | drilldown (Agent-Probe residual) |

Structure and labels plus seeded values only. Nothing depends on live data or the real "today", except the stale "10 days", which is computed from the seeding time and is deterministic within a run.

## 4. AC-14 user handoff checklist (replaces the stale plan text at Resume §5)
1. Merge the PR to `main`, then `git pull` on your PC. This also brings the nightly `chain-growth-snapshot.yml` archive.
2. Start the api and web as usual, with the real `api/data/cache/` and no `SCREENER_CACHE_ROOT`. Open **`/onchain`**.
3. Check:
   - [ ] 6 panels (ETH, Base, Arbitrum, Optimism, Polygon, Robinhood) and 3 unavailable cards (Solana, BNB, Tron). No zeros.
   - [ ] ETH active addresses (All range) shows markers at **floor 2022-06-30 / ramp 2022-08-08**, 2023-07-29→2024-03-15, and 2024-09-26→12-19. Arbitrum tx shows 2023-09-17→11-27 and 2026-05-31→07-09. Base daa shows 2025-04-23→05-24.
   - [ ] State labels match RFC-4: Polygon `floor`, Optimism daa `ramping`. They may have moved with new nights; if so, note it.
   - [ ] The comparison overlay in log scale is readable; the "% above 180-day low" toggle works; the colours are distinguishable to you.
   - [ ] Robinhood shows its limited-history note ("comparable from 2027-01-10") and a "late start" tag.
   - [ ] The L2BEAT cross-check text on the transactions metric (base/arb/op/robinhood) looks sensible (<~5%).
   - [ ] The attribution footer reads "Source: growthepie, https://www.growthepie.com."
   - [ ] Hover shows plausible raw numbers against growthepie.com for one or two dates.
   - [ ] Optional failure half of AC-12/AC-14: rename one chain's `api/data/cache/onchain/growthepie/<chain>/active_addresses.parquet`, reload, and confirm that chain shows "unavailable" while the others render. Then rename it back. (The Dune-key step in the plan no longer applies under the fallback scope.)
4. Record the review decisions: set `decision` + `rationale` + `timestamp` in `harness/rfc-003/review-decision.json` and `harness/rfc-004/review-decision.json` (both are currently PENDING).
5. Reply "AC-14 OK" (or list issues). Then the plan can move to ✅ VERIFIED and be archived.

## 5. RFC-6 exit gates and plan-text conflicts

**Exit gates**
- `uv run --project api pytest api/ -q` → 511 + new seeder tests, 5 deselected
- `cd web && pnpm test` → 138 / 19 files, unchanged
- `cd web && pnpm exec tsc --noEmit` → exit 0, then `git checkout web/tsconfig.tsbuildinfo`
- `cd web && PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome pnpm test:e2e`, run **twice** → 26 + ~15 onchain, all pass both times

Also in scope per the plan:
- the context docs (`data-sources` provider section, `all-context.md` routing row);
- rewriting the plan's Resume §5 AC-14 text.

The plan assigns the context-doc edits to RFC-6. The agent rules say `process/context/` edits belong to UPDATE PROCESS. Recommendation: do them in UPDATE PROCESS.

**Plan-text conflicts (the reports win)**
| Plan says | Reality / proposal |
|---|---|
| `build_chain_growth_fixture` / `seed_chain_growth`, `cache.write_*` | `build_onchain_fixture` / `seed_onchain` via `merge_onchain_series` (the RFC-3 helper) |
| `web/e2e/onchain-activity.spec.ts`, route `/onchain-activity` | `web/e2e/onchain.spec.ts`, `/onchain` (RFC-5 Q1) |
| 9 chains × 3 metrics, Dune, `DUNE_API_KEY` revoke test | Fallback (E4): 6 live + 3 unavailable, 2 metrics, no Dune. The AC-12 failure proof is replaced by a missing-archive chain (D3 below) and a user-side file rename. |
| "forced-single-source-failure fixture" | See D3 |
| pytest baseline 395/3 | 511/5 actual |
| Separate DrillDown check | Folded into the hover readout (RFC-5); optional scenario 16 |

## Decisions for you
- **D1 — Seeded date:** use a fixed date of 2026-09-26 for data, with only `as_of_utc` on the real clock. *Recommended*; the alternative (now-anchored) breaks the Robinhood gate scenario after 2027-01-10.
- **D2 — Pre-launch points on all 6 chains**, including Ethereum from 2015-07-01 (about 4,100 daily points). This matches your ask, costs a payload of roughly real-cache size, and keeps ~24k rows total. The alternative is pre-launch on 4 chains only (skip ETH and Polygon), with shorter series. *Recommended: all 6, as asked.*
- **D3 — Per-source failure proof (AC-12 at the UI):** seed Polygon **active_addresses only**, with no transactions archive. Switching the metric then turns Polygon into a `no-archived-data` card while the others render. *Recommended*; this is a real forced failure through the real reader. The alternative is to rely only on the 3 config-unavailable chains.
- **D4 — Context-doc edits:** move them to UPDATE PROCESS (recommended) or do them in RFC-6 as the plan text says.
- **D5 — Hover-readout scenario 16:** include it, and drop it only if it proves flaky (recommended), or skip it and leave drill-down as the Agent-Probe residual in AC-14.

## Forward Preview
- Test infra: `isolated_cache` fixture; `web/test/mocks/onchain-lightweight-charts.ts` is not needed for E2E.
- Blast radius: `api/scripts/seed_e2e_cache.py` (additive), `api/tests/scripts/test_seed_onchain_fixture.py` (new), `web/e2e/onchain.spec.ts` (new), plan Resume text.
- Commands: see Exit gates.
- Dependencies: none.
