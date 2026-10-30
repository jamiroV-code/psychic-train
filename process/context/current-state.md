---
name: context:current-state
description: "Observed, timestamped state of the repo: commit, workflows, tests, validator results, scheduled-job evidence, and what is unverified. Re-verify when stale."
keywords: current state, status, branch, commit, working tree, validators, baseline, ground truth, stale, verified, unverified, snapshot, cron
date: 30-10-26
---

# Current State

**Stamp: commit `3cd39e2` (`origin/main`, PR #196 merge, a docs-only SPEC wording fix; last code merge is PR #197 at `3f45921`), observed 2026-10-30 (UTC) from branch `claude/docs-catchup-2` (`origin/main` plus this docs catch-up).** Nightly data-snapshot bot commits sit below it. Previous state (stamp `4b3f70a`, 29-10-26) verbatim in `process/archive/current-state-archived_30-10-26.md`; older ones in `process/archive/current-state-archived_29-10-26.md` and `_21-10-26.md`.

Staleness rule (master-planner.md): stale when the stamp is not an ancestor of HEAD or when more than 10 non-cache commits landed since it (`git log 3cd39e2..HEAD --oneline -- . ':(exclude)api/data/cache' | wc -l`). Nightly bot commits do not make it stale.

## Observed (30-10-26)

| Fact | Value | Command |
|---|---|---|
| Merged since #190's base | #190 (T221 docs, 11:20Z), #191 (W8c2 Reddit stream, 11:20Z), #192 (W8e PC worker, 29-10 23:28Z), #193 (W8f Discovery wiring, 00:02Z), #194 (W8e2 host guide) and #195 (W8e2 health line), 11:19Z, #197 (W8g Sources panel text, 11:37Z), #196 (SPEC x_pool wording, 11:37Z) | `gh pr list --state merged --json number,title,mergedAt` |
| Open PRs | #198 (draft, W8c2 fix round 3: false feed end, retention, page cap, gap report); the wiring-plan PR and this docs PR may be open when read. The owner merges all (D-28) | `gh pr list --state open` |
| Workflows | 7 files in `.github/workflows` (names as on 29-10-26) | `ls .github/workflows` |
| `ci.yml` on main | success on `3cd39e2` and `d390dc9`; `3f45921` and `ff8e4a8` show `cancelled` (superseded runs) | `gh run list --workflow ci.yml --branch main` |
| Scheduled attention refresh | latest `chore: attention refresh` commit 2026-10-29 (30-10 not yet seen when read) | `git log origin/main --grep='attention refresh'` |

## Tests (worker reports, not re-run here)

- #191 W8c2 report: attention + tooling_guards + scripts, 1595 passed, 1 skipped (Windows PC, 29-10-26); the later 270-test run was its own subset. #192 W8e report: 1218 passed, 40 failed on Windows, the same 40 router tests also fail with `api/main.py` at `origin/main` (worker-reported). Figures for #193-#197: UNVERIFIED (not read). Web vitest for #197: UNVERIFIED.

## PC findings (OBSERVED, owner's PC, 30-10-26)

- 13 tests under `api/tests/routers/test_discovery.py` and `analytics/attention` `test_universe_classes.py::test_discovery_end_to_end_on_fixture` fail on plain `origin/main` with "handler must not reach the network" (found by the planner's verifier). Cause UNVERIFIED.
- Known Windows failure `tooling_guards/test_cli_guard.py::test_nothing_outside_the_tool_references_the_cli` (path separators, INFERENCE).

## omp model fallback (OBSERVED from session transcripts)

On 2026-10-29 an opus EXECUTE worker hit an Anthropic usage limit mid-run; omp switched it through `retry.fallbackChains` (opus, then openai-codex gpt-6-astra for 37 requests, then gpt-6.1-sol) and the run died on that provider's usage limit. **Owner decision:** fallback stays allowed; the planner reads the model per run from the agent transcript and reports any switch; code written on a fallback model needs an extra independent review.

## Validator results (owner PC, CRLF checkout, run 2026-10-29)

validate-context-discovery: 54 failures, 11 warnings (CRLF and Windows path separators, INFERENCE); validate-all-context: `failures: []`. Re-run for this change in `process/general-plans/active/docs-catchup-omp_29-10-26/docs-catchup-2_EXEC-REPORT_30-10-26.md`.

## What runs

- Screener and equities; Baskets (P5); data integration tooling (P9); discovery and weighted signal (P10: W1-W3, W9, weights v2 #156, volume fallback #183); universe U1-U6 (`U5 UNVERIFIED`); D-27 exchange tokens IN.
- Trends T100a-T100c and fixes (#149-#184, board-2). W8 collector slices merged: W8a, W8b, W8c (#185), W8d1 (#173), W8d2 (#186), W8c2 stream (#191, fix round 3 open in #198), W8e PC worker (#192), W8f Discovery wiring (#193), W8e2 host guide and health line (#194, #195), W8g Sources text (#197). All `review`; nothing is wired to a live provider here.
- Owner decisions 29/30-10-26 recorded in the W8c2 PLAN and SPEC (combined feeds, coverage per feed kind, no stream zeros, order `reddit_web` then `reddit_stream`, Q17 answered). Probe P-R7 passed on the owner's machine (owner-reported, not verified here).
- Docs and process: D-28 git flow; omp setup `process/context/omp-setup.md`; registry `process/MASTER-PLAN.md` and `process/MASTER-PLAN-board-2_29-10-26.md`; decisions D-22..D-28.

## Planner and worker spend

About 188 of the 200 USD ceiling (planner figures, 21-10-26). Spend after 21-10-26 is UNVERIFIED; costs of the rows since are `unmeasured`.

## Not run or unverified

- Live provider reachability; the owner's PC (deployed app, Task Scheduler, Tailscale); open owner probes from 13-10-26 (P-S1-1, P-S2-1, P-S8-1, P-S4-1, P-S5a-1, P-S5b-1, P-S6-1, P-S7-1, P-S9-2, P-S9-3, P-S11-2, BTC backfill): UNVERIFIED.
- Reddit and X access status; per-entry subreddit label on a combined Reddit feed (until the owner's probe); calibration checks 2027-01-18 and 2027-04-18 (future).
- Independent review: T117 no report found, UNVERIFIED. Every merged row since #145 is `review`; code written on a fallback model needs an extra review.

## Next actions

1. The owner reviews and merges open PRs (D-28), #198 first for W8c2.
2. Re-verify this state at the next planner session.
3. Owner probes above.
