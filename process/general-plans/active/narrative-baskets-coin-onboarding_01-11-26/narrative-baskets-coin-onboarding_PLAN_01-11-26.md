---
name: plan:narrative-baskets-coin-onboarding
description: "PLAN for automatic coin onboarding (T223): a per-coin ledger with 14-day probation and a top-120 exit band, eligibility integration, a pegged/wrapped classifier, a GitHub-run resolver for Wikipedia, Google Trends and Reddit/X names that writes overlay files, narrative proposals, a new-coins API and page, and a shadow mode before enforcement. Plan only; nothing executed."
date: 01-11-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: plan
---

[MODE: PLAN]

# Narrative Baskets: automatic coin onboarding - PLAN (01-11-26)

Date: 01-11-26
Status: ⏳ PLANNED
Complexity: COMPLEX (standard: one execution stream, seven slices, data, API, web and one workflow line). Risk tier RT3 (changes which coins are scored and writes owner-visible data automatically). SPEC: `narrative-baskets-coin-onboarding_SPEC_01-11-26.md` (merged, PR #215). Task id T223 and decision id D-31 are the next free ones (inference from `MASTER-PLAN` and `decisions.md`; EXECUTE re-checks). Branch of this plan: `claude/coin-onboarding-plan`; branch of EXECUTE: `claude/coin-onboarding`. Context read: `process/context/all-context.md` and the testing router `process/context/tests/all-tests.md`.

## Overview and Context

Today a coin that enters the top 100 is in the universe the same day and shows up as gaps in every per-coin source; nothing writes names automatically. This plan adds (1) a ledger that tracks each coin's state with a 14-day probation and a 7-day exit band at rank 120, (2) one change at the single eligibility choke point so watching, inactive and unclassified coins are not scored, (3) a classifier for pegged and wrapped tokens, (4) a resolver that finds Wikipedia, Google Trends and Reddit/X names, checks them and writes them to overlay files that the owner's files always override, (5) narrative proposals that never move placement, (6) one API route and a new-coins page, and (7) docs. Everything starts in shadow mode: the ledger, the classifier and the resolver run and log, and the universe does not change until the owner flips one setting.

## Owner decisions (closed 01-11-26)

| ID | Decision |
|---|---|
| O1 | Probation: 14 consecutive daily snapshots in the top 100; a missed snapshot day is neutral; a day outside the top 100 resets the count. |
| O2 | Exit: a member becomes inactive after 7 consecutive days outside the top 120 (the exit band is rank 120); a return to the top 120 cancels it. Inactive coins keep history and entries; a returning coin repeats probation and resumes with them. |
| O3 | No minimum listing age. "Watching" is visible and collects data. |
| O4 | Classification is automatic; a coin the classifier cannot place stays out of scoring (`unclassified`) until the owner confirms it. |
| O5 | Names that pass every check go live automatically; borderline ones wait for the owner with evidence; no name means a reason and a missing signal, never 0. The ambiguity list and approval rule of Trends stage 2 are never bypassed. |
| O6 | Narratives are proposed; the owner approves. |
| O7 | Seed: every coin in the first snapshot after go-live is a member (no change to today's universe); probation applies only to later entrants. |
| O8 | The resolver runs in GitHub, not on the owner's PC (owner, 01-11-26; this replaces the SPEC constraint "runs on the owner's PC"). It commits its data files like the other data jobs; this plan adds no push to `main` beyond that existing exception (D-28). |

SPEC gap (recorded, SPEC stays frozen): the SPEC's Constraints and AC18 say "the owner's PC". O8 changes that to GitHub; the AC18 owner probe becomes P-O1 below (workflow run and log read).

## Acceptance Criteria

AC1 to AC18 of the merged SPEC. The Verification Evidence table maps each to its gate; AC18 is the owner probe P-O1 on a real workflow run.

## Implementation Checklist (EXECUTE order)

- [ ] O0 settings file and shadow mode, pure ledger state machine with tests
- [ ] O1 ledger step in the daily refresh (snapshot widened to rank 120, seeding, daily update), tests
- [ ] O2 eligibility integration behind `enforce`, closed reasons extended in API and web, tests
- [ ] O3 classifier (pure rules plus a fetch step for watching coins), tests
- [ ] O4 resolver for Trends, Wikipedia and Reddit/X names with overlays, pending file, log and reverse tool, tests
- [ ] O5 narrative proposals and the approval check, pin tests made property-based, tests
- [ ] O6 API route and new-coins page, tests
- [ ] O7 docs, D-31, owner probe notes; both gate commands green against the saved baseline

## Phase Completion Rules

A slice is NOT complete until: (1) its named tests pass; (2) the changed behaviour is run once through the real entry point on fixtures; (3) the stored state or response is read back and checked; (4) failure cases give the stated reason; (5) the owner confirms where an owner probe is named. Markers: ⏳ PLANNED, 🔨 CODE DONE, 🧪 TESTING, ✅ VERIFIED, 🚧 BLOCKED. Code-only completion is CODE DONE, never VERIFIED.

## Verified inputs (read-only, `main` at the time of writing)

| Fact | Where | Consequence |
|---|---|---|
| The snapshot holds the top 100, 14 snapshots deep, per coin `id, symbol, market_cap, volume_24h`; no rank, name, price or categories | `universe_store.py` (`KEEP_SNAPSHOTS = 14`), `coingecko_attention.py` `fetch_top100_markets` | the ledger needs its own record; ranks 101-120 need a wider fetch; classification needs one more call per watching coin |
| The markets fetch is `per_page=100, page=1`; a 120-row call is UNVERIFIED live | `coingecko_attention.py` | O1 widens it to 120 and stores rank; probe P-O0 confirms the shape |
| The one eligibility choke point is `universe_classes.build`, fed by `load_universe_rows`; consumers: `discovery.py`, `discovery_history.py`, `sources.py`, `trends_keywords.guard_gaps/coverage`, `check_trends_keywords.py`, `spot_volume_refresh.py`, `defillama.py` | `universe_classes.py:95-122`, scout A | one change reaches all of them; Baskets uses `load_reference` and is unaffected |
| An in-universe coin with no narrative is excluded from scoring and listed `unassigned` | `discovery.py:404-470` | an unproposed narrative never scores a coin; that is today's behaviour |
| `REASONS` in `universe_classes.py` is a closed list used by the API model comment, the legacy `exclusion_list` sum, the web type, label and sentence, and fixture tests | D-29 (#206) | new reasons `watching`, `inactive`, `unclassified` follow the same ripple |
| The Reddit/X queries loader raises when a placed coin has no entry; pins: placed count 75 in `test_web_queries.py:84` and `test_narratives.py:43`, `3/75` in `test_attention_workflow_guard.py:260` | scout B, C | placement must not happen before a queries entry exists; the count pins become property checks (O5) |
| `wiki_articles.json` shape test fails on a key not in `KNOWN_KEYS` or the latest snapshot | `test_wiki_articles_shape.py` | auto titles go to an overlay the shape test does not read |
| The data workflow commits `api/data/cache/attention/` and `probe_records.json` with `git add -f` and pushes as the bot | `attention-refresh.yml:158-166,271-279` | overlays, the ledger, the pending file and the log live under `api/data/cache/attention/onboarding/`, so no new commit path is needed |
| Google Trends already runs on GitHub's runners (pytrends installed per run in the `refresh-extra` step) | `attention-refresh.yml:202-213` | the Trends resolver runs in the same step; Wikipedia and the snapshot-based steps run in `refresh` |
| Existing owner tools already hold the logic to reuse: `check_trends_keywords.py` (suggestions), `check_wiki_titles.py` (REST check, crypto words), `trends_campaign`/`trends_groups` (usable, spike, volume agreement) | scout B | the resolver calls these as libraries; their scripts stay as they are |
| Append-only per-day evidence pattern exists: `trends_runs.py`; a saved-choice machine cache exists: `defillama_map.json` | scout B | the onboarding log reuses the run-file pattern |

## O0. Settings, shadow mode, pure ledger (AC2, AC3, AC4, AC17)

Files (new): `api/data/coin_onboarding.json` (settings), `api/data/attention/coin_ledger.py` (pure state machine, no I/O), `api/data/attention/onboarding_settings.py` (loader/validator).
- Settings (named, validated, a bad file refuses with a plain message and the step is skipped, never a crash): `mode` (`shadow` default, `enforce`), `probation_days` 14, `exit_band_rank` 120, `exit_days` 7, check thresholds for the resolver (named constants listed in O4).
- Ledger entry per coin id: `symbol, state (watching|member|inactive), first_seen, last_in_top100, last_in_top120, consecutive_top100 (int), consecutive_outside120 (int), class, class_evidence, class_source (owner|auto|confirmed), seeded (bool), updated`.
- `advance(ledger, snapshot_date, ranks, settings)` rules: entrant -> `watching` with count 1; a day in the top 100 adds 1 (a day with no snapshot adds nothing and resets nothing); a day outside the top 100 resets the count to 0 for a `watching` coin; a `watching` coin with count `probation_days` -> `member` (its class decides scoring in O2); a `member` outside rank 120 for `exit_days` consecutive snapshot days -> `inactive`; a return to the top 120 resets `consecutive_outside120`; an `inactive` coin that re-enters the top 100 -> `watching` (count restarts) and keeps `class` and entries.
- Tests (new `api/tests/data/attention/test_coin_ledger.py`): enter; 13 days then drop; 14 days joins; drop and return restarts the count; a missing snapshot day is neutral; rank 101-120 stays member; exit on day 7 and not day 6; return on day 5 cancels; inactive keeps class and returns to watching; settings bad file; seeding marks `seeded` and `member`.

## O1. Ledger step in the daily refresh (AC1, AC3, AC5)

Files: `api/data/attention/coingecko_attention.py` (fetch 120 rows, store `rank`), `api/data/attention/universe_store.py` (snapshot keeps `rank`; keep 14 snapshots), `api/data/attention/onboarding_store.py` (new: `api/data/cache/attention/onboarding/ledger.json`, atomic write, same atomic pattern as the other stores), `api/scripts/refresh_attention.py` (new source `ledger` added to `DEFAULT_SOURCES` after `universe`).
- The markets fetch becomes `per_page=120` (one call); the universe still takes `[:TOP_N]` (100) for scoring, so nothing that reads the snapshot changes except that it carries rank and 20 extra rows. If the live 120-row response is not as documented the step fails closed: the snapshot is written as today and the ledger step reports `unavailable` and does not run (never a guess).
- First run (O7): if no ledger exists, every coin in the latest snapshot becomes `member` with `seeded: true`; no probation for them. Coins that later enter follow O0.
- The step runs with `mode: shadow` by default: it updates the ledger and writes the log; eligibility is unchanged until `enforce`.
- Tests: `test_refresh_attention.py` (new source registered; failed fetch leaves the snapshot and skips the ledger), `test_universe_store.py` (rank stored), `test_onboarding_store.py` (atomic write, corrupt file refused and kept), seeding test.

## O2. Eligibility integration behind `enforce` (AC1, AC6, AC7, AC16)

Files: `api/analytics/attention/universe_classes.py`, `api/analytics/attention/discovery.py` (legacy sum), `api/models/discovery.py` (comment), `web/lib/types/discovery.ts`, `web/components/narrative/DiscoveryExclusions.tsx`.
- `build(rows, rules, venues, today, ledger=None, mode)`: when `mode == "enforce"` and a ledger is given: a coin whose ledger state is `watching` is out with reason `watching` (detail "in probation, N of 14 days"); `inactive` is out with reason `inactive`; a coin with class `unknown` (class_source auto, not confirmed) is out with reason `unclassified`. Owner class lists and `force_include` keep their precedence (`force_include` wins over everything, as today). In `shadow` or with no ledger the function is unchanged.
- The three new reasons are added to `REASONS`, the legacy `exclusion_list` sum, the API model comment, the web type, label and sentence (same ripple as D-29).
- `refresh_attention._universe_rows` and `_symbols` still hand every runner the snapshot minus the legacy constants, so watching coins keep collecting data from day one (O3 of the SPEC); only scoring reads the eligible set.
- Tests: `test_universe_classes.py` (new cases: watching, inactive, unclassified, force_include wins, shadow unchanged, no ledger unchanged), `test_discovery.py` (excluded counts sum to universe minus shown with the new reasons), `routers/test_discovery.py` key set unchanged, web `DiscoveryExclusions.test.tsx` (labels and sentences for the three reasons). The existing fixture pins (74 eligible) hold because the fixtures pass no ledger.

## O3. Classifier (AC6, AC7)

Files (new): `api/data/attention/coin_class.py` (pure rules), `api/scripts/refresh_attention.py` (new source `classify`, runs for `watching` coins and for new unknowns only).
- Evidence record per coin, from one CoinGecko coin-detail call (UNVERIFIED live: `categories`, `name`, `asset_platform_id`) and the price series already fetched for the coin: stablecoin (a category naming stablecoins, or price within a band of 1.00 for the window), wrapped or staked (categories naming wrapped, liquid staking or bridged tokens, or a name pattern), commodity backed (categories naming tokenized gold or commodities), tokenized fund (categories naming tokenized treasuries or funds), else `normal`. Two independent signals give a confident class; one signal gives `unknown`; none gives `normal` only when a category list was read.
- Owner class lists in `discovery.json` always win (class_source `owner`); a confirmed coin (`class_source: confirmed`, set by the owner through the O6 tool) wins over auto. A classification fetch that fails leaves `unknown`, never `normal`.
- The evidence (categories, signals, price band) is stored in the ledger and shown on the page (AC14).
- Tests: new `api/tests/data/attention/test_coin_class.py` on fixture records (stablecoin by category, by price band only = unknown, wrapped by name and category, gold-backed, tokenized fund, normal, unknown, failed fetch, owner list wins, confirmed wins).

## O4. Resolver, overlays, pending file, log, reverse (AC8-AC12, AC15, AC16)

Files (new): `api/data/attention/onboarding_resolver.py` (pure checks), `api/data/attention/onboarding_sources.py` (thin fetchers reusing the existing check libraries), `api/data/attention/onboarding_store.py` (overlays, pending, log), `api/scripts/onboarding_reverse.py`; changed: `trends_keywords.py`, `wikipedia.py` loader wiring in `refresh_attention.py`, `web_queries.py`, `api/scripts/refresh_attention.py` (sources `resolve_wiki`, `resolve_trends`).
- Overlays (written only by the resolver, under `api/data/cache/attention/onboarding/`): `trends_keywords_auto.json`, `wiki_articles_auto.json`, `attention_queries_auto.json`. Loaders merge them under the owner files (owner entry wins for the same symbol). Auto entries carry `source: "auto"`, `resolved_at` and the evidence key. The owner files, their shape tests and `KNOWN_KEYS` are untouched.
- Trends: candidates from the suggestions endpoint plus qualified terms; each candidate is checked: identity (entity typed as a cryptocurrency and a name match; several equally likely entities means borderline), series (the daily verdict `ok`, no one-term spike: the `trends_groups` rules), volume (correlation with the coin's own exchange volume above `IDENTITY_MIN_CORR` when volume exists; no volume means borderline, never pass), ambiguity (the bare name is on the ambiguity list or a common word: only a topic passes). Pass -> overlay entry (a topic, or a qualified term for an unlisted coin); a coin on the ambiguity list never gets an automatic `term`, only a `topic` (the existing approval rule is unchanged and is asserted).
- Wikipedia: candidate titles from the snapshot name; checked with the REST summary: `type == standard`, crypto words present, not a disambiguation page, and the pageviews fetch returns enough days. Pass -> overlay.
- Reddit/X: the name from the snapshot (`name`, `cashtag_only` when the symbol equals the name); an ambiguous name (on the ambiguity list for the source, or a short common word) is borderline. Pass -> overlay entry. A coin is never placed in a narrative before it has a queries entry (O5).
- Borderline candidates go to `pending.json` with evidence; the source reads missing with the reason; nothing is written to an overlay. No candidate passes -> reason recorded in the ledger, never a zero.
- Every automatic write appends to `onboarding/log/<UTC date>.json` (per coin: source, action `applied|pending|none`, evidence summary, previous value). `onboarding_reverse.py SYMBOL SOURCE` removes an overlay entry, restores the previous state in the log, and the entry is not re-applied for that coin and source until the owner clears the block.
- Rate limits: a refusal or 429 stops the step for the run (exit class recorded) and the coin stays unresolved until the next run; no loop. The Trends resolver reuses the existing pacing and runs inside the existing `refresh-extra` budget (it takes at most a fixed number of coins per run, default 5, settings).
- The workflow: Wikipedia and the snapshot-based steps join the existing `refresh` run through `DEFAULT_SOURCES`; the Trends resolver is one more source name added to the existing `refresh-extra` command line in `.github/workflows/attention-refresh.yml` (`--sources trends` becomes `--sources trends,resolve_trends`). That is the only `.github` change; the worker must not make it. EXECUTE prints the exact diff in the EXEC-REPORT and the owner applies it by hand or approves a follow-up PR (owner approval needed per the earlier hard rule). Until then the resolver can be run by `python -m api.scripts.refresh_attention --sources resolve_wiki,resolve_trends` (owner run) and the shadow-mode ledger runs without any workflow change.
- Tests (new `test_onboarding_resolver.py`, `test_onboarding_store.py`, `test_onboarding_reverse.py`; changed `test_trends_keywords.py`, `test_wikipedia.py`, `test_web_queries.py`): pass, borderline, none per source with fakes; ambiguity-list coin gets only a topic; owner entry beats overlay; overlay absent loads as before; overlay entry for a coin on the ambiguity list is refused by the loader unless it is a topic; log append and reverse; 429 stops the step and leaves coins pending; no test reaches the network (the shared network-block fixture).

## O5. Narrative proposals and pin tests (AC13)

Files (new): `api/data/attention/narrative_proposals.py`, `api/scripts/onboarding_approve.py`; changed tests `test_narratives.py`, `test_web_queries.py`, `test_attention_workflow_guard.py`.
- Proposals: for a coin with no placement, map its CoinGecko categories through `attention_narrative_id_map.json` (existing seeds) to a narrative id; a proposal is written to `onboarding/narrative_proposals.json` with the evidence. It never touches `attention_narratives.json`.
- `onboarding_approve.py SYMBOL NARRATIVE` (owner run) checks that the coin has a Reddit/X queries entry (owner or overlay) and a ledger state `member`, prints a paste-ready placement for `attention_narratives.json` and the pins to update, and writes nothing to the narratives file (the owner applies it, as with the keyword file).
- The hard count pins (75 placed in two tests, `3/75` in the workflow guard test) become property checks: every placed coin has a queries entry; the narratives primary count equals the count the file declares; the guard test derives the expected count from the file. A deliberate placement therefore does not need a test edit.
- Tests: proposal built from categories; unmapped category gives no proposal; no auto-placement; approve tool refuses a coin without a queries entry; the property tests.

## O6. API route and new-coins page (AC14)

Files: `api/routers/discovery.py` (new `GET /api/narrative/onboarding`), `api/models/discovery.py` (new `OnboardingResponse`, `OnboardingCoin`), `api/analytics/attention/onboarding.py` (builds the rows from the ledger, overlays, pending file and proposals), `web/lib/api/discovery.ts`, `web/lib/types/discovery.ts`, `web/components/narrative/NewCoinsPanel.tsx`, `web/components/narrative/NarrativeTabs.tsx` (a "New coins" tab).
- Per coin: `symbol, state, days_in_top100 / probation_days, class, class_evidence, class_source, sources: {wikipedia, trends, reddit_x: {state: name|pending|missing|none, value, reason}}, pending: [..], proposal`. Watching, member (recent), inactive and pending coins are listed; a coin with nothing pending shows none. Read-only; no writes from the page.
- `GET` reads files only (no network). In shadow mode the page shows a banner "shadow: the universe is not changed".
- Tests: `test_onboarding.py` (rows from fixtures), `routers` key-set test, web `NewCoinsPanel.test.tsx` and `NarrativeTabs` test, and a fixture-backed load as a vitest test (Playwright is not run by the gates).

## O7. Docs and probes

- `process/context/decisions.md` D-31; one line each in `process/context/data-sources/all-data-sources.md` and `process/context/current-state.md`; an operator note in the EXEC-REPORT: how to read the log, reverse an entry, confirm a class, approve a narrative, and flip `mode` to `enforce`.
- Owner probes (not run by EXECUTE): **P-O0** the live shapes (a 120-row markets response with `rank`, `name`; one coin-detail response with `categories`, `asset_platform_id`; the suggestions entity types) via one owner run of `refresh_attention --sources universe,classify` and reading the log; **P-O1** one workflow or owner run of `resolve_wiki,resolve_trends` on a real unnamed coin, reading the log (AC18); **P-O2** after a week in shadow, review the ledger and the new-coins page, then set `mode` to `enforce`.

## Public Contracts

| Contract | Change |
|---|---|
| `api/data/cache/attention/universe.json` snapshot | each coin gains `rank`; 120 rows are fetched, the universe still scores the first 100; older snapshots without `rank` still load |
| `api/data/coin_onboarding.json` | new settings file (`mode`, `probation_days`, `exit_band_rank`, `exit_days`, thresholds) |
| `api/data/cache/attention/onboarding/` | new data directory: `ledger.json`, `*_auto.json` overlays, `pending.json`, `narrative_proposals.json`, `log/<date>.json`; committed by the existing bot step |
| Owner files (`trends_keywords.json`, `wiki_articles.json`, `attention_queries.json`, `attention_narratives.json`) | unchanged; the owner entry always wins over an overlay |
| `universe_classes.build` | optional ledger and mode arguments; three new reasons `watching`, `inactive`, `unclassified` (closed list extended; API additive, web type extended) |
| `GET /api/narrative/onboarding` | new route; read-only |
| `refresh_attention` sources | new names `ledger`, `classify`, `resolve_wiki`, `resolve_trends`; `DEFAULT_SOURCES` gains `ledger` (and `classify`, `resolve_wiki`); `resolve_trends` is added to the `refresh-extra` line by the owner |

## Touchpoints

Changed: `api/data/attention/coingecko_attention.py`, `universe_store.py`, `trends_keywords.py`, `wikipedia.py`, `web_queries.py`; `api/analytics/attention/universe_classes.py`, `discovery.py`; `api/models/discovery.py`; `api/routers/discovery.py`; `api/scripts/refresh_attention.py`; `web/lib/types/discovery.ts`, `web/lib/api/discovery.ts`, `web/components/narrative/DiscoveryExclusions.tsx`, `NarrativeTabs.tsx`; new files named per slice; the tests named per slice; the three docs of O7. Read only: `store.py`, `signal_snapshots.py`, `trends_runs.py`, `check_trends_keywords.py`, `check_wiki_titles.py`, `trends_campaign.py`, `trends_groups.py`. NOT touched by the worker: `.github/**` (the one-line change in O4 is printed for the owner), `deploy/`, `attention_pc_refresh.py`, the owner data files, `discovery.json` class lists, weights.

## Blast Radius

About 40 files (about 14 new), API, web and data. Live effect in shadow mode: none on scores or the universe; new files appear under `api/data/cache/attention/onboarding/` after the next refresh. Live effect after `enforce`: new entrants are not scored for 14 days and unknown classes stay out. Risk class RT3, mitigated by shadow mode, the owner-file-wins rule and the reversible log. No provider call is made by any test.

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| `test_coin_ledger`: new entrant is `watching`; `test_universe_classes`: `watching` coin is out and not in the reference | Fully-Automated | AC1 |
| `test_coin_ledger`: 13 vs 14 days, drop and return restarts | Fully-Automated | AC2 |
| `test_coin_ledger`: a missing snapshot day is neutral | Fully-Automated | AC3 |
| `test_coin_ledger`: rank 101-120 stays, exit at 7 not 6, cancelled exit | Fully-Automated | AC4 |
| `test_coin_ledger` + `test_onboarding_store`: inactive keeps class and entries, return resumes | Fully-Automated | AC5 |
| `test_coin_class`: stablecoin, wrapped, gold-backed, fund, normal; `test_universe_classes`: never scored | Fully-Automated | AC6 |
| `test_coin_class` + `test_universe_classes`: `unknown` stays out as `unclassified` | Fully-Automated | AC7 |
| `test_onboarding_resolver`: Trends pass goes live and is logged | Fully-Automated | AC8 |
| `test_onboarding_resolver`: Wikipedia pass; disambiguation and non-coin article refused | Fully-Automated | AC9 |
| `test_onboarding_resolver`: borderline per source goes to pending, signal missing with reason | Fully-Automated | AC10 |
| `test_onboarding_resolver`: no candidate gives reason and missing, never 0 | Fully-Automated | AC11 |
| `test_onboarding_resolver` + `test_trends_keywords`: ambiguity-list coin gets only a topic or an owner-approved term | Fully-Automated | AC12 |
| `test_narrative_proposals` + `onboarding_approve` tests: proposed, never auto-placed, approval checks the queries entry | Fully-Automated | AC13 |
| `test_onboarding` + `NewCoinsPanel.test.tsx` + routers key set + fixture-backed vitest load | Fully-Automated | AC14 |
| `test_onboarding_store` + `test_onboarding_reverse`: log append and reverse | Fully-Automated | AC15 |
| `test_refresh_attention` + `test_trends_keyword_guard` + loader tests: a new coin with no entry fails nothing | Fully-Automated | AC16 |
| `test_onboarding_settings`: settings drive the numbers; bad file refused | Fully-Automated | AC17 |
| Owner probe P-O1: a real run resolves a real unnamed coin and the log shows it | Agent-Probe (residual: live Google and Wikipedia are not reachable from the build environment) | AC18 |

## Tests and gates (commands)

```
uv run --project api python -m pytest api/tests/data/attention api/tests/scripts api/tests/analytics api/tests/routers api/tests/tooling_guards -q -p no:cacheprovider
cd web && pnpm exec vitest run components/narrative lib && pnpm exec tsc --noEmit
```
Baseline: save the FAILED ids of both commands on the untouched checkout first (Trends stage 2 found 41 API failures on untouched main, including `routers/test_discovery*.py`, `test_attention.py`, `test_discovery_price.py`, `test_equities_router.py`, and one web failure `lib/__tests__/plot-ink.test.ts`); report only new failures. On this Windows machine use `uv run --project api python -m pytest`, because bare `pytest` fails with a trampoline error. A diff-name check (changed files must be inside Touchpoints) replaces a gate script.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| A wrong automatic name gives a believable fake signal | all of identity, series, volume and ambiguity checks must pass; no volume means pending; the ambiguity list is never bypassed; every write is logged and reversible; shadow mode first |
| Probation or exit empties or distorts the universe | `mode: shadow` default; seeding keeps today's coins; the owner reviews the ledger for a week (P-O2) before `enforce` |
| The 120-row fetch or the coin-detail response differs from the docs | fail-closed steps that skip and report; P-O0 confirms before anything depends on them |
| Rate limits on CoinGecko, Google or Wikipedia | per-run caps, one stop on a refusal, retry on the next run, no loop |
| A new placement breaks count pins | the pins become property checks (O5) |
| The workflow line is not applied | the ledger, classifier and Wikipedia work without it; only `resolve_trends` waits for the one-line change |
| Overlay files conflict with owner files | owner wins by rule; a test asserts it; the loader never raises on an overlay |
| The ledger is lost or corrupt | atomic writes; a corrupt file is refused and kept; a missing ledger re-seeds as members with a log line (never mass-watching) |

## Test Infra Improvement Notes

(none identified yet)

## Cursor + RIPER-5 guidance

RIPER-5: this PLAN, then VALIDATE, then the owner's ENTER EXECUTE MODE for T223 with agent `riper-opus` on branch `claude/coin-onboarding`. EXECUTE order O0 to O7, each slice with its tests before the next; stop and report on scope expansion. After each slice: what is functional, what was tested, what the owner can check. Do not edit `.github/`.

## Resume and Execution Handoff

1. Selected plan file: `process/general-plans/active/narrative-baskets-coin-onboarding_01-11-26/narrative-baskets-coin-onboarding_PLAN_01-11-26.md`.
2. Last completed phase or step: PLAN written; nothing executed.
3. Validate-contract status: pending (VALIDATE not run).
4. Supporting context files loaded: the SPEC; the three read-only research passes (universe and snapshots, per-source name stores, narratives and web and tests); `trends_keywords.py`; `attention-refresh.yml` commit steps.
5. Next step for a fresh agent: run VALIDATE, get the owner's ENTER EXECUTE MODE, then start at O0.

## Validate Contract

(placeholder — vc-validate-agent writes this section before EXECUTE)
