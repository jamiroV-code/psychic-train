---
name: master-plan-board-2
description: "Second board file of the MASTER-PLAN: compact rows T119-T221 and the W8c2-W8g rows of 30-10-26 (Trends, W8 X and Reddit collector, universe U3 and U6, weights v2, docs and process) rebuilt 29-10-26 from gh and git only. Same columns and rules as MASTER-PLAN.md."
date: 29-10-26
metadata:
  node_type: root
  type: master-plan
  read_when: "looking up a task or PR from #148 to #197; before creating a plan artifact or spawning a worker for the attention, Trends or W8 programs"
---

# my_site - Master Plan board 2 (T119-T221)

Continuation of `process/MASTER-PLAN.md` (rules, lanes, older rows). Same writer rule: only the Master Planner session edits this file. Why a second file: the new rows did not fit the 19,000 B cap of MASTER-PLAN.md without dropping IDs.

### Weighted signal, universe, Trends, W8 and docs (T119-T220)

Columns: ID · What · Status · PR / evidence · Cost. Built 29-10-26 from `gh pr list --state all` and `git log faf416b..origin/main` only; What = PR title abbreviated. `review` = merged, not independently reviewed (nothing here has independent evidence read). Cost `unmeasured` = no report states one; spend after 21-10-26 is UNVERIFIED.

| ID | What | Status | PR / evidence | Cost |
|---|---|---|---|---|
| T119 | narratives list reviewed by the owner (data) | review | #148 | unmeasured |
| T123 | U3 excluded-coins line, thin tag, Unassigned and hidden narratives | review | #151 | unmeasured |
| T146 | U6 docs: D-27 exchange tokens IN as a narrative, supersedes D-20 | review | #160 | unmeasured |
| T189 | Discovery not-tradeable exclusion from stored venue lists | review | #177 | unmeasured |
| T130 | weights v2: search vote group, early-source gate, per-day weights versions | review | #156 | unmeasured |
| T150 | frozen-snapshot guard reads the weights a record was scored with | review | #163 | unmeasured |
| T204 | CoinGecko volume fallback counts for coverage only | review | #183 | unmeasured |
| T120 | Trends by coin name SPEC (docs) | review | #149 | unmeasured |
| T121 | T100a Trends tools PLAN and VALIDATE (docs) | review | #150 | unmeasured |
| T100a, T122 | Trends keyword file, loader, checker, probe | review | #152 | unmeasured |
| T128 | Trends CLIs fail cleanly when the session cannot start | review | #155 | unmeasured |
| T134 | 12 checker PASS topics, Trends checker v2 | review | #157 | unmeasured |
| T154 | Trends keywords, 29 topic ids | review | #164 | unmeasured |
| T155 | Trends keyword checker v3 | review | #165 | unmeasured |
| T161 | Trends checker stops when Google refuses, paces long runs | review | #166 | unmeasured |
| T160 | qualified Trends terms for unresolved coins | review | #171 | unmeasured |
| T178 | checker fixes after the #166 review | review | #176 | unmeasured |
| T192 | Trends terms for 8 owner-named tickers | review | #178 | unmeasured |
| T195 | revert OKB and PEARL terms, add PYTH fallback term | review | #180 | unmeasured |
| T144 | Trends batching plan for T100b and T100c (docs) | review | #159 | unmeasured |
| T100b, T149 | Trends one coin per request, replace-series store, per-pull archive | review | #162 | unmeasured |
| T100c | Trends step in the daily workflow | review | #170 | unmeasured |
| T175 | T100b-PIT point-in-time Trends reads for the history chart | review | #172 | unmeasured |
| T180 | every Discovery coin must have a Trends keyword (guard) | review | #174 | unmeasured |
| T194 | Trends and attention data gaps analysis (docs) | review | #179 | unmeasured |
| T197 | per-coin Trends outcomes per run, empty-response retry once | review | #181 | unmeasured |
| T196, T201 | probe_trends term-group tester and campaign mode | review | #182 | unmeasured |
| T203 | Trends time budget 780 s, step limit 18 min | review | #184 | unmeasured |
| T126 | W8 X and Reddit collector SPEC (docs) | review | #153 | unmeasured |
| T141 | W8a API Anything vetting, report only | review | #158 | unmeasured |
| T169 | W8a2 twscrape vetting report (docs) | review | #169 | unmeasured |
| T140 | W8b pure core of the collector | review | #161 | unmeasured |
| T163 | Reddit engagement SPEC and PLAN (docs) | review | #167 | unmeasured |
| T210 | W8c Reddit search.rss connector, ledger, mention metrics | review | #185 | unmeasured |
| T171 | W8d1 X pure core for twscrape | review | #173 | unmeasured |
| T212 | W8d2 X reader, twscrape wrapper, xreader group | review | #186 | unmeasured |
| T164 | quality-over-speed audit and host-profile PLAN (docs) | review | #168 | unmeasured |
| T217 | D-28 nobody pushes to main, PC sync scripts, omp note; T220 commits are inside (ancestor of the #187 merge) | review | #187 | unmeasured |
| T127 | Wikipedia title for INJ (data) | review | #154 | unmeasured |
| T124, T131, T133, T135, T136, T138, T139, T142, T147, T152, T157, T158, T159, T166, T167, T168, T170, T179, T181, T186, T187, T190, T191, T200, T202, T207, T209, T211, T214, T219, T220 | IDs only in inner commit subjects of merged branches (reviews, SPEC and PLAN rounds, fixes); how each landed UNVERIFIED | review | git subject only | unmeasured |
| T221 | docs catch-up PLAN and EXECUTE | review | PLAN merged: #188, #189; EXECUTE merged: #190 (2026-10-30 11:20Z, merge `d390dc9`) | unmeasured |
| W8c2 | Reddit stream-and-count: comments and posts feeds, method `reddit_stream` | review | #191, merge `ff8e4a8`; fix round 3 (false feed end, retention, page cap and continuation, gap report) in open draft PR #198, not merged | unmeasured |
| W8e | PC worker wiring (`attention_pc_refresh`, lifespan start/stop) | review | #192, merge `8f1b502` | unmeasured |
| W8f | Discovery wiring: fetch_side, source_impl, reason codes, X rotation mode | review | #193, merge `0d669f4` | unmeasured |
| W8e2 | server host guide (Windows and Linux) and read-only health line on X/Reddit Sources rows | review | #194 (guide, `ab34e77`), #195 (health line, `aa1f8d6`) | unmeasured |
| W8g | Sources panel health and completeness text for PC worker rows | review | #197, merge `3f45921` | unmeasured |
| - | SPEC rule 18(a) and AC47 use `x_accounts` and `x_pool_max` wording (owner decision) | review | #196, merge `3cd39e2` | unmeasured |
| - | docs catch-up 2: state and registry to `3cd39e2`, W8c2 PLAN/SPEC owner decisions (D1-D3, Q17, E1-E4) recorded | in_progress | this EXECUTE, one draft PR; the owner merges (D-28) | unmeasured |
