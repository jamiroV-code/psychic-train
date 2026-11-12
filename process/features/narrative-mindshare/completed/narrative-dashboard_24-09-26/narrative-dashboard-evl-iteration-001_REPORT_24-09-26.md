---
name: narrative-dashboard-evl-iteration-001
description: EVL cycle 1 for RFC-4 + RFC-5 — null-delta render not guarded by a test
date: 2026-09-24
metadata:
  domain: tests
  iteration: 1
  loop_status: CONTINUE
---

# EVL Iteration 001 — RFC-4 + RFC-5

**Result:** all 5 gates green, with one missing test assertion found by mutation testing.

- pytest: 388 passed, 3 deselected
- scoped RFC-4 + contract tests: 13 passed
- vitest: 109 passed, 16 files
- `tsc --noEmit`: exit 0
- Playwright: 12/12 passed, run with `PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`

| Gap | Evidence | Fix |
|---|---|---|
| Nothing tests that a null change-in-attention delta renders "—" rather than 0 | Mutating `ChangeInAttentionView.tsx` to render `0` for a null delta left `RankViews.test.tsx` green | vc-execute-agent (supplement mode) adds an assertion on the delta cell for the null-delta row; vc-tester then re-runs |

The RFC-4 mutation (disabling first-observation-wins) failed its test as expected, so that guard is real.

TL;DR: All gates pass; one missing assertion must be added and re-confirmed.
