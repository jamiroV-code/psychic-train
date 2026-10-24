## 1 Task ID
T163 addenda 1 and 2 (24/7 server host as the target; quality over speed), same branch claude/t163-reddit-engagement-spec and the same draft PR #167.
## 2 Outcome
done (docs only).
## 3 Summary
Addendum 1 (owner decision 24-10-26, relayed by the planner): the target host is a spare laptop running 24/7. SPEC rule 15 sets a BASELINE schedule (X units spread over the UTC day with 3-6 min as the MINIMUM spacing; Reddit per-coin search.rss spread over the day with t=week; subreddit comments.rss every 2 h; posts new.rss every 6 h; archive enrichment once a day; Reddit budget 250) and rule 10 keeps the old 1-3 h small-window behaviour only as DEGRADED MODE (outages, interim). The X read budget (800 posts, N 40, N_min 20, page cap 3, adaptive halving/doubling) stays the binding limit (about 20 coins/day, rotation about 4 days); P-X6 and P-X8 measure the real cap; raising it is a config change after clean weeks. Q11 superseded; AC24 and AC30 reworded; AC37-AC40 added (40 ACs); Annex J (server host requirements with owner-run PowerShell examples); Q19 (Trends on the server, recommended server primary, GitHub fallback) and Q20 added; new PLAN slice W8e2 (host guide and health line); W8e written for unattended weeks. Addendum 2: SPEC rule 16 Quality over speed (nothing dropped, shrunk, shortened or cut to fit a time budget; completeness per source-day in the evidence sidecar and on the Sources text; AC38; PLAN hard stop); T164 referenced, not duplicated. PLAN re-validated: Gate: PASS. USD: W8b 6-8, W8e 4-6, W8e2 3-4, total 34-46.
## 4 Files changed
SPEC (amended), PLAN (amended, validation record appended), this report, in `process/general-plans/active/narrative-baskets_02-10-26/`.
## 5 Commits
Branch claude/t163-reddit-engagement-spec, PR #167 (SHA in the PR).
## 6 Tests run
No code. Docs gates 24-10-26 UTC: plan validator failures []; only the collector docs changed; no .github/; secret scan clean; git diff --check exit 0; 40 ACs, AC1..AC40 mapped; banned names only in ban sentences.
## 7 Tests NOT run
All code gates (no code). Not proven: that the spare laptop exists; that the Task Scheduler and powercfg examples behave as written (not run); that Reddit honours t=week on search.rss; that a 24/7 pace stays inside X's unofficial caps.
## 8 Deviations
Readings and choices of mine, for the planner and owner to overrule (Q20): (1) "X trickle spread over the whole UTC day at the configured 3-6 min spacing" cannot hold literally under a 20-unit daily budget (20 units at 3-6 min end after about 90 minutes), so 3-6 min is the MINIMUM spacing and the worker spreads the units evenly (about one per 72 min); a flag x_spread_over_day=false gives the 90-minute cluster; (2) the Reddit daily request budget default is raised to 250 on a 24/7 host (about 171 planned requests plus margin) with 150 kept as the degraded value, so every earlier mention of 150 means degraded mode; (3) per-coin search uses t=week by default, because t=day reaches only 24 h back from the request and misses part of yesterday for requests made late in the day (this changes the T163 text, which said t=day); (4) X changes were not requested and none were made except the schedule wording. The addenda are owner decisions relayed by the planner; the SPEC status line says they are not yet approved in this session.
## 9 Blockers
Owner: Q19 (Trends on the server), Q20 (spread reading, Reddit budget 250, t=week); Q17 and Q18 from the first T163 report still open; P-R7 and P-R8 probes still to be run; the laptop must exist before the baseline can be proven live. Registry request: T163 addenda done.
## 10 Follow-up
Planner may dispatch W8b and W8c now; W8e2 after W8f; T164 audit is separate.
## 11 Context cost
Re-read the sections being amended; about 70k tokens for both addenda. A shell hook once blocked a heredoc containing one word, so scripts and this report were written with the file tool; no hook setting was changed.
