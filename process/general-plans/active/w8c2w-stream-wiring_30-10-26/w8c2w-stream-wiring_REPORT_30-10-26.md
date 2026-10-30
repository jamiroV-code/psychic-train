# W8c2w report: Reddit stream wiring PLAN (PLAN-REV 4, plan fixes round 3)

## 1 Task ID

T222 (ID free: T221 is the highest in `git log --all` subjects and PR titles; no T222 anywhere; W8c2 PRs have no T id), slice W8c2w. Phase PLAN only (RIPER-5), agent riper-sonnet, direct lane. Branch `claude/w8c2w-stream-wiring-plan` (PR #200, draft). Plan: `w8c2w-stream-wiring_PLAN_30-10-26.md` in this folder. This report covers the original plan, round 1 (owner decisions Q1-Q9), round 2 (second review, share default 0.45) and round 3 (third independent review of PR #200; #198 and #199 now merged).

## 2 Outcome

done (plan revised to PLAN-REV 4 and re-validated; nothing implemented; all owner questions Q1-Q9 decided, none open; one display point flagged in section 8)

## 3 Summary

Round 3 changes (PLAN-REV 4):

- Fix 1 (blocking, Q3): W9 is now "Sources: NO CHANGE". `reddit_stream` is NOT added to `sources.PC_STORES`; `sources.py` and `test_sources_health.py` are removed from the owned files, tests, the G1 regex, the collision text, RFC-7 and the envelope, and added to the not-owned list and to the G2 forbidden regex; a new G8 check fails if either file changes. The four wiring problems (not in `PC_STORES`; `state_path('reddit_stream')` raises `ValueError`; `<store>_health.json`; per-coin completeness format) matter only if the store were added, so none is addressed. All Sources text requirements were removed (W5, W9, W12, section 2, risks, P-S2, W-AC5, W-AC7, Q5). `share_exhausted` and the counts stay in the worker's day record `reddit_stream/_meta/_budget/<day>.json`. Guard tests: `test_sources_route_unchanged_with_stream_enabled`, `test_sources_pc_stores_still_excludes_reddit_stream` (in the stream test file).
- Fix 2 (blocking, new W11b): the cap follows the CURRENT mode, but the mode follows uptime. Rule: the persisted day count is never refunded or rescaled; before every request the wrapper requires `count < cap_of_current_mode`; a request is never started when `count >= current cap`. BASELINE to DEGRADED above the new cap (100 against 67): nothing more that UTC day; DEGRADED to BASELINE: the remaining BASELINE cap. The shared `reddit_web` budget stays the hard limit in both modes. Acceptance sentences (W-AC9, envelope, Public Contracts, one test name) reworded to "never starts a request once the count has reached the current mode's cap; the count is not retroactive". Red-first tests: `test_budget_baseline_to_degraded_same_utc_day_count_not_refunded_stream_sends_nothing_more`, `test_budget_degraded_to_baseline_same_utc_day_remaining_baseline_cap_applies`, `test_stream_never_starts_a_request_when_count_at_or_above_current_mode_cap`, `test_shared_reddit_web_budget_stays_hard_limit_in_both_modes`; the first two and both guard tests are in G4 and checked by identity in G8.
- Fix 3 (G8): new function `idcheck` runs the pytest `-k` selection with `-v` and requires each named test to appear with PASSED (exit 0, no FAILED/ERROR/SKIPPED/XFAIL/XPASS among the selected ids). Used for the four switch tests and, as `g8b`, for the two mode-change tests and the two Sources guard tests.
- Fix 4: collision text rewritten in the present tense: re-run `gh pr list --state open` on 30-10-26 shows ONE open PR, #200 (this plan); #198 and #199 are MERGED. The dated historical note on #198 is kept; G10 unchanged; G0 comment updated. Also verified on `origin/main` (`reddit_stream.py` lines 47-48): `_seen` and `_completeness` are NOT pruned by the library, so the worker prunes them (W6, RFC-6; the old UNVERIFIED wording is gone).
- Fix 5: envelope 5,972 B (`wc -c`, cap 8,000), first line `ROLE: WORKER`, marker `PLAN-REV: 4` (plain text outside the fence) with the envelope check and the handoff text updated.

## 4 Files changed

- `process/general-plans/active/w8c2w-stream-wiring_30-10-26/w8c2w-stream-wiring_PLAN_30-10-26.md` (revised)
- `process/general-plans/active/w8c2w-stream-wiring_30-10-26/w8c2w-stream-wiring_REPORT_30-10-26.md` (this file)

## 5 Commits

One new commit on `claude/w8c2w-stream-wiring-plan` on top of `c1228955`, plain push (no force) to the existing branch, updating PR #200; hash in the worker's final message.

## 6 Tests run

No product tests (plan only). Run, 30-10-26:

- Strict plan validator `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs --strict <plan>`: 0 failures, 0 warnings.
- `bash -n` of the extracted Validate Contract (extraction with `tr -d '\r'`, as the envelope does): OK, 84 lines.
- Envelope measured with `wc -c` on the text between the four-backtick fences: 5,972 B (cap 8,000).
- `gh pr list --state open` (read-only): one open PR, #200.
- Dry run of the Validate Contract in a temporary detached worktree of `origin/main` (`224caf56`, #198 and #199 merged; `REPO` exported from the remote on the command line only), exit 1. PASS (no FAIL line): G0 (the #198 page cap key is on `origin/main`), G2, G3, G9, G10 (no open PR other than #200; #200 touches no owned file). FAIL as expected before EXECUTE: G1 (empty change set), G4 (test file and all required names missing, 0 of 50 tests), G5 (no EXEC-REPORT), G6 (pytest exit 4, test file missing), G7 (no BASEFAIL file; the pytest part itself ran), G8 (switch missing; `g8` and `g8b` pytest exit 4 and each of the 8 named tests missing; share key missing in the JSON, `web_queries.py` and the worker). The new G8 sources-unchanged check passed (no change). Pattern: G0, G2, G3, G9, G10 pass; G1, G4 to G8 fail, as intended.
- Temporary worktrees: `git worktree remove` failed with Invalid argument on Windows; handled with `rm -rf` and `git worktree prune`; `git worktree list` shows only the isolated checkout.

## 7 Tests NOT run

- Every test of the plan's section 4 (they do not exist yet).
- The passing paths of G4 to G8 (need the EXECUTE tree), including the new `idcheck` identity selection.
- All owner probes P-S1 to P-S5 (live behaviour, owner's machine).

## 8 Deviations

1. The review's preferred path for fix 1 of round 2 (derive the count from poll records) stays rejected: #198's code does not record every sent request (round 2 facts).
2. G8 runs pytest (named selections with `-v`); it needs the stream test file.
3. The share counter and the `share_exhausted` record are one small day file under `reddit_stream/_meta/_budget/` written by the worker. DISPLAY POINT for Main and the owner (UNVERIFIED, not claimed by the plan): the round-3 instruction says the record is "shown by `--stream-status`". On `origin/main`, `reddit_stream.stream_status` reads only polls, seen ids and completeness files, and `probe_pc_sources.py` prints that result; both files are outside the owned set and the completeness file is written and frozen by the library. So the plan writes the record in the worker's day file (local, read by hand in P-S3) and says explicitly (W9) that this slice does not make `--stream-status` print it. Making the probe print it needs a one-line probe or library change (a separate owner-approved slice).
4. The shared worktree held copied parent changes at the start of earlier rounds; in this round the isolated checkout had none to stash; `origin` was added there for publication and never written to a file.

## 9 Blockers

None for this plan. EXECUTE is blocked only on: this plan PR merged and Main filling the three envelope values (#198 is already merged).

## 10 Follow-up

- After EXECUTE the owner runs P-S1 to P-S5; P-S3 reports the real stream spend (`used`, `_budget` count, poll pages), which decides whether 0.45 stays.
- Proposed owner-decision line for a later docs task (Q4): "SPEC AC14 waiver: one method per coin series and window is accepted; Discovery takes the first store of `source_impl.reddit` that yields a change for the coin and window; `reddit_impl_order` and `source_impl.reddit` stay two copies guarded by a consistency test." Not part of the EXECUTE slice.
- Not in this slice: any Sources row or text for the stream (Q3), showing the share record in `--stream-status` (section 8, point 3), window-level method choice, engagement enrichment (W8c3).

## 11 Context and cost

Read: the plan and the report, `reddit_stream.py` and `probe_pc_sources.py` on `origin/main` (`stream_status`, prune facts), the open-PR list. The gate dry run took about 170 s. No model spend figure is measured here (UNVERIFIED).
