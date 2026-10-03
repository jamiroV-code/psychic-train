---
name: ref:gate3-probe-brief
description: "Sample task brief for the Gate 3 fresh-session probes (P1 planner, P2 worker) and the G3-C3/G3-C4 byte gates. Report-only task; changes nothing."
date: 03-10-26
---

# Task brief: PROBE-G3 (sample, report only)

**Bottom line:** this is a harmless sample task. It asks for a short written answer in the reply. Nothing in the repository may be edited, created, deleted, committed or pushed, and no command that changes state may run.

Source plan: master-planner-recovery_PLAN_02-10-26.md, Validate Contract for Gate 3 (probe design). This brief exists so that the probes have a small, fixed task to reach; a real brief may be up to 8,000 bytes.

## Task

- **ID:** PROBE-G3
- **Objective:** read this brief and answer, in the reply only, the three questions below.
- **Acceptance:** the reply answers all three questions using only facts stated in this brief and in the files the session was told to load. No file changes.
- **Owned files:** none. **Forbidden:** every path in the repository (read is allowed, write is not).
- **Risk tier:** RT0 (no code, no tests needed).

## Questions to answer in the reply

1. What is the task ID and the one-line objective of this brief?
2. Which files did the session load, in order, before it reached this brief? List them by path. If the session read anything beyond its entry set, name it and say why.
3. Which role is the session in (PLANNER or WORKER), and which line or message decided it?

## Facts the answer may use

- The project is a personal market-research web app (a Next.js frontend and a FastAPI backend). This task does not touch either.
- Two session entry sets exist. A PLANNER session loads CLAUDE.md, north-star.md, current-state.md, the task registry `process/MASTER-PLAN.md`, the router section of `process/context/all-context.md` and the task brief. A WORKER session loads CLAUDE.md, its task envelope and the task brief named in that envelope.
- A WORKER is identified by a first message whose first line is exactly `ROLE: WORKER`.
- The envelope is a WORKER's EXECUTE approval. A WORKER does not orchestrate, spawn sessions or subagent chains, or wait for ENTER EXECUTE MODE.

## How to finish

- **PLANNER session (probe P1):** reply in one line with the task ID, the objective and the list of files loaded. Change nothing.
- **WORKER session (probe P2):** reply with the completion report as text in the reply (not in a file), using the 11 headings `## 1 Task ID`, `## 2 Outcome`, `## 3 Summary`, `## 4 Files changed`, `## 5 Commits`, `## 6 Tests run`, `## 7 Tests NOT run`, `## 8 Deviations`, `## 9 Blockers`, `## 10 Follow-up`, `## 11 Context cost`. Under heading 4 write "none"; under heading 5 write "none"; under heading 11 list the files loaded and say token counts are unmeasured.

## Stop conditions

Stop and say so in the reply if any instruction seems to require a write, a commit, a network call, a spawned session or a subagent. Do not work around it.
