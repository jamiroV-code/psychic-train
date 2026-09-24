# RFC-001 Phase Report — LiqTide raw archive + history backfill

**Date**: 24-09-26
**Plan**: `regime-dashboard_PLAN_24-09-26.md`
**Status**: 🔨 CODE DONE — not ✅ VERIFIED until Step 4 runs on the user's PC and the scheduled task produces a next-morning file

## What changed

| File | Change |
|---|---|
| `api/data/cache.py` | `read_liqtide_history` reads with `union_by_name=true` (old rows lack the new columns → NULL). New: `liqtide_raw_path`, `write_liqtide_raw` (append-only, atomic tmp→rename), `read_liqtide_raw`, `list_liqtide_raw_dates`, `liqtide_backfill_path`, `write_liqtide_backfill` |
| `api/data/liqtide_adapter.py` | `LiqTidePayload` gains `tide_value` (0–100) + `tide_label` (defaulted, after `raw`); parsed from `tide_index.value/label`; appended as the last two archive-row columns; `fetch_latest` also writes the verbatim raw JSON on a fresh, non-dry-run fetch |
| `api/scripts/snapshot_liqtide.py` | prints `tide_value`/label; warns if the raw file wasn't written; `--coverage` shows raw-JSON day count |
| `api/scripts/backfill_liqtide_series.py` | new — raw payload → `cache/liqtide/backfill/{date}.parquet` (`series_key, date, value`) |
| `api/tests/data/test_liqtide_raw_archive.py` | new, 13 tests, all on `isolated_cache` |
| `api/tests/scripts/test_backfill_liqtide_series.py` | new, 8 tests, all on `isolated_cache` |

## Deviation from plan

- Backfill path is `cache/liqtide/backfill/{date}.parquet`, not `cache/liqtide/backfill_{date}.parquet`:
  `read_liqtide_history` globs `liqtide/*.parquet`, so a file beside the daily rows would have been
  read as an archived day. A test pins this (`test_backfill_not_read_as_a_daily_payload`). Plan updated.
- Adding columns required `union_by_name=true` in `read_liqtide_history`; without it DuckDB would
  reject the mix of the existing 2026-09-20 row and new rows.

## What was tested (in the cloud sandbox, Python 3.11, copy of `api/`)

- Baseline before changes: **182 passed, 1 deselected** (the 179 in all-context + 3 tests needing
  `web/lib/types/screener.ts` and a watchlist; sandbox used `watchlist.example.json`).
- New tests: **21 passed**. Full suite after changes: **203 passed, 1 deselected**.
- Real-file check: your archived `2026-09-20.parquet` + a new-schema row read together →
  `tide_value` NaN for 09-20, 52.0 for the new row; `build_full_composite()` still runs.
- Sandbox cache tree checked empty after the run (no fixture leakage).
- Not run: anything against live LiqTide (sandbox egress blocks liqtide.com) — that's Step 4 below.

## Step 4 — run on your PC (from the repo root)

```powershell
uv run --project api pytest api/ -q
uv run --project api python api/scripts/snapshot_liqtide.py
uv run --project api python api/scripts/snapshot_liqtide.py      # second run: must not overwrite
uv run --project api python api/scripts/backfill_liqtide_series.py
uv run --project api python api/scripts/snapshot_liqtide.py --coverage
uv run --project api python -c "import duckdb; print(duckdb.sql(\"select series_key, min(date), max(date), count(*) from 'api/data/cache/liqtide/backfill/*.parquet' group by 1 order by 1\"))"
```

Expected: pytest green (≈200 passed); snapshot prints `tide_value 52.0`-ish with a label and a
`raw archive` path, exit code 0; the second run prints the same and does not change the file;
backfill lists `tide_value` from 2024-09-04 (≈112 points), `btc_dom` from 2025-06-10, etc.

**Update 24-09-26:** no Task Scheduler job is needed — `.github/workflows/liqtide-snapshot.yml`
already snapshots daily at 23:30 UTC and commits the archive (09-21 … 09-24 captured). The
instructions below are kept only as a fallback.

Fallback — scheduled task (Ops Runbook): `where uv` → Task Scheduler → daily **03:00** →
program = that full `uv.exe` path, arguments `run --project api python api/scripts/snapshot_liqtide.py`,
start in = repo root, tick "Run task as soon as possible after a scheduled start is missed".

## Verification checklist

- [ ] Manual test passed (Step 4 commands)
- [ ] Data verified (DuckDB coverage output pasted here)
- [x] Error handling confirmed (HTTP 500, malformed JSON, dry run → nothing written; tests)
- [ ] User confirmed working (the next GitHub Actions snapshot commit includes `raw/{date}.json`)

**What's Functional Now**: every future LiqTide fetch keeps the full payload; the 0–100 index is
stored; ~2 years of published weekly index + thinned metric history can be extracted.
**Ready For**: RFC-002 (component maths) once the checklist above is ticked.
