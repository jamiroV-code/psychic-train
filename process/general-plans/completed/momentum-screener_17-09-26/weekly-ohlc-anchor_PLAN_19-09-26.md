# Weekly OHLC Anchor — SIMPLE Plan

**Date**: 19-09-26
**Slug**: `weekly-ohlc-anchor`
**Origin**: `process/general-plans/backlog/weekly-ohlc-golden-values_19-09-26.md` (raised by RFC-005 VALIDATE cycle 2, gap-resolution D)
**Parent program**: `momentum-screener_17-09-26` — inner-loop RFC, SPEC governed by `momentum-screener_SPEC_17-09-26.md`
**Phases run**: RESEARCH → INNOVATE → PLAN → EXECUTE (inline, see Session Constraints) → EVL (user-run) → UPDATE PROCESS
**Status**: ✅ VERIFIED — 155 passed, 0 failed, 1 deselected, 19-09-26, **after ADR-6**. The earlier 148-passed VERIFIED was premature: it was true of the suite and false of the product. See §ADR-6.

---

## TL;DR

`_derive_weekly_from_daily` used a bare `resample("W")`, which pandas reads as `W-SUN` with
`closed="right", label="right"`. The Monday–Sunday **grouping was already correct**; the **label
was the week's close date**, six days after the exchange convention of stamping a weekly candle
with its open. Fixed to `W-MON` + `closed="left"` + `label="left"`, which produces identical OHLCV
membership and correct labels. Golden-value tests added. The forming week is kept, by decision.

**That was necessary but not sufficient.** With ADR-5 alone the live cache was still wrong: DuckDB
converts TIMESTAMPTZ to the session timezone on read, so daily bars came back `Europe/Brussels`
and `W-MON` anchored on *Brussels* midnight — Monday locally, **Sunday 22:00 UTC**. ADR-6 pins
every cache read to UTC. The 13 ADR-5 tests were green throughout, because none of them crossed
the boundary where the conversion happened.

---

## Session Constraints (recorded, not worked around)

This pass ran in a Cowork session with no execution surface on the user's machine:

- No `device_bash` — no shell on the user's PC. Computer-use resolved terminals as **click-tier**
  (visible and clickable, cannot type), so the terminal route does not run commands either.
- The cloud sandbox has **pypi and npm blocked by egress policy (403)** — no `pyarrow`, `duckdb`
  or `ccxt` available there, so the cached Parquet could not be read and no exchange could be
  queried for an independent weekly cross-check.
- The `vc-*` subagent types this repo's `CLAUDE.md` routes to are **not spawnable in Cowork**
  (available agent types are `general-purpose`, `Explore`, `Plan`, …). RIPER-5 phases were run
  inline by the orchestrator. This is a protocol deviation from §Orchestrator Role, recorded
  rather than concealed.

Consequence for this plan's honesty: every gate below was **written unrun** and handed to the
user to execute. The EVL Results section records the run that closed that gap; the Verification
Evidence section is left as written pre-run, so the record shows what was claimed before the
suite spoke and what the suite actually settled.

---

## ADR-5 — Week anchor convention

**Decision**: weekly bars are anchored Monday-open, left-labelled — `resample("W-MON",
closed="left", label="left")`. The still-forming week is **kept** in the series, labelled with its
Monday like every other bar.

**Rationale**:

- Exchange and charting convention (Binance, TradingView) stamps a weekly candle with its **open**,
  Monday 00:00 UTC. The prior output was six days late against every external reference.
- The forming week is kept so the weekly momentum leg reflects the **current** week. Excluding it
  would stale the weekly RSI/SMA leg by up to six days — a coin that flipped on Tuesday would not
  surface until the following Monday, a real blind spot in a screener checked daily.
- Rejected: an `is_closed` / `partial` column. Most honest, but it is a change to
  `cache.OHLCV_COLUMNS` touching every reader and all four existing Parquet files — blast radius
  well beyond this fix. Revisit if a caller actually needs closed-only weeks.

**Standing Rule 4 carve-out**: "closed bars are immutable" now has one documented exception — the
newest weekly bar is mutable until its week closes. Every earlier bar is immutable, and
`test_a_complete_week_closes_the_forming_bar_without_moving_earlier_ones` proves it.

**Migration**: none needed. `cache.write_ohlcv` overwrites the whole series each refresh, so the
four existing Sunday-labelled `1w.parquet` files self-heal on the next board request.

---

## ADR-6 — Cache reads are pinned to UTC

**Decision**: every DuckDB read in `api/data/cache.py` goes through `_connect()`, which issues
`SET TimeZone='UTC'`. `read_ohlcv` additionally re-asserts the contract in pandas
(`pd.to_datetime(..., utc=True)`), so a future DuckDB that ignores or renames the setting degrades
to a no-op rather than to silently local timestamps. `ohlcv_last_refresh` returns tz-aware UTC.

**The defect**: `_raw_to_df` builds timestamps in UTC, but DuckDB converts a TIMESTAMP WITH TIME
ZONE to the *session* timezone on read, and that defaults to the machine's local zone. Observed on
the user's machine:

```
dtype             datetime64[us, Europe/Brussels]
times of day seen ['01:00:00', '02:00:00']        # daily bars stored at 00:00 UTC
weekly label      2026-09-14 00:00:00+02:00  ->  Mon
same label in UTC 2026-09-13 22:00:00+00:00  ->  Sun
```

**Why it matters beyond the two-hour offset**:

1. **DST moves the anchor.** Brussels midnight is 22:00 UTC in summer and 23:00 UTC in winter, so
   the weekly boundary shifts by an hour mid-year and one week each spring and autumn is 167 or
   169 hours long. Both `01:00` and `02:00` already appear in the cached daily bars for this
   reason.
2. **It is not weekly-specific.** Every series `read_ohlcv` returned was in local time — so was
   every liquidity, liqtide, narrative and legs read.
3. **The data's meaning depended on who ran the code.** Two machines in different timezones read
   the same Parquet files and got different weeks. Unacceptable for the stated intent of opening
   this to the public later.

**Why ADR-5's tests could not catch it**: all 13 call `_derive_weekly_from_daily` directly on
tz-aware UTC fixtures. The conversion happens one layer below, in the Parquet -> DuckDB round
trip. `api/tests/data/test_cache_timezone.py` (7 tests) crosses that boundary on every assertion,
including two parametrised DST-transition cases that assert weekly spacing is a constant 7 days.

**Migration**: none. `write_ohlcv` overwrites the whole series, so caches re-derive correctly on
the next refresh — confirmed: `BTC/1w.parquet` was rewritten after the ADR-6 commit landed.

---

## Findings that correct the backlog stub

The stub predicted "every weekly RSI reading in the dual-timeframe filter is shifted by a period."
Investigation says otherwise, and the record should carry the correction:

1. **Severity is lower than feared on the indicator axis.** `resample("W")` (W-SUN, right-closed,
   right-labelled) buckets Monday through Sunday — the same membership `W-MON`/left/left produces.
   Verified: `naive.reset_index(drop=True).equals(anchored.reset_index(drop=True))` is `True`, and
   the index differs by exactly `Timedelta(days=6)`. Weekly RSI and the 60-period SMA are computed
   over the close **sequence**, which never moved. **No momentum PASS/FAIL was ever wrong from
   this.** What was wrong: chart x-placement and any cross-timeframe date join.

2. **Severity is higher than feared on a different axis.** The trailing partial week was labelled
   with its not-yet-reached right edge, so on any day before Sunday **the newest weekly bar carried
   a future timestamp**. Confirmed empirically: with daily bars through Sat 2026-09-19, the old
   code emits a bar stamped Sun 2026-09-20.

3. **The stub's `_cache_is_fresh` suspicion is wrong.** `fetch_ohlcv` returns from its `1w` branch
   *before* the freshness check at the cache-first path is ever consulted, so `1w` re-derives from
   daily on every call. `_TIMEFRAME_SECONDS["1w"]` is dead for this purpose. Annotated in place so
   the next reader does not re-chase it.

4. **Unrelated live-data hazard found and fixed.** `test_weekly_recursion_does_not_deadlock` drove
   the real cache-first path with no cache redirection: it merged a fixture bar into the user's
   live `BTC/1d.parquet` and `write_ohlcv` overwrote the series. Same defect class as the RFC-005
   watchlist incident (parent plan Deviations #1), which deleted BTC from the live watchlist.

---

## Touchpoints

| File | Change |
|---|---|
| `api/data/ccxt_adapter.py` | `_derive_weekly_from_daily` anchored to `W-MON`/left/left; `WEEK_ANCHOR`/`WEEK_CLOSED`/`WEEK_LABEL` module constants; ADR-5 rationale comment; dead `_TIMEFRAME_SECONDS["1w"]` annotated |
| `api/tests/data/test_weekly_derivation.py` | **new** — 13 tests: golden values, anchor regression, forming-week policy, edges, end-to-end |
| `api/tests/conftest.py` | **new** — `isolated_cache` fixture (opt-in) redirecting `cache.CACHE_ROOT` at `tmp_path` |
| `api/tests/data/test_ccxt_symbol_resolution.py` | two cache-touching tests now request `isolated_cache` (deviation — see below) |
| `api/scripts/check_weekly_anchor.py` | **new** (UPDATE PROCESS) — read-only spot check of the anchor on the *live* Parquet cache, which the isolated-cache tests deliberately say nothing about |
| `process/context/tests/all-tests.md` | count 135→148; `1w` Known Gap closed; sixth Standing Lesson entry + rule 4; debugging row; spot-check command |
| `process/general-plans/backlog/weekly-ohlc-golden-values_19-09-26.md` | closed, with its two incorrect predictions corrected rather than overwritten |
| `api/data/cache.py` | **ADR-6** — `_connect()` (UTC-pinned) replaces all 8 bare `duckdb.connect()` reads; `_as_utc()` re-assert in `read_ohlcv`; `ohlcv_last_refresh` returns tz-aware UTC |
| `api/tests/data/test_cache_timezone.py` | **new (ADR-6)** — 7 tests, every one crossing the Parquet round trip; includes both DST transitions |
| `api/scripts/diagnose_weekly.py` | **new**, then corrected — its first version read the LOCAL weekday and printed a false all-clear over a still-broken cache |
| `api/scripts/refresh_cache.py` | repo-root `sys.path` bootstrap — the documented Ops Runbook command could never have run |

**Blast radius**: `_derive_weekly_from_daily` is called from exactly one place (`fetch_ohlcv`'s
`1w` branch). Every `1w` consumer — `screener_board`, the weekly momentum leg, the board's
timeframe toggle — sees the same values at corrected timestamps. No schema change, no migration.

---

## Deviations from the stub's literal scope

1. **`api/tests/conftest.py` added** (not named in the stub). Required: the end-to-end test drives
   `fetch_ohlcv`, which without redirection writes to the user's real Parquet cache.
2. **`test_ccxt_symbol_resolution.py` edited** (outside the stub's blast radius). Justified: that
   file already had the live-cache hazard in it, discovered while reading the `1w` path. Left
   unfixed it would corrupt real data on the next full-suite run.
3. **`isolated_cache` is opt-in, not autouse.** Autouse across the whole suite would change what
   every existing cache-touching test reads, and that change cannot be run in this session.
   Deliberately not taken. **Named residual** — worth revisiting once someone can run the suite.
4. **No independent-source cross-check performed.** The stub asks for verification "against a
   second independent source (TradingView weekly, or an exchange that publishes native weeklies)".
   Egress policy blocked it. The Monday-open convention is asserted from documented exchange
   behaviour, not measured. **Named residual — the one thing in this plan taken on authority.**

---

## Verification Evidence

**What was actually verified, in this session:**

- Golden values, anchor behaviour and all pure-pandas edge cases were run in a standalone harness
  (pandas 3.0.2) reproducing `_derive_weekly_from_daily` exactly. All assertions pass: golden
  OHLCV for three weeks, all-Monday labels, no future-dated bar, naive-vs-anchored membership
  equality and the exact `+6d` label shift, gap-week membership, Sunday completion leaving weeks
  1–2 byte-identical, single-bar week, empty-schema passthrough.
- `python -m py_compile` clean on all four touched files.

**What was NOT verified and must be run by the user:**

```
cd api
uv run pytest tests/data/test_weekly_derivation.py -v     # the new gate
uv run pytest tests/                                      # full suite — was 135 passed, 0 failed
```

- `test_fetch_ohlcv_1w_writes_monday_labelled_bars_to_the_cache` has never executed — it needs
  `ccxt` and `duckdb`, absent from this sandbox. It is the only test here that touches the real
  adapter path.
- The `isolated_cache` fixture has never executed. If `monkeypatch.setattr(cache, "CACHE_ROOT", …)`
  does not take, the two edited tests in `test_ccxt_symbol_resolution.py` still write to the live
  cache. **Check `api/data/cache/ohlcv/BTC/1d.parquet`'s mtime after the first run.**
- The full suite has not been re-run against this diff. The `conftest.py` addition is the piece
  most likely to surprise — a new `conftest.py` at `api/tests/` is collected for every test below it.

**What this coverage does NOT prove:**

- That Monday-open is the right convention for Hyperliquid specifically (asserted, not measured —
  deviation 4).
- That the four existing `1w.parquet` files have actually self-healed. Predicted from
  `write_ohlcv`'s overwrite semantics; confirm by reading one back after a board request.
- Anything about the RFC-005 "open observation" — the `1w.parquet` mtimes ~31s later than their
  siblings. Untouched here. It lives in the same function and should be looked at next.

---

## EVL Results (19-09-26, run by the user)

```
148 passed, 1 deselected in 10.62s
```

Baseline before this plan was 135 passed / 1 deselected (RFC-005 closeout). The delta is **+13,
exactly the size of `test_weekly_derivation.py`** — no existing test was broken, none was
silently skipped, and the new file contributed every one of its gates. The 1 deselected is the
standing `-m integration` network gate, unchanged.

**The `isolated_cache` fixture is confirmed working, by external evidence.** The two tests it was
added to drive the real cache-first path; before this session `api/data/cache/ohlcv/BTC/1d.parquet`
carried mtime `1789822271845`, and after the 148-test run it still carries `1789822271845`. The
suite did not touch the user's live Parquet cache. Had the monkeypatch failed to bind, that file
would have been overwritten with a single fixture bar — the RFC-005 watchlist incident repeated.
This closes the largest unverified item flagged in Verification Evidence below.

`test_fetch_ohlcv_1w_writes_monday_labelled_bars_to_the_cache` — the one test that had never
executed anywhere, because this session's sandbox lacks `ccxt` and `duckdb` — is inside that 148
and passed.

## ADR-6 EVL (19-09-26)

```
155 passed, 1 deselected
```

148 -> 155 is exactly the 7 new tests. Nothing existing failed, which is the informative part: the
UTC pin moves timestamps for every cached series, so a pre-existing test quietly asserting against
local time would have surfaced here. None did. `BTC/1w.parquet` was rewritten at mtime
`1789826031291`, after the `cache.py` commit at `1789825921189` — the file on disk was produced by
the pinned code.

## Process failures in this plan, recorded

1. **"✅ VERIFIED — 148 passed" was declared over a broken product.** The suite was green, the
   live weekly series was still Sunday-anchored in UTC, and the plan said VERIFIED. The claim was
   scoped to the test run and read as a claim about the product.
2. **The `1w.parquet` self-heal was asserted, then contradicted.** The plan stated caches "self-heal
   on the next board request". In fact a running uvicorn holding the pre-fix import kept rewriting
   them with the old anchor — which is what the first STALE report was, and it was misread as the
   user not having loaded the board.
3. **A diagnostic tool produced a false all-clear and was believed over a correct one.**
   `check_weekly_anchor.py` evaluated weekdays in UTC and reported `Sun` accurately.
   `diagnose_weekly.py`, written afterwards to investigate, read the local weekday, reported `Mon`,
   and concluded "Nothing wrong". The newer and more elaborate tool was trusted over the simpler
   one that encoded the external contract. Both are now UTC-based and print both columns.

## Residuals carried forward (not closed by the green run)

1. **Week-anchor convention is asserted, not measured.** Monday-open comes from documented
   exchange/charting convention, never cross-checked against a native-weekly source. A green suite
   proves the code does what ADR-5 says; it cannot prove ADR-5 matches Hyperliquid. This is the
   single thing in this plan taken on authority. Closing it needs one network call from a machine
   with egress — cheap, and worth doing the next time someone has a shell.
2. **`isolated_cache` is opt-in, not autouse.** A future test that drives `fetch_ohlcv` and forgets
   the fixture will pass while overwriting live data — it fails by succeeding. Recorded as rule 3
   in `process/context/tests/all-tests.md` §Standing Lesson. The autouse decision is now runnable
   (the suite executes) and should be revisited by whoever next touches the test tree.
3. **[CLOSED 19-09-26]** Live `1w.parquet` files have self-healed — but only after the API process
   holding the pre-fix import was dealt with, not merely on the next board request as this plan
   originally claimed. Original text: **Live `1w.parquet` files have not self-healed yet.** Verified: `BTC/1w.parquet` mtime
   `1789823591406` predates this fix landing (`1789823727440`), so it still carries Sunday labels
   from the running uvicorn's old module. Expected to correct on the next board request after an
   API restart. `api/scripts/check_weekly_anchor.py` was added to check this rather than assume it.

4. **Other cached series are unverified under the UTC pin.** ADR-6 changed reads for liquidity,
   liqtide, narrative and legs as well as OHLCV. The suite is green but no test asserts the tz
   contract for those readers specifically. Cheap to add; not added here.

## Resume and Execution Handoff

- **Last completed step**: ADR-6 UPDATE PROCESS. Plan VERIFIED at 155 passed, backlog stub closed,
  `all-tests.md` updated (count 148→155, seventh Standing Lesson entry, rules 5 and 6, two
  debugging rows, a new Known Gap for the unverified non-OHLCV readers, and a new Update Trigger
  for structurally-uncatchable defects).
- **Next step**: nothing blocking. `check_weekly_anchor.py` is the standing spot check; re-run it
  after any change to `cache.py` or the derivation.
- **Then**: the RFC-005 "open observation" is the natural next thread — the four `1w.parquet`
  mtimes ~31s later than their siblings, which does not match the fetch order in
  `build_coin_panel`. It lives in the same function this plan just rewrote and is still
  unexplained. Or resume the queued work: RFC-006 (frontend `reason` rendering, `getJson` timeout),
  Playwright E2E, RFC-001 stub closeout.
