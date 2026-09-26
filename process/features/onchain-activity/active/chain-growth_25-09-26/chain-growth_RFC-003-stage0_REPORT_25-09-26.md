---
phase: rfc-003-stage0
date: 2026-09-25
status: COMPLETE
feature: onchain-activity
plan: process/features/onchain-activity/active/chain-growth_25-09-26/chain-growth_PLAN_25-09-26.md
---

# chain-growth RFC-3 Stage 0: storage, nightly workflow, backfill (fallback scope, no Dune)

**TL;DR:** Store one Parquet file per (source, chain, metric) under `api/data/cache/onchain/`.
Each night, fetch the **full** history from growthepie (12 requests) and L2BEAT (4 requests),
6 s apart, and merge it with a **revision window**:
- New dates are inserted.
- Dates in the last 14 days are updated when the provider changes them, with `revised=true` and the old value kept.
- Older dates are never overwritten.

Because every run fetches full history, **no separate backfill script is needed**: the first run is
the backfill. The workflow `chain-growth-snapshot.yml` runs at 22:00 UTC, copies
`narrative-snapshot.yml` line for line, uses no secrets, and stages only `api/data/cache/onchain/`.
One user decision is optional (§7). Nothing has been written except this report.

Inputs read: the FEASIBILITY verdict, the RFC-1 outcome, RFC-2 Stage 0 §7–§8, the RFC-2 report,
`cache.py` (narrative/exchange/liqtide helpers), `.gitignore`, both snapshot workflows,
`snapshot_narrative.py`, `seed_e2e_cache.py` and `tests/conftest.py::isolated_cache`.

## 1. Storage schema, paths, write semantics

**Path:** `api/data/cache/onchain/{source}/{chain_id}/{metric}.parquet`
- `source` ∈ `growthepie`, `l2beat`
- `chain_id` is our id from `chains.json` (for example `polygon`, not `polygon_pos`)
- `metric` ∈ `active_addresses`, `transactions`

L2BEAT stores `transactions` only, taken from its `count` column. `uops_count` is dropped because no AC uses it.

**Columns** (`ONCHAIN_COLUMNS`):

| column | type | meaning |
|---|---|---|
| `date` | string `YYYY-MM-DD` (UTC) | the day the value describes |
| `value` | float64 | provider value (never null: a missing value means no row) |
| `first_seen_utc` | string ISO | when we first stored this date |
| `as_of_utc` | string ISO | when the current `value` was last written |
| `revised` | bool | true if the value ever changed after first storage |
| `previous_value` | float64, nullable | the value just before the latest revision |

**`cache.py` additions (additive only; no existing function changes):**
```python
ONCHAIN_COLUMNS = [...]
ONCHAIN_REVISION_WINDOW_DAYS = 14
def onchain_series_path(source: str, chain_id: str, metric: str) -> Path
def read_onchain_series(source: str, chain_id: str, metric: str) -> pd.DataFrame   # empty frame w/ columns if absent
def merge_onchain_series(source: str, chain_id: str, metric: str,
                         points: list[tuple[str, float]], *, today: str,
                         now_utc: str, window_days: int = ONCHAIN_REVISION_WINDOW_DAYS
                         ) -> OnchainMergeResult   # inserted, revised, unchanged, out_of_window_drift, wrote_file
```
This replaces the plan's `write_chain_growth_point` (one point per call). The fallback fetches full
series, so writing one point per call would do hundreds of Parquet rewrites per chain.

**Merge rule** (the decision asked for in the handoff):

| incoming date is… | action |
|---|---|
| not in the store | insert (`first_seen_utc = as_of_utc = now`, `revised=false`) |
| in store, within `today - 14 d` … `today`, value differs (`abs` diff > 1e-9 × max(1,\|v\|)) | replace; `previous_value = old`, `revised = true`, `as_of_utc = now` |
| in store, older than the window, value differs | **keep ours**, count as `out_of_window_drift` and log it in the summary line |
| in store, same value | no-op |
| in store but missing from provider response | **keep ours** (never deleted) |
| future date (> today UTC) | dropped |

The file is only rewritten when at least one row was inserted or revised. This keeps git diffs
empty on no-change nights, because a Parquet rewrite is not byte-stable.

**Why this and not pure first-observation-wins:** growthepie revises recent days, for example a
partial "today" figure that is completed later. Pure first-observation-wins would permanently
freeze an incomplete number, which is exactly "silently wrong". Pure overwrite would be honest
about the value but would hide that it changed. The window plus `revised`/`previous_value` keeps the
correct number and a visible trail. Freezing history older than 14 days keeps the archive stable if
the provider rewrites deep history or drops chains. The narrative precedent (first-observation-wins,
`write_exchange_point`) suited daily snapshots of a "right now" value. That does not apply here,
because this is a provider-maintained time series.

**Staleness:** there is no daily "unavailable" row. A failed fetch leaves the file untouched.
RFC-4 derives `stale` from `max(as_of_utc)` age. Solana, BNB and Tron (`source: "none"`) are skipped
before any fetch and never get a file (decided in RFC-2 Stage 0 §7).

**Redistributable (AC-9):** not stored per row. It comes from the adapter constant keyed by the
`source` path segment, which is one source of truth. Storing it per row would freeze stale flags if
terms change.

## 2. Backfill script: not needed

- growthepie `/v1/metrics/chains/{chain}/{metric}.json` and L2BEAT `?range=max` both return full
  history, so the nightly run with full-series merge *is* the backfill. The first run fills all
  history; later runs add new days and apply revisions.
- Request budget: 6 growthepie chains × 2 metrics = 12, plus 4 L2BEAT = **16 requests/night**.
  With `REQUEST_SPACING_SECONDS = 6` between calls to the same host, that is ~10 req/min and
  about 70 s per host. It stays under the unverified ~10 req/min limit.
- Bulk `/v1/export/{metric}.json` (2 requests) was rejected for the nightly job:
  - Its payload covers every chain growthepie tracks (large).
  - One failure loses all chains, which weakens AC-12 isolation.
  - Its real shape is less confirmed than the per-chain one.
- History depth (the RFC-1 known gap) becomes an output: the first run's summary line prints the
  first and last date per series, which answers it for RFC-4.
- **Plan deviation:** `backfill_chain_growth.py` is dropped. A `--only chain[,chain]` flag on the
  snapshot script covers "refill one chain by hand".

## 3. Workflow `.github/workflows/chain-growth-snapshot.yml`

- `on: schedule: cron "0 22 * * *"` + `workflow_dispatch: {}`. This is 60 min before narrative
  (23:00) and 90 min before liqtide (23:30), matching the plan's runbook. The runtime is ~2–3 min
  including `uv sync`.
- `permissions: contents: write` only.
- `concurrency: {group: chain-growth-snapshot, cancel-in-progress: false}`.
- No `pull_request` trigger. **No `env:` secrets at all.**
- Steps are identical to narrative (E1 diff check):
  1. checkout@v4, setup-uv@v3, `uv sync --project api`.
  2. `uv run --project api python -m api.scripts.snapshot_chain_growth`, with the same exit-code
     capture: `1` → fail job; `2` → `::warning::`.
  3. Commit with `git add api/data/cache/onchain/` **only**.
  4. The same 3-attempt `git pull --rebase` + push retry.
  - Commit message: `chore: chain-growth snapshot YYYY-MM-DD`.
- `.gitignore`: add after the narrative block
  ```
  # Chain-growth archive (chain-growth RFC-3): provider revisions and possible
  # loss of deep history make the nightly merged series worth keeping.
  !api/data/cache/onchain/
  ```
- `git check-ignore -v` test list (run in Stage 1, recorded in `verification.json`). Expected
  results:

  | path | expected |
  |---|---|
  | `api/data/cache/onchain/growthepie/base/active_addresses.parquet` | **not ignored** (exit 1) |
  | `api/data/cache/onchain/l2beat/base/transactions.parquet` | not ignored |
  | `api/data/cache/narrative/pytrends/x.parquet` | not ignored (unchanged) |
  | `api/data/cache/liqtide/2026-09-20.parquet` | not ignored (unchanged) |
  | `api/data/cache/narrative/coingecko_trending.parquet` | ignored (unchanged) |
  | `api/data/cache/ohlcv/x.parquet` | ignored (unchanged) |

## 4. Script `api/scripts/snapshot_chain_growth.py`

- **CLI:**
  - `--dry-run` sets `cache.CACHE_ROOT` to a `tempfile.mkdtemp` and restores it in `finally`, exactly like snapshot_narrative.
  - `--verify-only` reads the stored series and prints row count, first/last date, revised count and last `as_of` per series, with no network.
  - `--only ethereum,base` limits the run to those chains.
  - `--window-days N` sets the revision window (default 14).
- **Flow:** `load_chains()` → skip `source == "none"` with the line `solana: skipped (source-unavailable)`
  → for each live chain and metric, call `growthepie_adapter.fetch_chain_metric` → merge. For each
  chain with `cross_check`, call `l2beat_adapter.fetch_activity(key, "max")` → merge `transactions`.
- **Spacing:** an injectable `sleep` (default `time.sleep`) is called between requests, so tests don't wait.
- **Isolation:**
  - Each (source, chain, metric) runs in its own `try/except Exception`.
  - An `unavailable` result or an exception prints one line and continues.
  - Adapters already never raise; the try/except guards the merge/IO.
- **Summary line per series:** `growthepie/base/active_addresses: ok inserted=3 revised=1 drift=0 rows=1024 first=2021-06-15 last=2026-09-24`, or `…: unavailable (http-429)`.
- **Exit codes:** `0` if ≥1 series succeeded; `2` if every attempted series was unavailable; `1` on an unexpected crash (top-level guard). This is the same contract as narrative.

## 5. Tests (isolated cache, no network)

`api/tests/data/test_cache_chain_growth.py` (uses the `isolated_cache` fixture):
- Round-trip through the real `merge_onchain_series` → `read_onchain_series`; column set and dtypes;
  empty read on a missing file. (append-only-dedup)
- Revision inside the window: value replaced, `revised=true`, `previous_value` set, `as_of` updated.
- Change outside the window: the stored value is kept and `out_of_window_drift == 1`.
- A date missing from the provider response stays stored; duplicate dates in the input dedupe.
- A no-change merge leaves the file mtime and bytes untouched (`wrote_file is False`).
- UTC: `today` near midnight UTC; future dates are dropped; all dates are `YYYY-MM-DD` strings.
- The path uses our `chain_id`, not the provider key.

`api/tests/scripts/test_snapshot_chain_growth.py` (fake adapters via monkeypatch, `sleep` stubbed):
- Multi-chain run where one chain raises, one returns unavailable and the rest succeed. The others
  are written and equal a solo run. (single-chain-failure-isolation, AC-12)
- solana/bnb/tron: no fetch call and no file under `onchain/`. (honest-missing-states, AC-7)
- `--dry-run`: the real `CACHE_ROOT` stays empty afterwards, and `CACHE_ROOT` is restored.
- Exit code 2 when all are unavailable; 0 on partial success.
- `--verify-only` makes no adapter calls.
- `sleep` is called between requests (spacing is enforced).

Gate commands are unchanged from the plan:
`uv run --project api pytest api/tests/data/test_cache_chain_growth.py api/tests/scripts/test_snapshot_chain_growth.py -q`,
plus a full `pytest api/ -q` (baseline 445 / 5 deselected). `actionlint` is not installed here, so the
workflow check is a manual line-by-line diff against narrative-snapshot.yml (Hybrid).

## 6. Risk-evidence pack (E2), `harness/rfc-003/`

- Written in Stage 1 with the code, and required before `🔨 CODE DONE`.
- Risk class: **deploy/runtime** (a new `contents: write` scheduled workflow). `mustStopBeforeFinalize: true`.
- `context-snippets.json`: the workflow trigger/permissions/push block, the `.gitignore` lines, and the merge function.
- `verification.json`: gate runs, `git check-ignore` table, and the E1 diff vs narrative.
- `review-decision.json`: `PENDING` until the user reviews it (manual-first, same as narrative RFC-4).
- `adversarial-validation.json` scenarios. Secret exfiltration is removed because there are no secrets.

| scenario | ruled out by |
|---|---|
| Fork PR triggers a write-capable run | no `pull_request`/`pull_request_target` trigger |
| Push collision with narrative/liqtide jobs on `main` | 60/90 min offset + own concurrency group + 3-try rebase retry |
| Job commits files outside the archive | `git add api/data/cache/onchain/` only |
| Malicious or garbage provider data lands on main | adapters drop null/NaN/negative values; parquet only (no code); out-of-window history is frozen; worst case is bad numbers, and they are revertible via git |
| Supply chain: third-party actions | only `actions/checkout@v4` + `astral-sh/setup-uv@v3`, the same as the precedents; `uv sync` uses the committed `uv.lock` |
| Unbounded repo growth | ~11 small parquet files; rewritten only on change |
| Rate-limit ban of the runner IP | 16 req/night, 6 s spacing |

## 7. Plan-text conflicts and user decisions

**Conflicts** (for UPDATE PROCESS, not applied here):
1. `write_chain_growth_point` (per point, append-only) → `merge_onchain_series` (full series,
   revision window). The path is `onchain/{source}/{chain}/{metric}`, not `chain_growth/…`.
2. `backfill_chain_growth.py` is dropped (§2).
3. `DUNE_API_KEY` env mapping is removed; P5 wording becomes "new `contents: write` workflow" (already
   listed in RFC-2 Stage 0 §8 item 7).
4. AC-9: redistributable comes from the adapter constant, not a per-row column.
5. AC-7: "a failed chain writes `status=unavailable`" becomes "a failed chain writes nothing". RFC-4
   derives unavailable/stale from absence or age. This is consistent with RFC-2 Stage 0 §7.

**User decision needed:** only the go-ahead. Optional: confirm a 14-day revision window (a
technical default; I will use 14 unless you know growthepie revises further back).

## Closeout
- Classification: **Keep in active/testing**. Stage 0 has been presented; RFC-3 code has not started.
- Follow-up stubs created: none. CONTEXT_PARTIAL: none. Deviations: the §7 items above (proposed, not applied).

## Forward Preview
### Test Infra Found
- `isolated_cache` (monkeypatches `cache.CACHE_ROOT`) and the snapshot_narrative dry-run pattern.
### Blast Radius Changes
- `cache.py` (additive), `.gitignore` (+1 negation), 1 new workflow, 1 new script and 2 new test files. There is no backfill script.
### Commands to Stay Green
- `uv run --project api pytest api/ -q` → 445 passed / 5 deselected (no code touched).
### Dependency Changes
- None.
