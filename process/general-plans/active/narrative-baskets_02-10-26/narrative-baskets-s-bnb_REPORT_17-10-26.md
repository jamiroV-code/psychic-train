# T87 report: keep BNB in Discovery

1. **Task ID:** T87 (branch `claude/t87-keep-bnb`)
2. **Outcome:** done. BNB is no longer excluded from Discovery; LEO OKB CRO GT KCS BGB MX stay excluded.
3. **Summary:** BNB was dropped in three places: `discovery.json` `exclude`, the CoinGecko `exchange-based-tokens` category (`exclude_category_ids`), and `attention_universe.json` `exchange_tokens` (which `load_universe` uses to build the reference). Removed BNB from the first and third, and added `include_despite_category: ["BNB"]` to `discovery.json`, honoured in `discovery.py` (an allow-listed symbol is un-excluded from category exclusion unless it is in `exclude`). `decisions.md` D-20 now reads "owner confirmed 2026-10-17: BNB kept, LEO OKB CRO GT KCS BGB MX excluded", status active.
   **Known limits:** `attention_universe.json` is shared, so BNB also re-enters the main attention reference, not only Discovery. The `include_despite_category` key is optional (absent = old behaviour). Discovery needs BNB's CoinGecko volume over the 20M floor and two agreeing source groups, as for any coin.
4. **Files changed:** `api/analytics/attention/discovery.py`, `api/data/discovery.json`, `api/data/attention_universe.json`, `api/tests/analytics/attention/test_discovery.py` (2 new tests), `api/tests/analytics/attention/test_universe.py` (pinned list updated), `process/context/decisions.md`, this report.
5. **Commits:** one on `claude/t87-keep-bnb`.
6. **Tests run:** red-first: the 3 new/updated tests failed on base (3 failed, 46 passed in `api/tests/analytics/attention`). Full `UV_FROZEN=1 uv run --project api pytest api/ -q`: 1406 passed, 1 skipped, 5 deselected (envelope baseline >= 1377; +2 new tests). The 4 tracked coingecko parquet files were restored before commit.
7. **Tests NOT run:** untouched-origin/main full-suite baseline was not re-measured (the envelope's expected figure was used); no network or provider runs.
8. **Deviations:** also edited `attention_universe.json` and `test_universe.py` (not named in the envelope) because the universe exclusion would otherwise still hide BNB.
9. **Blockers:** none.
10. **Follow-up:** owner may want a one-off Discovery refresh to see BNB in its categories.
11. **Context cost:** about 45 KB read/tool output, well under the cap.
