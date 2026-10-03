---
name: spec:t20-untrack-tsbuildinfo
description: "Worker brief T20: stop tracking web/tsconfig.tsbuildinfo and add its .gitignore line (RT0, Gate 5/6 worker pilot)"
date: 03-10-26
feature: general
---

# T20 - stop tracking web/tsconfig.tsbuildinfo and ignore it (worker brief)

**TL;DR:** remove `web/tsconfig.tsbuildinfo` from the git index (keep the file on disk), add the exact line `web/tsconfig.tsbuildinfo` to `.gitignore`, prove it with four local checks plus CI, open a PR against `main`, self-merge only when every condition in your envelope holds.

Registry row: T20 in `process/MASTER-PLAN.md` (you do not edit it). Envelope: `t20-untrack-tsbuildinfo_REF_03-10-26.md` in this folder.

## Why

`web/tsconfig.json` sets `incremental: true`, so every `tsc` run (local and CI) rewrites `web/tsconfig.tsbuildinfo` (about 170 KB). Because the file is tracked, each run shows up as a spurious change. Nothing reads it from git: `.github/workflows/ci.yml` never mentions it, and the two other mentions (`api/tests/deploy/test_deploy_config_shape.py`, `deploy/README.md`) only say "never copy it" and stay correct. Untracking stops the churn; `tsc` recreates the file when missing (measured: exit 0 in about 5 s).

## Steps (exactly these, in order)

1. `git rm --cached web/tsconfig.tsbuildinfo` (index only; the working copy stays).
2. Append the line `web/tsconfig.tsbuildinfo` to `.gitignore` directly under the existing `# Node (web/)` comment block (if that heading is absent, append at the end of the file). One line, no other `.gitignore` change.
3. Run the local gates 1-4 of your envelope once, after the last edit, and record each in report heading 6 (command, result, UTC time, commit SHA).
4. Commit with a `chore:` prefix, for example `chore: stop tracking web/tsconfig.tsbuildinfo`.
5. Write and commit the report, push the branch, open the PR against `main` by REST or MCP, wait for CI, check the self-merge conditions, merge (squash) or stop at `review`.

No pytest, vitest or tsc locally: CI on your PR head runs `tsc` and the island build from a checkout that no longer has the file, which is the real proof.

## Expected gate results

| Gate | Command | Expected |
|---|---|---|
| 1 | `git ls-files web/tsconfig.tsbuildinfo \| wc -l` | `0` |
| 2 | `grep -cxF 'web/tsconfig.tsbuildinfo' .gitignore` | `1` |
| 3 | `git check-ignore -q web/tsconfig.tsbuildinfo; echo rc=$?` | `rc=0` |
| 4 | `git diff --check origin/main..HEAD` | no output |
| 5 | `git diff --name-only origin/main..HEAD` | only `.gitignore`, `web/tsconfig.tsbuildinfo` and files in this task folder |
| 6 | check-runs on your current head | `api — pytest` and `web — vitest, tsc, island build` both completed / success |

## Home-PC note (copy into report headings 9 and 10)

The user's home PC deploys with `git pull --ff-only` (deploy Stage A, non-fatal). If its copy of `web/tsconfig.tsbuildinfo` is locally modified, the first pull that carries this change refuses, and the PC keeps serving the old build. One-time step for the user, before that pull: run `git status --short web/tsconfig.tsbuildinfo` on the PC; if it shows `M`, run `git checkout -- web/tsconfig.tsbuildinfo` first, then pull. The cloud cannot verify this (known gap).

## Report requests

Heading 9: ask the Master Planner to move T20 to `accepted` and then `archived` with the merge SHA, and repeat the home-PC note. Heading 10: any follow-up (for example the stale tsbuildinfo sentence in operating-instructions.md, which the planner fixes, not you).
