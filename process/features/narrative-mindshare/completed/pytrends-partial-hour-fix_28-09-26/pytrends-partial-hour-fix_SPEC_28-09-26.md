---
name: spec:pytrends-partial-hour-fix
description: "Stop nightly pytrends narrative points from archiving Google's incomplete current hour as a real 0/near-0 value"
date: 28-09-26
feature: narrative-mindshare
---

# Pytrends Partial-Hour Zeros — SPEC

## Summary

Every night, the app records one Google Trends "attention" reading per tracked narrative category
(ai, rwa, l2s, memecoins) for the `/narrative` dashboard. Right now that reading is sometimes not a
real reading at all — it's Google's current, still-filling-in hour, which is frequently 0 or far too
low. Because Google Trends keeps no history to go back and fix later, every night this happens the
real value for that category is gone forever. This SPEC locks the requirement to stop recording
Google's incomplete hour as if it were a finished one, so the nightly archive (and the confidence
signals built on top of it) stop silently degrading.

## User Stories / Jobs To Be Done

- As the app's user (a solo trader relying on the narrative dashboard for confidence signals), I
  want each night's pytrends attention reading to reflect a real, complete measurement, so that the
  `/narrative` history and composite scores I use for sizing decisions aren't quietly corrupted by
  zeros that were never true.
- As the same user, when I look at the `/narrative` dashboard's data-quality caveat, I want to trust
  that a category showing "0" or a sharp drop is a real signal (or an honestly-flagged unavailable
  reading), not an artifact of when the nightly job happened to run.
- As the maintainer of this codebase, I want the fix scoped to only the code path that's actually
  broken, so it does not block or conflict with the already-planned `narrative-v2` RFC-3 batching
  work that touches the same file later.

## What The User Wants (Behavioral Outcomes)

- The nightly pytrends fetch for each narrative keyword no longer treats Google's current,
  in-progress hour as a finished data point. If the only data available is that incomplete hour, the
  fetch behaves the same as "no usable data was returned" — the existing `unavailable` /
  `presumed-dead` handling already built for other failure cases takes over. No new zero-but-fake
  value gets written to the archive.
- This applies to the live nightly fetch only (`_fetch_live` / `fetch_trend`, the path
  `snapshot_narrative.py` calls every night). The separate 269-day historical backfill script already
  does this correctly and is not changed by this fix — it's cited as the existing pattern to follow.
- Categories that previously wrote 0 every night purely due to this bug (observed: `memecoins`,
  `RWA`) should, from the night this fix ships onward, either get a real nonzero reading or be
  honestly marked unavailable — never a fabricated 0.
- Already-archived zero-valued points (the nights this bug already damaged, e.g. 09-24 through
  09-28) are left as-is, dated exactly as they were recorded. This SPEC does not retroactively edit
  or delete history — see Acceptance Criteria and Out Of Scope for the explicit reasoning.
- Nothing about how the `/narrative` dashboard displays, blends, or trust-weights sources changes as
  a side effect of this fix — the only change is that the nightly number being fed in is more
  trustworthy.

## Flow / State Diagram

```
BEFORE (buggy):

  nightly snapshot job (snapshot_narrative.py)
        │
        ▼
  pytrends_adapter.fetch_trend(keyword)
        │
        ▼
  _fetch_live(keyword)
        │
        ▼
  pytrends "now 7-d" hourly frame  ──▶  df.iloc[-1]  ──▶  value, as_of
                                          (last row = Google's
                                           CURRENT, INCOMPLETE hour
                                           — often 0 / undercounted)
        │
        ▼
  cache.write_narrative_point()  ──▶  archived forever, unrecoverable if wrong


AFTER (fixed):

  nightly snapshot job (snapshot_narrative.py)
        │
        ▼
  pytrends_adapter.fetch_trend(keyword)
        │
        ▼
  _fetch_live(keyword)
        │
        ▼
  pytrends "now 7-d" hourly frame
        │
        ├─▶ drop isPartial=True rows (same pattern already used by
        │    backfill_pytrends_history.py's daily_points())
        │
        ▼
  any complete rows left?
        │
   ┌────┴────┐
   │  yes    │   no
   ▼         ▼
 last      return (None, None)
 complete    │
 row's       ▼
 value,   fetch_trend() falls back to existing
 as_of    unavailable / presumed-dead handling
   │         │
   ▼         ▼
  cache.write_narrative_point()   no fake point written;
  (real value only)               category shown honestly
                                   unavailable that night
```

## Acceptance Criteria (Testable Outcomes)

1. **`_fetch_live` never returns Google's incomplete current hour as a value.** When the pytrends
   "now 7-d" hourly frame's last row is flagged `isPartial=True`, that row is excluded before picking
   the most recent point.
   - proven by: `test_fetch_live_drops_partial_hour_row` (new, `api/tests/data/test_pytrends_adapter.py`)
   - strategy: Fully-Automated

2. **When every available row is partial (no complete hour exists yet), the fetch behaves exactly
   like today's "no usable data" case** — returns `(None, None)`, and `fetch_trend` falls into its
   existing `unavailable` / `presumed-dead` logic (item 47/47a) rather than writing a fabricated 0.
   - proven by: `test_fetch_live_all_rows_partial_returns_none` (new)
   - strategy: Fully-Automated

3. **When the frame has no `isPartial` column at all** (defensive: some pytrends responses may omit
   it), behavior is unchanged from today — the last row is used as before. This fix only changes
   behavior when `isPartial` is present and true on the row that would otherwise be picked.
   - proven by: `test_fetch_live_no_ispartial_column_unchanged` (new)
   - strategy: Fully-Automated

4. **No regression to existing pytrends/narrative consumers.** `snapshot_narrative.py`'s own test
   suite, `trigger.py`'s narrative-category computation, and `/narrative` dashboard history all
   continue to pass unchanged, since they consume `fetch_trend`'s already-existing return contract
   (value/as_of/status) and either mock `_fetch_live` directly or only observe its public output.
   - proven by: existing `api/tests/scripts/test_snapshot_narrative.py` full pass (all cases,
     unmodified) + full `pytest api/ -q` regression run
   - strategy: Fully-Automated

5. **Already-archived zero-valued points are left untouched — no retroactive correction.** This fix
   changes behavior going forward only; it does not rewrite, delete, or flag any existing cached
   narrative point. This mirrors the stance already taken for the separate, permanently-lost
   2026-09-25 narrative-point gap (cron-timing fix, no backfill attempted).
   - proven by: no code path in this fix touches `cache.write_narrative_point`'s existing rows,
     `read_narrative_history`, or any cache file under `api/data/cache/narrative/` — confirmed by
     the diff's touchpoint list containing only `pytrends_adapter.py` (+ its new test file)
   - strategy: Agent-Probe (reviewer confirms the diff touches no cache read/write/migration code)

6. **This fix does not interfere with `narrative-v2` RFC-3's planned batched multi-keyword fetch.**
   RFC-3 (not started, blocked behind RFC-2) adds a new, additive batched-fetch function to
   `pytrends_adapter.py` and changes the nightly job's call site to use it later. This fix only
   modifies the existing single-keyword `_fetch_live` internals (the isPartial-row selection) and
   does not change `_fetch_live`'s function signature, its call sites, or the module's public
   surface, so RFC-3's future additive work is unaffected when it lands.
   - proven by: diff review confirms `_fetch_live(keyword: str) -> tuple[float | None, str | None]`
     signature and all call sites (`fetch_trend`, `snapshot_narrative.py`) are unchanged
   - strategy: Agent-Probe (reviewer/diff check — no automated contract test exists for a
     not-yet-built RFC-3 function)

## Out Of Scope

- **`narrative-v2` RFC-1 through RFC-7** — the unified config file, RFC-3's batched multi-keyword
  pytrends fetch, momentum view, and social-mindshare view are a separate, already-scoped plan
  (`narrative-v2_25-09-26`, RFC-1 in progress). This SPEC does not touch that plan or its files.
- **The 2026-09-25 unrecoverable narrative-point gap.** Already closed by the cron-timing fix
  (`snapshot-cron-timing_27-09-26`); no further action.
- **Retroactively correcting or backfilling already-archived zero-valued points.** Explicit decision
  in AC-5: leave existing history as-is, honestly dated.
- **Switching to a daily-aggregate value instead of an hourly point** (candidate fix (b) from the
  original backlog note). This is a larger semantic change to what a "point" means for pytrends
  (would need a new source-status/scale flag akin to `mixed_scale`) and is not chosen by this SPEC —
  it's a candidate INNOVATE may consider, but the SPEC's acceptance criteria are written against the
  simpler drop-partial-rows pattern already proven correct elsewhere in this codebase
  (`backfill_pytrends_history.py`), which does not require this bigger change.
- **Any change to `trigger.py`'s known, separately-tracked category-id-vs-keyword keying bug.**
  Already identified, already deliberately deferred (see `all-context.md` Open Questions), and
  unrelated to this fix — that bug is about which cache key is *read*, this bug is about what value
  gets *written*.
- **Any change to `api/scripts/backfill_pytrends_history.py`.** It already handles this correctly;
  cited only as precedent, not touched by this fix.
- **UI/dashboard changes.** No `/narrative` component, API model, or router change is in scope.

## Constraints

- Must not change `_fetch_live`'s function signature or its call sites (`fetch_trend`,
  `snapshot_narrative.py::snapshot_pytrends`) — required for AC-6's RFC-3 non-interference.
- Must not require live network access to test — the existing test suite mocks
  `TrendReq`/`_fetch_live`'s return; the new unit tests must use synthetic DataFrame fixtures (same
  shape as `backfill_pytrends_history.py`'s own isPartial-drop tests), matching this repo's
  `integration`-marker convention (real-network tests are deselected by default).
- Must not modify `api/tests/scripts/test_snapshot_narrative.py` — those tests already mock
  `_fetch_live`'s return value directly and should not need to change for an internal fix.
- Must not touch `cache.write_narrative_point()`, `read_narrative_history`, or any existing archived
  cache file — this is a forward-only behavior fix (Constraint mirrors AC-5).
- Fix belongs in `narrative-mindshare/`, not `process/general-plans/`, per this repo's existing
  ownership split (narrative surfaces are documentation-owned by `narrative-mindshare/` since the
  narrative-dashboard program; see `all-context.md`).

## Open Questions

None. (Retroactive-correction stance resolved in AC-5/Out-Of-Scope: leave existing archived points
as-is. Candidate-fix choice between drop-partial-rows vs. daily-aggregate deferred to INNOVATE, with
this SPEC's acceptance criteria written against the drop-partial-rows outcome since it has a proven
precedent in this codebase and satisfies all ACs without a larger semantic change.)

## Background / Research Findings

From this session's RESEARCH phase (treated as ground truth):

- **Root cause**: `api/data/pytrends_adapter.py:50-74`, `_fetch_live` takes `df.iloc[-1]` of Google
  Trends' hourly `"now 7-d"` frame with no `isPartial` filtering. The last row is frequently the
  current, incomplete hour, which is often 0 or heavily under-counted.
- **Confirmed real damage**: nightly archived points show `memecoins` and `RWA` writing 0.0 on every
  nightly snapshot since 09-24/09-26; only `ai` gets real nonzero values
  (`pytrends-partial-hour-zeros_NOTE_27-09-26.md`). Google Trends keeps no history, so each affected
  night's real value is permanently lost.
- **A working fix pattern already exists in this codebase**: `backfill_pytrends_history.py:102-113`
  (`daily_points`) already drops `isPartial` rows (`work = work[~partial]`) for its 269-day
  daily-window backfill path — read directly and confirmed during this SPEC session. This is
  candidate fix (a) from the original backlog note, already proven, not a new invention.
- **Blast radius / consumers confirmed by direct read**: `snapshot_narrative.py::snapshot_pytrends`
  (nightly caller of `_fetch_live` via `fetch_trend`), `trigger.py:199`
  (`compute_narrative_categories`), `history.py` (`/narrative` dashboard consumer). `mixed_scale` in
  `history.py`'s composite logic is driven by backfilled-vs-nightly source variant
  (`point_status == BACKFILLED_STATUS`), not by isPartial/hour-completeness — confirmed not touched
  by this fix.
- **Cache write path**: `cache.write_narrative_point()` (`api/data/cache.py:376-388`) is
  dedup-on-date, one row per calendar day, keyed by keyword for pytrends — already correct, unrelated
  to the separately-fixed 2026-09-25 keying bug.
- **Existing tests**: `api/tests/scripts/test_snapshot_narrative.py` monkeypatches `_fetch_live`
  directly — confirmed this fix does not require updating those tests. No
  `api/tests/data/test_pytrends_adapter.py` exists yet for `_fetch_live` itself — confirmed zero test
  coverage of the actual bug today.
- **Explicit non-overlap with `narrative-v2` (confirmed by reading `narrative-v2_PLAN_25-09-26.md`
  this session)**: RFC-3 ("Multi-keyword blending + anchor-chained pytrends batching") is NOT
  STARTED, depends on RFC-2 (also NOT STARTED). RFC-3's own plan text (ADR-3, Touchpoints) confirms
  it adds a *new, additive* batched-fetch function to `pytrends_adapter.py` and changes
  `snapshot_narrative.py`'s nightly call site to use it — the existing single-keyword path is
  preserved as a fallback per RFC-3's own design. This fix's narrower scope (only `_fetch_live`'s
  internal row-selection) does not conflict with or block that future work.
- **User decision, this session**: fix now, independent of `narrative-v2`, because the data loss is
  live, ongoing, and unrecoverable, and RFC-3 (which would also touch this file) is blocked behind
  RFC-2 and not imminent.
- Source files read directly to confirm findings before writing this SPEC:
  `api/data/pytrends_adapter.py`, `api/scripts/backfill_pytrends_history.py`,
  `process/general-plans/backlog/pytrends-partial-hour-zeros_NOTE_27-09-26.md`,
  `process/features/narrative-mindshare/active/narrative-v2_25-09-26/narrative-v2_PLAN_25-09-26.md`,
  `process/context/all-context.md`, `process/context/tests/all-tests.md`.
