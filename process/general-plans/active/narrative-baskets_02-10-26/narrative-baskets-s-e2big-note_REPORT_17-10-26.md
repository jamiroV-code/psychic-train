# T94 Report: planner shell E2BIG note

## 1 Task ID
T94

## 2 Outcome
Done. One decision entry (D-21) appended.

## 3 Summary
Added D-21 to process/context/decisions.md: symptom, effect, workarounds, fix and mitigation for the planner-shell E2BIG failure seen on 2026-10-17.
Known limits: causes are unconfirmed hypotheses. No pointer line added: decisions.md and master-planner.md have no known-issues or troubleshooting section.

## 4 Files changed
- process/context/decisions.md (D-21 appended)
- this report

## 5 Commits
One commit on claude/t94-planner-shell-e2big-note.

## 6 Tests run
git diff --check origin/main...HEAD (clean); ASCII check on entry (ok, 1207 B); only allowed files changed.

## 7 Tests NOT run
None applicable (docs only).

## 8 Deviations
Entry first drafted at 1824 B, trimmed to 1207 B to meet the 1,400 B cap.

## 9 Blockers
None.

## 10 Follow-up
Owner may want a pointer line if a troubleshooting section is added later.

## 11 Context cost
Read: CLAUDE.md, envelope, tail of decisions.md, one grep. No other docs opened.
