# S3 Step 0: London Strategic Edge shape probe (P-S3-1)

Run once on your own PC (this container's proxy blocks the LSE host). It checks what the
offline adapter (`api/data/lse_adapter.py`) only assumes: the auth header scheme, the candles
row shape and timestamp convention, whether weekly bars are served, how an unknown ticker
answers, and the `/vault/usage` shape.

## Needs

Python 3.10+ and `httpx` only (`pip install httpx`, or run it inside the `api` uv env).

## Run

From the repo root, with the key set for this shell session only (never in a file, never on
the command line of a saved script):

```bash
# bash/zsh: read the key without echoing it, export it for this shell only
read -rs LSE_API_KEY && export LSE_API_KEY
python process/general-plans/active/screener-batch1_03-10-26/s3-probe/lse_probe.py
unset LSE_API_KEY
```

PowerShell: assign the output of `Read-Host -MaskInput` to the `LSE_API_KEY` entry of `$env:`,
run the script, then remove that entry with `Remove-Item Env:` and the same name.

If every request fails with a connection error or 404, the host or path guess is wrong: set
`LSE_BASE_URL` (for example to the host the `lse-data` SDK uses) and run again.

## What it does

- AAPL daily, last 60 days: tries `Authorization: Bearer` then `X-API-Key`, on two ASSUMED
  candles paths, and stops at the first 200.
- AAPL `timeframe="1w"` (if not 200, the adapter derives weekly from daily, D9).
- A bad ticker (expect 404, mapped to `bad_symbol`).
- `GET /vault/usage` (key names only).

The console shows only labels, the header scheme name, HTTP status codes, key names and type
names. It never prints the key, a header, a URL, a response body or a price.

## Output

- Raw responses: `api/data/cache/equities/_probe/*.json` (git-ignored, stays on your PC, never
  commit or share them; LSE prohibits redistribution).
- Sanitised fixture: `s3-probe/out/lse_candles_probe_shape.json`. Symbol `TEST`, prices and
  volumes from a seeded synthetic walk; it keeps only the real response's keys, value types,
  wrapper layout and timestamp strings (calendar positions, which carry the bar-timestamp
  convention under test). Open it and check before copying.

## Then

```bash
cp process/general-plans/active/screener-batch1_03-10-26/s3-probe/out/lse_candles_probe_shape.json \
   api/tests/data/fixtures/lse_candles_probe_shape.json
UV_FROZEN=1 uv run --project api pytest api/tests/data/test_lse_adapter.py -q -k probe_fixture_parses -rs
```

Expect `1 passed` (gate G-S3-6). Report the console output (it is safe to paste) so the
adapter's assumed constants (base URL, path, auth header) can be confirmed or corrected.
