---
slug: chain-growth
date: 2026-09-25
verdict: NOT-VIABLE
originating-phase: innovate
---

# chain-growth RFC-1 — Feasibility VERDICT

**TL;DR** — The full design (Dune for Solana/BNB/Tron/Polygon + new-addresses everywhere) is
**NOT-VIABLE**: the Dune account cannot run any query and the user will not pay. The **locked
fallback** (plan P2 / E4) applies verbatim. growthepie is **VIABLE** and also covers Polygon
(`polygon_pos`), so the unavailable set shrinks to Solana, BNB and Tron. L2BEAT is **VIABLE** as a
cross-check for Base, Arbitrum and Robinhood; Optimism's L2BEAT shape is unresolved. `new_addresses`
is dropped for all chains.

Evidence source: `chain-growth-probe-result_25-09-26.json` (commit `93ea023`, run
2026-09-25T19:49:03Z on the user's PC, `overall: FAIL`), plus the user's Dune MCP test and the
user's own reading of the three terms pages (2026-09-25). No API key appears in this file (E3).

## Hypothesis

The full ADR-1/ADR-2 source design is feasible on free tiers: (a) Dune can run 17 isolated queries
per night within 2,500 credits/month and the 2-minute small engine; (b) growthepie serves `daa` and
`txcount` for Ethereum, Base, Arbitrum, Optimism and Robinhood Chain with usable history; (c) L2BEAT
has a keyless activity endpoint usable as a tx cross-check for the same L2 set; (d) each source's
terms allow the planned use.

Per-source sub-hypotheses:

| Source | Sub-hypothesis |
|---|---|
| Dune | Free account can execute ad-hoc/saved queries via API within budget and timeout |
| growthepie | Keyless master list covers the target chains + `daa`/`txcount`, with retrievable history |
| L2BEAT | Keyless per-project activity endpoint exists and returns daily tx counts |
| Terms | Reuse terms are known and recorded per source (ADR-8) |

## Mechanism Under Test

- Dune REST API: `POST /api/v1/sql/execute`, execution status/results, usage endpoint.
- growthepie: `GET https://api.growthepie.xyz/v1/master.json`, `GET /v1/fundamentals_full.json`.
- L2BEAT: `GET https://l2beat.com/api/scaling/activity` and `.../activity/{project}` for
  base, arbitrum, optimism, robinhood.
- Terms pages for all three (manual read by the user).

## Probe Family

4 — External API shape capture.

## Probe Cost Class

`needs-live-provider`. Gate met: the user ran the probe on their own PC with their own key
(explicit opt-in). Dune spend was capped at 50 credits by the script; actual spend **0 credits over
0 successful executions** (`dune_credits_spent`: PASS, `spent: 0.0`).

## Probe Method

- `uv run --project api python -m api.scripts.probe_chain_sources` (user PC, key read from an
  interactive prompt, never written to disk). Output: `chain-growth-probe-result_25-09-26.json`.
- User test of Dune's MCP server with `SELECT 1`.
- User read of growthepie, L2BEAT and Dune terms pages.

## Evidence Captured

### Dune — FAIL (all executes refused)

| Probe item | Status | Detail (from JSON) |
|---|---|---|
| `dune_execute` (`SELECT 1`) | FAIL | HTTP 402 "This api request would exceed your configured datapoint limit per billing cycle…" |
| `dune_solana_scale_35d` | FAIL | same HTTP 402 |
| `dune_coverage_{solana,bnb,tron,polygon,robinhood}` | FAIL | same HTTP 402 on all five |
| `dune_usage` | UNKNOWN | usage endpoint HTTP 405 |
| `dune_budget_math` | UNKNOWN | credit cost per query not reported (no execution succeeded) |
| `dune_credits_spent` | PASS | 0.0 credits, 0 executions |

Additional user evidence: Dune MCP `SELECT 1` also failed; the account is read-only and cannot run
queries. The user will not pay for a plan. No path to any Dune data exists.

### growthepie — master PASS, history depth UNKNOWN

| Probe item | Status | Detail |
|---|---|---|
| `growthepie_master` | PASS | host `https://api.growthepie.xyz`; chain keys include `ethereum`, `base`, `arbitrum`, `optimism`, `robinhood`, **`polygon_pos`** (30 keys total); metric keys include `daa`, `txcount` (16 total); launch dates: ethereum 2015-07-30, arbitrum 2021-08-31, optimism 2021-12-16, base 2023-08-09, robinhood 2026-07-01 |
| `growthepie_history_depth` | UNKNOWN | `GET /v1/fundamentals_full.json` → HTTP 403. Wrong endpoint for this question; depth is unmeasured |

Robinhood Chain slug is confirmed as `robinhood` (the only match; no guessed slug).

### L2BEAT — endpoint PASS, 3 of 4 projects PASS

| Probe item | Status | Detail |
|---|---|---|
| `l2beat_endpoint` | PASS | `https://l2beat.com/api/scaling/activity`, keyless |
| `l2beat_activity_base` | PASS | 30 points, 2026-08-26..2026-09-24, types `timestamp`/`count`/`uopsCount` |
| `l2beat_activity_arbitrum` | PASS | same shape, 30 points |
| `l2beat_activity_robinhood` | PASS | same shape, 30 points |
| `l2beat_activity_optimism` | FAIL | "no chart.types / chart.data in L2BEAT response" — shape differs or slug is wrong |

30 points is the default window, so history needs an explicit range parameter.

### Terms (user-read, 2026-09-25)

| Source | Finding | `redistributable` |
|---|---|---|
| growthepie | CC BY 4.0; required attribution: "Source: growthepie, https://www.growthepie.com." | `True` (with attribution) |
| L2BEAT | No data-reuse licence | `False` |
| Dune | Personal/internal use only | `False` (source unused) |

The user notes all current use is personal.

## Verdict

NOT-VIABLE

This keyword applies to the **full design** hypothesis (because Dune is NOT-VIABLE). Per source:

| Source | Verdict | Why |
|---|---|---|
| Dune | **NOT-VIABLE** | Every execute returned HTTP 402; MCP `SELECT 1` failed; account is read-only; user will not pay. Meets the plan's fallback trigger ("auth fails outright … can't cover even a reduced cadence"). |
| growthepie | **VIABLE** | All target chains plus `polygon_pos` present, `daa`/`txcount` present, keyless, CC BY 4.0. History depth still to measure on the right endpoint (known gap, not a blocker). |
| L2BEAT | **VIABLE** (cross-check only) for base, arbitrum, robinhood | Keyless, tx `count` + `uopsCount`. Optimism unresolved (shape/slug). Not a primary source, so this does not block RFC-2 (E5 logic applies per project). |

## Resulting Design Constraint

The **locked fallback** (plan RFC-1 Stage 0 item 1, P2 / E4) applies, verbatim:

> ship only the 5 growthepie/L2BEAT-covered chains (Ethereum, Base, Arbitrum, Optimism, Robinhood
> Chain) with `daa`/`tx_count`; Solana, BNB Chain, Tron, and Polygon render an explicit "source
> unavailable" state per AC-7 rather than being silently dropped from `chains.json`;
> `new_addresses` is dropped for ALL chains (no fallback source exposes it) until a replacement is
> researched in a follow-up plan. This is the locked fallback — RFC-1 records whichever of "full
> design" or "this fallback" applies, it does not invent a third option.

**Finding that improves the fallback (not a new option):** growthepie's master list contains
`polygon_pos`, so Polygon moves from "source unavailable" to live via growthepie. This is the case
the plan's RFC-1 exit gate anticipated ("move it to growthepie if growthepie in fact covers it").
The live set becomes **Ethereum, Base, Arbitrum, Optimism, Polygon, Robinhood Chain**; the
unavailable set shrinks to **Solana, BNB Chain, Tron**. Scope, metrics and shape are otherwise the
fallback's exactly.

- **What this licenses:** growthepie as the sole primary source for `daa` and `tx_count` on
  ethereum, base, arbitrum, optimism, polygon_pos and robinhood, keyless, `redistributable=True`
  with the exact attribution "Source: growthepie, https://www.growthepie.com." rendered page-level
  (E6: this matches the ADR-1 draft wording). L2BEAT's keyless
  `https://l2beat.com/api/scaling/activity/{project}` as a tx cross-check for base, arbitrum and
  robinhood, `redistributable=False`. Robinhood Chain slug `robinhood` on both sources.
- **What this forbids:** any Dune adapter, Dune SQL file, Dune query id, or `DUNE_API_KEY` secret;
  `new_addresses` for any chain; dropping Solana/BNB/Tron from `chains.json` (they stay, explicitly
  unavailable); treating L2BEAT as a primary series or redistributing its data; guessed slugs;
  `fundamentals_full.json` as the history endpoint (403).
- **What remains uncertain (known-gap):** (1) growthepie per-chain history depth — must be measured
  on the per-metric endpoint in RFC-2 Stage 0 / backfill; (2) the L2BEAT range parameter for full
  history (default returns 30 points); (3) Optimism on L2BEAT — likely a different project slug
  (L2BEAT lists OP Mainnet as `op-mainnet`), unconfirmed; (4) growthepie launch date for
  `polygon_pos` was not printed by the probe; (5) Dune account creation date was not recorded (moot
  now). None blocks RFC-2.

VC-FEASIBILITY-VERDICT-READY: NOT-VIABLE — /home/user/psychic-train/process/features/onchain-activity/completed/chain-growth_25-09-26/chain-growth-feasibility_FEASIBILITY_25-09-26.md
