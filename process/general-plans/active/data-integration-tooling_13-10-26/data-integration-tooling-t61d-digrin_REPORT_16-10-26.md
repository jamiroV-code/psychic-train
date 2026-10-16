---
name: report:data-integration-tooling-t61d-digrin
description: "T61d cloud scrape BTC-HIST from digrin.com: stopped at preview, robots_blocked (robots.txt answered 301)"
date: 16-10-26
feature: data-integration-tooling
---

# T61d report

## 1 Task ID
T61d, branch claude/t61d-digrin-scrape.

## 2 Outcome
STOPPED at the preview, twice. Attempt 1 (digrin.com): `robots_blocked`, `robots returned 301`, exit 4. Attempt 2 (www.digrin.com, owner-approved retry): fetch OK, but `result: invalid`, `detail: missing columns: open, high, low, close, volume`, exit 5. Nothing stored, no real run.

## 3 Summary
- Setup: `uv sync` only. Approvals, scrape and evidence dirs are under a private folder outside the checkout (not committed). REA skipped as instructed.
- Approval stored: source btc-hist-digrin, tier 1, host digrin.com, page /stocks/detail/BTC-USD/price, 90 days, id btc-hist-digrin-20261016, revision 1, expires 2027-01-14T14:10:36Z. Owner message time: 16 Oct 2026 (planner-relayed "Approve as written").
- Exact owner statement: "Owner 16 Oct 2026: approved source btc-hist-digrin, host digrin.com, page /stocks/detail/BTC-USD/price, tier 1, 90 days, one request per run; robots checked by tool"
- Recipe: tools/data-integration/recipes/btc-hist-digrin.recipe.json, selector `table`, url `https://digrin.com/stocks/detail/BTC-USD/price`. The task text gave `https://www.digrin.com/...` but also said to use the exact host the approval names (digrin.com); the gate matches hosts exactly, so I used the non-www host.
- Dry-run: `permitted: yes`, `rate: one request per run`, `baseline: none`.
- Preview: `result: robots_blocked - the site's robots.txt does not allow this page, nothing was fetched`; `detail: robots returned 301`.
- Interpretation (ASSUMED, not verified): the non-www host redirects to www (a 301), and the tool treats a non-200 robots answer as a block. This is the www vs non-www case the task warned about. Not widened, not retried.
- Known limits: the page content was never seen; whether it has a daily OHLCV table is unknown.

## 4 Files changed
- tools/data-integration/recipes/btc-hist-digrin.recipe.json (new)
- this report (new)

## 5 Commits
One commit on the task branch (see PR).

## 6 Commands run (UTC 2026-10-16)
- `uv sync --project tools/data-integration`: exit 0, 14:10:22
- `approvals add ... --owner-statement`: exit 0, 14:10:36
- `run btc-hist-digrin.recipe.json --dry-run`: exit 0, 14:10:36
- `run btc-hist-digrin.recipe.json --preview`: exit 4, 14:10:43

## 7 Not run
Real run, `--accept-baseline`, selector refinement, tier 2/3, data validation (no data).

## 8 Deviations
Recipe URL uses `digrin.com`, not `www.digrin.com` (see 3).

## 9 Blockers
robots.txt fetch on digrin.com answered 301. Fixing it needs a decision by the owner: a NEW approval and recipe naming host `www.digrin.com` (the exact www host). I did not do that, as it changes the approved host.

## 10 Follow-up
Owner decides whether to approve host www.digrin.com (new card), then re-run dry-run and one preview.

## 11 Context cost
Small: about 8 tool calls, under 1 USD. The t61c zorinaq report named in the brief is not on origin/main, so it was not read.

## Supplement (retry, 16-10-26)
- The owner confirmed in this session: "Yes, retry once with www.digrin.com". New approval record for the same source, host www.digrin.com, page /stocks/detail/BTC-USD/price, tier 1, 90 days (revision 2, expires 2027-01-14T14:12:11Z).
- Exact statement: "Owner 16 Oct 2026: retry approved for source btc-hist-digrin, host www.digrin.com, page /stocks/detail/BTC-USD/price, tier 1, 90 days, one request per run"
- Recipe URL changed to https://www.digrin.com/stocks/detail/BTC-USD/price (selector `table`).
- Dry-run: `permitted: yes`. Preview (14:12:15Z): robots passed and the page was fetched (www host is the right one), but `result: invalid - the page or table failed the checks, nothing was stored`, `detail: missing columns: open, high, low, close, volume`, exit 5.
- Meaning: the first `table` on the page lacks OHLCV columns (the tool needs date, open, high, low, close, volume). The preview printed no outline or column list, so what the page offers is unknown. Not guessed, no resampling. Another selector needs another request, which needs a further owner OK.
- Commands: `approvals add` exit 0 14:12:11; `run --dry-run` exit 0; `run --preview` exit 5 14:12:15.
- Next: the owner can inspect the page in a browser and give a selector for a daily OHLC table (if any), or drop digrin as a source.

## Supplement 2 (third preview, table outline, 16-10-26)
- The owner confirmed in this session: "Yes, one more preview on www.digrin.com". The planner message quoting the same owner choice was not itself treated as authority. Same approval record (btc-hist-digrin, www.digrin.com, tier 1, revision 2), one request. Branch merged with origin/main (includes the table-header outline, PR #95).
- Dry-run: `permitted: yes`. Preview at 2026-10-16T17:11:23Z, exit 5:
  - `result: invalid - the page or table failed the checks, nothing was stored`
  - `detail: missing columns: open, high, low, close, volume`
  - tables matched: 1; columns: 3; rows: 196; headers: Date, Adjusted price, Real price
- Meaning: the page offers one table with a date and two price columns (adjusted and real), no open/high/low/volume. It is not OHLCV. Per the stop rule I did not map columns, resample or retry, and did not run the real run. Recommendation: drop digrin as the BTC-HIST source.
- Nothing stored; no --replace; no approvals, evidence or scraped data committed.
- Commands: `uv sync` exit 0; `approvals status` exit 0; `run --dry-run` exit 0; `run --preview` exit 5.

## Decision (16-10-26)
The owner said in this session: "Drop digrin and mark the PR ready". Digrin is dropped as a BTC-HIST source. The recipe btc-hist-digrin.recipe.json was removed from the PR, so the final change is this report only (heading 4 above lists the recipe as it was before removal). The private approval record (btc-hist-digrin, expires 2027-01-14) stays in the private store, outside the repo; the owner can revoke it by deleting that record.
