# T31 report

## 1 Task ID
T31 - chain-growth rescue (branch claude/t31-chain-growth-rescue)

## 2 Outcome
done (pending CI and merge, see PR)

## 3 Summary
- Wrote the full completed/chain-growth_25-09-26/ tree (30 files incl. CLOSEOUT and approved rfc-003/004 review-decision.json) from origin/claude/split-all-context; `git rm -r` of active/chain-growth_25-09-26.
- Added only the `## On-chain Activity` section (34 lines) to all-data-sources.md; frontmatter/header/date edits are outside the section so skipped.
- Fixed growth.py docstring path and probe_chain_sources.py DEFAULT_OUT to completed/.
- Source listing (heading 6): 31 entries incl. renames; superseded files skipped (heading 8).

## 4 Files changed
process/features/onchain-activity/{active -> completed}/chain-growth_25-09-26/** ; process/context/data-sources/all-data-sources.md ; api/analytics/onchain/growth.py ; api/scripts/probe_chain_sources.py ; this task folder (report).

## 5 Commits
Branch claude/t31-chain-growth-rescue. Content commit f394d740d6feea6b76bcf178a394e76b69907d93 (base fc72ff3). Report commit follows it (cannot self-reference; see PR head).

## 6 Tests run
Source listing: `git diff --name-status origin/main...origin/claude/split-all-context` showed M all-context.md, A context-changelog.md, M all-data-sources.md, M tests/all-tests.md, M onchain-activity/_GUIDE.md, D active rfc-003/004 review-decision.json, 25 R/A entries moving active/ -> completed/ (incl. A CLOSEOUT, A completed rfc-003/004 review-decision.json).

| Gate | Command | Result | UTC | SHA |
|---|---|---|---|---|
| preflight | fetch, checkout -B, test -f x4, cat-file SPEC | ok | 2026-10-03T19:49Z | fc72ff3 |
| py_compile | python -m py_compile growth.py probe_chain_sources.py | rc 0 | 2026-10-03T19:49Z | fc72ff3+worktree |
| importers pytest | api/tests/scripts/test_probe_chain_sources.py (importers: comparison.py, probe script, that test) | 17 passed | 19:49:34 | worktree (pre-commit, same content as f394d74) |
| full suite | uv run --project api pytest api/ -q | 870 passed, 1 skipped, 5 deselected, 1 xfailed | 19:53:57 | worktree (same content as f394d74) |
| grep api | git grep -n chain-growth_25-09-26 -- api | only completed/ paths | 19:49Z | worktree |
| grep active | git grep active/chain-growth_25-09-26 -- onchain-activity api | empty | 19:49Z | worktree |
| dir gone | test ! -d .../active/chain-growth_25-09-26 | ok | 19:49Z | worktree |
| growthepie | git grep -c growthepie all-data-sources.md | 4 | 19:49Z | worktree |
| diff check | git diff --check | clean | 19:49Z | worktree |
| validate-context-discovery | node ...validate-context-discovery.mjs | 1 failure ".agents/skills does not resolve to .claude/skills": BASELINE (.agents/skills is a tree on origin/main; no touched path) | 19:49Z | worktree |
| validate-all-context | node ...validate-all-context.mjs | no failures, no warnings | 19:49Z | worktree |
| remaining refs | git grep chain-growth_25-09-26 outside onchain-activity | see heading 9 | 19:49Z | worktree |
| CI | check-runs on head | see PR; recorded in final reply | - | - |

## 7 Tests NOT run
Source-branch checks were not run. No other test skipped. Importer pytest ran before commit; content identical to f394d74.

## 8 Deviations
- Skipped (superseded by main, per envelope): process/context/all-context.md, context-changelog.md, tests/all-tests.md, process/features/onchain-activity/_GUIDE.md.
- Data-sources section is 34 lines, not the +41 in the SPEC (the +41 included header/keywords/date lines outside the section).
- baseline: .agents/skills validator failure.

## 9 Blockers
No blockers, 0 fix cycles. Remaining `chain-growth_25-09-26` hits outside onchain-activity: api/analytics/onchain/growth.py:7 and api/scripts/probe_chain_sources.py:73 (both completed/), all-data-sources.md:331 (completed/), and the T31 task folder REF/SPEC. No active/ hits.
Registry-update request for the planner: mark T31 accepted, then archived with the merge SHA. The three held branches (kind-tesla-tat3vo, inspiring-pasteur-awqxk3, split-all-context) become deletable by the user; PR #5 is moot.

## 10 Follow-up
Planner updates MASTER-PLAN.md / current-state.md / archive index (forbidden to this worker). User deletes held branches.

## 11 Context cost
Loaded: CLAUDE.md, the T31 envelope, the SPEC, source-branch diffs. About 35k tokens. The line "ROLE: WORKER" in the first system notification identified the role.
Tool names:
- mcp__github__merge_pull_request: see final reply
- mcp__github__create_pull_request: see final reply
- mcp__github__update_pull_request_branch: none
- mcp__claude-code-remote__create_session: none
- mcp__claude-code-remote__archive_session: none
- mcp__claude-code-remote__send_message: none
- mcp__claude-code-remote__unarchive_session: none
- mcp__claude-code-remote__interrupt_session: none
- mcp__claude-code-remote__set_session_title: none
- mcp__claude-code-remote__set_session_tags: none
- mcp__claude-code-remote__list_sessions: none
- mcp__claude-code-remote__get_session: none
- mcp__claude-code-remote__list_events: none
- mcp__claude-code-remote__get_event: none
- mcp__ccd_session__spawn_task: none
- mcp__ccd_session__dismiss_task: none
- other present session tools (mcp__claude-code-remote__*: add_repo, create_trigger, delete_trigger, fire_trigger, get_trigger, list_environments, list_repos, list_triggers, list_sessions excluded above, read_documentation, register_repo_root, send_later, subscribe_pr_activity, unsubscribe_pr_activity, unwatch_url, update_trigger, watch_url): none
