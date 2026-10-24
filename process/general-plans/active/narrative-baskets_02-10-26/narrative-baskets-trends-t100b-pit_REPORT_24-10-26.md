---
name: report:narrative-baskets-trends-t100b-pit
description: "T175 (T100b-PIT, M1 option A): the Discovery history chart reads Trends for day D from the pull archived on D+1 (last row D), snapshot first, never from the replaced live series; missing days stay missing with a reason."
date: 24-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: report
---

# T175 T100b-PIT (point-in-time Trends reads for the Discovery history chart): REPORT

## 1 Task ID

T175 = T100b-PIT, M1 option A from the T149 round 2 report (owner decision 23-10-26). Branch `claude/t175-t100b-pit`, one draft PR to `main`. Base `main` at `015e109` (contains merged #162).

## 2 Outcome

**done**, with one deviation from the file set (heading 8: a 4-line optional parameter in `discovery.py`). No web/ change, no schema change, no `.github/`, no pyproject/uv.lock, no `api/data/cache` file, no network.

## 3 Summary

**The rule (exact).** For chart day D (a UTC date, D <= today-1), Trends is taken from, in order:

1. **Frozen snapshot.** `signals/<D>_w<window>.json` for the chart's own window (7, 30 or 90). If its row for the coin has a `trends` entry, that `change` and `as_of` are used as recorded (authoritative). Only the Trends entry is taken; every other source still reads its store. A record of another window, another coin, or a row without a `trends` entry does not count, and the next step decides. A malformed entry also does not count.
2. **Pull archive.** The pull for D is the one made on **UTC date D+1** (`trends_pull_date(D) = D + 1`), the file `<cache>/attention/trends_pulls/<D+1>.parquet`. `write_pull_archive` keeps only days < pull date, so a complete pull ends on D. It is used only if the coin's **last row in that pull is exactly D**, and then it is gated like any series (at least `min_history_days` rows, i.e. 90).
3. **Otherwise Trends is missing on D**, never 0, and never taken from a later or an earlier pull. The reason sits in `SourceSeries.reason` (internal; the payload has no per-source field, adding one would be a schema change):

| Case | state | reason |
|---|---|---|
| no file for D+1 | unavailable | `no-pull-archive` |
| file unreadable (truncated, not parquet) | unavailable | `unreadable-pull-archive` |
| coin not in that pull (failed the interest rule, rate-limited, ...) | unavailable | `symbol-not-in-pull` |
| last row is not D (Google lagged, pull ends D-1) | unavailable | `pull-last-row-not-day` |
| fewer than 90 rows | insufficient-history | `<n> days in pull` |
| Trends not probed | unavailable | `not-probed` (the snapshot still applies) |

A day with no usable source at all stays omitted, as before. A day with other sources is scored without Trends, its weight rescaled (`covered_weight` drops by 25).

**The live (replaced) Trends series is never read by the chart.** Every other source reads its store exactly as before (test `test_other_sources_unchanged` compares against the old code path, day by day).

**Implementation** (`discovery_history.py`): `_TrendsPulls` reads each pull file at most once per computation (shared by all coins of a category chart); `_PulledTrends` gives it the `_Stored` interface (`at`, `count`), so `_load` swaps it in for the `trends` key only. `_frozen_trends` reads the window's snapshot rows once (`signal_snapshots.read_snapshots`, unchanged). The cache signature now also holds the identity (mtime, size, inode) of the D+1 pull and the snapshot file for every chart day, so a new pull or snapshot invalidates. `history_days["trends"]` now counts the rows of the pull for the last chart day (0 when that pull is absent), not the live series.

**Snapshot semantics are not changed**: `signal_snapshots.py` is not edited, only read; `test_frozen_signals_files_untouched` (hashes) still passes.

**NOT provable here: real archive contents.** The archive only starts filling from the first scheduled Trends run (Trends is still `not-probed` until T100c). What the chart shows until then and just after:

- 0 pulls: no chart day has Trends (unless a snapshot row carries one; today's snapshots are taken before `refresh-extra`, so they normally do not).
- 1 pull (made on P): only day P-1 has Trends.
- 2 pulls (P, P+1): days P-1 and P. Trends then fills one more past day per daily run: a full 30-day window after 30 daily pulls, 90 days after 90. A failed run leaves a permanent hole on that day (never back-filled from a later pull, by design).
- Until today's Trends run has archived its pull, the last chart day (yesterday) has no Trends while live Discovery still shows the previous pull (lag 1). After the run, the last chart day equals live scoring (`test_last_day_matches_live_when_todays_pull_is_archived`).

## 4 Files changed

- `api/analytics/attention/discovery_history.py`: Trends reader (`trends_pull_date`, `_TrendsPulls`, `_PulledTrends`, `_frozen_trends`, reason constants), signature extended, docstring.
- `api/analytics/attention/discovery.py`: `_coin(..., frozen=None)`, 4 lines (heading 8). Default `None` = unchanged behaviour.
- `api/tests/analytics/attention/test_discovery_history_pit.py` (new, 22 tests).
- `api/tests/analytics/attention/test_discovery_history.py`: `test_last_day_matches_live_scoring` also archives today's pull, as the Trends run does (2 lines; the assertion is unchanged).
- `api/tests/data/attention/test_trends_pull.py`: the M1 characterization test is rewritten to the fixed behaviour (`test_replace_revises_live_series_but_not_past_chart_days`): the live series is still revised, no past chart day moves.
- This report.

## 5 Commits

1. `feat(discovery): point-in-time Trends reads for the history chart (T175)`: code and tests.
2. `docs(process): T175 report`: this file.

## 6 Tests run

- Red first: the 22 new tests, before the reader existed: **21 failed, 1 passed**. The pass was `test_last_day_matches_live_when_todays_pull_is_archived` (old code read the live series, which equals today's pull there). The failures were the expected ones: the live store gave Trends on only 11 of 30 days, later pulls leaked into day D, snapshot days were ignored.
- Named tests: `test_chart_day_d_reads_pull_d_plus_1`, `test_chart_never_reads_later_pull`, `test_pull_without_last_row_d_is_missing`, `test_absent_pull_is_missing_not_zero`, `test_snapshot_wins_over_archive`, `test_other_sources_unchanged`, plus `test_no_look_ahead_over_several_pulls` (property test, 8 seeds: ~37 daily pulls each that rescale, revise 5 past values, drop coins at 10% and whole pulls at 10%; each day D must equal the value from pull D+1 and must be identical when only pulls <= D+1 exist). Also: reasons/gate boundary (90 ok, 89 not), unreadable pull, not probed, snapshot window and coin isolation, snapshot without archive, cache invalidation, history_days, category chart.
- Mutation check, 14 mutants on the new code (pull date D+2, pull date D, no last-row check, later pull, live store for Trends, snapshot ignored, snapshot any window, signature without pulls, signature without snapshots, gate off by one, probe ignored, absent pull as empty, `frozen` branch removed in `_coin`, count from live): **14 killed, 0 survived**. A first run had 2 survivors: a symbol filter in `_frozen_trends` (equivalent mutant: lookups are keyed by symbol; the filter was removed) and the 90-row boundary (a boundary test was added).
- `pytest api/tests/analytics/attention api/tests/data/attention api/tests/scripts`: **974 passed**.
- Full `pytest api`: **2042 passed, 1 skipped, 5 deselected** (network tests opt-in).
- `ruff check` on the 5 touched files: 5 findings, the same 5 as on `main` (I001 x3, TRY004 x2 in untouched lines); 0 new.
- `git diff --check`: clean. Secret scan of the diff (key, secret, token, password, bearer, sk-): nothing. File set: only the files in heading 4.

## 7 Tests NOT run

- Real archive contents and a real chart over real pulls: impossible here (heading 3, no pull exists yet).
- Web tests: no web/ change.

## 8 Deviations

- **`discovery.py` edited** (outside the named file set): `_coin` gains `frozen=None`, a map source -> `DiscoverySource` used instead of recomputing that source. Without it "snapshot wins" would need a copy of `_coin`'s aggregation in `discovery_history.py`, which breaks its promise to score "exactly like live scoring". Live scoring never passes it; the full suite is unchanged; the mutant removing the branch is killed. The planner can ask to undo it (then: drop snapshot-first, archive only).
- **Snapshot-first is per source (Trends), not per day.** Taking the whole snapshot day would be option B (changes every source's chart path), which the owner did not choose. A snapshot row without a Trends entry falls back to the archive (snapshots are taken before `refresh-extra`, so most lack Trends).
- The snapshot's Trends entry is used even when Trends is not probed now: it is a frozen record of what was scored that day.
- Missing reasons are internal (no payload field), to avoid a schema change.

## 9 Blockers

None.

## 10 Follow-up

- When T100c records the Trends probe, check after the first two runs that `trends_pulls/` holds one file per run date and the chart shows Trends on exactly those days.
- Snapshot after `refresh-extra` (the existing LIMITATION in `signal_snapshots.py`) would let snapshots carry same-day Trends; not needed for correctness here.

## 11 Context cost

Read: CLAUDE.md, the envelope, the T100b PLAN (M1/point-in-time lines), the T149 r2 report heading 9 (M1 options), r4 report headings (format), `discovery_history.py`, `store.py`, `signal_snapshots.py`, `discovery.py` (`_source_change` .. `_coin`, `series_names`), `types.py`, the router (windows), the history and trends-pull tests. Extra docs beyond the envelope: `process/context/operating-instructions.md` (grep only, for the `uv run --project api` test command); `api/data/attention/types.py`, `api/models/discovery.py` and `api/routers/discovery.py` (short reads). Not opened: master-planner.md.
