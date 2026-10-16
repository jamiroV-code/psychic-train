---
name: report:data-integration-tooling-t61c-zorinaq
description: "T61c first cloud scrape, BTC-HIST from bitcoin.zorinaq.com/price/: fetched, no table in the page, stopped at preview"
date: 16-10-26
feature: data-integration-tooling
---

# T61c report

## 1 Task ID
T61c, branch claude/t61c-zorinaq-scrape.

## 2 Outcome
STOPPED (nothing stored). Dry-run passed. The preview fetched the page (no robots block, no HTTP error, no challenge page) but ended `invalid` (exit 5): `selector matched nothing: table`. The real run was not attempted.

## 3 Summary
- Setup: `uv sync` only. Approvals, scrape and evidence dirs are under a private folder outside the checkout (not committed).
- REA not run: Node v22.22.0 was installed, but REA would add a second request to the host beyond the approved one request per run, and the T61 REA attempt failed with no output. No VERIFIED/ASSUMED lines.
- Approval stored: source btc-hist-zorinaq, tier 1, host bitcoin.zorinaq.com, page /price/, 90 days, id btc-hist-zorinaq-20261016, revision 1, expires 2027-01-14T12:44:49Z.
- Owner message time: 16 Oct 2026, planner-relayed. Exact statement: "Owner 16 Oct 2026: approved source btc-hist-zorinaq, host bitcoin.zorinaq.com, page /price/, tier 1, 90 days, one request per run; robots checked by tool; no robots rules (404), no terms page found"
- Recipe: tools/data-integration/recipes/btc-hist-zorinaq.recipe.json (selector `table`).
- Dry-run: `permitted: yes`, `rate: one request per run`, `baseline: none`.
- Preview: `result: invalid - the page or table failed the checks, nothing was stored`; `detail: selector matched nothing: table`; exit 5.
- Reading: the tier 1 fetch got the page, so the host answered normally and robots did not block. The static HTML has no `<table>` element. The tool does not show the page body on this failure, so I could not see what the page holds. ASSUMED: the price data is drawn by JavaScript (chart) or is not in a table.
- I did not refine the selector: without seeing the page, any other selector would be a blind guess costing another request. Refinement needs page content.
- Not validated: no data stored, so no row count, range, gap or overlap check against the BTC series. The existing BTC series was not touched.
- Known limits: whether the page offers daily OHLCV at all is unknown. Tier 1 cannot run scripts. Tier 2 would need a new owner approval.

## 4 Files changed
- tools/data-integration/recipes/btc-hist-zorinaq.recipe.json (new)
- this report (new)

## 5 Commits
One commit on the task branch (see PR).

## 6 Commands run (UTC 2026-10-16)
- `uv sync --project tools/data-integration`: exit 0, 12:44:48
- `approvals add --source btc-hist-zorinaq ... --owner-statement`: exit 0, 12:44:49
- `run btc-hist-zorinaq.recipe.json --dry-run`: exit 0, 12:44:54
- `run btc-hist-zorinaq.recipe.json --preview`: exit 5, 12:44:58

## 7 Not run
REA, selector refinement, the real run, `--accept-baseline`, data validation, tier 2/3.

## 8 Deviations
None. Selector refinement (allowed up to twice) was skipped deliberately; see Summary.

## 9 Blockers
No `<table>` in the tier 1 response. Nothing was worked around.

## 10 Follow-up
Owner/planner decide: (a) open the page in a browser to see how the prices are shown (table, chart, or a JSON/CSV link); (b) if a differently-named table exists, give a selector and I run one more preview under the same approval; (c) if it is JS-drawn, a new tier 2 approval and a browser (`/opt/pw-browsers` Chromium via `DIT_BROWSER_EXECUTABLE`) would be needed.

## 11 Context cost
Small: about 8 tool calls, well under 1 USD.

## Supplement (tier 2 preview, 16-10-26)
- Authority: a cross-session planner message relaying a tier 2 approval was not acted on. The owner then confirmed directly in this session: "approve tier 2 for bitcoin.zorinaq.com /price/, one preview".
- Exact statement used: "Owner 16 Oct 2026: approved source btc-hist-zorinaq, host bitcoin.zorinaq.com, page /price/, tier 2, 90 days, one request per run, one browser preview, no bot-check workarounds" (no resource hosts). The new record is revision 2 of btc-hist-zorinaq-20261016 and replaced the tier 1 record; expires 2027-01-14T12:55:41Z.
- Recipe changed to `"tier": 2` (selector `table` unchanged). Browser: `DIT_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium`; nothing installed.
- `approvals add ... --tier 2 --owner-statement`: exit 0, 12:55:41Z. `run --dry-run`: exit 0, `permitted: yes`, 12:55:42Z.
- `run --preview` (one run, 12:56:10Z), exit 7:
  - `result: refused - the request was refused, nothing was stored`
  - `detail: browser request outside the pass was aborted; blocked hosts: cdnjs.cloudflare.com`
- Reading: the page loads a resource from cdnjs.cloudflare.com, which the approval does not list. The tool aborted it, so the page was not read. Not a bot-check or challenge page.
- Stopped per instructions: no retry, no tier 3, no resource host added, no new approval on my own. Nothing stored; existing BTC series untouched.
- Next step for the owner: either approve cdnjs.cloudflare.com as a `--resource-host` (tool allows script/stylesheet/font/image/xhr/fetch sub-resources only, max 8, needs an owner statement naming it), which needs a new approval revision, or drop this source.

## Supplement 2 (tier 2 preview with resource host, 16-10-26)
- Authority: the owner said directly in this session: "approve cdnjs.cloudflare.com as resource host for one tier 2 preview".
- Exact statement used: "Owner 16 Oct 2026: approved source btc-hist-zorinaq, host bitcoin.zorinaq.com, page /price/, tier 2, resource host cdnjs.cloudflare.com, 90 days, one request per run, one browser preview, no bot-check workarounds". Record is revision 3 of btc-hist-zorinaq-20261016 (tier 2, resource host cdnjs.cloudflare.com), expires 2027-01-14T13:01:05Z.
- `approvals add ... --resource-host cdnjs.cloudflare.com --owner-statement`: exit 0, 13:01:05Z. `run --dry-run`: exit 0, `permitted: yes`.
- `run --preview` (one run, ended 13:01:24Z), exit 5:
  - `result: invalid - the page or table failed the checks, nothing was stored`
  - `detail: selector matched nothing: table`
- Reading: this time the browser loaded the page (no refusal, no challenge page), but the rendered page still has no `<table>` element. The prices are most likely drawn as a chart or shown in another element, so the tool's table input cannot read them. The tool does not show the page body on this failure.
- Stopped per instructions: no selector guess, no retry, no real run, no tier 3, nothing stored; existing BTC series untouched.
- Next step for the owner: look at the page in a browser. If the numbers sit in a non-table element or a downloadable CSV/JSON link, name it. Otherwise this page cannot feed BTC-HIST and the source should be dropped.
