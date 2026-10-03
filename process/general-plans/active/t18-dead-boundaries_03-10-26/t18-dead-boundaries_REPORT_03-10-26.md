## 1 Task ID
T18

## 2 Outcome
done (pending CI on head; see heading 9)

## 3 Summary
Removed `confirmed_boundaries_path`, `write_confirmed_boundaries`, `read_confirmed_boundaries` and their section comment from `api/data/cache.py`. Deleted only the three test items: the parametrised `write_confirmed_boundaries` entry and `test_round_trip_confirmed_boundaries` (atomic_writes), and `test_confirmed_boundaries_datetimes_read_back_in_utc` (timezone). Pre-change grep found no non-test runtime caller. pytest: 873 passed before, 870 after (873 - 3). No snapshot or unowned file touched.

## 4 Files changed
- api/data/cache.py (-20)
- api/tests/data/test_cache_atomic_writes.py (-12)
- api/tests/data/test_cache_timezone.py (-15)
- this report

## 5 Commits
Branch claude/t18-dead-boundaries: ed604f3 (code change); report commit follows (see PR).

## 6 Tests run
- `git grep -nE 'write_confirmed_boundaries|read_confirmed_boundaries|confirmed_boundaries_path' -- api web deploy .github` BEFORE (origin/main 56fb966): hits in api/data/cache.py (366,370,371,376,377), api/tests/data/test_cache_atomic_writes.py (205-209,303,304), api/tests/data/test_cache_timezone.py (204,207), api/tests/deploy/test_deploy_config_shape.py:258, deploy/README.md:104,105. No non-test runtime caller.
- `git grep -n 'legs/confirmed' -- api web deploy .github` BEFORE: no hits; AFTER: no hits.
- same first grep AFTER (ed604f3): only api/tests/deploy/test_deploy_config_shape.py:258 and deploy/README.md:104,105 remain.
- `uv run --project api pytest api/ -q` @56fb966 2026-10-03T14:57:34Z: 873 passed, 1 skipped, 5 deselected, 1 xfailed.
- `uv run --project api pytest api/tests/data -q` @ed604f3-pre-commit 2026-10-03T15:00:45Z: 203 passed, 4 deselected.
- `uv run --project api pytest api/ -q` @ed604f3 2026-10-03T15:01:05Z: 870 passed, 1 skipped, 5 deselected, 1 xfailed.
- `pnpm --filter web test` @ed604f3 2026-10-03T15:04:10Z: 30 files, 223 passed.
- `pnpm --filter web exec tsc --noEmit` @ed604f3 15:04Z: exit 0.
- `cd web && pnpm build:islands` @ed604f3 15:04Z: built OK.
- `git status --porcelain`: clean; `git diff --name-only origin/main..HEAD`: only the three owned code files; `git diff --check`: empty.

## 7 Tests NOT run
Playwright e2e (not required at RT3, no route changed). Web gates were first attempted without node_modules (fail: vitest/vite not found); ran `pnpm install --frozen-lockfile` in web/ (no tracked change) and ran them once.

## 8 Deviations
Web install needed before gates 4-6 (environment only). Gate 9 (CI) recorded in the PR, not here.

## 9 Blockers
None. Fix cycles used: 0. Registry-update request: T18 accepted, then archived with the merge SHA.

## 10 Follow-up
For R12 (owner of deploy/README.md and api/tests/deploy/test_deploy_config_shape.py): deploy/README.md lines 104-105 say "`cache.write_confirmed_boundaries` and `cache.read_confirmed_boundaries` have no non-test callers"; those functions no longer exist, and `test_readme_migration_says_legs_cache_is_not_needed` (line 258) asserts the name appears in that README section. Reword both together.

## 11 Context cost
Loaded: CLAUDE.md, the envelope, T18 SPEC, grep of operating-instructions.md rows; about 15k tokens. Merge/PR tools present: mcp__github__merge_pull_request, mcp__github__create_pull_request; session tools in tool list (not used): none called. The line "ROLE: WORKER" in the envelope told me I am a WORKER.
