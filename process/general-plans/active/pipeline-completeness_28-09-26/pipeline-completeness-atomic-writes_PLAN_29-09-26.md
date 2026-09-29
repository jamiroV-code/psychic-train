---
name: plan:pipeline-completeness-atomic-writes
description: "Make every parquet write in api/data/cache.py atomic (temp in same dir, fsync, os.replace) — prerequisite of P2 automatic resume (deployability SPEC OQ9/OQ10, AC12)"
date: 29-09-26
feature: none (general-plans, P1 lane)
---

# Atomic parquet writes in `api/data/cache.py` — PLAN (SIMPLE)

TL;DR: add one private helper `_atomic_to_parquet(df, path)` to `cache.py` (unique temp file in the same directory → write → fsync → `os.replace`; temp removed on any exception) and route the 9 existing `to_parquet(` call sites through it. Add one `api/tests/data/test_cache_atomic_writes.py` (isolated, offline). Add one `.gitignore` line so a leftover temp from a hard kill can never be committed by the nightly workflows. No refactor, no signature or behaviour change (T21).

**Status**: PLANNED (validated, awaiting EXECUTE approval)
**Complexity**: SIMPLE

## Overview

Context: `process/context/all-context.md` (Key Patterns: "numbers are never silently wrong"); testing context `process/context/tests/all-tests.md` (pytest, `integration` marker deselected, offline). A power loss mid-`to_parquet` can truncate a whole series; this makes each parquet write all-or-nothing so the P2 auto-resume-on-boot can be enabled safely.

## Acceptance Criteria

- (a) Every `to_parquet(` in `cache.py` routes through `_atomic_to_parquet` — Fully-Automated (G1).
- (b) AC12: an interrupted write leaves the original file byte-identical and readable, and no temp remains — Fully-Automated (G2).
- (c) Normal round-trip behaviour unchanged for every writer family, incl. liqtide no-overwrite and onchain write-only-when-changed — Fully-Automated (G3).
- (d) Existing cache tests + full suite unchanged — Fully-Automated (G5).
- (e) `write_narrative_point` / `write_exchange_point` keep prior rows after an interrupted second write — Fully-Automated (G4).
- (f) New tests never touch real `api/data/cache` or `watchlist.json` (T22) — Fully-Automated (G6).

## Phase Completion Rules

- `CODE DONE` when checklist steps 2-5 are done and green.
- `VERIFIED` only after an independent vc-tester EVL run reproduces G1-G7 (post-phase testing per `process/context/tests/all-tests.md`).
- Known-gaps KG1-KG4 do not block VERIFIED; they stay recorded.

## Source Requirement

- `origin/claude/p2-deploy:process/general-plans/active/deployability_28-09-26/deployability_SPEC_28-09-26.md` — OQ9 (owner: P1), OQ10 (atomic writes are a prerequisite of automatic resume on boot), §4 "The one real risk", AC12.
- `process/MASTER-PLAN.md` T21 (cache.py refactor is SOLO, later — keep this minimal) and T22 (test isolation trap).

## Decisions

| # | Decision | Rationale | Rejected alternatives |
|---|---|---|---|
| D1 | Helper `_atomic_to_parquet(df: pd.DataFrame, path: Path) -> None`, private, placed right after `_as_utc`. Body: `fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")`; open `os.fdopen(fd, "wb")` as `fh`; `df.to_parquet(fh, index=False)`; `fh.flush(); os.fsync(fh.fileno())`; close; `os.replace(tmp, path)`. On ANY exception (`BaseException`, so KeyboardInterrupt too): best-effort `os.unlink(tmp)` (swallow `OSError`), then re-raise. | Same dir → same filesystem → `os.replace` is an atomic rename. `mkstemp` gives an OS-guaranteed unique name (no collision between concurrent writers, e.g. nightly job + resume script). Leading dot + `.tmp` suffix means no `*.parquet` glob matches it. | (a) fixed `path.with_suffix(".parquet.tmp")` like the JSON writers — two concurrent writers of the same file would clobber each other's temp; (b) `tempfile` in system temp dir — cross-filesystem, `os.replace` not atomic / fails on Windows across drives; (c) write-then-validate-by-reading-back — extra cost, rename-after-complete-write already gives the guarantee; (d) a shared refactor of all writers — forbidden by T21. |
| D2 | **fsync the temp file: yes.** No directory fsync. | Without fsync, on ext4/NTFS a power loss after rename can leave the new name pointing at a zero-length/partial file — exactly the failure AC12 targets. Files are small (KB–low MB), cost is negligible even at ~200 writes per refresh. Writing through a file handle (pandas/pyarrow accept a binary file object) is what makes fsync possible; `to_parquet(path)` gives no handle. Directory fsync (POSIX-only, `os.open(dir, O_RDONLY)` fails on Windows) would make the rename itself durable; skipped: the worst case without it is "old file survives", which is safe. | fsync omitted (process-crash safe only, not power-loss safe — the SPEC scenario is power loss). |
| D3 | Call sites swapped 1:1 (9 sites: `write_ohlcv` L106, `write_liqtide_payload` L210, `write_liqtide_backfill` L283, `write_liquidity_series` L312, `write_confirmed_boundaries` L340, `write_narrative_point` L388, `write_trending_snapshot` L407, `write_exchange_point` L512, `merge_onchain_series` L632). The expression before `.to_parquet(path, index=False)` becomes the helper's first argument verbatim. Every surrounding guard stays as is: `write_liqtide_payload`'s `if not path.exists()`, `merge_onchain_series`'s `if result.inserted or result.revised` (writes only when changed, `wrote_file` unchanged), every `mkdir`. | Zero behaviour change. | — |
| D4 | JSON writers (L254-256, L454-456) untouched. | Already temp-then-replace; changing them is out of scope. Their fixed temp name is a known, pre-existing minor weakness (not fixed here — T21). | Converting them to the helper (scope creep). |
| D5 | `api/analytics/cointegration/pairs_response.py::compute_and_persist` untouched. | Already tmp + `os.replace` (L135-137, L182-184), temp named `*.tmp` in the same dir — consistent with D1. It does not fsync; noted as known-gap, not in lane (`api/analytics/**` is out of scope). | Editing it (out of scope). |
| D6 | **Add `.gitignore` rule `api/data/cache/**/*.tmp`**, placed AFTER the three `!api/data/cache/{liqtide,narrative,onchain}/` negations. | The helper cleans its temp on exceptions, but a hard kill / power loss cannot run cleanup. `liqtide/`, `narrative/`, `onchain/` are git-tracked and the nightly workflows run `git add api/data/cache/{liqtide,narrative,onchain}/` (non-`-A` forms, still stage new untracked files) — a stray temp there would be committed to `main`. Verified: `.gitignore` currently has no `*.tmp` rule. `ohlcv/`, `pairs/`, `liquidity/` are already ignored so `git add -A` there skips them. Rule is lane-owned (P1 owns `.gitignore`) and is a pure additive ignore. | (a) no rule — relies on cleanup that cannot run on power loss; (b) a sweep step in workflows — `.github/workflows/*` out of scope; (c) global `*.tmp` — broader than needed. |
| D7 | Windows: `os.replace` maps to `MoveFileExW(MOVEFILE_REPLACE_EXISTING)`, atomic replace on NTFS same volume. It raises `PermissionError` if the target is held open without share-delete (e.g. a concurrent reader mid-read). In that case the helper's cleanup removes the temp and the error propagates, the ORIGINAL file stays intact (safe failure, same as today's crash mode, strictly better than truncation). | Documented, not engineered around (no retry loop — would be new behaviour). | Retry-with-backoff on `PermissionError` (behaviour change, untestable on Linux). |

### Reader safety check (temp can never be read as data)

| Reader | Pattern | Matches `.X.parquet.<rand>.tmp`? |
|---|---|---|
| `cache.read_liqtide_history` | `liqtide/*.parquet` (glob + DuckDB) | No (ends `.tmp`) |
| `cache.list_liqtide_raw_dates` / `list_exchange_market_snapshot_dates` | `*.json` | No |
| every other `cache.read_*` / `ohlcv_footer_stats(_many)` / `ohlcv_bar_count` | exact file path | No |
| `api/scripts/snapshot_narrative.py:304,309` | `*.parquet` | No |
| `api/scripts/snapshot_chain_growth.py:148` | `*/*/*.parquet` | No |
| `api/scripts/check_weekly_anchor.py:51` | `ohlcv_root.iterdir()` filtered `is_dir()` — temps are files inside `ohlcv/{SYM}/` | No |
| `pairs_response` spreads | writes its own staging dir; reads exact paths | No |

## Touchpoints

- `api/data/cache.py` — add `import tempfile`; add `_atomic_to_parquet`; swap 9 call sites. Nothing else.
- `api/tests/data/test_cache_atomic_writes.py` — new.
- `.gitignore` — one additive line + comment (D6).
- This task folder — plan (+ EXECUTE report).

## Public Contracts

None changed. All public `cache.*` function signatures, return values, file paths, file formats (parquet written by pyarrow, `index=False`), and column sets are identical. New symbol `_atomic_to_parquet` is private.

## Blast Radius

- Files: 3 (cache.py, one new test file, .gitignore). Package: `api/`.
- Risk class: data-write path of the only datastore (destructive-write class) → hybrid-minimum rule satisfied by fully-automated round-trip + interrupted-write tests against a real filesystem (tmp_path).
- HARD OUT OF SCOPE: `web/`, `api/main.py`, deploy config, `api/data/pytrends_adapter.py` + its test, `api/data/watchlist.py`, `api/data/ccxt_adapter.py`, `api/analytics/**`, `process/context/**`, `api/tests/conftest.py`, `.github/workflows/*`, any non-write code in `cache.py`.

## Implementation Checklist

1. Baseline: `uv run --project api pytest api/ -q 2>&1 | tail -3` — record passed/deselected. Snapshot real data: `find api/data/cache -type f -exec sha256sum {} + | sort > $SCRATCH/before.txt; sha256sum api/data/watchlist.json >> $SCRATCH/before.txt 2>/dev/null` (scratchpad, never the repo).
2. Write `api/tests/data/test_cache_atomic_writes.py` first (red). Module-level `@pytest.fixture(autouse=True) def _isolate(isolated_cache, tmp_path, monkeypatch)` that also `monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH", tmp_path / "watchlist.json")` (import from `api.data.watchlist` via whatever name it exports — confirm the attribute exists before patching; `raising=True`). Every test additionally names `isolated_cache` in its signature. Tests:
   - `test_helper_round_trip` — helper writes, `pd.read_parquet` equals input, no `*.tmp` left in dir.
   - `test_interrupted_write_preserves_original` (AC12, helper level) — write v1; record bytes; monkeypatch `pd.DataFrame.to_parquet` with a fake that writes 10 junk bytes to the target handle/path and raises `RuntimeError`; call helper with v2 → raises; original bytes identical, `pd.read_parquet` readable and equals v1, `list(dir.glob("*.tmp")) == []`.
   - `test_replace_failure_preserves_original` — monkeypatch `cache.os.replace` to raise `OSError`; same asserts.
   - `test_first_write_interrupted_leaves_no_file` — no prior file; interrupted → target does not exist, no temp.
   - Parametrised per writer family (9 writers) `test_<writer>_interrupted_preserves_prior` — call real writer once (valid), then again with the interruption monkeypatch → original byte-identical, readable via the module's own `read_*`, no temp.
   - Round-trip per family (9) — normal writes read back identically via `read_*` (proves unchanged behaviour); `write_liqtide_payload` second call with different data is still a no-op; `merge_onchain_series` with identical points → `wrote_file is False` and file mtime/bytes unchanged.
   - AC(e): `write_narrative_point` and `write_exchange_point` — write row A, then interrupted write of row B → reading back returns exactly row A; then an uninterrupted write of B → A and B both present.
   - `test_no_bypass` — `inspect.getsource(cache)` contains exactly one `.to_parquet(` (inside the helper).
3. `cache.py`: `import tempfile`; add helper per D1; swap 9 sites per D3.
4. `.gitignore`: append after the onchain negation block: comment + `api/data/cache/**/*.tmp`.
5. Green: new file passes; full suite equals baseline + new tests, 0 failures.
6. Isolation proof: `uv run --project api pytest api/tests/data/test_cache_atomic_writes.py -q --setup-show | grep -c "SETUP    F isolated_cache"` equals the collected test count; re-hash real cache into `after.txt`; `diff before.txt after.txt` empty.
7. Gitignore proof (throwaway repo in scratchpad, never the real repo): copy `.gitignore`, create `api/data/cache/narrative/x/.a.parquet.abc.tmp` + a real `.parquet`, run `git add api/data/cache/narrative/`, `git status --porcelain` shows only the parquet. Also `git check-ignore -v` on a temp path in `liqtide/` and `onchain/`.
8. Write EXECUTE report in this task folder.

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| G1 `grep -c "to_parquet(" api/data/cache.py` = 1 and `grep -n "_atomic_to_parquet(" api/data/cache.py` shows 1 def + 9 calls; plus `test_no_bypass` | Fully-Automated | (a) no writer bypasses the helper |
| G2 `uv run --project api pytest api/tests/data/test_cache_atomic_writes.py -q` — interrupted/replace-failure/first-write tests, per-writer interrupted tests | Fully-Automated | (b) AC12 — original byte-identical + readable, no stray temp |
| G3 same file — per-family round-trip, liqtide no-op, onchain no-write-when-unchanged | Fully-Automated | (c) behaviour unchanged; D3 guards preserved |
| G4 same file — narrative/exchange RMW interrupted then resumed | Fully-Automated | (e) prior rows preserved |
| G5 `uv run --project api pytest api/ -q` = baseline + new, 0 failed | Fully-Automated | (d) no regression |
| G6 `--setup-show` count + before/after sha256 diff of real `api/data/cache` + `watchlist.json` | Fully-Automated | T22 — tests never touch real data |
| G7 throwaway-repo `git add` / `git check-ignore` check | Fully-Automated | D6 — stray temp never committed |
| True power loss / SIGKILL mid-write | Known-Gap | Not reproducible here. G2 proves ordering (rename only after a complete write). fsync (D2) closes the data-not-on-disk window at the OS level but cannot be tested without a crash harness. No dir fsync: rename itself may be lost on power loss → old file survives (safe). |
| Windows `os.replace` under concurrent open reader | Known-Gap | Linux container only; D7 argues safe failure. User PC check optional. |

## Test Infra Improvement Notes

(none identified yet) — candidate: a reusable "interrupt writer" fixture if T21 later unifies writers.

## Risks

- Monkeypatching `DataFrame.to_parquet` must target the handle-based call; if the fake writes to the handle, cleanup must still close the fd before unlink (Windows would otherwise fail unlink). Helper closes via `with` before replace/unlink.
- `mkstemp` creates the file with mode 0600; after `os.replace` the parquet keeps 0600 (previously umask default, typically 0644). Single-user tool, git does not track the 0644 vs 0600 read bits beyond executable → acceptable; EXECUTE must note it in the report. Mitigation if desired: `os.chmod(tmp, 0o644)` before replace — **do it** (one line, preserves previous observable mode on POSIX; no-op-ish on Windows).

## Resume and Execution Handoff

1. Selected plan: `process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness-atomic-writes_PLAN_29-09-26.md`
2. Last completed step: PLAN + VALIDATE (this file). EXECUTE not started.
3. Validate-contract: written below (`Gate: CONDITIONAL`, known-gaps only).
4. Context loaded: P2 deployability SPEC (OQ9/10, §4, AC12), `api/data/cache.py`, `api/tests/conftest.py`, `process/MASTER-PLAN.md` T21/T22, P1 plan (T22 isolation pattern), `.gitignore`, `.github/workflows/*` `git add` lines, `pairs_response.py` L130-185.
5. Next step for a fresh agent: run checklist step 1 (baseline + hash snapshot), then step 2.

## Validate Contract

generated-by: outer-pvl
date: 2026-09-29
Date: 29-09-26
Gate: CONDITIONAL

### V1 pre-check
Plan file exists; Blast Radius present; no Inner Loop Refresh Note. Structure validated with `validate-plan-artifact.mjs`.

### Net gate derivation

| Layer 1 dimensions | Status |
|---|---|
| Infra fit | PASS — same-dir temp, `os.replace` atomic on POSIX and NTFS same volume |
| Test coverage | CONCERN — OS-level durability (power loss / SIGKILL) not testable; exception simulation only |
| Breaking changes | PASS — no public contract change; file mode kept 0644 via chmod |
| Security surface | PASS — no auth/secrets; `.gitignore` rule prevents accidental commit of stray temps |

| Layer 2 sections | Status |
|---|---|
| Helper (D1/D2) | PASS — fd closed before replace/unlink |
| 9 call-site swap (D3) | PASS — all 9 sites located by grep; guards preserved |
| Reader safety | PASS — table above, no glob matches `.tmp` |
| `.gitignore` (D6) | PASS — negation ordering verified in EXECUTE step 7 |
| Windows (D7) | CONCERN — reasoned, not tested |

Totals: 0 FAILs / 2 CONCERNs / 7 PASSes → Net Gate: CONDITIONAL (both CONCERNs are environment-impossible, accepted as known-gaps; not fixable by plan supplement).

### Test gates (offline, run in order)
1. `grep -c "to_parquet(" api/data/cache.py` → `1`
2. `uv run --project api pytest api/tests/data/test_cache_atomic_writes.py -q` → all pass
3. `uv run --project api pytest api/tests/data/test_cache_atomic_writes.py -q --setup-show | grep -c "SETUP    F isolated_cache"` → equals collected count
4. `uv run --project api pytest api/ -q` → baseline + new, 0 failed
5. sha256 before/after diff of `api/data/cache` + `api/data/watchlist.json` → empty
6. Throwaway-repo `git add` / `git check-ignore -v` for temps under liqtide/narrative/onchain → ignored

### Execute-agent instructions
- E1: Swap sites by expression, not line number (lines may drift). Touch no other code in `cache.py`.
- E2: Red first (step 2) before editing `cache.py`.
- E3: Never run git add/commit/stash/checkout against the real repo; git experiments only in a scratchpad repo.
- E4: If `watchlist_store.DEFAULT_WATCHLIST_PATH` has a different name in `api/data/watchlist.py`, patch the real attribute and record it; do not edit `watchlist.py`.
- E5: If any existing test asserts on file mode or a `.tmp` name, stop and report (do not edit it).

### Accepted known-gaps
- KG1: true power loss / kill mid-write not reproducible; fsync closes the OS-buffer window but is untested; no directory fsync (worst case: old file survives).
- KG2: Windows `os.replace` vs open reader untested (safe-fail by reasoning).
- KG3: `pairs_response.compute_and_persist` temp writes are not fsynced (out of lane, `api/analytics/**`).
- KG4: JSON writers keep a fixed temp name (T21 later).
