# Phase Report — Weekly OHLC Anchor (ADR-5)

**Date**: 19-09-26
**Plan**: `process/general-plans/active/momentum-screener_17-09-26/weekly-ohlc-anchor_PLAN_19-09-26.md`
**Status**: ✅ VERIFIED — 155 passed, 0 failed, 1 deselected (baseline 135; 148 after ADR-5, 155 after ADR-6)
**Phases run**: RESEARCH → INNOVATE → PLAN → EXECUTE → EVL → UPDATE PROCESS → (ADR-6 supplement cycle: DEBUG → EXECUTE → EVL → UPDATE PROCESS)
**SPEC**: skipped — inner-loop item under `momentum-screener_SPEC_17-09-26.md`

---

## Outcome

`_derive_weekly_from_daily` used a bare `resample("W")`. Pandas reads that as `W-SUN`,
`closed="right"`, `label="right"`. Now `W-MON`, `closed="left"`, `label="left"`.

| | Before | After |
|---|---|---|
| Weekly bar label | week's **close** (Sunday) | week's **open** (Monday) |
| Offset vs exchange convention | +6 days | 0 |
| Newest bar on a mid-week day | stamped in the **future** | stamped at the current week's Monday |
| OHLCV values per bucket | correct | unchanged — identical |
| Weekly anchor **in UTC** | Sunday (label +6d) | Monday 00:00 UTC |
| Cached timestamp timezone | machine-local (`Europe/Brussels`) | UTC, pinned at the read |
| Week length across a DST change | 167 or 169 hours | always 168 |
| `1w` output value tests | none | 20 (13 ADR-5 + 7 ADR-6) |
| Backend suite | 135 passed | 155 passed |

---

## The finding that matters most

**The backlog stub's headline fear did not happen, and the record now says so.**

The stub predicted that a wrong week anchor meant "every weekly RSI reading in the dual-timeframe
filter is shifted by a period." It was not. `resample("W")` — right-closed, right-labelled — groups
Monday through Sunday, the *same* membership `W-MON`/left/left produces. Verified directly:

```
naive.reset_index(drop=True).equals(anchored.reset_index(drop=True))   →  True
(naive.index - anchored.index).unique()                                →  [Timedelta('6 days')]
```

Weekly RSI and the 60-period SMA run over the close **sequence**, which never moved. No momentum
PASS/FAIL was ever wrong from this. What was wrong was chart x-placement and any cross-timeframe
date join.

The severity moved rather than vanished: the trailing partial week was labelled with its
not-yet-reached right edge, so on any day before Sunday **the newest weekly bar carried a future
timestamp** — with daily bars through Sat 2026-09-19, the old code emitted a bar dated Sun
2026-09-20. That is the defect this work actually fixed.

A third stub claim was simply wrong: the `_cache_is_fresh` suspicion. `fetch_ohlcv` returns from
its `1w` branch before that check is reached, so `1w` re-derives on every call and
`_TIMEFRAME_SECONDS["1w"]` is dead for that purpose. Annotated in place so it isn't re-chased.

## The second defect, and why the first fix looked complete

ADR-5 shipped green and the live weekly series was **still wrong**. `check_weekly_anchor.py` kept
reporting `Sun` and that was read as a stale cache rather than as a second defect.

DuckDB converts a TIMESTAMP WITH TIME ZONE to the *session* timezone on read, defaulting to the
machine's local zone. So `_raw_to_df`'s UTC timestamps came back as `Europe/Brussels`, daily bars
read at 01:00/02:00 instead of 00:00, and `resample("W-MON")` anchored on Brussels midnight:

```
weekly label as stored   2026-09-14 00:00:00+02:00   Mon
the same instant in UTC  2026-09-13 22:00:00+00:00   Sun
```

Monday-anchored locally is Sunday-anchored in UTC, and an exchange weekly opens Monday 00:00 UTC.
The fix had moved the error from six days to two hours, not removed it. ADR-6 pins every cache
read to UTC.

Three things make this worth more than its two hours:

- **DST moved the anchor**: Brussels midnight is 22:00 UTC in summer, 23:00 in winter, so one week
  each spring and autumn was 167 or 169 hours long.
- **It was not weekly-specific** — every reader in `cache.py` was returning local time.
- **The data's meaning depended on the reader's timezone.** Two machines, same Parquet files,
  different weeks. For a tool intended to open to the public later, that is the real defect.

**The 13 ADR-5 tests could not have caught it.** Every one calls `_derive_weekly_from_daily`
directly on tz-aware UTC fixtures. The conversion happens one layer below, in the Parquet round
trip. The coverage was genuine, hand-computed and thorough, and it sat above the boundary where
the data actually changed. `test_cache_timezone.py` crosses that boundary on every assertion.

## Process failures, recorded

1. **VERIFIED was declared over a broken product.** 148 passed was true of the suite and false of
   the product, and the plan said VERIFIED without that distinction.
2. **A prediction was asserted, contradicted by evidence, and the evidence was explained away.**
   "Caches self-heal on the next board request" was wrong — a running uvicorn holding the pre-fix
   import kept rewriting them with the old anchor. The first STALE report was that, and it was
   read as the user not having loaded the board.
3. **A new diagnostic gave a false all-clear and was believed over a correct older check.**
   `check_weekly_anchor.py` evaluated weekdays in UTC and said `Sun`, accurately, for hours.
   `diagnose_weekly.py`, written to investigate, read the *local* weekday, said `Mon`, and printed
   "Nothing wrong". The newer, more elaborate tool won on nothing but novelty. Both now evaluate
   in UTC and print both columns, and `all-tests.md` rule 6 records the general form: when two
   checks disagree, believe the one encoding the external contract.

## What the process caught that a straight fix would not have

**A live-data hazard, found by reading the `1w` path rather than by any gate.**
`test_weekly_recursion_does_not_deadlock` drove the real cache-first path with no cache
redirection: it merged a fixture bar into the user's live `BTC/1d.parquet`, and `write_ohlcv`
overwrites the whole series. This is the RFC-005 watchlist incident's twin — there a default
argument bound the real path at import, here a module constant was simply never redirected. A
suite of 135 green tests had been quietly corrupting real market data.

Fixed with an opt-in `isolated_cache` fixture in a new `api/tests/conftest.py`, and **confirmed
by external evidence rather than by the suite's own word**: `BTC/1d.parquet` carried mtime
`1789822271845` before the run and `1789822271845` after it. Had the monkeypatch failed to bind,
that file would have been overwritten.

**The sixth Standing Lesson entry, and the only one no shim caused.** The previous five green-but-
wrong incidents all came from sandbox shims or a fixture that isolated nothing. This one is
different and worth its own rule: the `1w` path already *had* coverage — including a concurrency
test proving it did not deadlock — and none of it looked at the output values. A gate that asks
"does it crash?" passes identically whether the arithmetic is right or wrong.

## Deviations

1. **`api/tests/conftest.py` added** — not in the stub's scope; required, because the end-to-end
   test drives `fetch_ohlcv`.
2. **`test_ccxt_symbol_resolution.py` edited** — outside the stub's blast radius. Justified: the
   hazard was already in that file and would corrupt real data on the next full-suite run.
3. **`isolated_cache` is opt-in, not autouse.** Autouse would change what every existing
   cache-touching test reads, and at the time that change could not be run. Named residual.
4. **Session had no execution surface.** No `device_bash`; computer-use resolved terminals as
   click-tier (cannot type); the cloud sandbox has pypi and npm blocked (403), so no `pyarrow`,
   `duckdb` or `ccxt`. Code and tests were written unrun, verified in a standalone pandas harness,
   and executed by the user. Recorded because it changes what "verified" meant at each step.
5. **RIPER-5 phases were run inline by the orchestrator.** The `vc-*` subagent types this repo's
   `CLAUDE.md` routes to are not spawnable in Cowork. A protocol deviation from §Orchestrator
   Role, recorded rather than concealed.

## Context updated

- `process/context/tests/all-tests.md` — count 135→148; the `1w` Known Gap closed; sixth Standing
  Lesson row plus a new rule 4 ("does it crash?" is not "is it right?"); rule 3 extended with the
  `isolated_cache` requirement; a debugging row for weekly bars plotted late; the live-cache
  spot-check command.
- `process/general-plans/backlog/weekly-ohlc-golden-values_19-09-26.md` — closed, with its two
  incorrect predictions corrected in place rather than overwritten.

## Residuals carried forward

1. **Week-anchor convention is asserted, not measured.** Monday-open comes from documented
   exchange convention; no native-weekly source was ever queried. The one thing here taken on
   authority. One network call from a machine with egress closes it.
2. **`isolated_cache` is opt-in.** A future test that forgets it passes while overwriting live
   data — it fails by succeeding. The autouse decision is now runnable and should be revisited.
3. **[CLOSED]** Live `1w.parquet` self-healed — after the stale uvicorn was dealt with, not merely
   on the next board request. `BTC/1w.parquet` mtime `1789826031291` postdates the ADR-6 commit
   `1789825921189`, so the file on disk was produced by the pinned code.
4. **Non-OHLCV cache readers are unverified under the UTC pin.** ADR-6 changed liquidity, liqtide,
   narrative and legs reads as well. Suite is green; no test asserts their tz contract.

## Next

- Nothing blocking. `check_weekly_anchor.py` is the standing spot check after any change to
  `cache.py` or the derivation.
- **Cheap and not done**: a tz-contract test for the non-OHLCV readers (liquidity, liqtide,
  narrative, legs). ADR-6 changed their reads too; only OHLCV has an assertion.
- **RFC-005's open observation is now the oldest unexplained thing in this program**: the four
  `1w.parquet` mtimes ~31s later than their siblings, which does not match the fetch order in
  `build_coin_panel`. It lives in the function this plan just rewrote and was not touched here.
- Queued: RFC-006 (frontend `reason` rendering, `getJson` timeout + catch, unify the three dead-data
  renderings); Playwright E2E, unblocked since RFC-005; RFC-001 stub closeout toward archival.
