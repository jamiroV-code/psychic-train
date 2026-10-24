# T88 (P5) refresh fix - REPORT

## 1 Task ID
T88 (P5), branch `claude/t88-p5-refresh-fix`, base origin/main.

## 2 Outcome
Done. Rate-limit handling, per-host pacing and self-explaining failure lines are in. Draft PR open, not merged. The next live run will show whether the fixes are enough.

## 3 Summary
**Confirmed by code and by the log's own timing:**
- `universe`/`categories` `RuntimeError` came from `coingecko_attention.fetch_*` returning `None` on any failure. The reason was thrown away, then the runner raised a bare `RuntimeError("... unavailable")`, and `main` printed only the class name. This is why no reason was visible.
- The old retry was 3 attempts with sleeps of 1 s and 2 s and no pacing. Counting the failures from the log shows persistent 429s: wikipedia has 58 - 20 = 38 failed coins at about 3 s each, and coingecko has 46 at about 3 s each. That adds up to about 252 s, which is the observed 4m10s. `categories` died in about 4 s, which is exactly one call with its 3 s of backoff.
- A 429 burst on a shared runner IP is therefore the most consistent cause. The old code had no pacing at all (about 100 wikipedia calls and 56 CoinGecko calls back to back).

**Changes:**
- New `api/data/attention/http_retry.py` with:
  - `get_with_retry`: retries 429 only, honours `Retry-After` (capped), otherwise exponential backoff with jitter.
  - `Pacer`: per-host minimum spacing between calls.
  - `redact`/`describe_exc`: ASCII-only output, URLs, `key=`/token/Bearer strings, IPs and long tokens removed, 120 characters max. Headers and URLs are never printed.
- CoinGecko: paced at 1 call per 6 s, 3 retries on 429 with backoff of 5/10/20 s plus jitter, and a descriptive User-Agent.
- Wikipedia: identifying User-Agent with the repo URL, paced at 0.25 s, 3 retries on 429.
- `LAST_FAILURE` in `coingecko_attention` records why `fetch_top100`, `fetch_top100_markets` or `fetch_categories` returned `None`. The runners put it in the `RuntimeError` message.
- Lines now read `universe: error RuntimeError: markets unavailable: HTTP 429`.
- Source lines gain `[ok 20, no-article 45, rate-limited 38, ...]`. The `N/M ok` prefix is unchanged, so the workflow verifier regex still matches.
- A circuit breaker stops a source after 5 consecutive rate-limited coins and marks the rest `capped` without requests. Without it, persistent 429s with the longer backoff would take about an hour. A failed coin never aborts the batch.

**Known limits / hypotheses until the next live run:**
- Hypothesis: persistent 429 is the cause. The code and timing support it, but the status was never logged. A 403/401 is possible and would now show as `HTTP 403`.
- Hypothesis: 6 s pace plus the wikipedia UA fix will lift the ok counts. Not provable offline.
- Projected runtime is about 6 min for the default run (about 58 CoinGecko calls at 6 s) plus categories at about 8 s per category (6 s pace plus the old 2 s pause). The workflow has no `timeout-minutes`, so GitHub's 360 min default applies.
- If CoinGecko still 429s from the runner IP, the next step is a demo API key via a secret (an owner decision), not more retries.
- I kept the state name `capped` for rate limiting. It is a shared Literal used by `record_probe` and the models, and renaming it is out of scope. The summary prints it as `rate-limited`.

## 4 Files changed
- `api/data/attention/http_retry.py` (new)
- `api/data/attention/coingecko_attention.py`
- `api/data/attention/wikipedia.py`
- `api/scripts/refresh_attention.py`
- `api/tests/data/attention/conftest.py` (autouse fixture zeroing pacers so tests never really sleep)
- `api/tests/data/attention/test_http_retry.py` (new, 14 tests)
- this report

## 5 Commits
One commit: `fix(attention): pace and retry 429, explain refresh failures (T88)`.

## 6 Tests run
- Red first: `test_http_retry.py` failed at import before the implementation.
- Full suite `UV_FROZEN=1 uv run --project api pytest api/ -q`: **1418 passed, 1 skipped, 5 deselected**.
- Baseline was 1377 passed / 1 skipped / 5 deselected or higher. The suite includes 14 new tests; the rest of the increase is later merges.
- The attention and scripts subset on the stashed (untouched) tree: 330 passed.
- Gates: `git diff --check` clean. `api/uv.lock` and `api/pyproject.toml` unchanged. `git diff origin/main -- web .github` empty. The 4 narrative parquet files were restored. The protected AC-25 tests were not touched.

## 7 Tests NOT run
Any live call to Wikipedia or CoinGecko (forbidden). The real workflow.

## 8 Deviations
- `capped` kept as the state name (see 3).
- The circuit breaker and the autouse test fixture go slightly beyond the asks but follow from them (runtime bound, tests not sleeping).
- The read cap was slightly exceeded (about 37 KB against 36 KB) because I read the full fetcher files.

## 9 Blockers
None.

## 10 Follow-up
- After the next live run, read the new `error ... HTTP <n>` and outcome counts. If it is still 429, consider the demo key route or splitting the schedule.
- Optional workflow change, not applied because `.github` is forbidden. Add `timeout-minutes: 90` to the job, since a paced run can take 15 to 20 minutes and a stuck run should not use 360 min:
```diff
   refresh:
     runs-on: ubuntu-latest
+    timeout-minutes: 90
```
- The verifier can stay as is. It treats 0 ok as FAILED, and a partial ok still commits the ok coins.

## 11 Context cost
About 15 file reads and 9 shell calls, well under the cap in spend.
