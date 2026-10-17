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

## 6b. Reddit and the rest in the daily run

The daily GitHub run has a second job, "refresh-extra". It adds Binance and
Hyperliquid volume, Google Trends and Reddit after the main job.

Reddit needs two repository secrets (exact names):
`REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET`.
1. Open reddit.com/prefs/apps, click "create another app".
2. Pick type "script", any name, redirect uri `http://localhost`.
3. Copy the client id (under the app name) and the secret.
4. GitHub repo: Settings -> Secrets and variables -> Actions ->
   New repository secret. Add both names with those values.
Without both secrets the Reddit step is skipped ("reddit: not-probed
no credentials").

Yellow warnings: a source says "unavailable" with a reason (HTTP 451, 403,
429). The provider blocked the GitHub server; nothing is faked or recorded,
and the job stays green. A red job means a real code error: send the log.

Binance usually stays unavailable (451) from GitHub. Then run the same
refresh on your PC (section 2 style):
`uv run --project api python api/scripts/refresh_attention.py --sources exchange_volume`
then `uv run --project api python api/scripts/record_probe.py --sources exchange_volume`.

## 7. What to send back to the planner

Only the printed summary lines from steps 2 and 3 (for example `wikipedia: ok (40/47 coins ...)`) and one sentence on how the two tabs looked.
Never send keys, tokens, the environment, or the contents of any file with a secret.
