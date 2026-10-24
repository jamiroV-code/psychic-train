# T83 P5 fix pack report

## 1 Task ID
T83, branch `claude/t83-p5-fixpack`, base `origin/main` ea4065b. API only.

## 2 Outcome
Done. F-1, F-2, F-3, F-8, F-13 fixed; F-7 noted only. Draft PR opened against main, not merged.

## 3 Summary
- F-1: weights and discovery files now use fetcher names (`exchange_volume`, `xsearch`). `xsearch` weight is one value, 0.25, in the JSON only; `xsearch.WEIGHT` and `registry.SOURCE_WEIGHTS` deleted. `hyperliquid_volume` is explicitly excluded (`registry.EXCLUDED_SOURCES`): it is the same volume group as exchange_volume and adds no independent signal. `source_groups` keeps coingecko and exchange_volume in group "volume" (AC-41).
- F-2: breadth lag is the selected window (7/30/90); `BREADTH_LAG_DAYS` removed.
- F-3: `store.read_points` raises `StoreReadError` on an unreadable file; `registry.read_series` maps it to state `unavailable`. Baskets and Discovery both go through `read_series`.
- F-8: four comments updated (comment/JSON-string only).
- F-7: the `mapping.py` docstring edit from T80 is left as is. This task edits a comment in `mapping.py` (~line 23) as the envelope asked.
- Known limits: `write_series` and `scripts/record_probe.py` call `read_points`, so a corrupt file still raises there. That is intended: no silent overwrite of history, but the owner must delete the bad file. The F-2 test patches `coin_score_at` by day to reproduce the report's numbers; no end-to-end fixture with a naturally rising-then-falling series.

## 4 Files changed
api/data/attention_weights.json, api/data/discovery.json, api/data/attention/{registry,store,xsearch}.py, api/analytics/attention/basket.py, comments in api/data/narrative_categories.json and api/analytics/narrative/{mapping,narrative_config,exchange_attention}.py, api/tests/data/attention/test_xsearch.py (weight now read from the JSON), new api/tests/analytics/attention/test_fixpack_p5.py (7 tests), this report.

## 5 Commits
One commit on the branch (see PR).

## 6 Tests run
- Red first: `UV_FROZEN=1 uv run --project api pytest api/tests/analytics/attention/test_fixpack_p5.py -q` -> 6 failed (1 of the 7 passes before the fix).
- `UV_FROZEN=1 uv run --project api pytest api/ -q` -> 1393 passed, 1 skipped, 5 deselected (2026-10-17 UTC, base SHA ea4065b plus working tree). Baseline floor 1377; the 7 new tests are in this count; I did not re-measure untouched main.
- `git diff --check origin/main`: clean. `git diff --exit-code api/uv.lock api/pyproject.toml`: clean. `git diff origin/main -- web`: empty. 4 tracked coingecko parquet files restored. AC-25 tests untouched.

## 7 Tests NOT run
Web tests, Playwright, any network or provider call.

## 8 Deviations
Edited `mapping.py` (comment) because the envelope listed it under F-8. Modified one existing test (`test_xsearch.py`) because it read the deleted constant.

## 9 Blockers
None.

## 10 Follow-up
F-4, F-5, F-6, F-9..F-12 untouched. Slice G probes must record `exchange_volume` and `xsearch` names.

## 11 Context cost
CLAUDE.md 13,443 B, report sections 4 and 9, touched code; under the 36,000 B cap is not guaranteed (code reads were extra). No other docs opened.
