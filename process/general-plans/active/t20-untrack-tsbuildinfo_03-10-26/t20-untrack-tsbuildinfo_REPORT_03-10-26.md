## 1 Task ID
T20

## 2 Outcome
done (pending CI and merge; see PR)

## 3 Summary
Removed web/tsconfig.tsbuildinfo from the git index (working copy kept) and added the line `web/tsconfig.tsbuildinfo` under `# Node (web/)` in .gitignore. Local gates 1-5 passed. CI on head is the remaining proof.

## 4 Files changed
- .gitignore (one added line)
- web/tsconfig.tsbuildinfo (removed from index only)
- process/general-plans/active/t20-untrack-tsbuildinfo_03-10-26/t20-untrack-tsbuildinfo_REPORT_03-10-26.md (this report)

## 5 Commits
Branch claude/t20-untrack-tsbuildinfo. d8f3283 chore: stop tracking web/tsconfig.tsbuildinfo. A second commit adds this report (SHA in the PR).

## 6 Tests run
- `git ls-files web/tsconfig.tsbuildinfo | wc -l` -> 0 (2026-10-03T06:23:38Z, d8f3283)
- `grep -cxF 'web/tsconfig.tsbuildinfo' .gitignore` -> 1 (2026-10-03T06:23:38Z, d8f3283)
- `git check-ignore -q web/tsconfig.tsbuildinfo; echo rc=$?` -> rc=0 (2026-10-03T06:23:38Z, d8f3283)
- `git diff --check origin/main..HEAD` -> no output (2026-10-03T06:23:38Z, d8f3283)
- `git diff --name-only origin/main..HEAD` -> .gitignore, web/tsconfig.tsbuildinfo only (2026-10-03T06:23:38Z, d8f3283)
- Gate 6 (CI check-runs) recorded on the PR.

## 7 Tests NOT run
pytest, vitest, tsc: not allowed locally for RT0; CI runs them.

## 8 Deviations
None.

## 9 Blockers
No blockers; 0 fix cycles used. Registry request: move T20 to `accepted`, then `archived` with the merge SHA. Home-PC note: the home PC deploys with `git pull --ff-only`. If its copy of web/tsconfig.tsbuildinfo is locally modified, the first pull carrying this change refuses and the PC keeps serving the old build. Before that pull, the user runs `git status --short web/tsconfig.tsbuildinfo` on the PC; if it shows `M`, run `git checkout -- web/tsconfig.tsbuildinfo`, then pull. The cloud cannot verify this (known gap).

## 10 Follow-up
Planner to fix the stale tsbuildinfo sentence in operating-instructions.md. Repeat the home-PC note above for the user.

## 11 Context cost
Loaded: CLAUDE.md, the T20 SPEC, operating-instructions.md (grep excerpts only); about 12k tokens. Opened no other docs. Tools: Bash, Read, Edit, Write, Agent, mcp__github__* (including create_pull_request, merge_pull_request, get_check_run, pull_request_read), mcp__claude-code-remote__* (including archive_session, which I do not use). The envelope line `ROLE: WORKER` told me I am a WORKER.
