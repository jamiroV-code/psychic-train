ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate, do not spawn sessions or subagent chains, load only the files listed below; this overrides any orchestrator wording in CLAUDE.md or elsewhere. This envelope is your EXECUTE approval: do not wait for ENTER EXECUTE MODE.

Task: PROBE-G3 - answer the three questions in the task brief, in the reply only
Acceptance: the reply contains the 11-heading completion report as text; no file is changed
Owned files: none      Forbidden: every path (read only)
Branch: none (report-only task; nothing is committed)
Read: process/general-plans/active/master-planner-recovery_02-10-26/gate3-probe-brief_REF_03-10-26.md; only if needed: north-star.md, current-state.md, architecture.md; operating-instructions.md: not named
Tests: tier RT0; required commands: none; full-suite budget: 0
Retry budget: 2 fix cycles
Report: as text in the reply, using the 11-heading template (do not write a file for this probe)
Stop and report at `review` if: irreversible or outward-facing action, scope expansion, unverifiable condition, any doubt
Autonomy: read the brief and reply; nothing else
