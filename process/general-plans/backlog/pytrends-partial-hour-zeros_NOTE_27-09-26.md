---
name: note:pytrends-partial-hour-zeros
description: "Backlog: nightly pytrends narrative points read 0 from Google's incomplete isPartial hour; plus the unrecoverable 2026-09-25 narrative gap"
date: 27-09-26
feature: none
---

# Pytrends partial-hour zeros (backlog note)

**TL;DR:** Some nightly pytrends points are 0 because the value we store is the last hour of
Google's hourly "now 7-d" frame, and that hour is still incomplete. Separately, 2026-09-25 has no
narrative point at all and cannot be recovered. Neither is fixed. Found during
`process/general-plans/active/snapshot-cron-timing_27-09-26/`.

## Finding 1 — partial-hour zeros

**RESOLVED 2026-09-28** — see
`process/features/narrative-mindshare/completed/pytrends-partial-hour-fix_28-09-26/`. Fixed via a
full RESEARCH → SPEC → INNOVATE → PLAN → VALIDATE → EXECUTE → EVL cycle (SIMPLE plan, `Gate:
PASS`), not ad hoc. Chose the first suggested follow-up option below (drop `isPartial` rows); the
daily-aggregate alternative was considered and explicitly not chosen (larger semantic change, no
proven precedent needed since the drop-partial-rows pattern already existed in
`backfill_pytrends_history.py`). Existing archived zeros (09-24 through 09-28) were left as-is,
honestly dated, per the original suggestion below.

- Observed: memecoins dropped 34 → 0 between nightly points; RWA is 0 on every nightly point.
- Cause: `api/data/pytrends_adapter.py` takes `df.iloc[-1]` of the "now 7-d" `interest_over_time()`
  frame. That frame is hourly, and its last row is Google's current, incomplete hour (flagged
  `isPartial=True`), which is often 0 or heavily under-counted.
- Suggested follow-up (needs its own plan — it changes stored values and the `/narrative`
  composite):
  - drop `isPartial` rows before taking the last point, or
  - store a daily aggregate (e.g. the mean of the last complete 24 hours) instead of one hour.
- Existing archived zeros would stay as-is (honestly dated) unless the follow-up plan decides
  otherwise.

## Finding 2 — 2026-09-25 narrative gap

- `narrative-snapshot.yml` was scheduled for 23:00 UTC, but GitHub started it ~2h late
  (01:03–01:07 UTC). Points are dated by the UTC day the run executes, so the 09-25 slot was skipped.
- Unrecoverable: Google Trends' short window, Reddit search and CoinGecko trending keep no history.
  pytrends' own `backfill_pytrends_history.py` could refill pytrends only, and only on a different
  request scale (`mixed_scale`) — not done, left as a documented gap.
- Cause fixed by the cron move (narrative now `17 18 * * *`); no further action planned.
