---
name: spec:t31-chain-growth-rescue
description: "Brief T31 (proposed, NOT approved, no envelope): rescue the chain-growth archive and on-chain source notes from three unmerged branches onto main, fresh"
date: 03-10-26
feature: general
---

# T31 - chain-growth rescue (brief only, proposed)

**TL;DR:** The chain-growth closeout (archive move `active/` -> `completed/`, CLOSEOUT note, two review-decision files) and a new "On-chain Activity" section in `all-data-sources.md` exist only on unmerged branches (`kind-tesla-tat3vo` commit `4fd60bd`, `inspiring-pasteur-awqxk3`, `split-all-context`). User decision 03-10-26: "Rescue it via a task". Status `proposed`: no worker until the user approves; no envelope exists yet. Registry row: T31 in `process/MASTER-PLAN.md`.

## Scope (apply onto main fresh, not a rebase of the old branches)

1. Move `process/features/onchain-activity/active/chain-growth_25-09-26/` to `completed/` (same task folder name).
2. Add `chain-growth_CLOSEOUT_28-09-26.md` and the two `review-decision.json` files (`harness/rfc-003/`, `harness/rfc-004/`).
3. Add the "On-chain Activity" section (growthepie, L2BEAT, Dune rejected) to `process/context/data-sources/all-data-sources.md`; main has 0 matches for growthepie.
4. PR #5's two path fixes: `api/analytics/onchain/growth.py` docstring path and `api/scripts/probe_chain_sources.py` line 73 `DEFAULT_OUT` -> `completed/chain-growth_25-09-26`.

Source content with `git show origin/claude/split-all-context:<path>` and `origin/claude/kind-tesla-tat3vo` (`4fd60bd`). Take only the paths above; the branches' context-doc edits are superseded by main.

## Ownership

Owned: `api/analytics/onchain/growth.py`, `api/scripts/probe_chain_sources.py`, `process/features/onchain-activity/**`, `process/context/data-sources/all-data-sources.md`, this task folder. Forbidden: CLAUDE.md, AGENTS.md, README.md, `.claude/**`, `.codex/**`, `.github/**`, `web/**`, `deploy/**`, `process/MASTER-PLAN.md`, `process/context/current-state.md`, `process/archive/**`, every other path.

## Tests

Tier RT2 (two path-only edits in `api/`). Gates: `uv run --project api pytest` on any test file that imports `growth.py` or the probe script (find with `git grep`), then `uv run --project api pytest api/ -q` once (budget 1); `python -m py_compile` on both files; `git grep -n 'chain-growth_25-09-26' -- api` shows only `completed/` paths; `node .claude/skills/vc-audit-context/scripts/validate-context-discovery.mjs` and `validate-all-context.mjs` for the context edit; `git diff --check`; CI green.

## Acceptance

Every item 1-4 present on main; no `active/chain-growth_25-09-26` path left; diff names only owned files. After T31 merges, `kind-tesla-tat3vo`, `inspiring-pasteur-awqxk3`, `split-all-context` become deletable (user deletes) and PR #5 is moot.
