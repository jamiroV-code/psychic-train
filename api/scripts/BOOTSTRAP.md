# Bootstrap: populating a fresh checkout's data cache

TL;DR: run the five commands in section 3, in order, once. Roughly 10-15
minutes (estimated), almost all of it network wait. Nothing in the data cache
is committed to git, so a fresh checkout always starts empty — this is the
documented route back to a working `/screener`, `/pairs` and `/regime`.

This file covers data only. It does not describe how to start the API or the
web app.

## 1. Purpose — what "populated" means

| Page | Needs | Populated when |
|---|---|---|
| `/screener` | `api/data/watchlist.json` + OHLCV bars for every watchlist coin across all five timeframes | `bootstrap_watchlist` then `refresh_cache` have run |
| `/pairs` | daily OHLCV for all 18 pairs-universe coins + the precomputed results cache | `refresh_cache` (or the deep backfill) then `compute_pairs` have run |
| `/regime` | the 5 primary FRED liquidity series | `backfill_primaries` has run |

Until then the pages render honest "unavailable" / "insufficient" states
rather than wrong numbers — nothing crashes, but nothing is useful either.

## 2. Prerequisites

- `uv sync --project api` (installs the `api/` environment).
- Outbound network access to Hyperliquid (via `ccxt`) and
  `fred.stlouisfed.org`. Both are **keyless** — no secrets, no `.env` entries
  are needed for any command below.
- Run every command from the repository root.

## 3. Ordered command sequence

Order matters: `compute_pairs` only ever READS the OHLCV cache, so it must run
**after** whichever command last wrote bars.

```bash
# 1. Create api/data/watchlist.json from the checked-in example (idempotent;
#    never overwrites an existing watchlist).
uv run --project api python -m api.scripts.bootstrap_watchlist

# 2. Refresh OHLCV: watchlist coins + BTC/HYPE on all five timeframes, plus
#    every pairs-universe coin on 1d.
uv run --project api python -m api.scripts.refresh_cache

# 3. Refresh the 5 primary FRED liquidity series (/regime inputs).
uv run --project api python -m api.scripts.backfill_primaries

# 4. ONE-TIME, MANUAL: deep daily history for the 18 pairs-universe coins.
#    Not scheduled, not idempotent-cheap — see section 6 (Depth).
uv run --project api python api/scripts/backfill_pairs_universe.py

# 5. Precompute the pair statistics. Run this LAST, and again after any
#    later refresh_cache run (see section 10).
uv run --project api python -m api.scripts.compute_pairs
```

Exit codes for steps 2, 3 and 5: `0` = at least one item succeeded; `2` = the
script ran but nothing succeeded (degraded, worth investigating); `1` (or any
other code) = a crash.

## 4. What each step populates

| Directory / file | Filled by | Scheduled or manual |
|---|---|---|
| `api/data/watchlist.json` | `bootstrap_watchlist` | manual one-time (then hand-edited via `/screener`) |
| `api/data/cache/ohlcv/` | `refresh_cache`, and deep-seeded by `backfill_pairs_universe` | both — nightly via `pairs-refresh-snapshot.yml`, plus the manual one-time deep seed |
| `api/data/cache/liquidity/` | `backfill_primaries` | both — nightly via `liquidity-backfill-snapshot.yml`, plus manual |
| `api/data/cache/pairs/` | `compute_pairs` | both — nightly (second step of `pairs-refresh-snapshot.yml`), plus manual |

## 5. Expected wall-clock per step

Every figure below is **estimated**, not measured on your machine.

| Step | Estimated duration |
|---|---|
| `bootstrap_watchlist` | estimated under 1 second |
| `refresh_cache` (~22 symbols x 4 fetched timeframes, plus derived weekly; ccxt-rate-limited) | estimated several minutes |
| `backfill_primaries` (5 FRED CSV downloads) | estimated under 1 minute |
| `backfill_pairs_universe` (18 sequential deep fetches) | estimated a few minutes |
| `compute_pairs` (153 pairs) | ~56 s (recorded from a real run; estimated to vary with machine) |
| **Total** | **estimated 10-15 minutes**, dominated by network wait |

## 6. Depth — nightly refresh is shallow, the deep history is manual

`refresh_cache` fetches at most `DEFAULT_LIMIT = 500` daily bars per coin. The
real pair-screener quality history is ~2,230 daily bars, reaching back to
Hyperliquid's apparent daily-history floor around 2020-08-19, and it comes
**only** from the one-time `backfill_pairs_universe.py` deep fetch
(`DEEP_LOOKBACK_LIMIT = 5000`). `fetch_ohlcv` merges into the cached tail, so
a deep-backfilled file keeps its history through every later nightly refresh.

Consequence: a pairs result computed on an ephemeral CI runner (which has no
deep history) is a **canary artifact, not a quality result** — at most 500
bars per coin. Judge pair statistics only against a locally deep-backfilled
cache.

Adding a coin to `api/data/pairs_universe.json` (hand-edited) also requires
running the deep backfill for that coin; otherwise its history stays shallow.

## 7. Cache strategy (D1) — nothing here is committed

`api/data/cache/ohlcv/`, `api/data/cache/liquidity/`, `api/data/cache/pairs/`
and `api/data/watchlist.json` are gitignored on purpose. Committing them was
estimated to add **~1.5-3.3 GB/year** to the repository (estimated:
~365 MB-1.1 GB/yr for OHLCV, ~1.1-2.2 GB/yr for pair spreads, ~36 MB/yr for
liquidity), because those files are fully overwritten on every run and so diff
every night. That is one to two orders of magnitude beyond the committed
archives that do exist (liqtide, narrative, on-chain — together well under
1 MB, and byte-identical on quiet nights).

The archives that ARE committed exist because their upstream data disappears.
ccxt and FRED are themselves the durable primary source, so re-fetching is the
recovery path — which is what this runbook is. Estimated full recovery time
from an empty checkout: see section 5 (estimated 10-15 minutes).

## 8. What the two new nightly workflows do today

`pairs-refresh-snapshot.yml` (19:17 UTC) and `liquidity-backfill-snapshot.yml`
(19:47 UTC) run the same scripts on a schedule. **Their commit steps are inert
today**: the runner is ephemeral and the owned directories are gitignored, so
nothing persists between runs and the commit step always reports "nothing new
to commit".

What they genuinely buy now is a nightly integration canary: a crash (any exit
code other than 0 or 2) fails the job loudly, which is real value given this
project's history of silent provider breakage. A total provider outage
(exit 2) raises a warning annotation only and does not fail the job.

Once a persistent disk exists, the schedule and safety shape become fully
functional with **zero rewrite** — either the host's own disk carries the
cache, or the paths are un-ignored and the same staging lines start committing
real changes.

## 9. Known limits

- Live fetches and real cron firing are **unverified** as of writing: the
  development container's egress proxy blocks ccxt/Hyperliquid and FRED, and a
  scheduled run cannot be observed before merge. The first scheduled or
  `workflow_dispatch` run after merge is the proof.
- No documented rate-limit ceiling exists for bulk Hyperliquid fetches. 18
  sequential deep fetches succeeded with no throttling in a prior real run;
  beyond that, behaviour is unknown.
- If `uv run` itself fails with exit code 2, the workflow reads it as
  "degraded" rather than a crash. Accepted known gap.
- Because commits are inert, `git log` on the cache directories shows nothing
  even when the workflows run fine. The observable is the Actions run history.

## 10. Staleness: always run `compute_pairs` after `refresh_cache`

`/pairs` provenance compares per-coin bar counts against the OHLCV cache. Any
`refresh_cache` run changes those counts, so **`/pairs` reads `stale` until
`compute_pairs` runs**. This is honest reporting, not a bug — but it means the
two commands belong together, which is exactly why the nightly workflow runs
them as two steps of one job.
