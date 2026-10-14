---
name: spec:market-framework
description: "Market Intelligence Framework: five owner-confirmed classifications (LTF, MTF, HTF, CYCLE, PERP) on the main dashboard, with optional system suggestions, rule-based weights, and an append-only reproducible history"
date: 13-10-26
feature: general-plans
metadata:
  node_type: memory
  type: spec
---

[MODE: SPEC]

# Market Intelligence Framework - SPEC

**TL;DR:** The dashboard (route /) gets a compact strip of five classifications: LTF, MTF, HTF (Bullish/Neutral/Bearish), CYCLE (Bull/Bear) and PERP POSITIONING (Aggressive/Delta Neutral/Passive). You choose the inputs, you make every reading, and only your confirmed readings feed transparent weighted rules. Suggestions appear only where you enable them; a changed suggestion is flagged pending and never moves a classification. Conflicts and missing data are explicit states. History is append-only. PERP shows "insufficient data" (no source exists). Global M2, TOTAL and ETH/BTC are missing and show "unavailable" until the companion SPEC delivers them.

Status: PAUSED by owner 14-10-26 until the owner decides which input fits which timeframe; do not move to INNOVATE.

**Status:** Draft. Facts: VERIFIED (checked in repo) or FROM-RESEARCH.

## 1. Locked decisions (owner answers 13-10-26)

| ID | Decision |
|---|---|
| L1 | **Verdict-rule exception.** The repo rule (north-star.md, D-2, realignment and baskets SPECs) forbids system-made bullish/bearish output. Owner overrules it for this framework only: "system suggestions only on data i approve, i do every reading and it overrides on where there's a suggestions label". **Planner interpretation, owner to confirm:** (a) suggestions exist only for inputs the owner enabled them on; others show numbers only. (b) The owner makes every reading; agreeing is an explicit action. (c) The owner's reading wins; the suggestion is secondary; a changed suggestion is pending while the last accepted reading stays. (d) Applies to route / only; other pages stay label-free, enforced by a guard test. (e) No confidence scores, probabilities or "signal agreement"; conflict and missing data are explicit states; weights are owner-set. Must be removable cleanly. Text: Appendix A. |
| L2 | **PERP: structure now, data later.** No funding rate, open interest, long/short ratio, liquidation or basis data exists (VERIFIED: grep of api/ source found none). Define structure, candidate inputs and an "insufficient data" state, shown and recorded until a source is integrated. Probing Hyperliquid is a later step. |
| L3 | **Timeframes (no intraday).** HTF = yearly/quarterly/monthly (liquidity, halving cycle, TOTAL, secular expansions). MTF = weekly (BTC.D, ETH/BTC, SSR). LTF = daily (value areas, capitulation flushes, deep discount). |
| L4 | **Scope (owner to confirm):** crypto market, BTC primary, TOTAL/BTC.D/ETH/BTC as market-wide inputs. |
| L5 | **Companion SPEC** data-integration-tooling_13-10-26 covers data tooling. Missing data shows "input unavailable until integrated"; the framework works with whatever exists. |

## 2. User stories

- **US-1** Discover existing datasets and indicators and activate the ones I choose.
- **US-2** For inputs with suggestions on, see a suggested reading and agree or override; only my confirmed reading counts.
- **US-3** When a suggestion changes, keep my last accepted reading and see the new one flagged as pending.
- **US-4** Configure each input independently: contribute on/off, weight, thresholds, suggestions on/off.
- **US-5** Get LTF, MTF, HTF, CYCLE computed independently, with explicit conflicted / insufficient-data / uncertain states.
- **US-6** PERP has its own logic, never concludes from one input (rising open interest alone is not positioning), and says "insufficient data" without data.
- **US-7** See a compact overview on /, an expandable detail, "why" for each result and "what changed".
- **US-8** Keep an append-only history of suggestions, approvals, overrides, input values, timestamps, results, configuration.
- **US-9** Compare suggestions with my readings and evaluate across past conditions.
- **US-10** Changing configuration never rewrites the past; versions are identifiable.
- **US-11** Add new inputs later without redesign.

## 3. Input catalogue

Status: EXISTS, DERIVABLE (from project data), MISSING (needs integration), NO-DATA (no source chosen). Bar = bar size needed.

| Group | Candidate input | Status | Bar |
|---|---|---|---|
| HTF | Global M2 money supply | MISSING | monthly |
| HTF | Central bank balance sheets | PARTIAL: Fed WALCL (FRED); others MISSING | weekly/monthly |
| HTF | TOTAL crypto market cap | MISSING | monthly/quarterly |
| HTF | Secular bull/bear expansion (BTC structure) | DERIVABLE from daily BTC (about 6 years of daily BTC only) | monthly/quarterly/yearly |
| CYCLE | Position in 4-year halving cycle | DERIVABLE (halving dates public; confirm) (only about 1.5 cycles of price history) | monthly |
| CYCLE | BTC trend vs long-run structure | DERIVABLE from daily BTC | monthly |
| MTF | Bitcoin Dominance (BTC.D) | EXISTS (LiqTide, from about 2024-09) | weekly |
| MTF | ETH/BTC ratio | DERIVABLE if ETH daily bars cached (derived) | weekly |
| MTF | Stablecoin Supply Ratio | stablecoins EXISTS (DefiLlama); BTC supply DERIVABLE (confirm) (derived/estimated) | weekly |
| LTF | Structural value areas (accumulation floors) | DERIVABLE from daily BTC | daily |
| LTF | Capitulation / liquidation flush events | NO-DATA; price-flush proxy DERIVABLE (proxy) | daily |
| LTF | Deep discount level for DCA | DERIVABLE  | daily |
| PERP | Funding rate, open interest, long/short ratio, liquidations, basis | NO-DATA (structure only) | any |

Monthly, quarterly and yearly bars do not exist; they can only be built from daily bars (FROM-RESEARCH: about 75 / 25 / 6 bars).

## 4. Flow

```
 dataset found -> owner activates input -> suggestions on? -yes-> system suggests
      no: numbers only                          owner agrees OR overrides (explicit)
                                                         |
 new data -> suggestion changed? -yes-> PENDING flag; accepted reading stays
                                                         |
 accepted readings x weights/thresholds -> rules -> LTF / MTF / HTF / CYCLE / PERP
   result: value | conflicted | insufficient data | uncertain
 every step appended to history with its configuration version
```

## 5. Acceptance criteria

Each criterion names its test and strategy (FA Fully-Automated, HY Hybrid). Synthetic fixtures only.

- **AC-1** Only owner-accepted readings affect a classification. Test: suggestion present, not accepted, no change. FA.
- **AC-2** A changed suggestion leaves the classification and last accepted reading untouched and shows a pending flag until the owner accepts or overrides. Test: suggestion-change scenario. FA.
- **AC-3** Agreeing is an explicit action; nothing is auto-accepted, including after restart or data refresh. Test: restart scenario. FA.
- **AC-4** Suggestions appear only for inputs with suggestions enabled; others show numbers only. Test: toggle. FA.
- **AC-5** Each input has independent contribute, weight, threshold and suggestion settings; changing one does not change another. Test: isolation. FA.
- **AC-6** The five classifications are computed independently; a change to an HTF input does not alter LTF. Test: independence. FA.
- **AC-7** Classifications can show explicit states (conflicted, insufficient data, uncertain) with a rule breakdown. No confidence or probability number appears. Test: state scenarios, UI text check. FA.
- **AC-8** PERP outputs Aggressive, Delta Neutral or Passive only through its own rules, never from one input, and shows "insufficient data" while no PERP data exists. Test: no-data, single-input. FA.
- **AC-9** Every history record is append-only: suggestions, changes, approvals, overrides, input values with timestamps, results and the configuration used. Test: attempted edit fails. FA.
- **AC-10** A configuration change creates a new identifiable version; all earlier records still show the version they used and their original results. Test: change config, reload. FA.
- **AC-11** Monthly, quarterly and yearly bars use closed bars only; the current bar is shown as forming and not used in rules (proposed default, OQ-2). Test: bar-boundary fixtures. FA.
- **AC-12** Missing or too-short history for an input yields "insufficient data" for that input, never a guessed value. Test: short series. FA.
- **AC-13** Every input shows source, as-of time and staleness; derived values (SSR, ETH/BTC, halving position) are labelled derived or estimated. Test: detail view. FA.
- **AC-14** A guard test fails if bullish/bearish/aggressive/passive-style labels appear outside the framework module and dashboard components. Test: guard test over all other pages. FA.
- **AC-15** Route / shows the compact five-item overview; an expandable detail lists inputs, suggestions, pending items, overrides, weights, thresholds, "why" and "what changed". Test: component plus seeded e2e. FA.
- **AC-16** Works at mobile width and matches the existing look. Test: mobile e2e plus owner review. HY.
- **AC-17** Suggestion-vs-owner comparison and historical classifications are viewable from saved history. Test: fixture history. FA.
- **AC-18** A new input can be added without changing existing inputs' behaviour. Test: add synthetic input. FA.
- **AC-19** No new heavy dependencies; screener, equities and other pages behave as before (existing suites stay green). Test: full suites, dependency diff. FA.
- **AC-20** The exception is removable: deleting the framework module and dashboard components restores the label-free app with no leftover references. Test: removal rehearsal. HY.

## 6. Data honesty

No fabricated, interpolated or back-filled data; gaps stay gaps (a missed LiqTide day is lost, FROM-RESEARCH). Derived values and proxies carry a "derived", "estimated" or "proxy" label. Every input shows source, as-of time and staleness.


## 7. Out of scope

Equities; intraday timeframes; confidence scores, probabilities, signal agreement; auto-accepting; alerts; labels outside /; fetching PERP data or probing Hyperliquid; new data pipelines (companion SPEC); rewriting existing code; P&L backtesting.

## 8. Constraints

Personal-use tool; reuse existing data; no heavy new dependencies; no database today (files only, FROM-RESEARCH); public repo, so owner opinions are not committed by default; synthetic fixtures; no secrets or IPs in records; no unverified claims.

## 9. Risks and unknowns

- About 6 years of daily BTC (1.5 halving cycles): CYCLE evidence is thin and must say so.
- Cold start: history begins on day one.
- Replay must never look like owner readings.
- Public repo: owner opinions not committed by default.
- Noisy suggestions could spam pending flags; labels could spread to other pages (AC-14).
- Live-source probes only run on the owner's PC.

## 10. Open questions

| # | Question | Proposed default | Tag |
|---|---|---|---|
| OQ-1 | Which inputs feed CYCLE vs HTF? | CYCLE: halving position and long-run BTC trend; HTF: liquidity, TOTAL, secular structure | NEEDS-OWNER |
| OQ-2 | Bar-close rule | Closed bars only; current bar forming and unused | SAFE-DEFAULT |
| OQ-3 | Timezone for closes | UTC closes (data is UTC); display in Brussels time | SAFE-DEFAULT |
| OQ-4 | Reading states per input | Bullish / neutral / bearish only | SAFE-DEFAULT |
| OQ-5 | What is a "changed suggestion" (flap protection) | Counts only after the new value holds a minimum number of bars (design question) | SAFE-DEFAULT |
| OQ-6 | Replay of past dates | Yes, as clearly separated system-only replay, never mixed with owner confirmations | SAFE-DEFAULT |
| OQ-7 | Where owner history lives and its backup | Machine-local, not committed; options listed in section 11 | NEEDS-OWNER |
| OQ-8 | Confirm the L1 interpretation (a)-(e) | As written in L1 | NEEDS-OWNER |
| OQ-9 | Confirm L4 scope (crypto, BTC primary) | As written | NEEDS-OWNER |
| OQ-10 | CYCLE two states, PERP three states as requested | Yes, plus explicit non-value states | SAFE-DEFAULT |

NEEDS-OWNER count: 4 (OQ-1, OQ-7, OQ-8, OQ-9).

## 11. Questions for INNOVATE

1. Storage and backup for history and owner configuration (options: local append-only files, a new local store, owner-private repo or encrypted backup).
2. Rule engine shape and how weights, thresholds and conflicts are expressed.
3. Replay design and labelling.
4. Configuration versioning (hash, sequence, or both).
5. Hysteresis design for pending suggestions.
6. UI placement on / and detail pattern.
7. Isolation boundary that keeps the module removable.

## 12. Background

FROM-RESEARCH: OHLCV via Hyperliquid/ccxt (1d never trimmed, backfill about 2020-08, 1w derived); LiqTide daily metrics from about 2024-09; FRED WALCL; DefiLlama stablecoins since 2017-11; RSI and SMA exist; no event-log or config-versioning pattern. VERIFIED: layout.json gitignored; web/app/page.tsx exists; north-star.md is at process/context/north-star.md; decisions.md latest is D-14.

## Appendix A: proposed text (not applied)

**D-15 Framework exception to D-2 (13-10-26).** The Market Intelligence Framework on route / may show owner-confirmed classifications and optional system suggestions on owner-activated inputs. The owner's reading always prevails; suggestions are secondary, never auto-accepted. Other pages stay label-free (D-2 stands). No confidence scores or signal agreement. Guard-tested; removable with the framework module. 

**North-star amendment.** After the data-not-verdicts statement add: "Exception (D-15): on the main dashboard only, the Market Intelligence Framework shows the owner's own confirmed readings and owner-enabled suggestions".

## Appendix B: companion tooling SPEC

data-integration-tooling_13-10-26 (written in parallel; referenced by name only) is the dependency for Global M2, TOTAL history, longer BTC history and any future PERP source. Until delivered, those inputs show "input unavailable until integrated".
