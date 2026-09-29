---
name: plan:pipeline-completeness-atomic-writes
description: "Make every parquet write in api/data/cache.py atomic (temp in same dir, fsync, os.replace) — prerequisite of P2 automatic resume (deployability SPEC OQ9/OQ10, AC12)"
date: 29-09-26
feature: none (general-plans, P1 lane)
---

# Atomic parquet writes in `api/data/cache.py` — PLAN (SIMPLE)

TL;DR: add one private helper `_atomic_to_parquet(df, path)` to `cache.py` (unique temp file in the same directory → write → fsync → `os.replace`; temp removed on any exception) and route the 9 existing `to_parquet(` call sites in `api/data/cache.py` through it (cache.py ONLY — see KG5: `etf_flows_adapter.py` has a separate non-atomic writer that is out of this assignment). Add one `api/tests/data/test_cache_atomic_writes.py` (isolated, offline). Add one `.gitignore` line so a leftover temp from a hard kill can never be committed by the nightly workflows. No refactor, no signature or behaviour change (T21).

**Status**: PLANNED — PVL supplement applied 29-09-26 (gaps N1-N3 + snapshot strength folded in); VALIDATE must re-run from V1 before EXECUTE
**Complexity**: SIMPLE

## Overview

Context: `process/context/all-context.md` (Key Patterns: "numbers are never silently wrong"); testing context `process/context/tests/all-tests.md` (pytest, `integration` marker deselected, offline). A power loss mid-`to_parquet` can truncate a whole series; this makes each parquet write all-or-nothing so the P2 auto-resume-on-boot can be enabled safely.

## Acceptance Criteria

- (a) Every `to_parquet(` in `api/data/cache.py` (that file only; no repo-wide claim) routes through `_atomic_to_parquet` — Fully-Automated (G1). Not covered: `api/data/etf_flows_adapter.py::merge_into_cache` (KG5).
- (b) AC12: an interrupted write leaves the original file byte-identical and readable, and no temp remains — Fully-Automated (G2).
- (c) Normal round-trip behaviour unchanged for every writer family, incl. liqtide no-overwrite and onchain write-only-when-changed — Fully-Automated (G3).
- (d) Existing cache tests + full suite unchanged — Fully-Automated (G5).
- (e) `write_narrative_point` / `write_exchange_point` keep prior rows after an interrupted second write — Fully-Automated (G4).
- (f) New tests never touch real `api/data/cache` or `watchlist.json` (T22) — Fully-Automated (G6).

## Phase Completion Rules

- `CODE DONE` when checklist steps 2-5 are done and green.
- `VERIFIED` only after an independent vc-tester EVL run reproduces G1-G7 (post-phase testing per `process/context/tests/all-tests.md`).
- Known-gaps KG1-KG5 do not block VERIFIED; they stay recorded.
- **Scope statement (P2 AC12):** this plan makes the `cache.py` writers atomic only. P2's AC12 ("every cache file") is NOT fully met until `etf_flows_adapter.merge_into_cache` also goes through an atomic helper (KG5, Future Work).

## Source Requirement

- `origin/claude/p2-deploy:process/general-plans/active/deployability_28-09-26/deployability_SPEC_28-09-26.md` — OQ9 (owner: P1), OQ10 (atomic writes are a prerequisite of automatic resume on boot), §4 "The one real risk", AC12.
- `process/MASTER-PLAN.md` T21 (cache.py refactor is SOLO, later — keep this minimal) and T22 (test isolation trap).

## Decisions

| # | Decision | Rationale | Rejected alternatives |
|---|---|---|---|
| D1 | Helper `_atomic_to_parquet(df: pd.DataFrame, path: Path) -> None`, private, placed right after `_as_utc`. Body: `fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")`; open `os.fdopen(fd, "wb")` as `fh`; `df.to_parquet(fh, index=False)`; `fh.flush(); os.fsync(fh.fileno())`; close; `os.replace(tmp, path)`. **File mode (explicit):** after the handle is closed and before `os.replace`, `os.chmod(tmp, mode)` where `mode` = the existing target's permission bits (`os.stat(path).st_mode & 0o7777`) when the target exists, otherwise `0o644`. `mkstemp` creates 0600, so without this the parquet would silently become 0600. This does NOT claim to "preserve the previous mode" in general: a plain path write yields `0666 & ~umask` (0644 / 0664 / 0600 under umask 022 / 002 / 077), so a first-ever write is normalised to 0644 (hard-coding 0644 for existing files would loosen a 0600 file under umask 077, hence copy-from-target). On Windows `os.chmod` only toggles the read-only bit (0o644 leaves it writable) — effectively a no-op. On ANY exception (`BaseException`, so KeyboardInterrupt too): best-effort `os.unlink(tmp)` (swallow `OSError`), then re-raise. The helper's docstring/comments must NOT contain the literal text `to_parquet(` (keeps G1 and `test_no_bypass` at exactly 1). | Same dir → same filesystem → `os.replace` is an atomic rename. `mkstemp` gives an OS-guaranteed unique name (no collision between concurrent writers, e.g. nightly job + resume script). Leading dot + `.tmp` suffix means no `*.parquet` glob matches it. | (a) fixed `path.with_suffix(".parquet.tmp")` like the JSON writers — two concurrent writers of the same file would clobber each other's temp; (b) `tempfile` in system temp dir — cross-filesystem, `os.replace` not atomic / fails on Windows across drives; (c) write-then-validate-by-reading-back — extra cost, rename-after-complete-write already gives the guarantee; (d) a shared refactor of all writers — forbidden by T21. |
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
- HARD OUT OF SCOPE (explicit): `api/data/etf_flows_adapter.py` (`merge_into_cache` writes `CACHE_ROOT/etf_flows/btc_spot.parquet` directly — KG5; the orchestrator ruled it outside this assignment), `api/scripts/seed_e2e_cache.py`, `web/`, `api/main.py`, deploy config, `api/data/pytrends_adapter.py` + its test, `api/data/watchlist.py`, `api/data/ccxt_adapter.py`, `api/analytics/**`, `process/context/**`, `api/tests/conftest.py`, `.github/workflows/*`, any non-write code in `cache.py`.

## Implementation Checklist

1. Baseline: `uv run --project api pytest api/ -q 2>&1 | tail -3` — record passed/deselected. Snapshot real data: `{ find api/data/cache -type f -printf '%p %s %T@\n' | sort; find api/data/watchlist.json -printf '%p %s %T@\n' 2>/dev/null; } > $SCRATCH/before.txt` (path + size + mtime), plus a content-hash snapshot `{ find api/data/cache -type f -exec sha256sum {} + | sort; sha256sum api/data/watchlist.json 2>/dev/null; } > $SCRATCH/before.sha` (scratchpad, never the repo). Size+mtime is required because parquet writes are deterministic, so a hash-only diff misses an identical-content rewrite.
2. Write `api/tests/data/test_cache_atomic_writes.py` first (red). Module-level `@pytest.fixture(autouse=True) def _isolate(isolated_cache, tmp_path, monkeypatch)` that also `monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH", tmp_path / "watchlist.json")` (import from `api.data.watchlist` via whatever name it exports — confirm the attribute exists before patching; `raising=True`). Every test additionally names `isolated_cache` in its signature. Tests:
   - `test_helper_round_trip` — helper writes, `pd.read_parquet` equals input, no `*.tmp` left in dir.
   - `test_interrupted_write_preserves_original` (AC12, helper level) — write v1; record bytes; monkeypatch `pd.DataFrame.to_parquet` with a fake that (i) when handed a `Path`/`str` TRUNCATES that target and writes 10 junk bytes, and (ii) when handed a file handle writes 10 junk bytes to it, then raises `RuntimeError`. The Path-truncating branch is mandatory: a handle-only fake raises AttributeError on the old path-based code, leaves the file intact and passes vacuously; the truncating fake genuinely corrupts current code, so the test is red-first; call helper with v2 → raises; original bytes identical, `pd.read_parquet` readable and equals v1, `list(dir.glob("*.tmp")) == []`.
   - `test_replace_failure_preserves_original` — monkeypatch `cache.os.replace` (note `cache.os` IS the process-global `os` module) with a fake that raises `OSError` ONLY when the destination is under the isolated root (`tmp_path`) and delegates to the real `os.replace` otherwise; same asserts.
   - `test_first_write_interrupted_leaves_no_file` — no prior file; interrupted → target does not exist, no temp.
   - Parametrised per writer family (9 writers) `test_<writer>_interrupted_preserves_prior` — call real writer once (valid), then again with the interruption monkeypatch, where the second call MUST actually reach the write: `write_liqtide_payload` and `write_exchange_point` use a NEW date on the second call (same-date is a guarded no-op / returns False); `merge_onchain_series` second call inserts or revises at least one point (otherwise `wrote_file` is False and nothing is written) → original byte-identical, readable via the module's own `read_*`, no temp.
   - Round-trip per family (9) — normal writes read back identically via `read_*` (proves unchanged behaviour); `write_liqtide_payload` second call with different data is still a no-op; `merge_onchain_series` with identical points → `wrote_file is False` and file mtime/bytes unchanged.
   - AC(e): `write_narrative_point` and `write_exchange_point` — write row A, then interrupted write of row B → reading back returns exactly row A; then an uninterrupted write of B → A and B both present.
   - `test_no_bypass` — `inspect.getsource(cache)` contains exactly one `.to_parquet(` (the call inside the helper; docstring/comments must not contain that text). Scope: `cache.py` only (KG5).
   - `test_isolation_canary` — `assert cache.CACHE_ROOT == tmp_path` (the `isolated_cache` root) and `assert watchlist_store.DEFAULT_WATCHLIST_PATH == tmp_path / "watchlist.json"`, same canary the sibling script test files use.
   - `test_mode_handling` — first write yields mode 0o644; overwriting a file chmod'ed 0o600 keeps 0o600 (POSIX only, `skipif` on Windows).
3. `cache.py`: `import tempfile`; add helper per D1; swap 9 sites per D3.
4. `.gitignore`: append after the onchain negation block: comment + `api/data/cache/**/*.tmp`.
5. Green: new file passes; full suite equals baseline + new tests, 0 failures.
6. Isolation proof: `uv run --project api pytest api/tests/data/test_cache_atomic_writes.py -q --setup-show | grep -c "SETUP    F isolated_cache"` equals the collected test count; re-snapshot the real cache + `watchlist.json` with the SAME size+mtime `find -printf '%p %s %T@\n'` command into `after.txt` and the sha256 command into `after.sha`; `diff before.txt after.txt` AND `diff before.sha after.sha` both empty.
7. Gitignore proof (throwaway repo in scratchpad, never the real repo): copy `.gitignore`, create `api/data/cache/narrative/x/.a.parquet.abc.tmp` + a real `.parquet`, run `git add api/data/cache/narrative/`, `git status --porcelain` shows only the parquet. Also `git check-ignore -v` on a temp path in `liqtide/` and `onchain/`.
8. Write EXECUTE report in this task folder (note the file-mode behaviour per D1 and the KG5 scope statement).
9. (UPDATE PROCESS, not EXECUTE) write backlog stub `process/general-plans/backlog/pipeline-etf-flows-atomic-write_NOTE_29-09-26.md` for KG5 (see Known Gaps and Future Work).

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| G1 `grep -c "to_parquet(" api/data/cache.py` = 1 and `grep -n "_atomic_to_parquet(" api/data/cache.py` shows 1 def + 9 calls; plus `test_no_bypass` | Fully-Automated | (a) no writer IN `api/data/cache.py` bypasses the helper (cache.py only; other modules, e.g. etf_flows_adapter, not covered — KG5) |
| G2 `uv run --project api pytest api/tests/data/test_cache_atomic_writes.py -q` — interrupted/replace-failure/first-write tests, per-writer interrupted tests | Fully-Automated | (b) AC12 — original byte-identical + readable, no stray temp |
| G3 same file — per-family round-trip, liqtide no-op, onchain no-write-when-unchanged | Fully-Automated | (c) behaviour unchanged; D3 guards preserved |
| G4 same file — narrative/exchange RMW interrupted then resumed | Fully-Automated | (e) prior rows preserved |
| G5 `uv run --project api pytest api/ -q` = baseline + new, 0 failed | Fully-Automated | (d) no regression |
| G6 `--setup-show` count + canary test + before/after size+mtime (`find -printf '%p %s %T@'`) AND sha256 diff of real `api/data/cache` + `watchlist.json` | Fully-Automated | T22 — tests never touch real data |
| G7 throwaway-repo `git add` / `git check-ignore` check | Fully-Automated | D6 — stray temp never committed |
| True power loss / SIGKILL mid-write | Known-Gap | Not reproducible here. G2 proves ordering (rename only after a complete write). fsync (D2) closes the data-not-on-disk window at the OS level but cannot be tested without a crash harness. No dir fsync: rename itself may be lost on power loss → old file survives (safe). |
| KG5 `api/data/etf_flows_adapter.py::merge_into_cache` non-atomic parquet write (request path of `GET /api/regime/components`, git-ignored, no git copy) | Known-Gap | Outside this assignment (orchestrator ruling). Not proven or fixed here; P2 AC12 NOT fully met until it is routed through an atomic helper. Backlog stub + Future Work below. |
| Windows `os.replace` under concurrent open reader | Known-Gap | Linux container only; D7 argues safe failure. User PC check optional. |

## Test Infra Improvement Notes

(none identified yet) — candidate: a reusable "interrupt writer" fixture if T21 later unifies writers.

## Risks

- Monkeypatching `DataFrame.to_parquet` must target the handle-based call; if the fake writes to the handle, cleanup must still close the fd before unlink (Windows would otherwise fail unlink). Helper closes via `with` before replace/unlink.
- `mkstemp` creates the file with mode 0600. Mitigation is specified in D1: copy the existing target's mode when it exists, else 0o644. Caveat (umask): a path write gives `0666 & ~umask` (0644/0664/0600), so 0o644 for a NEW file is a normalisation, not strict preservation; copy-from-target avoids loosening an existing 0600 file under umask 077. EXECUTE notes this in the report.

## Known Gaps and Future Work

- KG1 power loss/SIGKILL durability (untestable here); KG2 Windows `os.replace` vs open reader; KG3 `pairs_response` not fsynced (out of lane); KG4 JSON writers' fixed temp name (T21).
- **KG5 (scope ruling 29-09-26: record, do NOT widen)** — `api/data/etf_flows_adapter.py:103-111` (`merge_into_cache`) does read-modify-write and `merged.to_parquet(...)` directly into `CACHE_ROOT/etf_flows/btc_spot.parquet` (also `api/scripts/seed_e2e_cache.py:232`). It is in the request path of `GET /api/regime/components` (`api/analytics/regime/components.py:484`, `etf_flows_adapter.py:301`), git-ignored (no git copy); `read_cached` swallows read errors and Farside is limited to one attempt per UTC day, so a truncated file is not quickly self-healing. It is NOT an EXECUTE touchpoint. **P2's AC12 is NOT fully met until this writer also goes through an atomic helper.**
- **Future Work (needs a user scope decision):** ~2-line follow-up in `etf_flows_adapter.py` — route `merge_into_cache` through the helper, exposing a public/documented cross-module helper name (rather than importing the private `_atomic_to_parquet`) and extending the bypass test accordingly.
- **UPDATE PROCESS backlog stubs:** `process/general-plans/backlog/pipeline-etf-flows-atomic-write_NOTE_29-09-26.md` (KG5 + the follow-up above).

## Resume and Execution Handoff

1. Selected plan: `process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness-atomic-writes_PLAN_29-09-26.md`
2. Last completed step: PLAN + first independent VALIDATE pass (CONDITIONAL) + PVL supplement (4 gaps folded in 29-09-26). EXECUTE not started.
3. Validate-contract: written below (`Gate: CONDITIONAL`, first pass, now STALE relative to the supplement) — VALIDATE must re-run from V1 and produce a fresh contract before EXECUTE.
4. Context loaded: P2 deployability SPEC (OQ9/10, §4, AC12), `api/data/cache.py`, `api/tests/conftest.py`, `process/MASTER-PLAN.md` T21/T22, P1 plan (T22 isolation pattern), `.gitignore`, `.github/workflows/*` `git add` lines, `pairs_response.py` L130-185.
5. Next step for a fresh agent: re-run VALIDATE from V1 (orchestrator spawns vc-validate-agent). Only after `Gate: PASS` (or accepted CONDITIONAL after >=1 cycle): checklist step 1 (baseline + size/mtime/hash snapshot), then step 2.

## Validate Contract

Status: CONDITIONAL
Date: 29-09-26
date: 2026-09-29
generated-by: outer-pvl
supersedes: 2026-09-29 (outer-pvl; inline fast-mode self-validation by the plan's author) — independent second-look validate has current evidence and found items the inline pass did not

Parallel strategy: sequential
Rationale: score 2/7 (S2 destructive-write data path, S6 high-risk class); 3 files, one dominant surface; independent checks were run by the validator directly in a scratch dir, no fan-out needed.

Validator provenance: this contract was written by an independent vc-validate-agent pass, NOT by the agent that authored the plan. Verification below was run against source and in throwaway dirs (scratchpad), never against the real repo state or real `api/data/cache`.

### Independent evidence (what was actually run)

- Baseline at HEAD `df2c3c9`: `uv run --project api pytest api/ -q` = **789 passed, 5 deselected** (170 s). Record this as the G5 baseline.
- Helper output equivalence (pandas 3.0.6, pyarrow 25.0.1): `df.to_parquet(fh, index=False)` through an `os.fdopen` handle vs `df.to_parquet(path, index=False)` — **byte-identical files** for six representative frames (tz-aware UTC OHLCV, narrative with None, Arrow-string/Int64 exchange frame, onchain string/bool/NaN frame, empty typed frame, sorted-index frame); schema incl. metadata equal, `created_by` equal, codec SNAPPY both. Behaviour is unchanged.
- Exception paths (scratch helper mirroring D1+chmod): fake `to_parquet` writing junk then `RuntimeError`; `KeyboardInterrupt`; `os.replace` -> `OSError`. Each: original bytes identical, `pd.read_parquet` equals v1, zero `*.tmp` left, **fd count delta 0** (no leak, no double close; `with os.fdopen` closes before unlink). Unlink failure is swallowed, original error re-raised.
- Red-first check: the same truncating fake applied to the CURRENT `df.to_parquet(path)` path leaves the original corrupted (original-intact = False), so a per-writer test using a fake that truncates when handed a `Path` genuinely fails before the change.
- `.gitignore`: throwaway repo with a copy of the real `.gitignore` + the proposed line after the `!…/onchain/` negation. `git check-ignore -v` attributes the rule (`.gitignore:48`) to a dotfile `…/.keep.parquet.a8_k3x9z.tmp` in `liqtide/`, `liqtide/raw/`, `narrative/`, `narrative/pytrends/`, `narrative/exchange/`, `onchain/`, `onchain/growthepie/base/`; `ohlcv/BTC/` already ignored by `api/data/cache/*`. Real `.parquet` files in those dirs stay un-ignored and `git add` stages only them. **Without the rule, the same `git add` stages every stray `.tmp`** (risk is real). Ordering is correct.
- Reader glob audit: all globs are `*.parquet`, `*/*/*.parquet`, `*.json`, or exact paths; `.name.rand.tmp` matches none.
- Isolation: `watchlist_store.DEFAULT_WATCHLIST_PATH` exists (`api/data/watchlist.py:41`), same pattern already used by 4 other test files; `--setup-show | grep -c "SETUP    F isolated_cache"` verified to equal the collected count on `test_compute_pairs.py` (17 = 17). `api/tests/conftest.py` untouched by the plan. No existing test asserts on file mode or a `.tmp` name in `cache.py` outputs (E5 clear).

### Net gate derivation

| Layer 1 dimensions | Status |
|---|---|
| Infra fit | CONCERN — N1: `api/data/etf_flows_adapter.py:110` (`merge_into_cache`) writes a cache parquet directly, outside `cache.py`; not recorded anywhere in the plan |
| Test coverage | CONCERN — N3: test-design pitfalls (below) + structural KG1/KG2 |
| Breaking changes | CONCERN — N2: `chmod 0o644` claim "preserves previous mode" is true only for umask 022, and D1's body omits the chmod (Risks says "do it"). Output bytes themselves are unchanged (verified) |
| Security surface | PASS — `.gitignore` rule proven; only advisory: hard-coded 0644 can widen a 0600 (umask 077) user's file |

| Layer 2 sections | Status |
|---|---|
| Helper (D1/D2/D7) | PASS mechanics (no fd leak, no masking) — N2 chmod wording only |
| 9 call-site swap (D3) | PASS — sites at L106/210/283/312/340/388/407/512/632; every `mkdir` precedes the write; liqtide `exists()` guard, onchain write-only-when-changed, `wrote_file` all preserved; `liquidity_series_age_seconds` mtime semantics preserved (rename keeps temp's write-time mtime) |
| Reader safety | PASS — verified against every glob/listing in `api/` |
| `.gitignore` (D6) | PASS — reproduced |
| Test plan (step 2) | CONCERN — N3 |
| T22 isolation (step 1/6) | PASS with N3(e) — sound design; hash snapshot is content-only |
| Scope | PASS — plan touches only `cache.py`, the new test file, one `.gitignore` line, task folder; conftest, web/, workflows, pytrends, watchlist, ccxt, analytics untouched |
| D5 `pairs_response.compute_and_persist` | PASS (out of scope, safe) — results and provenance are tmp + `os.replace`; spreads are staged in `spreads.tmp` then `rmtree` + `os.replace` (short no-dir window) but provenance is unlinked FIRST, so readers see `results_unavailable`, never wrong data; derived, recomputable, `pairs/` is git-ignored. Not fsynced (already KG3) |
| Known-gap honesty (KG1-KG4) | PASS — claims are not overstated: KG1 says exception-simulation only and fsync untested; KG2 is reasoning-only. But the gap list is INCOMPLETE (N1) |

Totals: **0 FAILs / 4 CONCERNs (N1-N3 fixable in the plan; N4 structural) / rest PASS** → Net Gate: **CONDITIONAL, first pass, with FIXABLE concerns**.
Because N1-N3 can be fixed by a plan supplement, this is NOT terminal: `PHASE_COMPLETE: VALIDATE` is withheld. See SUPPLEMENT REQUEST in the handoff.

### Concerns (numbered, with resolution route)

- **N1 (fixable by plan text; needs a scope decision)** — Bypass writer outside `cache.py`. `api/data/etf_flows_adapter.py:103-111` `merge_into_cache` does read-modify-write (`read_cached` + `concat`) then `merged.to_parquet(path, index=False)` into `CACHE_ROOT/etf_flows/btc_spot.parquet`. It runs in the REQUEST path of `GET /api/regime/components` (`api/analytics/regime/components.py:484` -> `fetch_btc_spot_flows` -> L301) and from `seed_e2e_cache.py:232`. The file is git-ignored (`api/data/cache/*`), so there is no git copy; `read_cached` swallows read errors and returns an empty frame, so a truncated file self-heals only by a fresh Farside fetch, which is rate-limited to one attempt per UTC day. The plan's G1 / `test_no_bypass` ("exactly one `.to_parquet(` in cache.py") is true but does NOT prove AC12 for "every cache file", which is what the P2 SPEC (§4, AC12) requires before auto-resume. The plan's known-gaps do not mention it. The user assigned only `cache.py`, so the validator does not silently widen scope. Route: plan must (a) name it as KG5 + a backlog stub, (b) reword G1/AC(a) to "every `to_parquet(` **in cache.py**" and stop implying repo-wide coverage, (c) tell P2/user that AC12 is NOT fully satisfied until `etf_flows_adapter.merge_into_cache` also goes through the helper, and offer the 2-line follow-up (needs a non-underscore or documented cross-module helper name — do not import a private name from another module). The user/orchestrator decides whether to widen scope now.
- **N2 (fixable)** — File mode. Verified: path-based write yields `0666 & ~umask` (0644 under umask 022, 0664 under 002, 0600 under 077). Hard-coded `chmod 0o644` therefore does NOT "preserve previous observable mode" in general; under umask 077 it loosens permissions. Also D1's body omits the chmod while Risks/Contract claim it exists. Route: put the chosen behaviour into D1 explicitly. Recommended: chmod to the existing target's mode when the target exists, else 0o644; state the umask caveat honestly. Windows: `os.chmod` only toggles the read-only bit (0o644 leaves it writable) — no-op-ish, fine.
- **N3 (fixable)** — Test-plan pitfalls that would make tests vacuous or fragile:
  (a) The interrupt fake MUST truncate the target when handed a `Path` (and write junk to a handle when handed one); a handle-only fake raises `AttributeError` on the old path-based code, leaves the file intact, and the test "passes" before the change. (I proved the path-truncating variant corrupts old code.)
  (b) Per-writer "interrupted" tests need a second call that actually reaches `to_parquet`: `write_liqtide_payload` second call for the SAME date is a no-op (guard) and `write_exchange_point` same-date returns False — the interrupted call must use a NEW date; `merge_onchain_series` must insert/revise something or it never writes.
  (c) Add the canary test used by the four sibling files (`assert cache.CACHE_ROOT == tmp_path` and `watchlist_store.DEFAULT_WATCHLIST_PATH == tmp_path / "watchlist.json"`) — the plan has none.
  (d) `monkeypatch.setattr(cache.os, "replace", …)` mutates the process-global `os` module; scope the fake to raise only when the destination is under the isolated root and delegate otherwise. Also keep the literal text `to_parquet(` out of the helper's docstring/comments so G1's `grep -c` and `test_no_bypass` stay = 1.
  (e) The T22 before/after snapshot is content-hash only; parquet writes are deterministic (verified byte-identical), so a stray rewrite of the real file with identical data would go undetected. Add size + mtime (`find … -printf '%p %s %T@\n'`) and the `watchlist.json` line.
- **N4 (structural — cannot be fixed by planning)** — KG1 (true power loss / SIGKILL durability, fsync untested, no directory fsync) and KG2 (Windows `os.replace` with an open reader). Note KG2 is not exotic: the P2 SPEC's always-on box is the user's own PC.

### Test gates (5-column table)

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| (a) / G1 | every `to_parquet(` in `cache.py` goes through `_atomic_to_parquet` | Fully-Automated | `grep -c "to_parquet(" api/data/cache.py` = 1 + `test_no_bypass` (cache.py only — see N1) | B |
| (b) / G2 | interrupted write, `os.replace` failure and first-write interruption leave original byte-identical, readable, no `*.tmp` | Fully-Automated | `uv run --project api pytest api/tests/data/test_cache_atomic_writes.py -q` (helper-level + 9 per-writer tests; fake truncates on Path — N3a/b) | B |
| (c) / G3 | normal round-trip unchanged per writer; liqtide no-overwrite; onchain write-only-when-changed | Fully-Automated | same file, per-family round-trip tests | B |
| (e) / G4 | narrative/exchange RMW keep prior rows after interrupted second write | Fully-Automated | same file, AC(e) tests (interrupted call uses a new date — N3b) | B |
| (d) / G5 | no regression | Fully-Automated | `uv run --project api pytest api/ -q` = 789 passed / 5 deselected baseline + new tests, 0 failed | A |
| (f) / G6 | tests never touch real cache or `watchlist.json` | Fully-Automated | `--setup-show \| grep -c "SETUP    F isolated_cache"` == collected count; canary test; before/after `find … -printf '%p %s %T@'` + sha256 diff empty | B |
| D6 / G7 | stray temp never staged by nightly `git add` | Fully-Automated | throwaway-repo `git add` + `git check-ignore -v` (validator reproduced it: PASS, and shows the risk without the rule) | A |

Named residuals (NOT strategies; carried as gap-resolution D, none is a proving gate):
- KG1 power-loss/SIGKILL durability, no dir fsync — D (cannot test here).
- KG2 Windows `os.replace` vs open reader — D (user-PC check optional).
- KG3 `pairs_response` writes not fsynced (out of lane) — D.
- KG4 JSON writers' fixed temp name (T21) — D.
- **KG5 (new, from N1) `etf_flows_adapter.merge_into_cache` non-atomic parquet write, request-path, no git copy** — C or D per the user's scope decision (route to P2/P1 follow-up or widen scope).

Failing stubs (Fully-Automated rows, TDD red-first; scenario text verbatim):
```
test("should route every to_parquet call in cache.py through _atomic_to_parquet", () => { throw new Error("NOT IMPLEMENTED — TDD stub: no bypass") })
test("should leave the original file byte-identical and readable when the write is interrupted", () => { throw new Error("NOT IMPLEMENTED — TDD stub: interrupted write") })
test("should behave identically to the non-atomic writers on the normal path", () => { throw new Error("NOT IMPLEMENTED — TDD stub: round-trip unchanged") })
test("should keep prior rows after an interrupted second write to narrative and exchange series", () => { throw new Error("NOT IMPLEMENTED — TDD stub: RMW preserved") })
test("should not touch the real cache or watchlist", () => { throw new Error("NOT IMPLEMENTED — TDD stub: isolation") })
```
(Language-neutral skeleton; the real tests are pytest.)

Legacy line form:
- cache.py writers: [Fully-automated: `uv run --project api pytest api/tests/data/test_cache_atomic_writes.py -q`] | [Fully-automated: `uv run --project api pytest api/ -q`] | [Fully-automated: throwaway-repo gitignore check] | [known-gap: power loss, Windows open-reader, etf_flows_adapter bypass — documented]

Dimension findings:
- Infra fit: CONCERN — etf_flows_adapter.py:110 is an unwrapped, request-path, git-ignored RMW parquet write; not in scope, not recorded.
- Test coverage: CONCERN — fake must truncate on Path, second calls must reach the write, add canary, scope the os.replace patch, size+mtime in the isolation snapshot; power-loss untestable here.
- Breaking changes: CONCERN — file-mode claim overstated (umask-dependent) and absent from D1's body; output bytes unchanged (verified byte-identical).
- Security surface: PASS — gitignore reproduced; advisory only on 0644 widening.
- Helper section: PASS — no fd leak/double-close, BaseException cleanup correct, original error not masked.
- Call-site swap section: PASS — 9 sites, all guards and mkdirs preserved.
- Reader-safety section: PASS.
- `.gitignore` section: PASS — reproduced, ordering correct.
- Scope: PASS.

Open gaps:
- N1 etf_flows_adapter.py bypass (needs user scope decision) — NEW PLAN/SCOPE decision required if not widened.
- N2 chmod semantics; N3 (a)-(e) test-plan fixes.
- KG1-KG5 residuals above.

What this coverage does NOT prove:
- G1/`test_no_bypass`: does not prove no OTHER module writes cache files atomically-or-not (etf_flows_adapter does not).
- G2/G4: prove that a SIMULATED exception (fake `to_parquet`, failing `os.replace`) leaves the original intact; they do NOT prove behaviour under real power loss, SIGKILL mid-write, a full disk, or an fsync that the OS ignores.
- G3: proves per-writer round-trip on synthetic frames, not on the real 57-file cache.
- G5: proves no regression in the 789-test suite, not real-network refresh behaviour.
- G6: proves the tests did not modify the real cache/watchlist; it does not prove other suites are isolated.
- G7: proves git ignores a `.tmp` in tracked dirs; it does not prove no other stray file type can be committed.
- Windows: nothing here proves `os.replace` succeeds while DuckDB/API holds a read handle.

Gate: CONDITIONAL (first pass; fixable concerns N1-N3 outstanding — NOT terminal, supplement cycle required before EXECUTE; structural gaps KG1/KG2 unfixable here)
Accepted by: NO HUMAN has accepted any concern. KG1, KG2 (structural, untestable in this container) are provisionally carried under the autonomous-run policy only. N1-N3 are not accepted — they are open supplement items. This independent pass (a different agent from the plan's author, with scratch-dir experiments) is the substantive second look; the earlier inline fast-mode contract was self-validation.

## Autonomous Goal Block

SESSION GOAL: Make every parquet write in api/data/cache.py atomic (temp + fsync + os.replace) so P2 auto-resume is safe (AC12).
Charter + umbrella plan: N/A — single plan (sibling program plan: process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness_PLAN_28-09-26.md, no Stable Program Goal).
Autonomy: standing autonomous execution per feedback_autonomous_phase_execution.md; removes approval pauses only, subagent delegation stays mandatory.
Hard stops / safety constraints:
- Never touch real api/data/cache or watchlist.json; tests must use isolated_cache + watchlist redirect (T22); conftest.py stays unmodified.
- Files allowed: api/data/cache.py, api/tests/data/test_cache_atomic_writes.py, one .gitignore line, this task folder. web/, api/main.py, workflows, pytrends, watchlist.py, ccxt_adapter.py, api/analytics/**, process/context/** are out of scope.
- Never git add/commit/stash/checkout the real repo for experiments; use a scratch repo.
- Do not widen scope to etf_flows_adapter.py without an explicit user decision (N1).
- Do not run EXECUTE until the PVL supplement for N1-N3 is applied and PVL re-validates.
Next phase: PVL supplement (vc-plan-agent) for N1-N3, then re-validate; then EXECUTE: process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness-atomic-writes_PLAN_29-09-26.md
Validate contract: inline in this plan (## Validate Contract), Gate CONDITIONAL first pass.
Execute start: `uv run --project api pytest api/ -q` baseline (789 passed/5 deselected) | `uv run --project api pytest api/tests/data/test_cache_atomic_writes.py -q` | gitignore throwaway-repo check | high-risk pack: no (destructive-write class, covered by fully-automated round-trip + interrupted-write tests)
