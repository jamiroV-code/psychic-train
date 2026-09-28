---
name: note:screener-weekly-bars-flake
description: "Backlog: web/e2e/screener.spec.ts:103 'weekly bars are Monday 00:00 UTC' fails intermittently inside full Playwright suite runs, not in isolation; not yet proven pre-existing against base"
date: 28-09-26
feature: none
---

# screener.spec.ts weekly-bars flake (backlog note)

**TL;DR:** A screener Playwright test fails about 1 in 3 full-suite runs, but passes 15/15 when
re-run alone. Judged a pre-existing, unrelated, environmental flake during the
`narrative-v2_25-09-26` UPDATE PROCESS closeout (28-09-26, 2nd session) — but that judgement has
NOT been proven by reproducing the failure against the base commit in a clean worktree. Needs a
future session to actually do that proof and root-cause it.

## Finding

- Test: `web/e2e/screener.spec.ts:103`, "weekly bars are Monday 00:00 UTC".
- Observed during narrative-v2's independent EVL confirmation run: full Playwright suite run 3
  times (`PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome cd web &&
  pnpm test:e2e`) → run 1 = 55/55, run 2 = 54/55 (this test failed), run 3 = 55/55.
- Isolated re-run of just this spec with `--repeat-each=15` → 15/15 passed. It only fails inside a
  full-suite run, suggesting resource contention (timing/cold-start/parallel-worker pressure) rather
  than a logic bug in the test or the underlying weekly-bar-anchoring code.
- The identical failure signature (same test, same run-2-of-3 position) was already present in PR
  #7's own pre-this-session description — i.e. this is not new to the narrative-v2 work.

## Why not fixed now

- `narrative-v2` touches zero screener files, code, or API surface — there's no narrative-v2 change
  that could plausibly cause this.
- Root-causing and fixing this needs its own scoped investigation, not a side effect of an unrelated
  feature's UPDATE PROCESS pass.

## Suggested follow-up (needs its own plan)

- Reproduce against the pre-narrative-v2 base commit in a clean worktree (the same proof technique
  used for the pre-existing screener flake found during `pair-screener_25-09-26` — see
  `process/features/cointegration-screener/completed/pair-screener_25-09-26/`) to confirm this is
  genuinely pre-existing and not masked/introduced by any other recent change.
- Once proven pre-existing, root-cause the resource-contention hypothesis (e.g. run with reduced
  Playwright worker parallelism, or profile cold-start latency during the full-suite run) and decide
  whether a config-only fix (like the `pair-screener_25-09-26` `expect.timeout` bump) is sufficient,
  or whether the underlying weekly-bar-anchoring test needs a more robust wait condition.
