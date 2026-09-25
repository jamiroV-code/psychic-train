---
name: plan:chain-growth
description: "New /onchain-activity dashboard tracking daily active addresses, new addresses, and tx count per chain (incl. Robinhood Chain, Solana) with a normalized floor/ramp comparison view"
date: 25-09-26
feature: onchain-activity
---

[MODE: PLAN]

# Chain Participant Growth Dashboard — `/onchain-activity`

**Date**: 25-09-26
**Complexity**: Complex (standard complex — one authoritative plan, 6 RFCs, RFC-1 is a
mandatory FEASIBILITY gate that RFC-2+ build on)
**Status**: 📋 PLANNED — no code exists yet. SPEC locked, INNOVATE decision summary (vc-predict:
CAUTION) encoded below as ADRs. Nothing may build on Dune, growthepie, or any other candidate
source until RFC-1's live probe confirms it — this sandbox's egress proxy blocks all of them.
**Feature folder**: `process/features/onchain-activity/`
**Owner**: user · executor: vc harness agents

> **TL;DR** — Build `/onchain-activity`: nine chains (Ethereum, Robinhood Chain, Base, Arbitrum,
> Optimism, Polygon, BNB Chain, Tron, Solana), three metrics (DAA, new addresses, tx count),
> sourced from a split of growthepie (EVM L2s+Ethereum, keyless), L2BEAT (tx cross-check, keyless)
> and Dune (Solana/BNB/Tron/Polygon + new-addresses everywhere, keyed, user's free account). RFC-1
> is a hard feasibility gate — before any adapter is written, it proves the Dune account can
> actually run per-chain queries within free-tier credits, and confirms growthepie/L2BEAT chain
> coverage including Robinhood Chain. Everything downstream (config, adapters, nightly archive,
> floor/ramp analytics, frontend, tests) is gated on RFC-1 passing. This mirrors the regime and
> narrative dashboards' own "prove the source before building on it" precedent — CAUTION-flagged
> by vc-predict specifically because Dune's free-tier credit ceiling (2,500/month) and 2-minute
> small-engine query timeout are real failure surfaces, not hypothetical ones.

---

## Overview

`process/features/onchain-activity/` is a brand-new feature folder — no code exists anywhere in
the repo for chain-level participant activity. This plan follows the same shape as the two
existing dashboard programs (`cycle-regime`, `narrative-mindshare`): provider adapters behind a
common contract, an append-only per-(entity, metric) cache using the existing `cache.py` patterns,
a nightly forward-archive GitHub Actions workflow, Python-only analytics (floor/ramp + comparison
maths), a `GET /api/onchain/growth` endpoint reusing the regime dashboard's `grid_dates` /
`gap_before` / `max_gap_days` response shape, and a small-multiples + normalized-overlay frontend
pattern lifted from `ComponentPanel`.

The single hardest constraint in this plan is **feasibility-first sequencing**: unlike the regime
and narrative dashboards (which built on sources whose *existence and basic shape* were already
well understood, even if live-blocked in-sandbox), this program's INNOVATE decision explicitly
carries **vc-predict: CAUTION** because two of the four candidate sources (Dune's credit economics,
growthepie's exact chain-slug coverage for a chain that launched 12 weeks ago) are genuinely
unverified, not just untested. RFC-1 exists specifically to convert that CAUTION into either a
locked design or an early, cheap pivot — before RFC-2 writes a single adapter.

## Quick Links

- [1. Context and Goals](#1-context-and-goals)
- [Phase Completion Rules](#phase-completion-rules)
- [Architecture Decisions (ADRs, from INNOVATE)](#architecture-decisions-adrs-from-innovate)
- [High-Level Data Flow](#high-level-data-flow)
- [API Surface](#api-surface)
- [RFCs](#rfcs)
- [Touchpoints](#touchpoints) · [Public Contracts](#public-contracts) · [Blast Radius](#blast-radius)
- [Ops Runbook](#ops-runbook)
- [Verification Evidence](#verification-evidence) · [Test Infra Improvement Notes](#test-infra-improvement-notes)
- [Validate Contract](#validate-contract) · [Resume and Execution Handoff](#resume-and-execution-handoff)

### Status Strip

| RFC | Title | Status |
|---|---|---|
| RFC-1 | FEASIBILITY: Dune credit/API probe, growthepie/L2BEAT chain coverage, all source terms | ⏳ NOT STARTED — hard gate, RFC-2+ blocked until this passes |
| RFC-2 | Config + adapters (growthepie, L2BEAT, Dune) | ⏳ NOT STARTED — depends on RFC-1 |
| RFC-3 | Storage + nightly archive workflow + backfill | ⏳ NOT STARTED — depends on RFC-2 |
| RFC-4 | Floor/ramp + comparison analytics (real-data validated) + `GET /api/onchain/growth` | ⏳ NOT STARTED — depends on RFC-3 |
| RFC-5 | `/onchain-activity` frontend — panels, normalized overlay, drill-down | ⏳ NOT STARTED — depends on RFC-4 contract settling (may start in parallel once RFC-4's response model is locked) |
| RFC-6 | Tests, seeded E2E, context docs update, AC-14 real-cache walkthrough handoff | ⏳ NOT STARTED — depends on RFC-4 + RFC-5 |

---

## 1. Context and Goals

**Context loaded for this plan** (per `process/context/all-context.md` routing):

- `process/context/all-context.md` — repo state, redistribution posture, open questions
- `process/context/data-sources/all-data-sources.md` — free/keyless standing rules, adapter shape,
  redistribution-flag convention (this plan adds the first chain-activity provider category)
- `process/context/tests/all-tests.md` — runner split, exact commands, Standing Lesson table
  (the narrative RFC-6 `None`→`NaN` pandas lesson directly informs RFC-4's dtype discipline)
- `process/context/planning/all-planning.md` — complex-plan shape calibration
- `process/features/onchain-activity/_GUIDE.md` — scope, locked user decisions, target file layout
- `process/features/onchain-activity/active/chain-growth_25-09-26/chain-growth_SPEC_25-09-26.md`
  — locked SPEC (14 ACs, all read and carried below)
- `process/features/cycle-regime/completed/regime-dashboard_24-09-26/regime-dashboard_PLAN_24-09-26.md`
  and `process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md`
  — direct structural precedent (Status Strip, ADRs, RFC shape with Stage 0 present-and-STOP, Ops
  Runbook, Resume/Handoff)
- Code precedents read: `api/data/{defillama_adapter,etf_flows_adapter,cache}.py`,
  `api/routers/regime.py`, `api/analytics/regime/components_response.py` (`grid_dates`,
  `gap_before`, `max_gap_days`), `api/models/regime.py`, `web/components/regime/*`,
  `web/lib/regime-line-segments.ts`, `.github/workflows/{liqtide,narrative}-snapshot.yml`,
  `api/scripts/{snapshot_narrative,seed_e2e_cache}.py`, `web/e2e/regime.spec.ts`,
  `api/data/narrative_category_map.json` (the "option B" user-editable config precedent)

**Goals** (mapped from SPEC user stories):

1. Every tracked chain shows all three participant-growth metrics, honestly, with source/method
   disclosed (US-1, US-2, US-4 → AC-1, AC-2, AC-8).
2. A normalized comparison view makes "which chain bottomed and is ramping" visually obvious
   without comparing raw magnitudes (US-1 → AC-3, AC-13).
3. Robinhood Chain is visible from day one with a limited-history flag; floor/ramp markers wait
   for sufficient history on every chain (US-3, SPEC constraint → AC-4, AC-6).
4. Raw numbers are always available via drill-down (US-5 → AC-5).
5. The chain list is config-driven, no code change to add a chain an existing adapter supports
   (US-6 → AC-11).
6. A single chain/source failure never takes the rest of the dashboard down, and no key ever
   reaches the client (US-4 → AC-7, AC-9, AC-10, AC-12).
7. A real-machine walkthrough confirms the dashboard against live data before it's trusted (US-7
   → AC-14).

**Non-goals**: see SPEC Out Of Scope — no equity metrics, no buy/sell signals, no Sybil filtering
beyond source-native, no source backfill beyond native depth, no change to `/regime`, `/narrative`,
`/screener`.

## Phase Completion Rules

- `⏳ NOT STARTED` — plan section written, no code
- `🔨 CODE DONE` — implementation complete, EVL gates green, not yet user-verified against real data
- `✅ VERIFIED` — real-machine confirmation received (RFC-1's live probe results; RFC-6's AC-14
  walkthrough) or gate genuinely provable in-sandbox
- A phase may not claim `✅ VERIFIED` on synthetic-fixture evidence alone when the SPEC's `proven
  by:` strategy for its AC is Agent-Probe against real data.

---

## Architecture Decisions (ADRs, from INNOVATE)

**ADR-1 — Split sources by chain, not one universal provider.**
- growthepie (keyless, CC BY 4.0, attribution required: "Source: growthepie,
  https://www.growthepie.com") supplies `daa` (unique from-addresses) and `txcount` for Ethereum,
  Base, Arbitrum, Optimism, and Robinhood Chain (slug `robinhood` — **unverified, RFC-1 Stage 0
  confirms or finds the real slug**).
- L2BEAT activity API (keyless) supplies tx/UOPS as a cross-check only for the same L2 set — not a
  primary source, used to sanity-check growthepie's tx counts.
- Dune (the user's pre-2026-07-21 free account, `DUNE_API_KEY` server-side only) supplies all three
  metrics for Solana, BNB Chain, Tron, and Polygon, **plus** new-addresses for ALL nine chains
  (growthepie does not expose a new-addresses metric).
- Etherscan V2 and Artemis are **rejected**: Etherscan V2's free tier gates the volume this feature
  needs behind a paid plan for the multi-chain call pattern required here; Robinhood Chain's free
  access via Etherscan V2 sunsets 2026-10-15 (too close to rely on); Artemis is paid-gated. Neither
  appears in any adapter.
- Per-chain, per-metric source and counting-method disclosure is a first-class response field, not
  a UI-only label — see API Surface below.
- Rejected alternative: a single "universal" adapter shape that tries every source per chain and
  picks whichever responds — rejected because it hides which method backs a number, violating
  AC-2/AC-4's disclosure requirement outright.

**ADR-2 — Dune query discipline: isolated, versioned, schema-checked, budget-aware.**
- One Dune query per (chain, metric-group) — not one giant multi-chain query — so a single chain's
  query failure never blocks another chain's data (AC-12 failure isolation).
- New-addresses uses a **bounded-lookback incremental first-seen** approach (e.g. "addresses whose
  first-ever tx on this chain falls in the last 35 days, computed against a rolling window of prior
  first-seen state persisted in the cache"), never a full-history re-scan — full history per query
  would blow the 2-minute small-engine timeout and the credit budget on chains with billions of
  historical rows (Solana).
- Exactly **one execution per chain per day** via the nightly workflow, followed by Dune's "Get
  Latest Query Result" endpoint for any same-day re-reads (never re-executes) — this is the credit
  discipline that keeps 4 chains × 3 metrics well under the 2,500/month free-tier ceiling (RFC-1
  Stage 0 computes and records the exact per-query credit cost before RFC-2 writes any adapter
  code).
- Query IDs and the exact SQL are version-controlled in the repo: `api/data/dune_queries/*.sql`,
  with each query's numeric Dune query-id recorded in `api/data/chains.json` (per-chain config, see
  ADR-6) — never hardcoded as a bare literal in adapter code, so a query can be edited on Dune's
  UI and the repo updated deliberately, not silently drift.
- Every Dune adapter response is schema/health-checked (expected columns present, expected dtypes,
  non-implausible row count) before being trusted — not just a generic HTTP-retry. A schema
  mismatch is treated as `unavailable`, never silently coerced.
- The Dune small-engine 2-minute execution timeout is handled explicitly: poll `execution status`
  with a bounded number of retries and a hard ceiling under 2 minutes; a timeout is `unavailable`
  for that chain/day, never a blocking retry loop that could stall the whole nightly job.
- Rejected alternative: paying for Dune's medium/large query engine to avoid the 2-minute ceiling —
  rejected outright, violates the SPEC's free-sources-only constraint.

**ADR-3 — Storage: append-only per-(chain, metric) cache, new dedicated nightly workflow.**
- New `cache.py` functions follow the existing `write_liquidity_series`/`read_liquidity_series`
  and `write_exchange_point`/`read_exchange_series` shape exactly: `chain_growth_series_path(chain_id,
  metric)`, `read_chain_growth_series(chain_id, metric)`, `write_chain_growth_point(chain_id, metric,
  date, value, source, method, status)` — append-only, deduped on date, no overwrite of prior rows.
- New workflow `.github/workflows/chain-growth-snapshot.yml`, separate from
  `liqtide-snapshot.yml`/`narrative-snapshot.yml`, its own offset cron (proposed `0 22 * * *`, 30/60
  min clear of the other two jobs' windows) and its own `concurrency: chain-growth-snapshot` group,
  pull-rebase-retry push pattern (same as the two precedent workflows), `DUNE_API_KEY` mapped from
  a GitHub Actions secret into the job env — never logged, never echoed.
- Backfill: growthepie and L2BEAT both expose history natively — a one-off backfill script pulls
  whatever depth each source retains (RFC-1 Stage 0 records the actual depth per chain, not
  assumed). Dune gets a **single bounded historical pull** at setup time (not per-day accumulation
  from zero) — exact lookback window sized against RFC-1's credit-cost finding, so backfill itself
  does not blow the monthly budget.
- Rejected alternative: forward-only accumulation for every source including growthepie/L2BEAT
  (mirroring how LiqTide's archive had to start from zero because it has no historical endpoint) —
  rejected because growthepie/L2BEAT DO have historical endpoints; not using them would mean weeks
  of empty charts for no reason, unlike the LiqTide precedent where there was no other option.

**ADR-4 — Floor/ramp analytics live in Python, validated on real data before trust.**
- 7d/28d EMA smoothing per (chain, metric) as the base transform.
- Floor/ramp rule (exact formula finalized during RFC-4 against real backfilled data, following the
  regime dashboard's ADR-1 lesson that constants tuned on synthetic data can be silently wrong): a
  candidate rule is "% off the rolling N-day low, sustained for M consecutive days" — same shape as
  the regime dashboard's `SUSTAINED_DAYS`/`ZSCORE_THRESHOLD` re-tune precedent. RFC-4 documents the
  chosen `N`/`M`/threshold with the same evidence-table discipline the regime plan's ADR-1
  Amendments used, not asserted from memory.
- A minimum-history gate falls out of the same mechanism: a chain with fewer than `N + M` days of
  history (Robinhood Chain, day one) gets its raw series only, no marker, and an explicit "not
  enough history yet" state — this is the natural consequence of the rule's own preconditions, not
  a separate special case to hand-code per chain.
- Rejected alternative: hardcoding a Robinhood-Chain-specific "launched 2026-07-01" exception in the
  analytics layer — rejected in favor of the general minimum-history gate above, which handles any
  future newly-added chain the same way without a per-chain branch.

**ADR-5 — Frontend: small-multiples raw panels + one normalized overlay, no raw cross-chain plot.**
- New route `web/app/onchain-activity/page.tsx`.
- Per-chain raw panels reuse the `ComponentPanel` pattern (regime dashboard precedent) — one panel
  per chain, three series (DAA/new-addresses/tx count), hover readout, drill-down.
- Exactly one normalized/indexed comparison overlay (all tracked chains on one shared scale,
  optional log toggle) — never raw counts plotted together on one axis (AC-13 is a hard UI
  constraint, enforced by construction: the comparison component's API input type only accepts
  normalized series, never raw).
- Floor/ramp markers rendered on both the raw panel (as an annotation) and the overlay (as the
  primary visual signal); absent entirely for any chain/metric below the minimum-history gate, with
  the "not enough history yet" note rendered instead.
- Rejected alternative: a single combined chart with a log-scale y-axis showing raw counts for all
  chains at once — rejected because log-scale does not solve AC-13's disclosure requirement (it
  still shows uncorrected raw counts, just compressed) and was explicitly ruled out by the SPEC's
  wording ("never plotted directly on the same shared axis without normalization").

**ADR-6 — Config: flat, user-editable JSON, validated with skip+warn.**
- `api/data/chains.json`: array of `{id, label, enabled, launch_date, metrics: {daa: {source,
  source_key}, new_addresses: {source, source_key}, tx_count: {source, source_key}}}` — same
  "option B" user-editable pattern as `narrative_category_map.json`, including its `_comment`
  self-documentation convention.
- Invalid entries (unknown source name, missing required field) are skipped with a logged warning;
  valid entries still load — mirrors `narrative_category_map.json`'s validation posture exactly.
- Rejected alternative: a Python dict constant (mirroring the pre-RFC-1 `COIN_CATEGORY_MAP`) —
  rejected outright per SPEC AC-11's explicit "config file, not code" requirement.

**ADR-7 — API: reuse the regime dashboard's response shape.**
- `GET /api/onchain/growth` returns `grid_dates` (shared date union across all requested
  chains/metrics for synced panels), per-series `gap_before` flags, per-series `max_gap_days`,
  gzip'd via the existing global `GZipMiddleware` — same contract shape as
  `GET /api/regime/components`, extended with per-series `source`, `method`, `redistributable`,
  and `history_start_date` fields (AC-2, AC-8, AC-9 map directly to these fields).
- Rejected alternative: a bespoke response shape — rejected because reusing the proven
  `grid_dates`/`gap_before` contract (already frontend-tested by the regime dashboard) removes an
  entire class of sync-bug risk this program would otherwise have to re-discover from scratch.

**ADR-8 — Every source defaults `redistributable=False` pending a terms check.**
- growthepie (CC BY 4.0 — likely `True` once formally confirmed at RFC-1 Stage 0, but starts
  `False` until the license text is actually read, not assumed from a license-name string), L2BEAT,
  and Dune (query *results* built on indexed public data — Dune's own terms on redistributing
  *derived* query outputs are unconfirmed) all start `redistributable=False`. Same posture as the
  Hyperliquid precedent in the narrative dashboard. A one-line flip per source once the user
  confirms terms, recorded as an Open Question below, never silently assumed permissive.

---

## High-Level Data Flow

```
  chains.json (user-editable config: 9 chains, per-metric source+key, launch_date)
       │ drives which (chain, metric) pairs get fetched
       ▼
  Per-chain-metric adapter dispatch (api/data/{growthepie,l2beat,dune}_adapter.py)
   - growthepie: daa + txcount, Ethereum/Base/Arbitrum/Optimism/Robinhood Chain
   - l2beat: tx/UOPS cross-check only (not written to primary series)
   - dune: daa + new_addresses + txcount, Solana/BNB/Tron/Polygon; new_addresses for ALL chains
   - every adapter: typed result, status ok|unavailable|stale, schema/health-checked, never raises
       │ one row per (chain, metric, day)
       ▼
  cache.py chain_growth_series_path/read/write  (append-only, deduped on date)
       │
       ├── nightly: .github/workflows/chain-growth-snapshot.yml (1 execution/chain/day on Dune,
       │            "Get Latest Query Result" for same-day re-reads; growthepie/L2BEAT re-fetched
       │            fresh each run — both are cheap/keyless)
       │
       ▼
  api/analytics/onchain/ (growth.py: EMA smoothing, floor/ramp rule with minimum-history gate;
                            comparison.py: cross-chain normalization/indexing)
       │
       ▼
  GET /api/onchain/growth  (grid_dates, gap_before, max_gap_days, per-series source/method/
                             redistributable/history_start_date — regime-dashboard response shape)
       │                                     │
       ▼                                     ▼
  Per-chain raw panel                 Normalized comparison overlay
  (hover/drill-down raw values,       (indexed scale, floor/ramp markers,
   floor/ramp annotation)              optional log, no raw cross-chain plot — AC-13)
       │                                     │
       └──────────────┬──────────────────────┘
                       ▼
         /onchain-activity DASHBOARD (NEW)
   Robinhood Chain flagged "launched 2026-07-01, limited history" until minimum-history gate clears

  Degraded/edge states shown ON the dashboard, never hidden:
   - one chain's source fails a day -> that chain/metric reads "unavailable" for that day; every
     other chain unaffected (Dune per-chain query isolation, ADR-2)
   - a chain below the minimum-history gate -> raw series shown, no floor/ramp marker, explicit note
   - a chain removed from chains.json -> stops appearing; archived history not deleted
   - two chains' different counting methods (Solana signers vs EVM senders) -> both labelled,
     never implied equivalent
```

---

## API Surface

**`GET /api/onchain/growth`** (new, `api/routers/onchain_activity.py`)

Query params: `chains` (optional, comma-separated chain ids, defaults to all `enabled` chains in
`chains.json`), `start`, `end` (optional ISO dates, defaults to full available history).

Response shape (Pydantic model in `api/models/onchain_activity.py`, following
`api/models/regime.py`'s `ComponentsResponse` pattern):

```
{
  "grid_dates": ["2026-06-01", "2026-06-02", ...],
  "chains": [
    {
      "id": "robinhood",
      "label": "Robinhood Chain",
      "launch_date": "2026-07-01",
      "limited_history": true,
      "history_start_date": "2026-07-01",
      "min_history_gate_met": false,
      "metrics": {
        "daa": {
          "source": "growthepie",
          "method": "unique from-addresses",
          "redistributable": false,
          "max_gap_days": 2,
          "points": [{"date": "...", "value": 1234.0, "gap_before": false}, ...]
        },
        "new_addresses": { "source": "dune", "method": "bounded-lookback first-seen", ... },
        "tx_count": { "source": "growthepie", "method": "raw tx count", ... }
      },
      "floor_ramp": { "state": "not-enough-history" | "floor" | "ramping" | "declining" | "neutral", "marker_date": null }
    },
    ...
  ],
  "comparison": {
    "normalization_method": "indexed-to-28d-baseline",
    "series": [ { "chain_id": "ethereum", "grid_dates": [...], "index_values": [...] }, ... ]
  }
}
```

**`GET /api/onchain/chains`** (new, thin wrapper) — returns the parsed/validated `chains.json`
contents (id, label, enabled, launch_date, per-metric source labels) for the frontend's chain-list
UI, without duplicating parsing logic between router and any future script.

Neither endpoint touches `/api/regime/*` or `/api/narrative/*` — fully additive, new router
mounted in `api/main.py` alongside the existing two.

---

## Acceptance Criteria

Carried verbatim (ids) from the locked SPEC; each is proven by the named RFC's exit gate — see
Verification Evidence for the full strategy/gate table.

| AC | Criterion (short) | Proven at | Gate status pending user confirmation |
|---|---|---|---|
| AC-1 | Every tracked chain shows all 3 metrics | RFC-4 (API) + RFC-5 (render) | code gate only |
| AC-2 | Every series labelled with source + counting method | RFC-2 (adapter) + RFC-5 (badge) | code gate only |
| AC-3 | Normalized comparison view makes floor/ramp visually obvious | RFC-5 | requires Agent-Probe visual judgment against real data (AC-14) |
| AC-4 | Floor/ramp marker gated on sufficient history, one consistent rule | RFC-4 (rule + gate) | requires real-data-validated constants (RFC-4 Stage 0) |
| AC-5 | Raw values available on hover/drill-down | RFC-5 | code gate only |
| AC-6 | Robinhood Chain visible day one, limited-history flag | RFC-1 (slug confirmed) + RFC-5 (render) | requires RFC-1 VERDICT |
| AC-7 | Missing/failed fetch always explicit, never silently wrong | RFC-3 | code gate only |
| AC-8 | History depth per chain disclosed | RFC-4 (`history_start_date` field) | code gate only |
| AC-9 | Every source tagged with redistribution flag | RFC-2 | requires RFC-1 terms confirmation for final flip |
| AC-10 | No provider API key ever reaches the client | RFC-2 (adapter contract) | code gate only |
| AC-11 | Chain list editable via config file, no code change | RFC-2 (`chains.json`) | code gate only |
| AC-12 | Single chain/source failure never takes down the rest | RFC-3 (isolation) + RFC-6 (E2E forced-failure spec) | code gate only |
| AC-13 | Comparison view never plots raw counts across chains unnormalized | RFC-4 (type-level) + RFC-5 (prop-type enforcement) | code gate only |
| AC-14 | Real-machine walkthrough confirms dashboard against live data | RFC-6 (handoff written) | **requires user execution on their own machine — this container cannot reach any candidate provider** |

Overall plan acceptance: all 14 ACs' code-level gates green (AC-1 through AC-13) AND AC-14's
user walkthrough completed and confirmed. Per this repo's own precedent (regime dashboard AC-11,
narrative dashboard AC-12), the plan may reach `🔨 CODE DONE` on the first 13 without AC-14, but
may not reach `✅ VERIFIED` until the user confirms AC-14.

---

## RFCs

Each RFC below has a mandatory **Stage 0 (present and STOP)**: read/confirm the prior RFC's
findings, do the specific research/probe this RFC requires, present the concrete plan for this
RFC's scope, and stop for explicit go-ahead before writing code. This mirrors the regime and
narrative dashboards' own RFC Stage-0 discipline exactly.

### RFC-1 — FEASIBILITY: Dune, growthepie, L2BEAT, and all source terms

**Type**: hard feasibility gate. RFC-2 through RFC-6 may not begin until RFC-1's VERDICT is
recorded and is not `NOT-VIABLE` for the sources it depends on. This is the `vc-feasibility-test`
playbook applied at plan time, per the INNOVATE decision's CAUTION flag.

**Why this RFC exists before any code**: two of the four candidate sources have specific, testable
unknowns that materially change ADR-1/ADR-2's design if wrong — this sandbox's egress proxy blocks
all of them, so the probe must run as exact, copy-pasteable commands for the user (mirrors the
regime dashboard's Farside Stage-0 precedent and the narrative dashboard's AC-12 real-provider
constraint).

**Stage 0 (present and STOP) — this IS RFC-1's entire content**:

1. **Dune account + API execution probe.**
   - Exact commands for the user to run against `https://api.dune.com/api/v1`:
     - `curl -H "X-Dune-API-Key: $DUNE_API_KEY" https://api.dune.com/api/v1/query/{a-known-public-query-id}/results` —
       confirm the free-tier key can read an existing public query's latest result (near-zero credit
       cost, sanity check the key/auth path works).
     - Submit one bounded per-chain candidate query (e.g. Solana daily unique signers, last 35
       days) via `POST /v1/query/{query_id}/execute`, poll `GET /v1/execution/{execution_id}/status`
       to a hard ceiling under 2 minutes, then `GET /v1/execution/{execution_id}/results`.
     - Record: exact credit cost charged for that one execution (Dune returns this in the
       execution/status response), execution wall-clock time, whether the small (free-tier) engine
       completed within 2 minutes for a chain with Solana's transaction volume.
   - Compute the **credit budget math**: (credit cost per chain-metric query) × (4 Dune-sourced
     chains × up to 4 metric-groups incl. new-addresses-for-all-9-chains) × 30 nights, plus the
     one-off historical backfill pull's estimated cost, against the 2,500/month free-tier ceiling.
     If this exceeds budget, RFC-1 records which metric/chain combination must drop to a lower
     cadence (e.g. weekly instead of nightly) or be cut, and that becomes a locked RFC-1 finding,
     not a later surprise.
   - Confirm the account predates 2026-07-21 (the user's stated constraint) by checking account
     creation date in the Dune UI/API if exposed; record as a finding either way.

2. **growthepie coverage probe.**
   - Exact command: `curl https://api.growthepie.xyz/v1/master.json` (keyless) — inspect the chain
     key list for Ethereum, Base, Arbitrum, Optimism, and specifically whether a `robinhood` (or
     similarly-named) key exists for Robinhood Chain. If absent, record it as absent — do not guess
     an alternate slug without confirming it resolves.
   - For each present chain key, probe `daa`/`txcount` history depth (how many days back does the
     time series actually go) — this becomes the recorded backfill depth per chain (ADR-3).
   - Read growthepie's actual license page (not just the CC BY 4.0 name) and record the exact
     attribution string required.

3. **L2BEAT activity API probe.**
   - Exact command(s) against L2BEAT's public activity endpoint(s) for the same L2 set — confirm
     shape (tx count vs UOPS), confirm it's genuinely keyless, and confirm/deny Robinhood Chain
     coverage as a second data point alongside growthepie's own finding.

4. **Terms pages — read, don't assume.**
   - growthepie license page, L2BEAT terms, Dune's terms of service section on API result usage and
     redistribution of derived data. Record exact findings per ADR-8's "read the text, don't assume
     from the license name" rule.

**VERDICT artifact**: `chain-growth-feasibility_FEASIBILITY_25-09-26.md` in this task folder,
following the `vc-feasibility-test` VERDICT format (hypothesis / verdict keyword / Resulting Design
Constraint: licenses / forbids / uncertain), covering all four probes above as sub-findings.

**Touchpoints**: none (research/probe only — no source files touched).
**Blast radius**: zero code; one new artifact file in the task folder.
**AC mapping**: unblocks AC-1, AC-6, AC-9 (source-dependent facts this RFC resolves).
**Test gates**: N/A (no code). Exit gate: VERDICT artifact written and is not NOT-VIABLE for the
sources ADR-1/ADR-2 depend on; if NOT-VIABLE for any one source, RFC-1 records the fallback (e.g.
drop Polygon from Dune coverage, or move it to growthepie if growthepie in fact covers it) as a
locked finding that ADR-1 is amended against, per this plan's Post-EXECUTE Amendments discipline.

**proven by**: chain-growth-dune-credit-budget-probe, chain-growth-growthepie-robinhood-slug-probe,
chain-growth-l2beat-coverage-probe, chain-growth-source-terms-confirmed — strategy: Agent-Probe
(user-run, real network, this container cannot execute any of it).

---

### RFC-2 — Config + adapters (growthepie, L2BEAT, Dune)

**Depends on**: RFC-1 VERDICT (locked chain-source mapping, confirmed credit budget, confirmed
Robinhood Chain slug or its absence).

**Stage 0**: re-read RFC-1's VERDICT in full; confirm the exact chain→source mapping this RFC will
implement (may differ from ADR-1's draft mapping if RFC-1 found a source gap); present the exact
`chains.json` schema and adapter function signatures; stop for go-ahead.

**Scope**:
- `api/data/chains.json` — config file per ADR-6, seeded with RFC-1's confirmed findings (not the
  plan's draft assumptions).
- `api/data/growthepie_adapter.py` — keyless HTTP client against `master.json` + per-chain
  daa/txcount endpoints; typed result (`status: ok|unavailable|stale`), never raises, schema-checked.
- `api/data/l2beat_adapter.py` — keyless HTTP client, cross-check-only result type (not written to
  the primary chain-growth series — used by RFC-4's analytics as a secondary sanity input only).
- `api/data/dune_adapter.py` — `DUNE_API_KEY` from env, execute/poll/fetch-results per ADR-2's
  discipline (isolated per-chain queries, bounded poll with hard ceiling, schema/health check,
  "Get Latest Query Result" reuse for same-day calls), `redistributable=False` default.
- `api/data/dune_queries/*.sql` — one SQL file per (chain, metric-group), query ids recorded in
  `chains.json`.
- `api/data/chain_growth_config.py` (or equivalent) — loader for `chains.json` with the same
  skip+warn validation posture as `narrative_category_map.json`'s reader.

**Touchpoints**: `api/data/{growthepie_adapter,l2beat_adapter,dune_adapter}.py` (new),
`api/data/chains.json` (new), `api/data/dune_queries/*.sql` (new), `api/data/chain_growth_config.py`
or equivalent loader (new). No existing file is modified in this RFC.

**Public Contracts**: none exposed yet (no router in this RFC) — adapter return types are internal
until RFC-4 wires them into the response model.

**Blast Radius**: new files only, `api/data/` — zero risk to `/regime`/`/narrative`/`/screener`.

**AC mapping**: AC-9 (redistributable flag per adapter), AC-10 (no key in adapter return values —
key stays server-side in the adapter's own HTTP call), AC-11 (config-driven chain list), AC-12
(per-chain query isolation baked into the adapter contract).

**Test gates**: `uv run --project api pytest api/tests/data/test_{growthepie,l2beat,dune}_adapter.py
-q` (Fully-Automated, synthetic-fixture HTTP responses, no network); one opt-in
`-m integration` test per adapter hitting the real endpoint (Hybrid — same pattern as
`etf_flows_adapter`'s integration marker).

**proven by**: chain-growth-adapter-contract-shape, chain-growth-redistribution-flag-per-source,
chain-growth-no-client-side-secrets (key never in adapter return value), chain-growth-dune-query-
isolation — strategy: Fully-Automated (contract shape, redistribution flag, no-secret-in-return) /
Hybrid (real endpoint integration test, opt-in).

---

### RFC-3 — Storage + nightly archive workflow + backfill

**Depends on**: RFC-2 (adapters exist and are individually testable).

**Stage 0**: confirm RFC-2's adapter return shapes; present the exact `cache.py` function
signatures and the workflow YAML; stop for go-ahead.

**Scope**:
- `cache.py` additions: `chain_growth_series_path(chain_id, metric)`,
  `read_chain_growth_series(chain_id, metric)`, `write_chain_growth_point(chain_id, metric, date,
  value, source, method, status)` — append-only, deduped-on-date, mirroring
  `write_liquidity_series`/`write_exchange_point` exactly.
- `.gitignore` carve-out: `api/data/cache/chain_growth/*` blanket-ignored except a tracked-archive
  subpath, same "parent must be per-entry excluded" mechanic as `liqtide/` and `narrative/`.
- `.github/workflows/chain-growth-snapshot.yml` — new, offset cron, own concurrency group,
  pull-rebase-retry push, `DUNE_API_KEY` secret mapped into job env.
- `api/scripts/snapshot_chain_growth.py` — orchestrates one run: for each enabled chain/metric in
  `chains.json`, call the right adapter, write via `cache.py`, log per-chain outcome (never let one
  chain's failure abort the whole run — matches AC-12).
- `api/scripts/backfill_chain_growth.py` — one-off: pulls growthepie/L2BEAT's native history depth
  (per RFC-1's recorded findings) and Dune's single bounded historical pull (sized against RFC-1's
  credit-budget finding).

**Touchpoints**: `api/data/cache.py` (additive functions only), `.gitignore` (additive carve-out
line), `.github/workflows/chain-growth-snapshot.yml` (new),
`api/scripts/{snapshot_chain_growth,backfill_chain_growth}.py` (new).

**Public Contracts**: `cache.py`'s new functions become the read contract RFC-4's analytics layer
depends on — signature-stable append-only reads.

**Blast Radius**: `cache.py` gets additive functions only (no existing function signature changes)
— zero risk to regime/narrative cache paths. Workflow file is entirely new and isolated by its own
concurrency group.

**AC mapping**: AC-7 (honest missing/failed states — a failed chain writes `status=unavailable`,
never a zero-filled row), AC-12 (single-chain failure isolation — the snapshot script's per-chain
try/except), AC-9 (redistributable flag persisted alongside each written point).

**Test gates**: `uv run --project api pytest api/tests/data/test_cache_chain_growth.py -q`
(Fully-Automated, isolated-cache-root fixture per `all-tests.md`'s "isolated_cache" convention);
`uv run --project api pytest api/tests/scripts/test_snapshot_chain_growth.py -q` (Fully-Automated,
synthetic multi-chain fixture proving one chain's failure doesn't abort the run — direct AC-12
regression test). Workflow YAML syntax check (`actionlint` if available, else manual review)
— Hybrid.

**proven by**: chain-growth-honest-missing-states, chain-growth-single-chain-failure-isolation,
chain-growth-append-only-dedup — strategy: Fully-Automated.

---

### RFC-4 — Floor/ramp + comparison analytics (real-data validated) + `GET /api/onchain/growth`

**Depends on**: RFC-3 (at least one real or backfilled series exists to validate constants against).

**Stage 0**: confirm RFC-3's backfilled data is available; present the exact floor/ramp formula
candidate and the evidence-table plan for validating it (mirrors the regime dashboard's ADR-1
re-tune discipline — constants are not trusted until checked against real data); present the
`GET /api/onchain/growth` Pydantic model; stop for go-ahead.

**Scope**:
- `api/analytics/onchain/growth.py` — EMA smoothing (7d/28d), the floor/ramp rule, minimum-history
  gate (derives naturally from the rule's own window requirements per ADR-4).
- `api/analytics/onchain/comparison.py` — cross-chain normalization/indexing (indexed-to-baseline,
  per ADR-7's `normalization_method` field), never emits raw counts on the comparison series (AC-13
  enforced at the type level: the comparison series dataclass has no raw-value field at all).
- **Real-data validation step**: run the floor/ramp rule against RFC-3's backfilled growthepie/L2BEAT
  history for at least Ethereum + one L2, using the same sweep-and-evidence-table method as the
  regime dashboard's `SUSTAINED_DAYS` re-tune (try 2-3 candidate window/threshold values, compare
  against visually-confirmable floor/ramp moments in the real data, record the chosen constants with
  the evidence table in this RFC's own ADR amendment, not asserted from memory).
- `api/routers/onchain_activity.py` — `GET /api/onchain/growth`, `GET /api/onchain/chains`.
- `api/models/onchain_activity.py` — Pydantic models per the API Surface section above.
- **Dtype discipline** (direct lesson from the narrative-dashboard RFC-6 `None`→`NaN` bug, see
  Standing Lesson table in `tests/all-tests.md`): any pandas column mixing `str`/`None` (e.g. a
  `source` or `method` label column with mixed availability) is built with `dtype=object`
  explicitly — a regression test enforces this for every mixed-type column this RFC introduces.

**Touchpoints**: `api/analytics/onchain/{growth,comparison}.py` (new),
`api/routers/onchain_activity.py` (new), `api/models/onchain_activity.py` (new), `api/main.py`
(additive: mount the new router alongside `regime`/`narrative`).

**Public Contracts**: `GET /api/onchain/growth`, `GET /api/onchain/chains` — new, additive, do not
touch `/api/regime/*` or `/api/narrative/*` route registration.

**Blast Radius**: one additive line in `api/main.py` (router mount) is the only touch to a shared
file; everything else is new files. Contract-snapshot test on `api/main.py`'s existing route list
confirms no existing route is altered (same discipline as the narrative dashboard's AC-1 byte-
identical contract test).

**AC mapping**: AC-1, AC-2, AC-4, AC-8, AC-13 (all analytics/response-shape ACs).

**Test gates**: `uv run --project api pytest api/tests/analytics/onchain/test_growth.py -q`
(Fully-Automated, includes the real-data-validated constants as regression fixtures — same pattern
as the regime dashboard's `leg_boundary.py` confirming backtest); `test_comparison.py -q`
(Fully-Automated, type-level AC-13 enforcement test); `test_onchain_activity_router.py -q`
(Fully-Automated, response-shape + `grid_dates`/`gap_before` sync test, contract-snapshot on
`api/main.py`'s route list to prove `/regime`/`/narrative` routes unchanged).

**proven by**: chain-growth-floor-ramp-marker-history-gate (Hybrid: rule logic Fully-Automated,
"does this look right on real data" is Agent-Probe), chain-growth-cross-chain-normalization-boundary
(Fully-Automated), chain-growth-existing-routes-unchanged (Fully-Automated).

---

### RFC-5 — `/onchain-activity` frontend: panels, normalized overlay, drill-down

**Depends on**: RFC-4's response model locked (may start once the Pydantic model is stable, in
parallel with RFC-4's real-data validation step if `vc-agent-strategy-compare` recommends it at
that phase boundary — see Strategy Recommendation below).

**Stage 0**: confirm RFC-4's exact response shape; present the component tree (page → per-chain
panel list → comparison overlay → drill-down); stop for go-ahead.

**Scope**:
- `web/app/onchain-activity/page.tsx` — new route.
- `web/components/onchain-activity/{OnchainDashboard,ChainPanel,ComparisonOverlay,DrillDown,
  SourceMethodBadge,LimitedHistoryFlag}.tsx` — `ChainPanel` reuses the `ComponentPanel` sync/hover
  pattern (`regime-chart-sync.ts`, `regime-line-segments.ts` as direct precedent for honest-gap
  line rendering).
- `web/lib/api/onchain-activity.ts`, `web/lib/types/onchain-activity.ts`.
- `web/lib/format-unavailable-reason.ts` — additive: new `UnavailableReason` variants for
  chain-growth-specific states (e.g. `dune-credit-exhausted`, `insufficient-history`) added to the
  existing shared union, not hand-rolled per component (narrative-dashboard precedent).

**Touchpoints**: `web/app/onchain-activity/page.tsx` (new), `web/components/onchain-activity/*`
(new), `web/lib/api/onchain-activity.ts` (new), `web/lib/types/onchain-activity.ts` (new),
`web/lib/format-unavailable-reason.ts` (additive union extension only).

**Public Contracts**: none — this is a pure consumer of RFC-4's API; no new backend surface.

**Blast Radius**: new files + one additive union extension in a shared frontend util. Zero risk to
existing routes/components.

**AC mapping**: AC-3, AC-5, AC-6, AC-13 (frontend enforcement — `ComparisonOverlay`'s prop type
only accepts normalized series, matching RFC-4's type-level enforcement).

**Test gates**: `pnpm --filter web test` component tests for `ChainPanel`, `ComparisonOverlay`,
`LimitedHistoryFlag` (Fully-Automated, injected-fetcher fixtures per the regime/narrative precedent);
`pnpm --filter web exec tsc --noEmit` (Fully-Automated).

**proven by**: chain-growth-per-chain-three-metrics (frontend render), chain-growth-source-method-
labelling, chain-growth-normalized-overlay-view (Agent-Probe — visual judgment), chain-growth-
drilldown-raw-values (Agent-Probe), chain-growth-robinhood-chain-launch-flag — strategy: mixed per
AC table below.

---

### RFC-6 — Tests, seeded E2E, context docs update, AC-14 real-cache walkthrough handoff

**Depends on**: RFC-4 + RFC-5 code-complete.

**Stage 0**: confirm RFC-4/RFC-5 are both green on their own gates; present the E2E fixture-seeding
plan (`seed_e2e_cache.py::build_chain_growth_fixture`/`seed_chain_growth`, following the exact
`build_narrative_fixture` shape — write every source's history through the real `cache.write_*`
functions, keyed exactly as production keys them); stop for go-ahead.

**Scope**:
- `api/scripts/seed_e2e_cache.py` — additive `build_chain_growth_fixture`/`seed_chain_growth`
  functions (same isolated `SCREENER_CACHE_ROOT`-style pattern as the existing builders).
- `web/e2e/onchain-activity.spec.ts` — new Playwright spec: per-chain panel render, comparison
  overlay render, drill-down raw-value check, Robinhood-Chain-limited-history-flag render, a
  forced-single-source-failure fixture proving AC-12 at the UI layer.
- Full-suite regression run: `uv run --project api pytest api/ -q`, `pnpm --filter web test`,
  `pnpm --filter web exec tsc --noEmit`, `cd web && pnpm test:e2e` (with
  `PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome` in this container),
  run twice per the repo's existing "run twice" discipline for E2E confirmation.
- **Context docs update** (per this task's instructions): add a new provider-category section to
  `process/context/data-sources/all-data-sources.md` for chain-activity sources (growthepie, L2BEAT,
  Dune — mirroring how narrative/regime sources were documented), and add `onchain-activity` to
  `process/context/all-context.md`'s routing table (Task Routing Table row + Current Context state
  update per that file's own Context Update Protocol).
- **AC-14 handoff**: this RFC does NOT attempt AC-14 in-sandbox (this container cannot reach any of
  the four providers). It writes the exact user-PC walkthrough steps into Resume and Execution
  Handoff below, mirroring the regime dashboard's AC-11 and narrative dashboard's AC-12 precedent
  exactly (including forcing one source to fail — e.g. an intentionally-revoked/missing
  `DUNE_API_KEY` — to confirm the "visibly unavailable, not silently missing" half of AC-14).

**Touchpoints**: `api/scripts/seed_e2e_cache.py` (additive), `web/e2e/onchain-activity.spec.ts`
(new), `process/context/data-sources/all-data-sources.md` (additive section),
`process/context/all-context.md` (routing table update).

**Public Contracts**: none — test/context artifacts only.

**Blast Radius**: additive-only across all touched files; zero behavior change to existing routes.

**AC mapping**: AC-14 (handoff written, execution deferred to user), plus a full regression pass
proving AC-1 through AC-13 hold together end-to-end against the seeded fixture.

**Test gates**: as listed above — Fully-Automated for pytest/vitest/tsc, Hybrid for the seeded
Playwright E2E (requires the container chromium-path workaround, none-the-less deterministic once
running), Agent-Probe deferred to the user for AC-14's live-provider portion.

**proven by**: chain-growth-real-cache-user-walkthrough — strategy: Agent-Probe (user, real
machine, per SPEC).

---

## Strategy Recommendation (per RFC, from `vc-agent-strategy-compare`)

| RFC | Signals present | Score | Recommended strategy |
|---|---|---|---|
| RFC-1 | S5 (user explicitly needs depth — live probe), S6 (none — no code) | 1/7 | Sequential — single research/probe pass, user-executed |
| RFC-2 | S1 (multi-package? no, single `api/data/`), S3 (3 distinct adapters) | 2/7 | Parallel subagents — one per adapter (growthepie/L2BEAT/Dune), independent files, no cross-talk needed |
| RFC-3 | S6 (new scheduled workflow touches secrets), S7 (5+ files: cache.py, gitignore, workflow, 2 scripts) | 2/7 | Sequential — cache.py additions and the workflow are interdependent, safer as one pass |
| RFC-4 | S2 (new API surface), S6 (real-data-validated constants, high-risk-adjacent), S7 (5 files) | 3/7 | Sequential — analytics + API + real-data validation are tightly coupled, one agent should own the full thread |
| RFC-5 | S7 (6+ new component files) | 1/7 | Parallel subagents — panel components are independent of each other once the API contract is locked |
| RFC-6 | S6 (context docs + E2E + real-cache handoff) | 2/7 | Sequential — the handoff narrative needs one coherent author |

Full 4-option comparison (including agent-team) is re-run at each actual phase-END per the standard
protocol; this table is the PLAN-time estimate, not a substitute for the live invocation.

**Whole-plan structure recommendation**: kept as ONE plan document with 6 internal RFCs, not split
into separate phase-program plan files. Rationale: `vc-agent-strategy-compare`'s phase-program
threshold (3+ *phases each needing independent validate gates spanning many packages*) technically
applies (6 RFCs), but every RFC here shares one feature folder, one blast radius class
(`api/data/`, `api/analytics/onchain/`, one router, one frontend route), and — critically — RFC-1
is a hard sequential gate that makes RFC-2-6 genuinely dependent, not parallelizable phases needing
separate coordination machinery. The regime and narrative dashboards (this program's own structural
precedents) both used exactly this shape (one plan, N sequential/semi-parallel RFCs) rather than a
full umbrella+phase-plan-set program, and their scope (6 RFCs each, similar file count) is a closer
match than the phase-program threshold examples. Splitting into a full umbrella program would add
agent-team coordination overhead (blast-radius registry, per-phase plan files) without a
corresponding coordination need, since RFC-2 through RFC-6 form a single dependency chain, not
independent concurrent workstreams.

---

## Touchpoints

**New files only** (no existing production file is modified except two additive single-line
touches, called out explicitly):
- `api/data/chains.json`, `api/data/dune_queries/*.sql`, `api/data/chain_growth_config.py`
- `api/data/{growthepie_adapter,l2beat_adapter,dune_adapter}.py`
- `api/data/cache.py` — **additive functions only**, no existing function signature changed
- `.gitignore` — **additive carve-out line only**
- `.github/workflows/chain-growth-snapshot.yml`
- `api/scripts/{snapshot_chain_growth,backfill_chain_growth}.py`
- `api/scripts/seed_e2e_cache.py` — **additive functions only**
- `api/analytics/onchain/{growth,comparison}.py`
- `api/routers/onchain_activity.py`, `api/models/onchain_activity.py`
- `api/main.py` — **additive router-mount line only**
- `web/app/onchain-activity/page.tsx`
- `web/components/onchain-activity/*.tsx`
- `web/lib/api/onchain-activity.ts`, `web/lib/types/onchain-activity.ts`
- `web/lib/format-unavailable-reason.ts` — **additive union extension only**
- `web/e2e/onchain-activity.spec.ts`
- `process/context/data-sources/all-data-sources.md`, `process/context/all-context.md` — additive
  sections/rows only

## Public Contracts

- `GET /api/onchain/growth`, `GET /api/onchain/chains` — new, additive.
- `cache.py`'s new `chain_growth_*` functions — new read/write contract for RFC-4+ to depend on.
- No existing public contract (`/api/regime/*`, `/api/narrative/*`, `/api/screener/*`) changes in
  any way — enforced by RFC-4's route-list contract-snapshot test.

## Blast Radius

- Class: **new feature, additive-only touches to shared files** (2 files get single-line additions:
  `api/main.py` router mount, `.gitignore` carve-out; `cache.py`, `seed_e2e_cache.py`,
  `format-unavailable-reason.ts` get additive functions/union-members only).
- Risk class per orchestration.md's High-Risk Classes list: **none of auth/billing/schema-migration/
  public-API-breaking-change/deploy-runtime apply** — this is a new read-only dashboard with a new
  additive API surface. The nearest risk-adjacent item is the new GitHub Actions secret
  (`DUNE_API_KEY`) — handled per ADR-3's "never logged, never echoed" rule, same posture as the
  existing `REDDIT_CLIENT_SECRET` secret already in the repo's threat model.
- Estimated file count: ~28 new files, 5 files with single-line/additive touches. No destructive or
  irreversible operation anywhere in this plan.

---

## Ops Runbook

- **Secrets**: `DUNE_API_KEY` — user creates their own free Dune account/key (pre-2026-07-21
  account per the locked constraint, confirmed at RFC-1 Stage 0), sets it as a GitHub Actions
  repository secret (`Settings → Secrets and variables → Actions`) and locally in `.env` (not
  committed, matching `.env.example`'s existing pattern) for local dev/testing.
- **Scheduled job**: `chain-growth-snapshot.yml`, cron `0 22 * * *` (UTC) — offset from
  `liqtide-snapshot.yml` (23:30) and `narrative-snapshot.yml` (23:00) by at least 60/30 minutes to
  avoid runner contention; exact offset confirmed at RFC-3 Stage 0 once the actual runtime of a
  chain-growth run is known.
- **Credit monitoring**: RFC-1's computed credit budget is the standing reference; if actual usage
  drifts materially from the RFC-1 estimate (visible in Dune's dashboard), that's a signal to revisit
  ADR-2's per-chain cadence, not a silent problem to ignore.
- **Adding a chain**: edit `api/data/chains.json` only — no deploy needed for a chain whose source
  is already one of the three adapters; a genuinely new source (e.g. a 5th provider) is a new
  RESEARCH→PLAN cycle, not a config edit.
- **Rollback**: every touch in this plan is additive or new-file; reverting the entire feature is a
  revert of the RFC's commits with zero risk to existing dashboards, since no existing route,
  function signature, or shared component prop changed.

---

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| chain-growth-dune-credit-budget-probe | Agent-Probe (user, RFC-1) | AC-1, AC-9 (source feasibility) |
| chain-growth-growthepie-robinhood-slug-probe | Agent-Probe (user, RFC-1) | AC-6 |
| chain-growth-l2beat-coverage-probe | Agent-Probe (user, RFC-1) | AC-1 (cross-check availability) |
| chain-growth-source-terms-confirmed | Agent-Probe (user, RFC-1) | AC-9 |
| chain-growth-adapter-contract-shape | Fully-Automated (RFC-2) | AC-1, AC-2 |
| chain-growth-redistribution-flag-per-source | Fully-Automated (RFC-2) | AC-9 |
| chain-growth-no-client-side-secrets | Fully-Automated (RFC-2) | AC-10 |
| chain-growth-dune-query-isolation | Fully-Automated (RFC-2) | AC-12 |
| chain-growth-honest-missing-states | Fully-Automated (RFC-3) | AC-7 |
| chain-growth-single-chain-failure-isolation | Fully-Automated (RFC-3) | AC-12 |
| chain-growth-append-only-dedup | Fully-Automated (RFC-3) | AC-7, AC-8 |
| chain-growth-floor-ramp-marker-history-gate | Hybrid (RFC-4) | AC-4 |
| chain-growth-cross-chain-normalization-boundary | Fully-Automated (RFC-4) | AC-13 |
| chain-growth-existing-routes-unchanged | Fully-Automated (RFC-4) | (regression — protects `/regime`/`/narrative`/`/screener`) |
| chain-growth-per-chain-three-metrics | Fully-Automated (RFC-5) | AC-1 |
| chain-growth-source-method-labelling | Fully-Automated (RFC-5) | AC-2 |
| chain-growth-normalized-overlay-view | Agent-Probe (RFC-5) | AC-3 |
| chain-growth-drilldown-raw-values | Agent-Probe (RFC-5) | AC-5 |
| chain-growth-robinhood-chain-launch-flag | Fully-Automated (RFC-5) | AC-6 |
| chain-growth-config-driven-chain-list | Fully-Automated (RFC-2) | AC-11 |
| chain-growth-real-cache-user-walkthrough | Agent-Probe (RFC-6, user) | AC-14 |

## Test Infra Improvement Notes

(none identified yet — RFC-1's probe may surface a need for a Dune-specific sandbox test double if
the free-tier account cannot be safely exercised repeatedly in CI; revisit at RFC-2 Stage 0 if so)

---

## Validate Contract

(placeholder — vc-validate-agent writes this section before EXECUTE)

---

## Resume and Execution Handoff

1. **Selected plan file path**: `process/features/onchain-activity/active/chain-growth_25-09-26/chain-growth_PLAN_25-09-26.md`
2. **Last completed phase or step**: PLAN written (this document); no RFC started.
3. **Validate-contract status**: pending — VALIDATE has not run for this plan.
4. **Supporting context files loaded**: `process/context/all-context.md`,
   `process/context/data-sources/all-data-sources.md`, `process/context/tests/all-tests.md`,
   `process/context/planning/all-planning.md`, `process/features/onchain-activity/_GUIDE.md`,
   the locked SPEC, and the two structural precedent plans (regime, narrative dashboards).
5. **Next step for a fresh agent picking up mid-execution**: run VALIDATE on this plan, then start
   RFC-1 Stage 0 — the user must run the RFC-1 probe commands themselves (this container's egress
   proxy blocks Dune/growthepie/L2BEAT); do not attempt to fabricate or assume RFC-1's findings.
   **RFC-1 user-PC walkthrough steps** (to be run before or during RFC-1):
   - Create/confirm a Dune account predating 2026-07-21; generate a free-tier API key.
   - Run the exact `curl` commands in RFC-1 Stage 0 above against `api.dune.com`, `api.growthepie.xyz`,
     and L2BEAT's activity endpoint.
   - Record: Dune credit cost per query, execution time, small-engine 2-min timeout outcome for a
     Solana-scale query; growthepie's chain-key list (esp. Robinhood Chain) and history depth per
     chain; L2BEAT's shape and Robinhood Chain coverage; the exact license/terms text for all three.
   - Return findings to the agent continuing this plan as the RFC-1 VERDICT artifact's source
     material.
   **AC-14 walkthrough (deferred to RFC-6 completion)**: once RFC-6 is code-complete, on a machine
   with real network access: set `DUNE_API_KEY` and confirm `/onchain-activity` renders all nine
   chains' three metrics; confirm the normalized overlay shows a sensible floor/ramp read on at
   least one chain with sufficient history; confirm Robinhood Chain shows its limited-history flag;
   temporarily unset/revoke `DUNE_API_KEY` and confirm the Dune-sourced chains show a visible
   "unavailable" state (not silently missing) while growthepie/L2BEAT-sourced chains keep rendering
   normally (this is the concrete AC-12 + AC-14 joint proof); confirm hover/drill-down shows correct
   raw numbers.

---

Say **ENTER VALIDATE MODE** when ready to proceed to plan validation (required before implementation).
