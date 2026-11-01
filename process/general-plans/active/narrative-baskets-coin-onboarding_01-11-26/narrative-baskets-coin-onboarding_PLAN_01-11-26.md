---
name: plan:narrative-baskets-coin-onboarding
description: "PLAN for automatic coin onboarding (T223), revised after VALIDATE: a per-coin ledger with 14-day probation and a top-120 exit band, eligibility integration behind an enforce switch, a pegged/wrapped classifier, a GitHub-run resolver writing overlay files (owner files win), narrative proposals, a new-coins API and page, and shadow mode first. Includes the Validate Contract."
date: 01-11-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: plan
---

[MODE: PLAN]

# Narrative Baskets: automatic coin onboarding - PLAN (01-11-26, revision 2 after VALIDATE)

Date: 01-11-26
Status: ⏳ PLANNED
Complexity: COMPLEX (standard: one execution stream, seven slices, data, API, web and one workflow step). Risk tier RT3 (changes which coins are scored and writes owner-visible data automatically). SPEC: `narrative-baskets-coin-onboarding_SPEC_01-11-26.md` (merged, PR #215). Task id T223 and decision id D-31 are the next free ones (inference from `MASTER-PLAN` and `decisions.md`; EXECUTE re-checks). Branch of EXECUTE: `claude/coin-onboarding`. Context read: `process/context/all-context.md` and the testing router `process/context/tests/all-tests.md`.

## Overview and Context

Today a coin that enters the top 100 is in the universe the same day and shows up as gaps in every per-coin source; nothing writes names automatically. This plan adds (1) a ledger that tracks each coin's state with a 14-day probation and a 7-day exit band at rank 120, (2) one change at the eligibility choke point so watching, inactive and unclassified coins are not scored and members in the exit band stay scored, (3) a classifier for pegged and wrapped tokens, (4) a resolver that finds Wikipedia, Google Trends and Reddit/X names, checks them and writes them to overlay files the owner's files always override, (5) narrative proposals that never move placement, (6) one API route and a new-coins page, and (7) docs. Everything starts in shadow mode: the ledger, the classifier and the resolver run and log, and the universe does not change until the owner flips one setting.

## Owner decisions (closed 01-11-26)

| ID | Decision |
|---|---|
| O1 | Probation: 14 consecutive daily snapshots in the top 100; a missed snapshot day is neutral; a day outside the top 100 resets the count. |
| O2 | Exit: a member becomes inactive after 7 consecutive days outside the top 120; a return to the top 120 cancels it. Consequence made explicit by VALIDATE: under `enforce`, a member at rank 101 to 120 stays in the scored set (otherwise the band would change nothing); the percentile reference stays the top 100. Inactive coins keep history and entries; a returning coin repeats probation and resumes with them. |
| O3 | No minimum listing age. "Watching" is visible and collects data. |
| O4 | Classification is automatic; a coin the classifier cannot place stays out of scoring (`unclassified`) until the owner confirms it. |
| O5 | Names that pass every check go live automatically; borderline ones wait with evidence; no name means a reason and a missing signal, never 0. The ambiguity list and the approval rule of Trends stage 2 are never bypassed. |
| O6 | Narratives are proposed; the owner approves (the owner edits the narratives file from a printed, paste-ready placement). |
| O7 | Seed: every coin at rank 1 to 100 in the first snapshot after go-live is a member with class `normal` from the owner lists (no change to today's universe); ranks 101 to 120 are not seeded; probation applies only to later entrants. |
| O8 | The resolver runs in GitHub, not on the owner's PC (owner, 01-11-26; replaces the SPEC constraint "runs on the owner's PC"). It commits its data files like the other data jobs; no new push path to `main` is added (D-28). |

SPEC gap (recorded, SPEC stays frozen): the SPEC's Constraints and AC18 say "the owner's PC". O8 changes that to GitHub; the AC18 owner probe becomes P-O1 below (a real run and a log read). AC4 and AC13 are read as O2 consequence and O6 (approval = the owner edits the file).

## Acceptance Criteria

AC1 to AC18 of the merged SPEC. The Verification Evidence table maps each to its gate; AC18 is the owner probe P-O1.

## Implementation Checklist (EXECUTE order)

- [ ] O0 settings, shadow mode, pure ledger state machine with tests
- [ ] O1 snapshot widened to 120 rows with rank and name, ledger step in the daily refresh, seeding, tests
- [ ] O2 eligibility integration behind `enforce`, closed reasons extended in API and web, tests
- [ ] O3 classifier (pure rules plus a capped fetch step for watching coins), tests
- [ ] O4 resolver for Trends, Wikipedia and Reddit/X names with overlays, pending file, log and reverse tool, tests
- [ ] O5 narrative proposals, approval check, pin tests made property-based, tests
- [ ] O6 API route and New coins tab, tests
- [ ] O7 docs, D-31, owner probe notes; both gate commands green against the saved baseline

## Phase Completion Rules

A slice is NOT complete until: (1) its named tests pass; (2) the changed behaviour is run once through the real entry point on fixtures; (3) the stored state or response is read back and checked; (4) failure cases give the stated reason; (5) the owner confirms where an owner probe is named. Markers: ⏳ PLANNED, 🔨 CODE DONE, 🧪 TESTING, ✅ VERIFIED, 🚧 BLOCKED. Code-only completion is CODE DONE, never VERIFIED.

## Verified inputs (read-only, `main` at the time of writing)

| Fact | Where | Consequence |
|---|---|---|
| The snapshot holds the top 100, 14 snapshots deep, per coin `id, symbol, market_cap, volume_24h`; no rank, name, price or categories; the date is the UTC date of the run and a same-date write replaces | `universe_store.py` (`KEEP_SNAPSHOTS = 14`, `write_snapshot`), `coingecko_attention.py` `fetch_top100_markets` | the ledger keeps its own counters and its own `last_advanced_date`; ranks 101-120 need a wider fetch; classification needs another call |
| The markets fetch is `per_page=100`; `load_universe` and `load_universe_rows` sort by cap and take `[:TOP_N]` | `coingecko_attention.py:81`, `universe.py:36,63` | a 120-row fetch leaves the top-100 scoring rows identical (null caps sort last); the 120-row live shape is UNVERIFIED (P-O0) |
| `_universe_rows()` and `_symbols()` hand every runner all snapshot rows (no `[:100]`) | `refresh_attention.py:153-169` | widening to 120 would add 20 coins to every provider call, including paid X reads, unless capped (O1) |
| The one eligibility choke point is `universe_classes.build`, reached through `discovery.eligibility(cfg, rows)` by `discovery.py:444`, `discovery_history.py:227,261`, `sources.py:312`, `spot_volume_refresh.py:55`, `check_trends_keywords.py:505`, `eligible_discovery_symbols`; `defillama.py` reads `load_universe_rows` directly; Baskets uses `load_reference` | scout A and the O2 check | `eligibility` loads the ledger itself, so callers do not change |
| An in-universe coin with no narrative is excluded from scoring and listed `unassigned` | `discovery.py:404-470` | an unproposed narrative never scores a coin; unchanged |
| `REASONS` is a closed list used by the API model comment, the legacy `exclusion_list` sum, the web type, label and sentence, and fixture tests | D-29 (#206) | three new reasons follow the same ripple |
| `fetch_series` keeps only `total_volumes` (no prices); the markets rows keep no price | `coingecko_attention.py:119-124` | the classifier's price evidence needs a new price fetch; derived numbers only are stored |
| `categories.json` already holds per-category symbol lists (14 snapshots, 9 mapped category ids), written nightly and committed | `categories_store.py`, `refresh_attention._run_categories`, `attention_narrative_id_map.json` | narrative proposals reverse-look-up the symbol there; no new call |
| The Reddit/X and Trends loaders raise when a placed coin has no entry; `validate` raises on a duplicate topic or term and on unknown fields | `web_queries.py:296-299`, `trends_keywords.py:63,124-142` | overlays are validated per entry and merged in a separate pass that never raises; `load` and `safe_load` stay owner-only |
| Pins on counts and sets: placed 75 in `test_web_queries.py:84` and `test_narratives.py:43`; `len(topics) == 41` and the warnings list in `test_trends_keywords.py:43-49`; `KNOWN_KEYS` in `test_wiki_articles_shape.py` | scout B, C, VALIDATE | the count pins become property checks (O5); `3/75` in `test_attention_workflow_guard.py:260` is a literal fake line and is left alone |
| The data workflow commits `api/data/cache/attention/` recursively with `git add -f` and pushes as the bot; the verify step lists only wikipedia, coingecko and universe | `attention-refresh.yml:106,158-166` | `onboarding/` is covered; new steps must print explicit status lines because failures do not turn the job red |
| pytrends is installed only in the `refresh-extra` Trends step; that step has an 18-minute limit and the Trends budget uses most of it | `attention-refresh.yml:202-213`, `refresh_attention.py:50` | the onboarding network step is its own step with its own budget (printed owner diff) |
| Existing owner tools hold reusable logic but follow redirects and treat some passes as leads only; `check_trends_keywords.py` imports `api.analytics` | `check_trends_keywords.py:31-54,100-105`, `check_wiki_titles.py:40-72` | the pure verdict functions move into a library; auto-apply uses only the strict rules (O4) |

## O0. Settings, shadow mode, pure ledger (AC2, AC3, AC4, AC5, AC17)

Files (new): `api/data/coin_onboarding.json` (owner settings), `api/data/attention/coin_ledger.py` (pure state machine, no I/O), `api/data/attention/onboarding_settings.py` (loader and validator).
- Settings (named, validated; a bad file is refused with a plain message and the onboarding steps skip, never crash): `mode` (`shadow` default, `enforce`), `probation_days` 14, `exit_band_rank` 120, `exit_days` 7, `resolver_max_coins_per_run` 5, `classify_max_coins_per_run` 15, the check thresholds named in O3 and O4, plus two owner-edited maps: `confirmed_classes` (symbol to class) and `blocked_sources` (symbol to the sources the owner reversed). Owner edits live here, never in bot-written files, so they cannot race the CI rebase.
- Ledger document: top level `last_advanced_date` (UTC date of the last snapshot processed) and `seeded_at`; per coin id: `symbol, state (watching|member|inactive), first_seen, last_in_top100, last_in_top120, consecutive_top100, consecutive_outside120, class, class_evidence, class_source (owner|auto|confirmed), seeded, updated`.
- `advance(ledger, snapshot, settings)` uses `snapshot["date"]`, never the wall clock, and is a no-op when `snapshot.date <= last_advanced_date` (a same-day rerun counts the day once; the first run wins). Rules: entrant -> `watching` with count 1; a day in the top 100 adds 1 to a `watching` count; a day outside the top 100 resets a `watching` count to 0; a `watching` coin outside rank 120 for `exit_days` consecutive snapshots is removed from the ledger (logged); a `watching` coin with count `probation_days` -> `member`; a `member` outside rank 120 for `exit_days` consecutive snapshots -> `inactive`; a member's return to the top 120 resets `consecutive_outside120`; an `inactive` coin entering the top 100 -> `watching` (count restarts) keeping `class` and entries. A missing snapshot day changes nothing (no date, no call).
- `advance` requires a snapshot with at least 120 rows and a contiguous `rank` 1..120; otherwise it returns `unavailable` and changes nothing.
- Tests (new `test_coin_ledger.py`, `test_onboarding_settings.py`): enter; 13 days then drop; 14 days joins; drop and return restarts; missing day is neutral; same-date rerun is a no-op; stale or short snapshot is `unavailable`; rank 101-120 stays member; exit on day 7 not 6; return on day 5 cancels; watching coin removed after 7 days outside 120; inactive keeps class and returns to watching; settings valid, bad file, unknown key, owner maps.

## O1. Snapshot widening, ledger step, seeding (AC1, AC3, AC5)

Files: `api/data/attention/coingecko_attention.py` (fetch 120 rows; store `rank` = position + 1 and `name`; keep only symbols matching `[A-Z0-9_]{1,24}` and ids matching `^[a-z0-9][a-z0-9._-]{0,99}$`; quote ids in URLs), `api/data/attention/universe_store.py` (optional `rank`, `name`; older snapshots still load), new `api/data/attention/onboarding_store.py` (`api/data/cache/attention/onboarding/ledger.json`, atomic write, size cap), `api/scripts/refresh_attention.py` (new runner `_run_ledger`, source `ledger` added to `DEFAULT_SOURCES` after `universe` and before `signals`; special-cased in `main()` like `signals` so it never decides the exit code and prints an explicit line `ledger: ok` or `ledger: unavailable <reason>`).
- The runners' symbol list is capped: `_universe_rows` returns coins at rank 1 to 100 plus ledger members at rank 101 to 120 (a few coins), so provider and paid X cost stays flat; a test pins the runner symbol count. The Sources "universe" row keeps counting the top 100.
- The ledger step runs only when `snapshot.date == today` (UTC) and the snapshot has 120 contiguous ranks; otherwise it prints `ledger: skipped, stale snapshot` or `ledger: unavailable` and changes nothing.
- Seeding (O7): only when the ledger file is absent and `seeded_at` is unset: every coin at rank 1 to 100 becomes `member`, `seeded: true`, `class: normal`, `class_source: owner`, and the step logs the seeding. A corrupt ledger is refused and kept (never re-seeded); a lost ledger re-seeds once with a loud log line and the owner is told that probation progress was lost.
- Shadow mode: the step updates the ledger and the log; eligibility is unchanged.
- Tests: `test_coingecko_attention.py` (the row key set at `:56` gains `rank` and `name`; `per_page` is 120; hostile symbol and id are dropped), `test_universe_store.py` (rank and name round trip, optional), `test_onboarding_store.py` (atomic write, corrupt refused and kept, size cap), `test_refresh_attention.py` (the three `DEFAULT_SOURCES` literals at `:103,:139,:249` and the `RUNNERS` set at `:140`; ledger before signals; ledger never sets the exit code; runner symbol count capped; failed universe step skips the ledger), seeding tests (absent, present, corrupt, ranks 101-120 not seeded).

## O2. Eligibility integration behind `enforce` (AC1, AC4, AC6, AC7, AC16)

Files: `api/analytics/attention/universe_classes.py`, `api/analytics/attention/discovery.py` (`eligibility` and the legacy sum), `api/models/discovery.py` (comment), `web/lib/types/discovery.ts`, `web/components/narrative/DiscoveryExclusions.tsx`.
- `eligibility(cfg, rows, *, today=None, use_ledger=True)` loads the settings and the ledger itself (corrupt or missing ledger = no ledger = today's behaviour) and passes them to `build(rows, rules, venues=None, today=None, *, ledger=None, mode="shadow")`; none of the six callers change, except `discovery_history.py`, which passes `use_ledger=False` so past-day charts and coin histories keep today's meaning.
- Under `mode == "enforce"` with a ledger: precedence is `force_include` first, then the owner class lists and `not_tradeable`, then the ledger states, then the venue check. A coin whose ledger state is `watching` is out with reason `watching` (detail "in probation, N of 14 days"); `inactive` is out with reason `inactive`; a coin whose class is `unknown` (class_source `auto`) is out with reason `unclassified`; an auto class `stablecoin`, `wrapped_staked`, `commodity_backed` or `tokenized_fund` maps through `CLASS_REASON`. Ledger exclusions do not count in `checked` or `no_market` (so `data_suspect` is not skewed). Matching is by coin `id`; rows without an id are never gated.
- Exit band: under `enforce`, `eligibility` also takes the snapshot rows at rank 101 to 120 whose ledger state is `member` into the eligible input, so a member there stays scored; the percentile reference (`universe.load_universe`) is unchanged.
- Three new reasons `watching`, `inactive`, `unclassified` are added to `REASONS`, the legacy `exclusion_list` sum, the model comment, the web type, label and sentence.
- Tests: `test_universe_classes.py` (new cases: watching, inactive, unclassified, auto classes, force_include wins, owner list beats ledger, ledger exclusions do not skew `data_suspect`, id matching and rows without id, member at rank 101-120 stays, shadow unchanged, no ledger and corrupt ledger unchanged; the literals at `:225`, `:231`, `:272`, `:275`, `:277`, `:312`, `:314` are updated for the new zero-count keys), `test_discovery.py` (`:136`, `:579`, `:665` and the legacy sum), `routers/test_discovery.py` (`:109-110` `OLD_REASONS` gains the three keys), `test_discovery_history.py` (history unchanged under `enforce`), web `DiscoveryExclusions.test.tsx` (`:42,:47` length) and `DiscoveryTab.test.tsx` (`:44`).

## O3. Classifier (AC6, AC7)

Files (new): `api/data/attention/coin_class.py` (pure rules), additions to `coingecko_attention.py` (a coin-detail fetch and a price-statistics fetch), `api/scripts/refresh_attention.py` (source `classify`, run in the onboarding step, not in `DEFAULT_SOURCES`).
- Evidence per coin, from one CoinGecko coin-detail call (UNVERIFIED live: `categories`, `name`, `asset_platform_id`) and one `market_chart` call for prices; only derived numbers are stored in the ledger (`price_min`, `price_max`, `n_days`, `last_price`), never the series.
- Rules: stablecoin = a stablecoin category (or a `USD`-style symbol or name pattern) AND a tight window (max over min under 2%); wrapped or staked = a wrapped, liquid-staking or bridged category or a name pattern; commodity backed = a tokenized gold or commodity category; tokenized fund = a tokenized treasury or fund category; `normal` only when the category list is non-empty and no rule matched; an empty or failed response, or a single signal, gives `unknown`. Price alone never classes a coin.
- Owner class lists in `discovery.json` win (class_source `owner`); `confirmed_classes` in `coin_onboarding.json` win over auto (class_source `confirmed`). `classify` in `universe_classes` stays owner-lists only; the auto class lives in `coin_class` and the ledger and is merged by `build` (O2). The legacy `STABLECOIN_SYMBOLS` constant (10 symbols) is not read by the classifier; `_symbols` keeps using it as today (noted, unchanged).
- The step takes at most `classify_max_coins_per_run` coins (watching and unknown first), reuses a stored class, paces at the existing one call per 6 seconds, stops on a 429, and runs in the onboarding step with its own budget. A failed fetch leaves `unknown`, never `normal`.
- Tests (new `test_coin_class.py`): stablecoin by category and band, by pattern and band, category only (unknown), band only (unknown), wrapped by category, gold-backed, fund, normal with categories, empty categories (unknown), failed fetch (unknown), owner list wins, confirmed wins, near-1.00 coin without category stays unknown.

## O4. Resolver, overlays, pending file, log, reverse (AC8-AC12, AC15, AC16)

Files (new): `api/data/attention/onboarding_resolver.py` (pure checks), `api/data/attention/onboarding_sources.py` (fetchers and the verdict functions moved out of `check_trends_keywords.py` so `api.data` does not import `api.analytics`; the script keeps working from the library), `api/scripts/onboarding_reverse.py`; changed: `trends_keywords.py`, `web_queries.py`, `refresh_attention.py` (wiki loader and sources `resolve_wiki`, `resolve_trends`), `check_wiki_titles.py` (compare the returned page title).
- Overlays (written only by the resolver under `api/data/cache/attention/onboarding/`): `trends_keywords_auto.json`, `wiki_articles_auto.json`, `attention_queries_auto.json`. Merging is a separate entry point (`load_merged`) used by `refresh_attention`, `sources` and the check scripts; `load` and `safe_load` stay owner-only and ignore the overlay, and an explicit path argument never merges, so every test that reads the shipped files is unaffected. The overlay path is read from `cache.CACHE_ROOT` at call time. Each overlay entry is validated alone with the owner checkers (`SYMBOL_RE`, topic and term patterns, `NAME_RE`, no `approved`, no `no-keyword`, no `_anchor` or `_ambiguous`); extra keys (`source`, `resolved_at`) are stripped before merge. An entry that collides with the owner file, another overlay entry (topic, term or title) or the anchor is dropped to pending with a log line; the merge never raises and an owner entry always wins. Overlay Reddit/X entries are not added to `q.coins` (which drives stream matching and `placed` checks) until the coin is placed (O5).
- Trends: candidates from the suggestions endpoint. Auto-apply only for the strict rule: an exact-name topic typed as a cryptocurrency, used by no other symbol or the anchor, whose series passes the daily verdict (`fetch_alone` `ok`, `series_stats`), AND whose stored CoinGecko volume series (the 100-day `total_volumes` store, which exists even as `insufficient-history`) overlaps at least `IDENTITY_MIN_DAYS` (60, about 66 with smoothing) days and correlates above `IDENTITY_MIN_CORR`. A coin with less volume history stays pending by design and the log and page show "volume history N of 66 days"; qualified terms, lead rules (`ticker-title`, `bracket`), names guessed from the id, and several equally likely entities always go to pending. A coin on the ambiguity list is never given an automatic term (topic only, and only under the strict rule). The `one_term_spike` test is not used (it is a no-op for one series). `tg.analyze` is not the gate (it requires clean-rising).
- Wikipedia: the candidate title comes from the snapshot `name`; checks: `canonical title == candidate` (no redirect), the name or symbol appears in the first extract sentence, whole-word crypto terms (not substrings), not a disambiguation page, the title is not already assigned to another symbol (owner or overlay), and the pageviews fetch returns enough days. Pass -> overlay.
- Reddit/X: an auto entry is always `cashtag_only` (a bare name is never auto-applied); a name that fails `NAME_RE` (non-ASCII, over length) goes to pending.
- Borderline candidates go to `pending.json` with evidence; the source reads missing with the reason; nothing is written to an overlay. No candidate passes: the reason is recorded in the ledger, never a zero.
- Log: `onboarding/log/<UTC date>.json`, append-only, per coin: source, action `applied|pending|none`, evidence summary, previous value; strings are stripped of control and bidi characters and capped at 200 characters; file sizes are capped.
- Output hygiene: the steps print only counts and fixed tokens (never a name, id or evidence string to stdout), so no `::command::` or `startswith` marker in the workflow can be injected; the commit message stays static.
- Reverse: `onboarding_reverse.py SYMBOL SOURCE` validates both arguments (SYMBOL pattern, SOURCE from a closed set), refuses a placed coin (both loaders would raise), removes the overlay entry, appends to the log, and records `blocked_sources` through a printed paste-ready line for `coin_onboarding.json` (the owner applies it; bot files never carry owner edits). It does not purge a first-wins stored series (stated in the operator note).
- Budget and workflow: the onboarding network work (`classify`, `resolve_wiki`, `resolve_trends`) is ONE new step in the `refresh-extra` job, `continue-on-error`, with its own `timeout-minutes`, its own time budget (a coin cap per run, default 5; stop at the first 429; backoff and retry the next run) and pytrends installed like the Trends step, placed after the existing Trends step. It prints explicit status lines `classify: ok N/M`, `resolve_wiki: ...`, `resolve_trends: ...`. This is the only `.github` change; the worker must not make it. EXECUTE prints the exact diff in the EXEC-REPORT (the new step, and adding the new sources to the verify listing if wanted) and the owner applies it; `test_attention_workflow_guard.py` is updated in the same diff because it pins step order and `--sources trends ` text. Until applied the ledger runs in the default refresh and the network work can be run by hand (`python -m api.scripts.refresh_attention --sources classify,resolve_wiki,resolve_trends`); owner runs must not leave uncommitted edits to tracked onboarding files (a fast-forward pull would stop).
- Tests (new `test_onboarding_resolver.py`, `test_onboarding_sources.py`, `test_onboarding_reverse.py`, `test_onboarding_overlay.py`; changed `test_trends_keywords.py`, `test_web_queries.py`, `test_check_trends_keywords.py`, `test_check_wiki_titles.py`): pass, borderline, none per source with fakes; the strict Trends rule (exact topic, unique, volume overlap and correlation) and each way to fall to pending (no volume, short volume, lead rule, qualified term, several entities); an ambiguity-list coin gets no automatic term; Wikipedia redirect, disambiguation, wrong-subject and duplicate-title refusals; Reddit/X `cashtag_only` and bad-name pending; overlay collision, anchor collision, bad entry and hostile name never raise and never break the owner file; owner beats overlay; overlay absent loads as before; default `load()` ignores the overlay; log append, control-character stripping; reverse refuses a placed coin; 429 stops the step and leaves coins pending; stdout carries only fixed tokens; no test reaches the network (use the local `boom` patch pattern with `isolated_cache`; there is no shared network-block fixture in these test folders).

## O5. Narrative proposals and pin tests (AC13)

Files (new): `api/data/attention/narrative_proposals.py`, `api/scripts/onboarding_approve.py`; changed tests `test_narratives.py`, `test_web_queries.py`, `test_trends_keywords.py`.
- Proposals: for a coin with no placement and class `normal` and state `member`, reverse-look-up its symbol in the latest `categories.json` (the nightly per-category symbol lists for the 9 mapped category ids) and list every matching narrative id with the evidence; the proposal never picks one when several match and never touches `attention_narratives.json`. Narratives with no mapped category (gaming, store of value, payments, exchange tokens) are placed by hand only. Proposals are written to `onboarding/narrative_proposals.json`.
- `onboarding_approve.py SYMBOL NARRATIVE` (owner run) validates its arguments (SYMBOL pattern, narrative id pattern), requires state `member`, a Reddit/X queries entry AND a Trends keyword entry (owner or overlay), prints a paste-ready placement for `attention_narratives.json` built with `json.dumps` and stripped of control characters, and lists the pins that a placement touches; it writes nothing. Approval means the owner applies the printed edit (AC13 read accordingly).
- Pins become property checks so a deliberate placement needs no test edit: `test_narratives.py:43` becomes `set(SNAPSHOT) - NOT_PLACED <= set(m.primary)` and `set(m.unassigned) >= NOT_PLACED` (extras must each have a queries entry); `test_web_queries.py:84` becomes `len(placed) == len(set(placed))`, `"SOL" in placed` and `set(placed) <= set(q.coins)`; `test_trends_keywords.py:43-49` replaces `len(topics) == 41` and the exact warnings with property checks; `test_attention_workflow_guard.py:260` is left alone (a literal fake line).
- Tests: proposal from fixture categories; several matches listed; unmapped category gives none; non-normal class or non-member gives none; no auto-placement; the approve tool refuses a coin without a queries or keyword entry; hostile argument refused; the converted pins pass with an extra placed coin.

## O6. API route and new-coins page (AC14)

Files: `api/routers/discovery.py` (new `GET /api/narrative/onboarding`, no registration needed), `api/models/discovery.py` (`OnboardingResponse`, `OnboardingCoin`), `api/analytics/attention/onboarding.py` (builds rows from the ledger, overlays, pending file and proposals), `web/lib/api/discovery.ts` (`fetchOnboarding`), `web/lib/types/discovery.ts`, `web/components/narrative/NewCoinsPanel.tsx`, `web/components/narrative/NarrativeTabs.tsx` (a "New coins" tab and a `fetchOnboarding` prop like `fetchDiscovery`).
- `OnboardingResponse`: `mode` (`shadow|enforce`), `as_of`, `status` (`ok|no-ledger|corrupt`), the settings numbers (`probation_days`, `exit_band_rank`, `exit_days`), `coins[]`. Per coin: `symbol, state, days_in_top100, class, class_source, class_evidence, sources: {wikipedia, trends, reddit_x: {state: name|pending|missing|none, value, reason}}, pending[], proposal`. Watching, recent members, inactive and pending coins are listed; a coin with nothing pending shows none. Read-only, no network; strings are escaped as text (links, if any, use a fixed host and `encodeURIComponent`).
- In shadow mode the page shows a banner (`data-testid="onboarding-shadow"`: "shadow: the universe is not changed"); the copy avoids the words `confirmed` and `badge` (the `NarrativeTabs` vocabulary test bans them).
- Tests: `test_onboarding.py` (rows from fixtures, no ledger, corrupt ledger), `routers` route test with the local `boom` pattern and `isolated_cache`, web `NewCoinsPanel.test.tsx`, `NarrativeTabs.test.tsx` (`:32-34` tab list and the "has two tabs" title now list three) and `web/e2e/narrative.spec.ts:90-92` (the same text; Playwright is not run by the gates, the edit is made anyway), a fixture-backed vitest load.

## O7. Docs and probes

- `process/context/decisions.md` D-31; one line each in `process/context/data-sources/all-data-sources.md` and `process/context/current-state.md`; an operator note in the EXEC-REPORT: how to read the log, reverse an entry, confirm a class (`confirmed_classes`), approve a narrative, flip `mode` to `enforce`, and the printed workflow diff.
- Owner probes (not run by EXECUTE): **P-O0** the live shapes (a 120-row markets response with `name` and ordered by cap; one coin-detail response with `categories`, `asset_platform_id`; the price-statistics fetch; the suggestions entity types) via one owner run of `refresh_attention --sources universe,ledger,classify` and reading the log, before anything depends on them; **P-O1** one run of `resolve_wiki,resolve_trends` on a real unnamed coin (AC18); **P-O2** after a week in shadow, review the ledger and the New coins page, then set `mode` to `enforce`.

## Public Contracts

| Contract | Change |
|---|---|
| `api/data/cache/attention/universe.json` snapshot | each coin gains optional `rank` and `name`; 120 rows are fetched; scoring still takes the first 100 (plus ledger members at 101-120 under `enforce`); older snapshots still load |
| `api/data/coin_onboarding.json` | new owner settings file (`mode`, `probation_days`, `exit_band_rank`, `exit_days`, caps, thresholds, `confirmed_classes`, `blocked_sources`) |
| `api/data/cache/attention/onboarding/` | new bot-written directory: `ledger.json`, `*_auto.json` overlays, `pending.json`, `narrative_proposals.json`, `log/<date>.json`; committed by the existing recursive step |
| Owner files (`trends_keywords.json`, `wiki_articles.json`, `attention_queries.json`, `attention_narratives.json`) | unchanged; the owner entry always wins over an overlay; `load` and `safe_load` stay owner-only; `load_merged` is new |
| `eligibility` and `universe_classes.build` | `eligibility` loads settings and ledger itself (keyword `use_ledger`); `build` takes keyword-only `ledger` and `mode`; three new reasons `watching`, `inactive`, `unclassified`; `excluded_counts` gains three always-present keys (additive; old web builds fall back to the raw reason) |
| `GET /api/narrative/onboarding` | new, read-only |
| `refresh_attention` sources | `DEFAULT_SOURCES` gains only `ledger`; `classify`, `resolve_wiki`, `resolve_trends` run in the new owner-applied `refresh-extra` step or by hand; all print fixed-token status lines |
| `trends_runs`, `store`, `signal_snapshots`, `discovery_history` | unchanged; history keeps today's meaning |

## Touchpoints

Changed: `api/data/attention/coingecko_attention.py`, `universe_store.py`, `trends_keywords.py`, `web_queries.py`; `api/analytics/attention/universe_classes.py`, `discovery.py`; `api/models/discovery.py`; `api/routers/discovery.py`; `api/scripts/refresh_attention.py`, `check_wiki_titles.py`, `check_trends_keywords.py` (verdict functions move to the library); `web/lib/types/discovery.ts`, `web/lib/api/discovery.ts`, `web/components/narrative/DiscoveryExclusions.tsx`, `NarrativeTabs.tsx`; new files named per slice; the tests named per slice (including `test_coingecko_attention.py`, `test_universe_store.py`, `test_refresh_attention.py`, `test_universe_classes.py`, `routers/test_discovery.py`, `test_discovery_history.py`, `test_attention_workflow_guard.py`, `NarrativeTabs.test.tsx`, `DiscoveryExclusions.test.tsx`, `DiscoveryTab.test.tsx`, `web/e2e/narrative.spec.ts`); the three docs of O7. Read only: `store.py`, `signal_snapshots.py`, `trends_runs.py`, `trends_groups.py`, `categories_store.py`. NOT touched by the worker: `.github/**` (the diff is printed), `deploy/`, `attention_pc_refresh.py`, the owner data files, `discovery.json` class lists, weights.

## Blast Radius

About 45 files (about 16 new), API, web and data. Live effect in shadow mode: none on scores or the universe; new files appear under `api/data/cache/attention/onboarding/` after the next refresh; the runner symbol count is unchanged. Live effect after `enforce`: new entrants are not scored for 14 days, unknown classes stay out, and members at rank 101 to 120 stay scored. Risk class RT3, mitigated by shadow mode, owner-file-wins merging, strict auto-apply rules and the reversible log. No provider call is made by any test.

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| `test_coin_ledger`: new entrant is `watching`; `test_universe_classes`: a `watching` coin is out under `enforce` and not in the reference | Fully-Automated | AC1 |
| `test_coin_ledger`: 13 vs 14 days, drop and return restarts | Fully-Automated | AC2 |
| `test_coin_ledger`: a missing snapshot day is neutral; same-date rerun is a no-op | Fully-Automated | AC3 |
| `test_coin_ledger` + `test_universe_classes`: rank 101-120 stays member and stays scored; exit at 7 not 6; cancelled exit | Fully-Automated | AC4 |
| `test_coin_ledger` + `test_onboarding_store`: inactive keeps class and entries, return resumes | Fully-Automated | AC5 |
| `test_coin_class`: stablecoin, wrapped, gold-backed, fund, normal; `test_universe_classes`: never scored | Fully-Automated | AC6 |
| `test_coin_class` + `test_universe_classes`: `unknown` stays out as `unclassified`; seeded members are `normal` | Fully-Automated | AC7 |
| `test_onboarding_resolver`: the strict Trends rule applies and is logged | Fully-Automated | AC8 |
| `test_onboarding_resolver` + `test_check_wiki_titles`: Wikipedia pass; redirect, disambiguation, wrong subject, duplicate refused | Fully-Automated | AC9 |
| `test_onboarding_resolver`: borderline per source (short volume, lead rule, qualified term, bad name) goes to pending, signal missing with reason | Fully-Automated | AC10 |
| `test_onboarding_resolver`: no candidate gives reason and missing, never 0 | Fully-Automated | AC11 |
| `test_onboarding_resolver` + `test_onboarding_overlay`: ambiguity-list coin gets no automatic term; owner entry beats overlay | Fully-Automated | AC12 |
| `test_narrative_proposals` + approve-tool tests: proposed, never auto-placed, approval needs queries and keyword entries; converted pins pass with an extra placement | Fully-Automated | AC13 |
| `test_onboarding` + `NewCoinsPanel.test.tsx` + `NarrativeTabs.test.tsx` + routers route test + fixture-backed vitest load | Fully-Automated | AC14 |
| `test_onboarding_resolver` + `test_onboarding_reverse`: log append, control-character stripping, reverse | Fully-Automated | AC15 |
| `test_refresh_attention` + `test_trends_keyword_guard` + loader tests: a new coin with no entry fails nothing; a bad overlay entry never breaks the owner file | Fully-Automated | AC16 |
| `test_onboarding_settings`: settings drive the numbers; bad file refused | Fully-Automated | AC17 |
| Owner probe P-O1: a real run resolves a real unnamed coin and the log shows it | Agent-Probe (residual: live Google and Wikipedia are not reachable from the build environment) | AC18 |

## Tests and gates (commands)

```
uv run --project api python -m pytest api/tests/data/attention api/tests/scripts api/tests/analytics api/tests/routers api/tests/tooling_guards -q -p no:cacheprovider
cd web && pnpm exec vitest run components/narrative lib && pnpm exec tsc --noEmit
```
Real test paths: `api/tests/data/attention/` (web_queries, universe_store, trends_keywords, trends_keyword_guard, wikipedia, wiki_articles_shape, coingecko_attention), `api/tests/analytics/attention/` (narratives, universe_classes, discovery), `api/tests/scripts/` (refresh_attention*, check_*), `api/tests/tooling_guards/test_attention_workflow_guard.py`, `api/tests/routers/test_discovery.py`. Baseline: save the FAILED ids of both commands on the untouched checkout first (Trends stage 2 found 41 API failures on untouched main, among them `routers/test_discovery*.py`, `test_attention.py`, `test_discovery_price.py`, `test_equities_router.py`, and one web failure `lib/__tests__/plot-ink.test.ts`); report only new failures. On this Windows machine use `uv run --project api python -m pytest`, because bare `pytest` fails with a trampoline error. A diff-name check (changed files must be inside Touchpoints) replaces a gate script.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| A wrong automatic name gives a believable fake signal | the strict rule (exact topic, unique, volume overlap and correlation) is the only auto path; everything else is pending; the ambiguity list is never bypassed; every write is logged and reversible; shadow mode first |
| Trends auto-apply is rarely reachable for brand-new coins (volume history under 66 days) | stated and by design: those coins wait for the owner with "volume history N of 66 days"; Wikipedia and the snapshot-based steps are not affected |
| Probation or exit empties or distorts the universe | `mode: shadow` default; seeding keeps today's coins; the owner reviews the ledger for a week (P-O2) before `enforce` |
| The 120-row fetch or the coin-detail response differs from the docs | fail-closed steps that skip and print `unavailable`; P-O0 confirms before anything depends on them |
| Rate limits on CoinGecko, Google or Wikipedia | per-run caps, one stop on a refusal, retry on the next run, no loop; a separate step with its own timeout |
| A new placement breaks count pins | the pins become property checks (O5) |
| The workflow step is not applied | the ledger works in the default refresh; only the network steps wait for the owner's step |
| Overlay files conflict with owner files | owner wins by rule; per-entry validation; collisions go to pending; `load`/`safe_load` stay owner-only; tests assert it |
| The ledger is lost or corrupt | atomic writes; a corrupt file is refused and kept; a missing ledger re-seeds once with a loud log (probation progress lost, stated) |
| Hostile or odd coin names, ids, titles | symbol and id patterns at snapshot write; per-entry validation; fixed-token stdout; sanitized JSON strings; escaped web text |
| Owner edits race the bot rebase | owner edits (`confirmed_classes`, `blocked_sources`) live only in `coin_onboarding.json` |

## Test Infra Improvement Notes

(none identified yet; VALIDATE found that these test folders have no shared network-block fixture and that the `boom` patch is copied per file: a shared fixture would help.)

## Cursor + RIPER-5 guidance

RIPER-5: this PLAN, VALIDATE (done below), then the owner's ENTER EXECUTE MODE for T223 with agent `riper-opus` on branch `claude/coin-onboarding`. EXECUTE order O0 to O7, each slice with its tests before the next; stop and report on scope expansion. After each slice: what is functional, what was tested, what the owner can check. Do not edit `.github/`.

## Resume and Execution Handoff

1. Selected plan file: `process/general-plans/active/narrative-baskets-coin-onboarding_01-11-26/narrative-baskets-coin-onboarding_PLAN_01-11-26.md`.
2. Last completed phase or step: PLAN written and VALIDATE fix cycle applied; nothing executed.
3. Validate-contract status: written (below). First-pass net gate BLOCKED (2 FAILs); one fix cycle applied; the plan needs the owner's acceptance of the CONDITIONAL gate before EXECUTE.
4. Supporting context files loaded: the SPEC, three read-only research passes, nine VALIDATE agent reports.
5. Next step for a fresh agent: the owner accepts the Validate Contract below and gives ENTER EXECUTE MODE; then start at O0.

## Validate Contract

Validated 01-11-26 by a two-layer fan-out (4 dimension agents, 5 section agents), read-only, against `main` after PR #217 merged. Live behaviour needed a call in three places, all covered by probe P-O0 (VC-FEASIBILITY-PROBE-NEEDED): the 120-row markets shape, the coin-detail shape, Google suggestion entity types.

| Layer 1 dimension | First pass | After fixes |
|---|---|---|
| Infra fit | CONCERN | fixed (runner symbol cap, explicit status lines, separate step with own budget, idempotence) |
| Test coverage | CONCERN | fixed (real paths, missing pins named, `DEFAULT_SOURCES` and key-set literals listed) |
| Breaking changes | CONCERN | fixed (overlay merge entry point, `eligibility` loads the ledger, exit-band scoring, old data safe) |
| Security surface | CONCERN | fixed (strict auto rule, Wikipedia identity, output hygiene, id and symbol patterns, owner edits in the owner file) |

| Layer 2 section | First pass | After fixes |
|---|---|---|
| O0 + O1 ledger and refresh step | CONCERN | fixed |
| O2 eligibility | FAIL | fixed (router key set grows; ledger path; history unchanged; seeded class) |
| O3 classifier | CONCERN | fixed (price fetch, stored derived numbers, two-signal rule) |
| O4 resolver | FAIL | fixed (stored CoinGecko volume instead of Binance; strict rule; overlay merge; own budget) |
| O5 + O6 proposals, API, web | CONCERN | fixed (categories store, keyword entry required, property pins, tab test edits) |

First-pass totals: 2 FAIL, 7 CONCERN; net gate BLOCKED. All FAILs and CONCERNs were fixed in the plan text (P1 to P24 below). Net gate after the fix cycle: CONDITIONAL (the fixes are not re-validated by a second fan-out; the owner's acceptance is the recorded decision).

### Proposed Plan Updates applied

| # | What changed | Where | Why |
|---|---|---|---|
| P1 | `last_advanced_date`; use the snapshot date; same-date no-op; stale or short snapshot is `unavailable` | O0, O1 | a same-day rerun or stale snapshot double-counted |
| P2 | Seed rank 1-100 only, class `normal` from owner lists; re-seed only when absent; corrupt refused | O0, O1 | ranks 101-120 would skip probation; seeded coins would read `unknown` and empty the universe |
| P3 | Runners receive rank 1-100 plus members to 120; symbol count pinned | O1 | 120 rows would add 20 coins to every provider call, including paid X |
| P4 | `ledger` special-cased in `main()`, never sets the exit code, prints an explicit line | O1 | a generic runner path printed "0/0 ok" and could fail the run |
| P5 | `DEFAULT_SOURCES` gains only `ledger`; network work is one new `refresh-extra` step with its own timeout and budget (owner-applied diff) | O1, O4 | the Trends step has little headroom; verify step lists only three sources |
| P6 | `eligibility` loads settings and ledger itself; `build` takes keyword-only `ledger` and `mode` | O2 | no ledger path existed; the planned signature was invalid |
| P7 | Precedence and id matching; ledger exclusions do not count toward `data_suspect`; `discovery_history` keeps `use_ledger=False` | O2 | point-in-time reads must not change |
| P8 | Members at rank 101-120 stay scored under `enforce`; reference stays the top 100 | O2 | otherwise the exit band changed nothing |
| P9 | All exact-set literals named: `test_universe_classes.py:225,231,272,275,277,312,314`, `routers/test_discovery.py:109-110`, `test_discovery.py:136,579,665`, web exclusion tests | O2 | the first draft said "key set unchanged"; it grows by three keys |
| P10 | Price fetch added; only derived numbers stored; stablecoin = category (or pattern) AND tight band; price alone never classes; empty categories give `unknown`; cap and own step | O3 | the plan assumed prices already fetched |
| P11 | Trends volume check uses the stored CoinGecko 100-day volume series, needs 60+ overlap days; younger coins wait for the owner | O4 | Binance volume is blocked on the runner (451) and unavailable for new coins |
| P12 | Auto-apply only for the strict rule; qualified terms, lead rules and id-derived names go to pending | O4 | those are documented leads, not matches |
| P13 | Wikipedia: canonical title equals candidate, name or symbol in the first sentence, whole-word crypto terms, no duplicate title | O4 | the existing check follows redirects and matches substrings |
| P14 | Reddit/X auto entries are `cashtag_only`; bad names go to pending; overlay entries stay out of `q.coins` until placed | O4 | stream matching and `placed` checks iterate `q.coins` |
| P15 | Overlays merged through `load_merged` only; per-entry validation; collisions go to pending; `load`/`safe_load` owner-only | O4 | `validate` raises on duplicates and unknown fields and would stop Trends for every coin; pinned tests read the shipped file |
| P16 | Output hygiene: fixed-token stdout, sanitized JSON strings, symbol and id patterns, quoted URL parts | O1, O4 | injection into workflow markers, paths and URLs |
| P17 | Owner edits (`confirmed_classes`, `blocked_sources`) live in `coin_onboarding.json`; reverse refuses a placed coin | O0, O4 | bot-written files race the CI rebase; reversing a placed coin raises |
| P18 | Narrative proposals read `categories.json`; list all matches; only `normal` members; the approve tool requires queries AND keyword entries | O5 | the snapshot has no categories; the keyword loader also raises for a placed coin |
| P19 | Pin conversions: `test_narratives.py:43`, `test_web_queries.py:84`, `test_trends_keywords.py:43-49`; the `3/75` guard line is left alone | O5 | it is a literal fake line, not a count |
| P20 | Response fields `mode`, `as_of`, `status`, settings numbers; shadow banner testid; avoid banned words | O6 | the banner and the no-ledger state need data |
| P21 | `NarrativeTabs.test.tsx:32-34` and `web/e2e/narrative.spec.ts:90-92` listed; local `boom` pattern instead of a missing shared fixture | O6, O4 | tab list and network-block pattern |
| P22 | A `watching` coin outside rank 120 for the exit days is removed from the ledger | O0 | watchers would pile up |
| P23 | Real test paths listed; `test_coingecko_attention.py:56` key set and `test_universe_store.py` added | Tests | the first draft cited wrong paths |
| P24 | AC4 and AC13 read as O2 consequence and O6 (approval = the owner applies the printed edit) | Owner decisions | wording gaps against the frozen SPEC |

### Execute-Agent Instructions

| # | Instruction | Trigger |
|---|---|---|
| E1 | Save the baseline FAILED ids of both gate commands first; report only new failures. | start |
| E2 | Do not touch `.github/**`; print the exact new `refresh-extra` step diff, the `test_attention_workflow_guard.py` edits it needs, and the verify-listing line in the EXEC-REPORT. | O4 |
| E3 | Find every reference with the language server before changing a signature (`build`, `eligibility`, `load_universe_rows`, `_universe_rows`). | O1, O2 |
| E4 | Every step that talks to a provider is fail-closed: skip, print a fixed-token `unavailable` line, change nothing. | O1, O3, O4 |
| E5 | No test may reach the network; copy the local `boom` patch pattern with `isolated_cache`. | all |
| E6 | Never write names, ids or evidence strings to stdout; JSON only, sanitized and capped. | O4 |
| E7 | Default `mode` is `shadow`; no code path may flip it. | O0 |
| E8 | Stop and report on scope expansion, a newly failing baseline test outside the plan, a live request, or a decision not in the plan. | all |

### Backlog artifacts

| Artifact | What it tracks |
|---|---|
| Shared network-block test fixture | the `boom` patch is copied per file; a shared fixture would cut duplication |
| Auto-class evidence tuning | the 2% band and category lists are placeholders until P-O0 shows the real shapes |
| Volume history for new coins | Trends auto-apply needs about 66 days of CoinGecko volume; consider a second volume source later |
