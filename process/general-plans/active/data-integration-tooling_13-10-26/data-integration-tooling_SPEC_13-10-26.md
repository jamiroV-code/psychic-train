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

**TL;DR:** We add a repeatable, developer-run workflow for bringing in a new dataset: (1) investigate the source with REA, (2) look for a free API or public dataset, (3) only if none exists, scrape with Scrapling under a written approval, (4) validate, normalise, cache and store the result with provenance. Nothing scrapes by itself. Heavy pieces stay out of the API install and CI. No new page. **Status: draft.** L1 gating and L3 need owner confirmation; 6 questions need an owner answer.

Locked = owner decided 13-10-26. Flagged = planner proposal awaiting owner confirmation. VERIFIED = re-checked in repo; FROM-RESEARCH = research reports 13-10-26.

Companion SPEC: `market-framework_13-10-26`. Its missing data (Global M2, TOTAL market cap, long BTC history) are candidate first uses; building them is out of scope.

---

## Locked decisions

| ID | Decision | Status |
|---|---|---|
| L1 | Scrapling scope = all three tiers: (1) HTTP fetch, parser, crawler with polite defaults; (2) headless-browser rendering; (3) anti-bot features (Cloudflare solving, fingerprint masking). Owner answer 13-10-26. **Flagged gating:** tiers 2-3 run only for a source the owner approved by name in a per-source approval record (terms/robots check, alternatives considered); tier 3 also needs an explicit owner go per source. Farside's "no bypass, ever" stays unless the owner records a change. | Scope Locked; gating Flagged |
| L2 | Scraping starts only from an explicit developer command: no scheduler, background worker, Actions job, API-handler import or startup call. Scheduled refresh is a separate owner decision. Owner answer 13-10-26. | Locked |
| L3 | REA is a developer-run, version-pinned CLI step with a VERIFIED/ASSUMED protocol; not an API runtime dependency; no `rea-agents setup` or MCP registration without owner review of the diff. | Flagged |
| L4 | Companion SPEC `market-framework_13-10-26` is separate; this SPEC only supplies tooling. | Locked |

---

## Summary

A repeatable developer workflow so new data sections cost less and depend less on paid providers.

## User Stories / Jobs To Be Done

As a developer/data integrator I want to:
- **US-1** investigate a source with REA and record VERIFIED vs ASSUMED findings, so I know how its numbers are derived;
- **US-2** check free APIs, official endpoints and public datasets first and record the outcome, so scraping is never the default;
- **US-3** request approval to scrape a named source and have it recorded, so there is a durable why/what/how-politely record;
- **US-4** run a scrape explicitly and get validated, normalised, cached data with provenance;
- **US-5** re-run safely (cached, rate-limited, idempotent);
- **US-6** be told clearly when a page's structure changed, so wrong data is never stored silently;
- **US-7** repeat this workflow for any future dataset;
- **US-8** keep the API runtime and CI light.

## What The User Wants (Behavioral Outcomes)

A written workflow with one evidence artefact per step; scrapes refuse to start without a valid approval (tier 3 also needs the owner-go field); every stored scrape is traceable; a changed page yields an explicit "changed" or "uncertain" result, never a guess; re-runs use the cache; no frontend, no background activity.

## Workflow Definition (requirements; planner's assessment of the safest practical workflow, for owner confirmation)

| Step | Must produce (evidence artefact) |
|---|---|
| 1 Investigate with REA | Findings note: what the page loads, which endpoints it calls, what is computed client-side vs server-side, each line tagged VERIFIED or ASSUMED. States what REA cannot see (server-side methodology). |
| 2 Evaluate alternatives | Alternatives note: free APIs, official endpoints, public datasets/exports checked, outcome for each, redistribution and licence notes. Reuse of existing datasets considered first. |
| 3 Scrape approval (only if 2 finds nothing suitable) | Approval record with fields: source; why no API; alternatives checked; robots/terms check with date; allowed pages; rate policy; tier allowed (1/2/3); owner go (required for tier 3); expiry. |
| 4 Integrate | Validated, normalised data in the existing cache format with provenance, timestamps, error handling, rate limits; tests on local fixtures. |

Step 3 is skipped when step 2 finds a suitable API or dataset.

## Flow

```
new dataset -> [1 REA findings] -> [2 alternatives] --suitable--> normal adapter (no scraping)
                                        | none suitable
                                        v
                      [3 approval record] --missing/expired--> REFUSED
                                        | approved (tier 3: owner go)
                                        v
   explicit developer command -> robots check (blocked: REFUSED)
        -> fetch (cache hit: reuse) -> parse -> validate
           (changed/uncertain: explicit result, nothing stored)
        -> normalise -> store with provenance
```

## Scrapling integration requirements

| Capability | Requirement |
|---|---|
| Tiers and gating | Tiers 1-3 built; 2-3 gated per L1; tier recorded in provenance. |
| Parser | Reusable helpers; Scrapling has no table-extraction helper (FROM-RESEARCH), so tables are handled and tested explicitly. |
| Adaptive tracking | Best-match relocation is reported "uncertain", never accepted silently (library has no confidence gate, FROM-RESEARCH). Store lives outside site-packages. |
| Politeness | robots.txt obeyed on all tiers (library default off, FROM-RESEARCH), delays, low concurrency, honest user agent, per-host limits. |
| Caching | Cache by default; refresh only on explicit request; existing freshness rules. |
| Retries and errors | Bounded retries/timeouts; library exceptions mapped to a closed status/reason set; never raises past the module (as VERIFIED in lse_adapter.py). |
| Logging, validation | Structured logs without secrets; schema/type/range/row-count checks before storing. |
| Storage, provenance | Existing parquet + sidecar format (VERIFIED cache.py); provenance as in AC-10, optional raw snapshot. Today only fetched_at exists (FROM-RESEARCH). |
| Tests, platform | Local fixtures only; Windows and Python 3.12 via owner-run probes (only Linux/3.11 smoke-tested, FROM-RESEARCH). |
| Dependency isolation | Default api install and production API gain no heavy dependency (fetchers extra about 332 MB, FROM-RESEARCH). VERIFIED: api needs Python >=3.12, dev group is only pytest, 6 workflows run `uv sync --project api`. |

## REA integration requirements

Pinned version (research saw 6.4.0, FROM-RESEARCH); developer-run; not imported by the API; evidence template with VERIFIED/ASSUMED tags; no config edits or MCP registration without owner diff review. Honest fit: it can capture a page's bundle and network calls (may reveal API endpoints and client-side calculations); it cannot see server-side calculations or methodology and does not search public datasets; fit for web dashboards is unverified. Needs Node 22.19+ and a Chrome-family browser for capture (FROM-RESEARCH).

## Documentation and process requirements

Extend `process/context/data-sources/all-data-sources.md` (VERIFIED exists) and existing skills, no duplicate doc system; register the capability in `process/context/all-context.md`; add standing rules: approval record before scraping, and no scraped data in git-tracked directories without a recorded redistribution check (public repo, FROM-RESEARCH). VERIFIED: no existing Scrapling or REA reference in the repo.

## Acceptance Criteria (Testable Outcomes)

FA = Fully-Automated, HY = Hybrid, AP = Agent-Probe. Scenarios use existing pytest (`api/tests/data`).

- **AC-1** A scrape with no matching, unexpired approval record is refused with a reason and makes no network call. proven by: pytest, fake approval store, call-counting transport. FA
- **AC-2** No scheduler, workflow, API handler or startup code can invoke scraping. proven by: guard test scanning workflows and API entry modules. FA
- **AC-3** Tier 3 is refused without the explicit owner-go field; any tier above the record's allowed tier is refused. proven by: pytest, approval fixtures. FA
- **AC-4** Default `uv sync --project api` resolves with no Scrapling, browser or REA package; no CI install step gains them. proven by: lockfile check plus workflow grep gate. FA
- **AC-5** The tooling installs on demand in a clean environment without altering the API environment. proven by: scripted install check. HY
- **AC-6** A page disallowed by a fixture robots file is refused on every tier. proven by: pytest, local fixture server (browser tier HY). FA
- **AC-7** Configured delay, concurrency and per-host limits hold under a burst. proven by: pytest, fake clock. FA
- **AC-8** When a fixture page changes shape the result is an explicit "changed" or "uncertain" status with a reason, and nothing is stored. proven by: pytest, before/after fixtures. FA
- **AC-9** Missing columns, wrong types, out-of-range values or too few rows give an explicit failure and no stored file. proven by: pytest, malformed fixtures. FA
- **AC-10** Every stored scrape carries source URL, fetch time, response hash, library version, parser version and approval id. proven by: pytest reading the sidecar. FA
- **AC-11** Output reads through the existing cache/freshness code unchanged. proven by: pytest round trip. FA
- **AC-12** A second run makes no request and leaves identical data; a forced refresh makes only the allowed requests. proven by: pytest, call counter, hash compare. FA
- **AC-13** Timeouts, refused connections, challenge pages and HTTP errors map to the closed status set; no exception escapes. proven by: pytest, failing fixture server. FA
- **AC-14** Each request logs one structured line with outcome; no secret, key or IP appears. proven by: pytest on captured logs. FA
- **AC-15** CI makes no live network call; live tests sit behind the `integration` marker. proven by: marker audit, network-blocked CI run. FA
- **AC-16** Tier-1 fetch, parse and store passes on the owner's Windows PC under Python 3.12. proven by: owner-run probe (vc-feasibility-test). AP (cannot run in Linux CI)
- **AC-17** Tier 2 renders a local fixture page on the owner's PC. proven by: owner-run probe. AP (needs owner's browser)
- **AC-18** Workflow, evidence artefacts and approval fields are documented once in the data-sources doc and reachable from the context router. proven by: router validator, grep gate. FA
- **AC-19** A pinned REA version, evidence template (VERIFIED/ASSUMED) and "what REA cannot establish" statement exist; the API does not import REA; no agent config changed. proven by: grep gate, diff check. FA
- **AC-20** One owner-chosen dataset completes all four steps with findings note, alternatives note, approval record (if scraping) and stored data with provenance; an API found in step 2 still counts. proven by: owner review. HY

## Out Of Scope

Frontend pages; autonomous, scheduled or startup scraping; building Global M2, TOTAL or long-BTC datasets; changing existing adapters (incl. Farside's no-bypass rule); MCP registration or agent-config edits; paid providers or proxies.

## Constraints

Personal-use tool; no rewrites without evidence; reuse existing architecture; no duplicate doc systems; synthetic fixtures only, no live CI calls; no secrets, keys or IPs; no scraped third-party data in git-tracked directories without a recorded redistribution check; anti-bot legal responsibility is the owner's.

## Risks and unknowns

Single-maintainer pre-1.0 Scrapling (pin); browser size and Windows antivirus/SmartScreen (unmeasured); Python 3.12/Windows untested (AC-16); optional extras may conflict with pinned api packages (untested); wrong adaptive match; public-repo redistribution; REA fit for web dashboards unverified.

## Open Questions

| # | Question | Proposed default | Tag |
|---|---|---|---|
| OQ-1 | Where do approval records live? | One small file per source in the data-sources area, reviewed in git, no secrets. | NEEDS-OWNER |
| OQ-2 | First real dataset: Global M2, TOTAL market cap or long BTC? | Owner picks; recommend the source needing least anti-bot. | NEEDS-OWNER |
| OQ-3 | Confirm L1 gating and L3 (REA pinned, developer-run). | Accept as written. | NEEDS-OWNER |
| OQ-4 | How are browser tiers installed on the PC? | Separate opt-in owner-run step, size documented. | NEEDS-OWNER |
| OQ-5 | Pin policy and update cadence? | Exact pins; update only on owner request. | SAFE-DEFAULT |
| OQ-6 | Shared rate limiter in scope? | No; per-host limits inside the new tooling only. | SAFE-DEFAULT |
| OQ-7 | Shared adapter contract test (backlog note adapter-shared-contract-test_NOTE_03-10-26) in scope? | No; new tooling gets its own tests. | SAFE-DEFAULT |
| OQ-8 | Approval expiry length? | 90 days, renewable. | NEEDS-OWNER |
| OQ-9 | Raw snapshots by default? | Off; per approval record; untracked. | SAFE-DEFAULT |
| OQ-10 | Farside adapter stays untouched? | Yes. | NEEDS-OWNER |

## Questions for INNOVATE

1. Package layout and how heavy dependencies stay out of the default API install.
2. How approval is enforced.
3. How REA is invoked and its output captured.
4. Where the adaptive-tracking store lives.
5. Provenance storage format (extend sidecar or separate record).
6. How browser tiers are tested locally without live sites.

## Background / Research Findings

- REA (npm `rea-agents`, MIT): setup edits agent config; scratch run output unread. FROM-RESEARCH.
- Scrapling 0.4.15 (BSD-3): Linux/3.11 smoke test passed; Windows, 3.12, browser tiers, spider, CLI, MCP untested; no validation or provenance. FROM-RESEARCH.
