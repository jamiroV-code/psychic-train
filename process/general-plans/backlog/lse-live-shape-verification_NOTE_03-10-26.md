# Backlog: LSE live shape verification (S3 Known-Gap, AC-S3-5)

**Status:** open. Blocks only live use of `api/data/lse_adapter.py`; the S3 gate stays
CONDITIONAL (no vacuous green) until this closes.

## Why

The adapter was coded offline against the documented row shape
(`{symbol, open, high, low, close, volume, timestamp ISO}`, at most 5000 rows per request,
`lse-data-verification_17-09-26/findings.md:18`). This container cannot reach the LSE host, so
these are ASSUMED and isolated as constants in `lse_adapter.py`:

- `BASE_URL`, `CANDLES_PATH` and the query parameter names (`symbol`, `timeframe`, `start`,
  `limit`, `order`);
- header auth: `Authorization: Bearer <key>` (the probe also tries `X-API-Key`);
- the response wrapper (bare list, or a list under `data`/`candles`/`rows`/`results`);
- the bar-timestamp convention: bars are keyed by the UTC calendar date of `timestamp`;
- whether `timeframe="1w"` is served (the adapter derives weekly from daily either way, D9);
- an unknown ticker answers 404 (verified for delisted SIVB/FRC on 24-09-26).

## To close (P-S3-1, user PC)

1. Follow `process/general-plans/active/screener-batch1_03-10-26/s3-probe/README.md`: run
   `lse_probe.py` once with `LSE_API_KEY` set for the shell session only.
2. Check, then copy the sanitised `s3-probe/out/lse_candles_probe_shape.json` to
   `api/tests/data/fixtures/lse_candles_probe_shape.json` (symbol `TEST`, synthetic prices).
3. G-S3-6: `UV_FROZEN=1 uv run --project api pytest api/tests/data/test_lse_adapter.py -q -k probe_fixture_parses -rs`
   must report 1 passed; `test_committed_lse_fixtures_are_synthetic_only` must still pass.
4. If the probe reports a different auth scheme, path or wrapper, correct the constants in
   `lse_adapter.py` (and the header-auth test) in a follow-up task.

Never commit the raw probe output (`api/data/cache/equities/_probe/`, git-ignored) or any real
LSE price: the repo is public and LSE prohibits redistribution.
