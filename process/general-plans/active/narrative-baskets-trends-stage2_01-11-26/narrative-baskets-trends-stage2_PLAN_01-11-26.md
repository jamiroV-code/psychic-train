---
name: plan:narrative-baskets-trends-stage2
description: "PLAN for Trends stage 2: owner-kept ambiguity list and per-coin term approvals in the keyword file, a pure selection rule that proposes (never writes) keyword changes from the campaign evidence, the keyword recorded in each daily run, a waking-up watch list on the Sources panel, and a missing-signal reason for coins without a keyword. Plan only; nothing executed."
date: 01-11-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: plan
---

[MODE: PLAN]

# Narrative Baskets: Trends stage 2 - PLAN (01-11-26)

Date: 01-11-26
Status: ⏳ PLANNED
Complexity: COMPLEX (standard: one execution stream, six slices, API and web touched). Risk tier RT2 (changes which coins the daily Trends step pulls). SPEC: `narrative-baskets-trends-stage2_SPEC_01-11-26.md` (merged, PR #207). Branch of this plan: `claude/trends-stage2-plan`; branch of EXECUTE: `claude/trends-stage2`. Context read: `process/context/all-context.md` and the testing router `process/context/tests/all-tests.md`.

## Overview and Context

The daily Trends step keeps one request per coin and the same time budget. What changes is which keyword a coin may use (an owner-kept ambiguity list plus a per-coin approval), a read-only tool that proposes keyword changes from the campaign evidence, one new field in the daily run record, and a watch list for coins that are waking up. Nothing writes `trends_keywords.json` except the owner.

## Acceptance Criteria

The acceptance criteria are AC1 to AC16 of the merged SPEC, unchanged; the Verification Evidence table below maps each one to its gate. The owner confirms AC16 after the probe; every other criterion is proven by named automated tests.

## Implementation Checklist (EXECUTE order)

- [ ] S1: keyword file rules and tests, then run the keyword tests green
- [ ] S2: `trends_select.py` and report lines with tests, then run the script tests green
- [ ] S3: the daily run records the keyword; reason text; tests green
- [ ] S4: watch-list reader, Sources field, web note; tests green
- [ ] S5: Sources note grouping and reason text; tests green
- [ ] S6: docs and decision D-30; both gate commands green against the saved baseline

## Quick links

Owner decisions | Slices S1-S6 | Public contracts | Touchpoints | Blast radius | Verification evidence | Tests and gates | Risks | Resume and handoff

## Phase Completion Rules

A slice is NOT complete until: (1) its named tests pass; (2) the changed behaviour is run once through the real entry point on fixtures; (3) the stored state or API response is read back and checked; (4) failure cases give the stated reason; (5) the owner confirms where the SPEC says an owner probe is needed. Markers: ⏳ PLANNED, 🔨 CODE DONE, 🧪 TESTING, ✅ VERIFIED, 🚧 BLOCKED. Code-only completion is CODE DONE, never VERIFIED.

## Owner decisions (closed 01-11-26, from INNOVATE)

| ID | Decision |
|---|---|
| D1 | The ambiguity list and the approvals live in `api/data/trends_keywords.json`: a reserved key `_ambiguous` (list of symbols) and an optional `"approved": true` on a coin's own entry. Changing a coin's term does not keep the approval (the validator ties `approved` to the entry, and the tool prints the approved term; see S1 rule R4). |
| D2 | The tester proposes, the owner applies. No tool writes `trends_keywords.json`. |
| D3 | The selection rule runs in the campaign report (`--report`), pure and read-only. The daily run only reads the keyword file. |
| D4 | Variant agreement only warns: `unconfirmed` when a usable variant moves against the main term, `unchecked` when no usable variant or no stored volume exists. It never rejects by itself. |
| D5 | A changed keyword starts a new series: the daily run records the keyword it used per coin per day, so old days stay labelled with their old keyword. No splicing across terms. |
| D6 | The waking-up watch list is shown on the Sources panel only, not in any score. |
| D7 | Ambiguity list = the 12 of the T125 review plus SKY, PI, JST, NEAR, GRAM, RAIN, M, CC, LIT, NIGHT, STABLE (23). |

### Owner input before EXECUTE: Q1 ANSWERED (owner, 01-11-26)

Q1 (answered). Approved, seeded as `approved: true` by EXECUTE on the current term: ONDO (`ondo crypto`), PEPE (`Pepe coin`), TRX (`tron crypto`), APT (`aptos crypto`), CRO (`cronos crypto`), MORPHO (`morpho crypto`). APT, CRO and MORPHO are approved although the campaign reads them as waking up (median 0, no usable group): the owner wants them tracked daily and shown on the watch list when they surge. NOT approved, left as they are, so they stop being pulled and show as waiting for approval or needs owner after merge: CC, JST, RAIN, SKY, GRAM, LIT, NIGHT, M, STABLE (STABLE is also untested). Other listed coins already use a topic (BNB, HBAR, ICP, LINK, NEAR, PI, SHIB, SOL) and need no approval. Evidence from the campaign that informed the answer:

| Listed coin | Current term | Campaign view |
|---|---|---|
| APT | aptos crypto | waking up (median 0), no usable group |
| CRO | cronos crypto | waking up (median 0) |
| MORPHO | morpho crypto | waking up |
| ONDO | ondo crypto | usable, same term best |
| PEPE | Pepe coin | usable, same term best, clean rising |
| TRX | tron crypto | usable, same term best |
| SKY | sky crypto | usable but ambiguous (`sky crypto` 43%), volume correlation -0.11 |
| JST | just crypto | usable, near tie with `just coin` |
| CC | canton coin | usable |
| GRAM | the open network toncoin | too little interest; `the open network` usable (90%) |
| LIT | lighter crypto | usable only as bare `LIT` |
| NIGHT | midnight crypto | usable only as bare `midnight` |
| RAIN | rain protocol | usable (28% vs `rain crypto` 47%) |
| M | memecore crypto | no usable group, needs owner |
| STABLE | stable chain | untested |

Effect of the answer: the six approved coins keep their keyword and are still pulled. CC, JST, RAIN, SKY, GRAM, LIT, NIGHT, M and STABLE are not on the T125 list, so they ARE pulled today with their current terms; after merge these nine stop being pulled and their Trends signal reads missing with the reason "waiting for owner approval" until a topic or an approved term exists. EXECUTE reports the exact set of coins whose pull status changes, read from the shipped file before and after.

## S1. Keyword file: ambiguity list and approvals (AC6, AC7, AC11)

Files: `api/data/attention/trends_keywords.py`, `api/data/trends_keywords.json`, `api/data/attention/trends.py`, `api/data/attention/trends_candidates.py`.

Rules (validator, applied at load; a bad file is `bad keyword file`, never a crash, as today):
- R1. Reserved key `_ambiguous`: a list of unique upper-case symbols matching `SYMBOL_RE`. Missing key = empty list (older files still load).
- R2. A coin entry may carry `"approved": true` (only `true`; no other value). Allowed only on an entry with `term` (a topic is always accepted; `no-keyword` has nothing to approve). `approved` on a topic or no-keyword entry is an error.
- R3. Every symbol in `_ambiguous` must have an entry (existing placed-coin rule) and `_ambiguous` may not contain `_anchor`.
- R4. `keyword_status(km, symbol)`: for a symbol in `_ambiguous` a `term` entry returns `skipped-unqualified` unless it has `approved: true`; a topic returns `topic`; no-keyword stays `no-keyword`. A symbol not in `_ambiguous` is not restricted (the T125 constant no longer decides). The status string `skipped-unqualified` is kept so run files and readers do not change vocabulary; the Sources note says "waiting for owner approval".
- R5. `trends.NAME_RISK_SYMBOLS` is removed (single source of truth is the file). `trends.is_qualified_term` and `QUALIFIER_WORDS` stay: the candidate builder still uses them to make qualified candidate terms for listed coins. `trends_candidates` receives the ambiguous set as an argument instead of importing the constant.
- R6. The shipped file gets `_ambiguous` = the 23 coins of D7 and `approved: true` on exactly these six terms (Q1, answered): ONDO, PEPE, TRX, APT, CRO, MORPHO. No other term is approved.

Tests: `test_trends_keywords.py` (new cases: `_ambiguous` valid, duplicate, unknown shape, `_anchor` in list, `approved` on a topic, `approved: false`, approved term for an ambiguous coin pulled, unapproved term skipped, listed coin with topic pulled, unlisted coin with bare term pulled); `test_trends.py` (`test_name_risk_symbols_match_t125_list` becomes a test that the shipped `_ambiguous` list equals the 23 coins of D7); `test_trends_candidates.py` and `test_trends_t202.py` updated to pass the ambiguous set.

## S2. Selection rule in the campaign report (AC1-AC5, AC13-AC15)

Files: new `api/data/attention/trends_select.py` (pure: no network, no file writes), `api/scripts/trends_campaign.py` (report), `api/scripts/probe_trends.py` (`--report` output).

Rule `select(coin_record, entry, ambiguous) -> Selection{verdict, term, reasons, flags, others}`; verdict is one of `use-term`, `use-topic`, `needs-approval`, `needs-owner`, `waking-up`, `untested`:
- A group is a candidate only if its outcome is ok, its verdict is `ok` (the daily rule), and it has no one-term spike.
- Candidates are single-term groups. A bundle is never the signal (AC1); it only contributes flags.
- Order among candidates: fewest zero days, then most distinct values, then higher volume correlation (missing last). `clean rising` and `median` play no part (AC3).
- Identity flag (AC4): volume correlation below `IDENTITY_MIN_CORR` -> `unconfirmed (volume)`; no stored volume -> `unchecked (no volume)`.
- Variant flag (AC5, D4): compare the main term with the usable bundles that contain it; a usable variant whose `moves_alone` list names the main term -> `unconfirmed (variants)`; none usable -> `unchecked (no variants)`. Never a rejection.
- Ambiguous coin: a topic candidate -> `use-topic`; only a term candidate -> `needs-approval` unless `entry.approved` and the entry's term equals the candidate -> `use-term`.
- No candidate: quiet-then-surge in any group -> `waking-up`; otherwise `needs-owner` with the reason (`no usable group`, `frame-rejected`, `too-little-interest`).
- A listed coin absent from the campaign state -> `untested` (AC15); never `use-term`.
- `--report` prints one line per coin: current keyword and status, selection verdict, chosen term, flags, and the losing terms with why (AC13); plus a paste-ready JSON block of proposed entries labelled `proposal; you apply it`. `--report` stays read-only and never touches the network (AC14). `STAGE2_JSON_LABEL` is updated to the new shape.

Tests: new `api/tests/data/attention/test_trends_select.py` (empty, quiet, one-day spike, one-term spike refused; rising-but-gappy loses to steady-but-complete; bundle present never changes the term; volume flags with and without stored volume; variant flags agree/disagree/none; listed coin topic/approved term/unapproved term/term approved for another coin; no passing term; waking-up; untested); `test_probe_trends_t202.py` and `test_probe_trends_campaign.py` updated; `test_report_is_read_only_and_sends_no_request` (monkeypatch the fetch to fail).

## S3. Daily run: the keyword used is recorded (AC8, AC12, D5)

Files: `api/scripts/refresh_attention.py`.
- `_run_coin_record` adds `keyword` (the term or topic string used that day) next to `keyword_kind`. For a coin that was not pulled it is `null`. No other behaviour changes: one request per coin, same budget, same retries, same rotation.
- A coin with status `no-keyword` or `skipped-unqualified` keeps today's path (unavailable, reason `no keyword mapped` or `name-ambiguous: needs topic or qualified term`); the reason text becomes `waiting for owner approval` for the second (AC8). The Trends signal for such a coin is missing with that reason, never 0.
- Series storage is unchanged (replace-series by symbol, `trends_pulls` archive, frozen snapshots). The recorded `keyword` per day is what labels a changed keyword's history; this plan does not splice or rescale across terms (D5).

Tests: `test_refresh_attention_trends_runs.py` (`keyword` present for pulled coins and null otherwise; reader still accepts old files without the field), `test_refresh_attention_trends.py` (request count equals pulled coins; unapproved ambiguous coin sends no request and is reported with the new reason; budget test unchanged).

## S4. Waking-up watch list (AC9, AC10)

Files: `api/data/attention/trends_runs.py` (reader), `api/analytics/attention/sources.py`, `api/models/discovery.py`, `web/lib/types/discovery.ts`, `web/components/narrative/DiscoverySourcesPanel.tsx`.
- New pure reader `watch_list(run_files, max_files=30)`: for each coin, the number of consecutive latest days with outcome `quiet-then-surge`, ending at the newest file; a day with any other outcome ends the streak; a coin not in the newest file is not listed. Corrupt, oversized or unknown-shape files are skipped with the existing note, never blocking.
- `build_sources` adds `trends_watch: [{symbol, days_held}]` to the response (empty list when none). It reads no score, writes nothing and does not touch Discovery ranking (AC9).
- Web: the Sources panel renders a "Waking up" note under the Trends row: `SYM (N days)`; a coin that leaves the list disappears on the next load (AC10).

Tests: `test_trends_runs.py` (streaks, break, gap day, corrupt file, max files), `test_sources.py` (`trends_watch` present and empty), `test_discovery.py` (new: Discovery scores identical with and without a coin in the watch list), web `DiscoveryTab.test.tsx` watch text and absence, plus one fixture-backed end-to-end Sources load.

## S5. Sources coverage note distinguishes the cases (AC8)

Files: `api/analytics/attention/sources.py`, `api/models/discovery.py`, `web/components/narrative/DiscoverySourcesPanel.tsx`, `web/lib/format-unavailable-reason.ts`.
- `trends_keyword.missing` already lists `(symbol, status)`; the note groups them: `waiting for approval: SYMS`, `no keyword (needs owner): SYMS`. A new unavailable-reason text `waiting for owner approval` is added next to `no-trends-keyword`.

Tests: `test_sources.py` (`test_trends_keyword_coverage_over_eligible_coins` extended), `format-unavailable-reason.test.ts`, `DiscoveryTab.test.tsx`.

## S6. Docs and context

- `process/context/decisions.md` D-30 (one term per coin, ambiguity list and approvals in the keyword file, tester proposes, waking up watch only).
- `process/context/data-sources/all-data-sources.md` and `process/context/current-state.md`: one line each.
- Operator note in the plan's EXEC-REPORT for the owner: how to read `--report` and apply a proposal.

## Public Contracts

| Contract | Change |
|---|---|
| `trends_keywords.json` | new reserved key `_ambiguous`; optional `approved: true` on `term` entries; older files still load |
| `keyword_status` | rule for listed coins; status strings unchanged |
| `trends_runs/<date>.json` | coin record gains `keyword` (null when not pulled); readers ignore its absence |
| `GET /api/narrative/discovery/sources` | response gains `trends_watch` (list); additive; existing fields unchanged |
| `--report` output | new selection lines and proposal block; read-only |
| `NAME_RISK_SYMBOLS` | removed from `trends.py` (no web use; python callers are `trends_keywords.py`, `trends_candidates.py`, `refresh_attention.py`, `probe_trends.py`, all migrated in this plan) |

## Touchpoints

Changed: `api/data/attention/trends_keywords.py`, `trends.py`, `trends_candidates.py`, `trends_runs.py`, new `trends_select.py`; `api/data/trends_keywords.json`; `api/scripts/refresh_attention.py`, `trends_campaign.py`, `probe_trends.py`; `api/analytics/attention/sources.py`; `api/models/discovery.py`; `web/lib/types/discovery.ts`, `web/lib/format-unavailable-reason.ts`, `web/components/narrative/DiscoverySourcesPanel.tsx`; the tests named per slice; the three docs of S6. Read only: `store.py`, `discovery_history.py`, `signal_snapshots.py` (history behaviour is unchanged; a test asserts it).

## Blast Radius

About 20 files, API and web. Live effect: after merge the daily Trends step stops pulling any listed coin whose term is not approved (Q1). Discovery scoring code is not changed; a coin without a Trends signal reads as missing for that source, never 0. Risk class RT2; no provider call is made by any test.

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| `test_trends_select`: one term chosen with a bundle present | Fully-Automated | AC1 |
| `test_trends_select`: empty, quiet, one-day spike, one-term spike refused | Fully-Automated | AC2 |
| `test_trends_select`: gappy-rising loses to steady-complete | Fully-Automated | AC3 |
| `test_trends_select`: volume flags with and without volume | Fully-Automated | AC4 |
| `test_trends_select`: variant flags agree/disagree/none | Fully-Automated | AC5 |
| `test_trends_keywords` + `test_trends_select`: topic / approved / unapproved / other-coin term | Fully-Automated | AC6 |
| `test_trends` shipped list equals the 23 coins; added coin takes effect from the file | Fully-Automated | AC7 |
| `test_refresh_attention_trends` + `test_sources`: unapproved and no-keyword coins send no request and read missing with reason | Fully-Automated | AC8 |
| `test_discovery`: scores identical with and without a watch-list coin; `test_trends_runs` streaks | Fully-Automated | AC9 |
| `DiscoveryTab.test.tsx` watch text + fixture-backed Sources load | Fully-Automated | AC10 |
| `test_trends_keywords` bad-file cases and `bad keyword file` reason | Fully-Automated | AC11 |
| `test_refresh_attention_trends`: request count equals pulled coins; existing budget test | Fully-Automated | AC12 |
| `test_probe_trends_t202`: per-coin evidence lines on the real state shape | Fully-Automated | AC13 |
| `test_report_is_read_only_and_sends_no_request` | Fully-Automated | AC14 |
| `test_trends_select`: listed coin missing from the state is `untested` | Fully-Automated | AC15 |
| Owner probe P-T1: chosen terms vs the public Trends page for ten coins | Agent-Probe (residual: Trends is unreachable from the build environment) | AC16 |

## Tests and gates (commands)

```
uv run --project api python -m pytest api/tests/data/attention api/tests/scripts api/tests/analytics/attention -q -p no:cacheprovider
cd web && pnpm exec vitest run components/narrative lib && pnpm exec tsc --noEmit
```
Baseline: 24 failures that also fail on `main` (12 in `test_discovery.py`, 11 in `test_discovery_history.py`, `test_discovery_end_to_end_on_fixture`: "handler must not reach the network"). EXECUTE saves the baseline FAILED ids first and reports only new ones. A gate script is not generated for this plan; EXECUTE runs the two commands and a diff-name check (changed files must be inside Touchpoints).

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Nine coins stop being pulled after merge (CC, JST, RAIN, SKY, GRAM, LIT, NIGHT, M, STABLE) | Q1 is answered; the Sources note lists them as waiting for approval; the owner edits `approved` or sets a topic and nothing else is needed; EXECUTE reports the before and after set |
| A changed keyword mixes two terms in one history | the daily run records the keyword per day; no splicing; history reads are unchanged and asserted |
| Variant check misjudges weak extra variants | D4: warns only, never rejects |
| Thresholds are placeholders | named constants, tuned after the first real run |
| `NAME_RISK_SYMBOLS` removal misses a caller | the exported-symbol rule: references checked with the language server before the removal; the five callers are listed above |
| The watch-list scan is slow | at most 30 run files, size-capped like the existing reader |

## Test Infra Improvement Notes

(none identified yet)

## Cursor + RIPER-5 guidance

RIPER-5: this PLAN, then VALIDATE, then the owner's ENTER EXECUTE MODE for T-Trends-stage2 with agent `riper-opus` on branch `claude/trends-stage2`. EXECUTE order: S1, S2, S3, S4, S5, S6, each with its tests before the next; stop and report on scope expansion. After each slice: what is functional, what was tested, what the owner can check.

## Resume and Execution Handoff

1. Selected plan file: `process/general-plans/active/narrative-baskets-trends-stage2_01-11-26/narrative-baskets-trends-stage2_PLAN_01-11-26.md`.
2. Last completed phase or step: PLAN written; nothing executed.
3. Validate-contract status: pending (VALIDATE not run).
4. Supporting context files loaded: the SPEC, `trends_keywords.py`, the scout facts on `refresh_attention.py`, `trends_campaign.py`, `probe_trends.py`, `sources.py`, `DiscoverySourcesPanel.tsx`, `store.py`, `discovery_history.py`.
5. Next step for a fresh agent: Q1 is answered (see Owner decisions); run VALIDATE, get ENTER EXECUTE MODE, then start at S1.

## Validate Contract

(placeholder — vc-validate-agent writes this section before EXECUTE)
