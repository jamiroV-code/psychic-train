---
slug: pair-screener
date: 2026-09-25
verdict: VIABLE
originating-phase: pvl
---

# Feasibility Verdict: ccxt Hyperliquid deep OHLCV backfill without touching `ccxt_adapter.py`

## Hypothesis

Does ccxt's Hyperliquid `fetch_ohlcv(symbol, '1d', since=None, limit=5000)` return the
earliest-available (deep) history for a coin, or only the most-recent N candles ending at
"now" — and can a deep backfill be achieved for coins that already have a shallow ~501-bar
cache without modifying `api/data/ccxt_adapter.py` (marked read-only by the plan)?

## Mechanism Under Test

`ccxt.hyperliquid.fetch_ohlcv`'s `since`/`limit` → Hyperliquid `candleSnapshot`
`startTime`/`endTime` mapping, ccxt's client-side `filter_by_since_limit` post-filter, and
whether `api/data/ccxt_adapter.py::fetch_ohlcv`'s existing public signature already exposes
enough control to drive a deep fetch from a new script.

## Probe Family

1 — Local process / Node (here: Python) script — installed-library source inspection plus
local offline reasoning. No network call made.

## Probe Cost Class

`cheap-local`. Gate met (no container, no live provider, no browser needed). No live
Hyperliquid/exchange call was made, per the task constraint.

## Probe Method

```
cd api && uv run python -c "import ccxt; print(ccxt.__version__)"
uv run python -c "import ccxt, inspect; print(inspect.getsource(ccxt.hyperliquid.fetch_ohlcv))"
uv run python -c "import ccxt; ex = ccxt.hyperliquid(); d = ex.describe(); # search dict for candle/ohlcv keys"
uv run python -c "import ccxt, inspect; print(inspect.getsource(ccxt.Exchange.filter_by_since_limit))"
uv run python -c "import ccxt, inspect; print(inspect.getsource(ccxt.hyperliquid.parse_ohlcvs))" (falls back to base)
```
Plus direct reads of `api/data/ccxt_adapter.py` (full file) and `api/data/cache.py` (`read_ohlcv`/`write_ohlcv`), and a grep of `api/data/hyperliquid_narrative_adapter.py` for its `_exchange()` usage.

## Evidence Captured

- ccxt version installed: `4.5.78`.
- `describe()` confirms `features/default/fetchOHLCV = {'limit': 5000}` and
  `api/public/post/info/byType/candleSnapshot = 4` (rate-weight, not a size cap) — this is
  the documented basis for the adapter's own comment "Hyperliquid's underlying API allows up
  to 5000 candles."
- `ccxt.hyperliquid.fetch_ohlcv` source:
  - `useTail = since is None`; `originalSince = since`.
  - **If `since is None` and `limit` is given:** `since` is computed as
    `until - timeframe_ms * limit` (i.e. "the most recent `limit` bars ending now"). This is
    the shallow/warm-path behavior — NOT deep history when `since` is left `None`.
  - **If `since` is explicitly given** (any timestamp, including `0`): that value is sent
    verbatim as `startTime` in the `candleSnapshot` request, with `endTime = now`
    (`until`), and `originalSince` is preserved for the post-filter.
  - Request body: `{"type": "candleSnapshot", "req": {"coin": ..., "interval": ...,
    "startTime": since, "endTime": until}}` — a single request, no internal
    pagination/chunking loop in ccxt's implementation.
  - Response is parsed then passed through `parse_ohlcvs` → `filter_by_since_limit(sorted,
    since, limit, 0, tail=useTail)`.
- `Exchange.filter_by_since_limit` source: when `since` is explicitly defined, results are
  first filtered to `timestamp >= since`, then (since `tail=False` in this call path)
  `shouldFilterFromStart = True` → `filter_by_limit` keeps the **first** `limit` entries of
  the ascending-sorted array (oldest-first), i.e. a genuine forward window starting at
  `since` — not a "most recent N" truncation.
- Hyperliquid perpetuals only exist since the exchange's 2023 launch (well under
  5000 days ≈ 13.7y). So a single call with `since <= listing_date` (or `since=0`) and
  `limit=5000` requests a window wide enough to cover any currently-listed coin's entire
  history in one request — no pagination loop is structurally required for present-day
  Hyperliquid assets, though defensive pagination costs nothing to add.
- `api/data/ccxt_adapter.py::fetch_ohlcv(symbol, timeframe, since=None, limit=None,
  exchange=None)` (lines 312-393) is a PUBLIC function whose `since`/`limit` parameters flow
  straight through, unmodified, to the underlying ccxt call:
  - `effective_since = since` when the caller passes `since` explicitly (only overridden to
    "last cached bar" when the caller passes `since=None` and the cache is non-empty — line
    373-374).
  - The `_cache_is_fresh` warm-path skip (line 354) only fires `if since is None and
    _cache_is_fresh(...)` — passing a non-`None` `since` bypasses it unconditionally, forcing
    a live fetch even when a shallow cache already exists.
  - `merged = pd.concat([cached, fetched])` (line 391) then `cache.write_ohlcv(symbol,
    timeframe, merged)` — no adapter-internal dedup needed at this step.
- `api/data/cache.py::write_ohlcv` (lines 100-106): `df.sort_values("timestamp")
  .drop_duplicates(subset="timestamp", keep="last")` before writing — confirms merging a
  deep-fetch result into an existing shallow cache via the adapter's own public path is safe
  and dedupes correctly with no separate merge logic required in a new script.
- `api/data/hyperliquid_narrative_adapter.py` line 104: `ex = ccxt_adapter._exchange() if
  exchange is None else exchange` — it shares `ccxt_adapter`'s process-wide singleton/RLock
  directly (imports `ccxt_adapter`, calls its private `_exchange()`). A new backfill script
  calling the adapter's own public `fetch_ohlcv` reuses the same lock discipline and does not
  need to construct a separate exchange instance or touch this file.

## Verdict

**VIABLE.**

Realistic max depth per call: up to 5000 daily candles (~13.7 years), bounded in practice by
each coin's actual Hyperliquid listing date (exchange launched 2023, so every real coin's full
history fits in a single 5000-limit call today).

## Resulting Design Constraint

**What this licenses:** RFC-001's backfill script may call the EXISTING public function
`ccxt_adapter.fetch_ohlcv(symbol, "1d", since=<epoch-0-or-a-date-before-2023>, limit=5000,
exchange=None)` directly from a new script (e.g. `api/scripts/backfill_hyperliquid_history.py`)
with **zero changes to `api/data/ccxt_adapter.py`**. Passing an explicit `since` (not `None`)
is what forces the deep window and bypasses both the warm-cache skip and the "most-recent-N"
default; the returned frame merges safely into an existing shallow ~501-bar cache via the
adapter's own `pd.concat` + `cache.write_ohlcv` merge/dedupe path already in `fetch_ohlcv`. The
script may reuse `ccxt_adapter._exchange()` (same singleton/lock the narrative adapter already
shares) or, if run as a standalone one-off process, construct its own `ccxt.hyperliquid()` —
either is safe.

**What this forbids:** The backfill script must NOT call `fetch_ohlcv(symbol, "1d")` with
`since=None` and rely on `limit=5000` alone to reach deep history — when `since` is `None`,
ccxt computes `since` itself as "now minus `limit` bars" only when it is also the very first
call with an empty cache path in this adapter (`effective_since` is overridden to the *last
cached timestamp* whenever the cache is already non-empty, at adapter line 373-374); against
an ALREADY-shallow ~501-bar cache this produces an incremental top-up forward from the last
cached bar, not a backward deep fetch. The design must not assume ccxt or Hyperliquid silently
returns full history "by default" — the explicit `since` argument is mandatory.

**What remains uncertain (known-gap):** This probe is cheap-local/offline only — no live
Hyperliquid call was made, per the task's network-ban constraint, so the following are
inferred from source, not empirically confirmed: (1) whether Hyperliquid's `candleSnapshot`
endpoint itself silently caps a response below the requested window/5000 limit for very old
`startTime` values (ccxt applies no internal pagination/retry-until-exhausted loop for this
endpoint, so if the server truncates silently, the script would need to detect a
result count of exactly the server cap and page forward using the last returned timestamp);
(2) the actual per-coin Hyperliquid listing dates for the plan's target watchlist coins,
which determines whether any of them are young enough that "since=0, limit=5000" returns
fewer bars than the coin's real full history (should not happen given all Hyperliquid perps
postdate 2023, but unconfirmed empirically); (3) rate-limit/backoff behavior for a bulk
multi-symbol backfill loop — recommend the script call the adapter's public `fetch_ohlcv`
(which already wraps `_fetch_with_backoff`'s retry/backoff) per symbol rather than
constructing raw ccxt calls, so this is inherited rather than re-implemented, but a
multi-coin loop's aggregate rate-limit exposure was not probed live. RFC-001 should treat
(1)-(2) as items for its own AC checklist (e.g. an AC that logs bar-count-per-coin from the
real backfill run and flags any coin returning exactly 5000 bars for manual pagination
follow-up), rather than assuming this VERDICT closes them.

VC-FEASIBILITY-VERDICT-READY: VIABLE — process/features/cointegration-screener/active/pair-screener_25-09-26/pair-screener_FEASIBILITY_25-09-26.md
