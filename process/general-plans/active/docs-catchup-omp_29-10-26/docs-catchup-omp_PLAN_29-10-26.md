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

## Overview

The docs fell behind main: `omp-setup.md` is still an unverified guess although the owner probed omp on 2026-10-29, and `current-state.md` and `MASTER-PLAN.md` stop at PR #144 (21-10-26) while `main` has PRs through #187. This plan makes the docs match observed facts, with `UNVERIFIED` wherever nothing was observed, and lists where old "commit on main" wording survives.

## TL;DR

1. Rewrite `process/context/omp-setup.md` from "all UNVERIFIED" to "observed on the owner PC on 2026-10-29", with a phase-to-agent table and a short UNVERIFIED list (Section A).
2. `current-state.md` and `MASTER-PLAN.md` are stamped `faf416b` (21-10-26). `main` is now `b573309f` (29-10-26): 228 non-cache commits since, 68 merge commits, PRs #145-#187 all MERGED, none open (measured in this PLAN session with `gh`). Rebuild from PR titles, PR bodies and git subjects only; every unknown field says `UNVERIFIED`, cost says `unmeasured`, never 0 (Section B).
3. No live doc still says planners commit on `main` (the T217 guard patterns and a wider regex found hits only in completed, historical plans). Section C lists each hit and what to do (mostly: leave). Two related conflicts (worker self-merge text, `vc-publish` pushing `main`) are owner decisions, not edits.
4. Caps: `current-state.md` <= 8,000 B (target 7,000), `MASTER-PLAN.md` <= 19,000 B (target 17,500). Both must shrink old text into `process/archive/` verbatim while growing new rows; the plan gives the order.
5. Recommended EXECUTE agent: `riper-sonnet` (docs only, RT0). `riper-opus` is the owner's EXECUTE-for-code agent; using it here costs more for no benefit. This needs the owner's one-line OK because `riper-sonnet` is defined for non-EXECUTE phases (Q1).

## Scope

In scope (EXECUTE may touch only these):

- `process/context/omp-setup.md` (rewrite), `process/context/current-state.md` (rewrite), `process/MASTER-PLAN.md` (edit)
- new `process/archive/current-state-archived_<dd-mm-yy>.md`, new `process/archive/master-plan-archived-rows_<dd-mm-yy>.md`, `process/archive/index.md` (index rows)
- `process/context/context-changelog.md` (one entry), `process/development-protocols/master-planner.md` (section 7 row and one sentence in section 8), `process/context/operating-instructions.md` (one sentence in the worktree bullet), `process/context/all-context.md` (workflow count, only if verified)
- the task folder `process/general-plans/active/docs-catchup-omp_<dd-mm-yy>/` for the REF copy and the REPORT

Out of scope: `CLAUDE.md`, `AGENTS.md` (owner-approval items only, Section C), `.github/**`, `.claude/**`, `.codex/**`, `.agents/**`, `scripts/pc-sync/**`, all source code and tests, completed or active plans of other tasks, `decisions.md` (unless Q2 is answered yes), user-level omp agent files outside the repo.

## Verified inputs (measured in this PLAN session, 2026-10-29)

| Fact | Value | Command |
|---|---|---|
| `main` | `b573309ff081e29676df166db7fbb6849bd48556` (merge of #186), `faf416b` is its ancestor | `git merge-base --is-ancestor faf416b HEAD` |
| Non-cache commits since stamp | 228 (68 merge commits) | `git log faf416b..HEAD --oneline -- . ':(exclude)api/data/cache' \| wc -l` |
| PRs | 186 listed (#1-#187, #175 does not exist as a PR); states only MERGED and CLOSED (closed: #5, #86); open: none | `gh pr list -R <OWNER/REPO> --state all --limit 400 --json number,state` |
| Merge dates | #145-#146 on 2026-10-21; #185 on 2026-10-29 18:52Z; #186 on 2026-10-29 19:23Z; #187 on 2026-10-29 19:22Z | `gh pr view <n> --json mergedAt` |
| Workflows | 7 files (`ci.yml` plus six nightly snapshot and refresh jobs) | `ls .github/workflows` |
| Planner budget now | `planner_fixed=47235`, cap 56,000, headroom 8,765, `rc=0` (Windows CRLF checkout) | PLANNER-BUDGET block |
| Sizes now | `MASTER-PLAN.md` 17,774 B (T88-T118 block 2,638 B; historical block 9,608 B; recovery block 3,045 B), `current-state.md` 4,222 B, `CLAUDE.md` 13,806 B, router 6,231 B | `wc -c` |
| Line endings | working tree is CRLF (`core.autocrlf=true`); the index is LF. Every `wc -c` on the PC is larger than on Linux by one byte per line (`MASTER-PLAN.md` 132 lines) | `git ls-files --eol <file>` |
| Validator baseline on this PC | `validate-context-discovery.mjs`: 54 failures, 11 warnings, almost all "missing name/description frontmatter" and backslash-path "not indexed" lines [INFERENCE: CRLF and Windows path separators; the cloud baseline was 1 failure]; `validate-all-context.mjs`: `failures: []` | the two scripts |
| Isolated checkout of this worker | detached HEAD at `main`, no git remote configured (`git remote -v` empty, `origin/*` refs present), `gh` needs `-R` | `git remote -v` |

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
   | EXECUTE of a docs-only (RT0) slice | `riper-sonnet` if the owner confirms (Q1); the owner rule is that Opus is for real code and build |
   | Independent read-only review | `riper-sonnet` or `grok-review` (`grok-review` never writes) |
   | Anything else, or no agent name | not allowed |

5. **What omp does not load (OBSERVED unless noted).**
   - `.claude/agents` and `.codex/agents` are skipped by omp agent discovery (DOCUMENTED); their `model:` pins are inert. `vc-*` agents are not usable as omp agents.
   - Children do not see `CLAUDE.md` or `AGENTS.md` (all four probes saw none). An envelope must carry the role line and the hard rules inline. The 8,000-byte envelope cap stays a repo rule (master-planner.md section 8).
   - `vc-*` skills are listed in a child's context (OBSERVED in the T221 PLAN session, not by the owner probe). Whether they trigger is UNVERIFIED.
6. **Plan mode (DOCUMENTED, not tested).** omp plan mode uses the PLAN role (Opus 5.5 for the owner); `--plan-yolo` executes on the smol role (Haiku). Rule: never use omp plan mode or `--plan-yolo` for RIPER phases or EXECUTE.
7. **Workers and isolation.**
   - Local workers are subagents or separate sessions on the owner PC, not cloud containers: same disk, same credentials; isolation is an isolated checkout or worktree plus a `claude/*` branch. Cloud behaviours (egress block, proxy) do not apply, do not assume them either way.
   - `task.isolation.enabled=true` is saved in the owner config (OBSERVED); `isolated: true` gives a separate checkout; not available in omp plan mode (DOCUMENTED). Whether the results are applied back depends on `task.isolation.apply` (UNVERIFIED value).
   - Observed in the T221 PLAN session: the isolated checkout has a detached HEAD, no git remote configured, and `gh` needs `-R <OWNER/REPO>`. Push behaviour from such a checkout: see the T221 REPORT (UNVERIFIED as a general rule).
8. **Git flow (keep, D-28).** Existing section unchanged in substance: PC pushes `claude/*` branches and opens DRAFT PRs, never pushes `main`, owner merges every PR; `sync-main.ps1` and `push-task-branch.ps1`; ruleset with github-actions[bot] bypass; secrets stay outside the repo.
9. **UNVERIFIED list (final section):** the `resolvedModel` field of each agent; the Windows isolation backend behaviour; the PowerShell scripts in `scripts/pc-sync` (never run; the owner runs `-WhatIf`); ruleset Evaluate mode on a public free repo; `task.isolation.apply` value; whether `vc-*` skills trigger; plan mode and `--plan-yolo` behaviour.

Remove the old "Mapping (UNVERIFIED)" table (its four rows are answered or replaced above: agents, skills, model roles, `AGENTS.md`).

Other edit lists for deliverable A:

| File | Edit |
|---|---|
| `process/development-protocols/master-planner.md` section 7 table (about line 89-92) | add row: `Owner PC, omp` / isolated checkout or git worktree plus `claude/<task-id>-<slug>` branch / "not a cloud container; see omp-setup.md". Section 8 (envelope template): add one sentence "omp children do not load CLAUDE.md or AGENTS.md; put role and hard rules in the envelope; name the agent in every spawn". |
| `process/context/operating-instructions.md` worktree bullet (about line 57) | add one sentence: on the owner PC omp may create isolated checkouts when `task.isolation.enabled` is on; they follow the same branch and PR rules; see omp-setup.md. Re-read the bullet first; do not touch the adjacent self-merge text (Q3). |
| `process/context/all-context.md` line about "ci.yml plus five nightly" (about line 126, below the router part) | verify with `ls .github/workflows`; if there are six nightly files, change "five" to "six". Router row for omp-setup (line 91) already exists: no change. Skip this edit if `validate-all-context.mjs` fails after it. |
| `process/context/context-changelog.md` | one dated entry (29-10-26): omp-setup rewritten from the probe, current-state and MASTER-PLAN caught up to #187. Follow the file's existing entry format (read the last entries first). |

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
3. Observed table (command column for every row): last code merges (#185, #186, #187 and their dates), open PRs `none` (state the gh command and date), workflows 7 (names), scheduled refresh evidence (re-run the `git log` for the attention refresh dates), frozen signal snapshots count (re-run), CI state of `ci.yml` on main (from `gh run list`; if not read: UNVERIFIED), `.agents/skills` row (keep only if still true).
4. Tests: copy only numbers found in merged PR bodies or reports, each with the PR number and "worker report, not re-run"; otherwise "UNVERIFIED".
5. Validator results: re-run the validators (Section Validate), state the PC result with the CRLF caveat; the cloud baseline of 1 failure is history.
6. "What runs": one short paragraph each: screener and equities; Baskets; Discovery and weighted signal (weights v2, PR #156; CoinGecko volume coverage only, PR #183); universe and narratives U1 to U6 merged (D-27: exchange tokens are IN as a narrative, supersedes D-20; PR #160); Trends T100a, T100b, T100c and later work merged (PR list from the map above); W8 slices merged: W8a vetting (#158, #169), W8b (#161), W8c Reddit (#185), W8d1 X core (#173), W8d2 X reader (#186); docs and process PRs merged (#147, #168, #187 and others); git flow D-28 and `scripts/pc-sync/` merged, never run (UNVERIFIED); omp setup: `omp-setup.md`.
7. Planner and worker spend: state the last figure that already exists in the repo with its date ("about 188 of the 200 USD ceiling, planner figures, 21-10-26") and add: "no later figure is recorded in the files read; UNVERIFIED". Search PR bodies and reports for later USD figures first (`gh pr list ... --json body` then grep "USD"); use a later figure only if one is found, with its source (Q4).
8. "Not run or unverified": carry the 13-10-26 owner probes list and mark each `UNVERIFIED (no newer evidence read)`; Reddit API request of 18-10-26 and X: state that W8c and W8d2 code merged and that access or enablement status is UNVERIFIED; weighted-signal calibration checks 2027-01-18 and 2027-04-18 (still future); independent review: T96-T107 and part of T113 and T114 merged before it (D-26), plus whatever the T117 report states.
9. Next actions: no invented work. Write: (1) owner decides the open questions in the T221 REPORT; (2) re-verify state at the next planner session; (3) the owner probes. A "queued" list only if a registry row says so.
10. Decision pointer: "decisions D-22..D-28 in decisions.md".

### B3. `process/MASTER-PLAN.md` (edit, <= 19,000 B, target <= 17,500 B)

Order of work (the byte arithmetic is the main risk: +about 3,500-5,000 B of new rows against a 1,226 B room under the ceiling, 0 under the target):

1. Archive file: create `process/archive/master-plan-archived-rows_<dd-mm-yy>.md` (shape of `master-plan-archived-rows_21-10-26.md`: frontmatter, "moved verbatim, nothing deleted"). Move into it verbatim the current "Weighted signal and universe tasks (T88-T118, compact rows)" table (2,638 B). Rule from master-planner.md section 12: IDs stay on the board, so the board keeps a compact replacement with every ID listed (for example "T96, T101-T107: review, PRs #133-#140 ..."), not a bare range.
2. Update the three open rows before moving: T115 (merged #146), T117 (state from its report, else UNVERIFIED), T118 (merged #147). Update `Last verified` (date, new SHA, "PRs checked with `gh pr list --state all`"), `Active lanes` (no open PRs; lane state UNVERIFIED beyond that; P10 slices U3, U5, U6 merged; P9 and P8 states `UNVERIFIED` unless a read file says otherwise), `built from` stays revision 6 plus the T118 reconciliation.
3. New compact block "Weighted signal, universe, Trends, W8 and docs (T119-T220)": columns `ID · What · Status · PR / evidence · Cost`. One row per ID that is a PR title ID (list in B1) plus one grouped row for the 31 git-subject-only IDs, each ID spelled out so the coverage gate below can find it. `What` is the PR title abbreviated, not interpreted. Status `review` for merged PRs; Cost `unmeasured`. Rows for the same program may share a line only if every ID and PR number is present.
4. Measure. If over 17,500 B (target) but under 19,000 B (cap): stop adding and go to step 5 only when over the cap. If over the cap, apply the trim rule of master-planner.md section 12 in this order: (a) recovery-program (R) evidence cells to at most 300 B with the report path, moving the longer text verbatim to the archive file; (b) historical T-rows whose status is already `archived` or `accepted` and whose evidence cell is over 300 B: shorten the cell, move the long text verbatim; (c) `Carried notes` and `Active lanes` wording. Do not drop a row or an ID. If the cap still cannot be met without dropping IDs: stop and report (Q5), do not edit the cap.
5. `process/archive/index.md`: one row for each new archive file, same columns as existing rows; add an Approvals Log row only if the log's own rule requires it (read its first lines); the owner merging the EXECUTE PR is the approval and the row says so.
6. Mention D-27 and D-28 in the registry text where the rows apply (T146 row: D-27; T217 row: D-28). Mention that planner and worker spend after 21-10-26 is `UNVERIFIED` in the `Active lanes` paragraph.

Cost of the current-state and MASTER-PLAN together after the edit must keep `planner_fixed <= 56,000` (now 47,235; room 8,765 B for both files plus the other fixed files).

## C. Wording: planners commit on `main`

Search used: the five T217 guard regexes over the five guarded docs, plus a repo-wide regex for "commit ... on|to main" and "push ... to main" (searched `CLAUDE.md`, `AGENTS.md`, `README.md`, `process/`, `.claude/`, `.codex/`, `.agents/`, `scripts/`).

**Live docs: no stale rule remains.** Already D-28-conformant (no edit): `CLAUDE.md:43` and `:131`, `AGENTS.md:51`, `process/development-protocols/implementation-standards.md:64-67`, `process/development-protocols/master-planner.md:83`, `process/context/operating-instructions.md:10` and `:55`, `process/context/omp-setup.md:15-16`, `scripts/pc-sync/README.md:3`, `process/context/decisions.md:242-245`. The guard `api/tests/tooling_guards/test_git_flow_guard.py` pins these five docs.

Remaining old wording, with decision (line numbers from the 29-10-26 tree; EXECUTE re-greps first):

| File and line | Text (short) | Decision |
|---|---|---|
| `process/general-plans/completed/master-planner-recovery_02-10-26/master-planner-recovery_PLAN_02-10-26.md:369`, `:534`, `:774`, `:1447` | "commit directly on `main` per policy", "commit on `main` only when you ask", "repo policy (commit directly on `main` only on request)", cosmetic-gap note "commit on `main` by default" | LEAVE. Completed plan, historical record; D-28 "Consequences" already says it supersedes the old rule. |
| `process/general-plans/completed/master-planner-recovery_02-10-26/master-planner-recovery_GATE3-REVIEW_REF_03-10-26.md:72`, `:137` | verbatim copy of the old entry block line and a check list naming it | LEAVE (verbatim snapshot). |
| `process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness_PLAN_28-09-26.md:195` | "commit directly on the current branch; do not touch `main`" | LEAVE (already consistent with D-28). |
| `process/general-plans/active/screener-batch4_10-10-26/screener-batch4_PLAN_10-10-26.md:382` | "REF files are committed on main before the spawn" | LEAVE (old flow, historical plan). |
| nightly-cron wording (deployability SPEC `:195`, `:332`; pipeline-completeness PLAN `:116`, `:274`; SPEC `:248`; `.github` job descriptions) | workflows commit to `main` | LEAVE; correct under D-28 (bot exception). |
| `.claude/skills/vc-publish/SKILL.md:291`, `:294` and the same lines in `.agents/skills/vc-publish/SKILL.md` | `git push origin main && git push --tags` | OWNER QUESTION Q6. Kit skill, not a repo doc; do not edit in this task. |
| `process/context/operating-instructions.md:56` and `process/development-protocols/master-planner.md` sections 5 and 10 | worker self-merge standing authorization (02-10-26) versus D-28 "owner merges every PR" | OWNER QUESTION Q3. Not an edit in this task. |

Result: **no edit is planned for deliverable C**; the action is the explicit list above plus the grep gate G6 (proves no live-doc regression). If the owner answers Q3 or Q6 with an edit, that is a new task.

`CLAUDE.md` and `AGENTS.md` (owner-approval items; their diffs stop at review, nothing planned here): (i) optionally one line in the entry block that omp children do not load them, so envelopes carry rules inline (the omp-setup note covers it for now); (ii) nothing else is needed for D-28.

## Validate contract (EXECUTE must run these; all from the repo root in Git Bash)

Before any edit, record baselines; run the same commands after. Paths below use `<dd-mm-yy>` as the EXECUTE date. `<OWNER/REPO>` is filled in by Main when it dispatches (not written into repo files).

| # | Gate | Command | Pass |
|---|---|---|---|
| G1 | planner budget | `sed -n '/^# PLANNER-BUDGET:BEGIN/,/^# PLANNER-BUDGET:END/p' process/development-protocols/master-planner.md > pb.tmp.sh && bash pb.tmp.sh; rm -f pb.tmp.sh` | no `OVER-CAP`, no `MISSING`, `rc=0` (measured on the CRLF checkout, the stricter count) |
| G2 | sizes | `wc -c process/context/current-state.md process/MASTER-PLAN.md process/context/omp-setup.md` and `for f in process/context/current-state.md process/MASTER-PLAN.md; do git show :$f \| wc -c; done` (LF size of the index copy after `git add`) | current-state <= 8,000 (target 7,000); MASTER-PLAN <= 19,000 (target 17,500); omp-setup <= 7,000 (target) |
| G3 | context discovery, no new failures | `node .claude/skills/vc-audit-context/scripts/validate-context-discovery.mjs > vcd.before.json` before editing, `... > vcd.after.json` after, then `node -e "const f=require('fs');const b=JSON.parse(f.readFileSync('vcd.before.json','utf8')).failures,a=JSON.parse(f.readFileSync('vcd.after.json','utf8')).failures;const n=a.filter(x=>!b.includes(x));console.log('new failures',n.length);n.forEach(x=>console.log(x));process.exit(n.length?1:0)"`; then `rm vcd.before.json vcd.after.json` | `new failures 0`. Baseline on the PC is 54 failures and 11 warnings (CRLF and path-separator artefacts); do not try to fix them here |
| G4 | all-context | `node .claude/skills/vc-generate-context/scripts/validate-all-context.mjs` | `"failures": []` (the "N days old" warning is acceptable) |
| G5 | doc guard tests | `uv run --project api pytest api/tests/tooling_guards -q` | all pass (includes `test_git_flow_guard.py`: entry block identity, no old rule, new policy stated). If `uv` is not available on the machine: report as not run, do not substitute |
| G6 | no old main-commit rule in live docs | `grep -nEi "commit\w*\s+(only when the user asks,\s+)?directly on \`main\`\|commit on \`main\` by default\|commit on \`main\`,? only when\|everyone else commits on \`main\`\|direct user work commit on \`main\`" CLAUDE.md AGENTS.md process/development-protocols/implementation-standards.md process/development-protocols/master-planner.md process/context/operating-instructions.md process/context/omp-setup.md process/context/current-state.md process/MASTER-PLAN.md` | no output |
| G7 | omp-setup content | `grep -c "UNVERIFIED" process/context/omp-setup.md` (>= 6) and `grep -Ec "riper-sonnet\|riper-opus\|grok-review\|xai-oauth/grok-4.7\|never spawn without naming an agent\|task.isolation" process/context/omp-setup.md` (>= 8) and `grep -n "Mapping (UNVERIFIED)" process/context/omp-setup.md` (no output) | as stated |
| G8 | every task ID since the stamp is on the board | `git log faf416b..HEAD --format=%s -- . ':(exclude)api/data/cache' \| grep -oE '\bT[0-9]{2,3}[a-z]?[0-9]?\b' \| sort -u \| while read id; do grep -qw "$id" process/MASTER-PLAN.md \|\| echo "MISSING $id"; done` | no `MISSING` line (IDs are spelled out in the grouped rows; the stamp `faf416b` is the old stamp on purpose) |
| G9 | every PR number is on the board | `for n in $(seq 145 187); do [ $n -eq 175 ] && continue; grep -q "#$n\b" process/MASTER-PLAN.md \|\| echo "MISSING #$n"; done` | no `MISSING` line |
| G10 | PR state still true | `gh pr list -R <OWNER/REPO> --state open --json number,title` | `[]`; if not empty, current-state and MASTER-PLAN must list the open PR instead of "none" |
| G11 | new stamp valid | `git merge-base --is-ancestor <new stamp> HEAD && git log <new stamp>..HEAD --oneline -- . ':(exclude)api/data/cache' \| wc -l` | ancestor true; count <= 10 |
| G12 | no secrets or accounts in changed files | `git diff --name-only <base>..HEAD \| xargs grep -nEi "(token\|secret\|password\|cookie)\s*[=:]\s*\S{8,}\|\b[0-9]{1,3}(\.[0-9]{1,3}){3}\b\|C:\\\\Users"` (also eyeball for the owner's account and user names) | no output |
| G13 | whitespace and scope | `git diff --check` and `git diff --name-only origin/main...HEAD` (or `<base>..HEAD`) | `--check` clean; every listed file is in the Scope list above |
| G14 | no zero for missing | `grep -nE "\| (0\|0\.0\|0\.00) \|$" process/MASTER-PLAN.md` on the new block only | no new row with cost 0 unless a report states 0 |

The planner-budget numbers (G1) and the size numbers (G2) go into the REPORT under heading 6 with the command and UTC time. Validate on the CRLF working tree is the stricter case; the LF size is reported next to it.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| MASTER-PLAN cap overrun when 100 or so IDs are added | measure after each step; trim order in B3 step 4; stop and report rather than raise the cap (Q5) |
| Invented data in rebuilt rows (cost, test counts, status) | B1 rules; G8, G9, G14; a reviewer samples 10 rows against the PR |
| Status inflation | merged = `review`; anything stronger needs a read evidence item named in the row |
| CRLF checkout inflates byte counts and breaks validators | measure both; the PC baseline is recorded in G3; do not "fix" line endings in this task |
| Isolated checkout has no remote | gh calls use `-R`; if push is blocked in the isolated child, stop and report as in the T221 REPORT; never push elsewhere |
| Old wording found in completed plans tempts a mass edit | Section C says LEAVE with reasons; completed plans are a historical record |
| Probe findings written as universal truth | every claim tagged OBSERVED, DOCUMENTED or UNVERIFIED; `resolvedModel` stays UNVERIFIED |
| Public repo | no account names, paths with the user name, IPs, keys; G12; agent files are described, never copied |
| `riper-sonnet` used for an EXECUTE (not its documented role) | needs Q1 answered; otherwise use `riper-opus` and accept the cost |

## Open owner questions

- **Q1.** May a docs-only (RT0) EXECUTE run on `riper-sonnet`? Recommended yes: no code, no build, cheaper, and D-26 says Opus for code slices, Sonnet otherwise. If no: `riper-opus`, same envelope.
- **Q2.** Record the omp agent policy as a decision (D-29: user-level agents `riper-sonnet`, `riper-opus`, `grok-review`; never spawn without an agent name)? Default in this plan: no, it lives in `omp-setup.md` only.
- **Q3.** `operating-instructions.md:56` and master-planner.md sections 5 and 10 still describe worker self-merge (02-10-26 standing authorization); D-28 says the owner merges every PR. Which wins? Needs a separate task.
- **Q4.** Where is the worker and planner USD spend after 21-10-26 recorded (if anywhere)? Until then it stays `UNVERIFIED` in both files.
- **Q5.** If the IDs T119-T220 cannot fit under the 19,000 B cap with IDs retained, may the cap move, or should the T119+ block live in a new board file linked from MASTER-PLAN? (Protocol change; owner decision; not part of this EXECUTE.)
- **Q6.** `vc-publish` skill pushes `main` (kit remote). Leave as is, or change in a kit task? Not touched here.
- **Q7.** `CLAUDE.md` and `AGENTS.md`: add one line about children not loading them? Owner-approval item; diff stops at review.
- **Q8.** `task.isolation.apply` value and the Windows isolation behaviour: the owner to read the setting and run one isolated test (also settles the no-remote observation).

## Recommended EXECUTE agent

`riper-sonnet`, with Q1 answered yes. Reasoning: all changes are markdown, RT0; the hard part is careful reading and byte accounting, not code reasoning; the owner rule is Opus only for real code or build. If Q1 is no, use `riper-opus`. Never spawn without naming the agent. `grok-review` may do the independent review of the EXECUTE diff (read-only tools), not the EXECUTE itself.

## Phase Completion Rules

EXECUTE is one continuous session (docs only). It ends only when: every file in the per-file edit lists is done or reported blocked, all gates G1-G14 were run and recorded, the REPORT exists, one draft PR is open. A gate that fails twice for the same reason stops the run and is reported. No merge by the worker.

## Acceptance Criteria

1. `omp-setup.md` states the probe findings with OBSERVED, DOCUMENTED or UNVERIFIED tags, the agent table, the phase-to-agent table and the rule "never spawn without naming an agent" (G7).
2. `current-state.md` has a new stamp that is an ancestor of HEAD, open PRs stated as read from `gh`, no number without a source, size within the cap (G1, G2, G11).
3. `MASTER-PLAN.md` lists every task ID and PR number since the stamp (G8, G9), statuses never stronger than `review` without a named read evidence item, cost `unmeasured` where unknown (G14), size within the cap (G1, G2).
4. Old text moved to `process/archive/` verbatim, indexed in `process/archive/index.md`.
5. G6 clean; no live doc states the old main-commit rule; `CLAUDE.md` and `AGENTS.md` untouched.
6. G3 shows no new validator failure; G4 and G5 pass or are reported as not run with the reason.

## Implementation Checklist

- [ ] Baselines recorded (G1-G4, G10)
- [ ] A: `omp-setup.md` rewritten; four small edits done
- [ ] B2: `current-state.md` archived and rewritten
- [ ] B3: T88-T118 block archived; T119-T220 rows built; open rows T115, T117, T118 updated; D-27 and D-28 mentioned; archive index rows added
- [ ] C: G6 clean, hits listed in the REPORT
- [ ] G1-G14 re-run, results in REPORT heading 6
- [ ] Scratch files removed; explicit-path commit; draft PR opened

## Touchpoints

`process/context/omp-setup.md`, `process/context/current-state.md`, `process/MASTER-PLAN.md`, `process/context/context-changelog.md`, `process/context/operating-instructions.md`, `process/context/all-context.md` (one word, conditional), `process/development-protocols/master-planner.md` (one row, one sentence), `process/archive/index.md`, two new files in `process/archive/`, the task folder.

## Public Contracts

None changed. No API, schema, workflow, script or agent definition is touched. Guard tests that read these docs: `api/tests/tooling_guards/test_git_flow_guard.py` (five docs).

## Blast Radius

Docs only, risk RT0. Readers affected: every planner session (entry set loads `current-state.md` and `MASTER-PLAN.md`; their size counts against the 56,000 B fixed budget) and every omp spawn that follows `omp-setup.md`. A wrong cap breaks the planner-budget gate, not the app.

## Verification Evidence

Evidence for this PLAN: values in "Verified inputs" were measured in the PLAN session with `git`, `gh`, `wc -c` and the three validators listed there; nothing was edited outside the task folder. Not verified here: anything about omp itself beyond what the owner reported (the owner probe is the source for Section A, relayed by Main), PowerShell scripts, CI state, pytest results.

## Ready-to-paste EXECUTE envelope (< 8,000 B)

Main fills `<OWNER/REPO>` and `<dd-mm-yy>` and names the agent in the spawn.

````
ROLE: WORKER
You are a WORKER, direct lane. Do not spawn subagents. Phase: EXECUTE (docs only, RT0). You see no CLAUDE.md or AGENTS.md: the rules below are binding and complete.

HARD RULES
- Repo is PUBLIC: never write secrets, keys, IPs, cookies, account names, home-directory paths with a user name.
- Never merge or close PRs, never touch .github/**, never change repo settings, gh is read-only except one draft PR. Never push to main. Only push your own claude/* branch. Never force-push.
- North-star: numbers never silently wrong; missing is never 0; Python computes everything; no verdict logic. Unknown = UNVERIFIED, cost without a report = unmeasured.
- Status vocabulary: nothing stronger than `review` without independent evidence you read yourself (merged PR alone = review).
- Do not edit CLAUDE.md, AGENTS.md, decisions.md, completed or other plans, source code, tests, scripts/pc-sync/**, .claude/**, .codex/**, .agents/**.
- Retry budget: 2 fix cycles per failing gate; same failure twice = stop and report. Unsure = stop and report.
- Do not run builds, pytest or formatters beyond the gates listed here.

TASK T221-EXEC
Follow the PLAN: process/general-plans/active/docs-catchup-omp_29-10-26/docs-catchup-omp_PLAN_29-10-26.md. Read its Sections A, B, C and "Validate contract" in full; read nothing else beyond the files you edit and the sources it names. Branch: claude/t221-docs-catchup-exec from origin/main. gh calls use `-R <OWNER/REPO>` (your checkout may have no remote; if it has none and push is impossible, stop and report exactly what failed, do not push elsewhere).

STEPS
1. Record baselines: G1, G2, G3 (vcd.before.json), G4. Re-measure main SHA, open PRs (G10), and re-grep Section C patterns.
2. A: rewrite process/context/omp-setup.md as the PLAN Section A says (OBSERVED / DOCUMENTED / UNVERIFIED tags; phase-to-agent table; never spawn without an agent name; UNVERIFIED list). Then the four small edits in the Section A table (master-planner.md section 7 row and section 8 sentence, operating-instructions.md worktree bullet, all-context.md workflow count if verified, context-changelog.md entry).
3. B: archive the old current-state.md verbatim, rewrite current-state.md; archive the T88-T118 block verbatim, rebuild MASTER-PLAN rows T119-T220 from gh and git only (Section B1 rules), update the open rows T115, T117, T118, Last verified, Active lanes; add D-27 and D-28 mentions; record that W8a, W8b, W8c, W8d1, W8d2, Trends T100a-c and T149-T204, and the docs PRs are merged. Add archive index rows. Respect caps: current-state <= 8,000 B, MASTER-PLAN <= 19,000 B; target 7,000 and 17,500. Never drop a row or ID; if the cap cannot be met, stop and report.
4. C: no edits planned. Confirm the grep (G6) is clean and list the hits you saw in the REPORT.
5. Run G1-G14 after the edits. Remove scratch files (vcd.*.json, pb.tmp.sh). Stage files by explicit path, never `git add -A`.
6. Write the REPORT in the task folder: docs-catchup-omp_EXEC-REPORT_<dd-mm-yy>.md with the 11 headings: 1 Task ID, 2 Outcome (done|partial|failed), 3 Summary (<= 10 lines), 4 Files changed, 5 Commits (SHAs, branch), 6 Tests run (exact command, result, UTC time, SHA), 7 Tests NOT run (and why), 8 Deviations, 9 Blockers (risks, open questions, registry request), 10 Follow-up, 11 Context cost (files loaded, tokens, tools available).
7. Commit with a clean message, push claude/t221-docs-catchup-exec, open ONE DRAFT PR titled "docs: omp setup rewrite, state and registry catch-up T119-T220 (T221)". Do not merge.

STOP AND REPORT if: scope expansion, anything touching .github/, secrets, a cap that cannot be met, a validator that newly fails, push or isolation failure.
````

Envelope size measured in the PLAN session: 3,695 B (cap 8,000 B); first line is exactly `ROLE: WORKER`.

## Resume and Execution Handoff

Resume: read this file's TL;DR, Scope and Validate contract; the REPORT in this folder lists the PLAN session's own results. Testing context: RT0 docs gates G1-G14 run after EXECUTE (post-phase testing, by the EXECUTE worker; Main re-runs them once). Next instruction for Main: get the owner's answers to Q1 (agent for EXECUTE) and, if wanted, Q2, then paste the envelope above (fill the two placeholders, name the agent in the spawn) and give the explicit ENTER EXECUTE MODE for T221-EXEC.
