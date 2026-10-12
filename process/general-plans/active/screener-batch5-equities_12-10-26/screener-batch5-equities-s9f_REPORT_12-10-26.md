# T49 / S9F report: LSE adapter matches the live service

## 1. Task ID
T49 (batch 5, slice S9F), branch `claude/t49-lse-live-shape`.

## 2. Outcome
DONE. All gates green; counts match the envelope exactly.

## 3. Summary
- `BASE_URL = https://api.londonstrategicedge.com/vault`, `CANDLES_PATH = /candles`, `AUTH_HEADER = x-api-key` carrying the bare key (no Bearer). "ASSUMED" labels removed; module docstring describes the live shape.
- `extract_rows` renames the live `ts` key to `timestamp` (rows that already have `timestamp` are unchanged), so `parse_candles` reads `"YYYY-MM-DD 00:00:00.000000"` as that UTC calendar date.
- httpx, timeouts, the 5000 cap, caching, status mapping and closed Reason strings are unchanged; 400 stays `unavailable/http-error`; the key is never logged.

## 4. Files
- `api/data/lse_adapter.py` (constants, docstring, `extract_rows` + `_rename_ts`, header value)
- `api/tests/data/test_lse_adapter.py` (one line: header assertion `== SENTINEL`)
- `api/tests/data/test_lse_live_shape.py` (new, 4 plain-function tests)
- `api/tests/data/fixtures/lse_candles_probe_shape.json` (new, symbol TEST, `ts` strings, synthetic prices ~20-21, int and float opens)

## 5. Commits
- `e3177e8` fix(lse): match the live LSE vault service shape (T49)
- report commit (this file)

## 6. Tests run (SHA e3177e8, 2026-10-12 ~09:35 UTC)
- Red run on base code: 3 failed / 17 passed (test_probe_fixture_parses, live-shape parse, vault/x-api-key request). Tests (c) 404 and (d) bare 400 already passed on base because that mapping already existed.
- G1 `UV_FROZEN=1 uv run --project api pytest api/tests/data/test_lse_adapter.py api/tests/data/test_lse_live_shape.py -q`: 20 passed.
- G2 `UV_FROZEN=1 uv run --project api pytest api/ -q`: 1110 passed, 1 skipped, 5 deselected (baseline 1105/2/5).
- G3: web/ untouched (no web/ path in the diff).
- Scans vs origin/main...HEAD: `git diff --check` clean; no CLAUDE.md, AGENTS.md, README.md, .claude/, .github/, deploy/, uv.lock, api/pyproject.toml, web/ paths; no key-looking literal (only the existing test SENTINEL), no real prices.

## 7. Tests NOT run
No live call to the LSE service (no key in this container, and the brief forbids it). Web suite not run (untouched).

## 8. Deviations
None. Note: new tests (c) and (d) are regression locks; they were green before the change.

## 9. Blockers
None.

## 10. Follow-up
- `_request_daily` does not send `end` or `dataset`; not needed for the current daily fetch.
- Desc order puts today's forming bar first; the adapter requests `order=asc`, so a forming bar for today may be the last row. Unchanged behaviour; the planner may want to decide whether to drop an intraday-forming bar.

## 11. Context cost
Loaded: CLAUDE.md, the envelope, the adapter and its test file. No on-demand docs opened. Spend well under 3 USD.
