---
name: plan:data-integration-tooling-btc-hist-owner-guide
description: "Owner-run guide for the first real scrape (T61): BTC-HIST from charts.bitbo.io/halving-progress"
date: 15-10-26
feature: data-integration-tooling
---

# BTC-HIST first scrape: owner guide (T61)

TL;DR: check the site rules first, look at how the page gets its numbers, and only then approve and scrape. If the page has no daily price table, the right answer is STOP.

Run everything yourself in PowerShell, from the repo root. Replace every <PLACEHOLDER>. Do not paste secrets anywhere.

## 0. What this does and does not do

- Fetches ONE page (https://charts.bitbo.io/halving-progress/) when YOU type the command.
- No background or scheduled scraping. No crawling. No other pages.
- It never touches the existing BTC series. New data goes to its own key, BTC-HIST.
- Unknown: nobody has opened this page. It may not hold a daily price table, and may be drawn by JavaScript.

## 1. One-time setup

1. `uv sync --project tools\data-integration`
2. Node.js is needed for step 3 (the REA tool runs through npx).
3. A browser download (`scrapling install`) is a separate opt-in. Do it ONLY if step 3 shows the table is JavaScript-drawn (tier 2). Otherwise skip it.

Command form used below:

`uv run --project tools\data-integration python -m data_integration <command>`

## 2. STOP-first checks (before any approval)

1. In your own browser open https://charts.bitbo.io/robots.txt and the site's terms page.
2. Write down in your own words what they say about automated access to /halving-progress/.
3. If automation is prohibited or unclear: STOP. Tell the planner. Do not continue.

## 3. REA step: how does the page get its numbers?

1. Create a small text file <FINDINGS_FILE> (outside the repo) containing exactly:
   `{"sources": ["<SOURCE_URL>"]}`
   where <SOURCE_URL> is the page URL.
2. Run (live command, needs the confirm flags):

```
uv run --project tools\data-integration python -m data_integration rea inspect-web-page --confirm-source <SOURCE_URL> --findings <FINDINGS_FILE> -- --source <SOURCE_URL>
```

3. Optional second look: the same with `analyze-web-bundle` in place of `inspect-web-page`.
4. Other allow-listed commands (inspect-web-network-capture, export-web-scripts, ...) need a saved capture file; use them only if the planner asks.
5. Evidence is saved to the evidence folder on your PC. For each thing you learn, write one line: `VERIFIED: ...` (you saw it) or `ASSUMED: ...` (you guess).
6. Decision rule: STOP and report if (a) there is no daily price series, or (b) the numbers come from a third-party API call. (This guide deliberately ignores the API route.)
7. The tool only accepts a table with columns date, open, high, low, close, volume. A halving chart may not have these. If not, STOP.

## 4. Create the approval record (stays on this PC, never committed)

Interactive terminal only. You will be asked to type the source name.

```
uv run --project tools\data-integration python -m data_integration approvals add --source btc-hist-bitbo --tier 1 --host charts.bitbo.io --page /halving-progress/ --owner <YOUR_NAME_OR_INITIALS> --rate "<RATE_TEXT_E.G._ONE_REQUEST_PER_RUN>" --robots-checked "<DATE_AND_WHAT_ROBOTS_AND_TERMS_SAID>" --alternative "<OTHER_SOURCES_YOU_CHECKED>" --days 90
```

- Tier 1 first. Use `--tier 2` only if REA showed the table is JavaScript-drawn.
- `--days` defaults to 90 (maximum 366). `--alternative` can be repeated.
- Check with: `uv run --project tools\data-integration python -m data_integration approvals status`

## 5. Recipe: recipes\btc-hist.recipe.json (draft)

Save under tools\data-integration\recipes\ (unknown keys are rejected):

```
{
  "schema_version": 1,
  "source": "btc-hist-bitbo",
  "tier": 1,
  "url": "https://charts.bitbo.io/halving-progress/",
  "selector": "SELECTOR_FROM_PREVIEW",
  "dataset": {"symbol": "BTC-HIST", "timeframe": "1d"},
  "min_rows": 30,
  "politeness": {"min_delay": 2.0, "max_concurrent": 1, "max_per_host": 1}
}
```

- Replace SELECTOR_FROM_PREVIEW with the CSS selector of the table (example: `table.prices`). It can only be set after seeing the page; use your browser's inspect tool, confirm with --preview in step 6, and ask the planner if unsure.
- `tier` must match the approval (1 or 2). `min_rows` is yours to set (2 to 100000).

## 6. Run ladder (in order, stop at the first problem)

Prefix for all: `uv run --project tools\data-integration python -m data_integration run tools\data-integration\recipes\btc-hist.recipe.json`

1. Prefix + `--dry-run`: fetches nothing. Prints request, approval, rate, `permitted: yes/no`, baseline. Needs `permitted: yes`.
2. Prefix + `--preview`: fetches once, stores NOTHING. Prints row count, columns, first and last rows, page hash. Check the numbers look like daily BTC prices.
3. Real run: the prefix alone. A new selector has no baseline and ends with exit 6; if the preview looked right, repeat once with `--accept-baseline`.

| Code | Meaning | What to do |
|---|---|---|
| 0 | OK (or already same) | Report success |
| 2 | Usage or bad recipe | Fix the command or recipe |
| 3 | Approval refused (missing, expired, wrong tier, URL not approved) | Fix the approval (step 4) |
| 4 | Fetch failed (robots block, timeout, error, challenge page) | No retry loops. STOP, report |
| 5 | Page or table failed checks | Nothing stored. Report |
| 6 | Layout changed, or no baseline yet | New selector: see ladder step 3; otherwise report |
| 7 | Refused to protect existing data | Do nothing, report |

## 7. What to send the planner

Paste only: your robots/terms note (one line), the REA VERIFIED/ASSUMED lines, and the outcome lines (`result:`, `rows:`, `approval:`, `rate:`). Not the approval file, not folder paths, no secrets.

## 8. What NOT to do

- Never use `--replace` on the existing BTC series.
- Never share or commit the approval file or the evidence folder.
- Never run this from a scheduled job, a loop, or a script.
- Never widen an approval's host or page without re-checking robots and terms.

## 9. Honest known limits

- Tiers 2 and 3 are not proven on a real site.
- Size caps are checked after the download, not before.
- This page may simply not contain the data. Then the correct result is STOP, not forcing it.
- Windows and Python 3.12 are unverified until you run it.
- What REA expects for `--source` (a URL here) is unverified; if REA refuses, ask the planner.
