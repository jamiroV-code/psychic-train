# W8c2w report: Reddit stream wiring PLAN (PLAN-REV 2, plan fixes round 1)

## 1 Task ID

T222 (ID free: T221 is the highest in `git log --all` subjects and PR titles; no T222 anywhere; W8c2 PRs have no T id), slice W8c2w. Phase PLAN only (RIPER-5), agent riper-sonnet, direct lane. Branch `claude/w8c2w-stream-wiring-plan` (PR #200, draft). Plan: `w8c2w-stream-wiring_PLAN_30-10-26.md` in this folder. This report covers the original plan and plan fixes round 1 (after the independent review of PR #200 and the owner decisions of 30-10-26).

## 2 Outcome

done (plan revised to PLAN-REV 2 and re-validated; nothing implemented; all owner questions Q1-Q9 are decided, none open)

## 3 Summary

- Owner decisions recorded as decided, "recommended (d)" removed: Q1 option (b), new key `reddit_stream_budget_share` (float in (0,1], rejects 0, negatives, bool, above 1; default 0.5) capping the stream's requests per UTC day in BOTH modes, searches keep the rest, polls over the share truncated and continued, never dropped; Q2 environment variable `SCREENER_ATTENTION_REDDIT_STREAM=1` (matches `SCREENER_ATTENTION_PC_WORKER` and the other existing names); Q6 EXECUTE only after #198 is merged (G0); Q3, Q5, Q8, Q9 accepted; Q4 accepted with a proposed SPEC waiver line for a later docs task (no SPEC edit planned); Q7 conditional `canary_days`.
- Section 2 rewritten: default 0.5 with arithmetic: cap 125 of 250 (stream bound 124-132: 124 fits, 132 cut by 7), cap 75 of 150 (bound cut by 49-57; searches keep 75 against 76 needed for yesterday, one coin-day short only if the stream spends its whole cap; 0.45 would cover it). Options (a), (c), (d) kept as rejected with reasons; (d) conflicts with SPEC AC30, rule 10, AC24. New W11 (share wrapper around the shared `PcSource`, stream day counter file, no new `PcSource` state).
- Owned files grew by `web_queries.py`, `attention_queries.json`, `test_web_queries.py`; collision proof re-snapshotted with `gh pr list` on 30-10-26: open PRs #198 (touches those three files: real intersection, resolved by G0), #199 (docs, no intersection), #200 (this plan, no intersection). New gate G10 repeats the check at EXECUTE start.
- Tests: 69 named red-first tests (was about 50). Added: shared 429 pause both directions, explicit `_behind` restart no-burst assertion, AC38 stream day record (attempted, fetched, missing with reason counts), rule 16 quality-over-speed, budget-share tests (key validation, cap in both modes, truncated not dropped, searches keep the rest, counter survives restart), switch off = zero stream requests and no store writes.
- Validate Contract rewritten: `set -o pipefail`, work through files (no `grep -q` inside pipelines), pytest exit codes captured (G6 must be 0; G7 must be 0 or 1 with a positive passed or failed count, and exit 1 needs parsed FAILED lines; an empty after-file cannot pass a crash), G5 and G6 reject `0 passed`, G3 also catches `C:\Users`, `C:/Users`, `/home/<name>/` and requires `REPO` to be exported, G4 checks 21 names and at least 50 tests in the new file, G8 checks the new key and default, G10 open-PR collision. `tr -d '\r'` extraction and the FILL_IN stop rule kept.
- `PLAN-REV: 2` is a plain-text line outside the fence; the envelope checks it after extraction from `origin/main` and stops with "plan not merged yet" if absent (pattern of the docs-catchup plan). Envelope: 5,387 B (`wc -c`, cap 8,000), first line exactly `ROLE: WORKER`, no angle-bracket placeholders, decided values included, publication path under `isolation.apply=true`, hard rules, handoff says all questions are decided.
- Strict plan validator: `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs --strict <plan>`: 0 failures, 0 warnings.

## 4 Files changed

- `process/general-plans/active/w8c2w-stream-wiring_30-10-26/w8c2w-stream-wiring_PLAN_30-10-26.md` (revised)
- `process/general-plans/active/w8c2w-stream-wiring_30-10-26/w8c2w-stream-wiring_REPORT_30-10-26.md` (this file)

## 5 Commits

One new commit on `claude/w8c2w-stream-wiring-plan` on top of `5e0077bf`, plain push (no force) to the existing branch, updating PR #200; hash in the worker's final message.

## 6 Tests run

No product tests (plan only). Run, 30-10-26:

- Strict plan validator: 0 failures, 0 warnings.
- `bash -n` of the extracted Validate Contract (extraction with `tr -d '\r'`, as the envelope does): OK, 73 lines.
- Dry run of the contract in temporary worktrees (removed afterwards):
  - `origin/main` (`3cd39e26`), BASE `origin/main`: exit 1. FAIL G0 (#198 not merged), G1 (empty change set), G4 (test file and 21 test names missing, 0 of 50 tests), G5 (no EXEC-REPORT), G6 (pytest exit 4: the new test file does not exist; no passed count), G7 (no BASEFAIL file), G8 (switch, key, `PC_STORES` missing), G10 (#198 touches three owned files). PASS: G2, G3, G9. G7 pytest itself ran and collected on `main`.
  - #198 head (`403bc676`), BASE `origin/main`: FAIL G0, G1 (reddit_stream.py, probe, test, W8c2 report outside the owned set), G2 (forbidden paths), G10.
  - #198 head, BASE the #198 head: G0 PASSES (page cap key present); FAIL G1 (empty change set), G4, G5, G6, G7, G8 (and G8 "cannot read the worker": the #198 branch predates `attention_pc_refresh.py`, which exists on `main`; after the merge it is present), G10.
  - Negative test (temporary commit, discarded): a test file with a Windows path, a forward-slash path, a `/home/` path, an IPv4, and the repo slug, plus `web/x.txt` and `api/zz.txt`: FAIL G1, G2, G3 (secret-like text) and G3 (slug). Each G3 pattern was also checked on its own. Without `REPO` exported G3 fails.
  - Not demonstrated: the passing path of G4-G10, which needs the real implementation.

## 7 Tests NOT run

- Every test of the plan's section 4 (they do not exist yet).
- Validate Contract passing paths of G4-G10 (need the EXECUTE tree).
- All owner probes P-S1 to P-S5 (live behaviour, owner's machine).

## 8 Deviations

1. The review's item "G7 must fail when pytest crashes or collects nothing" is implemented by exit-code and summary checks; a full run on `main` took about 150 s in the dry run (uv sync and tests).
2. The default 0.5 is my proposal as the owner asked; it leaves the searches 75 of the 76 requests yesterday needs in the worst DEGRADED case. This is stated in the plan; 0.45 would cover it fully.
3. The share counter is a small day file under `reddit_stream/_meta/_budget/` written by the worker (the shared `PcSource` has no per-caller counter); it is a cap only, not a second budget state.
4. The shared worktree held copied parent changes at the start; they were stashed in a named stash (`parent-copy-changes`) in the isolated checkout and not touched. `origin` was added in that checkout for publication, never written to a file.

## 9 Blockers

None for this plan. EXECUTE is blocked on: #198 merged, this plan PR merged, Main filling the three envelope values.

## 10 Follow-up

- After EXECUTE the owner runs P-S1 to P-S5; P-S3 reports the real stream spend, which decides whether 0.5 stays.
- Proposed owner-decision line for a later docs task (Q4): "SPEC AC14 waiver: one method per coin series and window is accepted; Discovery takes the first store of `source_impl.reddit` that yields a change for the coin and window; `reddit_impl_order` and `source_impl.reddit` stay two copies guarded by a consistency test." Not part of the EXECUTE slice.
- Not in this slice: a second health line for the stream on the Sources row (Q3), window-level method choice, engagement enrichment (W8c3).

## 11 Context and cost

Read: the plan, the report, the docs-catchup plan (envelope and `PLAN-REV` pattern), `web_queries.py` and `attention_queries.json` of the #198 head (key validation pattern), `reddit_stream.py` of the #198 head (`run_poll`, `run_due`, completeness fields) by grep, `gh pr list` (read-only). About 120 KB in total. Tool calls for the dry runs ran about 6 minutes. No model spend figure is measured here (UNVERIFIED).
