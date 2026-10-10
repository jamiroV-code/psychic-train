---
name: report:screener-batch3-s5b-pvl-iteration-004
description: "PVL cycle 4 first pass: S5b re-validation of screener batch 3 after the S11 and T44 rebases (main fc12f27); 0 FAIL, 4 CONCERN"
date: 10-10-26
metadata:
  node_type: memory
  type: report
  feature: general-plans
  phase: "S5b"
---

# PVL iteration 004 (S5b, first pass): CONDITIONAL, 0 FAIL, 4 CONCERN

**TL;DR:** the S5b section is mechanically sound against the real code on main fc12f27 (every cited line, count and regex checked), but four things had to be fixed in the plan before a stamp: a test-count ambiguity that would stop the worker, a stale contract state, a wrong code pointer for the envelope, and one acceptance row that claimed more than its tests prove. No source was edited and nothing was committed.

Scope: `screener-batch3_PLAN_09-10-26.md`, section S5b and everything it reads; targeted by the "Changes since validation (S5b, 10-10-26)" list, then the whole section end to end. Code: main fc12f27 (T44 merged); the checkout adds process files only (`git diff fc12f27 HEAD -- api web` empty). Another agent is editing the process record files; none was touched.

## Checks and evidence

| Area | Result |
|---|---|
| Plan structure | `validate-plan-artifact.mjs` 0 failures, 0 warnings; `git diff --check` 0; ASCII only |
| Cited code lines | `ScreenerBoard.tsx` L41-49 (sharedRange and reset), L58-72 (board effect), L94-105 (grid, T44 props at 101-102), L107, L110-117; `CoinPanel.tsx` L15-17, L36, L56-62: all exact |
| U7 mechanics | `MiniChart` passes `linkedRange`/`onRangeChange`; `simple-lines.svelte` applies a linked range at mount (`keepRange`) and resets only on a timeframe or line-key change; `use-simple-lines.ts` updates in place; so a moved or added chart adopts the shared range with no island change |
| U2/U4/U5/U6 | implementable: board effect deps `[timeframe, fetchBoard, tick]` with cancelled flag; `SpaghettiChart` has `dataVersion` in its fetch deps (so `reloadToken` joins it) and a local `hidden` Set; `shareStructure`, `formatDateTimeZone`, `.visually-hidden` and the `.freshness-strip*` rules exist; the S5a mirrors (`layout.ts`, `RsiReading`, `RsiPoint`, `CoinPanel.rsi`, `ChartSeries.rsi`) and routes (`api/routers/layout.py`, `watchlist.py` body keys `symbol`, `group_id`, 409 `detail`) match |
| Existing-test sites | `ScreenerBoard.test.tsx` 10 renders; `ScreenerBoardLive.test.tsx` 12 tests, 2 sites in `setup`; `ScreenerBoardLinkedZoom.test.tsx` 3 tests, 3 render sites (first `render(` at 119, `<ScreenerBoard` at 121); no other file renders the board |
| Baselines | `vitest run components/screener` 51 in 7 files (6+6+8+10+3+12+6); `pnpm test` 335 in 43; `playwright test --list` 72 in 8 (contrast 7, brussels-time 3, live-refresh 4, narrative 17, onchain 16, pairs 9, regime 6, screener 10); full pytest 1016 passed, 2 skipped, 5 deselected, no xfail (272 s; no real layout or watchlist file created); tsc exit 0 |
| Test arithmetic | 12+4+7 = 23 lib; 7+9+15+5 = 36 components; +3+3 = 6; 65 total; 335+65 = 400 in 50 files; G-S5b-1 51+42+23 = 116 in 14; red run 65 failed, 51 passed; e2e 10+7+7 = 24 and 72+7 = 79 in 9 |
| Regexes | `S5b-scope` and `FORBIDDEN` on the 30 planned files print nothing; `S5b-scope` prints all 30 of 30 stray files (islands, chart, `lib/types`, T44 and S11 files, MASTER-PLAN, the plan itself); `FORBIDDEN` alone misses `chart-viewport.test.ts`, `live-refresh.spec.ts`, S11 `web/lib` files (caught by `S5b-scope`); `S5b-words` and `S5b-nostore` print nothing on the four existing files; `CAP-MESSAGE` first line 1 |
| Byte math | S5b ranges re-derived from the saved file: 66 lines, 20,421 B, room 36,000 - 13,443 - 20,421 = 2,136 B; CLAUDE.md 13,443 B; S5a set (merged) re-mapped 20,238 B; union 38,232 B; all range edges on intended lines |
| Wording | no goal, verdict or signal wording in any S5b range |
| Stamp | one stamp line in the header (the cycle 3 one), now stale over an S5b marked NEEDS RE-VALIDATION |

## Findings

| # | Class | Finding | Fix |
|---|---|---|---|
| F1 | CONCERN | `ScreenerBoardLayout` bullet (plan line 166): 17 semicolon clauses against a declared 15; every other bullet matches clause for clause (12, 4, 7, 7, 9, 5). The S11 rebase split "remove ... and closes the drill-down" and "board failure" into more clauses without raising the count; a worker writing 17 tests sees 402 not 400 and stops at `needs_input` | join two pairs; clause count 15 (+8 B) |
| F2 | CONCERN | contract state stale: header stamp predates the S5b edits; lines 11, 19, 127, Resume 3 and 5, goal block describe older states; line 224 says T40/T41 unregistered but MASTER-PLAN lists both; AC-S5b-11 and AC-S5b-12 missing from Verification Evidence, legacy line form, SPEC-link list | refresh in place; single stamp |
| F3 | CONCERN | envelope pointer for C4 is `api/routers/layout.py`, which holds no 422 rule; `GROUP_ID_RE`, 12-group and name rules are in `api/data/layout.py`; S5b generates group ids | pointer names both (line outside every range) |
| F4 | CONCERN | AC-S5b-12 row claims group edits, layout refetch and rollback keep the range; the U7 test folds cover move, move-to-group, add/remove, timeframe | row states those three hold by construction (range is `ScreenerBoard` state) |

Advisories a-h are recorded in the plan's "Validation record (PVL cycle 4, S5b re-validation)" (group-button names, backlog stub content, two hidden-break traps in `ScreenerBoardLive`, wrong `AbortSignal` rationale in the `S5b-words` note, RSI retention not named by a test, spare bytes, P-S5a-1, history line numbers).

Verdict: CONDITIONAL (0 FAIL, 4 CONCERN, all fixable in the plan text). Next: fix cycle (iteration 005), then re-verify (006).
