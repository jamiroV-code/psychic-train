## 1 Task ID
T138 (Reddit access change on new owner probe evidence), same branch and PR #153.
## 2 Outcome
done (docs only).
## 3 Summary
Owner probes (21-10-26, honest UA attention-probe/0.1): Reddit search.json = 403 with a ~190 KB block page; new.rss = 200 (52 KB); search.rss = 200 (53 KB). SPEC Annex A.2 rewritten: Reddit primary access is the public RSS/Atom feeds over plain HTTP (search.rss per coin over the subreddit set; entries counted per UTC day by updated/published; A.1 density formula applied to the feed window; JSON recorded as blocked); stream-and-count over subreddit new.rss added as an option and recommended complement (Q15). Reddit pace 60-120 s, 150 requests/day. W8c is plain HTTP, no API Anything, no adapter, no login; W8a gates only X (W8d); W8b and W8c can start now. P-R1 recorded, P-R6 (feed depth) added, P-R2..P-R5 adapted to RSS. AC2/AC8/AC9/AC17 reworded, AC25 added (Reddit access rules incl. DOCTYPE rejection). Re-validated: Gate: PASS.
## 4 Files changed
SPEC, PLAN (T138 validation record appended), this report, in `process/general-plans/active/narrative-baskets_02-10-26/`.
## 5 Commits
Branch claude/t126-xreddit-collector-spec, PR #153 (SHA in the PR).
## 6 Tests run
No code. Docs gates 21-10-26 UTC: plan validator failures []; only the xreddit-collector docs changed; no .github/; secret scan clean; git diff --check exit 0; 25 ACs mapped; banned names only in ban sentences.
## 7 Tests NOT run
All code gates (no code). Feed entry count, feed rate limit (about 1 per minute per IP is a third-party report) and depth: owner probes P-R6, P-R3, P-R4.
## 8 Deviations
SPEC was approved (locked) on 21-10-26 for the T136 text; T138 amends it at the planner's instruction and the status line says the owner's approval of the T138 changes is not recorded. 25 ACs (above the usual 20). Also fixed a typo: AC9 said "Annex E", now "Annex D". W8c USD 2-3, total 22-32.
## 9 Blockers
KEY RISK, stated in SPEC A.2: a feed returns only its newest entries, so for a busy coin yesterday is reachable only if the request happens soon after UTC midnight; with the PC on 1-3 h/day at unknown UTC hours, busy coins collected late are missing (never 0). Q16 (PC hours of day) and Q15 (stream-and-count, which also needs overlapping polls) are open for the owner. W8a precondition for X: owner's P-X2 paste or add_repo. Q1 remainder (throwaway X account). Registry request: T138 done.
## 10 Follow-up
Owner runs P-R6, P-R3, P-R4 now (PowerShell, no code needed) and pastes output; planner may dispatch W8b and W8c without waiting for W8a.
## 11 Context cost
Re-read the amended sections; about 40k tokens.
