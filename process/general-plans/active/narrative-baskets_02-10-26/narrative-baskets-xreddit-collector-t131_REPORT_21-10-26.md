## 1 Task ID
T131 (amend T126 SPEC, write PLAN, VALIDATE), same branch and PR #153.
## 2 Outcome
done (docs only). SPEC status: ready for owner review (amended T131); the owner has not approved it.
## 3 Summary
SPEC amended: new "Locked pacing rules" section, Q2/Q3/Q4/Q7 answered (Q6 superseded), AC1/AC8/AC10 reworded, AC19 (spend cap) and AC20 (narrative coins) added (20 ACs), Annex C/D/F/H updated, honest ban-risk wording, no evasion techniques. PLAN written (COMPLEX, 8 slices in the owner's order: W8a, W8b, W8c, W8e, W8f, W8g, W8d, W8h) with files, red tests, gates, models, USD, PowerShell probes, branches, dependencies. Validate contract: Gate: PASS. Generic W8 worker does NOT exist on main (checked). No slice touches .github/.
## 4 Files changed
`narrative-baskets-xreddit-collector_SPEC_21-10-26.md` (amended), `narrative-baskets-xreddit-collector_PLAN_21-10-26.md` (new), this report, in `process/general-plans/active/narrative-baskets_02-10-26/`.
## 5 Commits
Branch claude/t126-xreddit-collector-spec, PR #153 (SHAs in the PR).
## 6 Tests run
Baselines on base 007d53c (UV_FROZEN=1 uv run --project api pytest ...): attention suite 231 passed; scripts + data/attention + tooling_guards 492 passed; rest of API 1222 passed, 1 skipped, 5 deselected. Plan validator: failures [] (after fix). Docs gates V2-V10 per the PLAN Validation record. Run 21-10-26 UTC.
## 7 Tests NOT run
No code exists, so no slice gates. Live X, Reddit and API Anything behaviour: owner probes only. Other open PRs touching the shared edit files were not checked.
## 8 Deviations
SPEC was amended after it had been written (the planner asked for it; the owner had not approved it). W8a is report-only; the probe tool moved to W8b (ruling R-1, SPEC Annex H updated to match). Branch base is 007d53c; origin/main moved to 24b1d5e and was not merged.
## 9 Blockers
Owner approval of the SPEC is pending. W8a needs read access to the API Anything repo (outside the session's GitHub scope) or the owner's P-X2 paste. Q1 (dedicated X account) open, needed before W8d. Planner: decide whether T98 W8 worker is built first (shrinks W8e). Registry update request: T131 done; T126 SPEC amended, ready for owner review.
## 10 Follow-up
Owner reads PR #153; then ENTER EXECUTE MODE for W8a; owner runs P-X1, P-X2, P-R1 meanwhile. X capacity note for the owner: at the locked pace X backfill is slow (about 50 days for 14 days x 75 coins); history accrues mainly forward.
## 11 Context cost
Loaded: CLAUDE.md, T126 SPEC and weighted-signal SPEC, T121 PLAN (format and validate contract), vc-generate-plan SKILL and validator, sources.py, main.py lifespan, equities worker cites. About 60k tokens this task. Opened beyond the entry set: vc-generate-plan skill and validator script. Tools: Bash, file tools, GitHub MCP, session tools.
