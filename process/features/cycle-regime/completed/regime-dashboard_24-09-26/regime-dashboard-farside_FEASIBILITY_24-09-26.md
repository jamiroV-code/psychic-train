---
slug: regime-dashboard-farside
date: 2026-09-24
verdict: VIABLE
originating-phase: pvl
---

# RFC-003 Stage 0 Feasibility Probe — Farside Spot-BTC ETF Flows

## Hypothesis

A plain `httpx` GET from this PC can fetch and parse Farside's spot-BTC ETF daily flows table
(`Total` column, US$m) with history back to 2024-01-11.

## Mechanism Under Test

Whether `https://farside.co.uk/bitcoin-etf-flow-all-data/` is server-rendered HTML reachable by a
plain `httpx.Client` with a browser-like `User-Agent`, or whether it is gated behind a
Cloudflare bot-management challenge (JS challenge / CAPTCHA) that a non-browser client cannot pass.

## Probe Family

1 — Local process / Node script (here: local Python script using `httpx` + regex/table parsing,
run directly against the live public page — no test harness, no container, no auth).

## Probe Cost Class

`cheap-local` — public web page, GET only, no billing, no auth, no bot-protection bypass attempted.
Safety gate: none required; ran freely.

## Probe Method

Two live GET requests, ~5 seconds apart, to `https://farside.co.uk/bitcoin-etf-flow-all-data/`,
using `httpx.Client(timeout=30.0, follow_redirects=True)` with a normal desktop Chrome
`User-Agent` and standard `Accept`/`Accept-Language` headers. No CAPTCHA-solving, no
Cloudflare-challenge JS execution, no headless browser — a plain HTTP client only. Response body
saved and inspected for: HTTP status, byte size, Cloudflare/challenge string markers
(`checking your browser`, `just a moment`, `cf-error`, `captcha`, etc.), presence of an HTML
`<table>`, row count, first/last date rows, and value-formatting conventions (regex-based `<tr>`/
`<td>` extraction — no `lxml`/`bs4`/`html5lib` available in the `api` uv environment, so
`pandas.read_html` was not usable; a real adapter will need to add one of those as a dependency).
A third request to `/btc/` was not needed — the `-all-data/` page alone answered every open
question from the RFC-001 Stage 0 report's §3 table. Total requests used: 2 of the ~3 allowed.

## Evidence Captured

Request 1:
```
HTTP status: 200
Response size (bytes): 813511
Content-Type: text/html; charset=UTF-8
Server header: cloudflare
Cloudflare/challenge markers found: ['cloudflare', 'challenge-platform']  (generic CF headers/beacon script, NOT a challenge page)
```

Request 2 (~5s later, consistency check):
```
HTTP status: 200
Response size (bytes): 813510
Server header: cloudflare
```

No occurrence of `checking your browser`, `just a moment`, or `cf-error` in either response —
these are the standard Cloudflare interstitial-challenge strings, and they are absent. The
`cloudflare`/`challenge-platform` matches are just Cloudflare's standard response headers and bot
analytics beacon script tag, present on nearly all Cloudflare-fronted sites regardless of whether
a challenge is served.

Table parse (regex-based `<tr>`/`<td>` extraction, since `lxml`/`bs4` are not installed in `api`'s
uv env):

```
<table class="etf">  — single main table present (1 data table + 2 small nav tables elsewhere)
Header row: ['Date', 'IBIT', 'FBTC', 'BITB', 'ARKB', 'BTCO', 'EZBC', 'BRRR', 'HODL', 'BTCW',
             'MSBT', 'GBTC', 'BTC', 'Total']
Data date-rows found: 694
First date row:  ['11 Jan 2024', '111.7', ..., '655.3']   (matches RFC-001's "starts 11 Jan 2024")
Second date row: ['12 Jan 2024', ...]
Last date row:   ['24 Sep 2026', '-', '-', ..., '0.0']    (today — all dashes, market not closed yet)
Second-to-last:  ['23 Sep 2026', '166.3', ..., '346.9']    (yesterday — fully populated)
Summary row: ['Total', '65,022', '11,011', '2,134', '1,381', '144', '319', '329', '1,013', '82',
              '766', '(27,841)', '2,932', '57,290']
```

Formatting observed (694 date rows scanned):
- **Negatives**: parentheses, e.g. `(95.1)`, `(484.1)`, `(27,841)` — 1,813 negative cells found.
  No `-123.4` minus-sign style seen anywhere.
- **Thousands separator**: comma, e.g. `65,022`. Mostly only in the `Total` summary row, but 10
  individual daily cells also cross 1,000 and are comma-formatted (e.g. large IBIT days) — a
  parser must strip commas, not just assume ≤4-digit values.
- **Missing/no-data**: literal `-` (hyphen), used both for "ETF didn't exist yet" (e.g. `MSBT`,
  `GBTC`'s Bitcoin Mini Trust column before launch) and for "today, not yet reported" (the whole
  last row). 905 dash cells found across date rows.
- **Non-date rows**: exactly one summary row, labelled `Total` (no separate `Average` row was
  found on this page, contrary to the generic assumption in the task prompt — the `/btc/` variant
  page was not checked for an `Average` row since it wasn't needed to answer the hypothesis).
- **Zero values**: plain `0.0`, distinguishable from `-` (no fund flow that day vs. fund not yet
  launched).

Row count and date range confirm RFC-001 Stage 0's finding: continuous daily rows from
**11 Jan 2024** through **24 Sep 2026** (today, unpopulated) — 694 rows total, i.e. **usable
history back to 2024-01-11 as stated**, with no gaps in the date sequence over that span (not
individually re-verified date-by-date in this probe, but the row count of 694 matches a
continuous business-day-ish daily series over that ~2.7-year span with no visible truncation in
the HTML).

## Verdict

**VIABLE**

A plain `httpx` GET, with no Cloudflare-challenge handling of any kind, receives the fully
server-rendered HTML table on two consecutive live requests. The table is fetchable and parseable
by a non-browser client, and its history covers 2024-01-11 to present as required.

## Resulting Design Constraint

- **What this licenses:** RFC-003's `etf_flows_adapter.py` may be built as a plain HTTP fetch +
  HTML-table parse (no headless browser, no Cloudflare-challenge solver, no proxy needed) against
  `https://farside.co.uk/bitcoin-etf-flow-all-data/`. The adapter can rely on: a single `<table
  class="etf">` element, a `Date` header row, a `Total` column as the last column, one trailing
  `Total` summary row to skip, negative values in `(123.4)` parenthesis form, `-` for
  not-yet-launched/not-yet-reported cells (must map to the adapter's typed
  `unavailable`/`not_applicable`, never to 0), and commas as thousands separators that must be
  stripped before float parsing (not just on the summary row — some daily cells too). History
  starts 2024-01-11, confirmed live, matching the Stage 0 report and the plan's row 5 coverage
  claim (AC for RFC-002's ETF component).
- **What this forbids:** the adapter must NOT depend on `pandas.read_html`/`lxml`/`bs4`/
  `html5lib` being already available — none of the three common HTML-table parser backends are
  installed in `api`'s current `pyproject.toml`/`uv.lock`. One of them (or a hand-rolled
  regex/stdlib `html.parser` parser) must be added as an explicit new dependency in RFC-003's
  Stage 2 plan — this was previously unstated. The adapter must NOT assume today's row is
  populated (it is `-` until end-of-day) and must NOT assume the `Total` column stays a plain
  number without commas.
- **What remains uncertain (known-gap):** this probe used a normal residential/desktop-class
  browser User-Agent from a real home/office IP; it does not prove Farside will behave the same
  from a CI runner, cloud IP range, or scheduled-task context with a different network identity —
  Cloudflare bot management can and does differentiate by IP/ASN reputation, not just UA string.
  The daily-snapshot cron job (proposed 03:00 local, same machine as this probe per the plan) is
  low-risk since it runs from the same IP/browser fingerprint context as this probe, but that
  should be noted, not assumed permanent — if Farside's Cloudflare configuration tightens later,
  a future request could still fail even though this probe passed today. Not independently
  re-verified: whether every one of the 694 rows has a contiguous, gap-free date sequence
  (only row count and first/last dates were checked, not a full calendar diff).

## Probe Cost Class Confirmation

Actual cost class used: `cheap-local`. No container, no live-provider opt-in, no browser
automation, and no Cloudflare-worker sandbox were needed — 2 of the allotted ~3 plain HTTP GETs
resolved the hypothesis fully.

VC-FEASIBILITY-VERDICT-READY: VIABLE — process/features/cycle-regime/completed/regime-dashboard_24-09-26/regime-dashboard-farside_FEASIBILITY_24-09-26.md

**Status:** DONE
**Summary:** Farside's ETF-flows table is plain server-rendered HTML reachable by a bare `httpx` client (two live 200s, full 694-row table with a Cloudflare header but no challenge page) — RFC-003's plain-HTTP-adapter approach is VIABLE. One new fact for the plan: no HTML-table parser (`lxml`/`bs4`/`html5lib`) is currently installed in `api`, so RFC-003 needs to add one.
**Concerns/Blockers:** None blocking. Known-gap: behavior from a different network context (CI/cloud IP) than this probe's is unverified — treat as an operational risk to watch, not a design blocker, since the daily snapshot will run from the same machine/IP as this probe.
