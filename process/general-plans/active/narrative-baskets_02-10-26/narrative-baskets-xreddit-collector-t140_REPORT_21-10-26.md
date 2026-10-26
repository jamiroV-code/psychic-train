---
name: report:narrative-baskets-xreddit-collector-t140
description: "T140 worker report: slice W8b (pure collector core) of the X and Reddit PC collector, with the T147 review fixes."
date: 21-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: report
---

# T140 report: W8b pure collector core (round 2: T147 review fixes, 22-10-26)

## 1 Task ID

T140 = slice W8b of `narrative-baskets-xreddit-collector_PLAN_21-10-26.md` (PLAN and SPEC on branch
`claude/t126-xreddit-collector-spec`, PR #153, read with `git show`). Branch `claude/t140-w8b-collector-core`,
draft PR #161. Round 2 applies the independent review T147 (verdict MERGE AFTER SMALL FIXES), relayed by the
planner on 22-10-26.

## 2 Outcome

done (round 2: every REQUIRED and CARRY item fixed, red first; DEFER items listed under heading 10)

## 3 Summary

Round 1 built the W8b rows of PLAN section 3, all pure (no network import): `density.py` (SPEC A.1),
`pc_pace.py` (trickle, persisted budget/adaptive/pause state, queue, `run_x_unit`), `web_queries.py` +
`api/data/attention_queries.json` (config block and validator), `web_evidence.py` (sidecar, `commit_day`),
`pc_adapter.py` (Protocol, errors, fake, `SafeAdapter`, pinned SHA, 15 USD meter, log helper) and the
`probe_pc_sources.py` skeleton.

Round 2 (T147):
- B1: `commit_day` now takes `canary_ok` and `trailing_median` as required keyword arguments and stores only
  what `density.finalize` returns; the `value=` override is gone. A rejected zero or a missing day writes
  nothing (no value, no evidence row).
- B1b: `finalize` returns None for a non-finite or negative value, so NaN, inf and negatives are never stored.
- M1: `run_x_unit` rejects a bad `page_size` before any load; a page with more posts than `page_size` is counted
  in full (the real count), stops X for the UTC day and stores nothing (`page_overrun`).
- M2: the counted day is never earlier than the newest day seen (`PcSource._today`), so a clock moved back
  never reopens the budget, and a pause runs to the end of that later day; the meter keeps the later month.
- M3: `PcSource.earliest_next(min_s)`; `run_x_unit` returns `too_early` without calling the adapter until
  the configured minimum delay has passed since the last unit or attempt (persisted across a restart).
- L1: the evidence row (now carrying `value`) is written before the series value; a value lost between the two
  writes is restored from the row on the next call.
- L2: a `self_repair()` that raises spends the rest of the month's cap, then re-raises.
- L4: a state file that exists but is empty, unreadable, has missing/extra keys or a bad field (for example a
  negative or non-int `used`) raises `PcStateError` (fail closed); the meter treats such a file as the cap
  spent. W8e must pause the source on `PcStateError` and never reset the file (documented in `pc_pace.py`).
- L7: `describe_error` and `log_failure` never raise (a raising `status` property, an int subclass with a
  planted `__str__`/`__format__`, a non-str source, a logger that raises).
- L8: guards are now functions with planted-input tests: banned names, network imports (adds `ssl`, `asyncio`,
  `http`, `importlib`, dynamic `import_module`/`__import__`/`exec`/`eval`/`compile`) and fixed hours (adds
  `strftime('%H')`, `timetuple()`, `hour=`/`minute=` keywords, non-midnight `datetime(...)`).

## 4 Files changed

All new (relative to main): `api/data/attention/{density,pc_pace,web_queries,web_evidence,pc_adapter}.py`,
`api/data/attention_queries.json`, `api/scripts/probe_pc_sources.py`,
`api/tests/data/attention/test_{density,pc_pace,web_queries,web_evidence,pc_adapter}.py`,
`api/tests/scripts/test_probe_pc_sources.py`, `api/tests/tooling_guards/test_pc_collector_guards.py`, and this
report. Round 2 touched `density.py`, `pc_pace.py`, `web_evidence.py`, `pc_adapter.py`, their tests, the guard
file and this report. No `.github/`, `api/pyproject.toml`, `api/uv.lock` or `api/data/cache/` change.

## 5 Commits

Round 1: e1c73fe (core), 6c94380 and ee56a53 (report), 2146853 (first review fixes). Round 2: 0e789ef (merge
commit of `origin/main` 9d38000), 04c7f90 (T147 fixes), 0c29206 (merge commit of `origin/main` 9c128cc),
then this report and a trailing-blank-line fix. No rebase, no force-push.

## 6 Tests run

All `UV_FROZEN=1 uv run --project api pytest ... -q`. Baselines: fresh `origin/main` 9c128cc (PR #153 now merged),
measured on 23-10-26 in a separate worktree. Round-2 gate run started 2026-10-23T09:19:37Z on the final tree
(main 9c128cc merged in). An earlier round-2 run against main 9d38000 gave the same deltas (+118 everywhere).

| Gate | Fresh main 9c128cc | This branch (main merged + fixes) |
|---|---|---|
| Red first, round 2 (7 slice files, new tests before the fixes) | n/a | 24 failed, 94 passed |
| Slice tests | n/a | 118 passed (98 + 20 round-2 tests) |
| `api/tests/analytics/attention` | 280 passed, 1 failed (known) | 280 passed, 1 failed (same known test) |
| `api/tests/scripts api/tests/data/attention api/tests/tooling_guards` | 603 passed | 721 passed (603 + 118) |
| Full API (once) | 1874 passed, 1 skipped, 5 deselected, 1 failed (known) | 1992 passed (1874 + 118), 1 skipped, 5 deselected, 1 failed (same known test) |
| File set `git diff --name-only origin/main...HEAD` | | the 14 files plus this report; forbidden paths 0 |
| `git diff --check origin/main...HEAD`, secret scan (G8 pattern), banned-name grep, no-network-import grep | | all print nothing |
| `ruff check --line-length 120` on the 13 Python files | | all checks passed |

Known failure on main, not this PR's: `api/tests/analytics/attention/test_weights_v2.py::
test_committed_frozen_snapshots_match_their_days_weights` (T130 area, being fixed by T150 per the planner).

Mutation checks, round 2 (each break reverted; `git status` clean after): 24 of 24 caught, one or more per new
test: finalize bypassed (2 tests), defaults given to `canary_ok`/`trailing_median`, finite check removed,
repair removed, overrun check removed, page-size check removed, `_today` without max, pause end from the raw
clock, too-early check removed, min delay hard-coded to 180, unreadable file loaded as fresh, `used` check
removed, extra keys allowed, meter month equality only, no exhaust on a raising repair, unreadable meter as 0,
raising `status` unguarded, int subclass printed raw, `ssl`/`asyncio`/`importlib` roots removed, dynamic-call
check removed, `timetuple` removed, hour-format check removed, banned-name match removed. Round 1 mutations:
9 of 9 caught (no halving, no pause check, no restart min delay, no warn, posts not counted, no owner-pause
guard, no rotation sort, no attempt stamp, no fail-closed cost).

## 7 Tests NOT run

No provider, API Anything or live network call (none exists in W8b). Owner probes needed by this slice: none.

## 8 Deviations

- Round 2 changes two contracts later slices will call: `commit_day(..., result, *, canary_ok, trailing_median,
  now, method, backfilled=False)` (no `value=`), and `EvidenceRow` gains `value`. `UnitOutcome.stop` gains
  `too_early` and `page_overrun`. No caller exists outside the tests yet.
- `page_overrun` stops X for the rest of the UTC day but is not a warning (no pause, no halving): it is an
  adapter defect, not a provider signal. The overrunning page itself is counted in full against the budget.
- Round 1 deviations stand: Reddit 150/day and 60-120 s from the latest SPEC; `reddit_sample_min` 10 in the
  config; extra SPEC keys `x_page_gap_*` and `x_backfill_days`; per-coin `cashtag_only`; budget cut with
  k >= N_min uses the page-cap formula; no parser (Annex H vs PLAN section 3); AC23 and AC28 pure parts only.

## 9 Blockers

None for W8b. Risks:
- Live behaviour is unproven until the W8c/W8d probes; W8d/W8e still have to wire `run_x_unit`, handle
  `PcStateError` as a pause and pass each unit's end time to `next_due`.
- PLAN R-3 relies on `api/data/cache/*` being git-ignored, but `.github/workflows/attention-refresh.yml`
  (lines 158 and 253) runs `git add -f api/data/cache/attention/`, which would also stage `_pc_state/` and
  `<source>/_meta/` if they ever existed on the runner. They do not today. W8e and the later "how PC values
  reach the repo" decision must keep it that way, or narrow that `git add` (a `.github/` edit, owner approval
  first). Not changed here: `.github/` is a hard stop.

## 10 Follow-up

DEFERRED from T147 (as the planner listed them; details in the T147 review): L3, L5, L6 (W8d provenance), L9,
L11, and L10: the coin names and ambiguity lists in `api/data/attention_queries.json` need the owner's review;
on Reddit ETC, LINK, NEAR, HYPE, PI, PUMP, GT and CC are ordinary words. W8c can start on this core. PR #153 has
merged, so the PLAN and SPEC are on main.

## 11 Context and cost

Round 1: CLAUDE.md, envelope, PLAN (sections 2-8), SPEC (Locked pacing rules, AC list, Annexes A-D, H),
`store.py`, `attention_narratives.json`, `trends_keywords.py`, `narratives.py`, `cache.py`, tooling guard
helpers, master-planner.md section 9, `.github/workflows/attention-refresh.yml` and `ci.yml` (read only).
Round 2: the T147 findings as relayed by the planner; no new docs. Cost: unmeasured here (no meter visible in
this session); the planner put the slice at about 8.6 USD at the start of round 2, with a needs_input stop at
12 USD.
