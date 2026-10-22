## 1 Task ID
T133 (amend SPEC and PLAN after the T132 research), same branch and PR #153.
## 2 Outcome
done (docs only). SPEC status: ready for owner review (amended T131, T133); still not owner-approved.
## 3 Summary
SPEC: pace is now config (x_query_delay_min_s/max_s, default 180-360 s); daily read budget x_daily_post_budget 800 counted in posts loaded; sample N 40, N_min 20, page cap 3 (formula unchanged, noise about 16%); capacity about 20 coins/day, 75 narrative coins rotate about every 4 days; adaptive budget (halve after a warning day, double after 7 clean days); throwaway X account only; option D (official counts route, unbuilt fallback, one-call owner test) in Annex E; plain ban-risk wording; no evasion techniques. AC8 reworded, AC21 (budget) and AC22 (adaptive) added, Q10 (rotation rule for Discovery, flagged not implemented), Q11 (PC hours), Q12 (Reddit reading) added. PLAN: W8b (config, budget, adaptive; USD 5-7), W8d and W8e tests/acceptance, probes P-X8 and P-W2, hard stop updated, total 22-33 USD. Re-validated: Gate: PASS.
## 4 Files changed
SPEC (amended), PLAN (amended, T133 validation record appended), this report, all in `process/general-plans/active/narrative-baskets_02-10-26/`.
## 5 Commits
Branch claude/t126-xreddit-collector-spec, PR #153 (SHA in the PR).
## 6 Tests run
No code exists. Docs gates re-run 21-10-26 UTC: plan validator failures []; no files outside the three docs; no .github/; secret scan clean; git diff --check exit 0; 22 ACs, all mapped; banned-name hits only in ban sentences. Baselines from T131 unchanged (code untouched).
## 7 Tests NOT run
All code gates (no code). Live X, Reddit, API Anything and the 1,000 posts/day figure (third-party, unofficial): owner probes only.
## 8 Deviations
SPEC now has 22 ACs, above the vc-generate-spec maximum of 20, on the planner's instruction (stable numbering, AC21/AC22). Reddit "stays gentler than X per request" was read as unchanged 20-60 s / 300 per day; per coin Reddit (about 3 requests, 2 min) is not slower than X (3-6 min), so I flagged it as Q12 instead of changing numbers. Collector config lives in the new `attention_queries.json` (W8b), not `discovery.json`, to avoid an extra shared edit.
## 9 Blockers
Owner: SPEC approval; Q10 (rotation rule or fixed ~20-coin set), Q11 (PC hours), Q12; Q1 remainder (who creates the throwaway account). W8a still needs read access to the API Anything repo or the owner's P-X2 paste. Registry request: T133 done; T126 SPEC amended again, awaiting owner approval.
## 10 Follow-up
Owner runs P-W2 (PC hours) and optionally P-X8 (official counts one-call test). Planner decides whether the T98 W8 worker is built first.
## 11 Context cost
Re-read SPEC and PLAN sections being amended; no new protocol docs. About 45k tokens this task.
