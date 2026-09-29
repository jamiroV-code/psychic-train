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
| `start-web.ps1` | Starts the built web app (`next start`, never the dev server) on `<tailscale-ip>:3000`. `-DryRun` available. |
| `build-web.ps1` | Builds the web app with `NEXT_PUBLIC_API_BASE_URL=http://<tailscale-ip>:8000` baked in. `-DryRun` available. |
| `register-tasks.ps1` | Creates Task Scheduler tasks `mysite-api` and `mysite-web` that start at your logon (no admin, no SYSTEM account). `-Remove` deletes them. |

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

## Building the web app: the rebuild rule

`NEXT_PUBLIC_API_BASE_URL` is baked into the web app when it is built, not read when it
starts. So:

- Always build with `deploy\build-web.ps1` (it sets the variable first and prints the baked URL).
- If your Tailscale address changes, or you switch to a MagicDNS name, **rebuild**. A restart is not enough.
- If a `git pull` changes anything under `web\`, rebuild before the change appears.

A build without the variable silently falls back to `http://127.0.0.1:8000`, which on your
phone means the phone itself — every panel would fail.

## Starting it automatically (Task Scheduler)

`register-tasks.ps1` creates two tasks that run at **your** logon, as you, without admin
rights, restarting up to 3 times one minute apart if they fail. After a reboot with nobody
logged on, the app is down — that is expected for an intermittently available PC.

Logs: `%LOCALAPPDATA%\my_site\logs\api.log` and `web.log`.

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
