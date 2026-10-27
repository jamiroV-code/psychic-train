# T203 report: Trends time budget 540 -> 780 s, step limit 14 -> 18 min (27-10-26)

## 1. Task
Raise the Trends budget and the workflow step limit so healthy coins are not cut (quality over speed). Owner answer 27-10-26: "Both: raise now + server later"; written approval to edit `attention-refresh.yml` for the Trends step timeout only.

## 2. Changes
- `api/scripts/refresh_attention.py`: `TRENDS_TIME_BUDGET_S` 540 -> 780, comment with the arithmetic; breaker comment corrected (3 x 210 s = 630 s < 780 s, so the breaker can now fire before the budget; it is unchanged).
- `.github/workflows/attention-refresh.yml`: Trends step `timeout-minutes` 14 -> 18 (nothing else).
- Guard test and the budget test updated (see 6).

## 3. Timeout arithmetic
Step: budget 780 s + install ~60 s + one in-flight request ~60 s + store/archive/run-record ~60 s = ~960 s = 16 min; limit 18 min leaves 2 min margin (guard relation: limit >= budget + 120 s: 1080 >= 900).
Job: Binance 4 + Hyperliquid 4 + Trends 18 + Reddit 8 = 34; plus install/verify/probe/commit ~5 = 39 <= 40. The job limit stays 40 and was not touched.

## 4. Unchanged on purpose
Spacing (3 s + jitter), backoff (30/60/120 s), breaker (3) and the 20-retry cap. Nothing sped up. The deferred retry pass (PR #181) runs inside the same budget check, so it stays inside the new 780 s.

## 5. Why 780
At ~4 s per request, 92 keyworded coins need ~370 s plain; the old 540 s budget lost ~14 healthy coins once retries are counted (T199). The real run of 26-10-26 used ~5.5 min for 71 coins.

## 6. Tests
Red first: the guard (`== 780`, `== 18`) and `test_time_budget_caps_the_rest` failed on 540/14, passed after. The guard keeps pinning the relations (limit >= budget + 120 s; sum of step limits + 5 <= job limit), not only the literals. `test_refresh_attention_trends.py` is outside the file-set in the envelope but asserts the constant, so it had to change (sleep step 200 -> 300 s to keep "fifth coin stopped").

## 7. Gates
See the PR: guard + ci_workflow tests 28 passed; `api/tests/scripts` + `api/tests/data/attention` all passed after the fix; full `pytest api` 2253 passed, 1 skipped, 5 deselected; ruff: 19 errors on touched files, identical on main (none new); ruff, YAML parse, `git diff --check`, secret scan clean.

## 8. Not provable
Real run time. The next daily run shows it; the per-coin run record from PR #181 gives the timing. If the step nears 18 min, recompute before raising again (job sum is already 39 of 40).

## 9. Later slice (not built): W8e2 host profile
The 24/7 laptop runs the full Trends pass with no runner deadline; GitHub stays the capped fallback. This removes the budget as a quality limit.

## 10. Risk
A bad day (many 429s) can use the whole 18 min; the job still fits 40 min. Daily-run duration grows by up to 4 min.

## 11. Files opened beyond the envelope
None beyond `test_refresh_attention_trends.py` (see 6).
