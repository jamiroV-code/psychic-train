# my_site on your own PC, over Tailscale only

**TL;DR** — The API and web app run on your Windows PC and listen only on its Tailscale
address (`100.x.y.z`). Your phone reaches them through the Tailscale app. Nothing listens on
your home network or the internet, nothing is paid for, and nothing public is created. The PC
does not have to be always on: after downtime, the API start pulls the latest code
automatically; recomputing caches stays a manual step for now.

Full plan (with the long version of every step): `process/general-plans/active/deployability_28-09-26/deployability_PLAN_29-09-26.md`.

```
+---------------------------------------------------------------------------------+
| HARD STOP — NEVER DO ANY OF THESE                                               |
|                                                                                 |
| - Do NOT use Tailscale Funnel (`tailscale funnel` / `serve --funnel`): it makes |
|   the app public on the internet. Never.                                        |
| - Do NOT add port forwarding on your router, dynamic DNS, a subnet router or an |
|   exit node for this app.                                                       |
| - Do NOT bind the API or web app to 0.0.0.0 (all interfaces).                   |
| - Do NOT move this to a cloud host or anything paid.                            |
|                                                                                 |
| If a step ever seems to need one of these, stop and ask first.                  |
+---------------------------------------------------------------------------------+
```

## What this is

| Piece | What it does |
|---|---|
| `config.example.psd1` | Example settings. Copy it to `%LOCALAPPDATA%\my_site\deploy.psd1` and edit the paths. Holds nothing private. |
| `_common.ps1` | Shared helpers: load the config, wait (bounded) for the Tailscale address, log to `%LOCALAPPDATA%\my_site\logs\`, stage A pull. |
| `start-api.ps1` | Waits for the Tailscale address, runs the stage A pull, sets `SCREENER_CORS_ORIGINS`, starts the API on `<tailscale-ip>:8000`. `-DryRun` prints what it would do. |
| `start-web.ps1` | Starts the built web app (`next start`, never the dev server) on `<tailscale-ip>:3000`. `-DryRun` available. Refuses a stale build, frees only the web port, smoke-checks the new server (see "Restarting safely"). |
| `build-web.ps1` | Builds the web app with `NEXT_PUBLIC_API_BASE_URL=http://<tailscale-ip>:8000` baked in. `-DryRun` available. Frees only the web port first, then writes the build marker after a successful build (see "Restarting safely"). |
| `register-tasks.ps1` | Creates Task Scheduler tasks `mysite-api` and `mysite-web` that start at your logon (no admin, no SYSTEM account). `-Remove` deletes them. |
| `start-collector.ps1` | Starts the attention collector (X and Reddit) as its own process, so API restarts never interrupt it. `-DryRun` available. Not registered by `register-tasks.ps1` (see "Collector (separate from the API)"). |

**These scripts were written in a container that has no PowerShell.** Automated tests only
check their text. Run the parse check (B5) and dry runs (B6) before anything else.

## What Tailscale does and does not protect

| Protects | Does not protect |
|---|---|
| Only devices signed into your Tailscale account can reach the app. | Anyone who gets into your Tailscale account reaches the app: turn on two-factor sign-in and device approval in the Tailscale admin console. |
| Traffic between your phone and PC is encrypted. | The app itself has no login. Anything on your tailnet can read it and edit the watchlist. |
| The app has no listener on your home network or the internet (it binds the Tailscale address only). | A future change that binds 0.0.0.0 would undo that — the scripts and tests forbid it (not allowed). |

## Setup (first time)

Run these in a normal (not admin) PowerShell in the repo root. `<ip>` is your Tailscale
address from B1. Condensed from the plan's Section B; report results back when done.

| Step | Do | Expect |
|---|---|---|
| B0 | `git pull --ff-only`; read the box above and the table above. | Pull ok. |
| B1 | Install Tailscale for Windows, sign in. `& "C:\Program Files\Tailscale\tailscale.exe" ip -4` | One address starting `100.` |
| B2 | Install the Tailscale phone app with the SAME account. `& "C:\Program Files\Tailscale\tailscale.exe" status` | PC and phone listed. |
| B3 | `(Get-ChildItem api\data\cache -Recurse -File \| Measure-Object Length -Sum).Sum / 1MB` | A size in MB (informational). |
| B4 | `New-Item -ItemType Directory -Force "$env:LOCALAPPDATA\my_site"; Copy-Item deploy\config.example.psd1 "$env:LOCALAPPDATA\my_site\deploy.psd1"`, then edit `RepoRoot`, `UvPath` (`where.exe uv`), `PnpmPath` (`where.exe pnpm`), `TailscaleExe`. Leave `CacheRoot`/`WatchlistPath` empty. | Absolute paths filled in. |
| B5 | `Get-ChildItem deploy\*.ps1 \| ForEach-Object { $e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile($_.FullName,[ref]$null,[ref]$e); "$($_.Name): $($e.Count) errors" }` | Every script: `0 errors`. Otherwise stop and send the output. |
| B6 | `powershell -NoProfile -ExecutionPolicy Bypass -File deploy\start-api.ps1 -DryRun` (and `start-web.ps1 -DryRun`) | Host is your `100.x.y.z`; `SCREENER_CORS_ORIGINS=http://<ip>:3000`. |
| B7 | `cd web; pnpm install --frozen-lockfile; cd ..; powershell -NoProfile -ExecutionPolicy Bypass -File deploy\build-web.ps1`, then `Select-String -Path "web\.next\static\*" -Pattern 'http://100\.' -Recurse -List` | Build ok; at least one file contains `http://<ip>:8000`. |
| B7b | Empty-cache probe on loopback with temp dirs (full commands in the plan). | Every endpoint 200; `/api/pairs` says `results_unavailable`. |
| B8 | Window 1: `start-api.ps1`; window 2: `start-web.ps1` (same `powershell ... -File` form). `Invoke-RestMethod "http://<ip>:8000/api/health"`; open `http://<ip>:3000/pairs`. | `status ok`; page loads. |
| B9 | Phone, Wi-Fi off, Tailscale on: `http://<ip>:3000/screener`. | Page and data load. On timeout, see "Firewall (only if B9 times out)". |
| B10 | `netstat -ano \| findstr ":8000 :3000"`; `Invoke-WebRequest "http://<PC LAN IP>:8000/api/health" -TimeoutSec 5`; phone with Tailscale off. | Only `<ip>:8000` / `<ip>:3000` listening, never 0.0.0.0; the LAN request and the Tailscale-off phone both fail. If not: stop, do not register tasks. |
| B11 | `powershell -NoProfile -ExecutionPolicy Bypass -File deploy\register-tasks.ps1`; `Get-ScheduledTask mysite-* \| Select TaskName,State` | Both tasks, state Ready. |
| B12 | Reboot, log on, wait 2 minutes, `Invoke-RestMethod "http://<ip>:8000/api/health"`; read `api.log`. | `status ok`; the log shows the stage A pull result. |
| B13 | Downtime drill: power off across a UTC midnight; see "After downtime" below. | Newer bot commit pulled; screens honest. |
| B14 | Watchlist persistence through the API (there is no add-coin button in the web app). This writes your REAL watchlist: `Invoke-RestMethod -Method Post -Uri "http://<ip>:8000/api/watchlist" -ContentType "application/json" -Body '{"symbol":"ZZTEST"}'`; `Stop-ScheduledTask mysite-api; Start-ScheduledTask mysite-api`; `Invoke-RestMethod "http://<ip>:8000/api/watchlist"`; clean up with `Invoke-RestMethod -Method Delete -Uri "http://<ip>:8000/api/watchlist/ZZTEST"`. | `ZZTEST` survives the restart; gone after cleanup. |
| B15 | Sleep 10 minutes, wake, reload from the phone. | Loads; if not, `Start-ScheduledTask mysite-api; Start-ScheduledTask mysite-web`. |

## Moving to a different PC (cache migration)

**TL;DR** — Clone the repo on the new Windows PC, install the prerequisites, copy five
gitignored cache paths off the old PC, then **recreate `deploy.psd1` and re-run
`deploy\build-web.ps1`** so the new machine's Tailscale address gets baked in. Never copy
`web\.next`, `.venv` or `node_modules`. Nothing is permanently lost if a copy is missed —
everything is regenerable — but a fresh deep price-history fetch may not reach as far back,
so copying is preferred.

Use this section when the app moves to a **different** machine than the one that first held
the caches. The ordinary first-time setup above assumes the repo and the caches already live
on the same PC; that assumption does not hold for a migration.

### Copy these (they are gitignored — a `git clone` does NOT bring them)

| Path | What it is | Needed by |
|---|---|---|
| `api\data\cache\ohlcv\` | Price bars, including the one-time deep history (~2,230 daily bars back to about 2020-08-19) | `/screener`, `/pairs` |
| `api\data\cache\liquidity\` | FRED macro series | `/regime` |
| `api\data\cache\pairs\` | Precomputed pair statistics + `provenance.json` | `/pairs` |
| `api\data\watchlist.json` | Your screener watchlist | `/screener`, `/api/watchlist` |
| `api\data\cache\narrative\coingecko_trending.parquet` | **Optional.** The one gitignored file in `narrative\`; reference-only (it is excluded from the narrative composite) | `/narrative` (reference column only) |

### Do NOT need copying — a `git clone` already brings them

`api\data\cache\liqtide\`, `api\data\cache\narrative\` (every file except the one named
above), `api\data\cache\onchain\`. These are git-tracked, so the clone on the new PC has
them already.

### Do NOT need copying — dead weight

`api\data\cache\legs\`. Nothing reads it, and the code that wrote it has been removed, so an
existing folder is leftover data. Skip it.

### MUST NOT be copied — rebuild these on the new PC instead

```
+---------------------------------------------------------------------------------+
| THE BIG MIGRATION TRAP — do NOT copy `web\.next`                                |
|                                                                                 |
| The web build has the OLD PC's Tailscale address baked into it, because          |
| NEXT_PUBLIC_API_BASE_URL is inlined by `next build` (it is not read at start-    |
| up). The new PC gets a DIFFERENT Tailscale address, so a copied `web\.next`      |
| would leave every page calling an address that is no longer the API.            |
|                                                                                 |
| You MUST re-run `deploy\build-web.ps1` on the new machine, and you MUST          |
| recreate `%LOCALAPPDATA%\my_site\deploy.psd1` with the new machine's absolute    |
| paths. Copying the old config file is not enough.                               |
+---------------------------------------------------------------------------------+
```

Also never copy: `.venv\` (recreate with `uv sync --project api`), `node_modules\`
(recreate with `pnpm install --frozen-lockfile`), any `__pycache__\`, and
`web\tsconfig.tsbuildinfo`. They are machine- and path-specific.

### Why a copied cache works at all (portability)

No persisted cache file stores an absolute path, so a copied cache works at any repo
location on any machine. `api\data\cache\pairs\provenance.json` holds only `computed_at`,
`universe`, `per_coin_last_bar_date`, `per_coin_bar_count`, `statsmodels_version` and
`eg_autolag` — no paths.

**The one data-level gotcha:** `/pairs` serves `computation_status: stale` (flagged, not
wrong) if the new machine's installed `statsmodels` differs from the version the copied
results were computed with, or if the OHLCV bar counts change. `api\uv.lock` pins
statsmodels **0.15.0** exactly, so `uv sync --project api` reproduces it and a copied
`pairs\` cache stays `fresh`. If it ever reports `stale` anyway, one run of
`uv run --project api python -m api.scripts.compute_pairs` (about 56 seconds) fixes it.

### New-PC prerequisites

git, uv, pnpm + Node, Python 3.12 (`api\.python-version`), Tailscale. Then
`uv sync --project api` and `cd web; pnpm install --frozen-lockfile`.

### Migration steps, in this order

Order matters: the Tailscale address must exist on the new PC **before** the config is
written, and the config must be written **before** the web build. Copy with **both services
stopped on the old PC** so nothing is mid-write.

| Step | Do | Expect | If it fails |
|---|---|---|---|
| M0 | On the OLD PC: stop both services — `Stop-ScheduledTask mysite-api; Stop-ScheduledTask mysite-web` — and close any foreground windows. | Nothing is writing to `api\data`. | A process lingers: `Get-Process uvicorn,node -ErrorAction SilentlyContinue \| Stop-Process` |
| M1 | On the OLD PC, record what you are about to copy: `foreach($d in 'ohlcv','liquidity','pairs'){ $f=Get-ChildItem "api\data\cache\$d" -Recurse -File; "$d files=$($f.Count) MB=$([math]::Round(($f \| Measure-Object Length -Sum).Sum/1MB,2))" }` | Three lines with non-zero file counts. Write them down — M6 compares against them. | A count of 0 means that cache was never built on this PC; see "If a copy is missed" below. |
| M2 | On the NEW PC: install git, uv, pnpm + Node, Python 3.12, Tailscale. Then `git clone <your repo URL>` and `cd` into it. | The repo exists; `git log -1` shows a recent commit. | A tool is missing: `where.exe uv` / `where.exe pnpm` print nothing — install it before continuing. |
| M3 | On the NEW PC: `uv sync --project api`; then `cd web; pnpm install --frozen-lockfile; cd ..` | Both finish without error. | Network error: retry; these need internet. |
| M4 | Copy from the OLD PC to the NEW PC (USB drive, `robocopy` over the tailnet, or any file transfer): `api\data\cache\ohlcv\`, `api\data\cache\liquidity\`, `api\data\cache\pairs\`, `api\data\watchlist.json`, and optionally `api\data\cache\narrative\coingecko_trending.parquet`. Copy nothing else from `api\data`. | The five paths exist on the new PC. | No `watchlist.json` on the old PC: `Copy-Item api\data\watchlist.example.json api\data\watchlist.json` (BTC, HYPE, ETH, SOL). |
| M5 | On the NEW PC: install and sign into Tailscale with the SAME account, then `& "C:\Program Files\Tailscale\tailscale.exe" ip -4` | One NEW address starting `100.` — it is **different** from the old PC's. Write it down. | Empty or error: not signed in — use the tray icon. |
| M6 | Verify the copy arrived: re-run the M1 command on the NEW PC and compare. | The same file counts and sizes as M1. | A mismatch: re-copy that folder; a partial copy is worse than none. |
| M7 | Create the config fresh for THIS machine: `New-Item -ItemType Directory -Force "$env:LOCALAPPDATA\my_site"; Copy-Item deploy\config.example.psd1 "$env:LOCALAPPDATA\my_site\deploy.psd1"`, then edit `RepoRoot` (`(Get-Location).Path`), `UvPath` (`where.exe uv`), `PnpmPath` (`where.exe pnpm`), `TailscaleExe` (from M5). Leave `CacheRoot`/`WatchlistPath` empty. | Every path is absolute and points at the NEW machine. | Do not reuse the old PC's file verbatim — its paths and address are wrong. |
| M8 | Rebuild the web app so the NEW address is baked in: `powershell -NoProfile -ExecutionPolicy Bypass -File deploy\build-web.ps1`, then `Select-String -Path "web\.next\static\*" -Pattern 'http://100\.' -Recurse -List` | At least one file contains the NEW `http://<new ip>:8000`, not the old one. | The old address appears: you copied `web\.next` — delete it (`Remove-Item web\.next -Recurse -Force`) and rebuild. |
| M9 | Continue with the ordinary setup from **B5** above (parse check, dry run, start, reachability, Task Scheduler), then run the migration verification below. | As documented in B5-B15. | As documented there. |
| M10 | Decommission the OLD PC once the new one works: `powershell -NoProfile -ExecutionPolicy Bypass -File deploy\register-tasks.ps1 -Remove` on the OLD PC so it stops serving, then sign the old PC out of Tailscale (or remove that device in the Tailscale admin console). | The old PC has no tasks and is no longer on the tailnet. | A task is stuck: remove it from Task Scheduler by hand. |

### Verify the copied data actually arrived

Run these on the NEW PC with the API started (after B8). They prove the caches are being
read, not just present.

| Check | Command | Expect | If it fails |
|---|---|---|---|
| Pairs cache is live | `(Invoke-RestMethod "http://<new ip>:8000/api/pairs").computation_status` | `fresh`. Not `results_unavailable` (the `pairs\` copy did not arrive) and not `stale`. | `results_unavailable`: re-copy `api\data\cache\pairs\`. `stale`: check `statsmodels` (`uv run --project api python -c "import statsmodels; print(statsmodels.__version__)"` should print `0.15.0`), then run `uv run --project api python -m api.scripts.compute_pairs`. |
| Regime cache is live | `(Invoke-RestMethod "http://<new ip>:8000/api/regime/components").grid_dates.Count` | A number well above 0. | 0: `api\data\cache\liquidity\` did not arrive — re-copy it. |
| Price cache is live | Open `http://<new ip>:3000/screener` | Coin panels render with price history. | Empty or unavailable panels: `api\data\cache\ohlcv\` did not arrive — re-copy it. |
| Watchlist is yours | `Invoke-RestMethod "http://<new ip>:8000/api/watchlist"` | Your own coins, not just the four defaults. | Only the defaults: `api\data\watchlist.json` did not arrive. |

### If a copy is missed, or the old PC dies

Nothing is permanently lost — every cache on the old PC is regenerable, and all four scripts
below exist on this branch:

1. `uv run --project api python -m api.scripts.refresh_cache` — shallow OHLCV (about 500 bars).
2. `uv run --project api python -m api.scripts.backfill_pairs_universe` — the one-time deep OHLCV fetch. Never part of any automatic path.
3. `uv run --project api python -m api.scripts.backfill_primaries` — FRED series for `/regime`.
4. `uv run --project api python -m api.scripts.compute_pairs` — derived pair statistics (run last).

For the watchlist on this branch, copy the example:
`Copy-Item api\data\watchlist.example.json api\data\watchlist.json` (BTC, HYPE, ETH, SOL).
The scripted bootstrap (`api/scripts/bootstrap_watchlist.py`) and `api/scripts/BOOTSTRAP.md`
are available once P1 merges — they do not exist on this branch, and their commands are
deliberately not copied here.

**Unverified, which is exactly why copying is preferred:** whether a fresh deep fetch on the
new machine reaches the same roughly 2020-08-19 Hyperliquid daily-history floor. That floor
looks server-side but has never been confirmed against Hyperliquid's own documentation (an
existing known gap). A rebuild might therefore give you less price history than the copy
would have.

## Building the web app: the rebuild rule

`NEXT_PUBLIC_API_BASE_URL` is baked into the web app when it is built, not read when it
starts. So:

- Always build with `deploy\build-web.ps1` (it sets the variable first and prints the baked URL).
- If your Tailscale address changes, or you switch to a MagicDNS name, **rebuild**. A restart is not enough.
- If a `git pull` changes anything under `web\`, rebuild before the change appears. `start-web.ps1` now refuses a stale build (exit 4).

A build without the variable silently falls back to `http://127.0.0.1:8000`, which on your
phone means the phone itself — every panel would fail.

## Restarting safely after a web change (R12 guards)

The supported way to put a web change live:

1. `Stop-ScheduledTask mysite-web`
2. `git pull --ff-only`
3. `powershell -NoProfile -ExecutionPolicy Bypass -File deploy\build-web.ps1`
4. `Start-ScheduledTask mysite-web`
5. Read `%LOCALAPPDATA%\my_site\logs\web.log` and look for `Smoke check ok`.

Run `start-web.ps1` by hand only while the `mysite-web` task is stopped. If you start a
second copy while the task runs, it stops the running server; the old script then exits
with an error, Task Scheduler restarts it a minute later, and that restart stops your new
server in turn.

What the guards do:

- **Port-scoped stop.** `build-web.ps1` and `start-web.ps1` stop only the process listening
  on the configured web port, by its process id, never by program name. Log lines:
  `Port <p>: nothing listening; nothing to stop.`, `Port <p>: stopping PID <id> (<name>) listening on it.`,
  `Port <p>: still in use after 10s; not continuing.`
- **Build marker and stale refusal.** A successful `build-web.ps1` writes
  `web\.next\static\build-marker.json` (commit, web tree, build id, build time; nothing
  secret), served by the app at `http://<ip>:3000/_next/static/build-marker.json`.
  `start-web.ps1` refuses to start when the marker is absent or the `web\` sources changed
  since the build. Log lines: `Build is current: ...` or
  `Stale build: <reason>. Run deploy\build-web.ps1, then start again.`
- **Smoke check.** `start-web.ps1` runs `next start` as a child process, then polls
  `http://<ip>:3000/` on this PC's own Tailscale address every 2 s for HTTP 200 and the
  marker's build id (from the served marker file, else the page HTML). The default limit
  is 90 s; `start-web.ps1 -SmokeTimeoutSeconds <5..600>` changes it. Log lines:
  `Smoke check ok: <url> returned 200 and build id <id> matches the marker (evidence: marker-file|html).`
  or `Smoke check FAILED: <reason> after <n>s.`

Exit codes of `build-web.ps1` and `start-web.ps1`:

| Code | Meaning |
|---|---|
| 2 | Config error (missing key, bad `WebPort`, bad `-SmokeTimeoutSeconds`). |
| 3 | Timed out waiting for the Tailscale address. |
| 4 | Stale or missing build: run `build-web.ps1`. |
| 5 | The web port was not freed, or its listener is a protected process. |
| 6 | Smoke check failed; the new server was stopped. |
| 7 | The build marker could not be written. |

A failed build keeps pnpm's own exit code. After a passing smoke check, `start-web.ps1`
exits with the web server's own code when the server ends.

The first start after this change needs one rebuild: there is no marker yet, so
`start-web.ps1` refuses with exit 4 until `build-web.ps1` has run once.

## Starting it automatically (Task Scheduler)

`register-tasks.ps1` creates two tasks that run at **your** logon, as you, without admin
rights, restarting up to 3 times one minute apart if they fail. After a reboot with nobody
logged on, the app is down — that is expected for an intermittently available PC.

Logs: `%LOCALAPPDATA%\my_site\logs\api.log` and `web.log`.

## Collector (separate from the API)

The attention collector (X search and Reddit) used to run inside the API process, so every API
restart interrupted collection. It now runs as its own process:
`python -m api.data.attention_collector`, started by `deploy\start-collector.ps1`. It runs both
sources (two threads, same pacing, budgets and evidence as before) and writes the rotating log
`<cache>\attention\_logs\attention_pc.log` plus `%LOCALAPPDATA%\my_site\logs\collector.log`.

- **The API no longer needs `SCREENER_ATTENTION_PC_WORKER`.** The launcher sets it for the
  collector process only. The API still honours the flag (the old in-API mode), so nothing breaks
  while it is set, but then the API and the collector compete for one collector slot.
- **Only one collector at a time.** Both modes write `<cache>\attention\_pc_state\collector_heartbeat.json`
  every 30 s. A start is refused (exit code 3, log line `another_instance`) while another
  process's heartbeat is younger than 90 s and that process is alive, so the shared Reddit and
  X budgets are never spent twice. A crashed collector leaves an old heartbeat that does not block.
- **Status box.** /narrative, Discovery tab, under the window buttons: `Collector: Running
  (standalone process)` or `Running (inside the API)`, `Stopped (...)` or `Not started`, the start
  time, the heartbeat age, and one line each for X search and Reddit (last unit, pause, stale,
  budget). A missing or unreadable heartbeat never shows as running.
- **Stopping.** CTRL+C (or closing the window) stops it cleanly and marks the heartbeat stopped.
  `Stop-ScheduledTask` ends it hard; the box then reads `Stopped (process not running)`. If the box
  still reads Running after that, the process id is in the heartbeat file:
  `(Get-Content <cache>\attention\_pc_state\collector_heartbeat.json | ConvertFrom-Json).pid`.
- **Code updates.** The collector does not pull. After a pull that changes the collector, restart
  it (the box shows the commit it runs as `code <sha>`).

### Transport identity (B1, 02-11-26; both switches default off, nothing here has been run live)

Two optional keys in the `collector` block of `api\data\attention_queries.json` (absent means the defaults):

- `x_connection_style`: `plain` (default, httpx, one bounded curl fallback per UTC day pool-wide) or `curl`
  (normal browser-like transport for every X client). Changing it needs a collector restart.
  `deploy\start-collector.ps1` reads it, refuses any other value, and sets `TWS_HTTP_BACKEND` to `httpx` or `curl`
  for the collector process only. Global `TWS_PROXY`, `HTTP_PROXY`, `HTTPS_PROXY` and `ALL_PROXY` are still removed
  and still refused by the reader.
- `x_identity_enabled` (default false) with `x_account_identities`: per account label `accept_language`, `region`,
  `timezone`, an exact `impersonation_target` (for example `chrome131`, never an alias) and, for style `plain`, a
  literal `user_agent` of the same browser family. Unknown labels, invalid values and duplicate identities refuse
  startup. Under `curl` the wire user agent is the target's own (the curl backend ignores a supplied one).
- Before the library loads, the selected backend is verified (platform, distribution name and version, wheel tag,
  lock and allowlist hash, install record; the installed binaries are NOT re-hashed). Selected `curl` that does not verify
  refuses startup; there is no curl-on-curl fallback.
- Limitation: in `plain` style the daily curl fallback child sends the target-derived user agent, which may differ in
  version text from the account's literal one; it is used at most once per UTC day for the whole pool.
- Rollback: set `x_identity_enabled` false and `x_connection_style` `plain` (or remove both keys) and restart.
  Proxies and the real-account comparison are not part of B1 and were not run.

### Switchover steps (UNRUN: none of these commands has been run; run them in order)

| Step | Do | Expect |
|---|---|---|
| C1 | Find where the API gets the flag: `[Environment]::GetEnvironmentVariable('SCREENER_ATTENTION_PC_WORKER', 'User')`, and check the window or task that runs `start-api.ps1`. (UNRUN) | `1` if it is a user variable; otherwise it is set in the API window. |
| C2 | Remove it from the API launch environment: `[Environment]::SetEnvironmentVariable('SCREENER_ATTENTION_PC_WORKER', $null, 'User')`, or stop setting it in the API window. Then restart the API: `Stop-ScheduledTask mysite-api; Start-ScheduledTask mysite-api`. (UNRUN) | The box reads `Collector: Stopped (stopped cleanly)`. Collection pauses until C4. |
| C3 | `powershell -NoProfile -ExecutionPolicy Bypass -File deploy\start-collector.ps1 -DryRun` (UNRUN) | `SCREENER_ATTENTION_PC_WORKER = 1`, your Reddit stream setting, proxy variables cleared, the `uv run ... api.data.attention_collector` command. |
| C4 | Start it in its own window: `powershell -NoProfile -ExecutionPolicy Bypass -File deploy\start-collector.ps1` (or register the task below and `Start-ScheduledTask mysite-collector`). (UNRUN) | Log line `attention collector running`; within a minute the box reads `Collector: Running (standalone process)`. Exit code 3 means a collector is still running inside the API: redo C2. |
| C5 | Restart the API again: `Stop-ScheduledTask mysite-api; Start-ScheduledTask mysite-api`. (UNRUN) | The box still reads `Collector: Running (standalone process)` with the same start time. |

`SCREENER_ATTENTION_REDDIT_STREAM` is inherited as you set it (exactly `1` turns the Reddit stream
on); to keep it for the scheduled task, set it as a user variable:
`[Environment]::SetEnvironmentVariable('SCREENER_ATTENTION_REDDIT_STREAM', '1', 'User')` (UNRUN).

### Scheduled collector tasks (UNRUN)

`register-tasks.ps1` still registers only the API and web app. Use the separate
`register-collector-tasks.ps1` for the collector and daily doctor. It uses
`Register-ScheduledTask -Force`, so repeating registration replaces the definitions.
The actual token SID must match the private policy; never elevate or loosen ACLs
to bypass a refusal. See the owner runbook below before registering.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\register-collector-tasks.ps1
Get-ScheduledTask mysite-collector,mysite-collector-doctor | Select TaskName,State
```

UNRUN: registration does not start collection. After reviewing the doctor, run
`Start-ScheduledTask mysite-collector`. To remove both definitions, run
`powershell -NoProfile -ExecutionPolicy Bypass -File deploy\register-collector-tasks.ps1 -Remove`.
Stop collection first; removing a definition is not a substitute for stopping its process.

## LSE API key (equities prices)

The equities prices need `LSE_API_KEY`. Store it once; `start-api.ps1` loads it at every start
(an `LSE_API_KEY` already set in the window wins):

1. Copy the key, then run
   `powershell -NoProfile -ExecutionPolicy Bypass -File deploy\set-lse-key.ps1 -FromClipboard`
   (it checks the key, stores it and clears the clipboard; `-Prompt` types it at a hidden prompt instead).
2. Restart the API: `Stop-ScheduledTask mysite-api; Start-ScheduledTask mysite-api`.
3. Check: `deploy\set-lse-key.ps1 -Status` (present/absent and length, never the value);
   `api.log` shows `LSE key: from key file`. Remove: `deploy\set-lse-key.ps1 -Remove`.

The key is saved in `%LOCALAPPDATA%\my_site\lse-api-key.dat`, protected by Windows for this
user on this PC only: set it again on a new PC. Never commit, paste or log the key.

## After downtime: pull, then optionally recompute

The recovery sequence is: pull, then optionally recompute.

1. **Pull (automatic, stage A).** Every API start runs `git pull --ff-only`. It only
   fast-forwards; it never overwrites your edits. If it refuses (local edits, divergence, no
   network) it logs why and the app starts on the code it already has. It does not rebuild
   the web app and does not touch any cache file.
2. **Recompute (manual, stage B).** The recompute commands live in `api/scripts/BOOTSTRAP.md`
   (available once P1 merges — that file does not exist on this branch or `main` yet, and
   the commands are deliberately not copied here). Run its recompute steps by hand; never
   run the one-time universe backfill as part of recovery. Until P1 merges, this half of the
   drill is not available.

While caches are behind, screens show stale or unavailable states. (Known gap: the screener
chart does not yet mark an aged price cache as stale — reported to the screener's owner.)

### Stage B gate: do not automate recompute until ALL of these hold

Automatic recompute at boot could be interrupted by a shutdown mid-write and truncate a cache
file that has no git copy. It stays manual until:

1. `uv run --project api python -c "from api.data import cache; import sys; sys.exit(0 if hasattr(cache, '_atomic_to_parquet') else 3)"` exits 0 (P1's atomic write helper `_atomic_to_parquet` exists);
2. `uv run --project api pytest api/tests/data/test_cache_atomic_writes.py -q` passes;
3. P1's resume script exists and is safe to interrupt.

None of the scripts in this folder run any recompute or snapshot job, and a test enforces it.

## Firewall (only if B9 times out)

Windows Firewall may block tailnet traffic even though the app is bound to the Tailscale
address. Only then, in an admin PowerShell, add a rule limited to Tailscale addresses on the
Tailscale interface (it does not open your home network):

```powershell
New-NetFirewallRule -DisplayName "my_site tailnet" -Direction Inbound -Protocol TCP -LocalPort 8000,3000 -RemoteAddress 100.64.0.0/10 -InterfaceAlias Tailscale -Action Allow
```

### Fallback design (not used; documented only)

The rejected alternative is binding 0.0.0.0 (fallback only, not used) plus a firewall rule
scoped with `-RemoteAddress 100.64.0.0/10`. It is weaker: every interface gets a listener and
privacy depends entirely on the rule staying correct. Do not switch to it without asking.

## Rollback

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\register-tasks.ps1 -Remove
Get-Process uvicorn,node -ErrorAction SilentlyContinue | Stop-Process
```

Optionally sign out of Tailscale. Your caches and watchlist are untouched by all of this.

## X account caps, rest and ready (Stage 0)

These optional collector settings default **off** in code; existing query files need no change:

- `x_account_daily_cap`: `null` (no per-account limit), or an integer >= 1. Counts loaded entries per
  account per UTC day, including canaries, curl pages and abandoned attempts. The global read budget remains
  the ceiling. A coin-day already started may cross the account cap; it finishes on that account, and the
  next selection skips that account. If no account is selectable because of caps, X waits for the next UTC
  day as `budget_spent`; an in-flight lock wait takes precedence.
- `x_account_rest_days`: integer >= 0, default `0`. When enabled, a label newly added to an **existing**
  pool state rests from the first collector pass that registers it. Existing labels and first-ever pool
  files are grandfathered. Merely viewing status does not register an account or write state.

After adding a configured label and giving it normal manual use, mark it ready:

```powershell
uv run --project api python -m api.data.attention.twscrape_reader --mark-ready acct_new
```

The command accepts a configured label only and writes an ISO UTC timestamp to `account_ready.json`
in the configured accounts folder, atomically. It does not read cookies, open account databases or
contact X. The file is separate from `attention/_pc_state/x_pool.json`, so a running collector cannot
overwrite the mark. Both gates apply: rest must have elapsed **and** the ready mark must be from a
previous UTC day. The account then joins the next day's canary. Re-marking delays activation until
the next UTC day again; no collector restart is required to read the mark.

The status box reuses the X source's account health list: loaded reads today / cap, state and reason,
rest deadline, ready gate, last use and cookie age. Unknown reads stay unknown until accounting starts;
no cap means **no limit**, not zero. Capacity is a file snapshot of remaining selectable caps versus
global room, queued yesterday coin-days and pending canary pages; older backlog is separate. A
shortfall is in reads, not a promise of coverage: losses and restarts can consume extra reads.
Yesterday's coverage uses the existing completeness evidence: eligible = stored + missing,
exact = stored - capped, estimated = capped. Missing evidence is unknown, never fabricated zero.

Rollback: older versions reject the three added per-account state keys. Before rolling back, with
the collector stopped by the owner, back up the pool file and remove `reads_day`, `reads_used` and
`rest_until` from each account object. Keep the ready marks separately. This change does not deploy,
restart anything, renew cookies, add proxies or enable a browser.

## B2 private account routes (04-11-26 local cutover; release BLOCKED)

B2 is default off. This section is a configuration/rollback contract, NOT permission
to start/restart the collector or use live routes/providers. Synthetic local smoke
does not establish deployment ancestor ACLs, route quality, provider terms/privacy,
live region accuracy or anti-ban effectiveness. Owner acceptance and the RT4
evidence pack remain mandatory before live operation.

`CollectorQueriesPath` in the private deployment config, or the launcher's
`-QueriesPath`, selects an explicit absolute owner query file. Keep configured-route
queries, policy, assignments, route list and account DBs outside the repository.
The launcher passes that selection explicitly with frozen `xreader`, bounds query
input to 1 MiB, clears ambient proxy/CA variables and freezes the validated backend.
It does not print the private path. Python reloads/validates the strict schema
before constructing clients. Explicit direct/off requires `x_proxy_required=false`
AND `x_proxy_list_path`, `x_proxy_assignments_path`, `x_proxy_policy_path` all null;
partial/invalid/unavailable configured routing never falls back to direct.

Private policy/list/assignment schemas and authoritative resource limits are in
the selected identity-pool PLAN B2 and VALIDATE. Routes are HTTP without credentials
or verified HTTPS with separately supplied authentication; SOCKS is unsupported.
The owner publishes list/assignment replacements atomically and retains opaque
IDs when reordering. Admission verifies the expected unique exit, fresh bounded
Spamhaus/FireHOL raw-body caches and pinned baseline digest before use. Ipapi is
optional/off; without it region is owner-declared for the verified exit, not measured
geolocation. No provider/key/credential belongs in public configuration or state.

Windows requires the actual collector token/service SID as private-root owner,
protected root/file DACLs with exactly service Modify and SYSTEM directory
ReadAndExecute/file Read, and no inherited/unknown ACEs. Ancestors reject untrusted
owners and nonprivileged write/control rights; SYSTEM/elevated Administrators are
outside this threat boundary. Existing ACLs are never automatically repaired.
Ordinary home/TEMP ancestors are not conforming deployment proof. Synthetic tests
compose ancestor policy separately from native protected temporary files.

Configured cookie DBs use the same application-owned hook in collector, fallback
child and `--refresh-cookies LABEL --queries <selected-private-config>`. Both DB
and rollback journal are securely created/verified before SQLite opens. The FIRST
database pragma is verified `main.locking_mode=EXCLUSIVE`, before any recovery-
triggering read; verified `journal_mode=PERSIST` and `temp_store=MEMORY` follow
before migrations/writes. This preserves the verified journal during hot-crash
recovery; no replacement exception exists. WAL, shm, unknown/missing/replaced
sidecars refuse. Transaction/close checks retain identity and ACL. Live-DB
inspection permits its own SQLite writer but denies deletion/replacement; immutable
query/list/policy snapshot handles also deny writing. Exclusive SQLite contention
is bounded by the connection timeout and does not change direct/off DB behavior.

Every pool-state mutation reloads under the one adjacent lock
`<x_pool.json>.proxy-provider-budget.lock`: Windows `msvcrt.locking` or POSIX
`flock`, non-reentrant, bounded acquisition and `finally` release. Nested helpers
carry internal lock ownership. Optional ipapi reserves and atomically persists
one of 899 UTC-day request starts before sending and holds this SAME lock through
the one-shot completion/timeout. No refund/retry/overlap; final 11 seconds defer;
day change between reservation and send refuses without refund. Process death
releases the OS lock but retains the durable charge. A stale collector save cannot
overwrite reservations. Health work has its independent bounded cadence/cap and
does not consume X reads or bypass global/per-account caps.

Before each unit, changed account revisions evict their readers/bootstrap cache,
invalidate admission and queue canaries even with identity disabled. More than
three changes retain pending canaries across bounded batches and preserve
same-day/current-revision successful labels. Mid-unit typed route failures discard
partial samples while spent reads remain charged. Plain style keeps the existing
once/day pool-wide curl fallback; normal curl never falls back to curl or direct.
Child work/HMAC verifier material stays in bounded private stdin only, never
argv/environment/output/persistent storage; replies bind nonce/revision and are
rechecked before adoption.

**Stopped rollback to pre-B2 code (owner action only, UNRUN):** stop all writers,
back up pool state and private files, and remove exactly these seven per-account
keys: `proxy_id`, `identity_revision`, `proxy_health`, `proxy_checked_at`,
`proxy_quarantine_until`, `proxy_reason`, `proxy_changed_at`. Remove the top-level
`proxy_provider_budget`. Preserve all Part A counters/rest/ready marks and parse
strike fields. Do not strip other keys. Restore explicit direct/off config before
starting old code; never point old code at configured private routing. Private
admission/feed caches are not legacy pool state and must not be reused as proof.
Restore the backed-up B2 state/config together when returning to B2; removing the
keys deliberately loses admission/provider accounting and is not an online reset.

Local evidence (not full acceptance): first bounded smoke reported 12 passed /
8 failed / 0 skipped. Corrected failed mechanism cases subsequently reported
8 passed / 0 skipped (12.49 s), including real Windows protected DB/journal
sharing+ACL extraction/reopen with synthetic ancestor composition, real hot-crash
rollback with retained journal identity, actual spawned HMAC current-revision
bootstrap+GraphQL clients, both proxy-scheme curl cancellation, and admission/
provider/cache cases. Full locked backend, web and browser acceptance is owned by
the integration tester and must be recorded separately; these are not live probes.

Additional bounded regression evidence: a later 13-case smoke reported 11 passed /
2 failed (the two direct-child fixtures expected `fail` where existing strict
schema rejection correctly returned `refused`; assertions were corrected to the
exact safe contract). Partial-cleanup smoke also exposed callback socket-set
bookkeeping warnings; native socket membership now remains available until
multi cleanup, and any final callback-installed timer is cancelled. The corrected
9-case smoke reported 9 passed / 0 skipped (18.84 s), covering easy/watcher/timer
cleanup faults through both proxy schemes, exact required/partial direct refusal
and exclusive SQLite contention/release. Native refresh also exercised the
protected DB hook in that preceding smoke. Typed normal/canary/fallback dispatch
smoke separately reported 3 passed (1.43 s). These separate development runs are
not a consolidated acceptance total.

E8 proof-boundary correction: the earlier spawned direct/off predicate unit cases
use an injected search response and do not by themselves prove composed wire/
cursor/accounting behavior. A separate regression now composes parent pool/unit,
the real bounded child runner and spawned entrypoint, real `API.search_raw`,
QueueClient/cookie DB, cursor encoding and both direct TLS client factories. Its
test dependencies select only synthetic endpoint/DNS/trust and a deterministic
transaction-ID parser whose bootstrap still makes a real fixture TLS request.
It asserts continuation, adopted next cursor, retained global/account charges,
pool-wide daily fallback cap and no second child/wire attempt. Four additional
spawned configured/partial/required cases prove an available direct fixture route
is never used. Parent-authorized bounded implementer execution subsequently
reported **5 passed / 0 skipped (30.07 s)** for the composed test plus four negative
modes. A final strengthened child-diagnostic/protocol credential-marker assertion
reported **1 passed (7.22 s)** for the changed composed case; unchanged negatives
were not repeated. Fixture root causes were an incomplete runtime stub, omission
of Windows OS environment variables, a missing private temporary directory, and a
transaction-ID parser mock whose signature violated the pinned compatibility
guard. The corrected test uses real `ProxyRuntime`, the normal OS environment
through the production child allowlist, an existing isolated private temp directory
and the exact bootstrap signature. No production guard was bypassed or relaxed.
Independent consolidated acceptance and live release gates remain separate.

## Collector identity pool runbook (owner steps)

**UNRUN on the owner machine.** These are manual owner steps, not authorization
for an agent to log in, create accounts, apply firewall rules, or contact providers.
Keep optional features off until their step below. Fixture success means
CODE-COMPLETE, not LIVE-READY. A failed live gate leaves data missing-not-zero.
The per-account, per-session, in-process CONNECT relay binds only 127.0.0.1,
uses an explicit host allowlist and is NOT a gateway.

### 1. Prepare the private layout and accounts

Use `deploy/examples/private-layout.example.txt` as the layout guide and
`deploy/examples/collector-queries.example.json` as collector-block overrides,
not as a complete query document. Copy the complete committed query file outside
the repository, retain its coin/subreddit definitions, and edit its collector block.
Do not paste the example's `_how_to_use` key into the actual query document.
Use an installed Edge/Chrome executable, not a copied single executable: browser
installations need their companion files. Profiles must be dedicated to collection.

| Owner input | Exact form |
|---|---|
| Private queries | Absolute external JSON path; version 1 query document, strict collector keys |
| Deployment config | `%LOCALAPPDATA%\my_site\deploy.psd1`; `CollectorQueriesPath` points to that JSON |
| X labels | `x_accounts`: array of distinct lowercase `[a-z0-9_]{1,24}` labels, not credentials |
| X database folder | `x_accounts_db_path`: absolute external folder; one `<label>.db` per account |
| Reddit labels/profiles | `reddit_browser_accounts`: `[{"label":"r_acct1","profile":"r_acct1"},{"label":"r_acct2","profile":"r_acct2"}]` |
| Browser | `browser_path`: installed executable absolute path; `browser_profiles_dir`: private external folder |
| X profiles | `x_account_profiles`: object mapping each X label to a unique profile name |
| Routes | All three absolute `x_proxy_list_path`, `x_proxy_assignments_path`, `x_proxy_policy_path`; `x_proxy_required:true` |
| Surface | `reddit_surface_path`: absolute private published JSON; optional separate `x_surface_path` |

Labels and normalized profile names must be unique across both sites. Set
`x_account_rest_days:7`, `reddit_browser_account_rest_days:7` and an appropriate
per-account cap. About four X accounts, six worst case, is the sizing estimate
for this universe, not a coverage promise. The two Reddit accounts created
07-11-26 reach one week on 14-11-26; collector rest and next-day ready gates
still apply. Only the owner creates or logs into accounts.

Run from the repository root in a normal PowerShell:

```powershell
$q = 'C:\MySitePrivate\config\attention_queries.private.json'
$surface = 'C:\MySitePrivate\surface\reddit_surface.json'
$browser = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
$cache = 'C:\MySitePrivate\cache'
$env:SCREENER_CACHE_ROOT = $cache
$env:TWS_TELEMETRY = '0'
$env:DO_NOT_TRACK = '1'
$env:TWS_LOG_LEVEL = 'WARNING'
$env:TWS_RAISE_WHEN_NO_ACCOUNT = '1'
uv sync --project api --frozen --group xreader
```

Set the same CacheRoot in deploy.psd1. Never store real values in examples.
Private-root ACLs must satisfy the existing B2 owner/SYSTEM policy, including
ancestors; the doctor refuses unsuitable roots rather than repairing them.

### 2. Load X cookies, ready marks and routes

Use the owner's browser to obtain the cookie string. Read it without echoing or
putting its literal value in shell history; the refresh command's existing
environment boundary is transient. Never put cookies in arguments or logs.

```powershell
$secure = Read-Host 'X cookie string for x_acct1' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $env:X_REFRESH_COOKIES = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    uv run --project api --frozen --group xreader python -m api.data.attention.twscrape_reader --refresh-cookies x_acct1 --queries $q
} finally {
    Remove-Item Env:X_REFRESH_COOKIES -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    $secure.Dispose()
}
uv run --project api --frozen --group xreader python -m api.data.attention.twscrape_reader --mark-ready x_acct1 --queries $q
uv run --project api --frozen --group xreader python -m api.data.attention.reddit_accounts --mark-ready r_acct1 --queries $q
```

Repeat for each configured label. Ready means eligible from the next UTC day,
after rest, not immediate activation. Supply the existing B2 policy/list/assignment
files privately; preserve opaque route IDs, distinct exits across X and Reddit,
the policy's actual user SID, baseline hash and bounded feed caches. Do not
disable `x_proxy_required` to bypass unadmitted or quarantined routes.
Direct/off is only `false` plus **all three route paths null**.

### 3. Establish the daily report baseline

Reports are automatic at pass end; there is no enable switch to invent.

```powershell
uv run --project api --frozen --group xreader python -m api.scripts.attention_daily_report --print
```

Read `<cache>\attention\_reports\daily_report_<UTC-day>.json`.
Eligible must equal stored plus missing; exact and estimated describe stored
data. No evidence means unknown or missing, never an invented zero.

### 4. Review firewall text and admit the browser

The owner chose firewall containment and accepted CE-1/CE-2 profile exceptions.
This is not yet proof of installed-browser containment. Keep the sandbox enabled.
Generate text without changing any firewall state:

```powershell
uv run --project api --frozen --group xreader python -m api.scripts.browser_firewall_rule --program $browser
# For a dedicated Windows user, add --user 'MACHINE\collector'.
```

Review the output. The rule affects EVERY use of that executable unless scoped
to a dedicated Windows user. Only the owner applies the chosen command in an
administrator PowerShell. The netsh alternative is not user-scoped; do not use
it as a substitute for the scoped PowerShell rule.

```powershell
New-NetFirewallRule -DisplayName "mysite-collector-browser-block" -Direction Outbound -Action Block -Program $browser -Profile Any
Get-NetFirewallRule -DisplayName "mysite-collector-browser-block" | Get-NetFirewallApplicationFilter
# Removal, if needed:
Remove-NetFirewallRule -DisplayName "mysite-collector-browser-block"
```

After applying, return to the normal collector user's shell:

```powershell
uv run --project api --frozen --group xreader python -m api.data.attention.browser_selftest --binary $browser --cache-root $cache
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\doctor.ps1 -QueriesPath $q
```

`contained` requires attested rule, zero Established non-loopback endpoints and
working loopback relay. Rule presence alone is insufficient. Record BP1b and
BP3c results; reject unexpected ACLs rather than broadening exceptions.
Version/path/flag changes invalidate admission. TCP polling cannot prove absence
of short-lived connections, all UDP, or activity of unrelated processes.

### 5. Initialize profiles and log in manually

UNRUN: only after browser gates are admitted:

```powershell
uv run --project api --frozen --group xreader python -m api.data.attention.browser_session --site reddit --label r_acct1 --init-profile --queries $q
uv run --project api --frozen --group xreader python -m api.data.attention.browser_session --site reddit --label r_acct1 --interactive --queries $q
uv run --project api --frozen --group xreader python -m api.data.attention.browser_session --site reddit --label r_acct2 --init-profile --queries $q
uv run --project api --frozen --group xreader python -m api.data.attention.browser_session --site reddit --label r_acct2 --interactive --queries $q
```

The owner types credentials in the browser, never in the terminal. Stop at
login/challenge; do not automate challenge solving. Reddit cookie values are
never harvested. For X, initialize each configured X profile similarly with
`--site x`, then explicitly request owner-interactive harvesting:

```powershell
uv run --project api --frozen --group xreader python -m api.data.attention.twscrape_reader --harvest-cookies x_acct1 --interactive --queries $q
```

### 6. Run bounded owner probes in this order

Each command below is initially a **dry run**. Read its purpose, limits and
`approval_digest`. Re-run that exact command adding `--approve <that digest>`
only when the owner approves its provider requests/browser launches.
Do not reuse another probe's digest. Add `--commit (git rev-parse HEAD)` to
record the running revision.

```powershell
uv run --project api --frozen --group xreader python -m api.scripts.probe_owner PX1 --queries $q
uv run --project api --frozen --group xreader python -m api.scripts.probe_owner PX2 --queries $q
uv run --project api --frozen --group xreader python -m api.scripts.probe_owner PX3 --queries $q
uv run --project api --frozen --group xreader python -m api.scripts.probe_owner PX4 --queries $q
uv run --project api --frozen --group xreader python -m api.scripts.probe_owner PX5 --queries $q
uv run --project api --frozen --group xreader python -m api.scripts.probe_owner PX6 --queries $q
```

PX1 checks query IDs; PX2 compares candidates; PX3 checks each account; PX4
observes cookie rotation; PX5 compares transports; PX6 checks harvesting.
Enable `x_queryid_mode:"sentinel"` first, inspect evidence, then `"auto"`.
Enable `x_cookie_harvest_enabled:true` only after PX6; optional
`x_cookie_refresh_age_days` controls the age trigger. Suspensions are terminal,
not a reason to repeatedly harvest.

Then capture, review and explicitly publish Reddit grammar:

```powershell
uv run --project api --frozen --group xreader python -m api.scripts.probe_owner PR2 --mode bootstrap --queries $q
uv run --project api --frozen --group xreader python -m api.scripts.surface_tool surface-propose --section browser
uv run --project api --frozen --group xreader python -m api.scripts.surface_tool --approve-surface browser --surface-path $surface
uv run --project api --frozen --group xreader python -m api.scripts.probe_owner PR2 --mode verify --surface-path $surface --queries $q
uv run --project api --frozen --group xreader python -m api.scripts.probe_owner PR1 --mode bootstrap --surface-path $surface --queries $q
uv run --project api --frozen --group xreader python -m api.scripts.surface_tool surface-propose --section gql_anon
uv run --project api --frozen --group xreader python -m api.scripts.surface_tool --approve-surface gql_anon --surface-path $surface
uv run --project api --frozen --group xreader python -m api.scripts.probe_owner PR1 --mode verify --surface-path $surface --queries $q
uv run --project api --frozen --group xreader python -m api.scripts.probe_owner PR5 --queries $q
uv run --project api --frozen --group xreader python -m api.scripts.probe_owner PR6 --queries $q
```

The probe commands still need their own `--approve` digest; publication is a
separate owner decision. PR1 needs a valid gql_anon draft surface; absence must
refuse, not guess request grammar. PR5 compares admitted route classes; PR6
needs seven completed UTC days of local facts. Archive and cookie-HTTP routes
are not fallback options. If PR1/PR2 fail or captures do not fit, retain
missing-not-zero and use the owner-authorized parser-extension workflow on
real captures; do not pretend unsupported responses are empty results.

### 7. Enable measured optional behavior

Change the private JSON and restart after each change. Enable one B3 switch
at a time: `x_quiet_hours_enabled` (with per-account timezone/start/end),
`x_mixed_traffic_enabled` (with bounded `x_mixed_targets`), `x_variation_enabled`,
`x_adaptive_cooldown_enabled`, then `x_warmup_enabled`.

```powershell
uv run --project api --frozen --group xreader python -m api.data.attention.x_behaviour_report --from 2026-11-07 --to 2026-11-14
```

Use actual completed dates. Compare costs and outcomes; no anti-ban benefit is
claimed. Finally enable `reddit_live_methods:["browser"]`, adding `"gql_anon"`
only after its independent verify gate passes. It remains partial for comments.
Enable `reddit_session_check_enabled:true` only for the separate daily session
check; every browser launch still checks login regardless of that switch.

### 8. Daily checks and status meanings

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\doctor.ps1 -QueriesPath $q -Json
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\doctor.ps1 -QueriesPath $q -Live
uv run --project api --frozen --group xreader python -m api.scripts.attention_daily_report --print
```

Check heartbeat freshness, account capacity/rest, missing reasons, probe age,
quarantine and disk space. Doctor PASS means that check passed; WARN needs
attention; FAIL is a failed prerequisite; UNKNOWN means not measured/readable,
never healthy. Exit codes are 0 all PASS, 1 WARN/UNKNOWN, 2 any FAIL.

| State | Owner response |
|---|---|
| resting / not ready | Wait for rest and previous-UTC-day ready mark; do not reset counters |
| budget_spent | Wait for UTC rollover; do not reset charged reads |
| x_login_required | Refresh/harvest once after manual login; preserve accounting |
| x_account_suspended / locked | Stop using that account; no automatic recovery |
| quarantined / proxy_not_admitted | Diagnose route/exit/feed freshness; never bypass to direct |
| needs_probe / probe_stale | Run the specific approved live verify probe |
| surface_changed / surface_unpublished | Review/publish the section and re-verify |
| containment_residual_unaccepted | Browser blocked; complete firewall/admission steps |
| accepted_residual | Residual was accepted, NOT OS containment; owner's selected route is firewall |
| contained | A19 evidence passed for the exact admitted version; not absolute network proof |
| browser_unadmitted / cdp_pipe_unavailable / profile_policy_unsatisfied | Stop browser use; fix the named gate, never disable sandbox |
| missing / unknown / partial | Preserve that evidence classification; never relabel as zero or complete |

Reddit calendar: old feeds stop 13-11-26; API removal begins 12-01-27; public API
ends March 2027. Gaps between feed cutoff and first live settle cannot be
backfilled by this implementation. Respect provider terms and deletion requests;
do not preserve deleted content as a workaround for unavailable sources.

### 9. Register, restart and rollback

UNRUN: run as the same normal Windows user whose actual SID owns the private
policy. Tasks use Interactive/Limited, never elevated or stored credentials.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\start-collector.ps1 -Doctor -DryRun -QueriesPath $q
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\register-collector-tasks.ps1 -QueriesPath $q -DoctorTime 07:00
Get-ScheduledTask mysite-collector,mysite-collector-doctor | Select TaskName,State
Start-ScheduledTask mysite-collector
```

Collector starts at logon, restarts three times one minute apart and ignores
duplicate starts. Doctor runs daily at local 07:00. Logged-out collection is
not provided. Locked/disconnected rendering still requires owner probe BP12.
Record the first native run; text-shape tests do not prove Task Scheduler.
The launcher `-Doctor` runs offline: FAIL refuses start with exit 5; WARN/UNKNOWN
are logged without treating pending live evidence as a hard collection blocker.

Before a code update stop the collector, back up private state securely, pull
the approved revision, sync frozen dependencies, run doctor and restart.
Browser updates require fresh admission and profile checks before live use.

**Rollback:** stop writers first (`Stop-ScheduledTask mysite-collector`).
For optional-feature rollback set query IDs to `"off"`, harvest and all five
B3 booleans false, session check false, and `reddit_live_methods:[]`; restart.
For transport rollback follow the B1/B2 sections above and preserve charged
reads/rest/ready marks. Never point pre-B2 code at routed private databases.
For task rollback remove both definitions:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\register-collector-tasks.ps1 -Remove
```

For firewall rollback the owner runs the removal command from step 4, then
keeps browser-dependent features disabled until fresh containment evidence
exists. Do not remove private account data or reset quarantine as a rollback.
