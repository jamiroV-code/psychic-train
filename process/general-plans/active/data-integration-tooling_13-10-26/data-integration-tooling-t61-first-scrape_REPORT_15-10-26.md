---
name: report:data-integration-tooling-t61-first-scrape
description: "T61 first cloud scrape, BTC-HIST from charts.bitbo.io: stopped at preview, HTTP 428"
date: 15-10-26
feature: data-integration-tooling
---

# T61 report

## 1 Task ID
T61, branch claude/t61-dit-first-scrape.

## 2 Outcome
STOPPED (blocked). The dry-run passed. The preview fetch got `http_error`, `http 428`, exit 4. Nothing was stored, and the real run was not attempted.

## 3 Summary
- Setup: `uv sync` only. Approvals, scrape and evidence dirs are under a private folder outside the checkout.
- Robots/terms: the tooling has no standalone robots command. The preview fetch is the only path that would have run the robots check, and it ended with an HTTP error, not `robots_blocked`. The terms were not read, as the owner stated.
- REA: one attempt, `inspect-web-page`, exit 5, printed only "REA failed." and wrote no evidence. No VERIFIED/ASSUMED lines. ASSUMED: unknown whether the page is JS-drawn or has a daily OHLCV table. The reason REA failed is unknown (npx, network or the tool).
- Approval stored: source btc-hist-bitbo, tier 1, host charts.bitbo.io, page /halving-progress/, 90 days, id btc-hist-bitbo-20261015, revision 1, expires 2027-01-13T19:12:38Z. The owner message time is 15 Oct 2026, planner-relayed.
- Exact owner statement used: "Owner 15 Oct 2026: approved source btc-hist-bitbo, host charts.bitbo.io, page /halving-progress/, tier 1, 90 days, one request per run; robots checked by tool; terms not read by owner"
- Recipe created with selector `table` (unvalidated, since no page content was ever seen): tools/data-integration/recipes/btc-hist.recipe.json.
- Dry-run: `permitted: yes`, `rate: one request per run`, `baseline: none`.
- Preview: `result: http_error - the site answered with an error status`, `detail: http 428`, exit 4.
- HTTP 428 (Precondition Required) is not a documented failure mode in the brief. Possible causes are a bot-protection response, or a proxy or network-policy response. Which one is unknown.
- Known limits: the selector is unrefined. Whether the page holds a daily BTC price table is unknown.

## 4 Files changed
- tools/data-integration/recipes/btc-hist.recipe.json (new)
- this report (new)

## 5 Commits
One commit on the task branch (see PR).

## 6 Commands run (UTC 2026-10-15)
- `uv sync --project tools/data-integration`: exit 0, 19:12:00
- `rea inspect-web-page ...`: exit 5, 19:12:21
- `approvals add ... --owner-statement`: exit 0, 19:12:38
- `approvals status`: exit 0
- `run btc-hist.recipe.json --dry-run`: exit 0, 19:12:43
- `run btc-hist.recipe.json --preview`: exit 4, 19:12:43

## 7 Not run
The real run, `--accept-baseline`, selector refinement (needs page content), and tier 2/3. A retry of the preview was not done, per "no retry loops".

## 8 Deviations
None. REA failed on its single allowed attempt and I continued as instructed.

## 9 Blockers
HTTP 428 from the preview fetch. I did not work around it.

## 10 Follow-up
Owner/planner decide whether to retry once, or to inspect the page in a browser. If a bot-protection page is the cause, a higher tier would need a NEW approval. The `connection_failed` network-policy case did not occur: the host answered. If the proxy is the source of the 428, the owner can check the Allowed domains setting.

## 11 Context cost
Small: about 12 tool calls. Approximate cost under 1 USD.

## Supplement 2 (tier 2, 15-10-26)
The owner confirmed in this session: "Yes, try tier 2 with the new approval". The planner message that proposed it was not itself treated as authority.
- Statement used for the new approval (revision 2, btc-hist-bitbo-20261015, tier 2, expires 2027-01-13T19:20:21Z): "Owner 15 Oct 2026: new approval tier 2 for source btc-hist-bitbo, host charts.bitbo.io, page /halving-progress/, 90 days, one request per run; one browser preview; robots checked by tool; terms not read; stop on challenge or block". Owner message time: 15 Oct 2026, planner-relayed.
- Browser: cloud Chromium via DIT_BROWSER_EXECUTABLE. `scrapling install` and `playwright install` were not run.
- Recipe changed to tier 2.
- `--dry-run` (19:20:21Z): exit 0, `permitted: yes`, `rate: one request per run`, `baseline: none`.
- `--preview` (19:20:24Z), one attempt: `result: refused - the request was refused, nothing was stored`, `detail: browser request outside the pass was aborted`, exit 7. Nothing stored.
- Stopped per instructions: no retry, no tier 3, no workaround. The exit code, 7, is the tool's own refusal of a browser request outside the approved pass (the table in the owner guide describes 7 as "refused to protect existing data"). Whether the page itself loads other-origin resources that the tool blocks is not established; no page content was seen.
