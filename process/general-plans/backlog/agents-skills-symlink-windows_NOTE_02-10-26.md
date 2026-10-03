---
name: note:agents-skills-symlink-windows
description: "Backlog: behaviour of a symlinked .agents/skills on the user's Windows PC is unverified"
date: 02-10-26
feature: general
---

# Verify a symlinked `.agents/skills` on the Windows PC (backlog note)

**TL;DR:** Housekeeping item H1 would replace the 339 tracked files in `.agents/skills` with a symlink to `.claude/skills`, clearing the baseline failure in validate-skills and validate-context-discovery. Nobody has checked how that symlink behaves when the user pulls on Windows.

- **What is unproven:** that a mode-120000 entry checks out as a working link on the PC, and that the validators and Codex discovery still pass there.
- **Why:** the cloud container is Linux; Windows needs `git config core.symlinks true` plus Developer Mode or an elevated checkout, otherwise the link becomes a text file.
- **How to close:** on the PC, check `git config core.symlinks`, pull the H1 commit, confirm `.agents/skills` resolves to `.claude/skills`, run both validators; record the result. Rollback is `git revert` of the H1 commit.
- **Source:** master-planner-recovery plan, section 7 H1 and Verification Evidence known gaps; F15.
