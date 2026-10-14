---
name: spec:data-integration-tooling
description: "Developer-run REA + Scrapling tooling for integrating new datasets, with approval, validation, caching and provenance. No frontend."
date: 13-10-26
feature: general-plans
metadata:
  node_type: memory
  type: spec
---

[MODE: SPEC]

# Data Integration Tooling (REA + Scrapling) - SPEC

**TL;DR:** A developer-run workflow for new datasets: (1) investigate with REA, (2) look for a free API or public dataset, (3) only if none exists, scrape with Scrapling under a per-source approval record, (4) validate, cache and store with provenance. Nothing scrapes by itself. Heavy pieces stay out of the API install and CI. Approval records stay on the owner's PC. No new page. **Status: draft, updated 14-10-26.** 2 questions need an owner answer.

Locked = owner decided. Flagged = awaiting confirmation. FROM-RESEARCH = research 13-10-26.

Companion SPEC `market-framework_13-10-26` is PAUSED by the owner (14-10-26) until the owner decides which input fits which timeframe. Long BTC history is the first real use because the framework will need it later.

---

## Locked decisions

| ID | Decision | Status |
|---|---|---|
| L1 | Scrapling scope = all three tiers: (1) HTTP fetch/parser/crawler; (2) headless browser; (3) anti-bot. Gating (owner answer 14-10-26): a per-source approval record naming the site and listing the allowed tier is enough; the extra per-use owner go for tier 3 is REMOVED. The record stays mandatory per source (robots/terms check, allowed pages, rate policy, allowed tier, owner approval date, expiry). Browser tiers install as a separate opt-in step on the owner's PC. | Locked |
| L2 | Scraping starts only from an explicit developer command: no scheduler, worker, Actions job, API-handler import or startup call in the NEW tooling (owner answer 13-10-26). The AC-2 guard covers the new tooling's entry points only (see L6). | Locked |
| L3 | REA stays version-pinned and developer-run, not an API runtime dependency. Wrapper-only (DIT-6): an allow-listed wrapper runs web/static commands only; `npx rea-agents setup` is rejected (superseded owner answer of 14-10-26), no MCP, no `.mcp.json`, no agent-config change. | Locked |
| L4 | Companion SPEC `market-framework_13-10-26` is separate and PAUSED (14-10-26); this SPEC only supplies tooling. | Locked (unchanged, pause noted) |
| L5 | Approval records are kept ONLY on the owner's PC, never committed (gitignored local store). Owner answer 14-10-26. Consequences: (i) real scrapes run on the owner's PC, started by the owner or guided by the planner, not in the cloud sandbox (it only builds and tests with fixture records); (ii) each stored scrape copies the approval facts (source, tier, approval date, expiry, id) into its provenance; (iii) a guard test fails if a record is tracked or staged; (iv) step 1-2 notes stay in the public repo (source names appear, as for Farside and LiqTide), raw snapshots stay untracked; (v) the owner is told how to back up the store. Expiry default 90 days, renewable. | Locked; expiry default and public notes Flagged (OQ-8, OQ-11) |
| L6 | Farside adapter STAYS UNTOUCHED (owner declined to move it, 14-10-26). Farside refreshes on demand by API request (`api/analytics/regime/components.py:484` via `api/routers/regime.py:57`; once per UTC day, cache-first). The AC-2 guard must NOT cover it: neither broken nor extended. | Locked |
| L7 | First real dataset for the end-to-end run (AC-20) = longer BTC price history (owner answer 14-10-26). A free public dataset or API found in step 2 counts as a pass and needs no scraping. | Locked |

---

## Summary

A repeatable developer workflow so new data costs less and depends less on paid providers.

## User Stories / Jobs To Be Done

As a developer/data integrator I want to: **US-1** record VERIFIED vs ASSUMED findings from REA; **US-2** check free APIs and datasets first, so scraping is never the default; **US-3** keep a durable local per-source approval record; **US-4** run a scrape explicitly and get validated, cached data with provenance; **US-5** re-run safely (cached, rate-limited, idempotent); **US-6** be told when a page changed, so wrong data is never stored silently; **US-7** repeat this for any dataset; **US-8** keep the API runtime and CI light.

## What The User Wants (Behavioral Outcomes)

One evidence artefact per step; scrapes refuse to start without a valid, unexpired local approval whose tier covers the request; stored scrapes explain their own approval; a changed page yields "changed" or "uncertain", never a guess; re-runs use the cache; real scrapes run on the owner's PC; no frontend, no background activity.

## Workflow Definition (requirements)

| Step | Must produce |
|---|---|
| 1 Investigate with REA | Findings note (public repo): page loads, endpoints, client vs server side, each line VERIFIED or ASSUMED; what REA cannot see. |
| 2 Evaluate alternatives | Alternatives note (public repo): free APIs, endpoints, public datasets checked, outcomes, licences. |
| 3 Scrape approval (only if 2 finds nothing suitable) | Local approval record: source name; why no API; alternatives checked; robots/terms check with date; allowed pages; rate policy; allowed tier (1/2/3); owner approval (name, date); expiry. |
| 4 Integrate | Validated data in the existing cache format with provenance (incl. L5 facts); fixture tests. |

Step 3 is skipped when step 2 finds a suitable API or dataset.

## Flow

```
new dataset -> [1 REA findings] -> [2 alternatives] --suitable--> normal adapter (no scraping)
                                        | none suitable
                                        v
          [3 local approval record] --missing/expired/tier too low--> REFUSED
                                        | approved (allowed tier listed)
                                        v
   explicit command on owner's PC -> robots check (blocked: REFUSED)
        -> fetch (cache hit: reuse) -> parse -> validate
           (changed/uncertain: explicit result, nothing stored)
        -> normalise -> store with provenance (incl. approval facts)
```

## Scrapling and REA integration requirements

- **Tiers:** 1-3 built; each source limited to its record's allowed tier; tier recorded in provenance.
- **Parser:** reusable helpers; tables handled and tested explicitly (no Scrapling table helper). Adaptive relocation reported "uncertain"; store outside site-packages.
- **Politeness:** robots.txt obeyed on all tiers, delays, low concurrency, honest user agent, per-host limits.
- **Caching, errors, logs:** cache by default; bounded retries; closed status set, nothing raised past the module (as lse_adapter.py); structured logs without secrets; validation before storing; existing parquet + sidecar format (VERIFIED cache.py).
- **Platform:** local fixtures only; Windows and Python 3.12 via owner-run probes.
- **Dependency isolation:** default api install gains no heavy dependency (fetchers extra ~332 MB).
- **REA:** pinned version (research saw 6.4.0); developer-run; not imported by the API; VERIFIED/ASSUMED evidence template; registration only as L3 says, with a statement of which REA modes are enabled. It cannot see server-side methodology; needs Node 22.19+ and a Chrome-family browser.

## Documentation and process requirements

Extend `process/context/data-sources/all-data-sources.md` and existing skills; register the capability in `process/context/all-context.md`; document local-store backup; standing rules: approval record before scraping, no scraped data in tracked directories without a redistribution check.

## Acceptance Criteria (Testable Outcomes)

FA = Fully-Automated, HY = Hybrid, AP = Agent-Probe. Existing pytest (`api/tests/data`). Raised from 20 to 23 on 14-10-26.

- **AC-1** A scrape with no matching, unexpired local approval record is refused with a reason, no network call. proven by: pytest, fixture store. FA
- **AC-2** No scheduler, workflow, API handler or startup code can invoke the NEW scraping tooling; the guard lives in `api/tests/tooling_guards/`, is a file-only import scan, and covers the new tooling's entry points only; the Farside on-demand path (L6) is documented as outside it. proven by: guard test plus doc grep. FA
- **AC-3** Any tier above the record's allowed tier is refused; tier 3 runs only when the record lists tier 3 (no separate per-use go). proven by: pytest, approval fixtures. FA
- **AC-4** Default `uv sync --project api` resolves with no Scrapling, browser or REA package: exact package names are absent from `api/pyproject.toml` and `api/uv.lock`, and workflows contain no `tools/data-integration`. proven by: lockfile and workflow grep. FA
- **AC-5** The tooling installs on demand in a clean environment without altering the API environment. proven by: Hybrid scripted install check. HY
- **AC-6** A page disallowed by a fixture robots file is refused on every tier, including tiers 2 and 3 (robots check before navigation). proven by: pytest, fixture server. FA
- **AC-7** Configured delay, concurrency and per-host limits hold under a burst. proven by: pytest, fake clock. FA
- **AC-8** A changed fixture page gives an explicit "changed" or "uncertain" status with a reason, and nothing is stored. proven by: pytest fixtures. FA
- **AC-9** Missing columns, wrong types, out-of-range values or too few rows give an explicit failure and no stored file. proven by: pytest fixtures. FA
- **AC-10** Every stored scrape carries source URL, fetch time, response hash, library version, parser version and approval id. proven by: pytest reading the provenance file. FA
- **AC-11** Output reads through the existing cache/freshness code unchanged: round trip through the cache read functions. proven by: pytest round trip. FA
- **AC-12** A second run makes no request and leaves identical data; a forced refresh makes only allowed requests. proven by: pytest, call counter. FA
- **AC-13** Timeouts, refused connections, challenge pages and HTTP errors map to the closed status set; no exception escapes. proven by: pytest fixtures. FA
- **AC-14** Each request logs one structured line with outcome; no secret, key or IP appears. proven by: pytest on captured logs. FA
- **AC-15** CI makes no live network call; live tests sit behind the `integration`, `browser` and `antibot` markers; CI runs only the API job. proven by: static marker audit. FA
- **AC-16** Tier-1 fetch, parse and store passes on the owner's Windows PC under Python 3.12. proven by: owner-run script. AP
- **AC-17** Tier 2 renders a local fixture page on the owner's PC. proven by: owner-run script after the opt-in browser install. AP
- **AC-18** Workflow, evidence artefacts, approval fields and local-store backup guidance are documented once in the data-sources doc, reachable from the context router. proven by: router validator, grep gate. FA
- **AC-19** A pinned REA version, an evidence template (VERIFIED/ASSUMED) and "what REA cannot establish" statement exist; the API does not import REA; an allow-listed wrapper exists; no agent-config file is changed by this work (worker gate: `git diff origin/main...HEAD` on `.claude/`, `CLAUDE.md`, `AGENTS.md`, `.mcp.json` is empty; NOT a CI check). proven by: grep gate, worker diff check. FA
- **AC-20** The end-to-end dataset is long BTC price history (DIT-9, new cache key `BTC-HIST`, existing BTC series not replaced), completing all four steps (approval record only if scraping) with stored data and provenance; an API or dataset found in step 2 counts. proven by: owner review. HY
- **AC-21** The approval store path and the approvals folder pattern are gitignored; a guard test fails if any record is tracked or staged in git. proven by: pytest on git index. FA
- **AC-22** Provenance copies source name, allowed tier, approval date, expiry and approval id, so a stored scrape is explainable without the local file. proven by: pytest reading the provenance file. FA
- **AC-23** The wrapper rejects `setup`, `update`, `uninstall`, `mcp` and every non-allow-listed command. proven by: pytest on the wrapper. FA

## Out Of Scope

Frontend pages; autonomous or scheduled scraping; building Global M2, TOTAL or the market framework; changing existing adapters, including Farside and its on-demand refresh (L6); committing approval records; real scrapes in the cloud sandbox; paid providers or proxies.

## Constraints

Personal-use tool; reuse existing architecture; synthetic fixtures only, no live CI calls; no secrets, keys or IPs; no scraped data in tracked directories without a redistribution check; anti-bot legal responsibility is the owner's; approval records local-only (L5).

## Risks and unknowns

Single-maintainer pre-1.0 Scrapling (pin); browser size and Windows antivirus unmeasured; Windows/Python 3.12 untested (AC-16); wrong adaptive match; public-repo redistribution; REA fit for dashboards unverified.
- **REA runtime-capture:** REA's runtime-capture modes run targets with the user's permissions. So the SPEC requires the dry-run diff (AC-23) and a statement of which REA modes are enabled. What setup changes is UNKNOWN.
- **Tiers 2 and 3 may stay unproven live:** with long BTC history first, they may never meet a real browser-only or bot-protected site in this update. They ship built and fixture-tested but NOT proven live until a real source needs them; live proof is a later owner-run probe.
- **Local-only records:** a lost disk loses them; backup guidance (AC-18) mitigates.

## Open Questions

| # | Question | Resolution / default | Tag |
|---|---|---|---|
| OQ-1 | Where do approval records live? | CLOSED: local-only (L5). | Closed |
| OQ-2 | First real dataset? | CLOSED: long BTC history (L7). | Closed |
| OQ-3 | Confirm gating and REA? | CLOSED: L1, L3. | Closed |
| OQ-4 | Browser tier install? | CLOSED: separate opt-in step. | Closed |
| OQ-5 | Pin policy and update cadence? | Exact pins; update only on owner request. | SAFE-DEFAULT |
| OQ-6 | Shared rate limiter in scope? | No; per-host limits in the new tooling only. | SAFE-DEFAULT |
| OQ-7 | Shared adapter contract test (backlog note)? | No; own tests. | SAFE-DEFAULT |
| OQ-8 | Approval expiry length? | 90 days, renewable; owner may change. | SAFE-DEFAULT |
| OQ-9 | Raw snapshots by default? | Off; per approval record; untracked. | SAFE-DEFAULT |
| OQ-10 | Farside adapter untouched? | CLOSED: yes (L6). | Closed |
| OQ-11 | Step 1-2 notes (with source names) stay in the public repo? | Yes unless the owner decides otherwise. | SAFE-DEFAULT |
| OQ-12 | Where does the local approval store live and how is it backed up? | CLOSED 14-10-26 (DIT-8): one `<source>.approval.json` per source under `%LOCALAPPDATA%\my_site\approvals\` (env `DIT_APPROVALS_DIR` for tests). | CLOSED |
| OQ-13 | Which REA modes are enabled after the dry run? | CLOSED 14-10-26: no dry run; `setup` rejected; web/static commands only via the wrapper. | CLOSED |

## Questions for INNOVATE

1. Package layout; heavy dependencies out of the default API install. [ANSWERED DIT-1]
2. How approval is enforced. [ANSWERED DIT-2, DIT-8]
3. How REA is invoked and its output captured. [ANSWERED DIT-6]
4. Where the adaptive-tracking store lives. [ANSWERED DIT-4]
5. Provenance format (extend sidecar or separate record). [ANSWERED DIT-3]
6. Testing browser tiers locally without live sites. [ANSWERED DIT-5]
7. Protecting the local approval store from accidental commit and loss. [ANSWERED DIT-8]
8. Capturing and reviewing the dry-run record of `rea-agents setup`. [ANSWERED DIT-6; `rea-agents setup` rejected, no dry run]

## Background / Research Findings

- REA (npm `rea-agents`, MIT): setup edits agent config; output unread. Scrapling 0.4.15 (BSD-3): Linux/3.11 smoke test only. FROM-RESEARCH.
- Owner answers of 14-10-26 are in L1 to L7 and Open Questions.

## Change log 14-10-26

- L1, L3 rewritten; L4 pause note; L5-L7 added.
- Step 3: "owner go" replaced by owner approval (name, date); records local-only.
- AC-2, AC-3, AC-18, AC-19, AC-20 reworded. AC-21, 22, 23 added (20 to 23); AC-1..20 not renumbered.
- OQ-1, 2, 3, 4, 10 closed; OQ-8 now SAFE-DEFAULT; OQ-11, 12, 13 added; INNOVATE questions 7-8 added.
- Risks added (REA capture, unproven live tiers, local-only records); companion mentions note the pause.
- Wording trimmed to fit size; tables merged; no AC dropped.
- Amendment 14-10-26 (T53 S-T0): AC-2, 4, 5, 6, 10, 11, 15, 16, 17, 19, 20, 21, 22, 23 reworded to match DIT-1..9; AC numbering kept; L3 rewritten wrapper-only; OQ-12, OQ-13 closed; INNOVATE questions 1-8 answered; `rea-agents setup` rejected.
