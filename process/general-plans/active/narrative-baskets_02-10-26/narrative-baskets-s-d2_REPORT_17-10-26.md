# T80 S-D2 report: delete the old verdict code

## 1 Task ID
T80 (P5 S-D2), branch `claude/t80-p5-s-d2-delete-verdict`, base origin/main c918d85.

## 2 Outcome
DONE. `trigger.py` and `momentum.py`, `/categories` and `/momentum`, and their models and tests are deleted. No live importer was found first (git grep over api, web, scripts). `/history` and `/mindshare` are unchanged.

## 3 Summary
- Deleted `api/analytics/narrative/{trigger,momentum}.py`.
- `routers/narrative.py`: dropped both routes and the trigger import; `min_sources` now reads `history.MIN_AVAILABLE_SOURCES` (same value, 2, which D1 already owns).
- `models/narrative.py`: dropped `NarrativeTriggerState`, `NarrativeCategory`, `SourceAvailability` and the two momentum models. `/history` models are untouched, `trust_weight` stays in the composite point.
- New `api/tests/analytics/test_no_narrative_verdict_fields.py` (11 tests). Red first on base: 9 failed, 2 passed (the 2 are the `/history` key pins, as intended). Green after the deletion.
- Known limits: the plan's AC-11 wording also says no `trust_weight` in `/history`; the envelope overrides it (keep, JSON byte-identical), so the guard pins `trust_weight` and scans only `triggered|confirmed`. Web has no consumer of the removed routes (git grep empty), so web is untouched.

## 4 Files changed
Deleted: `trigger.py`, `momentum.py`; tests `analytics/test_narrative_trigger.py` (old trigger logic), `analytics/narrative/test_trigger_tripwire.py` (froze trigger.py's API), `analytics/narrative/test_momentum.py` (momentum module), `routers/test_narrative_categories_contract.py` and `routers/test_narrative.py` (/categories only), `routers/test_narrative_momentum.py` (/momentum).
Edited: `routers/narrative.py`, `models/narrative.py`, `test_narrative_v2_boundaries.py` (momentum block removed), `test_narrative_history.py` (get_categories-separation test removed), `test_screener_no_verdict_contract.py` (trigger import and patches removed), `test_exchange_attention.py` (trigger.py dropped from the scanned list), `test_onchain_activity_router.py` (`/categories` dropped from the route list), comment-only rewords in `history.py` line 50 and `mapping.py` lines 6, 43.
Added: `api/tests/analytics/test_no_narrative_verdict_fields.py`.
`test_no_verdict_symbols.py` needed no edit.

## 5 Commits
One commit: `refactor(narrative): delete trigger and momentum verdict code (T80 S-D2)`, plus this report.

## 6 Tests run
- Baseline, untouched origin/main c918d85, `UV_FROZEN=1 uv run --project api pytest api/ -q`: 1406 passed, 1 skipped, 5 deselected (2026-10-17 ~09:3x UTC).
- Guard test on base: 9 failed, 2 passed (red first).
- After, `UV_FROZEN=1 uv run --project api pytest api/ -q`: 1377 passed, 1 skipped, 5 deselected, 2026-10-17T09:5xZ, on the working tree at base c918d85 plus the uncommitted change. Arithmetic: 1406 - 40 removed + 11 new = 1377.
- `git diff --check`: clean. `git diff --exit-code origin/main -- api/uv.lock api/pyproject.toml web`: clean.
- AC-25 protected tests (pytrends partial-hour, nightly archive): untouched and green.

## 7 Tests NOT run
vitest (web untouched). ruff (repo already reports 354 pre-existing findings).

## 8 Deviations
- `trust_weight` kept in `/history` (envelope), against the plan's AC-11 wording.
- Comment-only edits in `history.py` and `mapping.py` (outside the D2 owned list) so the source scan passes.
- `routers/test_narrative.py` deleted rather than edited, because every test in it covered `/categories`.
- Running the suite rewrites four tracked `api/data/cache/narrative/coingecko/*.parquet` files; restored, not committed.

## 9 Blockers
None.

## 10 Follow-up
- Stale prose mentions of `trigger.py` remain in docstrings of `coingecko_adapter.py`, `pytrends_adapter.py`, `hyperliquid_narrative_adapter.py`, `exchange_attention.py`, `narrative_config.py`, `snapshot_narrative.py`, `backfill_pytrends_history.py`, `cache.py`, `test_scoring.py`, `migrate_narrative_config.py`, plus docs (`all-context.md`, `all-tests.md`, `all-data-sources.md`). Docs sweep and the legacy `coingecko/{category}` series freeze note belong to the plan's closing slice.
- `trust_weight` in the composite is still history-owned (D1 follow-up unchanged).
- The suite dirties the tracked coingecko parquets.

## 11 Context cost
CLAUDE.md, envelope, plan D2 slice and decisions, D1 report heading 10, and the capped code ranges; well within the 36,000 B cap.
