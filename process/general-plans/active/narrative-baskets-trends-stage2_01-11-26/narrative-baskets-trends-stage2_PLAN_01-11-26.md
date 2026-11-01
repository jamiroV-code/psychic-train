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
| D1 | The ambiguity list and the approvals live in `api/data/trends_keywords.json`: a reserved key `_ambiguous` (list of symbols) and an optional `"approved": "<exact term>"` on a coin's own `term` entry. The approval is bound to the term (SPEC: the approval is stored with the term): `keyword_status` pulls a listed coin's term only when `approved` equals the entry's `term` exactly, so editing the term without re-approving it stops the pull. (VALIDATE change: was a boolean flag.) |
| D2 | The tester proposes, the owner applies. No tool writes `trends_keywords.json`. |
| D3 | The selection rule runs in the campaign report (`--report`), pure and read-only. The daily run only reads the keyword file. |
| D4 | Variant agreement only warns: `unconfirmed` when a usable variant moves against the main term, `unchecked` when no usable variant or no stored volume exists. It never rejects by itself. |
| D5 | A changed keyword is not spliced with the old one. The stored series (replace-series by symbol) always reflects the latest successful pull, so a changed keyword re-pulls its whole 100-day window under the new term; it never mixes two terms. Per-day provenance lives in the run files: each coin record gains `keyword` (the keyword assigned and attempted that day). Limit, stated and tested: if a changed keyword's pull fails, the stored series still belongs to the older term while the run record names the new one. Archives and signal snapshots carry no keyword and are unchanged. (VALIDATE change: was "old days stay labelled".) |
| D6 | The waking-up watch list is shown on the Sources panel only, not in any score. |
| D7 | Ambiguity list = the 12 of the T125 review plus SKY, PI, JST, NEAR, GRAM, RAIN, M, CC, LIT, NIGHT, STABLE (23). |

### Owner input before EXECUTE: Q1 ANSWERED (owner, 01-11-26)

Q1 (answered). Approved, seeded as `"approved": "<current term>"` by EXECUTE (R6): ONDO (`ondo crypto`), PEPE (`Pepe coin`), TRX (`tron crypto`), APT (`aptos crypto`), CRO (`cronos crypto`), MORPHO (`morpho crypto`). APT, CRO and MORPHO are approved although the campaign reads them as waking up (median 0, no usable group): the owner wants them tracked daily and shown on the watch list when they surge. NOT approved, left as they are, so they stop being pulled and show as waiting for approval or needs owner after merge: CC, JST, RAIN, SKY, GRAM, LIT, NIGHT, M, STABLE (STABLE is also untested). Other listed coins already use a topic (BNB, HBAR, ICP, LINK, NEAR, PI, SHIB, SOL) and need no approval. Evidence from the campaign that informed the answer:

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

Files: `api/data/attention/trends_keywords.py`, `api/data/trends_keywords.json`, `api/data/attention/trends.py`, `api/data/attention/trends_candidates.py`, `api/scripts/probe_trends.py` (the two former `NAME_RISK_SYMBOLS` sites), and the tests listed below. Everything that breaks when the constant and the status rule change is migrated inside S1, so the suite is green at the end of S1.

Rules (validator, applied at load; a bad file is `bad keyword file`, never a crash, as today):
- R1. Reserved key `_ambiguous`, handled in `validate()` before the symbol-key loop (a lower-case key fails `SYMBOL_RE` today): a list of unique `str` upper-case symbols matching `SYMBOL_RE`, none of them `_anchor`. Missing key = empty list so older files load; the shipped-list test (S1) protects the shipped file. `KeywordMap` gains a defaulted field `ambiguous: frozenset[str]` placed after `not_placed` (tests build it positionally).
- R2. `approved` is added to `ALLOWED_FIELDS`. A coin entry may carry `"approved": "<term>"` (a string equal to that entry's `term`); allowed only on an entry with `term` and rejected on topic, no-keyword and `_anchor` entries, and rejected when it differs from `term` (so a duplicate or stale approval is an error, not silently ignored).
- R3. Every symbol in `_ambiguous` must have an entry in the file, checked independent of `placed_symbols` (the existing placed-coin rule only runs when `placed_symbols` is passed).
- R4. `keyword_status(km, symbol)`: for a symbol in `km.ambiguous` a `term` entry returns `skipped-unqualified` unless `approved == term`; a topic returns `topic`; no-keyword stays `no-keyword`. A symbol not in `_ambiguous` is not restricted (the T125 constant no longer decides). The status string `skipped-unqualified` and the run outcome string are kept so run files and readers do not change vocabulary.
- R5. `trends.NAME_RISK_SYMBOLS` is removed. Its callers, all migrated in this slice: `trends_keywords.py` (`keyword_status`), `trends_candidates.py` (`candidate_groups` takes the ambiguous set as an argument with default `frozenset()`), and `probe_trends.py` at the `--alone` risk note and the `loader_flag` for `--try`; the loader flag keeps the value `loader-valid` for a usable term and uses the text `needs approval (ambiguous)` for an unapproved listed term, so `trends_campaign.py`'s check that stored `loader_flags` equal `loader-valid` is not changed. `trends.is_qualified_term` and `QUALIFIER_WORDS` stay. `refresh_attention.py` does not use the constant (checked).
- R6. The shipped file gets `_ambiguous` = the 23 coins of D7 and `"approved": "<its current term>"` on exactly these six: ONDO (`ondo crypto`), PEPE (`Pepe coin`), TRX (`tron crypto`), APT (`aptos crypto`), CRO (`cronos crypto`), MORPHO (`morpho crypto`). No other term is approved.

Tests (all in S1, same slice so the suite is green at the end of S1): `test_trends_keywords.py` (new: `_ambiguous` valid, duplicate, non-string item, `_anchor` in list, missing entry for a listed symbol; `approved` on a topic, on no-keyword, on `_anchor`, a non-string, a string that differs from the term; approved term pulled, same term re-edited without re-approval skipped, unapproved term skipped, topic pulled, unlisted bare term pulled; `KeywordMap` positional construction still works; update `:312` and `test_t160_name_risk_symbols_never_have_a_bare_term` at `:354-362` to the shipped `_ambiguous` list); `test_trends_keyword_guard.py` (update `PINNED_ELIGIBLE` expectations: the guard reports the eight pinned coins CC, GRAM, JST, LIT, M, NIGHT, RAIN, SKY as `skipped-unqualified`; update `NO_GAPS`, the "78 of 79" gap-report text, and the LINK cases at `:76,:130,:144` to use an explicit `_ambiguous` fixture; add a before-and-after test on the shipped file asserting exactly the nine coins CC, JST, RAIN, SKY, GRAM, LIT, NIGHT, M, STABLE change from pulled to `skipped-unqualified`); `test_trends.py` (`test_name_risk_symbols_match_t125_list` becomes: the shipped `_ambiguous` list equals the 23 coins of D7); `test_trends_candidates.py` and `test_trends_t202.py` (pass the ambiguous set; `test_trends_t202.py:84,102-111`); `test_probe_trends_try.py:111` (`needs qualifier word` text becomes `needs approval (ambiguous)`) and `test_probe_trends_campaign.py:127` (GRAM reads `missing`, not `weak`); `test_check_trends_keywords.py` (still passes; read-only check); `test_refresh_attention_trends.py:24,110,299-309,410` and `test_refresh_attention_trends_runs.py:63-98` (fixtures get `_ambiguous` and `approved` where they use LINK, TRX or APT terms).

## S2. Selection rule in the campaign report (AC1-AC5, AC13-AC15)

Files: new `api/data/attention/trends_select.py` (pure: no network, no file writes), `api/scripts/trends_campaign.py` (report), `api/scripts/probe_trends.py` (`--report` output).

Rule `select(coin_record, entry, ambiguous) -> Selection{verdict, term, reasons, flags, others}`; verdict is one of `use-term`, `use-topic`, `needs-approval`, `needs-owner`, `waking-up`, `untested`:
- A group is a candidate only if its outcome starts with `ok`, its verdict is `ok` (the daily rule), and it has no one-term spike (a vacuous filter for single-term groups; spike tests use synthetic bundle fixtures). A state coin whose outcome starts with `frame-rejected` has no metrics and is never a candidate (use `startswith`, as `_recommend` does). Malformed or missing metrics mean "no candidate", never a crash.
- Candidates are single-term groups. A bundle is never the signal (AC1); it only contributes flags.
- Order among candidates: first keep the coin's current keyword when it is itself a candidate (a change is proposed only when the current keyword is not a candidate); otherwise topic first, then fewest zero days, then most distinct values, then higher volume correlation (missing last). `clean rising` and `median` play no part (AC3). For an ambiguous coin, bare name and bare ticker groups are never candidates (only a topic or a qualified term). Reason: a dry run on the real state file showed that ranking by zero days alone proposes bare tickers for 27 unlisted coins (for example topic to ticker for AERO, BGB, KCS), which are exactly the ambiguous names this feature guards against.
- Identity flag (AC4): volume correlation below `IDENTITY_MIN_CORR` -> `unconfirmed (volume)`; no stored volume -> `unchecked (no volume)`.
- Variant flag (AC5, D4): compare the main term with the usable bundles (`kind=bundle`) that contain it; `moves_alone` is relative to the bundle's own best term, so the flag can only fire when the main term is not that best term; a usable bundle whose `moves_alone` names the main term -> `unconfirmed (variants)`; no usable bundle -> `unchecked (no variants)`. Never a rejection. Dry run: 65 of 74 chosen terms read `unchecked`, 9 agree, 0 `unconfirmed`; the flag is informational.
- Ambiguous coin: a topic candidate -> `use-topic`; only a term candidate -> `needs-approval` unless `entry.approved` equals the candidate term -> `use-term`. A `needs-approval` line prints the candidate as a suggestion only; an approved term must equal the entry's term, and the tool never emits `approved`.
- No candidate: quiet-then-surge in any group -> `waking-up` (the report line says `approved, pulled` when the coin is approved); otherwise `needs-owner` with the reason (`no usable group`, `frame-rejected`, `too-little-interest`). A state coin with no entry in the keyword file (USD0, FLR) is reported as `not in the keyword file`, never as a verdict.
- A listed coin absent from the campaign state -> `untested` (AC15); never `use-term`.
- `--report` prints one line per coin: current keyword and status, selection verdict, chosen term, flags, and the losing terms with why (AC13); plus a paste-ready JSON block of proposed entries labelled `proposal; you apply it`, built with `json.dumps` and filtered through `is_valid_term` and `is_valid_topic`. `--report` stays read-only and never touches the network (AC14); the state path is still refused inside the repository. `STAGE2_JSON_LABEL` is updated to the new shape.

Tests: new `api/tests/data/attention/test_trends_select.py` (empty, quiet, one-day spike, one-term spike refused; rising-but-gappy loses to steady-but-complete; current keyword kept when it is a candidate, even against a bare ticker with fewer zero days; bundle present never changes the term; volume flags with and without stored volume; variant flags agree/disagree/none; listed coin topic/approved term/unapproved term/term approved for another coin; no passing term; waking-up; untested; malformed metrics; frame-rejected; state coin without entry; proposal block contains no `approved` key); `test_probe_trends_t202.py` and `test_probe_trends_campaign.py` updated; `test_report_is_read_only_and_sends_no_request` (monkeypatch the fetch to fail).

## S3. Daily run: the keyword used is recorded (AC8, AC12, D5)

Files: `api/scripts/refresh_attention.py`.
- Where the value comes from: `_run_trends` sets `metas[s] = {"kind": status, "keyword": kw}` (today `meta` is only `{"kind": status}` at `refresh_attention.py:345`); `_run_coin_record` emits `meta.get("keyword")`. `keyword` is the keyword assigned and attempted that day: coins that are capped or hit the time budget keep their keyword; skipped, no-keyword and bad-file coins get `null` (their `keyword_kind` handling at `:348` is unchanged and a test pins both). No other behaviour changes: one request per coin per pass (the existing 429 and empty-response retries are unchanged), same budget, same rotation.
- Reason text: one new constant `trends.WAITING_APPROVAL = "waiting for owner approval"` replaces the literal behind `trends.NAME_AMBIGUOUS` (clean cutover: `NAME_AMBIGUOUS` is removed), and `MISSING_KEYWORD_REASON` and `_TRENDS_REASON_OUTCOME` both use it, so the outcome stays `skipped-unqualified` and the `trends detail:` line is unchanged (changing only one of the two maps would turn the outcome into `failed`). Old run files and stored reasons that carry the old string stay mapped to `skipped-unqualified` in the reader. The Trends signal for such a coin is missing with that reason, never 0 (AC8).
- Series storage is unchanged. The history rule is D5.

Tests: `test_refresh_attention_trends_runs.py` (add `keyword` to `COIN_KEYS` at `:32` and to the unpulled-coin check at `:214`; `keyword` present for pulled coins and null otherwise; a file without `keyword` still reads), `test_refresh_attention_trends.py` (the three pins on `trends.NAME_AMBIGUOUS` at `:111`, `:307`, `:410` and the `MISSING_KEYWORD_REASON` pins at `:410`, `:419` move to the new constant; request count equals pulled coins in a no-retry fixture; an unapproved ambiguous coin sends no request and is reported `skipped-unqualified`; an old reason string still reads as `skipped-unqualified`; D5 limit: a failed pull under a changed keyword leaves the old series and records the new keyword; budget test unchanged).

## S4. Waking-up watch list (AC9, AC10)

Files: `api/data/attention/trends_runs.py`, `api/scripts/trends_campaign.py`, `api/analytics/attention/sources.py`, `api/models/discovery.py`, `web/lib/types/discovery.ts`, `web/components/narrative/DiscoverySourcesPanel.tsx`.
- The run-file helpers `RUN_FILE_RE`, `MAX_RUN_FILE_BYTES`, `RUN_OUTCOMES`, `_latest_run` and the shape check move from `trends_campaign.py` into `trends_runs.py` (the data layer must not import `scripts`), and `trends_campaign.py` imports them; the `trends_runs.py` docstring that says no reader exists is corrected. New reader `watch_list(date)` there: for each coin the streak of consecutive calendar dates, read from the file names, ending at the newest file, whose latest-run outcome is `quiet-then-surge`. Outcomes `failed`, `capped`, `time-budget` and a missing file date are neutral (they neither extend nor break the streak; real files carry 5 to 10 `failed` and up to 47 `time-budget` a day); any other outcome ends it; a keyword that differs between two days (when both carry `keyword`) ends it (D5). A coin absent from the newest file is not listed. `days_held` counts surge days, shown as `30+` at the 30-file cap. Files are capped at 1 MB each; symlinks and non-regular files are skipped; a corrupt, oversized or unknown-shape file is skipped silently (the response has no note field) and a corrupt newest file gives an empty list. Output symbols are filtered with `SYMBOL_RE`, `days_held` is an `int`, the list length is capped. The path is taken from `cache.CACHE_ROOT` at call time. Real-file simulation on 27 to 31 Oct gives QNT 5, ASTER 5, KAS 4, ATOM 4, LIT 4, CRO 3, NIGHT 3, MORPHO 2, ENA 1, DASH 1.
- `build_sources` adds `trends_watch` to the response (an optional list `[{symbol, days_held}]`, `null` or empty when none); route `GET /api/narrative/sources`. It reads no score, writes nothing and does not touch Discovery ranking (AC9); `discovery.py` must not import `trends_runs` or `sources` (asserted). The web type is optional (`trends_watch?: ... | null`) and the panel renders nothing when it is empty or missing.
- Web: the Sources panel renders a separate element "Waking up (daily pulls)" under the Trends row: `SYM (N days)`; a coin that leaves the list disappears on the next load (AC10). It is separate from the coverage note so the existing exact-text assertions stay valid. A coin that is waking up in the campaign report but not pulled (unapproved) is not on this list.

Tests: new `api/tests/data/attention/test_trends_runs.py` (streaks, a failed or time-budget day does not break it, a different keyword breaks it, missing date neutral, corrupt newest file, oversized file, symlink, `30+` cap, unsafe symbol filtered), `api/tests/analytics/attention/test_sources.py` (`trends_watch` present and empty; model key set without TestClient), `api/tests/analytics/attention/test_discovery.py` (new: Discovery scores identical with and without a coin in the watch list; `discovery.py` does not import `trends_runs`), `api/tests/routers/test_discovery.py::test_sources_route_shape_and_no_network` (exact key set gains `trends_watch`), web `DiscoveryTab.test.tsx` and `DiscoverySourcesPanel.test.tsx` (watch text, absence, null), and the Sources load as a vitest test (Playwright is not run by the gates).

## S5. Sources coverage note distinguishes the cases (AC8)

Files: `api/analytics/attention/sources.py`, `api/models/discovery.py`, `web/components/narrative/DiscoverySourcesPanel.tsx`, `web/lib/format-unavailable-reason.ts`.
- `trends_keyword.missing` lists `(symbol, status)` for the four statuses `no-entry`, `no-keyword`, `skipped-unqualified`, `bad-file`; the note groups by `detail` (no wire change, no new reason literal): `waiting for approval: SYMS` (`skipped-unqualified`), `no keyword (needs owner): SYMS` (`no-keyword`), `no keyword entry yet: SYMS` (`no-entry`), `keyword file invalid` (`bad-file`). The "No Google Trends keyword yet" prefix stays for the no-keyword and no-entry groups so the existing exact-text assertions in `DiscoveryTab.test.tsx:442,457` hold; the waiting group is a separate sentence. `format-unavailable-reason.ts` and `web/lib/types/discovery.ts:192` change only if a new code is added (none is).

Tests: `test_sources.py::test_trends_keyword_coverage_over_eligible_coins` (extended: the four detail values), `DiscoveryTab.test.tsx` (new waiting note), `format-unavailable-reason.test.ts` (unchanged).

## S6. Docs and context

- `process/context/decisions.md` D-30 (one term per coin, ambiguity list and approvals in the keyword file, tester proposes, waking up watch only).
- `process/context/data-sources/all-data-sources.md` and `process/context/current-state.md`: one line each.
- Operator note in the plan's EXEC-REPORT for the owner: how to read `--report` and apply a proposal.

## Public Contracts

| Contract | Change |
|---|---|
| `trends_keywords.json` | new reserved key `_ambiguous`; optional `approved: "<term>"` on `term` entries (equal to the term); older files still load |
| `keyword_status` | rule for listed coins (approval bound to the term); status strings unchanged |
| `trends_runs/<date>.json` | coin record gains `keyword` (the keyword assigned and attempted; null when not pulled); readers ignore its absence |
| `GET /api/narrative/sources` | response gains optional `trends_watch` (list); additive; existing fields unchanged |
| `--report` output | new selection lines and proposal block; read-only |
| `trends.NAME_RISK_SYMBOLS`, `trends.NAME_AMBIGUOUS` | removed (clean cutover); replaced by the file's `_ambiguous` and `trends.WAITING_APPROVAL`; callers: `trends_keywords.py`, `trends_candidates.py`, `probe_trends.py` (two sites), `refresh_attention.py` (`NAME_AMBIGUOUS` only), and the tests listed per slice; no web use |

## Touchpoints

Changed: `api/data/attention/trends_keywords.py`, `trends.py`, `trends_candidates.py`, `trends_runs.py`, new `trends_select.py`; `api/data/trends_keywords.json`; `api/scripts/refresh_attention.py`, `trends_campaign.py`, `probe_trends.py`; `api/analytics/attention/sources.py`; `api/models/discovery.py`; `web/lib/types/discovery.ts`, `web/components/narrative/DiscoverySourcesPanel.tsx`; the tests named per slice (including `test_trends_keyword_guard.py`, `routers/test_discovery.py`, `DiscoverySourcesPanel.test.tsx`); the three docs of S6. Read only: `store.py`, `discovery_history.py`, `signal_snapshots.py`, `check_trends_keywords.py`, `snapshot_narrative.py` (grep for `trends_keywords` at EXECUTE; add it here if it reads the file), the PC worker and PC scripts (checked: they do not read the keyword file or the run files), `.github/` (not touched; the stale 540 s comment at `attention-refresh.yml:203` is noted, not edited).

## Blast Radius

About 22 files, API and web. Live effect: after merge the daily Trends step stops pulling the nine listed coins whose term is not approved (Q1). Discovery scoring code is not changed; a coin without a Trends signal reads as missing for that source, never 0. Risk class RT2; no provider call is made by any test.

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
| `test_refresh_attention_trends` + `test_sources` + `routers/test_discovery`: unapproved and no-keyword coins send no request and read missing with reason through the daily run, the Sources response and the Discovery response | Fully-Automated | AC8 |
| `test_discovery`: scores identical with and without a watch-list coin; `test_trends_runs` streaks | Fully-Automated | AC9 |
| `DiscoveryTab.test.tsx` watch text + fixture-backed Sources load | Fully-Automated | AC10 |
| `test_trends_keywords` bad-file cases (including an approval for a term that is not the stored term) and the `bad keyword file` reason | Fully-Automated | AC11 |
| `test_refresh_attention_trends`: one request per coin per pass with no-retry fixtures; existing budget test | Fully-Automated | AC12 |
| `test_probe_trends_t202`: per-coin evidence lines on the real state shape | Fully-Automated | AC13 |
| `test_report_is_read_only_and_sends_no_request` | Fully-Automated | AC14 |
| `test_trends_select`: listed coin missing from the state is `untested` | Fully-Automated | AC15 |
| Owner probe P-T1: chosen terms vs the public Trends page for ten coins | Agent-Probe (residual: Trends is unreachable from the build environment) | AC16 |

## Tests and gates (commands)

```
uv run --project api python -m pytest api/tests/data/attention api/tests/scripts api/tests/analytics/attention api/tests/routers -q -p no:cacheprovider
cd web && pnpm exec vitest run components/narrative lib && pnpm exec tsc --noEmit
```
Baseline: 24 failures that also fail on `main`, all inside these gates and named by full path: 12 in `api/tests/routers/test_discovery.py`, 11 in `api/tests/routers/test_discovery_history.py`, and `api/tests/analytics/attention/test_universe_classes.py::test_discovery_end_to_end_on_fixture` ("handler must not reach the network"). The routers path was missing from the first draft of the gate (VALIDATE finding) and is added. On this Windows machine `uv run pytest` fails with "uv trampoline failed to canonicalize script path"; use `uv run --project api python -m pytest ...`. EXECUTE saves the baseline FAILED ids first and reports only new ones. A gate script is not generated for this plan; EXECUTE runs the two commands and a diff-name check (changed files must be inside Touchpoints).

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Nine coins stop being pulled after merge (CC, JST, RAIN, SKY, GRAM, LIT, NIGHT, M, STABLE) | Q1 is answered; the Sources note lists them as waiting for approval; the owner sets a topic or an approval and nothing else is needed; a test asserts the exact nine; EXECUTE reports the before and after set |
| A changed keyword and the stored series | replace-series makes the store hold only the latest successful term; the run record names the keyword attempted; a failed pull under a new keyword keeps the old series (tested and documented, D5) |
| Variant check misjudges weak extra variants | D4: warns only, never rejects |
| Thresholds are placeholders | named constants, tuned after the first real run |
| `NAME_RISK_SYMBOLS` and `NAME_AMBIGUOUS` removal misses a caller | the callers are listed in Public Contracts; references are checked with the language server before the removal; S1 migrates `probe_trends.py` in the same slice so no slice leaves the suite red |
| The watch-list scan is slow or reads hostile files | at most 30 run files, 1 MB each, regular files only, one parse per request inside `build_sources`; no cache needed (the route has none) |

## Test Infra Improvement Notes

(none identified yet)

## Cursor + RIPER-5 guidance

RIPER-5: this PLAN, then VALIDATE, then the owner's ENTER EXECUTE MODE for T-Trends-stage2 with agent `riper-opus` on branch `claude/trends-stage2`. EXECUTE order: S1, S2, S3, S4, S5, S6, each with its tests before the next; stop and report on scope expansion. After each slice: what is functional, what was tested, what the owner can check.

## Resume and Execution Handoff

1. Selected plan file: `process/general-plans/active/narrative-baskets-trends-stage2_01-11-26/narrative-baskets-trends-stage2_PLAN_01-11-26.md`.
2. Last completed phase or step: PLAN written; nothing executed.
3. Validate-contract status: written (below). Net gate on the first pass was BLOCKED (two FAILs); one fix cycle applied; the plan needs the owner's acceptance of the CONDITIONAL gate before EXECUTE.
4. Supporting context files loaded: the SPEC, `trends_keywords.py`, the scout facts on `refresh_attention.py`, `trends_campaign.py`, `probe_trends.py`, `sources.py`, `DiscoverySourcesPanel.tsx`, `store.py`, `discovery_history.py`.
5. Next step for a fresh agent: the owner accepts the Validate Contract below, gives ENTER EXECUTE MODE; then start at S1.

## Validate Contract

Validated 01-11-26 by a two-layer fan-out (4 dimension agents, 4 section agents), read-only, against `main` after PR #208 merged. No live Google call was needed (VC-FEASIBILITY-PROBE-NEEDED: none).

| Layer 1 dimension | First pass | After fixes |
|---|---|---|
| Infra fit | CONCERN | fixed (callers, reader layer, run-file facts, 429 retries) |
| Test coverage | FAIL | fixed (routers added to gate; guard, key-set, COIN_KEYS tests named) |
| Breaking changes | FAIL | fixed (reason constants moved together; probe_trends migrated; optional web field; route path) |
| Security surface | CONCERN | fixed (approval bound to the term; reader moved and capped; symbol filter) |

| Layer 2 section | First pass | After fixes |
|---|---|---|
| S1 keyword file | CONCERN | fixed |
| S2 selection rule | CONCERN | fixed |
| S3 daily run | CONCERN | fixed |
| S4 watch list | CONCERN | fixed |
| S5 Sources note | CONCERN | fixed |

First-pass totals: 2 FAIL, 7 CONCERN, 0 PASS; net gate BLOCKED. All FAILs and CONCERNs were fixed in the plan text (P1-P14 below). Net gate after the fix cycle: CONDITIONAL (the fixes are not re-validated by a second fan-out; the owner's acceptance is the recorded decision).

### Proposed Plan Updates applied

| # | What changed | Where | Why |
|---|---|---|---|
| P1 | `approved` is the exact term string, not a flag | D1, R2, R4, R6 | a boolean survived a term edit; the SPEC says the approval is stored with the term |
| P2 | D5 reworded; run record `keyword` is the keyword attempted | D5, S3 | replace-series re-pulls the whole window under the latest term; no per-day label exists in the store |
| P3 | `_ambiguous` handled before the key loop; explicit entry check; defaulted `KeywordMap` field; `approved` in `ALLOWED_FIELDS` | S1 R1-R3 | lower-case key fails `SYMBOL_RE`; positional construction in tests |
| P4 | `probe_trends.py` migrated in S1; loader flag text defined | S1 R5 | removing the constant otherwise breaks `--alone`, `--try` and a slice boundary |
| P5 | Missing tests named: `test_trends_keyword_guard.py`, `test_trends_keywords.py:312,354-362`, `test_probe_trends_try.py:111`, `test_probe_trends_campaign.py:127`, fixtures | S1 tests | 8+ tests fail otherwise |
| P6 | `trends.WAITING_APPROVAL` replaces `NAME_AMBIGUOUS` in all three places | S3 | changing one map turns the outcome into `failed` |
| P7 | Run-file helpers move into `trends_runs.py`; watch-list layer, caps, symlink and symbol rules | S4 | `analytics` must not import `scripts`; hostile-file safety |
| P8 | Streak rule: transient outcomes and missing dates are neutral; keyword change breaks it; calendar-date unit; `30+` | S4 | real files carry 5-10 `failed` and up to 47 `time-budget` a day |
| P9 | `trends_watch` optional in the web type; route is `/api/narrative/sources`; router key-set test named | S4, Contracts | typed fixtures and old builds |
| P10 | Coverage note grouped by `detail` for all four statuses; no new reason literal | S5 | `no-entry` and `bad-file` were uncovered; wire stays unchanged |
| P11 | Selection keeps the current keyword when it is a candidate; topic first; bare names never candidates for ambiguous coins; entry-less coins; `startswith`; malformed metrics | S2 | a dry run proposed bare tickers for 27 unlisted coins |
| P12 | Gate adds `api/tests/routers`; the 24 baseline failures named by full path; Windows `python -m pytest` note | Tests and gates | the first gate missed 23 of the 24 baseline failures and would have hidden the key-set break |
| P13 | AC8 gets a Discovery-response assertion; AC12 reworded to one request per coin per pass | Evidence table | the SPEC says every screen; retries exist |
| P14 | Callers list corrected (`refresh_attention.py` uses only `NAME_AMBIGUOUS`) | Contracts, Risks | accuracy |

### Execute-Agent Instructions

| # | Instruction | Trigger |
|---|---|---|
| E1 | Before S1, save the baseline FAILED ids of both gate commands; report only new failures. | start |
| E2 | Before removing `NAME_RISK_SYMBOLS` and `NAME_AMBIGUOUS`, find every reference with the language server and migrate all of them in the same slice. | S1, S3 |
| E3 | Read `trends_keywords.json` in full (only lines 1-300 of 417 were read during VALIDATE) before seeding R6; the six approved coins and the 23 listed coins must pass the new validator. | S1 |
| E4 | Grep `snapshot_narrative.py` for `trends_keywords`; if it reads the file, add it to Touchpoints and report. | S1 |
| E5 | Do not edit `.github/`; report the stale 540 s comment at `attention-refresh.yml:203` as a note only. | all |
| E6 | `--report` and `select` must never write `trends_keywords.json` or emit `approved`; test it. | S2 |
| E7 | EXECUTE reports the exact before-and-after set of coins whose pull status changes; it must equal the nine named in the plan. | S1 |
| E8 | Stop and report on scope expansion, a newly failing baseline test outside the plan, or a live Google request. | all |

### Backlog artifacts

| Artifact | What it tracks |
|---|---|
| STABLE campaign run | STABLE is on the ambiguity list but untested; run `--all-eligible` once after S2 so the report shows it |
| Variant-agreement tuning | 65 of 74 chosen terms read `unchecked`; tune after the first real run |
