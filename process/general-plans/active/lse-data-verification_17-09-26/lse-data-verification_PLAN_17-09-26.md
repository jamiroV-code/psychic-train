---
name: plan:lse-data-verification
description: "Verify London Strategic Edge as my_site's equity data provider (coverage, accuracy, corporate actions, quota, redistribution terms) and record an ADOPT/ADOPT-WITH-LIMITS/REJECT verdict"
date: 17-09-26
feature: general-plans
---

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

**Symbol set (fixed, so results are comparable):** `AAPL`, `MSFT`, `SPY`, `XOM`, `KO`, `NVDA`,
plus `SIVB` (SVB Financial Group, delisted from Nasdaq 2023-03-28 after the 2023-03-10 bank
failure) as the delisted-ticker survivorship probe, with `FRC` (First Republic, delisted
2023-05-01) as backup if SIVB's result is ambiguous.

**Test.** For each symbol, request from the earliest available date to today. Record first date,
last date, row count, and count of missing sessions against an exchange calendar
(`pandas_market_calendars` or equivalent).

**Verify.** A table in `findings.md`: symbol, first date, last date, rows, missing sessions,
longest gap. The delisted ticker either returns history or returns nothing — both are findings,
and the second one means the screener universe is survivorship-biased.

**Done when.** Real history depth is a number, not a marketing claim.

> **Supplement note (24-09-26):** delisted-ticker probe (SIVB, backup FRC) and the Phase 4
> 50-symbol universe are now fixed in the plan text — see the symbol set above and the frozen
> list in Phase 4. This resolves the earlier VALIDATE-flagged gap; VALIDATE re-run pending.

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

> **Supplement note (24-09-26):** NVDA is now a member of the Phase 2/3 fixed symbol set (see
> Phase 2) — the earlier VALIDATE-flagged inconsistency is resolved. Also see the Validate
> Contract's Stooq Fallback note: this container cannot confirm Stooq's keyless CSV endpoint is
> still reachable; that check is deferred to the user's PC run.

### Phase 4 — Screener-scale feasibility ⏳

**What happens.** Test the use case that motivated the search, rather than a single symbol.

**Test.** Backfill a realistic screener universe (50 symbols, daily, maximum history),
preferring bulk Parquet export over per-symbol REST calls where available. Time it. Measure quota
consumed via `GET /vault/usage`. Write the result to a scratch Parquet store and run one DuckDB
query across it — a 3-year window over all symbols — to confirm the store shape works.

**Fixed universe (frozen 2026-09-24, not recomputed):** a frozen, explicit 50-symbol list spanning
sectors, written verbatim here rather than derived from a live index query (not reproducible
offline). Includes all 6 fixed-set live symbols (`AAPL`, `MSFT`, `SPY`, `XOM`, `KO`, `NVDA`).
`verify_provider.py` must read this list from a constant (e.g. `PHASE4_UNIVERSE`), so the same
list can be pointed at the next provider if the verdict is REJECT:

```
AAPL, MSFT, NVDA, GOOGL, AMZN, META, AVGO, ORCL, CRM, ADBE,
JPM, BAC, WFC, GS, MS,
UNH, JNJ, LLY, PFE, ABBV,
KO, PEP, WMT, PG, MCD, NKE, SBUX, HD, TGT, COST,
BA, CAT, GE, HON, UPS,
XOM, CVX, COP, SLB, OXY,
DIS, NFLX, CMCSA, VZ, T,
LIN, FCX, NEM,
NEE, SPY
```

(50 symbols total: 10 tech, 5 financials, 5 healthcare, 10 consumer, 5 industrials, 5 energy,
5 comm/media, 3 materials, 1 utility (NEE), plus SPY as the index proxy — 49 equities + SPY.)

**Verify.** Elapsed time, quota consumed, resulting store size on disk, DuckDB query time. Extrapolate
to the intended universe size and state whether a periodic refresh fits inside the free allowance.

**Done when.** It is known whether the screener is affordable on the free tier, with numbers.

> **Supplement note (24-09-26):** the 50-symbol universe now has a frozen, explicit list (see
> above) — the earlier VALIDATE-flagged gap is resolved. **Scratch-store location (resolved as an
> execute-agent instruction, not a plan change):** write the Phase 4 Parquet store outside
> `process/` entirely (e.g. `/tmp/` on whichever machine runs this phase, or the session
> scratchpad path) — never inside this task folder. This reconciles the Assumptions line
> "everything written stays inside this task folder" (that line covers durable artefacts:
> `verify_provider.py`, `findings.md`, `VERDICT.md`) with the Non-Functional Requirement that
> scratch data is "never committed": nothing under `process/` is currently `.gitignore`d, so a
> `store/` subfolder inside this task folder would not actually satisfy "never committed" without
> a separate `.gitignore` edit this plan does not otherwise need.

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
3. The delisted-ticker probe (SIVB, with FRC as backup) returns a documented result, and survivorship bias is stated as present or absent
4. Cross-source daily-close comparison over 5 years reports median, 99th percentile and maximum absolute % difference per symbol
5. Split behaviour is documented for both AAPL (Aug 2020) and NVDA (Jun 2024), naming whether default series are adjusted
6. OHLC integrity assertions run over the full pull and all violations are counted and reported
7. A 50-symbol backfill completes with elapsed time, quota consumed and store size recorded, and one DuckDB query runs across the resulting Parquet store
8. Redistribution terms are quoted verbatim with URL and access date, and the public-launch question is answered yes or no
9. `VERDICT.md` states ADOPT / ADOPT-WITH-LIMITS / REJECT and cites the evidence above
10. `all-data-sources.md` and `all-context.md` are updated, and the user confirms the decision

## Implementation Checklist

1. ~~Decide where verification runs (cloud workspace vs user's machine); record it in this plan~~
   **Decided (VALIDATE, 24-09-26): run the FULL plan (all 5 phases). vc-execute-agent writes
   `verify_provider.py` + offline fixture tests + a `findings.md` skeleton in the cloud
   workspace; the live network commands (Phases 1–4's actual LSE/Stooq calls) run on the
   user's own PC, with output pasted back.** Reason: this cloud container's egress proxy
   returns 403 (CONNECT-tunnel) for both `londonstrategicedge.com` and `stooq.com` — the same
   failure mode hit the regime dashboard's FRED/DefiLlama calls, whose AC-11 also had to run on
   the user's PC. See the Validate Contract's "Execution Split" for exact commands on each side.
2. Register for the free LSE API key; confirm no payment details required
3. Create a throwaway `uv` environment; install `lse-data`, `pandas`, `duckdb`, `pyarrow`, a market-calendar package
4. Store the key in the environment only; confirm it is not written to any file under `process/`
5. Fetch 30 days of `AAPL` daily; print rows — **test**: values plausible, dates correct
6. Call `GET /vault/usage` before and after step 5 — **test**: quota delta recorded
7. Write `verify_provider.py` in this task folder, parameterised by symbol set and window
8. Implement the coverage check (first/last date, rows, missing sessions vs exchange calendar) — **test**: run on the 6-symbol fixed set, table written to `findings.md`
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
- `process/context/tests/all-tests.md` — current state: `pytest` (api/), `vitest` + Playwright (web/)
  all exist and are green (see Validate Contract Dimension Findings — this line previously said "no
  test surface exists", which was true until 18/19-09-26 and is stale now). None of that runner
  infrastructure applies to this plan (no `api/`/`web/` code is touched) — verification here uses
  its own small offline pytest suite scoped to this task folder, plus manual/pasted-output checks
  for anything that needs the live network.
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

**Note on strategy mix (corrected 24-09-26 — see Touchpoints):** `all-tests.md` now records real,
green `pytest`/`vitest`/`Playwright` runners for `api/` and `web/`, but none of that surface is
touched by this plan (Blast Radius: no application code). This plan's own verification *logic* —
the coverage/gap calculation, the cross-source diff distribution, the split-discontinuity check,
and the OHLC integrity assertions — gets genuine, fully-automated offline pytest coverage against
synthetic fixtures, scoped to this task folder (not the `api/` uv project — see the Validate
Contract's Test Gates for the exact command). What stays manual is only the part that needs a real
network call to LSE/Stooq/Alpaca's own servers, or human judgement (licence text, split
interpretation, the verdict itself) — those are Hybrid/Agent-Probe, run by the user on their own
PC per the Validate Contract's Execution Split, not a known-gap. If a runner is chosen later for
`api/`, the OHLC integrity assertions here are still the natural seed for the first `api/` test
module.

## Test Infra Improvement Notes

(none identified yet)

## Validate Contract

Status: PASS
Date: 24-09-26 (re-validated, cycle 2)
date: 2026-09-24
generated-by: outer-pvl
supersedes: 2026-09-24 (outer-pvl) — outer PVL has current evidence (post plan-supplement cycle 1: G1/G2/G3 resolved)

Parallel strategy: sequential
Rationale: 7-signal score for this VALIDATE fan-out = 1/7 (only S7 present — Blast Radius lists
exactly 5 files). No multi-package scope, no schema/API/auth surface, no phase-program
classification, low risk class. `vc-agent-strategy-compare` LOW threshold (0-1) → sequential,
single-agent analysis — no parallel dimension/section fan-out was spawned for this VALIDATE pass.

### Execution Split (what runs where)

**vc-execute-agent (opus), in the cloud workspace — writes, does not call the network:**
1. Write `verify_provider.py` in this task folder with the provider logic factored into small,
   independently-testable functions:
   - `fetch_candles(symbol, start, end, api_key)` — thin network wrapper around the `lse-data`
     client; reads `api_key` from a function argument only, never hardcodes or logs it
   - `compute_coverage(df, calendar)` → `(first_date, last_date, rows, missing_sessions, longest_gap)`
   - `probe_delisted(symbol, api_key)` → result rows or empty
   - `cross_source_diff(lse_df, other_df)` → `{max, p99, median}` absolute % difference
   - `detect_split_discontinuity(df, split_date, expected_ratio)` → observed ratio + flag
   - `assert_ohlc_integrity(df)` → list of violations (empty = clean)
   - A CLI (`--phase {1,2,3,4}`) that calls the above; reads `LSE_API_KEY` (and, if the Stooq
     fallback triggers, `ALPACA_API_KEY`) from the environment only — never accepts a key as a
     CLI flag, never writes one to `findings.md`, `VERDICT.md`, or any log line
2. Write offline fixture tests (pytest, synthetic pandas DataFrames, no network) for every
   function above — see Test Gates below for the exact command and what each proves
3. Write a `findings.md` skeleton with one section per phase and explicit placeholders for the
   numbers the user's pasted output will fill in
4. Run the offline suite in-container and confirm it is green before handing off
5. Do NOT run `verify_provider.py --phase {1,2,3,4}` in-container — this container's egress
   proxy returns 403 for `londonstrategicedge.com` and `stooq.com`; a live attempt is expected
   to fail and is not a defect to chase
6. Do NOT touch `api/data/`, `api/`, or `web/`
7. Do NOT attempt to register for the LSE (or Alpaca) API key, and never write a key value into
   any file — env var only

**User, on their own PC — runs the live commands, pastes output back:**

```bash
# 1. Register for the free LSE API key in a browser first (manual, not scriptable).
#    If a payment card is requested at any point: STOP, do not proceed, report back.

# 2. One-time throwaway environment, inside the task folder:
cd process/general-plans/active/lse-data-verification_17-09-26
uv venv .venv-lse --python 3.12
source .venv-lse/bin/activate            # Windows: .venv-lse\Scripts\activate
uv pip install lse-data pandas duckdb pyarrow pandas_market_calendars httpx pytest

# 3. Set the key in the environment only — never in a file:
export LSE_API_KEY="<paste-your-key>"    # Windows: set LSE_API_KEY=<paste-your-key>

# 4. Optional sanity check — confirms the environment before spending quota:
uv run --with pytest,pandas,duckdb,pyarrow,pandas_market_calendars pytest . -q

# 5. Run each phase and paste the full stdout back into the session:
python verify_provider.py --phase 1
python verify_provider.py --phase 2
python verify_provider.py --phase 3      # add ALPACA_API_KEY export first if Stooq fails — see Stooq Fallback below
python verify_provider.py --phase 4
```

For AC 8: open `https://londonstrategicedge.com/terms/` in a browser, copy the exact
redistribution clause verbatim (not a paraphrase), and paste it back with the URL and today's
date.

### Stooq Fallback

This container cannot confirm whether Stooq's keyless CSV export (`stooq.com`) is still live —
its egress proxy returns 403 for it too, the same as LSE. **If, when the user runs Phase 3 on
their PC, Stooq's CSV endpoint is dead, rate-limited beyond use, or now requires a key:**
substitute Alpaca free tier as the primary AC-4 cross-check (not merely the tiebreaker the plan
currently names it as). **Implication to flag to the user before this happens:** Alpaca requires
its own separate free registration and its own API key (`ALPACA_API_KEY`) — this is an extra
manual signup step beyond LSE's, only needed if Stooq is unreachable. Record which path was
actually used in `findings.md`.

### Hard Stops

- **Card requested at signup** (LSE or, if triggered, Alpaca) → STOP immediately, do not
  proceed, report back. Per the plan's own Assumptions — this changes the premise of a "free
  tier" evaluation.
- **No secret in `process/`** — the LSE/Alpaca API key never appears in `verify_provider.py`,
  `findings.md`, `VERDICT.md`, this plan file, or any committed log output. Environment
  variable only, on whichever machine runs the live calls.
- **No `api/data/` adapter work** — this plan verifies a provider; it does not implement one.
  Adapter work is a separate, later plan gated on a written ADOPT verdict (per Scope and
  Integration Notes).
- **Scratch data is never committed** — the Phase 4 backfill's Parquet store is written outside
  `process/` entirely (e.g. `/tmp/`, or the runner's own scratch path) — not into a `store/`
  subfolder inside this task folder, since nothing under `process/` is currently
  `.gitignore`d and this plan does not otherwise need a `.gitignore` change.

### Test Gates

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC1 | Authenticated request succeeds; quota cost measured via `GET /vault/usage` before/after | Hybrid | User-run on PC: `python verify_provider.py --phase 1`; paste stdout (rows + quota delta) into `findings.md` | A |
| AC2-math | Coverage function (first/last date, row count, missing-session count vs exchange calendar) is arithmetically correct | Fully-Automated | `uv run --with pytest,pandas,pandas_market_calendars pytest process/general-plans/active/lse-data-verification_17-09-26/ -k coverage -q` (offline, synthetic OHLC fixture with known gaps) | A |
| AC2-live | Coverage table populated for the fixed symbol set from real LSE data | Hybrid | User-run: `python verify_provider.py --phase 2`; paste table into `findings.md` | A |
| AC3-math | Delisted-ticker probe correctly classifies empty-vs-nonempty result as survivorship-bias present/absent | Fully-Automated | Same suite, `-k delisted` | A |
| AC3-live | Delisted-ticker probe run against real LSE data for SIVB (backup: FRC) | Hybrid | User-run: `python verify_provider.py --phase 2` | A |
| AC4-math | Cross-source diff distribution (max/p99/median absolute % diff) computed correctly | Fully-Automated | Same suite, `-k cross_source_diff`, synthetic close-price fixture | A |
| AC4-live | Cross-source comparison run against real LSE + Stooq (or Alpaca, if substituted) data | Hybrid | User-run: `python verify_provider.py --phase 3`; note which second source was actually used | A |
| AC5-math | Split-ratio detection math (raw discontinuity vs adjusted-series check) is correct | Fully-Automated | Same suite, `-k split_probe`, synthetic bars either side of a known 4:1 and 10:1 split | A |
| AC5-live | Split behaviour interpreted for AAPL (Aug 2020) and NVDA (Jun 2024) from real bars | Agent-Probe | Agent inspects the user's pasted bars either side of each date, judges adjusted vs raw | A |
| AC6 | OHLC integrity assertions (`low<=min(open,close)`, `max(open,close)<=high`, positivity, no dup timestamps, monotonic dates) | Fully-Automated | Same suite, `-k ohlc_integrity`, synthetic fixture with each violation type injected | A |
| AC7-math | Backfill store-shape / DuckDB query logic is correct | Fully-Automated | Same suite, `-k store_shape`, synthetic 3-symbol Parquet fixture | A |
| AC7-live | 50-symbol backfill (frozen universe, Phase 4) timed, quota measured, one DuckDB 3-year query run across the real store | Hybrid | User-run: `python verify_provider.py --phase 4` | A |
| AC8 | Redistribution terms quoted verbatim with URL and access date | Agent-Probe | User visits `londonstrategicedge.com/terms/` in a browser, pastes the verbatim clause; agent transcribes into `VERDICT.md` | A |
| AC9 | `VERDICT.md` states ADOPT/ADOPT-WITH-LIMITS/REJECT citing the evidence above | Agent-Probe | Agent synthesizes `findings.md` + the AC8 quote into `VERDICT.md` | A |
| AC10 | Context docs updated; user confirms | Agent-Probe | Agent edits `all-data-sources.md` + `all-context.md`; user says "confirmed" | A |

gap-resolution legend:
- A — proven now (gate passes in this cycle, once the live/agent-probe leg completes)
- B — fixed in this plan (gate added by this plan's checklist)
- C — deferred to a named later phase/plan (none used in this contract as of the 24-09-26
  plan-supplement — the delisted ticker and 50-symbol universe are now both named in the plan
  text)
- D — backlog test-building stub (not used in this contract)

C-4 reconciliation: the `strategy` column above carries only Fully-Automated / Hybrid /
Agent-Probe. No row uses Known-Gap as a proving strategy — every developed behavior in this
plan's blast radius has at least one Fully-Automated or Hybrid gate (see Net-Gate
Vacuous-Green Check below).

Legacy line form:
- Coverage/gap/diff/split/OHLC-integrity math: Fully-automated:
  `uv run --with pytest,pandas,duckdb,pyarrow,pandas_market_calendars pytest process/general-plans/active/lse-data-verification_17-09-26/ -q`
- Live provider calls (AC1, AC2-live, AC3-live, AC4-live, AC7-live): Hybrid — precondition:
  free LSE (and possibly Alpaca) API key, run on the user's own PC, output pasted back
- Split interpretation, licence quote, verdict, context-doc confirmation (AC5-live, AC8, AC9,
  AC10): agent-probe — human/agent judgement, not mechanically assertable

**Inline failing stubs (Fully-Automated rows):**

```
test("should compute coverage stats correctly against a synthetic fixture with known gaps", () => {
  throw new Error("NOT IMPLEMENTED — TDD stub: AC2-math coverage calculation")
})
test("should classify delisted-ticker probe result as survivorship-bias present/absent", () => {
  throw new Error("NOT IMPLEMENTED — TDD stub: AC3-math delisted classification")
})
test("should compute cross-source diff distribution (max/p99/median) correctly", () => {
  throw new Error("NOT IMPLEMENTED — TDD stub: AC4-math cross-source diff")
})
test("should detect a 4:1 and a 10:1 split discontinuity against synthetic bars", () => {
  throw new Error("NOT IMPLEMENTED — TDD stub: AC5-math split detection")
})
test("should flag every injected OHLC integrity violation and report zero on a clean fixture", () => {
  throw new Error("NOT IMPLEMENTED — TDD stub: AC6 OHLC integrity assertions")
})
test("should build and query a Parquet store shape matching the real backfill output", () => {
  throw new Error("NOT IMPLEMENTED — TDD stub: AC7-math store shape / DuckDB query")
})
```

(Written as plain Python `pytest` functions when execute-agent implements them — the JS-style
`test(...)` wrapper above is this contract's stub notation, not literal syntax to run as-is.)

### Net-Gate Vacuous-Green Check

Every developed behavior in this plan's blast radius (the 6 pure functions in
`verify_provider.py`) has a Fully-Automated proving test above. No behavior rests on Known-Gap
alone. The live-network legs (AC1/2/3/4/7-live) are Hybrid, proven by the user's pasted output,
not dropped as gaps. AC5-live/AC8/AC9/AC10 are Agent-Probe, requiring judgement that cannot be
mechanically asserted, and are proven by the recorded interpretation in `findings.md`/`VERDICT.md`.
This satisfies the ban on a vacuously-green net gate.

### Dimension findings (re-validated, cycle 2 — 24-09-26)

- Infra fit: PASS — no container/infra/runtime surface touched; scratch script confined to this
  task folder; the scratch-store location gap is resolved as an execute-agent instruction.
- Test coverage: PASS — Touchpoints/Verification Evidence text now correctly states real
  `pytest`/`vitest`/Playwright runners exist for `api/`/`web/` but are inapplicable to this
  plan's own blast radius; this plan's verification logic gets its own offline pytest suite.
  Confirmed still accurate on re-read; no drift since first pass.
- Breaking changes: PASS — no public contract, schema, or API is changed; `Public Contracts`
  section correctly scopes this as a future-constraint only.
- Security surface: PASS — Execution Split's execute-agent instructions (env-var-only key,
  never a CLI flag, never logged) and Hard Stops ("No secret in `process/`") remain intact and
  consistent on re-read.
- Phase 2/3 feasibility (Execution Brief): PASS — plan-supplement cycle 1 named the delisted
  ticker (SIVB, backup FRC — Phase 2) and added NVDA to the fixed symbol set. Re-checked by
  direct grep: SIVB/FRC/NVDA appear consistently across Phase 2, Phase 3 supplement note, AC3,
  AC5, Test Gates AC3-live, Open Gaps, and Resume/Handoff — no stale "5-symbol" or "unnamed"
  ticker references remain anywhere in the plan.
- Phase 4 feasibility (Execution Brief): PASS — a frozen, explicit 50-symbol list is now written
  into Phase 4, read from a `PHASE4_UNIVERSE` constant. Independently verified: exactly 50
  entries, all unique (script check, no duplicates), and all 6 fixed-set live symbols (`AAPL`,
  `MSFT`, `SPY`, `XOM`, `KO`, `NVDA`) are members of the universe.
- Phase 5 feasibility (Execution Brief): PASS — the verbatim-quote requirement remains correctly
  scoped as Agent-Probe; unaffected by the supplement.

### What this coverage does NOT prove

- The Fully-Automated offline suite proves the verification *logic* (coverage/gap math,
  cross-source diff math, split-ratio detection, OHLC integrity assertions, store-shape/query
  logic) is correct against synthetic fixtures. It does NOT prove LSE's real data is accurate,
  complete, or correctly adjusted — that is exactly what the Hybrid/Agent-Probe legs (run by the
  user, on their PC, against the real API) are for, and none of AC1/2/3/4/5/7/8/9/10 can be
  closed from this container alone.
- It does NOT prove the LSE free tier stays free, or that its quota/rate limits match what is
  advertised — that is discovered empirically during the user's live run, not asserted in
  advance.
- It does NOT prove Stooq's keyless CSV endpoint is currently reachable (this container's egress
  is blocked for it too) — see Stooq Fallback.
- ~~It does NOT resolve which delisted ticker or which 50 symbols are used~~ **Resolved via
  plan-supplement cycle 1: both are now named (SIVB/FRC; the frozen 50-symbol list) — see Open
  Gaps.** What remains unresolved is only whether the *real* LSE/Stooq data for those named
  symbols behaves as expected — that is exactly the Hybrid/Agent-Probe legs' job, not a gap in
  this coverage.

### Open gaps

- ~~Delisted ticker for the Phase 2/3 survivorship-bias probe is unnamed~~ **Resolved via
  plan-supplement cycle 1 (24-09-26): SIVB (backup: FRC) — see Phase 2 symbol set.**
- ~~NVDA is used in the Phase 3 split probe without being a member of the fixed symbol set~~
  **Resolved via plan-supplement cycle 1 (24-09-26): NVDA added to the fixed symbol set — see
  Phase 2.**
- ~~The Phase 4 50-symbol backfill universe has no named list or selection rule~~ **Resolved via
  plan-supplement cycle 1 (24-09-26): a frozen, explicit 50-symbol list is now written into
  Phase 4.**
- Whether Stooq's keyless CSV endpoint is still reachable is unknown until the user's PC run —
  see Stooq Fallback (not a plan gap, a live-network unknown).

Gate: PASS
Accepted by: N/A — Gate is PASS, no unresolved CONCERNs remain to accept. All 3 gaps from the
first-pass CONDITIONAL (G1 delisted ticker, G2 NVDA in fixed set, G3 50-symbol universe) were
closed by plan-supplement cycle 1 and independently re-verified in this V1–V7 re-run (cycle 2):
uniqueness/count-checked 50-symbol list, cross-section grep confirming no stale references, and
re-read of all previously-CONCERN dimensions. `results.tsv` in this task folder records baseline
(cycle 0, CONDITIONAL) + cycle 1 (supplement applied) — the mechanical `wc -l` ≥ 3 gate for
EXECUTE eligibility is satisfied independent of this PASS. `PHASE_COMPLETE: VALIDATE` is now
legal — see V7 verdict below.

## Autonomous Goal Block

SESSION GOAL: Verify London Strategic Edge as my_site's equity data provider — quality, coverage, corporate actions, quota cost, and redistribution terms — and record an ADOPT / ADOPT-WITH-LIMITS / REJECT verdict.
Charter + umbrella plan: N/A — single plan (process/general-plans/active/lse-data-verification_17-09-26/lse-data-verification_PLAN_17-09-26.md)
Autonomy: Standard RIPER-5 gates apply; no standing autonomy granted. ENTER EXECUTE MODE still requires an explicit user command (now legal to issue — see Next phase below).
Hard stop conditions / safety constraints:
- If free registration (LSE or Alpaca) requests payment/card details, stop immediately and report — do not proceed.
- No secret (API key) is ever written to any file under process/ — environment variable only.
- No api/data/ adapter work happens in this plan — that is a separate, later plan gated on a written ADOPT verdict.
- Scratch Parquet data from the Phase 4 backfill is never committed — written outside process/ entirely.
- Live network verification cannot run in the cloud container (egress proxy blocks londonstrategicedge.com and stooq.com) — those steps run on the user's own PC only; the agent must never attempt them in-container.
Next phase: VALIDATE re-run (cycle 2, 24-09-26) confirms Gate: PASS — all 3 gaps closed and independently re-verified. ENTER EXECUTE MODE is now legal.
Validate contract: inline in plan (## Validate Contract section, this file)
Execute start: Fully-auto: `uv run --with pytest,pandas,duckdb,pyarrow,pandas_market_calendars pytest process/general-plans/active/lse-data-verification_17-09-26/ -q` | Hybrid/live: user runs `verify_provider.py --phase {1..4}` on their PC per the Execution Split | Agent-Probe: AAPL/NVDA split interpretation, licence verbatim quote, VERDICT.md synthesis | high-risk pack: no (risk class: low; no auth/billing/schema/API/container surface)

## Resume and Execution Handoff

1. **Selected plan file path**
   `process/general-plans/active/lse-data-verification_17-09-26/lse-data-verification_PLAN_17-09-26.md`

2. **Last completed phase or step**
   VALIDATE re-run (cycle 2, 24-09-26): confirmed all three plan-supplement cycle 1 fixes
   (delisted-ticker name, NVDA symbol-set inclusion, 50-symbol universe definition) are closed
   and internally consistent. Gate: PASS.

3. **Validate-contract status**
   Written, `## Validate Contract` above, Gate: PASS, `generated-by: outer-pvl` (supersedes the
   24-09-26 first-pass CONDITIONAL contract).

4. **Supporting context files loaded**
   - `process/context/all-context.md`
   - `process/context/data-sources/all-data-sources.md`
   - `process/context/tests/all-tests.md`

5. **Next step for a fresh agent picking up mid-execution**
   VALIDATE has reached Gate: PASS (cycle 2, 24-09-26). `ENTER EXECUTE MODE` is now legal. When
   EXECUTE does run: read `findings.md` in this task folder first — if it exists, its last
   completed section tells you which phase to resume; if not, start at Phase 1.

   **Do not** begin the `api/data/` adapter from this plan even if the verdict looks favourable
   mid-flight. Adapter work is a separate plan gated on a written ADOPT verdict.

## Cursor + RIPER-5 Guidance

- Use Cursor Plan mode: import the Implementation Checklist above
- RIPER-5: RESEARCH → INNOVATE → PLAN → VALIDATE (CONDITIONAL, first pass) → PLAN-SUPPLEMENT
  cycle 1 (complete, 24-09-26) → VALIDATE re-run (PASS, cycle 2, complete) → EXECUTE (ready to start)
- Avoid writing product code during EXECUTE — the deliverable is a verdict, not an adapter
- After each phase: STOP and record the numbers in `findings.md` before proceeding

**Next Step:** VALIDATE re-run complete — Gate: PASS. Say `ENTER EXECUTE MODE` to begin Phase 1
of the Execution Split (vc-execute-agent writes `verify_provider.py` + offline fixture tests in
the cloud workspace; the user then runs the live commands on their own PC per the Execution
Split above).
