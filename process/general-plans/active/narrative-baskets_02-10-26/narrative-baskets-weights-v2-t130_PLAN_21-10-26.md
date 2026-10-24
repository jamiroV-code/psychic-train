---
name: plan:narrative-baskets-weights-v2-t130
description: "T130 FAST MODE PLAN and VALIDATE for weights v2 of the Discovery weighted signal: owner-locked weights, a search vote group, an early-source trigger gate, weight 0 = parked, strict config validation, and per-day weights versions so frozen snapshots and past chart days never change."
date: 21-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: plan
---

# Weighted signal, weights v2 (T130): PLAN

[MODE: VALIDATE]

Date: 21-10-26
Complexity: SIMPLE (one slice, api only, no web)
Status: VALIDATED: Gate: PASS
Validation: T130 worker, FAST MODE (compressed RESEARCH/PLAN/VALIDATE in one session) on `main` 24b1d5e. The owner's ENTER EXECUTE MODE covers this change only (envelope).

**Summary:** The owner locked new source weights (they need not sum to 100), a "search" vote group (trends and wikipedia), and an early-source rule: a coin can only trigger when trends, reddit or xsearch is rising. github_dev is parked at weight 0. The scorer selects the weights version by the day being scored, so days up to 2026-10-21 keep v1 in live scoring, frozen snapshots and the history chart, and days after it use v2. The change is api-only. The response gains an additive `weights_version` field and the web stays unchanged.

## 1. Research findings (main 24b1d5e)

- Scoring is `discovery._coin` (`api/analytics/attention/discovery.py:143-164`), used by live Discovery, the snapshot job (`signal_snapshots.take_snapshot` runs `build_discovery`) and the history chart (`discovery_history._score_day`, which RECOMPUTES every past day with the current config).
- `source_groups` does NOT exist today: T98 removed it (weighted-signal SPEC decision 1; `test_shipped_config_is_valid_and_sums_to_100` asserts its absence). The group mechanism is new here.
- Validation (`discovery.py:43-75`): unknown keys in `source_weights` already rejected, negative rejected, sum must be 100. There is no top-level unknown-key check.
- Weight 0 is already skipped in `_coin`, but `series_names` still reads every weighted source, and the Sources panel (`sources.py:131`) lists github_dev as a weighted source that shows `not-probed`.
- Frozen snapshots: 12 files 2026-10-17..20, all scored with v1 weights (`config.source_weights` = v1 in each). Reader `read_snapshots` never rewrites.
- Today's data: every snapshot row has only coingecko (exchange slot) and/or wikipedia (2026-10-20_w30: 26 coins coingecko only, 25 coingecko+wikipedia).

## 2. Decisions

| # | Decision |
|---|---|
| D1 | `source_weights` v2: trends 25, reddit 20, xsearch 15, exchange_activity 15, wikipedia 10, defillama 5, github_dev 0. The sum-to-100 rule is dropped for `source_weights` (total must be > 0). It stays for `exchange_sub_weights`. Scoring already rescales over available weight. |
| D2 | `source_groups: {"search": ["trends", "wikipedia"]}`. Group rule: available members' weights sum to the group weight. The group counts as rising iff its rising members' weight is at least 50% of that group weight. A rising group adds its full available weight to `rising_weight`, and a non-rising group adds 0. Covered weight and the score (weighted mean change) are unchanged: the group only affects the trigger vote. Example: trends rising and wikipedia flat gives 25/35 = 71%, so the group is rising and adds 35. Wikipedia rising alone gives 10/35, so it adds 0. |
| D3 | `early_sources: ["trends", "reddit", "xsearch"]`. A coin triggers iff (a) at least one early source is usable and rising (its own raw change >= `rising_threshold_pct`), (b) `rising_weight * 100 >= trigger_pct * covered`, and (c) `covered >= min_covered_weight`. Confirming sources alone never trigger. |
| D4 | Weight 0 = parked. The source is not read (`series_names` excludes it unless an older weights version gives it weight), not counted in covered or rising weight, and its Sources row is `state: "off"`, note `parked: weight 0, not fetched`. It is excluded from `total_sources`, so it is not shown as failing. No fetcher exists for github_dev, so nothing fetches it today. |
| D5 | Weights versions by day: `weights_version: 2` plus `weights_history: [{weights_version: 1, until: "2026-10-21", source_weights: v1, source_groups: {}, early_sources: []}]`. `weights_for_day(cfg, day)` returns the version whose `until` covers the day (the first entry with day <= until), else the top-level (current) one. Live, snapshot and history all score day D with that version. As a result, past chart days and frozen days are never rescored with v2, and no frozen file is recomputed. |
| D6 | Frozen snapshots are not rewritten. New records carry a top-level `weights_version`. `read_snapshots` adds `weights_version` to each row in memory (1 when the record has none). The full config, including history, is stored and hashed as before. |
| D7 | Strict load: the top-level keys must come from a closed set (REMOVED_KEYS keep their specific message). Group members, group names and `early_sources` must be known weighted source ids. A source may belong to at most one group, and `exchange_activity` is allowed in a group. History entries are validated the same way (versions strictly increasing and below `weights_version`, `until` dates strictly increasing). A config without the new keys behaves as before: no groups, no gate, version 1. |
| D8 | Additive response fields: `weights_version: int = 1` on `DiscoveryResponse`, `DiscoveryHistoryDay` and `DiscoveryCategoryDay`. No web change. Web types ignore the extra field. Two follow-ups are left out: the web chart marking v1/v2 points and the Sources header text "of 100 weight". |
| D9 | `min_covered_weight` stays 30 (absolute). With v2 the max is 90. Any coin that can trigger needs one early source, and the smallest early source (xsearch 15) plus the exchange slot (15) gives exactly 30. So the floor equals "one early source plus one confirming source", which is consistent with D3. Impact today: coins have only exchange slot plus wikipedia, which gives 25 < 30. Under v2 every coin is thin and nothing triggers until trends, reddit or xsearch data lands (under v1 the same coins had 35). That is expected and owner-visible. |
| D10 | `until: "2026-10-21"` assumes the merge lands before the 2026-10-23 refresh (which would freeze day 2026-10-22 under v1). A guard test checks that every committed frozen snapshot's weights equal `weights_for_day` for its date. (Corrected by T150: the weights a record was scored with are its own config's version for its day, or its `weights` field. Reading the stored top-level `config.source_weights` was a test bug, because since T130 that field holds the current version.) If main gains a later v1 snapshot first, that test goes red on merge-in, and the fix is to move `until` to the last v1 day. |

Baskets tab scores are untouched (`score.py`/`basket.py` do not read `discovery.json` weights).

## 3. Files

- `api/data/discovery.json`: D1, D2, D3, D5.
- `api/analytics/attention/discovery.py`: validation (D7), `weights_for_day`, group and early gate in `_coin`, `series_names` over all versions with weight > 0, `weights_version` in `build_discovery`.
- `api/analytics/attention/discovery_history.py`: score each day with `weights_for_day`; per-day `weights_version`.
- `api/analytics/attention/signal_snapshots.py`: record `weights_version`; reader adds it in memory.
- `api/analytics/attention/sources.py`: weight 0 row `off`, not counted.
- `api/models/discovery.py`: D8 fields.
- Tests: `test_discovery.py`, `test_discovery_history.py`, `test_signal_snapshots.py`, `test_sources.py`, router key-set tests, new `test_weights_v2.py`.
- Docs: weighted-signal SPEC gets one short addendum line naming this plan (the SPEC's config section).

## 4. Red tests (new, `api/tests/analytics/attention/test_weights_v2.py`)

Table tests: rescale with v2 weights (score = sum w*c / available), group vote (the 4 cases of D2), early gate (confirming-only never triggers even at 100% rising, early rising plus confirming triggers, early present but flat does not), weight-0 source ignored (data present, not in covered weight, not read), load validation (unknown top-level key, unknown group member, unknown early source, negative weight, source in two groups, bad history entry, history until order), `weights_for_day` boundary (2026-10-21 v1, 2026-10-22 v2), snapshot frozen (an existing file stays byte-identical and the v1 record reads back with `weights_version` 1), committed-snapshots guard (D10), history day carries the version and a v1 day's value is unchanged by the v2 switch.

## Validate Contract

| Gate | Command | Pass |
|---|---|---|
| G1 red first | new tests fail on main code before the implementation | failures recorded in the report |
| G2 full suite | `UV_FROZEN=1 uv run --project api pytest api -q` | baseline 1811 passed, 1 skipped, 5 deselected on main 24b1d5e, plus the new tests. 0 failed. |
| G3 scope | `git diff --stat origin/main...HEAD -- web .github` | empty |
| G7 frozen snapshots | `cd api/data/cache/attention/signals && sha256sum -c` over the 12 pinned hashes (report) | 12 lines `OK` |
| G8 hygiene | `git diff --check origin/main...HEAD` plus the secret scan of earlier plans | exit 0, prints nothing |

Gate: PASS (no blocking gap; the D10 merge-timing gap is guarded by a test, not left open).
