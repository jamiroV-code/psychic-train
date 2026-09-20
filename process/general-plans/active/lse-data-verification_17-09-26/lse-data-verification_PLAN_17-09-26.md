# London Strategic Edge — Data Verification

**Date**: 17-09-26
**Status**: ⏳ PLANNED
**Complexity**: Simple
**Owner**: unassigned
**Task folder**: `process/general-plans/active/lse-data-verification_17-09-26/`

**TL;DR** — Before my_site commits to London Strategic Edge as its equity data source, prove the
data is accurate, complete and correctly adjusted, and read the redistribution terms verbatim.
Output is a written verdict (ADOPT / ADOPT-WITH-LIMITS / REJECT) plus an updated
`process/context/data-sources/all-data-sources.md`. **No product code is written in this plan.**

## Quick Links

- [Overview](#overview)
- [Goals and Success Metrics](#goals-and-success-metrics)
- [Phase Completion Rules](#phase-completion-rules)
- [Execution Brief](#execution-brief)
- [Scope](#scope)
- [Assumptions and Constraints](#assumptions-and-constraints)
- [Functional Requirements](#functional-requirements)
- [Acceptance Criteria](#acceptance-criteria)
- [Implementation Checklist](#implementation-checklist)
- [Risks and Mitigations](#risks-and-mitigations)
- [Touchpoints](#touchpoints)
- [Public Contracts](#public-contracts)
- [Blast Radius](#blast-radius)
- [Verification Evidence](#verification-evidence)
- [Resume and Execution Handoff](#resume-and-execution-handoff)

## Overview

`process/context/all-context.md` records the equity data provider as the one genuinely open
decision blocking work. London Strategic Edge (LSE) is the leading free candidate: one free API
key, no card, and claims of 133bn ticks / 118,000 datasets / 30+ years across 14 candle
resolutions, with bulk Parquet export that pairs directly with this project's Parquet + DuckDB
store. Its Python client `lse-data` is MIT-licensed and appears actively maintained.

Two things are unproven, and both are decision-grade:

1. **Data quality.** "133 billion ticks, free" is a strong claim from a small operator. Silently
   wrong or unadjusted price history does not announce itself — it produces plausible-looking
   charts and quietly invalid cointegration results. This is exactly the failure mode
   `all-context.md` calls out under "Numbers are never silently wrong".
2. **Redistribution.** The client is MIT; the *data* is understood to be personal-use only, not
   redistributable to third parties. my_site is built for personal use now with the stated intent
   to open up later, so this determines whether LSE can be in the public build at all.

This plan resolves both by measurement and by reading the terms, then records a verdict.

## Goals and Success Metrics

| Goal | Metric |
|---|---|
| Know whether LSE price history is trustworthy | Cross-source agreement on daily closes within a stated tolerance, on a named symbol set |
| Know whether corporate actions are handled | Documented behaviour across at least two known splits |
| Know whether history depth solves the screener's problem | Measured usable history for the intended pair universe |
| Know the free allowance in practice | Measured quota cost of one realistic backfill |
| Know the redistribution position | Terms quoted verbatim in the verdict, with source URL and date |
| Leave the decision recorded, not remembered | `all-data-sources.md` and `all-context.md` Open Decisions updated |

## Phase Completion Rules

A phase is NOT complete until:

1. **Integration Test** - Works with other system pieces
2. **Manual Test** - User can perform the action
3. **Data Verification** - Database/state changes confirmed
4. **Error Handling** - Failure cases handled gracefully
5. **User Confirmation** - User says "it works"

Status meanings:
- ⏳ PLANNED - Not started
- 🔨 CODE DONE - Written but not E2E tested
- 🧪 TESTING - Currently being tested
- ✅ VERIFIED - Tested AND confirmed working
- 🚧 BLOCKED - Has issues

After each phase, document:
- [ ] What was tested manually
- [ ] Data verified (show query + result)
- [ ] Errors encountered and fixed
- [ ] User confirmation received

**Adaptation for this plan:** the artifact under test is a dataset, not a feature. "Data verified"
means the measured numbers are written into `findings.md` in this task folder with the query or
script that produced them. A phase that produces a conclusion without a recorded number is not
complete.

## Execution Brief

### Phase 1 — Access and client sanity ⏳

**What happens.** Register for the free API key, install `lse-data` into a throwaway `uv`
environment, and pull one small known series end to end.

**Test.** Fetch daily candles for `AAPL` over the last 30 days. Print them. Call
`GET /vault/usage` before and after.

**Verify.** Rows returned, dates plausible, prices in a sane range for the symbol, and the usage
endpoint reports a quota change consistent with one small request.

**Done when.** A round trip works and the cost of a single request is known.

### Phase 2 — Depth and coverage ⏳

**What happens.** Pull the longest available daily history for a fixed symbol set and measure what
is actually there, rather than what is advertised.

**Symbol set (fixed, so results are comparable):** `AAPL`, `MSFT`, `SPY`, `XOM`, `KO`, plus one
known delisted ticker to probe survivorship bias.

**Test.** For each symbol, request from the earliest available date to today. Record first date,
last date, row count, and count of missing sessions against an exchange calendar
(`pandas_market_calendars` or equivalent).

**Verify.** A table in `findings.md`: symbol, first date, last date, rows, missing sessions,
longest gap. The delisted ticker either returns history or returns nothing — both are findings,
and the second one means the screener universe is survivorship-biased.

**Done when.** Real history depth is a number, not a marketing claim.

### Phase 3 — Accuracy and corporate actions ⏳

**What happens.** The phase that actually decides adoption. Cross-check LSE closes against an
independent free source, and probe split handling directly.

**Second source.** Stooq (free, keyless CSV) as primary cross-check; Alpaca free tier as tiebreaker
if the two disagree.

**Test.**
1. Align daily closes for the symbol set over a 5-year window; compute absolute % difference per
   day; report max, 99th percentile and median per symbol.
2. Probe two known splits — AAPL 4:1 (Aug 2020) and NVDA 10:1 (Jun 2024). Inspect the bars either
   side of each date.
3. OHLC internal consistency across the full pull: assert `low <= min(open, close)`,
   `max(open, close) <= high`, no non-positive prices, no duplicate timestamps, monotonic dates.
4. Note whether the API distinguishes adjusted from unadjusted series, and which one the default
   call returns.

**Verify.** Recorded numbers for each check. A split that shows a raw ~4x discontinuity in a series
the API calls adjusted is a correctness failure, not a quirk.

**Done when.** Agreement tolerance, split behaviour and OHLC integrity are all written down.

### Phase 4 — Screener-scale feasibility ⏳

**What happens.** Test the use case that motivated the search, rather than a single symbol.

**Test.** Backfill a realistic screener universe (start at 50 symbols, daily, maximum history),
preferring bulk Parquet export over per-symbol REST calls where available. Time it. Measure quota
consumed via `GET /vault/usage`. Write the result to a scratch Parquet store and run one DuckDB
query across it — a 3-year window over all symbols — to confirm the store shape works.

**Verify.** Elapsed time, quota consumed, resulting store size on disk, DuckDB query time. Extrapolate
to the intended universe size and state whether a periodic refresh fits inside the free allowance.

**Done when.** It is known whether the screener is affordable on the free tier, with numbers.

### Phase 5 — Terms and verdict ⏳

**What happens.** Read the actual published terms and write the decision.

**Test.** Locate the terms of service / data licence and the `lse-data` repository licence. Quote
the redistribution clauses verbatim with URL and access date. Do not paraphrase a licence into a
verdict.

**Verify.** `VERDICT.md` in this task folder states ADOPT / ADOPT-WITH-LIMITS / REJECT, with the
evidence from Phases 2–4 cited, and answers explicitly: *can LSE-derived values be served to other
users in a public my_site?*

**Done when.** `all-data-sources.md` and the Open Decisions table in `all-context.md` reflect the
verdict, and the user confirms the decision.

### Expected Outcome

- `findings.md` — measured coverage, accuracy, corporate-action and quota numbers
- `VERDICT.md` — ADOPT / ADOPT-WITH-LIMITS / REJECT with reasoning and verbatim licence quotes
- `process/context/data-sources/all-data-sources.md` — LSE row replaced by verified facts; the
  "unverified" caveat removed or the provider struck out
- `process/context/all-context.md` — "Equity data provider" moves out of Open Decisions
- A scratch verification script retained in this task folder, so the check is repeatable against
  any future provider rather than being a one-off

## Scope

**In scope**

- Obtaining a free API key and exercising the `lse-data` client
- Measuring coverage, accuracy, corporate-action handling and quota cost
- Reading and quoting the data licence
- Updating context docs with the verdict

**Out of scope**

- Any `api/data/` adapter implementation — that is a separate plan, gated on an ADOPT verdict
- Any frontend work
- Evaluating LSE's options, macro or ML features — equities history is the question here
- Choosing a fallback provider if the verdict is REJECT — that becomes its own decision

## Assumptions and Constraints

- Free registration is genuinely free and requires no payment details. If a card is requested,
  stop and report; that changes the premise.
- Stooq is available keyless as a cross-check source. If not, substitute Alpaca free tier and note
  the substitution.
- This session's tooling cannot run a shell on the user's machine. Verification runs either in the
  cloud workspace (network permitting) or by the user locally, with output pasted back. Decide
  which at the start of EXECUTE — see Resume and Execution Handoff.
- Everything written stays inside this task folder. Per task-folder artefact colocation, no sibling
  `reports/` or `references/` directories are created.
- No secret goes into any file under `process/`. The API key lives in the environment only.

## Functional Requirements

- Verification runs from a single repeatable script, not ad-hoc commands
- Every claim in `findings.md` carries the number and the command that produced it
- The symbol set and time windows are fixed up front so results are comparable across providers
- The delisted-ticker probe is included; survivorship bias is a silent screener killer
- Cross-source comparison reports a distribution, not a single spot check
- Licence quotes are verbatim with URL and access date

## Non-Functional Requirements

- The verification script should run unattended in under ~15 minutes for the 50-symbol case
- Scratch data goes to a temp path or `store/`, never committed
- Rate limiting is respected; a quota exhaustion during verification is itself a finding to record

## Acceptance Criteria

1. A free API key is obtained and one authenticated request succeeds, with quota cost measured
2. Coverage table exists for the fixed symbol set: first date, last date, rows, missing sessions, longest gap
3. The delisted-ticker probe returns a documented result, and survivorship bias is stated as present or absent
4. Cross-source daily-close comparison over 5 years reports median, 99th percentile and maximum absolute % difference per symbol
5. Split behaviour is documented for both AAPL (Aug 2020) and NVDA (Jun 2024), naming whether default series are adjusted
6. OHLC integrity assertions run over the full pull and all violations are counted and reported
7. A 50-symbol backfill completes with elapsed time, quota consumed and store size recorded, and one DuckDB query runs across the resulting Parquet store
8. Redistribution terms are quoted verbatim with URL and access date, and the public-launch question is answered yes or no
9. `VERDICT.md` states ADOPT / ADOPT-WITH-LIMITS / REJECT and cites the evidence above
10. `all-data-sources.md` and `all-context.md` are updated, and the user confirms the decision

## Implementation Checklist

1. Decide where verification runs (cloud workspace vs user's machine); record it in this plan
2. Register for the free LSE API key; confirm no payment details required
3. Create a throwaway `uv` environment; install `lse-data`, `pandas`, `duckdb`, `pyarrow`, a market-calendar package
4. Store the key in the environment only; confirm it is not written to any file under `process/`
5. Fetch 30 days of `AAPL` daily; print rows — **test**: values plausible, dates correct
6. Call `GET /vault/usage` before and after step 5 — **test**: quota delta recorded
7. Write `verify_provider.py` in this task folder, parameterised by symbol set and window
8. Implement the coverage check (first/last date, rows, missing sessions vs exchange calendar) — **test**: run on the 5-symbol set, table written to `findings.md`
9. Add the delisted-ticker probe — **test**: result recorded either way
10. Implement the cross-source close comparison against Stooq — **test**: per-symbol difference distribution written to `findings.md`
11. Implement the split probes for AAPL and NVDA — **test**: bars either side of each split date printed and interpreted
12. Implement OHLC integrity assertions — **test**: violation counts reported, zero or otherwise
13. Run the 50-symbol backfill to a scratch Parquet store; record time, quota and size — **test**: one DuckDB 3-year window query returns across all symbols
14. Locate the data licence and `lse-data` repo licence; quote redistribution clauses verbatim into `VERDICT.md`
15. Write the verdict with reasoning; update `all-data-sources.md` and `all-context.md`
16. Present findings to the user and obtain confirmation before marking ✅ VERIFIED

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Verification quota is consumed before Phase 4 | Measure cost per request in Phase 1 and budget the backfill against the remaining allowance before running it |
| Cross-source disagreement is ambiguous — which one is wrong? | Use a third source (Alpaca) as tiebreaker before concluding LSE is at fault |
| Adjusted vs unadjusted confusion produces a false failure | Explicitly determine which series the default call returns before interpreting split results |
| The check silently becomes a single-symbol spot check | The fixed symbol set and the distribution requirement are acceptance criteria, not suggestions |
| An ADOPT verdict is later undermined by a licence change | Record the access date on every quote; re-check terms before public launch |
| Free tier disappears mid-project | Bulk Parquet export means history already pulled is retained locally; pull the full backfill early rather than fetching on demand |

## Integration Notes

- Depends on the Parquet + DuckDB storage decision recorded in `process/context/all-context.md` (2026-09-17)
- Blocks: the `api/data/` equity adapter, and any cointegration work on equities
- Does not block: crypto work — `ccxt` is already settled and independent of this verdict
- The verification script is deliberately provider-agnostic in shape, so a REJECT verdict costs
  little: point it at the next candidate

## Touchpoints

**Read**

- `process/context/all-context.md` — Open Decisions, storage decision, numerical-truth conventions
- `process/context/data-sources/all-data-sources.md` — Equity Providers table and Licensing section
- `process/context/tests/all-tests.md` — current state: no test surface exists; verification here is manual by necessity
- `process/features/cointegration-screener/_GUIDE.md` — the feature this unblocks

**Write**

- `process/general-plans/active/lse-data-verification_17-09-26/verify_provider.py`
- `process/general-plans/active/lse-data-verification_17-09-26/findings.md`
- `process/general-plans/active/lse-data-verification_17-09-26/VERDICT.md`
- `process/context/data-sources/all-data-sources.md` (on completion)
- `process/context/all-context.md` (Open Decisions row, on completion)

**Not touched**

- `web/`, `api/` — no product code exists and none is created here

## Public Contracts

None exposed by this plan; it ships no code that another package calls.

It does, however, **constrain a future contract**. The eventual `api/data/` equity adapter must
carry a redistribution flag on its output, per the rule in `all-data-sources.md`. The verdict
produced here sets that flag's value for LSE. Any later adapter design that omits the flag
contradicts this plan's outcome.

## Blast Radius

**Risk class: low.** Documentation and a scratch script only.

- Files changed on completion: 2 context files, 3 new files in this task folder
- Packages affected: none — no application code exists
- Reversibility: fully reversible; the only durable output is written knowledge
- The real risk is the opposite one: *skipping* this plan and building the screener on unverified
  data, where the cost is invalid research results that look correct

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| Authenticated request succeeds; quota delta measured | Hybrid | AC 1 |
| Coverage table over fixed symbol set vs exchange calendar | Fully-Automated | AC 2 |
| Delisted-ticker probe | Hybrid | AC 3 |
| Cross-source close comparison vs Stooq, distribution reported | Fully-Automated | AC 4 |
| Split probes at AAPL Aug-2020 and NVDA Jun-2024 | Agent-Probe | AC 5 |
| OHLC integrity assertions over full pull | Fully-Automated | AC 6 |
| 50-symbol backfill timed and quota-measured; DuckDB query over Parquet store | Hybrid | AC 7 |
| Licence located and quoted verbatim with URL and date | Agent-Probe | AC 8 |
| Verdict written citing the above | Agent-Probe | AC 9 |
| Context docs updated; user confirms | Agent-Probe | AC 10 |

**Note on strategy mix:** `process/context/tests/all-tests.md` records that this repo has no test
runner and no test surface. That is expected here — this plan verifies an external dataset, not
this codebase, so its gates are script assertions and recorded observations rather than a suite.
If a runner is chosen later, the OHLC integrity assertions are the natural seed for the first
`api/` test module.

## Test Infra Improvement Notes

(none identified yet)

## Validate Contract

(placeholder — vc-validate-agent writes this section before EXECUTE)

## Resume and Execution Handoff

1. **Selected plan file path**
   `process/general-plans/active/lse-data-verification_17-09-26/lse-data-verification_PLAN_17-09-26.md`

2. **Last completed phase or step**
   None — plan created 17-09-26, nothing executed.

3. **Validate-contract status**
   Pending — vc-validate-agent has not run.

4. **Supporting context files loaded**
   - `process/context/all-context.md`
   - `process/context/data-sources/all-data-sources.md`
   - `process/context/tests/all-tests.md`
   - `process/features/cointegration-screener/_GUIDE.md`

5. **Next step for a fresh agent picking up mid-execution**
   Read `findings.md` in this task folder first — if it exists, its last completed section tells you
   which phase to resume. If it does not exist, start at Phase 1 step 1: decide where verification
   runs. That decision is the one blocker a fresh agent cannot infer. Two options: run in the
   agent's own workspace if it has network access to the provider, or hand `verify_provider.py` to
   the user to run locally and paste back the output. Ask if unclear; do not guess, because a
   half-run verification that silently used a different environment than the one recorded is worse
   than no verification.

   **Do not** begin the `api/data/` adapter from this plan even if the verdict looks favourable
   mid-flight. Adapter work is a separate plan gated on a written ADOPT verdict.

## Cursor + RIPER-5 Guidance

- Use Cursor Plan mode: import the Implementation Checklist above
- RIPER-5: RESEARCH → INNOVATE → PLAN complete; this plan is the PLAN artifact
- Avoid writing product code during EXECUTE — the deliverable is a verdict, not an adapter
- After each phase: STOP and record the numbers in `findings.md` before proceeding

**Next Step: ENTER EXECUTE MODE** when the user approves, beginning at Phase 1.
