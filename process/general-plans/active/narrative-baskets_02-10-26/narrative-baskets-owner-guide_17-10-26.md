# Narrative Baskets: owner guide for the first live refresh

Plain steps for your own PC. Nothing here needs a paid key except X, which stays off until you choose.
Run every command from the repo folder (the one holding `api/`).

## 1. Set up (once)

Windows PowerShell:
```
git pull
uv sync --project api
```
macOS / Linux:
```
git pull
uv sync --project api
```

## 2. First live refresh

Default sources (Wikipedia, CoinGecko, top-100 universe):
```
uv run --project api python api/scripts/refresh_attention.py
```
Then the category snapshot for Discovery:
```
uv run --project api python api/scripts/refresh_attention.py --sources categories
```
Same command on Windows and macOS/Linux. Add `--dry-run` first to see the plan without any call.
Each line prints `source: n/m ok, k rows written`. Wait a minute between runs if CoinGecko answers slowly.

## 3. Record what you saw

This reads the local store only and fetches nothing.
```
uv run --project api python api/scripts/record_probe.py --dry-run
uv run --project api python api/scripts/record_probe.py
```
It writes `api/data/attention/probe_records.json`. A source with no record counts as not-probed and feeds no score.
If a source failed on your PC, record it by hand, for example:
```
uv run --project api python api/scripts/record_probe.py --sources wikipedia --state reddit=unavailable
```
`--state SOURCE=STATE` also takes `capped`, `no-article`; `not-probed` removes a record.

## 4. Look at the site

1. Start the app the usual way and open it in your browser.
2. Open the My baskets tab: each basket should show a score, or a clear reason it has none.
3. Open the Discovery tab: categories should list with moving scores.
4. A tab saying "no data" or "insufficient history" is expected early: scores need 90 completed days.

## 5. What each state means

- ok: at least one coin has 90+ completed UTC days; the source feeds scores.
- insufficient-history: data exists but under 90 days; shown, not scored.
- unavailable: nothing stored or the provider failed; feeds no score.
- no-article: the coin has no Wikipedia page mapped.
- capped: a spend or read cap stopped the run.
- not-probed: no record yet; feeds no score.

## 6. X (optional, last)

X stays `insufficient-history` until it has 90 days of your own data, and is off by default.
Put the key ONLY in a private environment variable for the current terminal. Never in a file, never in chat.

Windows PowerShell:
```
$env:X_BEARER_TOKEN = Read-Host "X token"
$env:X_LIVE = "1"
```
macOS / Linux:
```
read -s X_BEARER_TOKEN; export X_BEARER_TOKEN; export X_LIVE=1
```
Check the plan first (no call): `uv run --project api python api/scripts/refresh_attention.py --sources xsearch` with `X_LIVE` unset prints reads and USD planned.
Caps (defaults): 10 reads per run (`X_MAX_READS_PER_RUN`), 50 per day (`X_MAX_READS_PER_DAY`), 1.00 USD per day (`X_MAX_USD_PER_DAY`), 0.01 USD per read (`X_USD_PER_READ`). Lower them the same way before a first real run.
Close the terminal when done; the variables disappear.

## 7. What to send back to the planner

Only the printed summary lines from steps 2 and 3 (for example `wikipedia: ok (40/47 coins ...)`) and one sentence on how the two tabs looked.
Never send keys, tokens, the environment, or the contents of any file with a secret.
