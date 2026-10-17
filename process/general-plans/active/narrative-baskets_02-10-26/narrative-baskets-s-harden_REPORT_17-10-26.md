# T93 (P5) extra-sources hardening - REPORT

## 1 Task ID
T93 (P5), branch `claude/t93-p5-extra-hardening`, base origin/main.

## 2 Outcome
done (DRAFT PR, not merged). Suite: 1473 passed, 1 skipped, 5 deselected, 0 failed.

## 3 Summary
- M1: `_collect_guarded` (refresh_attention.py) now drives Trends and Reddit: after 5 consecutive provider blocks it stops requesting and marks the rest `capped` (printed `rate-limited`) with reason "skipped after repeated provider failures"; never 0, never fetched. Soft time budget `SOURCE_TIME_BUDGET_S = 360` s per source: remaining symbols get reason "time budget reached". Fetched series are kept and stored by the unchanged store loop. Reddit uses `reddit.Session`: one OAuth token per run, one refresh after a 401 (`reddit_adapter._fetch_with_backoff` got an optional `status_out` dict; default behaviour unchanged).
- M2: `attention_extra.classify`: a line with `reasons:` is `failed` when code-class reasons (`fetch-failed: X`/`parse-failed: X`, X outside PROVIDER_CLASSES, no HTTP) weigh at least as much as all other reasons (weights from the `xN` counts); otherwise `unavailable`. Plain data outcomes and `BadSymbol` count as non-code.
- L2: Hyperliquid runner calls `fetch_daily_market_snapshot` once and fans out via the existing `snapshot=` parameter; stored values unchanged.
- L4: refresh-extra `timeout-minutes` 30 -> 40; guard test updated.
- Guide 6b reworded (4,893 B, ASCII).
- Known limits: `reason_summary` shows only the top 3 reasons, so M2 weights use those only. The breaker counts only provider blocks, so a code error in every symbol still runs all symbols (fast, and now red). The time budget is checked between symbols, so one slow call can overrun it. A pre-existing quirk remains: a mostly-blocked run that stored some rows is `ok` for classify, as before. Not measured against live providers.

## 4 Files changed
.github/workflows/attention-refresh.yml (one line); api/scripts/refresh_attention.py; api/scripts/attention_extra.py; api/data/attention/reddit.py; api/data/reddit_adapter.py; api/tests/scripts/test_attention_extra.py; api/tests/scripts/test_refresh_attention_extra_hardening.py (new); api/tests/tooling_guards/test_attention_workflow_guard.py; owner guide; this report.

## 5 Commits
One commit on the task branch (see PR).

## 6 Tests run
Red first (15 failing before the code). Then `UV_FROZEN=1 uv run --project api pytest api/ -q`: 1473 passed, 1 skipped, 5 deselected (baseline 1455 + 18 new). `python3 yaml.safe_load` of the workflow: ok. Gates git diff --check, lock/pyproject, web and .github scope are listed under heading 8.

## 7 Tests NOT run
actionlint (not installed offline). No workflow run, no live refresh, no network.

## 8 Deviations (adversarial review)
(a) Core refresh job: `git diff` of the workflow is a single hunk at the refresh-extra job (`timeout-minutes: 30` -> `40`); the `refresh` job lines are identical. wikipedia/coingecko/universe/categories runners and `_collect` untouched; `main()` untouched. Shared edit: `reddit_adapter._fetch_with_backoff` gained an optional kwarg; existing callers pass nothing and behave identically (reddit adapter tests green).
(b) Probe records: `verify` is unchanged. The only new way a line turns red is M2, which prevents a probe for a source that is now failed; `ok` lines are decided exactly as before (rows written > 0 plus freshness). A partial run with rows stored is `ok` as before.
(c) Secrets: the token lives only in memory inside `Session`; nothing printed or logged; reasons are class names and codes only.
(d) Time budget: it is checked before each fetch and only converts not-yet-fetched symbols to `capped`; already fetched series stay in the returned list and are stored (test `test_time_budget_stops_cleanly_and_keeps_fetched`).
(e) YAML valid per PyYAML; actionlint not run.
Also: deviation from the envelope - I added `BadSymbol` as a data class (unlisted symbol on Binance is not a code error); disclosed here.

## 9 Blockers
None.

## 10 Follow-up
Run refresh-extra once live and check the printed lines; consider a longer reason list if M2 needs more than the top 3 reasons.

## 11 Context cost
CLAUDE.md plus the report parts, five code files and the guide section: within the 36,000 B cap. Spend well under 4 USD.
