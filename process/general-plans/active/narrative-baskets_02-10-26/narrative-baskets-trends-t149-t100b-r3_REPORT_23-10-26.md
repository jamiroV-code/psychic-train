---
name: report:narrative-baskets-trends-t149-t100b-r3
description: "T149 round 3: fixes from the independent re-review T158 on PR #162 (L1 to L9, required and optional). Full API green."
date: 23-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: report
---

# T149 round 3 (T158 re-review fixes on PR #162): REPORT

## 1 Task ID

T149 round 3. Fixes from re-review T158 (verdict MERGE AFTER SMALL FIXES) on PR #162, branch `claude/t149-t100b-trends-fetch`. Rounds 1 and 2 have their own reports in this folder.

## 2 Outcome

done. Every required item (L1, L2, L4, L5, L7, L9) and every optional item (L3, L6, L8) is in.

## 3 Summary

- **L1:** `fetch_alone` really never raises now. The frame handling is wrapped, so a non-DataFrame, an integer or string index, or duplicate columns give `unavailable` with reason `parse-failed: <Class>` (class only) and never cost the other coins.
- **L2:** a partial row inside the series leaves non-consecutive kept points. That is now `gap`, and nothing is stored. Before, the result read ok while the store guard silently rejected it.
- **L3 (optional):** a value outside 0..100, or not finite, is `bad-value` in `fetch_alone`. The store's replace guard also rejects NaN, inf and negative values (100 is a Trends-only bound, so the store does not check it).
- **L4:** `why` is set before the client `try`. A factory that returns None gives `session-failed: no client`.
- **L5:** symbols are de-duplicated case-insensitively before any request (`AAVE,aave` costs one request).
- **L6 (optional):** a comment at `TRENDS_BREAKER_AFTER`. At the production constants the 429 breaker cannot fire: 3 coins x 210 s of backoff exceeds the 540 s budget, which stops the source first.
- **L7:** one failed store write (for example OSError) no longer stops the remaining writes.
  - The coin becomes `unavailable` with reason `store-failed: <Class>`, which is counted in the source's `trends:` line.
  - A final `trends: error store-failed: <Class> xN` line follows, so the verifier reads it as failed (red) and the exit code is 1.
  - This applies to every source, because `main()` shares one store loop.
- **L8 (optional):** `quiet-then-surge` now also needs the last-week median to be at least `SURGE_RATIO` (3) times the baseline median, not just a threshold crossing.
- **L9:** boundary tests:
  - last-week median exactly 3 is a surge; 2 is not;
  - 5 live days out of `SURGE_DAYS` 7 is not a surge; 7 is;
  - the 3x ratio is exact.

## 4 Files changed

`api/data/attention/trends.py`, `api/data/attention/store.py`, `api/scripts/refresh_attention.py`; tests in `test_trends.py` (+15 cases), `test_store.py` (+3), `test_refresh_attention_trends.py` (+3); this report. All within the PLAN's file list. Nothing under `.github/`.

## 5 Commits

On `claude/t149-t100b-trends-fetch`: one fix commit plus this report (see the PR). origin/main was already merged (no new commits on main since 534e949).

## 6 Tests run

All runs used `UV_FROZEN=1 PYTHONDONTWRITEBYTECODE=1`, on 23-10-26 UTC.
- **Red first:** 15 failed before the code. The 4 L9 boundary cases were green by design: they pin the existing boundaries, and the mutations below prove them.
- **G1** (5 Trends test files): 138 passed.
- **Full API:** **1980 passed, 0 failed**, 1 skipped, 5 deselected. Before this round: 1961. +19 tests.
- **G7:** 3x OK. `git diff --check` is clean.
- **ruff:** only the old BLE001 at `trends.py:30` remains; it was already there.
- **Mutations:** 10, all killed. Stale-pyc protection was on (no bytecode written, mtime bump after each restore).

| Mutation | Killed by |
|---|---|
| remove the frame-handling try | `test_fetch_alone_malformed_frame_never_raises` (4 cases) |
| remove the interior-gap check | `test_fetch_alone_interior_partial_row_is_a_gap` |
| `0 <= v <= 100` -> `0 <= v` | `test_fetch_alone_rejects_out_of_scale_values[101.0]` |
| drop the surge ratio | `test_surge_needs_a_ratio_over_the_baseline` |
| `>=` -> `>` on the last-week median | `test_surge_boundaries` (median exactly 3) |
| all 7 live -> at least 5 live | `test_surge_boundaries` (5 of 7) |
| remove the store finite/negative guard | `test_replace_series_rejects_non_finite_or_negative` |
| remove the symbol de-duplication | `test_duplicate_symbols_cost_one_request` |
| ignore store failures | `test_one_store_failure_keeps_storing_the_others` |
| change the factory-None reason | `test_factory_returning_none_marks_coins_unavailable` |

## 7 Tests NOT run

No live Google call. Web checks were not run (web untouched).

## 8 Deviations

L7 is applied in the shared `main()` store loop, so a store failure in any source now keeps storing the other coins. Before, the first failure stopped that source's remaining writes. The red result is unchanged: the last line is still an `error` line, and the exit code is 1 when that source is the only one run.

## 9 Blockers

None. Unchanged from round 2: M1 is a separate task (T100b-PIT), and M2b stays NO for now (owner decisions of 23-10-26).

## 10 Follow-up

T100b-PIT; T100c (owner approval of the `.github/` change).

## 11 Context cost

Loaded: the T158 message, the current `trends.py`, `refresh_attention.py` and `store.py` sections being edited. About 25k tokens for this round. USD not metered; my estimate is that all rounds together are under the 10 USD ask level. Tools: Bash, file tools, GitHub MCP, send_message.
