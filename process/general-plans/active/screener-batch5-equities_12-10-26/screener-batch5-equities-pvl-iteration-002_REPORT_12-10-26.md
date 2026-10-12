---
domain: plan
iteration: 2
date: 2026-10-12
plan: screener-batch5-equities_PLAN_12-10-26.md
mode: PLAN supplement (PVL-supplement, applied by the validator session as the task permits)
gaps_found: 12
fail_count: 0
concern_count: 12
applied: 12
loop_status: supplement_folded
---

# PVL iteration 002 - screener-batch5-equities (fold of F1-F12; results.tsv row 2)

The supplement touched only the sections named by the gaps; no section was added except "Scope and scan commands" (F6), no overlay section exists, and no test count changed (pytest +106, vitest +76, e2e +13). All edits were made with scripted exact-once replacements, so each one failed loudly if its anchor was missing or duplicated.

## Where each finding went

| # | Plan location | Change |
|---|---|---|
| F1 | S9A design (`lse_adapter`, `equities_refresh` bullets), Owned (edit), AC-S9A-7, Public Contracts | "ADD two functions": `read_cached_equity` and `refresh_equity` (no existing line changes); `refresh_ticker` defaults to it |
| F2 | S9A design (`equities_calendar`, `equities_board` bullets), calendar tests, AC-S9A-2/3 | weekly stale/partial on the daily leg; chips built in `equities_board` (1w from the derived weekly bar); spring DST case added |
| F3 | S9E design (worker loop, `status()`), tests line | retry judged against the tick's own session; `next_tick_at` is the stored wake instant, advanced at tick start |
| F4 | S9A design (`equities_board`, router bullets) | reason mapping onto the closed `UnavailableReason`; `Literal["1d","1w"]` on board, spaghetti, chart |
| F5 | S9A design (`equities_store`, `equities_refresh` bullets) | store lock + 35-thread router test; pending flag; one module lock that S9E reuses |
| F6 | gate conventions 7-10, S9A-S9E gate lines, new section "Scope and scan commands" | 13 commands (FORBIDDEN, FIXTURES, S-secret, five scopes with the worker's own report allowed, words, utc, nostore, clock); all read `origin/main...HEAD` after the commit; tests `delenv("LSE_API_KEY")` |
| F7 | S9C design bullets and G-S9C-2, G-S9C-5 | `"use client"` context, shared `MAX_COINS`, `export function fetchChartView` kept, module-level fetchers, date-only chip tooltip and 1w caption, runnable `--exclude` command |
| F8 | S9D Owned (edit), design, e2e case 10, G-S9D-5 | seed order, empty `LSE_API_KEY`, 420 sessions, no UTC word on the page |
| F9 | S9E tests line | router test 3 "running through the `TestClient(app)` lifespan with a fake fetch" |
| F10 | existing-test table row S9A, S9A tests line | changed tests each assert a refusal |
| F11 | budget table mid, landing paragraph, Q5 | mids 27.8 / 91.4 / 97.2; calibration (S5b +25%); spend gate 93.0 USD before D as before E |
| F12 | ranges table and its explanation | rebuilt (iteration 003 re-derives it) |

Open choices: Q5 now names the gate before D; Q9 notes the home page card list is untouched. Q1-Q4, Q6-Q8, Q10 unchanged.
