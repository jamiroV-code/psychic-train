# T75 (P5 S-B3) report: Reddit and X sources

## 1 Task ID
T75, branch claude/t75-p5-s-b3-reddit-x, base origin/main 212fc59.

## 2 Outcome
Done. Reddit and X sources added, fixtures only; all gates green. Draft PR opened, not merged.

## 3 Summary
- reddit.py wraps reddit_adapter (token and search helpers); no REDDIT_CLIENT_ID/SECRET = unavailable with zero network. One point per run: post count of the last-day window, dated the last completed UTC day.
- xsearch.py: token only from os.environ.get("X_BEARER_TOKEN") at call time, used only in the Authorization header; failures log type(exc).__name__ only. X_LIVE off = dry run (zero network, estimate() gives planned reads and USD; the runner prints it). Caps X_MAX_READS_PER_RUN / _PER_DAY / X_MAX_USD_PER_DAY, X_USD_PER_READ (defaults 10 / 50 / 1.0 / 0.01); day counter in cache/xsearch_usage/<date>.json; each read counts before it is sent (failed reads count). At a cap the series state is `capped`.
- X returns only the last completed day per run, so the store holds X's own rows and read_series reports insufficient-history until 90. WEIGHT 0.25 (registry.SOURCE_WEIGHTS). Spike over 10x median sets a "spam-flag" reason.
- registry.FETCHERS gained reddit and xsearch; refresh_attention RUNNERS gained _run_reddit, _run_xsearch; DEFAULT_SOURCES unchanged.
- Known limits:
  - X unit price and default caps are guesses; the owner must set X_USD_PER_READ from the real plan.
  - The X endpoint (tweets/counts/recent, granularity=day) was never called live; response shape follows X docs, unverified.
  - Reddit count is capped at 100 (adapter limit) and dated yesterday for a rolling 24h window.
  - Spam flag is a spike heuristic only, not bot detection.
  - xsearch/reddit have no probe record, so the store reader reports them not-probed until slice G.

## 4 Files changed
api/data/attention/{reddit,xsearch,registry}.py; api/scripts/refresh_attention.py; api/tests/data/attention/{test_reddit,test_xsearch,test_registry}.py; api/tests/scripts/test_refresh_attention.py; this report.

## 5 Commits
ac404f7 red tests; fead529 implementation; report commit follows on the branch.

## 6 Tests run
- Baseline, untouched origin/main tree: UV_FROZEN=1 uv run --project api pytest api/ -q = 1342 passed, 1 skipped, 5 deselected (2026-10-17T05:47Z; tests collected before my test edits).
- Red count: 18 (reddit 4 + xsearch 12 not collectable, plus 2 failing: registry set, pinned runners).
- After, SHA fead529: same command = 1360 passed, 1 skipped, 5 deselected (baseline + 18) at 2026-10-17T05:51Z.
- Local swap demo: DEFAULT_SOURCES + "xsearch" failed 2 tests; swapped reddit/xsearch runners failed the pinned test; both reverted.
- git diff --check clean; diff empty on forbidden and protected paths; real cache dir (216 lines of size, mtime, sha256) identical before and after.
- Spend: about 0 USD external; no live calls.

## 7 Tests NOT run
Any live X or Reddit call; refresh_attention.py live.

## 8 Deviations
Baseline run overlapped my test edits (collection finished first). Pinned-runner tests added to test_refresh_attention.py as the planner asked. Tracked-file scan regex requires a `%XX` in the AAAA token form because a prototype html holds base64 runs of A.

## 9 Blockers
None.

## 10 Follow-up
Owner sets X_USD_PER_READ and caps in the private env; slice G probes should add probe records for reddit and xsearch; S-C applies SOURCE_WEIGHTS.

## 11 Context cost
Read about 35.5 KB within the 36,000 B cap (one 440 B grep of RUNNERS beyond the file range allotted, within the headroom). Other docs not opened.
