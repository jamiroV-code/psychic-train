---
name: pair-screener-evl-iteration-002
date: 2026-09-26
domain: tests
iteration: 2
loop_status: CONTINUE
---

# Pair Screener — EVL Iteration 002 (RFC-002)

**Result:** gates green (20 passed; full 440 passed / 3 deselected), 1 test gap.

| Gap | Fix |
|---|---|
| MIN_OVERLAP_DAYS off-by-one: 364 shared days → `insufficient_overlap` was not asserted (only 365 ok and 300 were tested) | Add one boundary test to `api/tests/analytics/test_cointegration_stats.py`; re-run gates via vc-tester |

vc-tester reviewed the deviations and found them consistent with the locked plan text:
- a Johansen-only refusal keeps the pair `ok`, with `johansen_reason` (D2 wording);
- `bh_adjust` lives in the pure engine;
- `diagnostic_scope` and `overlap_days=None` match the §11 example.

The rebuilt fixture (c) was judged a legitimate test.

TL;DR: one missing boundary test; everything else confirmed.
