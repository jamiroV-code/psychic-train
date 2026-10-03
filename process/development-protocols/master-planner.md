---
name: protocol:master-planner
description: "Master Planner posture and worker protocol: task lifecycle, acceptance rule, standing authorization, worker envelope and 11-heading report templates, isolation, the four archive operations, branch-deletion consent, session start and end."
date: 02-10-26
metadata:
  node_type: protocol
  type: protocol
  read_order: 10
  required: false
  read_when: "Master Planner posture or worker spawn"
---

# Master Planner Protocol

**The Master Planner plans, registers, dispatches, monitors and accepts; it never implements. Workers execute one registry task each on their own branch. A task becomes `accepted` only on independent evidence, never on a worker's word.** Registry: `process/MASTER-PLAN.md`. Source plan: `process/general-plans/active/master-planner-recovery_02-10-26/master-planner-recovery_PLAN_02-10-26.md` (section 4). Decisions: decisions.md (D-5 to D-8).

## 1. Roles and entry sets

| Role | Who | Loads by default | Cap (bytes, provisional) |
|---|---|---|---|
| PLANNER | the Master Planner session, or a user-opened interactive session | CLAUDE.md, north-star.md, current-state.md, `process/MASTER-PLAN.md`, the router section of `process/context/all-context.md` (top through the line before `## Context Group Lifecycle`), the task brief | 64,000 |
| WORKER | a spawned session whose first message starts with `ROLE: WORKER` | CLAUDE.md, the task envelope, the task PLAN or SPEC it names; operating-instructions.md only when the envelope names it | 36,000 (43,000 with operating-instructions.md) |

On demand only: this file, architecture.md, operating-instructions.md, `orchestration.md`, context-changelog.md, other protocols. A spawned session does not inherit the planner's context; it loads CLAUDE.md by itself, so its envelope must state its role.

## 2. Master Planner posture (orchestrator rules)

These rules apply to a session in planner or orchestrator posture. They do not apply to a WORKER.

- **Detect, route, pass context, monitor.** Route each request to the matching RIPER-5 agent; pass the exact plan path and the context router; check the agent stays in its phase.
- **Delegate, do not do the phase work.** A session in orchestrator posture never researches, brainstorms, plans, implements or updates rules itself; it delegates to `vc-research-agent`, `vc-spec-agent`, `vc-innovate-agent`, `vc-plan-agent`, `vc-validate-agent`, `vc-execute-agent` and `vc-update-process-agent`. The one exception: a trivial question that needs no mode-specific work (for example "What is RIPER-5?") may be answered directly. (Moved here from CLAUDE.md and AGENTS.md at Gate 3.)
- **Execute-agent preflight.** Before spawning `vc-execute-agent`, confirm exactly one plan file is selected and pass its path explicitly in the prompt. If several plans exist under `process/general-plans/active/` or `process/features/*/active/`, ask the user which one. Never let the execute agent infer the plan from ambient state. (Moved here from CLAUDE.md and AGENTS.md at Gate 3.)
- **No inline execution.** In planner posture the session never edits source files and never runs validate-contract gate commands itself; EXECUTE is a spawned `vc-execute-agent`, EVL confirmation is a spawned `vc-tester`.
- **Strategy at every transition.** Invoke `vc-agent-strategy-compare` for the next phase (sequential, parallel subagents, workflow, agent team). An agent team means TeamCreate + TaskCreate/TaskUpdate + SendMessage, not uncoordinated parallel calls.
- **Model policy.** EXECUTE agents run on opus; every other phase on sonnet.
- **/goal block** after every VALIDATE; PVL and EVL loop rules, intent routing and the QUICK FIX lane: `orchestration.md`.
- **Only this session spawns and archives sessions** (`create_session`, `archive_session`, `send_message`, `list_sessions`, `list_events`, `set_session_tags`, `subscribe_pr_activity`, `get_session`, `interrupt_session`; GitHub merge tools). vc-* subagents do not see these tools. Names and behaviour are re-checked at Gate 2 step R4 (vii).
- **One registry writer.** Only the Master Planner edits the registry and current-state.md.

## 3. Task lifecycle

```
proposed -> approved (user) -> queued (deps met, lane free) -> in_progress (worker spawned)
in_progress -> review (worker report received) -> accepted (independent evidence) -> archived
in_progress|review -> failed (retry budget exhausted) | blocked (named blocker) | needs_input (user question)
any pre-accepted state -> cancelled (user or planner, with reason)
review -> in_progress (acceptance rejected, with reasons; counts against the retry budget)
```

`approved` on a registry row is standing EXECUTE consent for that task only.

**Decomposition:** one task = one objective, one acceptance statement, about 15 files or one blast-radius area, one branch. Split when files cross `api/` and `web/` ownership, when a schema or contract change is involved (own task, lands first), or when acceptance needs a user decision (separate `needs_input` task). No task starts with an unmet dependency.

## 4. Acceptance rule (hard)

`accepted` requires ALL of:

- (a) the report has all 11 headings (section 9);
- (b) the task's required tests were re-run by a party other than the implementer (a spawned vc-tester, the user, or CI on the head SHA) and recorded with command and timestamp;
- (c) the changed-file list matches the task's declared ownership;
- (d) for user-visible behaviour, user acceptance or a recorded agent-probe.

A worker saying "done" yields `review` only. Missing tier evidence keeps the task at `review` and is recorded as a gap; a known gap is never a pass. A merged task that still needs (d) stays `review` after the merge until that evidence exists.

## 5. Standing authorization (user, 02-10-26)

User's words: "it spawns workers for tasks you already marked approved, without asking again (max 3 sessions at the same time excl. master planner session), each session can merge and archive on itself automatically if it's sure it's ready and safe to merge".

1. **Spawn:** the Master Planner may spawn a worker for any `approved` task without asking again. Max 3 concurrent workers, excluding the planner.
2. **Self-merge and self-archive** only when ALL hold: (a) CI green on the head commit (both `ci.yml` jobs `success`; pending, skipped or neutral is not green); (b) the risk-tier tests passed and were independently re-run or confirmed by CI; (c) the diff touches only declared files; (d) no merge conflicts; (e) the completion report is committed; (f) the Master Planner has recorded `accepted` then `archived` with commit refs (the worker requests it in report headings 9 and 10). (g) the diff touches neither CLAUDE.md nor AGENTS.md: such a diff stops at `review` for the user's diff check (user 03-10-26).
3. **No class exception** (user, "no exceptions"): high-risk classes may self-merge when every condition holds.
4. **Fail-safes:** an unsure worker stops at `review`; every condition must be evidenced; a denied or permission-prompting merge or archive call means stop at `review`, never retry around it.
5. **Verifiability:** behaviour visible only on the user's PC (Windows PowerShell scripts at runtime, Task Scheduler, Tailscale, the live app) cannot be evidenced from the cloud, so such a task stops at `review` and the user verifies.
6. **Merges are serialized:** the branch must contain the current `origin/main` tip with CI re-run; one self-merge at a time (the planner holds the merge token in the registry `Worker/session` column).
7. **Post-merge check:** after each self-merge the Master Planner checks CI on the merge SHA on `main`; on red it proposes `git revert <merge sha>` and halts further self-merges until the user responds.
8. **Decided 03-10-26 (Open Question 10):** a worker may self-merge anything inside its owned files except a diff touching CLAUDE.md or AGENTS.md (stops at `review`, see (g)); direct worker lane (Open Question 12): keep as is. Still open: RT4 bypass of user acceptance.

Nothing above is platform-enforced (private repo, no branch protection, `allow_auto_merge` false): every control is procedure.

## 6. Worker lane and commit policy

- A WORKER is a direct-lane session: it does not orchestrate, spawn sessions or run the multi-agent RIPER chain. Tiny tasks (RT0 or RT1, about 100 lines or less, no schema, auth, API, billing or migration surface) use the QUICK FIX lane; one `vc-quick-fix-agent` spawn is not a subagent chain. Every other worker writes a compact validate-contract in its own task folder (the gate list from the envelope) before editing, then edits and runs its gates.
- Workers commit on `claude/<task-id>-<slug>` and open a PR. The Master Planner session and direct user work commit on `main`, only when the user asks.
- Retry budget: see "Bounded retry" in operating-instructions.md (single home: 2 fix cycles per failing gate, same failure twice stops, 10-cycle outer ceiling).

## 7. Isolation

| Environment | Unit | Mechanism |
|---|---|---|
| Cloud | one session = one container + one branch | `create_session(prompt, branch)`; branch `claude/<task-id>-<slug>` |
| User's PC | git worktree | user-driven; the planner records the path but cannot create or remove it |

Each lane lists owned and forbidden path globs in its registry row. Two lanes never own an overlapping glob; shared files (`.gitignore`, `process/context/all-context.md`, CLAUDE.md) have one owner at a time. Overlap found at queue time forces serialization.

## 8. Worker envelope template

Sent as the worker's first message and saved as `{slug}_REF_{dd-mm-yy}.md` in the task folder. At most 8,000 bytes. Links, not contents.

```
ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate, do not spawn sessions or subagent chains, load only the files listed below; this overrides any orchestrator wording in CLAUDE.md or elsewhere.

Task: <ID> - <objective>
Acceptance: <one statement>
Owned files: <globs>      Forbidden: <globs>
Branch: claude/<task-id>-<slug>
Read: <task PLAN or SPEC path>; only if needed: north-star.md, current-state.md, architecture.md; operating-instructions.md: <named | not named>
Tests: tier RT<n>; required commands: <list>; full-suite budget: <n>
Retry budget: 2 fix cycles; same failure twice stops
Report: <task folder>/<slug>_REPORT_<dd-mm-yy>.md using the 11-heading template
Stop and report at `review` if: irreversible or outward-facing action, scope expansion, unverifiable condition, any doubt
Autonomy: <what this task may do without asking>
```

## 9. Completion report template

Path: `{task folder}/{slug}_REPORT_{dd-mm-yy}.md`. All 11 headings are required; "unmeasured" is allowed under heading 11.

```markdown
## 1 Task ID
## 2 Outcome
done | partial | failed
## 3 Summary
(10 lines or fewer)
## 4 Files changed
## 5 Commits
(SHAs and branch)
## 6 Tests run
(exact command, result, UTC timestamp, commit SHA)
## 7 Tests NOT run
(and why)
## 8 Deviations
(from scope)
## 9 Blockers
(risks, open questions, registry-update request)
## 10 Follow-up
(proposed tasks)
## 11 Context cost
(files loaded, approximate tokens; tools available to this session)
```

## 10. The four archive operations

| Op | Meaning | How | Allowed when |
|---|---|---|---|
| A | Archive documents | move the task folder to `completed/`; add a row to `process/archive/index.md` | normal task flow, user-visible |
| B | Mark logically complete | registry `accepted` then `archived` | only after the acceptance rule |
| C | Archive a session | `archive_session` | after the handover report is durable and the merge is verified; never with unresolved asks; otherwise user approval |
| D | Delete a branch / remove a worktree | GitHub branch delete or `git push origin --delete <branch>`; worktrees only by the user | see the consent below |

**Branch-deletion standing consent (user, 02-10-26: "delete merged task branches after verified merge and saved report").** Covers only merged worker task branches `claude/<task-id>-<slug>` that the Master Planner created for a registry task (not `claude/p1-pipeline`, `claude/p2-deploy` or any of the 12 pre-existing branches). Order: merge verified (PR merged, merge SHA reachable from `origin/main`, CI on it green), report committed, registry `accepted` then `archived`; then write the Approvals Log row (date, branch, merge SHA, report path, 'standing consent 02-10-26', status `pending`); then delete; then set the row to `done`, `failed` or `deletion deferred`. An empty log means no removal is permitted. The delete mechanism is unverified until the Gate 6 pilot; if none works, the branch stays. Every other branch and every worktree needs explicit per-branch user approval.

Wording rule: say "report file written" for A and "registry updated" for B; state C or D only when the tool call returned success. Never discard active work: an unmerged branch or unresolved asks block C and D.

## 11. Session start and end

**Start (planner):** read the PLANNER set; run `vc-review-situation`; check current-state.md staleness: stale when its stamped commit is not an ancestor of HEAD (`git merge-base --is-ancestor <stamp> HEAD` fails) or when more than 10 non-cache commits landed since it (`git log <stamp>..HEAD --oneline -- . ':(exclude)api/data/cache' | wc -l`); re-verify if stale; read the task row and brief; confirm lane and ownership.

**Start (worker):** read the envelope and only what it names.

**End (planner):** refresh current-state.md (branch, commit, uncommitted work, test results with timestamps, next action); update the registry row; write the report; commit or list any uncommitted work. Before closing, run the PLANNER-BUDGET block in section 12 and trim if headroom is below 3,000 B.

**End (worker):** commit the report on the task branch; request the registry update in report headings 9 and 10.

## 12. Planner entry-set budget

Fixed part = all-context.md router section (top through the line before `## Context Group Lifecycle`) + CLAUDE.md + north-star.md + current-state.md + MASTER-PLAN.md. Gate: fixed part <= 56,000 B, which keeps the 64,000 B planner cap for any task brief <= 8,000 B. Per-file ceilings (sum 56,000): CLAUDE.md 16,000; north-star.md 6,000; current-state.md 8,000 (target <= 7,000); MASTER-PLAN.md 19,000 (target <= 17,500); router 7,000. The lines with master-planner.md and a worst-case brief are reported only, never gated and never used to raise a cap. Run from the repo root in bash; pass is no OVER-CAP or MISSING line and `rc=0`.

```
# PLANNER-BUDGET:BEGIN
BRIEF_CAP=8000; FIXED_CAP=$((64000 - BRIEF_CAP)); MISS=0
for f in CLAUDE.md process/context/north-star.md process/context/current-state.md process/MASTER-PLAN.md process/context/all-context.md process/development-protocols/master-planner.md; do test -s "$f" || { echo "MISSING $f"; MISS=1; }; done
over() { n=$(wc -c < "$1"); [ "$n" -le "$2" ] || { echo "OVER-CAP $1 $n > $2"; MISS=1; }; }
ROUTER=$(sed '/^## Context Group Lifecycle/,$d' process/context/all-context.md | wc -c)
over CLAUDE.md 16000; over process/context/north-star.md 6000; over process/context/current-state.md 8000; over process/MASTER-PLAN.md 19000
[ "$ROUTER" -le 7000 ] || { echo "OVER-CAP router $ROUTER > 7000"; MISS=1; }
FIXED=$((ROUTER + $(cat CLAUDE.md process/context/north-star.md process/context/current-state.md process/MASTER-PLAN.md | wc -c)))
MP=$(wc -c < process/development-protocols/master-planner.md)
echo "planner_fixed=$FIXED cap=$FIXED_CAP headroom=$((FIXED_CAP-FIXED))"
echo "info_with_master_planner=$((FIXED+MP)) info_worst_case_brief=$((FIXED+MP+BRIEF_CAP)) gated_worst_case_brief=$((FIXED+BRIEF_CAP)) of 64000"
test "$MISS" -eq 0 && test "$FIXED" -le "$FIXED_CAP"; echo rc=$?
# PLANNER-BUDGET:END
```

**Brief cap:** a task brief is at most 8,000 B; for a larger PLAN read only its status, TL;DR and acceptance sections.

**Trim rule:** when headroom under 56,000 is below 3,000 B at a planner session end, trim before closing: (1) current-state.md is rewritten in place, one status block per gate at most, older gate narrative replaced by a link to its report; (2) MASTER-PLAN.md: R-row evidence cells at most 300 B with the report path, rows of finished NEW tasks (status `archived`) move to the archive index, historical T-rows and every registry ID stay; (3) router: Task Routing Table rows one line each; (4) CLAUDE.md only with the user.
