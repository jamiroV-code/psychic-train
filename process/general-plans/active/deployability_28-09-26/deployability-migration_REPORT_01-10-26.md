---
name: report:deployability-migration
description: "EXECUTE supplement 01-10-26 — different-PC cache-migration runbook in deploy/README.md, plan Section B-M, 9 new shape tests"
date: 01-10-26
metadata:
  node_type: memory
  type: report
  feature: none
  phase: EXECUTE-supplement
---

# Deployability — different-PC migration supplement (EXECUTE report, 01-10-26)

**Status: COMPLETE.** Documentation + shape tests only. No `.ps1`, `api/main.py`, `web/`,
`api/scripts/`, workflow, `.gitignore`, `cache.py` or context-doc change was needed — copying
the caches is a manual operator step, so no launcher needed editing.

Plan: `process/general-plans/active/deployability_28-09-26/deployability_PLAN_29-09-26.md`
(Gate: CONDITIONAL, accepted by user 29-09-26). Branch `claude/p2-deploy`.

## Why

The user cannot use the original PC and is migrating to a **different Windows PC** (old PC
still bootable, files copyable). That voids the plan's Phase 1 same-PC premise and activates
what the SPEC called the Phase 2 cache-migration problem.

## What Was Done

1. **`deploy/README.md`** — new `## Moving to a different PC (cache migration)` section:
   - must-copy table: `api\data\cache\ohlcv\`, `liquidity\`, `pairs\`, `api\data\watchlist.json`,
     and the optional reference-only `narrative\coingecko_trending.parquet`;
   - what arrives with `git clone` (`liqtide/`, `narrative/` bar that one file, `onchain/`);
   - `legs/` named as dead weight (no non-test caller of
     `cache.write_confirmed_boundaries` / `read_confirmed_boundaries`);
   - a bordered MUST-NOT-COPY box for **`web\.next`** — the old PC's Tailscale address is baked
     in by `next build` (F2), so `build-web.ps1` must be re-run and
     `%LOCALAPPDATA%\my_site\deploy.psd1` recreated with the new machine's absolute paths —
     plus the virtualenv / `node_modules` / `__pycache__` / `tsconfig.tsbuildinfo` list;
   - portability evidence (`provenance.json` stores no absolute path) and the one data-level
     gotcha: `/pairs` reports `stale` on a statsmodels/bar-count mismatch; `uv.lock` pins
     0.15.0 so a copied cache stays `fresh`, and one `compute_pairs` run (~56s) fixes it;
   - prerequisites; ordered steps **M0-M10** (quiesce → record → clone/prereqs → deps → copy →
     new Tailscale IP → verify copy → recreate config → rebuild → join at B5 → retire old PC);
   - a "verify the data is actually READ" table (`computation_status: fresh`, non-empty
     `grid_dates`, screener panels, your own watchlist) with failure branches;
   - full-rebuild fallback (all four scripts exist on this branch; watchlist via
     `watchlist.example.json`; `BOOTSTRAP.md` still "available once P1 merges"), and the
     **unverified** ~2020-08-19 Hyperliquid floor as the reason to prefer copying.
2. **Plan `## Overview`** — new `### PREMISE AMENDED 01-10-26` note; the "cache split-brain
   does not apply to Phase 1 (nothing to move)" sentence explicitly withdrawn; the hosting
   row no longer asserts the same-PC premise.
3. **Plan section B** — new `### Section B-M` table (M0-M11), the plan-side mirror, with the
   load-bearing ordering stated and "copy with both services stopped" enforced at M0.
4. **Plan `## Deviations`** — scoped-supplement entry recording all of the above.
5. **`api/tests/deploy/test_deploy_config_shape.py`** — 9 new text-shape tests (same
   conventions as the existing file: read files as text, never execute PowerShell):
   `test_readme_has_migration_section`,
   `test_readme_migration_names_every_must_copy_path`,
   `test_readme_migration_marks_next_build_as_must_not_copy`,
   `test_readme_migration_says_legs_cache_is_not_needed`,
   `test_readme_migration_states_pairs_staleness_rule`,
   `test_readme_migration_lists_paths_that_arrive_with_git_clone`,
   `test_readme_migration_orders_tailscale_before_config_before_build`,
   `test_readme_migration_requires_services_stopped_and_old_pc_retired`,
   `test_readme_migration_has_verification_and_rebuild_fallback`.

**Red-before-green evidence:** with `deploy/README.md` stashed, all 9 new tests fail
(`9 failed, 14 deselected`); with the section in place they pass.

## Test Gate Outcomes

| Gate | Before | After | Result |
|---|---|---|---|
| `uv run --project api pytest api/tests/deploy -q` | 38 passed / 1 xfailed | **47 passed / 1 xfailed** | PASS (+9, exactly the new tests) |
| `uv run --project api pytest api/ -q` | 752 passed / 5 deselected / 1 xfailed | **761 passed / 5 deselected / 1 xfailed** | PASS (+9, zero failures, zero regressions) |
| `git diff --check` | — | clean | PASS |
| `validate-plan-artifact.mjs` on the plan | — | 0 failures, 0 warnings (637 lines) | PASS |
| Scope check | — | only `deploy/README.md`, `api/tests/deploy/test_deploy_config_shape.py`, the plan, this report | PASS (within allowlist) |
| `git status --short api/data` | empty | empty | PASS (no real cache or watchlist touched) |

## Plan Deviations

One, deliberate and inside the allowlist: the ordering shape test asserts order across the
numbered `| M… |` step rows rather than first-occurrence of each string in the section, because
`deploy.psd1` and `build-web.ps1` also appear earlier in the MUST-NOT-COPY warning box. The
assertion is stricter in intent (it pins the step table itself), not weaker.

## Test Infra Gaps Found

- Unchanged from 29-09-26: these are **text-shape guards only**. Green proves the README says
  the right things; it does not prove any migration step works. The migration steps M0-M11 are
  Agent-Probe (user-run on Windows) and are **not** claimed as proven.
- Backlog stub (carried, not new): PowerShell parser gate in CI.
- No new automated coverage is possible for the copy itself in this container (no Windows, no
  second machine, no real cache to move).

## Forward Preview

- **Test infra found:** `api/tests/deploy/` shape-test conventions extended cleanly; the
  `_migration_section()` helper gives future README sections a cheap scoping pattern.
- **Blast radius changes:** none beyond the allowlist; no source behavior changed.
- **Commands to stay green:** `uv run --project api pytest api/tests/deploy -q` (47 passed /
  1 xfailed) and `uv run --project api pytest api/ -q` (761 passed / 5 deselected / 1 xfailed).
- **Dependency changes:** none.

## Closeout Packet

- Selected plan: `process/general-plans/active/deployability_28-09-26/deployability_PLAN_29-09-26.md`
- Finished: the migration runbook, plan premise amendment, Section B-M, 9 shape tests, all gates green.
- Verified: everything automated above. **Unverified:** every user-PC step (section B and B-M),
  and whether a fresh deep fetch reaches the ~2020-08-19 Hyperliquid floor.
- Remaining: user runs B-M then B5-B15 on the new PC and reports back.
- **Classification: Keep in active/testing.** Section A stays `CODE DONE`, not `VERIFIED`.
- Not committed or pushed (orchestrator owns that).
