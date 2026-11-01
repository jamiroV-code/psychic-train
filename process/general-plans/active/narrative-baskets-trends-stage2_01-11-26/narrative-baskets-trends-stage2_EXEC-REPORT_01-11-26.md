---
name: exec-report:narrative-baskets-trends-stage2
description: "EXECUTE report for Trends stage 2 (slices S1-S6): ambiguity list and term-bound approvals, selection rule in --report, keyword in the daily run file, waking-up watch list, grouped Sources note, D-30."
date: 01-11-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: exec-report
---

# Narrative Baskets: Trends stage 2 - EXEC-REPORT (01-11-26)

Status: 🔨 CODE DONE (`review`). Branch `claude/trends-stage2`, one draft PR. Nothing is VERIFIED: owner probe P-T1 (AC16) needs live Google Trends and was not run.

## 1. Summary

All six slices are implemented with tests, one commit per slice (S1 to S6). Both gates show no failure beyond the baseline saved on the untouched checkout. After merge, the daily Trends step stops pulling exactly nine coins: CC, JST, RAIN, SKY, GRAM, LIT, NIGHT, M, STABLE. They read missing with "waiting for owner approval", never 0.

## 2. What changed (per slice)

- S1 (`4c124e35`): `trends_keywords.py` reads a new reserved key `_ambiguous` (a list of unique symbols, never `_anchor`, each with an entry) and an optional `"approved": "<term>"` field. `approved` is allowed only on a coin's term entry and must equal its term exactly. `KeywordMap.ambiguous` is a defaulted field after `not_placed`. `keyword_status` pulls a listed coin's term only when `approved == term`. `trends.NAME_RISK_SYMBOLS` is removed. `candidate_groups` takes `ambiguous=` (default empty). `probe_trends.loader_flag(sym, term, km)` returns `needs approval (ambiguous)` for an unapproved listed term and `loader-valid` otherwise, as before. The `--alone` note uses `keyword_status`. The shipped file gets the 23 D7 coins and `approved` on exactly ONDO, PEPE, TRX, APT, CRO and MORPHO.
- S2 (`c6d211d9`): new pure `api/data/attention/trends_select.py` with `select(symbol, coin, entry, ambiguous) -> Selection` and `proposal(...)`. `trends_campaign.selection(...)` builds one line per coin: the eligible coins, then every listed coin, then every coin in the state. `--report` prints those lines plus a paste-ready block labelled `proposal; you apply it`. `STAGE2_JSON_LABEL` now describes the keyword-file shape. The `--try` summary block now proposes a single term in the keyword-file shape (`{"term": ...}` / `{"topic": ...}`).
- S3 (`e2b87209`): `refresh_attention._run_trends` sets `metas[s]["keyword"]` for every pulled coin, and the run-file coin record carries `keyword` (null when the coin is not pulled). `trends.WAITING_APPROVAL = "waiting for owner approval"` replaces `NAME_AMBIGUOUS` in both maps. The old string stays mapped to `skipped-unqualified`.
- S4 (`442af64c`): the run-file helpers (`RUN_FILE_RE`, `RUN_OUTCOMES`, `MAX_RUN_FILE_BYTES`, `_latest_run`) moved into `trends_runs.py`, and the campaign imports them. New `trends_runs.watch_list(today)` reads at most 30 newest files, each 1 MB at most, regular files only, no symlinks. `failed`, `capped`, `time-budget` and missing dates are neutral; a keyword change ends a streak; symbols are filtered and the list is capped. `build_sources` adds `trends_watch`, and the model gets `DiscoveryTrendsWatch`. The web type is optional, and the panel shows "Waking up (daily pulls): SYM (N days)" (30 reads `30+`) as its own row under the Trends row.
- S5 (`5746a2ff`): the Trends note on the panel is grouped. "No Google Trends keyword yet: ..." covers no-keyword and no-entry. "Waiting for owner approval: ..." covers skipped-unqualified. "Keyword file invalid" covers bad-file. The wire shape is unchanged.
- S6: D-30 in `process/context/decisions.md`, one line each in `all-data-sources.md` and `current-state.md`, and this report.

## 3. Acceptance criteria and proving tests

| AC | Proven by |
|---|---|
| AC1 | `test_trends_select.py::test_bundle_present_never_changes_the_term`, `::test_one_day_spike_in_a_bundle_never_becomes_the_signal` |
| AC2 | `test_trends_select.py::test_empty_quiet_and_spike_groups_are_never_chosen`, `::test_one_day_spike_in_a_bundle_never_becomes_the_signal` |
| AC3 | `test_trends_select.py::test_rising_but_gappy_loses_to_steady_but_complete`, `::test_ties_break_on_distinct_values_then_volume` |
| AC4 | `test_trends_select.py::test_volume_flags` (3 cases) |
| AC5 | `test_trends_select.py::test_variant_flags_only_warn` (4 cases) |
| AC6 | `test_trends_keywords.py::test_stage2_keyword_status_rule`, `::test_stage2_approval_for_another_coin_does_not_count`, `::test_stage2_term_edited_without_reapproval_is_skipped`; `test_trends_select.py::test_ambiguous_coin_*`, `::test_ambiguous_term_approved_for_another_coin_does_not_count` |
| AC7 | `test_trends.py::test_shipped_ambiguous_list_is_the_23_d7_coins`, `test_trends_keywords.py::test_stage2_shipped_ambiguous_list_and_exact_approvals`, `::test_stage2_added_coin_takes_effect_from_the_file` |
| AC8 | `test_refresh_attention_trends.py::test_request_count_equals_pulled_coins_and_unapproved_sends_none`, `::test_coin_without_usable_keyword_is_missing_never_zero`; `test_sources.py::test_trends_keyword_coverage_over_eligible_coins`; `test_trends_select.py::test_no_passing_term_is_needs_owner_with_reason`; `routers/test_discovery.py::test_sources_route_shape_and_no_network` (key set updated; baseline-red, see section 5) |
| AC9 | `test_discovery.py::test_discovery_scores_identical_with_and_without_a_watch_list_coin`, `::test_discovery_does_not_import_the_watch_list_or_sources`; `test_trends_runs.py` (streak tests) |
| AC10 | `DiscoveryTab.test.tsx` "shows the waking-up watch list under the Trends row and drops a coin that left it"; `DiscoverySourcesPanel.test.tsx` watch text / empty-null-missing; `test_sources.py::test_trends_watch_lists_days_held` |
| AC11 | `test_trends_keywords.py::test_stage2_bad_ambiguous_list_is_refused` (6), `::test_stage2_bad_approval_is_refused` (4), `::test_stage2_approval_on_anchor_is_refused`, `::test_stage2_bad_approval_makes_safe_load_report_bad_file` |
| AC12 | `test_refresh_attention_trends.py::test_request_count_equals_pulled_coins_and_unapproved_sends_none`; existing `::test_time_budget_caps_the_rest` unchanged |
| AC13 | `test_probe_trends_campaign.py::test_report_selection_lines_per_coin` (state written by the real `save_state`) |
| AC14 | `test_probe_trends_campaign.py::test_report_is_read_only_and_sends_no_request` (fetch patched to raise; keyword file, data dir and state byte-identical; no `approved`) |
| AC15 | `test_trends_select.py::test_listed_coin_missing_from_state_is_untested`; `test_probe_trends_campaign.py::test_report_selection_lines_per_coin` (STABLE untested) |
| AC16 | NOT RUN: owner probe P-T1 needs live Google Trends (owner PC only) |

E7 (pull-status change): `test_trends_keyword_guard.py::test_stage2_exactly_the_nine_unapproved_coins_stop_being_pulled` compares the old T125 rule with the new rule over the shipped file. The set that changes is exactly {CC, JST, RAIN, SKY, GRAM, LIT, NIGHT, M, STABLE}, all from pulled to `skipped-unqualified`. No coin changes from not-pulled to pulled.

## 4. Gates

- API gate: `uv run --project api python -m pytest api/tests/data/attention api/tests/scripts api/tests/analytics/attention api/tests/routers -q -p no:cacheprovider`. Baseline (untouched `origin/main` worktree): 41 failed, 2192 passed. Final: 41 failed, 2266 passed, 2 skipped. The failed sets are identical (`comm` shows 0 new and 0 fixed).
- Web gate: `pnpm exec vitest run components/narrative lib && pnpm exec tsc --noEmit`. Baseline: 1 failed (`lib/__tests__/plot-ink.test.ts > plot axis ink > colours canvas axis labels ...`), 393 passed; tsc clean. Final: the same 1 failed, 397 passed; tsc clean.
- Red first: the S1 tests were run against the untouched code (28 failed, as expected). The S2 to S5 test files were written before their modules existed or before the change.

## 5. Baseline (BASEFAIL, saved before S1)

The plan expected 24; the untouched checkout shows 41. The 17 extra failures are in the same gate path and fail the same way on untouched `origin/main` ("handler must not reach the network" from the TestClient guard, plus a 409 race in the equities router): 7 in `api/tests/routers/test_attention.py`, 9 in `api/tests/routers/test_discovery_price.py` and 1 in `api/tests/routers/test_equities_router.py`. Stage 2 caused none of them and none was fixed. Full list:

```
api/tests/analytics/attention/test_universe_classes.py::test_discovery_end_to_end_on_fixture
api/tests/routers/test_attention.py::test_bad_window_is_422[0]
api/tests/routers/test_attention.py::test_bad_window_is_422[14]
api/tests/routers/test_attention.py::test_bad_window_is_422[abc]
api/tests/routers/test_attention.py::test_default_window_30_reads_store_only
api/tests/routers/test_attention.py::test_valid_windows[30]
api/tests/routers/test_attention.py::test_valid_windows[7]
api/tests/routers/test_attention.py::test_valid_windows[90]
api/tests/routers/test_discovery.py::test_default_window_is_30
api/tests/routers/test_discovery.py::test_enum_accepts[30]
api/tests/routers/test_discovery.py::test_enum_accepts[7]
api/tests/routers/test_discovery.py::test_enum_accepts[90]
api/tests/routers/test_discovery.py::test_enum_rejects_with_422[-7]
api/tests/routers/test_discovery.py::test_enum_rejects_with_422[0]
api/tests/routers/test_discovery.py::test_enum_rejects_with_422[14]
api/tests/routers/test_discovery.py::test_enum_rejects_with_422[30.5]
api/tests/routers/test_discovery.py::test_enum_rejects_with_422[abc]
api/tests/routers/test_discovery.py::test_ok_payload_shape
api/tests/routers/test_discovery.py::test_router_discovery_new_fields_present
api/tests/routers/test_discovery.py::test_sources_route_shape_and_no_network
api/tests/routers/test_discovery_history.py::test_bad_window_is_422[0]
api/tests/routers/test_discovery_history.py::test_bad_window_is_422[14]
api/tests/routers/test_discovery_history.py::test_bad_window_is_422[abc]
api/tests/routers/test_discovery_history.py::test_category_payload_carries_membership_as_of_and_old_ids_resolve
api/tests/routers/test_discovery_history.py::test_category_payload_shape
api/tests/routers/test_discovery_history.py::test_coin_payload_shape
api/tests/routers/test_discovery_history.py::test_default_window_is_30
api/tests/routers/test_discovery_history.py::test_empty_is_no_data
api/tests/routers/test_discovery_history.py::test_live_endpoint_unchanged
api/tests/routers/test_discovery_history.py::test_needs_exactly_one_subject
api/tests/routers/test_discovery_history.py::test_unknown_subjects_are_404_with_plain_message
api/tests/routers/test_discovery_price.py::test_bad_input_is_422[params0]
api/tests/routers/test_discovery_price.py::test_bad_input_is_422[params1]
api/tests/routers/test_discovery_price.py::test_bad_input_is_422[params2]
api/tests/routers/test_discovery_price.py::test_bad_input_is_422[params3]
api/tests/routers/test_discovery_price.py::test_bad_input_is_422[params4]
api/tests/routers/test_discovery_price.py::test_cache_older_than_window_is_no_data_but_reports_last_date
api/tests/routers/test_discovery_price.py::test_no_cache_is_no_data
api/tests/routers/test_discovery_price.py::test_non_finite_and_non_positive_closes_are_dropped
api/tests/routers/test_discovery_price.py::test_ok_returns_window_days_ending_yesterday
api/tests/routers/test_equities_router.py::test_concurrent_adds_store_exactly_thirty
```

Because `routers/test_discovery.py::test_sources_route_shape_and_no_network` is baseline-red, the new `trends_watch` key set is also proven without TestClient (`test_sources.py::test_sources_model_key_set_without_testclient`).

## 6. Real entry-point runs (fixtures, read-only)

- `python -m api.scripts.probe_trends --report <temp dir outside the repo>/small.json`, on a 5-coin state written with the real `save_state`. Exit 0. SKY `needs-approval` (suggestion `sky crypto`, flags `unchecked (no volume), unchecked (no variants)`); APT `waking-up ... approved, pulled`; M `needs-owner` (`too-little-interest`); STABLE `untested`. Proposal block `{}`.
- `--report` on the owner's real state file (read-only). Exit 0. The file's SHA-256 is unchanged, `api/data/trends_keywords.json` is unchanged, and no request was sent. Verdict counts: **use-term 34, use-topic 33, needs-approval 5, needs-owner 1, waking-up 6, untested 1**. needs-approval: RAIN, CC, GRAM, SKY, JST. waking-up: CRO, MORPHO, LIT, NIGHT, ETHFI, APT. needs-owner: M. untested: STABLE. Not in the keyword file: FLR, USD0. The proposal block holds 27 entries and no `approved` key.
- Sources built from the shipped cache (`build_sources(2026-11-01)`): `trends_watch` = ASTER 5, QNT 5, ATOM 4, KAS 4, LIT 4, CRO 3, NIGHT 3, MORPHO 2, DASH 1, ENA 1, matching the plan's simulation. Keyword coverage is 65 of 74. Waiting for approval: RAIN, CC, GRAM, M, SKY, JST, LIT, NIGHT. No entry: FLR.

## 7. Deviations and owner review items

- Baseline is 41, not 24 (section 5).
- S5: no-keyword and no-entry stay in one sentence ("No Google Trends keyword yet: ..."). The existing exact-text assertions (`DiscoveryTab.test.tsx` T180 tests) mix both details in one sentence, so splitting them would break those assertions, which the plan says must hold. Waiting-for-approval and invalid-file are separate sentences.
- `--try` summary: the paste-ready block now proposes one term in the keyword-file shape instead of a group (`STAGE2_JSON_LABEL` "updated to the new shape"). `test_probe_trends_try.py` and `test_probe_trends_campaign.py` were updated to match. The `--try` summary tests use the unlisted symbol XTON instead of GRAM, because GRAM is now ambiguous.
- `test_refresh_attention_trends_runs.py::test_file_stays_small_for_a_full_universe`: the size bound is now 48 000 bytes (was 40 000), because of the new per-coin `keyword` field.
- Review item: on the real state, 27 proposals include bare tickers for unlisted coins whose current keyword is not a usable candidate (for example WBT, LEO, BGB, GT, KCS, ATOM). This follows the plan's rule as written: bare tickers are excluded only for ambiguous coins, and the current keyword is kept only when it is a candidate. Proposals are never applied automatically; the owner decides each one.
- Watch list: LIT and NIGHT show today from older run files, made when they were still pulled. After merge they are not pulled, their newest outcome becomes `skipped-unqualified`, and they leave the list on the next run.
- E4: `api/scripts/snapshot_narrative.py` does not mention `trends_keywords` (grep: no match). Touchpoints are unchanged.
- E5 note (not edited): the stale 540 s comment at `.github/workflows/attention-refresh.yml:203`.

## 8. Files touched

`api/data/attention/{trends_keywords,trends,trends_candidates,trends_runs,trends_select}.py`, `api/data/trends_keywords.json`, `api/scripts/{refresh_attention,trends_campaign,probe_trends}.py`, `api/analytics/attention/sources.py`, `api/models/discovery.py`, `web/lib/types/discovery.ts`, `web/components/narrative/DiscoverySourcesPanel.tsx`. Tests: `test_trends_select.py` (new), `test_trends_runs.py` (new), `test_trends_keywords.py`, `test_trends_keyword_guard.py`, `test_trends.py`, `test_trends_candidates.py`, `test_trends_t202.py`, `test_probe_trends_try.py`, `test_probe_trends_campaign.py`, `test_refresh_attention_trends.py`, `test_refresh_attention_trends_runs.py`, `test_sources.py`, analytics `test_discovery.py`, `routers/test_discovery.py`, `DiscoveryTab.test.tsx`, `DiscoverySourcesPanel.test.tsx`. Docs: `decisions.md`, `all-data-sources.md`, `current-state.md`, this report. Not changed: `test_probe_trends_t202.py` (it passes as is), `format-unavailable-reason.ts` (no new code). Nothing under `.github/`.

## 9. Operator note: reading `--report` and applying a proposal

1. On your PC run `python -m api.scripts.probe_trends --report <state file>`. It reads the state only and sends no request.
2. Under "selection (stage 2)" each line reads: coin | current keyword (pull status) | verdict | chosen term | flags | reason | others and why they lost.
3. `use-term` / `use-topic` with a new term: the paste-ready block holds the entry. Copy it into `api/data/trends_keywords.json` yourself. The tool never writes the file.
4. `needs-approval`: the chosen term is a suggestion. To accept it, set that coin's `term` to it and add `"approved": "<the same term>"`. Editing the term later stops the pull until you approve again.
5. `waking-up`: watch only, never scored. `needs-owner`: find a topic or a better term. `untested`: run `--all-eligible` for it (STABLE).
6. Flags only warn: `unconfirmed (volume|variants)` means look closer; `unchecked` means no evidence, never "confirmed".

## 10. Risks and residuals

- AC16 / P-T1 not run (live Google). Thresholds are still placeholders. 6 coins read waking-up and 5 need approval on the real state.
- D5 limit (tested): a failed pull under a changed keyword keeps the older term's stored series, while the run record names the new keyword.

## 11. Next steps

The owner reviews the draft PR and merges. After merge: approve or set topics for the nine coins as wanted, run `--all-eligible` once for STABLE, run P-T1 on ten coins, then tune the thresholds after the first real run.
