---
domain: plan
iteration: 1
date: 2026-10-04
plan: screener-batch2_PLAN_04-10-26.md
gaps_found: 7
fail_count: 0
concern_count: 7
applied: 0
backlogged: 0
loop_status: validated_conditional
---

# PVL iteration 001 - screener-batch2 (first-pass VALIDATE; results.tsv row 1)

Code under test: origin/main 605424d (api/ and web/ identical to the working tree). Plan: 450 lines, 70,316 B. Validator `validate-plan-artifact.mjs`: 0 failures, 0 warnings.

## Verdict so far: CONDITIONAL (0 FAIL, 7 CONCERN). No `Gate: PASS` stamp.

User resolutions recorded as RESOLVED (not open): Q1 A, Q2 A, Q3 A (200 bars), Q4 A (AC-22 CONDITIONAL, backlog stub), Q5 A (0.5 x std, 3 earlier legs, shown on screen), Q6 A (span stated, user runs the existing backfill, no backfill code). The plan's "decided without asking" items (no `/scalp` alias, `active_benchmark_reason` dropped, S6 then S7) stand; no defect found against them.

## Verified as correct (re-derived from real code)

| Claim | Result |
|---|---|
| Baselines | vitest 245 passed in 33 files (run); tsc exit 0 (run); `build:islands` exit 0 (run); pytest collected counts per file match (see F-numbers for the one miss) |
| S4 deleted-test counts | badge 19, benchmark 6, momentum 12, integration 4, narrative contract 3, regime 3, sma 5 (3 remain), lse adapter 16 (15 + 1 skipped); component tests 3+4+5+5 = 17, scalp-label test 1; arithmetic 964 / 929 pytest and 229 vitest in 30 files holds |
| S6 / S7 arithmetic | 934, 951 pytest; 242 in 32, 254 in 34 vitest; every listed test name counts to 8 / 10+5+6+1 / 12+5 / 6+6 |
| Hidden breakers for A | every `monkeypatch.setattr(screener_board.leg_boundary / .narrative_trigger / .badge / select_active_benchmark)` found by grep is in the plan table (test_screener 111-112, 173-174, 229-230; freshness_payload 45-49; gain_contract 93-94; integration 77-78); imports of `BenchmarkSelection` (freshness_payload:18), `ConfidenceState` (integration:23), `SMA_LENGTH` from `trend` (test_screener:40) all listed; no web consumer of the deleted TS types outside the deleted components; no deploy, CI, script or doc names a removed route |
| Hidden breakers for B | importers of `momentum`/`trend`/`badge`/`benchmark`: only screener_board, routers/regime, and the tests listed; `confidence/__init__.py` and `indicators/__init__.py` are empty; nothing reads those files by path |
| `import api.main` split | `badge.py` imports `ConfidenceState/MomentumState/TrendState`, `benchmark.py` imports `BenchmarkSelection` from `api.models.screener`: keeping them in A is required, as planned |
| Scope regexes | S4-scope, S6-scope, S7-scope dry-run (Python and real `grep -vE`) against the files each slice owns: print nothing; an out-of-scope file is printed; FORBIDDEN matches none of the owned files; FIXTURES finds exactly the golden path for S4 |
| FIXTURE-EQ | the golden round-trips byte-identical through `json.dumps(indent=2, sort_keys=True)+"\n"`; the command run on the unedited file prints exactly the two `screener_narrative_state` blocks, so a correct edit prints nothing |
| Envelope byte math | recomputed from the file: S4 19,570, S6 17,271, S7 14,122; CLAUDE.md 13,443; operating-instructions.md 6,678; rooms 2,987 / 5,286 / 8,435 (S7 bound by the 8,000 B envelope cap). S4 envelope fits if it stays at or under 2,987 B (the template alone is 864 B) |
| Touch counts | A 31 (13 source + 18 tests), B 22 (14 + 8), 17 deletions: re-counted, matches |
| S6/S7 shared files | the five shared files are real (`simple-lines.svelte`, `island-loader.ts`, `screener/page.tsx`, `globals.css`, `screener.spec.ts`); API files are disjoint (screener vs regime); sequencing S4 then S6 then S7 is correct; `entry.js` passes props through, so no extra owned file |
| E2E facts | `.fixture-manifest.json` holds `bars_written.BTC["1d"] = 500` and `watchlist = [BTC, ETH, THIN]`, `benchmarks = [BTC, HYPE]`, THIN has 20 bars; `contrast.spec.ts` line 121 is the `rp-legend` selector; 7 contrast routes |
| D-14 | decisions.md D-14 and SPEC F5 allow a computed label with numbers visible on the BTC chart only; C7 (two independent labels, closed enums, numbers shown) is inside that; `ROC_WINDOW_DAYS = 14` exists |
| LayerChart | every unverifiable fact (U1 transform, Svg+Canvas in one Chart, canvas ratio, U2 Rect) is a spike with a named fallback; non-passive wheel listener has the `regime-panel` precedent; no LayerChart behaviour is assumed without a fallback |

## Findings (all CONCERN; fixes are plan edits, folded by one supplement cycle)

See the Validate Contract "Validation record (PVL cycle 1)" in the plan for the full text with file:line evidence. Summary:

| # | Sev | Finding |
|---|---|---|
| F1 | CONCERN | The S4 symbol gate matches the plan's own new tests: test name `test_board_response_has_no_active_benchmark_and_keeps_freshness_fields` contains `active_benchmark`, the route-gone test must request `/scalp`, `screener-api.test.ts` must name `fetchScalp*`. G-S4-9 excludes only `test_no_verdict_symbols.py`. Fix: exclude `test_screener_no_verdict_contract.py` and `screener-api.test.ts` in G-S4-9 and in the pytest gate skip-list. |
| F2 | CONCERN | `test_rsi.py (2, moved)`: `test_momentum.py` has ONE pure `compute_rsi` test (`test_daily_rsi_matches_independent_golden_reference`); `test_weekly_momentum_from_resampled_closes` calls `compute_dual_timeframe_momentum`. Fix: 1 moves (with `_reference_rsi`, `_make_daily_df`), 1 new (`compute_rsi` returns None below length); stub the new one. |
| F3 | CONCERN | C8/AC-S7-4/P-S7-1 claim `/legs` and `/btc-legs` answer from cache. `reads_cache_only_if_running` covers ccxt only; `compute_current_leg_state` also calls `liquidity_composite.build_*_composite`, i.e. `fred_adapter.fetch_series` (httpx plus backoff) and `defillama_adapter.fetch_stablecoin_supply` on TTL expiry. Fix: reword the claim to "BTC OHLCV read", record FRED/DefiLlama as accepted residual (S8-style), make both cache-only tests stub the composite builders, `_leg_inputs` must use only `.df` of the BTC result (test_leg_boundary fakes only `.df`). |
| F4 | CONCERN | The section is titled "secret-hygiene commands" but holds no secret scan; Hard rule "No secrets in files". Fix: add a diff scan (batch-1 `S3-secret-scan` form) as part of every slice gate. |
| F5 | CONCERN | Test 9 uses `test.use({ deviceScaleFactor: 2 })`; at file level it changes DPR for tests 1-8 and breaks test 7's pixel thresholds. Fix: put test 9 in its own `test.describe`. |
| F6 | CONCERN | After the table edit `test_confirmed_boundary_wires_hype_benchmark_into_response` (test_regime.py) has no assertion left. Fix: assert on `confirmed_boundaries` length/date, or rename. |
| F7 | CONCERN | Plan housekeeping: Q1-Q6 are resolved by the user but the plan still shows them open (Status line, "Open questions", Open gaps "Open: Q1-Q6", Resume step 5); the Validate Contract rewrite below line 418 moves later lines, so the fine range table (lines 440-450) must be re-derived last. |

Advisories (no verdict effect): (a) C1 says `benchmark.py` is "unused" after A, but `routers/regime.py` still uses it until B; (b) AC-S7-3 "bands on seeded data" depends on the seeded composite producing confirmed boundaries; jsdom never mounts the island, so bands are proven only by the hybrid E2E and P-S7-1; (c) age ratio boundary tests should use integer arithmetic (`3 * age < median`) to avoid float edge cases; (d) `/{symbol}/chart` inherits S8 limit (b) (any symbol queues one refresh).

## Gate commands run once (this cycle)

pytest `UV_FROZEN=1 uv run --project api pytest api/ -q`: 963 passed, 2 skipped, 5 deselected, rc 0 (215 s); vitest 245 passed in 33 files; `tsc --noEmit --incremental false` rc 0; `build:islands` rc 0; `validate-plan-artifact.mjs` 0 failures, 0 warnings (before and after the contract write; plan now 527 lines).

## Bookkeeping note for the orchestrator

This is the first-pass verdict, so `results.tsv` holds the header plus ONE row (iteration 1, `validated_conditional`); `wc -l` is 2, so the mechanical EXECUTE gate stays closed. The supplement cycle's TSV row will be iteration 2 (`wc -l` = 3). Plan edits made by VALIDATE: only the Validate Contract section (lines 268-272 replaced in place, same line count; a "Validation record (PVL cycle 1)" block inserted after the Mechanics line, plan lines 420-494). Lines 1-418 keep their numbers, so the fine range table (S4 19,570 B, S6 17,271 B, S7 14,122 B, recomputed after the write) is still exact; it must be re-derived LAST if the supplement adds lines in 353-384 (F1, F4).
