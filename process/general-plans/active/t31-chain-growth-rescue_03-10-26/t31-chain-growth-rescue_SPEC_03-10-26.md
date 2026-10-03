---
name: spec:t31-chain-growth-rescue
description: "Brief T31 (approved by the user 03-10-26; envelope _REF_ exists): rescue the chain-growth archive and on-chain source notes from three unmerged branches onto main, fresh"
date: 03-10-26
feature: general
---

# T31 - chain-growth rescue (approved)

**TL;DR:** The chain-growth closeout (archive move `active/` -> `completed/`, CLOSEOUT note, two review-decision files) and a new "On-chain Activity" section in `all-data-sources.md` exist only on unmerged branches (`kind-tesla-tat3vo` commit `4fd60bd`, `inspiring-pasteur-awqxk3`, `split-all-context`). User decision 03-10-26: "Rescue it via a task". Status `approved` by the user 03-10-26; the envelope `t31-chain-growth-rescue_REF_03-10-26.md` exists. Registry row: T31 in `process/MASTER-PLAN.md`.

## Scope (apply onto main fresh, not a rebase of the old branches)

1. Write the `completed/chain-growth_25-09-26/` tree under `process/features/onchain-activity/` from `git show origin/claude/split-all-context:<path>` for EVERY file there (branch-edited content wins), then `git rm -r` the `active/chain-growth_25-09-26` tree. A plain `git mv` is wrong: main's active/ copies hold PENDING decisions.
2. This includes the three added files: `chain-growth_CLOSEOUT_28-09-26.md` and `harness/rfc-003|004/review-decision.json` (approved by the user 2026-09-28).
3. Add only the `## On-chain Activity` section (+41 lines, between Reddit and `## Libraries`; growthepie, L2BEAT, Dune rejected) to `process/context/data-sources/all-data-sources.md`; main has 0 matches for growthepie. Do not take `all-context.md`, `context-changelog.md`, `tests/all-tests.md` or `onchain-activity/_GUIDE.md` (superseded by main).
4. PR #5's two path fixes: `api/analytics/onchain/growth.py` docstring path and `api/scripts/probe_chain_sources.py` line 73 `DEFAULT_OUT` -> `completed/chain-growth_25-09-26`.

Source content with `git show origin/claude/split-all-context:<path>` and `origin/claude/kind-tesla-tat3vo` (`4fd60bd`). Take only the paths above; the branches' context-doc edits are superseded by main.

## Ownership

Owned: `api/analytics/onchain/growth.py`, `api/scripts/probe_chain_sources.py`, `process/features/onchain-activity/**`, `process/context/data-sources/all-data-sources.md`, this task folder. Forbidden: CLAUDE.md, AGENTS.md, README.md, `.claude/**`, `.codex/**`, `.github/**`, `web/**`, `deploy/**`, `process/MASTER-PLAN.md`, `process/context/current-state.md`, `process/archive/**`, every other path.

## Tests

Tier RT2 (two path-only edits in `api/`). Gates: `uv run --project api pytest` on any test file that imports `growth.py` or the probe script (find with `git grep`), then `uv run --project api pytest api/ -q` once (budget 1); `python -m py_compile` on both files; `git grep -n 'chain-growth_25-09-26' -- api` shows only `completed/` paths; `node .claude/skills/vc-audit-context/scripts/validate-context-discovery.mjs` and `validate-all-context.mjs` for the context edit; `git grep -n 'active/chain-growth_25-09-26' -- process/features/onchain-activity api` prints nothing; `test ! -d process/features/onchain-activity/active/chain-growth_25-09-26`; `git grep -n growthepie -- process/context/data-sources/all-data-sources.md` > 0; any remaining `git grep -n 'chain-growth_25-09-26' -- . ':!process/features/onchain-activity'` hit is reported; `git diff --check`; CI green.

## Acceptance

Every item 1-4 present on main; no `active/chain-growth_25-09-26` path left; diff names only owned files. After T31 merges, `kind-tesla-tat3vo`, `inspiring-pasteur-awqxk3`, `split-all-context` become deletable (user deletes) and PR #5 is moot.
