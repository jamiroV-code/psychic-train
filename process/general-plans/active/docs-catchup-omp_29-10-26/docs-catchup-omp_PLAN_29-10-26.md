---
name: docs-catchup-omp-plan
description: "PLAN (T221) for the docs catch-up after PRs #145-#187: rewrite omp-setup.md with the 29-10-26 owner PC probe findings, rebuild current-state.md and MASTER-PLAN.md rows T119-T220 from PR and git data without inventing, and fix leftover commit-on-main wording."
date: 29-10-26
---

# Docs catch-up (omp setup, state, registry, wording) - PLAN

Date: 29-10-26
Task: T221 (next free ID: T220 is the highest seen in `git log --all` subjects and PR titles; no T221 exists anywhere)
Phase: PLAN only, nothing in this file has been executed
Complexity: Simple (docs only, RT0, one session, no phase gates)
Status: PLANNED, awaiting owner review and an explicit ENTER EXECUTE MODE.
PLAN-REV: 4 (round-4 fixes)

## Overview

The docs fell behind main: `omp-setup.md` is still an unverified guess although the owner probed omp on 2026-10-29, and `current-state.md` is stamped `faf416b` (21-10-26) but records only #145 merged and #146 open under a #144 stamp, while `main` has PRs through #187. `MASTER-PLAN.md` carries the same stamp. This plan makes the docs match observed facts, with `UNVERIFIED` wherever nothing was observed, lists where old "commit on main" wording survives, and replaces the stale worker self-merge text with the D-28 rule (the owner merges every PR; owner decision, locked in below).


## TL;DR

1. Rewrite `process/context/omp-setup.md` from "all UNVERIFIED" to "observed on the owner PC on 2026-10-29", with a phase-to-agent table and a short UNVERIFIED list (Section A).
2. `current-state.md` and `MASTER-PLAN.md` are stamped `faf416b` (21-10-26). This plan was measured at `b573309f` (29-10-26: 228 non-cache commits since the stamp, 68 merge commits, PRs #145-#187 all MERGED, measured with `gh`; at the 29-10-26 review PR #189 was open as a draft). `origin/main` has since moved (`c06d91d` includes the plan PR #188), so EXECUTE re-measures the stamp and G11 rejects stamping `faf416b` or `b573309f`. Rebuild from PR titles, PR bodies and git subjects only; every unknown field says `UNVERIFIED`, cost says `unmeasured`, never 0 (Section B). The board gets a T221 row that says only what was read (plan only: PR #188 merged, PR #189 draft at plan time; no cost figure).
3. No live doc still says planners commit on `main`. The T217 guard patterns found no live hit; the wider regex also hits completed plans, two ACTIVE plans (`pipeline-completeness_PLAN_28-09-26.md:195`, `screener-batch4_PLAN_10-10-26.md:382`) and the deployability SPEC (about `:332`); Section C says LEAVE for all of them. The `vc-publish` kit skill pushing `main` is decided: leave and flag only (Q6 closed).
4. Owner decision D-28 applied to the worker self-merge text (Q3, decided): `operating-instructions.md` line about workers (~56), `master-planner.md` section 5 (lines ~65-76) and section 10 (~149-152), and the status sentence in `MASTER-PLAN.md` (~line 20) are rewritten so that the owner merges every PR, a worker opens ONE draft PR and stops, the planner never merges (Section A2; new gates G15, G16).
5. Caps: `current-state.md` <= 8,000 B (target 7,000), `MASTER-PLAN.md` <= 19,000 B (target 17,500); the cap is NOT changed (Q5 decided). Both must shrink old text into `process/archive/` verbatim while growing new rows; the plan gives the order. If the T119-T220 rows still do not fit under 19,000 B with all IDs kept, that block goes into a NEW board file `process/MASTER-PLAN-board-2_<dd-mm-yy>.md` linked from MASTER-PLAN and the worker does not stop (B3 step 4).
6. EXECUTE agent (decided by the owner): `riper-sonnet` (docs only, RT0). No fallback agent; the spawn names `riper-sonnet` (Q1 closed).
7. Locked owner answers, no open questions left: Q2 no decision record, omp policy lives in `omp-setup.md` only and `decisions.md` is never edited; Q4 spend after 21-10-26 stays `UNVERIFIED`, the worker does not search for or use a later USD figure; Q5 board-2 file as in item 5; Q8 `task.isolation.apply = true` (default, OBSERVED 2026-10-29): successful isolated worker changes are auto-applied into the parent checkout and the worker's own branch and commit do not exist there, so the worker commits and pushes its own branch from its isolated checkout and reports that the planner must not publish the auto-applied copy again.
8. Owner flag: `decisions.md` D-6 (~lines 84-88) still says workers may self-merge although D-28 supersedes it in effect; the worker does NOT edit `decisions.md` and lists it in report heading 9 for the owner.


## Scope

In scope (EXECUTE may touch only these):

- `process/context/omp-setup.md` (rewrite), `process/context/current-state.md` (rewrite), `process/MASTER-PLAN.md` (edit)
- new `process/archive/current-state-archived_<dd-mm-yy>.md`, new `process/archive/master-plan-archived-rows_<dd-mm-yy>.md`, `process/archive/index.md` (index rows); new `process/MASTER-PLAN-board-2_<dd-mm-yy>.md` ONLY if B3 step 4 says the T119-T220 block does not fit the MASTER-PLAN cap (linked from MASTER-PLAN; frontmatter like the other process docs)
- `process/context/context-changelog.md` (one entry), `process/development-protocols/master-planner.md` (section 7 row, one sentence in section 8, the owner-merges rewrite of section 5 and of the section 10 sentences that assume a worker merge), `process/context/operating-instructions.md` (one sentence in the worktree bullet, the owner-merges rewrite of the workers bullet, one clause in the branch-deletion bullet), `process/context/all-context.md` (workflow count, only if verified; one index row only if G3 or G4 name the board-2 file as unindexed)
- the task folder `process/general-plans/active/docs-catchup-omp_<dd-mm-yy>/` for the REF copy and the REPORT

Out of scope: `CLAUDE.md`, `AGENTS.md` (not edited; Q7 decided: no change), `.github/**`, `.claude/**` (including the `vc-publish` skill; Q6 decided: leave and flag only), `.codex/**`, `.agents/**`, `scripts/pc-sync/**`, all source code and tests, completed or active plans of other tasks, `decisions.md` (Q2 closed: no decision record; never edited by the worker, even though D-6 is stale, see the A2 owner flag), user-level omp agent files outside the repo.


## Verified inputs (measured in this PLAN session, 2026-10-29)

| Fact | Value | Command |
|---|---|---|
| `main` | measured at `b573309ff081e29676df166db7fbb6849bd48556` (merge of #186); `origin/main` has since moved to `c06d91d`; `faf416b` is an ancestor of both | `git merge-base --is-ancestor faf416b HEAD` |
| Non-cache commits since stamp | 228 (68 merge commits) | `git log faf416b..HEAD --oneline -- . ':(exclude)api/data/cache' \| wc -l` |
| PRs | First measurement: 186 listed (#1-#187, #175 does not exist as a PR); states only MERGED and CLOSED (closed: #5, #86); open: none. At the 29-10-26 review the list also holds the plan's own PRs: #188 (MERGED) and #189 (OPEN, draft; read with `gh pr list --state open`) | `gh pr list -R <OWNER/REPO> --state all --limit 400 --json number,state` |
| Merge dates | #145-#146 on 2026-10-21; #185 on 2026-10-29 18:52Z; #186 on 2026-10-29 19:23Z; #187 on 2026-10-29 19:22Z | `gh pr view <n> --json mergedAt` |
| Workflows | 7 files (`ci.yml` plus six nightly snapshot and refresh jobs) | `ls .github/workflows` |
| Planner budget now | `planner_fixed=47235`, cap 56,000, headroom 8,765, `rc=0` (Windows CRLF checkout) | PLANNER-BUDGET block |
| Sizes now | `MASTER-PLAN.md` 17,774 B (T88-T118 block 2,638 B; historical block 9,608 B; recovery block 3,045 B), `current-state.md` 4,222 B, `CLAUDE.md` 13,806 B, router 6,231 B | `wc -c` |
| Line endings | working tree is CRLF (`core.autocrlf=true`); the index is LF. Every `wc -c` on the PC is larger than on Linux by one byte per line (`MASTER-PLAN.md` 132 lines) | `git ls-files --eol <file>` |
| Validator baseline on this PC | `validate-context-discovery.mjs`: 54 failures, 11 warnings, almost all "missing name/description frontmatter" and backslash-path "not indexed" lines [INFERENCE: CRLF and Windows path separators; the cloud baseline was 1 failure]; `validate-all-context.mjs`: `failures: []` | the two scripts |
| Isolated checkout of this PLAN worker | detached HEAD at `main`, no git remote configured at first (`git remote -v` empty, `origin/*` refs present), `gh` needs `-R` | `git remote -v` |
| `task.isolation.apply` | `true` (default): OBSERVED by the planner on 2026-10-29. Successful isolated worker changes are AUTO-APPLIED into the parent checkout as untracked or modified files; the worker's own branch and commit do not exist there | omp settings read in the PLAN session |

PR to task map (observed titles, #145 to #187). EXECUTE re-reads the full titles and bodies; this table is the starting map, not a source of truth:

| Group | PRs (task) |
|---|---|
| Universe and narratives U1-U6 | #145 (T113 U1), #146 (T115 U2), #148 (T119 list reviewed by owner), #151 (T123 U3), #160 (T146 U6, docs, D-27), #177 (T189 not-tradeable exclusion) |
| Weighted signal v2 | #156 (weights v2; task ID is past the first 90 characters of the title), #163 (T150 frozen-snapshot guard), #183 (T204 CoinGecko volume coverage only) |
| Trends T100a | #149 (T120 SPEC), #150 (T121 PLAN and VALIDATE), #152 (T122 T100a), #155 (T128), #157 (T134), #164 (T154), #165 (T155), #166 (T161), #171 (T160), #176 (T178), #178 (T192), #180 (T195) |
| Trends T100b, T100c and later | #159 (T144 batching plan), #162 (T149 T100b), #170 (T100c daily workflow), #172 (T175 point-in-time), #174 (T180 guard), #179 (T194 gaps analysis), #181 (T197), #182 (T196, T201 probe and campaign), #184 (T203) |
| W8 X and Reddit collector | #153 (T126 SPEC), #158 (T141 W8a vetting), #169 (T169 W8a2 twscrape vetting), #161 (T140 W8b core), #167 (T163 Reddit engagement SPEC and PLAN), #185 (T210 W8c Reddit connector), #173 (T171 W8d1 X pure core), #186 (T212 W8d2 X reader) |
| Docs and process | #147 (T118), #168 (T164 quality audit and host-profile PLAN), #187 (T217 D-28, PC scripts, omp note; T220 commits are in this branch, verify) |
| Data | #154 (T127 Wikipedia title INJ) |

Task IDs that appear in git subjects since the stamp but in no PR title (31; they sit in inner commit subjects, so how each landed is UNVERIFIED and its row says "git subject only"): T124 T131 T133 T135 T136 T138 T139 T142 T147 T152 T157 T158 T159 T166 T167 T168 T170 T179 T181 T186 T187 T190 T191 T200 T202 T207 T209 T211 T214 T219 T220. EXECUTE recomputes this list with the G8 pipeline.

## A. `process/context/omp-setup.md` (rewrite, target <= 7,000 B)

Keep the frontmatter keys (`name: context:omp-setup`, `description`, `keywords`, `date`); change `description` (no more "UNVERIFIED until probed"), add keywords `riper-sonnet, riper-opus, grok-review, agent definition, model pin, isolation, plan mode`, set `date` to the EXECUTE day. Tag every claim: **OBSERVED** (seen in the owner probe of 2026-10-29), **DOCUMENTED** (omp docs, not tested), **UNVERIFIED**. Sections, in this order:

1. **Status line.** Findings from the owner PC probe of 2026-10-29; four children were run (one per agent plus a nameless spawn).
2. **Model routing (OBSERVED).**
   - The `task` tool wire schema has no per-spawn model field. The model comes from the agent definition frontmatter or from a role.
   - A spawn with no agent name lands on the TASK role, which is a Grok model (`xai-oauth/grok-4.7`). Rule: **never spawn without naming an agent.**
3. **User-level agents (OBSERVED, created by the owner outside the repo, in the owner's omp agents folder under the home directory; their files are not in git):**

   | Agent | Model | Allowed use | Probe result |
   |---|---|---|---|
   | `riper-sonnet` | `@default` (Sonnet 5.5) | every non-EXECUTE phase, reviews, docs | context block read `anthropic/claude-sonnet-5-5` |
   | `riper-opus` | `@slow` (Opus 5.5) | EXECUTE only | context block read `anthropic/claude-opus-5-5` (self-reported; the `resolvedModel` field was not read: UNVERIFIED) |
   | `grok-review` | `@task` (Grok) | reviews only, read-only tools `read`, `grep`, `glob`; NOT for code until the owner approves | `xai-oauth/grok-4.7` |

4. **Phase to agent:**

   | Phase or job | Agent |
   |---|---|
   | RESEARCH, SPEC, INNOVATE, PLAN, VALIDATE, UPDATE PROCESS | `riper-sonnet` |
   | EXECUTE (code or build slice) | `riper-opus` |
   | EXECUTE of a docs-only (RT0) slice | `riper-sonnet` (owner decision for T221; the owner rule is that Opus is for real code and build) |
   | Independent read-only review | `riper-sonnet` or `grok-review` (`grok-review` never writes) |
   | Anything else, or no agent name | not allowed |

5. **What omp does not load (OBSERVED unless noted).**
   - `.claude/agents` and `.codex/agents` are skipped by omp agent discovery (DOCUMENTED); their `model:` pins are inert. `vc-*` agents are not usable as omp agents.
   - Children do not see `CLAUDE.md` or `AGENTS.md` (all four probes saw none). An envelope must carry the role line and the hard rules inline. The 8,000-byte envelope cap stays a repo rule (master-planner.md section 8).
   - `vc-*` skills are listed in a child's context (OBSERVED in the T221 PLAN session, not by the owner probe). Whether they trigger is UNVERIFIED.
6. **Plan mode (DOCUMENTED, not tested).** omp plan mode uses the PLAN role (Opus 5.5 for the owner); `--plan-yolo` executes on the smol role (Haiku). Rule: never use omp plan mode or `--plan-yolo` for RIPER phases or EXECUTE.
7. **Workers and isolation.**
   - Local workers are subagents or separate sessions on the owner PC, not cloud containers: same disk, same credentials; isolation is an isolated checkout or worktree plus a `claude/*` branch. Cloud behaviours (egress block, proxy) do not apply, do not assume them either way.
   - `task.isolation.enabled=true` is saved in the owner config (OBSERVED); `isolated: true` gives a separate checkout; not available in omp plan mode (DOCUMENTED). `task.isolation.apply = true` (default, OBSERVED 2026-10-29): successful isolated worker changes are auto-applied into the parent checkout as untracked or modified files, and the worker's own branch and commit do not exist there. A worker therefore publishes from its own isolated checkout (commit on its `claude/*` branch, push) and the planner must not publish the auto-applied copy again.
   - Observed in the T221 PLAN session: the isolated checkout has a detached HEAD, no git remote configured at first, and `gh` needs `-R` with the repo slug. Publishing path: add `origin` from the planner-pasted public URL, fetch, push only the worker's own `claude/*` branch. The Windows isolation backend behaviour beyond this is UNVERIFIED.
8. **Git flow (keep, D-28).** Existing section unchanged in substance: PC pushes `claude/*` branches and opens DRAFT PRs, never pushes `main`, owner merges every PR; `sync-main.ps1` and `push-task-branch.ps1`; ruleset with github-actions[bot] bypass; secrets stay outside the repo.
9. **UNVERIFIED list (final section):** the `resolvedModel` field of each agent; the Windows isolation backend behaviour; the PowerShell scripts in `scripts/pc-sync` (never run; the owner runs `-WhatIf`); ruleset Evaluate mode on a public free repo; whether `vc-*` skills trigger; plan mode and `--plan-yolo` behaviour; worker and planner spend after 21-10-26.

Remove the old "Mapping (UNVERIFIED)" table (its four rows are answered or replaced above: agents, skills, model roles, `AGENTS.md`).

Other edit lists for deliverable A:

| File | Edit |
|---|---|
| `process/development-protocols/master-planner.md` section 7 table (measured: header line 89, rows 91-92) | add a row after the `User's PC` row (line 92): `Owner PC, omp` / isolated checkout or git worktree plus `claude/<task-id>-<slug>` branch / "not a cloud container; see omp-setup.md". Section 8 (envelope template): add one sentence "omp children do not load CLAUDE.md or AGENTS.md; put role and hard rules in the envelope; name the agent in every spawn". |
| `process/context/operating-instructions.md` worktree bullet (about line 57) | add one sentence: on the owner PC omp may create isolated checkouts when `task.isolation.enabled` is on; they follow the same branch and PR rules; see omp-setup.md. Re-read the bullet first. The adjacent workers bullet (line ~56) and the branch-deletion bullet are rewritten in Section A2. |
| `process/context/all-context.md` line about "ci.yml plus five nightly" (about line 126, below the router part) | verify with `ls .github/workflows`; if there are six nightly files, change "five" to "six". Router row for omp-setup (line 91) already exists: no change. Skip this edit if `validate-all-context.mjs` fails after it. |
| `process/context/context-changelog.md` | one dated entry (29-10-26): omp-setup rewritten from the probe, current-state and MASTER-PLAN caught up to #187, worker self-merge text replaced by the D-28 owner-merges rule. Follow the file's existing entry format (read the last entries first). |

### A2. Owner merges every PR (D-28): exact replacement wording (owner decision Q3)

Operative rule, one sentence for every file: **the owner merges every PR; a worker opens ONE draft PR and stops; the planner never merges.** The 02-10-26 owner quote stays as history, marked "superseded by D-28". EXECUTE re-reads each place first (line numbers are from the 29-10-26 tree) and replaces only the named text. Every remaining line that still contains an operative self-merge phrase (`self-merge`, `self-archive`, `merge on itself`, `merge and archive on itself`, `may merge`, `can merge`, `may self`, `merge token`, `merges are serialized`) must also contain the literal `superseded by D-28` (gate G15 excludes exactly those lines). The replacement line `**Merge and archive (D-28):**` is deliberately not a scanned phrase: G15 looks for self-merge authorization wording, not generic words.

1. `process/context/operating-instructions.md` line ~56 (workers bullet). Replace the sentences "open a PR. A worker may self-merge only when every condition in master-planner.md holds (CI green on head, ... registry updated by the Master Planner). Unsure means stop at `review`." with: "A worker opens ONE draft PR and stops; the owner merges every PR (D-28) and the planner never merges. Unsure means stop at `review`." Keep the subagent sentence and the CLAUDE.md or AGENTS.md diff sentence unchanged. Branch-deletion bullet (~58): change "only merged worker task branches, under the 02-10-26 standing consent" to "only worker task branches whose PR the owner has merged (verified), under the 02-10-26 standing consent"; rest unchanged.
2. `process/development-protocols/master-planner.md` section 5 (lines ~65-76). Heading becomes `## 5. Standing authorization (user, 02-10-26; merge and archive part superseded by D-28)`. The "User's words" line becomes `History (user's words, 02-10-26, superseded by D-28 for the merge and archive part): "<the quote exactly as now>"`. Replace the numbered list with:
   - item 1 Spawn: unchanged.
   - item 2: "**Merge and archive (D-28):** the owner merges every PR. A worker opens ONE draft PR and stops; it never merges and never archives. The Master Planner never merges. Registry `accepted` then `archived` is recorded only after the owner's merge is verified and the acceptance rule (section 4) holds; the worker requests it in report headings 9 and 10. A diff touching CLAUDE.md or AGENTS.md stops at `review` for the user's diff check (user 03-10-26)."
   - item 3: "**Fail-safes:** an unsure worker stops at `review`; every condition must be evidenced; a denied or permission-prompting call means stop, never retry around it."
   - item 4: old item 5 (Verifiability) unchanged.
   - item 5: "**Owner merge check:** after each owner merge the Master Planner checks CI on the merge SHA on `main`; on red it proposes `git revert <merge sha>` to the owner and stops."
   - item 6: "**Items superseded by D-28:** the 03-10-26 worker-merge items (no class exception, serialized merges with a merge token in the registry, Open Question 10) are superseded by D-28 and not operative. Direct worker lane (Open Question 12): keep as is. RT4 bypass of user acceptance: still open (kept from the old item 8)."
   The closing paragraph ("Nothing above is platform-enforced ...") stays.
3. `master-planner.md` section 10 (lines ~149-152): row C "after the handover report is durable and the merge is verified" becomes "... and the owner's merge is verified". Branch-deletion consent (line ~152): keep the consent text, change "Order: merge verified (PR merged," to "Order: the OWNER's merge verified (PR merged by the owner," and append the sentence "The consent acts only after the owner's merge is verified; no worker or planner merge exists (D-28)." Line ~154 (wording rule) unchanged.
4. `process/MASTER-PLAN.md` line ~20 (status vocabulary), done inside the MASTER-PLAN rewrite (B3 step 7): replace "A status stronger than `review` needs independent evidence (merged PR, CI, vc-tester, user)." with "A status stronger than `review` needs independent evidence (an independent review report, CI on the merge SHA read with `gh`, vc-tester, or the owner); a merge alone is `review`." (G16).

**Owner flag (do NOT edit):** `process/context/decisions.md` D-6 (~lines 84-88, "Workers may self-merge under mechanical conditions", status active) still says workers may self-merge; D-28 supersedes it in effect. The worker leaves `decisions.md` untouched and lists this in report heading 9 for the owner. G15 does not scan `decisions.md`.


## B. `current-state.md` and `MASTER-PLAN.md`

### B1. Method (no invention)

Sources, read-only: `gh pr list -R <OWNER/REPO> --state all --limit 400 --json number,title,state,mergedAt,mergeCommit,body`; `gh pr view <n> --json body,files,statusCheckRollup` for PRs where a field is needed; `git log faf416b..HEAD --format='%h %ad %s' --date=short -- . ':(exclude)api/data/cache'`; report files in the task folders (`narrative-baskets-trends*`, `narrative-baskets*`, `data-integration-tooling*`) for test counts, cost and review evidence; `gh run list -R <OWNER/REPO> --workflow ci.yml --branch main --limit 5` for CI.

Rules:

- A field is filled only from one of those sources, with the source named (PR number, SHA, report path). Anything else is `UNVERIFIED`. Cost is a number only when a report or the registry already states it; otherwise `unmeasured`. Never write 0 for missing.
- Status: a task whose PR merged is `review` (merged, not independently reviewed). `accepted` or stronger only with independent evidence that is itself read: an independent review report (for example the T117 report if it exists; its verdict is read, not assumed), a green CI run on the merge SHA read with `gh`, or an owner statement. A planner or worker statement alone is not evidence. Nothing stronger than `review` is the default.
- "Merged" is shown from `mergedAt` and the merge SHA, not from the title.
- Task rows that have no PR (report-only tasks, IDs only seen in git subjects) say "git subject only" or "report only" with the path.

### B2. `process/context/current-state.md` (rewrite in place, <= 8,000 B, target <= 7,000 B)

1. Copy the current file verbatim to `process/archive/current-state-archived_<dd-mm-yy>.md` with frontmatter like `process/archive/current-state-archived_21-10-26.md` (read its first 10 lines and copy the shape). Nothing is deleted; the new file's stamp paragraph links to it.
2. New stamp: the `origin/main` SHA at EXECUTE time (re-measure; not `b573309f`), date, branch. Keep the staleness rule line with the new SHA.
3. Observed table (command column for every row): last code merges (#185, #186, #187 and their dates), open PRs listed as found at run time (`gh pr list --state open`, state the command and date; list every open PR by `#N`; the plan's own follow-up PR, for example #189, may still be open at that time; `none` only if the list is empty), workflows 7 (names), scheduled refresh evidence (re-run the `git log` for the attention refresh dates), frozen signal snapshots count (re-run), CI state of `ci.yml` on main (from `gh run list`; if not read: UNVERIFIED), `.agents/skills` row (keep only if still true).
4. Tests: copy only numbers found in merged PR bodies or reports, each with the PR number and "worker report, not re-run"; otherwise "UNVERIFIED".
5. Validator results: re-run the validators (Section Validate), state the PC result with the CRLF caveat; the cloud baseline of 1 failure is history.
6. "What runs": one short paragraph each: screener and equities; Baskets; Discovery and weighted signal (weights v2, PR #156; CoinGecko volume coverage only, PR #183); universe and narratives: name only the U-slices whose merged PR title names them (checked with `gh pr list --state merged`: U1 #145, U2 #146, U3 #151, U4 #144 (title "(T114, U4)", merged before the stamp `faf416b`, so outside the #145-#187 map), U6 #160; D-27: exchange tokens are IN as a narrative, supersedes D-20; PR #160); U5 has no merged PR title and is written `U5 UNVERIFIED`; Trends T100a, T100b, T100c and later work merged (PR list from the map above); W8 slices merged: W8a vetting (#158, #169), W8b (#161), W8c Reddit (#185), W8d1 X core (#173), W8d2 X reader (#186); docs and process PRs merged (#147, #168, #187 and others); git flow D-28 and `scripts/pc-sync/` merged, never run (UNVERIFIED); omp setup: `omp-setup.md`.
7. Planner and worker spend (Q4, decided): state the last figure that already exists in the repo with its date ("about 188 of the 200 USD ceiling, planner figures, 21-10-26") and add: "spend after 21-10-26 is UNVERIFIED". Do NOT search PR bodies, reports or anything else for a later USD figure and do not use one; the owner's answer is that spend after 21-10-26 stays UNVERIFIED.
8. "Not run or unverified": carry the 13-10-26 owner probes list and mark each `UNVERIFIED (no newer evidence read)`; Reddit API request of 18-10-26 and X: state that W8c and W8d2 code merged and that access or enablement status is UNVERIFIED; weighted-signal calibration checks 2027-01-18 and 2027-04-18 (still future); independent review: T96-T107 and part of T113 and T114 merged before it (D-26), plus whatever the T117 report states.
9. Next actions: no invented work. Write: (1) the owner reviews and merges this EXECUTE PR (D-28) and reads the report-heading-9 owner flags; (2) re-verify state at the next planner session; (3) the owner probes. A "queued" list only if a registry row says so.
10. Decision pointer: "decisions D-22..D-28 in decisions.md".

### B3. `process/MASTER-PLAN.md` (edit, <= 19,000 B, target <= 17,500 B)

Order of work (the byte arithmetic is the main risk: +about 3,500-5,000 B of new rows against a 1,226 B room under the ceiling, 0 under the target):

1. Archive file: create `process/archive/master-plan-archived-rows_<dd-mm-yy>.md` (shape of `master-plan-archived-rows_21-10-26.md`: frontmatter, "moved verbatim, nothing deleted"). Move into it verbatim the current "Weighted signal and universe tasks (T88-T118, compact rows)" table (2,638 B). Rule from master-planner.md section 12: IDs stay on the board, so the board keeps a compact replacement with every ID listed individually (for example `T96, T101, T102, T103, T104, T105, T106, T107: review, PRs #133-#140 ...`). Never write a range such as `T101-T107` in place of the IDs: G8 searches each ID with `grep -qw` and does not expand ranges, so a range finds only its first ID.
2. Update the three open rows before moving: T115 (merged #146), T117 (state from its report, else UNVERIFIED), T118 (merged #147). Update `Last verified` (date, new SHA, "PRs checked with `gh pr list --state all`"). `Active lanes`: list the open PRs exactly as `gh pr list --state open` returns them at run time (each as `#N`), and write `no open PRs` ONLY if that list is empty (G10 fails otherwise, except for PR numbers in `ALLOW_OPEN`; it reads only the Active lanes section and `Open PRs` label lines). Name a U-slice as merged only when a merged PR title names it: U1 #145, U2 #146, U3 #151, U4 #144 (T114, merged before the stamp, already on the board as T114, #144), U6 #160; U5 has no merged PR title, so write exactly `U5 UNVERIFIED` (G10 passes that wording; a line saying U5 is merged, done, shipped or complete fails unless a merged PR title contains U5). P9 and P8 and every other lane state not read from a file or `gh` are `UNVERIFIED`. Rewrite the same U-slice wording in the P10 registry row (about line 74, "U1, U4 done, U2 in review, U3 U5 U6 queued") as "U1 #145, U2 #146, U3 #151, U4 #144, U6 #160 merged; U5 UNVERIFIED". `built from` stays revision 6 plus the T118 reconciliation.
3. New compact block "Weighted signal, universe, Trends, W8 and docs (T119-T220)": columns `ID · What · Status · PR / evidence · Cost`. One row per ID that is a PR title ID (list in B1) plus one grouped row for the 31 git-subject-only IDs, each ID spelled out so the coverage gate below can find it. `What` is the PR title abbreviated, not interpreted. Status `review` for merged PRs; Cost `unmeasured`. Rows for the same program may share a line only if every ID and PR number is present.
   Also add one row `T221 · docs catch-up PLAN and EXECUTE (this task) · in_progress · PLAN only so far: plan PR #188 (merged) and plan-fix PR #189 (draft when the plan was written; re-read its state with gh at run time); EXECUTE in its own PR · unmeasured`. It states only what was read: the PLAN exists and PR #188 was merged. No cost figure. The G8 scan of git subjects since `faf416b` will find T221 (this plan's own commits), and G9 requires #188 and #189 on the board, so the row is required, not optional.
4. Measure (cap 19,000 B is NOT changed; target 17,500 B). If over the target but under the cap: nothing more to do. If over the cap with all IDs kept: first apply the trim rule of master-planner.md section 12 in this order: (a) recovery-program (R) evidence cells to at most 300 B with the report path, moving the longer text verbatim to the archive file; (b) historical T-rows whose status is already `archived` or `accepted` and whose evidence cell is over 300 B: shorten the cell, move the long text verbatim; (c) `Carried notes` and `Active lanes` wording. If it is still over the cap (Q5, decided): move the whole new T119-T220 block, including the T221 row, verbatim into a NEW board file `process/MASTER-PLAN-board-2_<dd-mm-yy>.md` (frontmatter like `process/MASTER-PLAN.md`: `name`, `description`, `date`, `metadata` with `node_type`, `type`, `read_when`; one heading that contains `T119-T220`; same columns) and leave in MASTER-PLAN one link line `Tasks T119-T221: see process/MASTER-PLAN-board-2_<dd-mm-yy>.md` plus the open rows T115, T117, T118. Never drop a row or an ID, never change the cap, and do not stop for this. Gates G8, G9, G14 read MASTER-PLAN plus every `process/MASTER-PLAN-board-2_*.md`; G13 allows the new file. If G3 or G4 then name the new file as not indexed, add the index row they ask for to `process/context/all-context.md` and say so in the REPORT.
5. `process/archive/index.md`: one row for each new archive file (the board-2 file is a live board file, not an archive: no index row), same columns as existing rows; add an Approvals Log row only if the log's own rule requires it (read its first lines); the owner merging the EXECUTE PR is the approval and the row says so.
6. Mention D-27 and D-28 in the registry text where the rows apply (T146 row: D-27; T217 row: D-28). Mention that planner and worker spend after 21-10-26 is `UNVERIFIED` in the `Active lanes` paragraph (no figure, no search).
7. `process/MASTER-PLAN.md` line ~20 status vocabulary: apply Section A2 item 4 in the same rewrite (the sentence no longer lets a merged PR alone justify a status stronger than `review`). It sits in the `Carried notes` area; it does not add bytes beyond about +80 B, count them in step 4.

Cost of the current-state and MASTER-PLAN together after the edit must keep `planner_fixed <= 56,000` (now 47,235; room 8,765 B for both files plus the other fixed files).

## C. Wording: planners commit on `main`

Search used: the five T217 guard regexes over the five guarded docs, plus a repo-wide regex for "commit ... on|to main" and "push ... to main" (searched `CLAUDE.md`, `AGENTS.md`, `README.md`, `process/`, `.claude/`, `.codex/`, `.agents/`, `scripts/`).
**Live docs: no stale main-commit rule remains.** Already D-28-conformant (no edit): `CLAUDE.md:43` and `:131`, `AGENTS.md:51`, `process/development-protocols/implementation-standards.md:64-67`, `process/development-protocols/master-planner.md:83`, `process/context/operating-instructions.md:10` and `:55`, `process/context/omp-setup.md:15-16`, `scripts/pc-sync/README.md:3`, `process/context/decisions.md:242-245`. The guard `api/tests/tooling_guards/test_git_flow_guard.py` pins these five docs. Separate from that rule, the worker self-merge text in `operating-instructions.md:56` and `master-planner.md` sections 5 and 10 is stale versus D-28 and is rewritten in this task (Section A2).

Remaining old wording, with decision (line numbers from the 29-10-26 tree; EXECUTE re-greps first):

| File and line | Text (short) | Decision |
|---|---|---|
| `process/general-plans/completed/master-planner-recovery_02-10-26/master-planner-recovery_PLAN_02-10-26.md:369`, `:534`, `:774`, `:1447` | "commit directly on `main` per policy", "commit on `main` only when you ask", "repo policy (commit directly on `main` only on request)", cosmetic-gap note "commit on `main` by default" | LEAVE. Completed plan, historical record; D-28 "Consequences" already says it supersedes the old rule. |
| `process/general-plans/completed/master-planner-recovery_02-10-26/master-planner-recovery_GATE3-REVIEW_REF_03-10-26.md:72`, `:137` | verbatim copy of the old entry block line and a check list naming it | LEAVE (verbatim snapshot). |
| `process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness_PLAN_28-09-26.md:195` | "commit directly on the current branch; do not touch `main`" | LEAVE (already consistent with D-28). |
| `process/general-plans/active/screener-batch4_10-10-26/screener-batch4_PLAN_10-10-26.md:382` | "REF files are committed on main before the spawn" | LEAVE (old flow, historical plan). |
| nightly-cron wording (deployability SPEC `:195`, `:332`; pipeline-completeness PLAN `:116`, `:274`; SPEC `:248`; `.github` job descriptions) | workflows commit to `main` | LEAVE; correct under D-28 (bot exception). |
| `process/context/operating-instructions.md:56` and `process/development-protocols/master-planner.md` sections 5 and 10 (lines ~65-76, ~149-152) | worker self-merge standing authorization (02-10-26) versus D-28 "owner merges every PR" | EDIT in this task (owner decision Q3): Section A2. The 02-10-26 quote stays as history marked superseded by D-28. |
| `.claude/skills/vc-publish/SKILL.md:291`, `:294`, `:303` (command block `git push origin main && git push --tags`) and the same lines in `.agents/skills/vc-publish/SKILL.md` | pushes `main` of the separate kit repo | LEAVE and flag only (owner decision Q6). The skill's own text at about `:298` says the command applies only to the kit repo, never to a project repo that forbids pushing to `main`. Not edited (`.claude/**` and `.agents/**` are out of scope). |

Result: **the only edits in deliverable C are the Section A2 rewrites**; every other hit is listed above with LEAVE or flag-only. Gates: G6 (no old main-commit rule in the live docs), G15 and G16 (no self-merge authorization text left).

`CLAUDE.md` and `AGENTS.md`: not edited (owner decision Q7: no change; omp children not loading them is covered by `omp-setup.md` and by the envelope rules).


## Validate contract (EXECUTE runs these; all from the repo root in Git Bash)

All gates are ONE bash script (the single fenced block below). The worker extracts it from this plan with the plain shell commands of the envelope (step 1; no angle-bracket placeholders in any executable command), runs `bash "$GF" before` once before any edit, then `STAMP=newsha bash "$GF" after` once the edits are done, and again with `PHASE=post` after the commit (tree must be clean). Baselines for G1 to G5 live in `$BASEDIR`; the default is the named dir `t221-baseline` under the git dir (never in the tree), and the worker leaves BASEDIR unset. They survive every later run. Only `CLEANUP=1 bash "$GF"` deletes the baselines (it removes only the five files the script writes, then the dir if empty); it runs last. Every gate prints `PASS`, `FAIL` or `NOTRUN`; the script exits non-zero if any gate fails. `gh` must be on `PATH` and authenticated; `REPO` (owner/name) is exported by the worker or derived at run time from `git remote get-url origin`, and is never written into repo files.

Who runs what: the worker runs `before` once and `after` (all of G1-G16) before opening the PR, and `PHASE=post` after the commit and before the push (BASEDIR unset; the worker deletes its baselines with `CLEANUP=1` at the end). Main CANNOT reuse those baselines (they sit in the worker's own git dir and are deleted), so Main re-runs the whole check with the procedure below after the worker reports: baselines taken in a clean worktree of the merge base (origin/main before the EXECUTE change), `after` taken in a clean worktree of the pushed EXECUTE branch, both with the same `BASEDIR` outside every git dir. n = the EXECUTE PR number.

Main procedure (Git Bash, from any checkout of the repo; `gh` on `PATH` and authenticated; nothing is written into the repo):

    export REPO=FILL_IN
    git fetch origin
    EXECBR=claude/t221-docs-catchup-exec
    MBSHA="$(git merge-base origin/main "origin/$EXECBR")"
    T="$(mktemp -d)"
    export BASEDIR="$T/baselines"
    git worktree add --detach "$T/base" "$MBSHA"
    git worktree add --detach "$T/exec" "origin/$EXECBR"
    PLANPATH=process/general-plans/active/docs-catchup-omp_29-10-26/docs-catchup-omp_PLAN_29-10-26.md
    GF="$T/t221-gates.sh"
    tr -d '\r' < "$T/exec/$PLANPATH" | sed -n '/^```bash$/,/^```$/p' | sed '1d;$d' > "$GF"
    bash -n "$GF"
    (cd "$T/base" && bash "$GF" before)
    (cd "$T/exec" && PHASE=post STAMP="$MBSHA" ALLOW_OPEN=n bash "$GF" after)
    (cd "$T/exec" && CLEANUP=1 bash "$GF")
    git worktree remove --force "$T/base"; git worktree remove --force "$T/exec"; rm -rf "$T"

Replace n with the EXECUTE PR number and FILL_IN with the repo slug. `STAMP` must be the SHA the worker wrote into `current-state.md` (normally `MBSHA`, the commit the worker branched from). `before` runs on the clean merge base, so G3 and G5 baselines describe the unedited docs; `PHASE=post ... after` runs on the clean pushed branch, so G13 also checks that the tree is clean. The script normalises `BASEDIR` to a path that Node can read (`pwd -W` on Git Bash), so a `mktemp -d` directory works. If Windows refuses to delete a worktree folder, say so in the review and leave it.

Dry run of this plan (before EXECUTE): see the REPORT, heading 6.

```bash
#!/usr/bin/env bash
# T221-EXEC validate contract. Run from the repo root in Git Bash.
# Set REPO (owner/name of the repo) in the environment, or let it derive from origin.
# Usage: bash "$GF" before                              (baselines: G1 G2 G3 G4 G5; run ONCE, an existing baseline is kept)
#        STAMP=newsha bash "$GF" after                  (all gates, working tree, before commit)
#        PHASE=post STAMP=newsha bash "$GF" after       (all gates, after commit; tree must be clean)
#        CLEANUP=1 bash "$GF"                           (the only call that deletes the baselines; run it last)
# BASEDIR=/absolute/dir keeps the baselines outside the git dir (Main runs `before` in one checkout and `after` in another with the same BASEDIR). Default: <git dir>/t221-baseline.
# ALLOW_OPEN="n m" lets those PR numbers be open without being listed in current-state.md (Main passes the EXECUTE PR).
# Every gate prints PASS/FAIL/NOTRUN; the script exits 1 if any gate FAILs.
set -u
REPO="${REPO:-$(git remote get-url origin | sed -E 's#^.*github\.com[:/]##; s#\.git$##')}"   # derived at run time, never written into repo files
BASE="${BASE:-origin/main}"
PHASE="${PHASE:-pre}"
ALLOW_OPEN="${ALLOW_OPEN:-}"
OLDSTAMP=faf416b
GD="$(git rev-parse --git-dir)"
BD="${BASEDIR:-$GD/t221-baseline}"
if [ "${CLEANUP:-}" = 1 ]; then for x in vcd.before.json vcd.after.json pytest.before pytest.before.tmp pytest.after; do rm -f "$BD/$x"; done; rmdir "$BD" 2>/dev/null; echo "baselines deleted: $BD"; exit 0; fi
mkdir -p "$BD" || { echo "cannot create BASEDIR $BD"; exit 1; }
BD="$(cd "$BD" && { pwd -W 2>/dev/null || pwd; })"   # Windows path for Node on Git Bash
MB="$(git merge-base "$BASE" HEAD)"
FAIL=0
gate() { n=$1; shift; out=$( "$@" 2>&1 ); rc=$?; printf '%s\n' "$out"
  case $rc in 0) echo "PASS $n";; 77) echo "NOTRUN $n";; *) echo "FAIL $n"; FAIL=1;; esac; }
cap() { n=$(wc -c < "$1" | tr -d ' '); echo "$1 $n B (cap $2)"; [ "$n" -le "$2" ] || { echo "OVER-CAP $1"; return 1; }; }
boards() { ls process/MASTER-PLAN.md process/MASTER-PLAN-board-2_*.md 2>/dev/null; }   # the board: MASTER-PLAN plus the optional board-2 file

g1() { s=$(mktemp); trap 'rm -f "$s"' EXIT
  sed -n '/^# PLANNER-BUDGET:BEGIN/,/^# PLANNER-BUDGET:END/p' process/development-protocols/master-planner.md > "$s"
  o=$(bash "$s" 2>&1 | tr -d '\r'); echo "$o"
  if echo "$o" | grep -qE 'OVER-CAP|MISSING'; then return 1; fi
  echo "$o" | grep -qx 'rc=0'; }

g2() { r=0
  cap process/context/current-state.md 8000 || r=1
  cap process/MASTER-PLAN.md 19000 || r=1
  cap process/context/omp-setup.md 7000 || r=1
  for f in process/context/current-state.md process/context/omp-setup.md $(boards); do
    echo "LF size $f $(tr -d '\r' < "$f" | wc -c | tr -d ' ') B (info)"; done
  n=$(wc -c < process/MASTER-PLAN.md | tr -d ' '); [ "$n" -le 17500 ] || echo "WARN MASTER-PLAN over target 17500"
  return $r; }

vcd() { node .claude/skills/vc-audit-context/scripts/validate-context-discovery.mjs; }
g3before() { if [ -s "$BD/vcd.before.json" ]; then echo "baseline exists, kept"; return 0; fi
  vcd > "$BD/vcd.before.json"; test -s "$BD/vcd.before.json"; }
g3() { vcd > "$BD/vcd.after.json"; test -s "$BD/vcd.before.json" || { echo "no baseline: run 'before' first"; return 1; }
  node -e 'const f=require("fs"),g=process.argv[1];const b=JSON.parse(f.readFileSync(g+"/vcd.before.json","utf8")).failures,a=JSON.parse(f.readFileSync(g+"/vcd.after.json","utf8")).failures;const n=a.filter(x=>!b.includes(x));console.log("baseline",b.length,"after",a.length,"new",n.length);n.forEach(x=>console.log(x));process.exit(n.length?1:0)' "$BD"; }

g4() { node .claude/skills/vc-generate-context/scripts/validate-all-context.mjs | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const j=JSON.parse(s);console.log("failures",j.failures.length);process.exit(j.failures.length?1:0)})'; }

# pyt prints the failing test ids; a pytest crash (non-zero exit without any FAILED line) returns 2 and never looks like a clean run
pyt() { o=$(uv run --project api pytest api/tests/tooling_guards -q 2>&1); rc=$?; o=$(printf '%s\n' "$o" | tr -d '\r')
  if [ "$rc" -ne 0 ] && ! printf '%s\n' "$o" | grep -q '^FAILED'; then echo "pytest exit $rc without any FAILED line (crash or collection error); last lines:" >&2; printf '%s\n' "$o" | tail -n 8 >&2; return 2; fi
  printf '%s\n' "$o" | grep '^FAILED' | sed 's/ - .*//' | sort -u || true; }
g5before() { command -v uv >/dev/null || { echo "uv not available: report as not run"; return 77; }
  if [ -f "$BD/pytest.before" ]; then echo "baseline exists, kept"; return 0; fi
  pyt > "$BD/pytest.before.tmp" || { echo "baseline run crashed"; rm -f "$BD/pytest.before.tmp"; return 1; }
  mv "$BD/pytest.before.tmp" "$BD/pytest.before"; echo "baseline failing guard tests: $(wc -l < "$BD/pytest.before" | tr -d ' ')"; }
g5() { command -v uv >/dev/null || { echo "uv not available: report as not run"; return 77; }
  test -f "$BD/pytest.before" || { echo "no baseline: run 'before' first"; return 1; }
  pyt > "$BD/pytest.after" || { echo "pytest crashed: not a clean run"; return 1; }
  n=$(comm -13 "$BD/pytest.before" "$BD/pytest.after"); echo "new failing guard tests: $(echo -n "$n" | grep -c .)"; echo "$n"
  [ -z "$n" ]; }

g6() { P='commit[a-z]*[[:space:]]+(only when the user asks,[[:space:]]+)?directly on `main`|commit on `main` by default|commit on `main`,? only when|everyone else commits on `main`|direct user work commit on `main`'
  printf 'commit directly on `main` per policy\n' | grep -Eq "$P" || { echo "pattern self-test failed"; return 1; }
  if grep -nEi "$P" CLAUDE.md AGENTS.md process/development-protocols/implementation-standards.md process/development-protocols/master-planner.md process/context/operating-instructions.md process/context/omp-setup.md process/context/current-state.md process/MASTER-PLAN.md; then return 1; fi; }

g7() { f=process/context/omp-setup.md; r=0
  for t in riper-sonnet riper-opus grok-review 'xai-oauth/grok-4.7' 'never spawn without naming an agent' 'task.isolation' OBSERVED DOCUMENTED; do
    grep -qiF -- "$t" "$f" || { echo "MISSING term: $t"; r=1; }; done
  n=$(grep -o 'UNVERIFIED' "$f" | wc -l); echo "UNVERIFIED mentions: $n"; [ "$n" -ge 6 ] || { echo "MISSING: fewer than 6 UNVERIFIED"; r=1; }
  if grep -n 'Mapping (UNVERIFIED)' "$f"; then r=1; fi
  return $r; }

g8() { r=0; ids=$(git log "$OLDSTAMP"..HEAD --format=%s -- . ':(exclude)api/data/cache' | grep -oE '\bT[0-9]{2,3}[a-z]?[0-9]?\b' | sort -u)
  [ -n "$ids" ] || { echo "no task IDs found in git subjects since $OLDSTAMP (git failure or empty log)"; return 1; }
  echo "task IDs in git subjects since $OLDSTAMP: $(echo "$ids" | wc -l | tr -d ' ')"
  all=$(cat $(boards))
  for id in $ids; do echo "$all" | grep -qw -- "$id" || { echo "MISSING $id"; r=1; }; done
  return $r; }

g9() { r=0; l=$(gh pr list -R "$REPO" --state all --limit 400 --json number --jq '.[].number' | tr -d '\r') || return 1
  [ -n "$l" ] || { echo "no PR list returned"; return 1; }
  all=$(cat $(boards))
  for n in $(echo "$l" | sort -n); do
    { [ "$n" -ge 145 ] && [ "$n" -le 187 ]; } || continue
    echo "$all" | grep -qE "#$n([^0-9]|$)" || { echo "MISSING #$n"; r=1; }; done
  for n in 188 189; do echo "$all" | grep -qE "#$n([^0-9]|$)" || { echo "MISSING #$n (the plan's own PR)"; r=1; }; done
  return $r; }

U5TOK='(?<![A-Za-z0-9-])U5(?![A-Za-z0-9])'   # the token U5 (not AC-U5, not U55)
# lanes_text FILES: only the lines that can claim "no open PRs": the section under a heading containing "Active lanes", and any line that starts with an "Active lanes" or "Open PRs" label (table cell or bullet)
lanes_text() { cat "$@" | { s=0; while IFS= read -r l; do case "$l" in '#'*) case "$l" in *[Aa]ctive\ lanes*) s=1;; *) s=0;; esac;; esac; if [ "$s" = 1 ] || printf '%s\n' "$l" | grep -qE '^[|*[:space:]-]*(Active lanes|Open PRs)'; then printf '%s\n' "$l"; fi; done; }; }
# u5_claims FILES: succeeds when a line says U5 is merged/done/shipped/complete (claim word after U5 or right before it, no ; . | and no not/never/UNVERIFIED/queued between)
u5_claims() { grep -nP "${U5TOK}(?:(?!\b(?:not|never|UNVERIFIED|queued)\b)[^;.|]){0,30}?\b(?:merged|done|shipped|completed?)\b|\b(?:merged|done|shipped|completed?)\b[: ]+(?:U[0-9],? *(?:and )?)*${U5TOK}" "$@"; }

g10() { j=$(gh pr list -R "$REPO" --state all --limit 400 --json number,state) || return 1
  bad=$(echo "$j" | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const a=JSON.parse(s).filter(p=>p.number>=145&&p.number<=187);const bad=a.filter(p=>p.state!=="MERGED");console.log(bad.map(p=>"#"+p.number+" "+p.state).join("\n"));console.error("PRs 145-187 found: "+a.length+" (expect 42, #175 is not a PR)");if(bad.length||a.length!==42)process.exit(1)})') || { echo "$bad"; return 1; }
  open=$(echo "$j" | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>console.log(JSON.parse(s).filter(p=>p.state==="OPEN").map(p=>p.number).join("\n")))' | tr -d '\r')
  echo "open PRs at run time: $(echo $open)"; r=0; others=""
  for n in $open; do
    case " $ALLOW_OPEN " in *" $n "*) continue;; esac
    others="$others #$n"
    grep -qE "#$n([^0-9]|$)" process/context/current-state.md || { echo "open PR #$n is not listed in current-state.md"; r=1; }; done
  if [ -n "$others" ] && lanes_text $(boards) process/context/current-state.md | grep -Ei 'no open (PRs|pull requests)'; then echo "an Active lanes or Open PRs line says 'no open PRs' while$others is open"; r=1; fi
  m=$(gh pr list -R "$REPO" --state merged --limit 400 --json title --jq '.[].title' | tr -d '\r') || return 1
  if u5_claims $(boards) process/context/current-state.md; then echo "$m" | grep -qP "$U5TOK" || { echo "U5 is claimed merged/done but no merged PR title contains U5"; r=1; }; fi
  return $r; }

g11() { : "${STAMP:?set STAMP to the new stamp sha}"
  case "$STAMP" in "$OLDSTAMP"*|b573309*) echo "STAMP is an old stamp"; return 1;; esac
  git merge-base --is-ancestor "$STAMP" HEAD || { echo "STAMP is not an ancestor of HEAD"; return 1; }
  n=$(git log "$STAMP"..HEAD --oneline -- . ':(exclude)api/data/cache' | wc -l | tr -d ' '); echo "commits since stamp: $n (max 10)"
  [ "$n" -le 10 ] || return 1
  grep -q "${STAMP:0:7}" process/context/current-state.md || { echo "stamp not written in current-state.md"; return 1; }; }

changed() { { git diff --name-only "$MB"; git ls-files --others --exclude-standard; } | sort -u; }
added() { git diff -U0 "$MB" | grep -E '^\+' | grep -vE '^\+\+\+ '; git ls-files --others --exclude-standard | while IFS= read -r f; do cat -- "$f"; done; }

g12() { ACCT="${REPO%%/*}"; [ -n "$ACCT" ] || { echo "REPO unresolved"; return 1; }
  P='(token|secret|password|cookie)[[:space:]]*[=:][[:space:]]*[^[:space:]]{8,}|\b[0-9]{1,3}(\.[0-9]{1,3}){3}\b|C:\\Users|/Users/|/home/[a-z]'
  printf 'password: abcdefgh1\n' | grep -Eiq "$P" || { echo "pattern self-test failed"; return 1; }
  if added | grep -nEi -e "$P" -e "$ACCT"; then echo "possible secret, IP, account name or user path in added lines"; return 1; fi; }

g13() { r=0
  git diff --check "$MB" || r=1
  ALLOW='^process/context/(omp-setup|current-state|context-changelog|operating-instructions|all-context)\.md$|^process/MASTER-PLAN\.md$|^process/MASTER-PLAN-board-2_[0-9-]+\.md$|^process/development-protocols/master-planner\.md$|^process/archive/(current-state-archived_[0-9-]+|master-plan-archived-rows_[0-9-]+|index)\.md$|^process/general-plans/active/docs-catchup-omp_29-10-26/'
  changed | while IFS= read -r f; do echo "$f" | grep -Eq "$ALLOW" || echo "OUT OF SCOPE $f"; done | tee "$GD/t221-scope.out"
  if [ -s "$GD/t221-scope.out" ]; then r=1; fi; rm -f "$GD/t221-scope.out"
  if [ "$PHASE" = post ]; then s=$(git status --porcelain); if [ -n "$s" ]; then echo "tree not clean after commit:"; echo "$s"; r=1; fi; fi
  return $r; }

# G14: in every board file, the block under the heading that contains T119-T220 must exist, with no zero cost cell and no blank or '-' cost cell
g14() { found=0; r=0
  for f in $(boards); do
    blk=$(sed -n '/^#.*T119-T220/,/^#/{/^#/!p}' "$f" | tr -d '\r')
    [ -n "$blk" ] || continue
    found=1
    if echo "$blk" | grep -nE '\|[[:space:]]*(\$?0([.,]0+)?([[:space:]]*USD)?|0[[:space:]]*/[[:space:]]*0([[:space:]]*USD)?)[[:space:]]*\|[[:space:]]*$'; then echo "zero cost cell in $f"; r=1; fi
    emp=$(echo "$blk" | awk -F'|' '/^[[:space:]]*\|/ { l=$0; gsub(/[|:[:space:]-]/,"",l); if (l=="") next; c=$(NF-1); gsub(/^[[:space:]]+|[[:space:]]+$/,"",c); if (c=="Cost") next; if (c==""||c=="-"||c=="—"||c=="–") print $0 }')
    if [ -n "$emp" ]; then echo "$emp"; echo "blank, '-' or dash cost cell in $f (write unmeasured)"; r=1; fi
  done
  [ "$found" -eq 1 ] || { echo "MISSING block (heading with T119-T220 in MASTER-PLAN or the board-2 file)"; return 1; }
  return $r; }

# G15 scans for the actual self-merge authorization phrases, never for generic words such as 'merge and archive'
g15() { r=0; F="process/development-protocols/master-planner.md process/context/operating-instructions.md"
  P='self-merge|self-archive|merge on itself|merge and archive on itself|may merge|can merge|may self|merge token|merges are serialized'
  printf 'a worker may self-merge when\n' | grep -Eiq "$P" || { echo "pattern self-test failed (must match)"; return 1; }
  printf '**Merge and archive (D-28):** the owner merges every PR.\n' | grep -Eiq "$P" && { echo "pattern self-test failed (D-28 wording must not match)"; return 1; }
  if grep -nEi "$P" $F | grep -vi 'superseded by D-28'; then echo "live self-merge authorization text remains"; r=1; fi
  for f in $F; do grep -q 'opens ONE draft PR' "$f" || { echo "MISSING owner-merges rule in $f"; r=1; }; done
  return $r; }

g16() { if grep -n 'needs independent evidence (merged PR' process/MASTER-PLAN.md; then return 1; fi
  grep -q 'a merge alone is `review`' process/MASTER-PLAN.md || { echo "MISSING corrected status sentence"; return 1; }; }

if [ "${1:-}" = before ]; then gate G1 g1; gate G2 g2; gate G3-before g3before; gate G4 g4; gate G5-before g5before; exit $FAIL; fi
gate G1 g1; gate G2 g2; gate G3 g3; gate G4 g4; gate G5 g5; gate G6 g6; gate G7 g7; gate G8 g8; gate G9 g9
gate G10 g10; gate G11 g11; gate G12 g12; gate G13 g13; gate G14 g14; gate G15 g15; gate G16 g16
[ "$FAIL" -eq 0 ] && echo "ALL GATES PASS (G5 may be NOTRUN). Baselines are kept in $BD; delete them only with CLEANUP=1." || echo "GATES FAILED"
exit $FAIL
```

Gate notes (what each one proves):

- G1 planner budget: the real block from master-planner.md section 12 is extracted to a temp file; fails on `OVER-CAP`, `MISSING` or anything but `rc=0` (CRLF checkout, the stricter count).
- G2 sizes: `current-state.md` <= 8,000 B, `MASTER-PLAN.md` <= 19,000 B, `omp-setup.md` <= 7,000 B (these are failures); the only WARN the script prints is MASTER-PLAN over its 17,500 B target. LF sizes of those files and of the board-2 file are printed for information. On this PC the working tree is CRLF, so every number is about one byte per line higher than on Linux.
- G3 context discovery: no new failure against the stored baseline (the PC baseline is 54 failures, 11 warnings, CRLF and path-separator artefacts; do not fix them here). G4 all-context: `failures` empty (the "N days old" warning is fine).
- G5 doc guard tests: `uv run --project api pytest api/tests/tooling_guards -q`; no new failing test against the stored baseline (one pre-existing failing test on this PC, `test_cli_guard.py`, backslash paths: record it, do not fix it). The pytest exit code is captured: a non-zero exit without any `FAILED` line (crash, collection error) fails the gate and the baseline run, it never looks like a clean baseline. If `uv` is missing the gate prints `NOTRUN`; report it as not run, do not substitute.
- G6 old main-commit rule: the five T217 patterns, with a self-test against a sample of the old text, over the eight live docs. G7 omp-setup: each required term is checked separately, at least 6 `UNVERIFIED` mentions, the old "Mapping (UNVERIFIED)" heading is gone.
- G8 every task ID in git subjects since `faf416b` is on the board (MASTER-PLAN plus the board-2 file; T221 included, see B3 step 3), each searched on its own with `grep -qw`; ranges such as `T101-T107` are NOT expanded, so every ID must be spelled out; it FAILS when git returns no IDs. G9 every PR number from #145 to #187 that `gh` lists is on the board, plus the plan's own PRs #188 and #189 (not every later PR forever).
- G10 PRs #145-#187: 42 found, all MERGED (#175 is not a PR). Open PRs are read at run time (the plan's own follow-up PR #189 may be open); every open PR must be listed as `#N` in `current-state.md` (B2 step 3), except numbers passed in `ALLOW_OPEN` (Main passes the EXECUTE PR when it re-runs after the PR exists). G10 also FAILS when a claim line says `no open PRs` (or `no open pull requests`) while an open PR outside `ALLOW_OPEN` exists; claim lines are only the section under an `Active lanes` heading and lines that start with an `Active lanes` or `Open PRs` label in `MASTER-PLAN.md`, the board-2 file and `current-state.md` (a later quotation of the phrase does not count). It also FAILS when a line says U5 is merged, done, shipped or complete (token `U5` only, not `AC-U5`; claim word within 30 characters, no `;` `.` `|`, and no `not`, `never`, `UNVERIFIED` or `queued` between) and no merged PR title contains U5. `U5 UNVERIFIED`, `U5 queued` and `U5 not merged` pass. The U5 logic was proved on a temp copy in revision 4 (see the REPORT).
- G11 new stamp: not an old stamp, ancestor of HEAD, at most 10 non-cache commits since, written in `current-state.md`.
- G12 secrets, IPs, user paths, account name (derived from the repo slug): checked on lines ADDED relative to the merge base with `origin/main`, committed or not, plus untracked files; no empty-xargs. G13 `git diff --check` against the merge base plus scope: every changed or untracked path must match the Scope list (the board-2 file included); with `PHASE=post` `git status --porcelain` must be empty.
- G14 in the new T119-T220 block (heading must contain `T119-T220`; looked up in MASTER-PLAN and in the board-2 file) no cost cell of 0 or `0/0 USD` and no blank, `-`, em dash or en dash cost cell (last table column). G15 scans for the actual self-merge authorization phrases (`self-merge`, `self-archive`, `merge on itself`, `merge and archive on itself`, `may merge`, `can merge`, `may self`, `merge token`, `merges are serialized`) in `master-planner.md` and `operating-instructions.md`, except on lines that say `superseded by D-28`; it self-tests that the old wording matches and that the A2 line `**Merge and archive (D-28):**` does not; both files must state `opens ONE draft PR`. G16 the MASTER-PLAN status sentence is corrected.

The planner-budget numbers (G1) and the size numbers (G2) go into the REPORT under heading 6 with the command and UTC time.


## Risks and mitigations

| Risk | Mitigation |
|---|---|
| MASTER-PLAN cap overrun when 100 or so IDs are added | measure after each step; trim order in B3 step 4; if still over the cap, the T119+ block moves to the board-2 file (Q5 decided); the cap is never changed and the worker does not stop for it |
| Invented data in rebuilt rows (cost, test counts, status) | B1 rules; G8, G9, G14; a reviewer samples 10 rows against the PR |
| Status inflation | merged = `review`; anything stronger needs a read evidence item named in the row |
| CRLF checkout inflates byte counts and breaks validators | measure both; the PC baseline is recorded in G3; do not "fix" line endings in this task |
| Isolated checkout has no remote, and its changes are auto-applied to the parent (`task.isolation.apply = true`, OBSERVED) | gh calls use `-R`; the worker adds `origin` from the pasted public URL and pushes its own `claude/*` branch itself; it reports that the parent now also holds the changes, so the planner never publishes them a second time; if push stays impossible, stop and report |
| Old wording found in completed plans tempts a mass edit | Section C says LEAVE with reasons; completed plans are a historical record |
| Probe findings written as universal truth | every claim tagged OBSERVED, DOCUMENTED or UNVERIFIED; `resolvedModel` stays UNVERIFIED |
| Public repo | no account names, paths with the user name, IPs, keys; G12; agent files are described, never copied |
| Worker self-merge text rewritten wrongly (new text allows a merge, or the history quote is lost) | Section A2 gives exact wording; G15 requires `opens ONE draft PR` in both files and `superseded by D-28` on every remaining legacy line; Main samples the diff of both files |
| `riper-sonnet` used for an EXECUTE (not its documented role) | owner approved this for T221 only (Q1 decided); the envelope names the agent; no other agent substitutes |

## Owner decisions (locked in, no open questions)

- **Q1 (decided):** the docs EXECUTE runs on `riper-sonnet` (owner OK given). No fallback to `riper-opus`.
- **Q2 (decided):** no decision record. The omp policy lives in `omp-setup.md` only; `decisions.md` is never edited (the stale D-6 is an owner flag, see A2).
- **Q3 (decided):** D-28 wins; the owner merges every PR. The worker self-merge text is replaced as in Section A2. This is part of this EXECUTE.
- **Q4 (decided):** spend after 21-10-26 stays `UNVERIFIED` in both files; the worker does not search for or use a later USD figure.
- **Q5 (decided):** the cap stays 19,000 B. If the T119-T220 rows do not fit with all IDs kept, the T119+ block goes into a NEW board file `process/MASTER-PLAN-board-2_<dd-mm-yy>.md` linked from MASTER-PLAN; the worker does not stop (B3 step 4).
- **Q6 (decided):** `vc-publish` is left as is and flagged only (the kit skill pushes to the kit repo; its own text at about `:298` says so). No edit.
- **Q7 (decided):** no `CLAUDE.md` or `AGENTS.md` change.
- **Q8 (decided):** `task.isolation.apply = true` (default), OBSERVED by the planner on 2026-10-29: successful isolated worker changes are auto-applied into the parent checkout as untracked or modified files, and the worker's own branch and commit do not exist there. The worker therefore commits on `claude/t221-docs-catchup-exec` in its isolated checkout and pushes it (adding `origin` from the pasted URL if none exists), and reports that its changes will also be auto-applied to the parent so the planner must not double-publish. The Windows isolation backend behaviour stays UNVERIFIED.

## Open owner questions

None. Q1-Q8 are decided above.

## Recommended EXECUTE agent

`riper-sonnet` (owner decision, Q1). Reasoning: all changes are markdown, RT0; the hard part is careful reading and byte accounting, not code reasoning; the owner rule is Opus only for real code or build. The envelope names the agent and Main spawns with that name; never spawn without naming the agent. `grok-review` may do the independent review of the EXECUTE diff (read-only tools), not the EXECUTE itself.

## Phase Completion Rules

EXECUTE is one continuous session (docs only). It ends only when: every file in the per-file edit lists is done or reported blocked, all gates G1-G16 were run and recorded, the REPORT exists, one draft PR is open. A gate that fails twice for the same reason stops the run and is reported. The worker never merges; the owner merges the PR.

## Acceptance Criteria

1. `omp-setup.md` states the probe findings with OBSERVED, DOCUMENTED or UNVERIFIED tags, the agent table, the phase-to-agent table and the rule "never spawn without naming an agent" (G7).
2. `current-state.md` has a new stamp that is an ancestor of HEAD, open PRs stated as read from `gh`, no number without a source, size within the cap (G1, G2, G11).
3. `MASTER-PLAN.md` lists every task ID and PR number since the stamp (G8, G9), statuses never stronger than `review` without a named read evidence item, cost `unmeasured` where unknown (G14), size within the cap (G1, G2).
4. Old text moved to `process/archive/` verbatim, indexed in `process/archive/index.md`.
5. G6 clean; no live doc states the old main-commit rule; `CLAUDE.md` and `AGENTS.md` untouched.
6. G3 shows no new validator failure; G4 and G5 pass or are reported as not run with the reason.
7. G15 and G16 clean: no live self-merge authorization text; the operative rule is "the owner merges every PR; a worker opens ONE draft PR and stops; the planner never merges"; the 02-10-26 quote kept as history marked superseded by D-28.
8. G1-G16 recorded in the REPORT with the exact output of the script run.


## Implementation Checklist

- [ ] Baselines recorded (`bash "$GF" before`, once; G10 and G11 inputs re-measured)
- [ ] A: `omp-setup.md` rewritten; four small edits done
- [ ] A2: owner-merges rewrite in `operating-instructions.md`, `master-planner.md` sections 5 and 10 (and the MASTER-PLAN status sentence in B3 step 7)
- [ ] B2: `current-state.md` archived and rewritten
- [ ] B3: T88-T118 block archived; T119-T220 rows built (in MASTER-PLAN, or in the board-2 file if the cap needs it); T221 row; open rows T115, T117, T118 updated; D-27 and D-28 mentioned; archive index rows added
- [ ] C: G6 clean, hits listed in the REPORT
- [ ] G1-G16 re-run (`after`, then `PHASE=post` on the committed tree), `after` results in REPORT heading 6, the `PHASE=post` result in the PR description and the final message; REPORT heading 9 lists the D-6 owner flag
- [ ] Explicit-path commit; `CLEANUP=1 bash "$GF"`; push own branch from the isolated checkout; draft PR opened with `-R`; final message states that the changes are also auto-applied to the parent


## Touchpoints

`process/context/omp-setup.md`, `process/context/current-state.md`, `process/MASTER-PLAN.md` (incl. the status sentence at ~line 20), new `process/MASTER-PLAN-board-2_<dd-mm-yy>.md` (only if the cap needs it), `process/context/context-changelog.md`, `process/context/operating-instructions.md` (worktree bullet, workers bullet ~56 and branch-deletion bullet), `process/context/all-context.md` (one word, conditional; one index row only if G3 or G4 ask), `process/development-protocols/master-planner.md` (section 7 row, section 8 sentence, section 5 rewrite, section 10 sentences), `process/archive/index.md`, two new files in `process/archive/`, the task folder. Read only, never edited: `process/context/decisions.md` (D-6 owner flag).

## Public Contracts

None changed. No API, schema, workflow, script or agent definition is touched. Guard tests that read these docs: `api/tests/tooling_guards/test_git_flow_guard.py` (five docs).

## Blast Radius

Docs only, risk RT0. Readers affected: every planner session (entry set loads `current-state.md` and `MASTER-PLAN.md`; their size counts against the 56,000 B fixed budget; `master-planner.md` and `operating-instructions.md` are read by every planner and worker, so the owner-merges rewrite changes what workers are told to do: they must stop at a draft PR) and every omp spawn that follows `omp-setup.md`. A wrong cap breaks the planner-budget gate, not the app.

## Verification Evidence

Evidence for this PLAN: values in "Verified inputs" were measured in the PLAN session with `git`, `gh`, `wc -c` and the three validators listed there; nothing was edited outside the task folder. Not verified here: anything about omp itself beyond what the owner reported (the owner probe is the source for Section A, relayed by Main), PowerShell scripts, CI state, pytest results.

## Ready-to-paste EXECUTE envelope (< 8,000 B)

Main replaces the three FILL_IN values in the VALUES block and spawns with the agent named `riper-sonnet`. `ORIGIN_URL` is the public https URL printed by `git remote get-url origin` in the main checkout (no token, no credentials; if it has any, strip them before pasting). The commands in the envelope contain no angle-bracket placeholders, so they can be pasted into a shell as they are.

````
ROLE: WORKER
You are a WORKER (agent riper-sonnet), direct lane. Do not spawn subagents. Phase: EXECUTE (docs only, RT0). You see no CLAUDE.md or AGENTS.md: the rules below are binding and complete.

VALUES (Main replaces FILL_IN; plain text, not commands). If any value still reads FILL_IN, stop and report.
REPO=FILL_IN
ORIGIN_URL=FILL_IN
DDMMYY=FILL_IN
REPO is the owner/name slug of the public GitHub repo, ORIGIN_URL its public https URL, DDMMYY today as dd-mm-yy. Paste the three lines into your shell, then run: export REPO ORIGIN_URL DDMMYY

HARD RULES
- Repo is PUBLIC: never write secrets, keys, IPs, cookies, account names, home-directory paths with a user name.
- The OWNER merges every PR (D-28). You open ONE draft PR and stop. Never merge or close PRs, never touch .github/**, never change repo settings; gh is read-only except that one draft PR. Never push to main. Only push your own claude/* branch. Never force-push.
- North-star: numbers never silently wrong; missing is never 0; Python computes everything; no verdict logic. Unknown = UNVERIFIED, cost without a report = unmeasured.
- Status vocabulary: nothing stronger than `review` without independent evidence you read yourself (a merge alone = review).
- Spend after 21-10-26 stays UNVERIFIED: do not search for or use a later USD figure.
- Do not edit CLAUDE.md, AGENTS.md, decisions.md, completed or other plans, source code, tests, scripts/pc-sync/**, .claude/**, .codex/**, .agents/**.
- Retry budget: 2 fix cycles per failing gate; same failure twice = stop and report. Unsure = stop and report.
- Do not run builds, pytest or formatters beyond the gates in the PLAN.

TASK T221-EXEC
PLAN file: process/general-plans/active/docs-catchup-omp_29-10-26/docs-catchup-omp_PLAN_29-10-26.md. Read its Sections A, A2, B, C and "Validate contract" in full; read nothing else beyond the files you edit and the sources it names. gh calls use -R "$REPO"; gh must be on PATH and authenticated.

STEPS
0. Isolation (OBSERVED: task.isolation.apply = true). When you finish, your changes are AUTO-APPLIED into the parent checkout as untracked or modified files, and your branch and commit do not exist there. So you publish yourself, from your isolated checkout. If git remote -v is empty: git remote add origin "$ORIGIN_URL". Then always: git fetch origin main. If add-remote, fetch or auth fails: stop and report exactly what failed. Then: git switch -c claude/t221-docs-catchup-exec origin/main
1. Gates script (plain shell, copy as is; the tr strips the CR of a CRLF checkout so the script is LF). Do not set BASEDIR (Main uses it):
    PLAN=process/general-plans/active/docs-catchup-omp_29-10-26/docs-catchup-omp_PLAN_29-10-26.md
    grep -q '^PLAN-REV: 4' "$PLAN" && echo PLAN-OK || echo "plan not merged yet"
   If that prints "plan not merged yet", STOP and report exactly: plan not merged yet (the PLAN in origin/main is older than revision 4; the owner must merge PR #189 first). Otherwise continue:
    GF="$(git rev-parse --git-dir)/t221-gates.sh"
    tr -d '\r' < "$PLAN" | sed -n '/^```bash$/,/^```$/p' | sed '1d;$d' > "$GF"
    bash -n "$GF"
   Baselines, once, before any edit: bash "$GF" before (G1-G5; later runs keep them). Re-measure main SHA and open PRs; re-grep Section C patterns.
2. A: rewrite process/context/omp-setup.md as Section A says (OBSERVED / DOCUMENTED / UNVERIFIED tags; phase-to-agent table; never spawn without an agent name; UNVERIFIED list). Then the small edits in the Section A table.
3. A2: apply the owner-merges wording exactly as Section A2 says to operating-instructions.md (workers and branch-deletion bullets), master-planner.md (section 5, section 10 row C and consent). The MASTER-PLAN status sentence is edited in step 4. Keep the 02-10-26 quote as history marked "superseded by D-28".
4. B: archive the old current-state.md verbatim, rewrite current-state.md; archive the T88-T118 block verbatim, rebuild rows T119-T220 from gh and git only (Section B1 rules) plus the T221 row; update open rows T115, T117, T118, Last verified, Active lanes; D-27 and D-28 mentions; fix the status-vocabulary sentence (A2 item 4); archive index rows. Caps: current-state <= 8,000 B, MASTER-PLAN <= 19,000 B (targets 7,000 and 17,500); the cap never changes. If the rows do not fit with all IDs kept, follow B3 step 4 (trim, then the new board-2 file process/MASTER-PLAN-board-2_ plus DDMMYY plus .md, linked from MASTER-PLAN); do not stop for that. Never drop a row or ID.
5. C: no other edits. G6 must be clean; list the hits you saw in the REPORT.
6. Final gates: write the stamp into current-state.md first (STAMP="$(git rev-parse origin/main)"), then run STAMP="$(git rev-parse origin/main)" bash "$GF" after. Fix, rerun (2 cycles max).
7. REPORT in the task folder: docs-catchup-omp_EXEC-REPORT_ plus DDMMYY plus .md, 11 headings: 1 Task ID, 2 Outcome (done|partial|failed), 3 Summary (<= 10 lines), 4 Files changed, 5 Commits (branch; SHAs of earlier commits only), 6 Tests run (exact command, result, UTC time, SHA: the `after` run; the PHASE=post run happens after the commit and cannot be in the file), 7 Tests NOT run (and why), 8 Deviations, 9 Blockers (risks, open questions, registry request; also this owner flag: decisions.md D-6 still says workers may self-merge, D-28 supersedes it, you did not edit it), 10 Follow-up, 11 Context cost. Then stage files by explicit path (never git add -A) and commit with a clean message.
8. Post gate: run PHASE=post STAMP="$(git rev-parse origin/main)" bash "$GF" after on the committed, clean tree (fix in a new commit and rerun, 2 cycles max). Only then run CLEANUP=1 bash "$GF" (deletes the baselines).
9. Push ONLY: git push origin claude/t221-docs-catchup-exec. Open ONE DRAFT PR with the PHASE=post result in its body: gh pr create -R "$REPO" --draft --base main --head claude/t221-docs-catchup-exec --title "docs: omp setup rewrite, state and registry catch-up T119-T220 (T221)". If push or PR creation fails: stop and report exactly what failed; never push elsewhere. Do not merge.
10. Final message: say plainly that your changes were also auto-applied to the parent checkout (untracked or modified files), that the branch and PR are already published from your isolated checkout, and that the planner must NOT commit, push or open a PR from the parent copy. Include the PHASE=post result.

STOP AND REPORT if: scope expansion, anything touching .github/, secrets, a validator that newly fails, push or auth failure, isolation failure.
````

Envelope size, measured with `wc -c` on the text between the four-backtick fences (LF): 6,500 B (cap 8,000 B). First line is exactly `ROLE: WORKER`. The extraction command of step 1 (with `tr -d '\r'`, needed on a CRLF checkout) yields a script byte-identical to the fenced block (checked with `cmp` in the revision 4 session, with `bash -n`).

## Resume and Execution Handoff

Resume: read this file's TL;DR, Scope, Section A2 and Validate contract; the REPORT in this folder lists the PLAN session's own results. Testing context: RT0 docs gates G1-G16 run after EXECUTE (post-phase testing, by the EXECUTE worker; Main re-runs them once with the "Main procedure" in the Validate contract: baselines from a clean worktree of the merge base, `PHASE=post ... after` from a clean worktree of the pushed branch, same `BASEDIR`, `ALLOW_OPEN` set to the EXECUTE PR number). Next instruction for Main: spawn EXECUTE only AFTER the owner has merged this PR (#189); the envelope stops with "plan not merged yet" if `origin/main` does not carry `PLAN-REV: 4`. All owner questions Q1-Q8 are decided (none open). Fill the three FILL_IN values in the envelope, spawn with the agent named `riper-sonnet`, and give the explicit ENTER EXECUTE MODE for T221-EXEC. Expect the worker's changes to also appear in the parent checkout through isolation auto-apply (OBSERVED setting): do not commit or publish them again. The owner merges the EXECUTE PR and reads the D-6 owner flag in the worker report.
