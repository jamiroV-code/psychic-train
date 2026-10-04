# T33 (batch 1, slice S3) completion report

## 1 Task ID

T33, batch 1 slice S3: LSE equities adapter and ticker store, probe-first. Branch
`claude/t33-s3-lse-adapter` from `main` 8c235b7.

## 2 Outcome

partial: everything codeable offline is done and green; the S3 gate is CONDITIONAL (no
vacuous green) until G-S3-6 (`test_probe_fixture_parses`) passes on the user's PC with the
sanitised probe fixture. Stopping at `review`.

## 3 Summary

- `s3-probe/lse_probe.py` + README committed first (caa802a): key from the environment only,
  header auth (tries `Authorization: Bearer`, then `X-API-Key`), explicit 15 s timeout, prints
  only labels, scheme names, status codes, key and type names; raw output to the git-ignored
  `api/data/cache/equities/_probe/`; writes a sanitised fixture (symbol TEST, seeded synthetic prices).
- `api/data/lse_adapter.py`: `fetch_equity_ohlcv(symbol, timeframe, transport=None, now=None)`
  -> `EquityOhlcvResult` (`ok|unavailable|stale|bad_symbol`, closed-enum `reason`,
  `redistributable=False`, `source="lse"`, four caveats). `1d`/`1w` only; 1w via
  `ccxt_adapter._derive_weekly_from_daily`; explicit NYSE rule-set calendar (D11); cache at
  `CACHE_ROOT/equities/<SYM>/{1d,1w}.parquet` via `cache._atomic_to_parquet` with footer attrs
  `mysite.redistributable=false`, B1-style `fetched_at` sidecar, 6 h TTL. Never raises, never logs.
- `api/data/equities_store.py`: `{"tickers": [...]}`, `SCREENER_EQUITIES_PATH` at call time,
  atomic temp+rename, idempotent add, ticker regex, no cap, `TickerNotFoundError`.
- 16 adapter tests + 13 store test items; `.gitignore` gains `api/data/equities.json`.

## 4 Files changed

- `process/general-plans/active/screener-batch1_03-10-26/s3-probe/lse_probe.py` (new)
- `process/general-plans/active/screener-batch1_03-10-26/s3-probe/README.md` (new)
- `api/data/lse_adapter.py`, `api/data/equities_store.py` (new)
- `api/tests/data/test_lse_adapter.py`, `api/tests/data/test_equities_store.py` (new)
- `api/tests/data/fixtures/lse_candles_synthetic.json` (new; 111 synthetic SYNTH rows, seeded walk)
- `.gitignore` (one added line: `api/data/equities.json`)
- `process/general-plans/backlog/lse-live-shape-verification_NOTE_03-10-26.md` (new)
- this report

No file outside Owned; `cache.py`, `ccxt_adapter.py`, `pyproject.toml`, `uv.lock`, `deploy/**`,
`api/scripts/**` untouched.

## 5 Commits

Branch `claude/t33-s3-lse-adapter`:

- caa802a s3-probe: LSE shape probe and README (T33 step 0)
- f529a40 T33 S3: LSE equities adapter, ticker store and tests
- (this report, next commit)

## 6 Tests run

All gate runs at f529a40 (code); the report commit after it changes no code.

| Gate | Command | Result | UTC |
|---|---|---|---|
| red | `UV_FROZEN=1 uv run --project api pytest api/tests/data/test_lse_adapter.py api/tests/data/test_equities_store.py -q` at 8c235b7 | ERROR: file not found (modules and tests absent) | 2026-10-04 ~01:05 |
| G-S3-1 | `UV_FROZEN=1 uv run --project api pytest api/tests/data/test_lse_adapter.py api/tests/data/test_equities_store.py -q -rs` | 28 passed, 1 skipped (`test_probe_fixture_parses`); collect: adapter 16, store 13 | 01:31 |
| G-S3-2 | `UV_FROZEN=1 uv run --project api pytest api/ -q -rs` (once) | 898 passed, 2 skipped (baseline `test_lane_scope` + probe skip), 5 deselected, 1 xfailed (S1 not merged), 0 failed | 01:31-01:35 |
| G-S3-3 | `git diff --check` and `git diff --check origin/main...HEAD` | exit 0 | 01:31 |
| G-S3-4 | S3-scope / FORBIDDEN / FIXTURES-MDR / S3-gitignore | nothing / nothing / nothing / exactly `+api/data/equities.json` | 01:31 |
| G-S3-5 | S3-key-grep | first: only `os.environ.get("LSE_API_KEY")` (probe :141, adapter :341); second: nothing. Every `print(` in the probe is in `_say(label, status)`; its call sites pass fixed labels, scheme names, status codes, row/usage key names, type names, a row count and the timestamp time-of-day suffix, never the key, headers, a URL or a body (hybrid review: tester to confirm) | 01:31 |
| G-S3-6 | probe-fixture test on the real shape file | NOT RUN (user PC; see heading 7) | - |
| G-S3-7 | `git check-ignore api/data/equities.json api/data/cache/equities/AAPL/1d.parquet api/data/cache/equities/_probe/x.json` | all three paths, exit 0 | 01:31 |
| G-S3-8 | S3-fixtures | `lse_candles_synthetic.json` and `s3-probe/lse_probe.py` only (README does not match the pattern); no raw probe output | 01:31 |
| G-S3-9 | S3-secret-scan | nothing | 01:31 |

Extra: the probe's `_sanitise` was exercised against a fabricated wrapped payload and its output
parsed through `lse_adapter.parse_candles` (scratch run, nothing committed).

## 7 Tests NOT run

- `test_probe_fixture_parses` (G-S3-6, AC-S3-5): skipped, `skipif` the fixture
  `api/tests/data/fixtures/lse_candles_probe_shape.json` is absent. It needs the user-PC probe
  (P-S3-1): this container cannot reach the LSE host. Known-Gap, recorded in the backlog note.
- Live fetching in general (auth scheme, base URL and path, wrapper, timestamp convention,
  `1w` support): same reason.
- Failing stubs: no `NotImplementedError` stubs were committed; the red run is the gate on the
  untouched base (test files absent).

## 8 Deviations

- The probe's sanitised fixture keeps the real responses' `timestamp` strings (calendar dates
  plus time-of-day, which carry the convention under test); every price and volume is
  synthetic, the symbol is TEST. Flagging in case the planner wants dates shifted too.
- The probe tries two ASSUMED candles paths (`/vault/candles`, `/candles`) and honours an
  optional `LSE_BASE_URL` override, since the REST host/path are unverified.
- Adapter additions inside its contract: a ticker failing `TICKER_RE` gives
  `bad_symbol`/`invalid-ticker` with no call (also keeps the cache path safe); a failed refresh
  with cached bars present returns those bars as `stale` (missing key stays `unavailable`); a
  fresh fetch newer than 6 days counts as current, older gives `stale`/`newest-bar-old`.
- Daily bars are normalised to 00:00 UTC of the timestamp's UTC date (ASSUMED convention).

## 9 Blockers

- Gate CONDITIONAL until G-S3-6 passes on the user's PC; backlog note
  `process/general-plans/backlog/lse-live-shape-verification_NOTE_03-10-26.md`
  (lse-live-shape-verification) holds the steps.
- Not self-merging: the CONDITIONAL gate and user-PC-only verification (master-planner.md §5.5)
  put this at `review`. Registry request: T33 -> `review` (PR from this branch).

## 10 Follow-up

- lse-live-shape-verification (backlog note above): run the probe, copy the fixture, run G-S3-6;
  correct `BASE_URL`/`CANDLES_PATH`/`AUTH_HEADER` in `lse_adapter.py` if the probe disagrees.
- S9 (later batch): equities page/router over `equities_store` and `fetch_equity_ohlcv`.

## 11 Context cost

Files loaded: CLAUDE.md; the envelope (+ saved REF copy); plan lines 36-45, 48-56, 73, 129-158,
277-286, 324-337, 353-362, 375-396; `all-data-sources.md` 219-252; `findings.md` 1-60.
Opened beyond the envelope (needed to code/report): `fred_adapter.py` 1-100, `cache.py`
(function index, 60-109), `ccxt_adapter.py` (imports, 268-300), `momentum.py` (`compute_rsi`
signature), `api/tests/conftest.py`, `watchlist.py` 1-60, `.gitignore`; a grep of
`lse-data-verification_17-09-26/verify_provider.py` for endpoint hints (no base URL found);
`master-planner.md` §5 and §9 (merge rule and this template). Approx. 60k tokens.
Tools: Bash, Read, Write, Edit, Grep, Glob, GitHub MCP; no subagents spawned.
