---
name: plan:pipeline-completeness-atomic-writes
description: "Make every parquet write in api/data/cache.py atomic (temp in same dir, fsync, os.replace) — prerequisite of P2 automatic resume (deployability SPEC OQ9/OQ10, AC12)"
date: 29-09-26
feature: none (general-plans, P1 lane)
---

# Atomic parquet writes in `api/data/cache.py` — PLAN (SIMPLE)

TL;DR: add one private helper `_atomic_to_parquet(df, path)` to `cache.py` (unique temp file in the same directory → write → fsync → `os.replace`; temp removed on any exception) and route the 9 existing `.to_parquet(` call sites in `api/data/cache.py` through it (cache.py ONLY — see KG5: `etf_flows_adapter.py` has a separate non-atomic writer that is out of this assignment). Add one `api/tests/data/test_cache_atomic_writes.py` (isolated, offline). Add one `.gitignore` line so a leftover temp from a hard kill can never be committed by the nightly workflows. No refactor, no signature or behaviour change (T21).

**Status**: PLANNED — PVL supplement cycle 1 applied (N1-N4 RESOLVED); PVL supplement cycle 2 APPLIED 29-09-26 (N6 G1 grep literal, N7 liqtide_payload interrupted test, N8 EAFP mode lookup, plus `$SCRATCH` definition). VALIDATE must re-run from V1 before EXECUTE (the `## Validate Contract` below predates cycle 2 and still quotes the pre-fix literals as history).
**Complexity**: SIMPLE

## Overview

Context: `process/context/all-context.md` (Key Patterns: "numbers are never silently wrong"); testing context `process/context/tests/all-tests.md` (pytest, `integration` marker deselected, offline). A power loss mid-`to_parquet` can truncate a whole series; this makes each parquet write all-or-nothing so the P2 auto-resume-on-boot can be enabled safely.

## Acceptance Criteria

- (a) Every raw `.to_parquet(` call in `api/data/cache.py` (that file only; no repo-wide claim) routes through `_atomic_to_parquet`: `grep -c '\.to_parquet(' api/data/cache.py` = 1 (the single call inside the helper) and `grep -c '_atomic_to_parquet(' api/data/cache.py` = 10 (1 def + 9 calls) — proven by: G1 + `test_no_bypass`, strategy: Fully-Automated. Not covered: `api/data/etf_flows_adapter.py::merge_into_cache` (KG5).
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
| D1 | Helper `_atomic_to_parquet(df: pd.DataFrame, path: Path) -> None`, private, placed right after `_as_utc`. Body: `fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")`; open `os.fdopen(fd, "wb")` as `fh`; `df.to_parquet(fh, index=False)`; `fh.flush(); os.fsync(fh.fileno())`; close; `os.replace(tmp, path)`. **File mode (explicit):** after the handle is closed and before `os.replace`, `os.chmod(tmp, mode)` where `mode` = the existing target's permission bits (`os.stat(path).st_mode & 0o7777`) when the target exists, otherwise `0o644`. **The mode is read EAFP:** `try: mode = os.stat(path).st_mode & 0o7777` / `except FileNotFoundError: mode = 0o644` — NOT `path.exists()` followed by `stat()`, so a target that vanishes between the two calls cannot spuriously fail the write. `mkstemp` creates 0600, so without this the parquet would silently become 0600. This does NOT claim to "preserve the previous mode" in general: a plain path write yields `0666 & ~umask` (0644 / 0664 / 0600 under umask 022 / 002 / 077), so a first-ever write is normalised to 0644 (hard-coding 0644 for existing files would loosen a 0600 file under umask 077, hence copy-from-target). On Windows `os.chmod` only toggles the read-only bit (0o644 leaves it writable) — effectively a no-op. On ANY exception (`BaseException`, so KeyboardInterrupt too): best-effort `os.unlink(tmp)` (swallow `OSError`), then re-raise. The helper's docstring/comments must NOT contain the literal text `.to_parquet(` (leading dot) and must NOT repeat the name followed by `(` (`_atomic_to_parquet(`), so that `grep -c '\.to_parquet(' api/data/cache.py` = 1 (the single raw call inside the helper) and `grep -c '_atomic_to_parquet(' api/data/cache.py` = 10 (1 definition + 9 call sites) hold exactly. Note: the plain pattern `to_parquet(` (no dot) would count 11, because the helper's own name contains it — never use it as a gate. | Same dir → same filesystem → `os.replace` is an atomic rename. `mkstemp` gives an OS-guaranteed unique name (no collision between concurrent writers, e.g. nightly job + resume script). Leading dot + `.tmp` suffix means no `*.parquet` glob matches it. | (a) fixed `path.with_suffix(".parquet.tmp")` like the JSON writers — two concurrent writers of the same file would clobber each other's temp; (b) `tempfile` in system temp dir — cross-filesystem, `os.replace` not atomic / fails on Windows across drives; (c) write-then-validate-by-reading-back — extra cost, rename-after-complete-write already gives the guarantee; (d) a shared refactor of all writers — forbidden by T21. |
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

1. Baseline: `uv run --project api pytest api/ -q 2>&1 | tail -3` — record passed/deselected. Define `SCRATCH` first: `SCRATCH=/tmp/claude-0/-home-user-psychic-train/556ebfba-efff-5917-8bb5-0d5715181672/scratchpad/atomic-writes; mkdir -p "$SCRATCH"` (the session scratchpad directory, OUTSIDE the repo; if EXECUTE runs in a different session, use that session's scratchpad path — never a path inside the repo). Snapshot real data: `{ find api/data/cache -type f -printf '%p %s %T@\n' | sort; find api/data/watchlist.json -printf '%p %s %T@\n' 2>/dev/null; } > $SCRATCH/before.txt` (path + size + mtime), plus a content-hash snapshot `{ find api/data/cache -type f -exec sha256sum {} + | sort; sha256sum api/data/watchlist.json 2>/dev/null; } > $SCRATCH/before.sha` (scratchpad, never the repo). Size+mtime is required because parquet writes are deterministic, so a hash-only diff misses an identical-content rewrite.
2. Write `api/tests/data/test_cache_atomic_writes.py` first (red). Module-level `@pytest.fixture(autouse=True) def _isolate(isolated_cache, tmp_path, monkeypatch)` that also `monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH", tmp_path / "watchlist.json")` (import from `api.data.watchlist` via whatever name it exports — confirm the attribute exists before patching; `raising=True`). Every test additionally names `isolated_cache` in its signature. Tests:
   - `test_helper_round_trip` — helper writes, `pd.read_parquet` equals input, no `*.tmp` left in dir.
   - `test_interrupted_write_preserves_original` (AC12, helper level) — write v1; record bytes; monkeypatch `pd.DataFrame.to_parquet` with a fake that (i) when handed a `Path`/`str` TRUNCATES that target and writes 10 junk bytes, and (ii) when handed a file handle writes 10 junk bytes to it, then raises `RuntimeError`. The Path-truncating branch is mandatory: a handle-only fake raises AttributeError on the old path-based code, leaves the file intact and passes vacuously; the truncating fake genuinely corrupts current code, so the test is red-first; call helper with v2 → raises; original bytes identical, `pd.read_parquet` readable and equals v1, `list(dir.glob("*.tmp")) == []`.
   - `test_replace_failure_preserves_original` — monkeypatch `cache.os.replace` (note `cache.os` IS the process-global `os` module) with a fake that raises `OSError` ONLY when the destination is under the isolated root (`tmp_path`) and delegates to the real `os.replace` otherwise; same asserts.
   - `test_first_write_interrupted_leaves_no_file` — no prior file; interrupted → target does not exist, no temp.
   - Parametrised per writer family (9 writers) `test_<writer>_interrupted_preserves_prior` — call real writer once (valid), then again with the interruption monkeypatch, where the second call MUST actually reach the write: `write_liqtide_payload` and `write_exchange_point` use a NEW date on the second call (same-date is a guarded no-op / returns False); `merge_onchain_series` second call inserts or revises at least one point (otherwise `wrote_file` is False and nothing is written) → original byte-identical, readable via the module's own `read_*`, no temp. **Exception — `write_liqtide_payload` (N7):** a new date targets a DIFFERENT file, so the date-1 original is never the write target and a byte-identical assertion alone would pass vacuously on the unmodified code. For this writer assert, after the interrupted new-date call: (i) the new date's path does NOT exist (on unmodified code the truncating fake leaves junk there, so this assertion is red-first), (ii) no `*.tmp`/`.*.tmp` remains, (iii) the date-1 file is byte-identical and readable. What this proves: an interrupted first write of a new date leaves no partial file and does not disturb earlier dates. What it does NOT prove: overwrite-atomicity for this writer — the `if not path.exists()` no-overwrite guard means the real writer never rewrites an existing date, so its red-first behaviour differs from the other eight (whose truncating-fake red run hits the existing target); an overwrite of an existing liqtide file is exercised only at helper level (`test_interrupted_write_preserves_original`) or if the guard were bypassed.
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
| G1 `grep -c '\.to_parquet(' api/data/cache.py` = 1 (the single call inside the helper) and `grep -c '_atomic_to_parquet(' api/data/cache.py` = 10 (1 def + 9 calls); plus `test_no_bypass` (`.to_parquet(` with leading dot, exactly 1) | Fully-Automated | (a) no writer IN `api/data/cache.py` bypasses the helper (cache.py only; other modules, e.g. etf_flows_adapter, not covered — KG5) |
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
2. Last completed step: PLAN + independent VALIDATE pass 1 (CONDITIONAL) + PVL supplement cycle 1 (4 gaps) + independent VALIDATE pass 2 (CONDITIONAL, N6-N8) + PVL supplement cycle 2 APPLIED (N6-N8 + `$SCRATCH`). EXECUTE not started.
3. Validate-contract: written below (`Gate: CONDITIONAL`, second independent pass; it predates supplement cycle 2 and is kept intact). Cycle 2 applied N6-N8; VALIDATE MUST re-run from V1 and reach `Gate: PASS` before EXECUTE.
4. Context loaded: P2 deployability SPEC (OQ9/10, §4, AC12), `api/data/cache.py`, `api/tests/conftest.py`, `process/MASTER-PLAN.md` T21/T22, P1 plan (T22 isolation pattern), `.gitignore`, `.github/workflows/*` `git add` lines, `pairs_response.py` L130-185.
5. Next step for a fresh agent: orchestrator re-spawns vc-validate-agent from V1 (supplement cycle 2 applied). Only after `Gate: PASS`: checklist step 1 (baseline + size/mtime/hash snapshot), then step 2.

## Validate Contract

Status: CONDITIONAL
Date: 29-09-26
date: 2026-09-29
generated-by: outer-pvl
supersedes: 2026-09-29 (outer-pvl; independent first pass, CONDITIONAL with N1-N4) — this second independent pass, run after PVL supplement cycle 1, has current evidence

Parallel strategy: sequential
Rationale: score 2/7 (S2 destructive-write data path, S6 high-risk class); 3 files, one dominant surface. The validator ran the Layer 1/Layer 2 checks itself (subagents cannot spawn agents) with scratch-dir experiments; no fan-out needed. `vc-scenario`/`vc-predict` were not invoked: every concern below is mechanical and was reproduced directly.

Validator provenance: written by an independent vc-validate-agent pass (not the plan's author, not the pass-1 validator). All experiments ran in the session scratchpad; the real repo, `api/data/cache` and `.gitignore` were only read. `git status --short` = empty before and after.

### Supplement cycle 1 verification (N1-N4)

| Item | Verdict | Where it landed / what was checked |
|---|---|---|
| N1 etf_flows_adapter bypass recorded, scope NOT widened | RESOLVED | TL;DR ("cache.py ONLY — see KG5"); AC(a) "that file only … Not covered: `etf_flows_adapter.py::merge_into_cache` (KG5)"; Phase Completion Rules "P2's AC12 … NOT fully met until `etf_flows_adapter.merge_into_cache` also goes through an atomic helper"; Blast Radius "HARD OUT OF SCOPE" lists `etf_flows_adapter.py`, `seed_e2e_cache.py` and every other path in the assignment; Touchpoints = exactly `api/data/cache.py`, `api/tests/data/test_cache_atomic_writes.py`, one `.gitignore` line, task folder; Verification Evidence KG5 row; Known Gaps KG5 + Future Work + backlog stub. Citations checked against source: writer at `etf_flows_adapter.py:110`, request path `components.py:484` → `fetch_btc_spot_flows` → `:301`; `seed_e2e_cache.py:232` is a CALLER of `merge_into_cache` (not a second writer; wording is loose but harmless). Repo-wide search for `to_parquet|write_table|COPY|ParquetWriter` outside tests finds only `cache.py` (9), `etf_flows_adapter.py:110` (KG5) and `pairs_response.py:174,183` (D5/KG3) — the gap list is complete. Scoping caveat: the G1 COMMAND is defective (N6) although its scope wording is honest. |
| N2 file mode | RESOLVED (+N8 clarity) | D1 now states: copy existing target mode (`os.stat(path).st_mode & 0o7777`), else 0o644; chmod between close and `os.replace`; umask caveat and Windows caveat honest; Risks and `test_mode_handling` consistent with it. Scratch-verified with a D1-mirror helper: first write → 0o644; overwrite of a 0o600 file → 0o600; target absent → 0o644; `os.stat` raising `FileNotFoundError` (race) is handled when written EAFP (try/except) and the write still succeeds. The plan does not say EAFP; an `exists()`-then-`stat()` implementation would turn the race into a spurious (safe: temp removed, original intact) exception → N8, one clause. |
| N3(a) truncating Path-fake | RESOLVED | Step 2 `test_interrupted_write_preserves_original` mandates it. Reproduced (see below): the truncating fake fails 8 of 9 real writers on the current code; a handle-only fake passes 9 of 9 vacuously on the current code. |
| N3(b) second call must reach the write | PARTIAL | Correct for `write_exchange_point` (same per-category file) and `merge_onchain_series`. NOT sound for `write_liqtide_payload`: a NEW date targets a DIFFERENT file, so "original byte-identical" is vacuous — it PASSES on the current non-atomic code even with the truncating fake (reproduced). → N7. |
| N3(c) canary | RESOLVED | `test_isolation_canary` (step 2) mirrors `test_bootstrap_watchlist.py:28` / `test_backfill_primaries.py:28`; `DEFAULT_WATCHLIST_PATH` exists (`watchlist.py:41`). |
| N3(d) global `os.replace` patch + docstring text | PARTIAL | `os.replace` fake is scoped to destinations under `tmp_path` and delegates otherwise: RESOLVED. The "no literal `to_parquet(` in the helper docstring" rule is mis-specified: the helper's own NAME `_atomic_to_parquet(` contains the substring `to_parquet(`, so plan gate G1 (`grep -c "to_parquet(" api/data/cache.py` = 1) returns **11** after the change (measured on a patched scratch copy: 1 raw call + 1 def + 9 calls). `test_no_bypass` (which greps `.to_parquet(` with the leading dot) is correct = 1. → N6. |
| N4 snapshot strength (size+mtime+sha256+watchlist) | RESOLVED | Steps 1 and 6 use `find … -printf '%p %s %T@\n'` (nanosecond mtime) AND `sha256sum`, plus `watchlist.json`; real cache has 57 files, `api/data/watchlist.json` is absent in this container and the `2>/dev/null` form tolerates that. An identical-content rewrite changes mtime, so it is now detected. Minor: `$SCRATCH` is not defined in the plan (E4). |
| T22 conftest untouched | RESOLVED | `api/tests/conftest.py` is in the hard-out-of-scope list and absent from Touchpoints; `isolated_cache` is only requested, never edited. |

### New independent evidence (what was actually run)

- **Byte equivalence through the real writers.** Scratch copy of `cache.py` with the D1 helper and all 9 sites swapped (regex on the 9 real lines). Each of the 9 real writer families (`write_ohlcv`, `write_liqtide_payload`, `write_liqtide_backfill`, `write_liquidity_series`, `write_confirmed_boundaries`, `write_narrative_point`, `write_trending_snapshot`, `write_exchange_point`, `merge_onchain_series`) produces a file **byte-identical** to the current code (9/9). Behaviour unchanged.
- **Red-first reproduction (per-writer interrupted-write test, scratch pytest, 40 cases).** Against the CURRENT `cache.py` with the truncating fake: 8 FAIL ("original corrupted": ohlcv, liqtide_backfill, liquidity, boundaries, narrative, trending, exchange, onchain) and 1 passes vacuously (`liqtide_payload`). Handle-only fake against current code: 9/9 pass vacuously. Against the patched copy: all 18 (both fakes × 9 writers) pass — original byte-identical, readable, zero `*.tmp`/`.*.tmp` left. Mode test and stat-race test pass on the patched copy. So the corrected design (step 2) is genuinely red-first, except for the `liqtide_payload` per-writer case (N7).
- **`.gitignore` (D6) reproduced** in a throwaway repo (copy of the real `.gitignore` + `api/data/cache/**/*.tmp` after the three negations): `git add` of `liqtide/`, `narrative/`, `onchain/` (incl. `liqtide/raw`, `narrative/pytrends`, `onchain/growthepie/base`) stages the 6 real parquets and 0 temps; `git check-ignore -v` attributes `.gitignore:48` to the deepest temp. Real `.gitignore` currently has no `tmp` rule (grep empty).
- **Reader safety re-audited:** repo-wide globs are `*.parquet`, `*/*/*.parquet`, `*.json`, `iterdir()`+`is_dir()`, or exact paths; `.name.parquet.<rand>.tmp` matches none.
- **Isolation soundness (T22):** `isolated_cache` patches `cache.CACHE_ROOT` (read at call time by every path function); `watchlist_store.DEFAULT_WATCHLIST_PATH` redirect + canary + per-test `SETUP    F isolated_cache` count + size/mtime/sha256 before/after diff together cover cache and watchlist. Residual: the `find` covers files only, not new empty directories, and covers `api/data/cache` only (not a `SCREENER_CACHE_ROOT` override) — advisory.
- **Forbidden-path check:** plan touches only `api/data/cache.py`, `api/tests/data/test_cache_atomic_writes.py`, one `.gitignore` line, the task folder. `web/`, `api/main.py`, deploy/CORS, `pytrends_adapter.py` + test, `watchlist.py`, `ccxt_adapter.py`, `api/analytics/**`, `process/context/**`, `conftest.py`, `.github/workflows/*`, `etf_flows_adapter.py`, `seed_e2e_cache.py` are all named out of scope. Checklist step 9 (backlog stub) is an UPDATE PROCESS action, not an EXECUTE touchpoint. No forbidden path touched.
- Plan structure validator: `validate-plan-artifact.mjs` = 0 failures, 0 warnings (275 lines). Carried baseline: 789 passed / 5 deselected (`uv run --project api pytest api/ -q`, recorded at HEAD `df2c3c9`; HEAD `bf4681a` differs only by process files; EXECUTE re-records it).

### Net gate derivation

| Layer 1 dimensions | Status |
|---|---|
| Infra fit | PASS — KG5 bypass recorded, scope honest, repo-wide writer search complete |
| Test coverage | CONCERN — N6 (G1 grep cannot pass as written), N7 (liqtide_payload per-writer case vacuous); structural KG1/KG2 |
| Breaking changes | PASS — 9/9 writers byte-identical; signatures/paths/formats unchanged; mode policy explicit |
| Security surface | PASS — `.gitignore` rule reproduced; mode copy avoids loosening a 0600 file |

| Layer 2 sections | Status |
|---|---|
| Helper (D1/D2/D7) | PASS mechanics; CONCERN (low) N8 — say EAFP stat |
| 9 call-site swap (D3) | PASS — sites at L106/210/283/312/340/388/407/512/632, guards and mkdirs preserved |
| Reader safety | PASS |
| `.gitignore` (D6) | PASS — reproduced |
| Test plan (step 2) | CONCERN — N7 |
| Gate commands (Verification Evidence / G1) | CONCERN — N6 |
| T22 isolation (steps 1/6) | PASS |
| Scope / KG5 honesty | PASS |
| Known-gap honesty (KG1-KG5) | PASS |

Totals: **0 FAILs / 3 new fixable CONCERNs (N6, N7, N8) / 4 items RESOLVED (N1-N4 from cycle 1) / rest PASS** → Net Gate: **CONDITIONAL, NOT terminal**. Every cycle-1 fix landed except two partials (N3b, N3d) which are exactly N7 and N6. Because N6 makes a mandatory gate impossible to pass as written, `PHASE_COMPLETE: VALIDATE` is withheld; a second, small PVL supplement cycle is required. Structural gaps (KG1, KG2) and recorded-not-fixed gaps (KG3, KG4, KG5) would be acceptable CONDITIONAL residuals on their own and are not what blocks the signal.

### Concerns (numbered, with resolution route)

- **N6 (fixable, one line, HIGH within this plan)** — G1 as written cannot pass. `grep -c "to_parquet(" api/data/cache.py` counts every line containing the substring, including `def _atomic_to_parquet(` and its 9 call sites → **11**, not 1 (measured). Fix: use `grep -c '\.to_parquet(' api/data/cache.py` = 1 (matches only the raw call inside the helper; `_atomic_to_parquet(` has an underscore, not a dot, before `to_parquet`), and `grep -c '_atomic_to_parquet(' api/data/cache.py` = 10 (1 def + 9 calls; only if the helper's docstring/comments do not repeat the name followed by `(`). Reword D1's "must NOT contain the literal text `to_parquet(`" to "must NOT contain the literal text `.to_parquet(`" and keep `test_no_bypass` as is. Places: D1 (last sentence), Verification Evidence G1 row.
- **N7 (fixable)** — `write_liqtide_payload` per-writer interrupted test is vacuous: the interrupted second call uses a NEW date → a different file → the date-1 original is never targeted (reproduced: passes on current code with the truncating fake). Fix in step 2: for this writer assert that after the interrupted new-date call the NEW date's path does NOT exist (that fails on the current code, which leaves junk there), no `.tmp`, and the date-1 file is byte-identical; keep the existing-target-overwrite assertions for the other 8 writers.
- **N8 (fixable, low)** — D1 should say the mode lookup is written EAFP: `try: mode = os.stat(path).st_mode & 0o7777 / except FileNotFoundError: mode = 0o644`, not `if path.exists()` then `stat` (a vanishing target would otherwise raise spuriously; failure would be safe but avoidable). Reproduced working in scratch.
- **Structural / recorded, not fixable by planning:** KG1 power loss/SIGKILL durability (fsync untested, no dir fsync); KG2 Windows `os.replace` vs an open reader (the always-on box is the user's own PC); KG3 `pairs_response` not fsynced; KG4 JSON writers' fixed temp name; KG5 `etf_flows_adapter.merge_into_cache` bypass — P2 AC12 NOT fully met.

### SUPPLEMENT REQUEST

- Gap 1: Section [decisions, verification-evidence] | Concern: N6 — G1 `grep -c "to_parquet(" api/data/cache.py` = 1 cannot pass (returns 11 because `_atomic_to_parquet(` contains the substring); D1's docstring rule quotes the wrong literal | Severity: CONCERN | Suggested addition: change G1 (and D1's docstring rule) to `grep -c '\.to_parquet(' api/data/cache.py` = 1 plus `grep -c '_atomic_to_parquet(' api/data/cache.py` = 10.
- Gap 2: Section [implementation-checklist] | Concern: N7 — per-writer interrupted test for `write_liqtide_payload` targets a different file (new date) and passes on the unmodified code | Severity: CONCERN | Suggested addition: in step 2, for `write_liqtide_payload` assert the interrupted new-date path does not exist (+ no temp, date-1 file byte-identical).
- Gap 3: Section [decisions] | Concern: N8 — D1 does not say how a missing/vanishing target is handled when copying mode | Severity: CONCERN (low) | Suggested addition: add one clause to D1: mode is read with try/except FileNotFoundError → 0o644 (EAFP), not exists()+stat.

### Test gates (5-column table)

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| (a) / G1 | every raw parquet write in `cache.py` goes through `_atomic_to_parquet` (cache.py only; KG5 excluded) | Fully-Automated | `grep -c '\.to_parquet(' api/data/cache.py` = 1; `grep -c '_atomic_to_parquet(' api/data/cache.py` = 10; `test_no_bypass` (N6: plan text still has the broken pattern) | B |
| (b) / G2 | interrupted write, `os.replace` failure and first-write interruption leave original byte-identical, readable, no `*.tmp` | Fully-Automated | `uv run --project api pytest api/tests/data/test_cache_atomic_writes.py -q` (helper-level + 9 per-writer tests; fake truncates on Path; liqtide_payload asserts new-date path absent — N7) | B |
| (c) / G3 | normal round-trip unchanged per writer; liqtide no-overwrite; onchain write-only-when-changed; mode 0644 / existing mode kept | Fully-Automated | same file, per-family round-trip + `test_mode_handling` | B |
| (e) / G4 | narrative/exchange RMW keep prior rows after interrupted second write | Fully-Automated | same file, AC(e) tests (interrupted call uses a new date) | B |
| (d) / G5 | no regression | Fully-Automated | `uv run --project api pytest api/ -q` = baseline (789 passed / 5 deselected, re-record in step 1) + new tests, 0 failed | A |
| (f) / G6 | tests never touch real cache or `watchlist.json` | Fully-Automated | `--setup-show \| grep -c "SETUP    F isolated_cache"` == collected count; `test_isolation_canary`; before/after `find … -printf '%p %s %T@\n'` and `sha256sum` diffs both empty | B |
| D6 / G7 | stray temp never staged by nightly `git add` | Fully-Automated | throwaway-repo `git add` + `git check-ignore -v` (reproduced by this validator: 6 parquets staged, 0 temps) | A |

Named residuals (NOT strategies; gap-resolution D unless stated):
- KG1 power-loss/SIGKILL durability, no dir fsync — D.
- KG2 Windows `os.replace` vs open reader — D (user-PC check optional).
- KG3 `pairs_response` writes not fsynced (out of lane) — D.
- KG4 JSON writers' fixed temp name (T21) — D.
- KG5 `etf_flows_adapter.merge_into_cache` non-atomic parquet write, request path, git-ignored — C/D per the user's scope decision; P2 AC12 NOT fully met until fixed.

Failing stubs (Fully-Automated rows, TDD red-first; scenario text verbatim; language-neutral skeleton, the real tests are pytest):
```
test("should route every to_parquet call in cache.py through _atomic_to_parquet", () => { throw new Error("NOT IMPLEMENTED — TDD stub: no bypass") })
test("should leave the original file byte-identical and readable when the write is interrupted", () => { throw new Error("NOT IMPLEMENTED — TDD stub: interrupted write") })
test("should behave identically to the non-atomic writers on the normal path", () => { throw new Error("NOT IMPLEMENTED — TDD stub: round-trip unchanged") })
test("should keep prior rows after an interrupted second write to narrative and exchange series", () => { throw new Error("NOT IMPLEMENTED — TDD stub: RMW preserved") })
test("should not touch the real cache or watchlist", () => { throw new Error("NOT IMPLEMENTED — TDD stub: isolation") })
```

Offline gate commands EXECUTE / EVL must run (all offline, run from repo root; `SCRATCH` = a directory in the session scratchpad OUTSIDE the repo):
1. `uv run --project api pytest api/ -q 2>&1 | tail -3` (baseline; record passed/deselected; expected 789 passed / 5 deselected)
2. before snapshots: `{ find api/data/cache -type f -printf '%p %s %T@\n' | sort; find api/data/watchlist.json -printf '%p %s %T@\n' 2>/dev/null; } > $SCRATCH/before.txt` and `{ find api/data/cache -type f -exec sha256sum {} + | sort; sha256sum api/data/watchlist.json 2>/dev/null; } > $SCRATCH/before.sha`
3. red run of the new test file on unmodified `cache.py` (helper-level tests fail: helper absent; per-writer truncating-fake tests must fail for all 9 writers, including liqtide_payload once N7 is applied)
4. `grep -c '\.to_parquet(' api/data/cache.py` → `1`; `grep -c '_atomic_to_parquet(' api/data/cache.py` → `10`
5. `uv run --project api pytest api/tests/data/test_cache_atomic_writes.py -q` → all pass
6. `uv run --project api pytest api/tests/data/test_cache_atomic_writes.py -q --setup-show | grep -c "SETUP    F isolated_cache"` → equals the collected test count
7. `uv run --project api pytest api/ -q` → baseline + new tests, 0 failed
8. after snapshots (same two commands → `$SCRATCH/after.txt`, `$SCRATCH/after.sha`); `diff $SCRATCH/before.txt $SCRATCH/after.txt` and `diff $SCRATCH/before.sha $SCRATCH/after.sha` both empty
9. throwaway-repo gitignore proof in `$SCRATCH` (never the real repo): copy `.gitignore`, create `api/data/cache/{liqtide,narrative,onchain}/…/.x.parquet.abc.tmp` + real parquets, `git add` the three dirs, `git status --porcelain` shows only parquets; `git check-ignore -v` on temps in `liqtide/` and `onchain/`
10. scope guard: `git status --porcelain` lists only `api/data/cache.py`, `api/tests/data/test_cache_atomic_writes.py`, `.gitignore`, and files inside the task folder; `api/tests/conftest.py` and `api/data/etf_flows_adapter.py` unmodified

Binding execute-agent instructions:
- E1: use the corrected G1 patterns from N6 (`\.to_parquet(`), not the broken text still present in the plan body until the supplement lands.
- E2: read the target mode EAFP (try/except FileNotFoundError → 0o644), chmod before `os.replace`, all inside the try that cleans the temp on `BaseException`.
- E3: for `write_liqtide_payload` assert the new-date target does not exist after the interrupted call (N7).
- E4: define `SCRATCH` as a scratchpad path outside the repo before step 1; never write snapshots into the repo.
- E5: never `git add/commit/stash/checkout/restore` the real repo for experiments.
- E6: KG5 stays recorded, not fixed; do not touch `etf_flows_adapter.py` or `seed_e2e_cache.py`; do not import the private helper from another module.
- E7: the handle-only fake alone is vacuous; keep the truncating Path-fake.
- E8: EXECUTE report notes the mode behaviour (D1) and the KG5 scope statement.

Legacy line form:
- cache.py writers: [Fully-automated: `uv run --project api pytest api/tests/data/test_cache_atomic_writes.py -q`] | [Fully-automated: `uv run --project api pytest api/ -q`] | [Fully-automated: throwaway-repo gitignore check] | [Fully-automated: `grep -c '\.to_parquet(' api/data/cache.py` = 1] | [known-gap: power loss, Windows open-reader, etf_flows_adapter bypass — documented]

Dimension findings:
- Infra fit: PASS — KG5 recorded honestly, scope not widened, repo-wide writer search complete.
- Test coverage: CONCERN — N6 (G1 grep returns 11, cannot pass), N7 (liqtide_payload per-writer test vacuous); power loss untestable here.
- Breaking changes: PASS — 9/9 real writers byte-identical after the swap; mode policy explicit and tested.
- Security surface: PASS — `.gitignore` reproduced; no permission loosening.
- Helper section: PASS mechanics; CONCERN (low) N8.
- Call-site swap section: PASS — 9 sites, guards and mkdirs preserved.
- Reader-safety section: PASS.
- `.gitignore` section: PASS — reproduced.
- Scope: PASS — forbidden paths untouched.

Open gaps:
- N6, N7, N8 (fixable plan text; SUPPLEMENT REQUEST above).
- KG1-KG5 residuals above (KG5: P2 AC12 NOT fully met; needs a user scope decision).

What this coverage does NOT prove:
- G1/`test_no_bypass`: does not prove no OTHER module writes cache files atomically-or-not (`etf_flows_adapter` does not; `pairs_response` is atomic but unsynced).
- G2/G4: prove that a SIMULATED exception (fake `to_parquet`, failing `os.replace`) leaves the original intact; they do NOT prove behaviour under real power loss, SIGKILL mid-write, a full disk, or an fsync the OS ignores.
- G3: proves round-trip on synthetic frames, not on the real 57-file cache.
- G5: proves no regression in the existing suite, not real-network refresh behaviour.
- G6: proves these tests did not modify the real cache/watchlist (files only, `api/data/cache` only); it does not prove other suites are isolated.
- G7: proves git ignores a `.tmp` in the tracked dirs; not that no other stray file type can be committed.
- Windows: nothing here proves `os.replace` succeeds while DuckDB/the API holds a read handle.

Gate: CONDITIONAL (second independent pass; cycle-1 items N1-N4 RESOLVED; 3 new small fixable concerns N6-N8 outstanding → NOT terminal, PVL supplement cycle 2 required before EXECUTE; structural gaps KG1/KG2 and recorded gaps KG3/KG4/KG5 remain)
Accepted by: NO HUMAN has accepted any concern or known-gap. KG1, KG2, KG3, KG4, KG5 are carried provisionally under the autonomous-run policy only. N6-N8 are NOT accepted — they are open supplement items.

## Autonomous Goal Block

SESSION GOAL: Make every parquet write in api/data/cache.py atomic (temp + fsync + os.replace) so P2 auto-resume is safer (AC12 for cache.py writers only; KG5 etf_flows_adapter still open).
Charter + umbrella plan: N/A — single plan (sibling program plan: process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness_PLAN_28-09-26.md, no Stable Program Goal).
Autonomy: standing autonomous execution per feedback_autonomous_phase_execution.md; removes approval pauses only, subagent delegation stays mandatory.
Hard stops / safety constraints:
- Never touch real api/data/cache or watchlist.json; tests use isolated_cache + watchlist redirect (T22); conftest.py stays unmodified.
- Files allowed: api/data/cache.py, api/tests/data/test_cache_atomic_writes.py, one .gitignore line, this task folder. web/, api/main.py, workflows, pytrends, watchlist.py, ccxt_adapter.py, api/analytics/**, process/context/**, etf_flows_adapter.py, seed_e2e_cache.py are out of scope.
- Never git add/commit/stash/checkout the real repo for experiments; use a scratch repo.
- Do not widen scope to etf_flows_adapter.py without an explicit user decision (KG5).
- Do not run EXECUTE until PVL supplement cycle 2 (N6-N8) is applied and VALIDATE re-runs from V1.
Next phase: PVL supplement (vc-plan-agent) for N6-N8, then re-validate from V1; then EXECUTE: process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness-atomic-writes_PLAN_29-09-26.md
Validate contract: inline in this plan (## Validate Contract), Gate CONDITIONAL, second independent pass.
Execute start: `uv run --project api pytest api/ -q` baseline (789 passed/5 deselected) | `uv run --project api pytest api/tests/data/test_cache_atomic_writes.py -q` | `grep -c '\.to_parquet(' api/data/cache.py` = 1 | gitignore throwaway-repo check | high-risk pack: no (destructive-write class, covered by fully-automated round-trip + interrupted-write tests)
