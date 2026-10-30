# Narrative Baskets: 24/7 server host guide (W8e2, 30-10-26)

Slice W8e2 of `narrative-baskets-xreddit-collector_PLAN_21-10-26.md`; turns SPEC Annex J items 1-11 into owner steps for the spare laptop that runs the X and Reddit collector worker.

**Status of every command in this guide: UNRUN.** Nothing here was executed on any host by the author. Each command is an example to adapt. Words in angle brackets (`<repo-root>`, `<service-user>`, `<accounts-dir>`) are placeholders you replace. No secret, cookie value or real path belongs in this file, in a commit, in a prompt or in a log.

## 0. What runs on the host

The API process (`api.main:app`) starts the attention worker in its lifespan only when `SCREENER_ATTENTION_PC_WORKER` is exactly `1` (`api/data/attention_pc_refresh.py`, `FLAG_ENV`, `enabled`). The worker runs the Reddit and X streams, persists its state under the cache (`<cache>/attention/_pc_state`: pause state, daily counts, effective budget, clean-day count, last unit time) and writes a rotating log to `<cache>/attention/_logs/attention_pc.log`. Times are UTC. While the host is off nothing runs and nothing is stored; after a restart the worker resumes through `_behind` at the configured pace (no burst).

Worker environment variables (all read in `attention_pc_refresh.py`):

| Variable | Meaning | Default |
|---|---|---|
| `SCREENER_ATTENTION_PC_WORKER` | `1` starts the worker; any other value or unset means off | off |
| `SCREENER_ATTENTION_PC_LOG_MAX_BYTES` | size cap per log file; a missing or invalid value falls back to the default | 5000000 |
| `SCREENER_ATTENTION_PC_LOG_FILES` | number of rotated log files kept; a missing or invalid value falls back to the default | 5 |

The cache location comes from `SCREENER_CACHE_ROOT` (set by `deploy/start-api.ps1` from the `CacheRoot` key of the deploy config; when empty the default `api/data/cache` is used).

## 1. Decision for the owner: which operating system

The plan (T179, Q29) leaves the final choice to the owner. Both are supported: the installer picks the `curl_cffi==0.16.3` wheel by platform, and the reader's startup guard refuses an unknown platform (it then runs with the curl fallback off and says so in the health line).

| | Windows | Linux (systemd) |
|---|---|---|
| Existing repo support | `deploy/start-api.ps1`, `deploy/register-tasks.ps1`, `deploy/README.md` already start the API at log-on, bound to the Tailscale address | No launcher in the repo; the unit file below is new and unrun |
| Unattended start without a person | A task at log-on needs a logged-in user, so you need auto-logon (a physical-access trade-off, step W3) or a task that runs whether the user is logged on or not (needs the user's password stored by Windows, and the DPAPI key helper used by `start-api.ps1` is untested in that mode) | A service starts at boot with no login at all |
| Crash restart | Task Scheduler restart settings (3 tries, 1 minute apart in `register-tasks.ps1`), then it stops | `Restart=always`, never gives up |
| Private temporary files | Library parse-error dumps use a literal `/tmp` path (`twscrape_reader.py`, `LIBRARY_DUMP_ROOT`); Windows has no equivalent, so the dump-cleaning step has no target there | `PrivateTmp=true` keeps the dumps private and a cleaner clears them |
| Account file permissions | The reader does NOT check the ACL on Windows (it reports `windows_acl_not_checked` in health); you set it with `icacls` | The reader enforces mode 600 files and owner uid |
| Updates and restarts | Windows Update may reboot at idle hours; you must set active hours | You choose when to reboot |
| Laptop quirks | Sleep, hibernate and lid action via `powercfg` | Masked sleep targets and `HandleLidSwitch=ignore` |
| Effort for a non-admin owner | Lowest (known tools, existing scripts) | Higher the first time |

**Recommendation (a judgement, not a measurement):** Linux for a machine that is meant to be forgotten for weeks, because it starts at boot without any login, restarts forever on crash, keeps the library dumps private and enforces the account-file permissions in code. Choose Windows if you want to reuse the existing `deploy/` scripts and Tailscale set-up unchanged and accept auto-logon on a dedicated local user. Whichever you choose, write the decision here once made: `OS chosen: ______ date: ______` (kept out of the repo until you decide).

Common to both: use a dedicated, non-admin local user (`<service-user>`), full-disk encryption, and never the owner's main accounts or password on this machine.

## 2. Install the X reader (both OS)

Run from `<repo-root>` on the host. The group is `xreader` in `api/pyproject.toml`; the command below is the one in `twscrape_reader.py` and the W8d2 report.

```powershell
uv sync --project api --frozen --group xreader
```

Then write the install record for the curl wheel of this platform (`--write-curl-record` exists in `twscrape_reader.py`; it prints a status and refuses unless `uv.lock` holds the table hash for this platform):

```powershell
uv run --project api --frozen python -m api.data.attention.twscrape_reader --write-curl-record
```

The flag `x_allow_curl_backend` stays `false` unless you decide otherwise (SPEC rule 19, AC53).

## 3. Accounts and cookies stay only on this host

Do not copy cookies, account files or the pool directory anywhere else, and do not put them in the repository, a commit, a prompt, a ticket or a log. This guide deliberately contains no cookie example.

- Account files live in a directory outside the repository on an encrypted disk, readable by the service user only. Config keys `x_accounts_db_path` (the directory) and `x_accounts` (labels only, registration order) are in `api/data/attention_queries.json`, collector block. With an empty path X does not start.
- Throwaway accounts only, never the main or a Premium account.
- Registering and refreshing cookies: use `python -m api.data.attention.twscrape_reader --refresh-cookies <label>`. The cookie string goes in the environment variable `X_REFRESH_COOKIES` (never on the command line), you remove the variable afterwards, and the command records the refresh time used for the cookie age in the health line. The exact PowerShell sequence (encrypted disk check, `icacls`, per-account upsert, local health check) is the "Owner steps on the 24/7 host" block under heading 10 of `narrative-baskets-xreddit-collector-t212-w8d2_REPORT_27-10-26.md`; follow it there rather than copying it here. On Linux the same report says: LUKS volume, `chmod 700` on the directory, `export` and `unset` instead of `$env:`.
- Local reader health with no request to X: `uv run --project api --frozen python -m api.scripts.probe_pc_sources --source xsearch --reader-status` (flag verified in `probe_pc_sources.py`; prints accounts active over total, cookie age in days, commit match, environment guard result, curl fallback status).

Environment the X reader requires (`REQUIRED_ENV` in `twscrape_reader.py`; the reader refuses to start without them): `TWS_TELEMETRY=0`, `DO_NOT_TRACK=1`, `TWS_LOG_LEVEL=WARNING`, `TWS_RAISE_WHEN_NO_ACCOUNT=1`. No proxy variables (`TWS_PROXY`, `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`) and no `TWS_HTTP_BACKEND` may be set in the service environment (only the curl fallback child gets `TWS_HTTP_BACKEND=curl`, set by the code).

## 4. Windows steps (W1-W9)

All examples are PowerShell, run as described, UNRUN. Elevation is needed only for `powercfg` machine settings and `w32tm /resync`.

**W1. Dedicated user and disk.** Create a local standard user for the collector. Turn on BitLocker for the system and data disks (`manage-bde -status C:` should show protection on).

**W2. Deploy config.** Copy `deploy/config.example.psd1` to the real config and fill `CacheRoot` if the cache should live on the encrypted data disk; `deploy/README.md` explains the Tailscale binding. The API stays bound to the Tailscale address, not a public port.

**W3. Auto-start and the log-on question (Annex J items 1 and 3).** `deploy/register-tasks.ps1` registers tasks `mysite-api` and `mysite-web` that start at log-on of the current user, limited rights, restart 3 times 1 minute apart, no time limit:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\register-tasks.ps1
Get-ScheduledTask -TaskName mysite-api
```

Register it while logged in as the collector user, so the task runs as that user. Annex J also gives a single-task form (`schtasks /Create /TN "AttentionApi" /SC ONLOGON /RL LIMITED /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File <repo-root>\deploy\start-api.ps1"`); use one form or the other, not both, or two API processes fight for the port.

A log-on task only runs after someone logs on, so after a power cut the laptop needs auto-logon. Trade-off: anyone with physical access gets that user's session and files. Mitigations: dedicated non-admin local user, full-disk encryption, nothing of yours on the box, laptop in a locked room. Setting up auto-logon is your choice and method (Sysinternals Autologon stores the password as an LSA secret rather than plain text; the plain registry method stores it readable). Do not use your main Windows password. The alternative, a task set to run whether the user is logged on or not, avoids auto-logon but is untested with the DPAPI key helper and the Tailscale wait in `start-api.ps1`; try it only if you accept that.

Note (T179): twscrape logs in with cookies, so no browser session needs to exist; the user-session requirement comes from the log-on task trigger, not from X.

**W4. Enable the worker.** Set the variables for the collector user so the task inherits them (they are read when the process starts; re-log-on or reboot after `setx`):

```powershell
setx SCREENER_ATTENTION_PC_WORKER 1
setx TWS_TELEMETRY 0
setx DO_NOT_TRACK 1
setx TWS_LOG_LEVEL WARNING
setx TWS_RAISE_WHEN_NO_ACCOUNT 1
# optional log rotation tuning (defaults 5000000 and 5):
setx SCREENER_ATTENTION_PC_LOG_MAX_BYTES 5000000
setx SCREENER_ATTENTION_PC_LOG_FILES 5
```

Check what `start-api.ps1` would run without starting anything: `powershell -NoProfile -ExecutionPolicy Bypass -File deploy\start-api.ps1 -DryRun`. Note: the dry run prints host, port, CORS, cache and watchlist; it does not print the worker variables, so confirm them with `Get-ChildItem Env:SCREENER_ATTENTION_PC_WORKER` in a new session.

**W5. No sleep, no hibernate, lid (Annex J item 2).**

```powershell
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0
powercfg /setactive SCHEME_CURRENT
powercfg /query SCHEME_CURRENT SUB_SLEEP
```

Keep the laptop on AC power. Set Windows Update active hours so restarts avoid long idle gaps (Settings, Windows Update, Advanced options, Active hours). If the laptop runs on battery during a blip, the settings above apply to AC only; the equivalent `-dc` switches are your choice.

**W6. Clock (item 5).** Windows day windows are UTC; a large clock error breaks them.

```powershell
w32tm /query /status
w32tm /resync
```

**W7. Log and disk rotation (item 4).** The worker log rotates by itself (step W4 variables). The cache is git-ignored and pruned by retention config (`x_raw_retention_days`, ledger 400 days by default). The free-space check is part of the health line once the code half of W8e2 lands; until then check free space monthly with `Get-PSDrive`.

**W8. Restart catch-up (item 6).** Nothing to do: after a restart or a power cut the worker resumes through `_behind` at the configured pace, missing is never 0, and a unit cut by a power loss is retried.

**W9. Remote viewing (item 7) and UPS (item 8).** Keep the API bound to the Tailscale address as `start-api.ps1` does; view it over Tailscale or a remote desktop tool of your choice; open no public port and no router forward. A small UPS is recommended, not required.

## 5. Linux steps (L1-L9)

All commands are UNRUN examples for a systemd distribution; run as root where `sudo` is shown. There is no Linux launcher in the repo, so the unit below is new.

**L1. Dedicated user and encrypted disk.** Create `<service-user>` without a login shell for the service. Put the repository, the cache and the accounts directory on a LUKS volume. The accounts directory: `chmod 700`; files mode 600 (the reader enforces mode 600, owner uid, and refuses otherwise).

**L2. Install** the reader (section 2) as `<service-user>` from `<repo-root>`.

**L3. Service unit** `/etc/systemd/system/attention-api.service` (adapt the paths; the bind address stays loopback, a VPN or SSH tunnel does remote viewing):

```ini
[Unit]
Description=Attention API with collector worker
After=network-online.target time-sync.target
Wants=network-online.target

[Service]
User=<service-user>
WorkingDirectory=<repo-root>
Restart=always
RestartSec=10
PrivateTmp=true
Environment=SCREENER_ATTENTION_PC_WORKER=1
Environment=SCREENER_CACHE_ROOT=<cache-root>
Environment=TWS_TELEMETRY=0
Environment=DO_NOT_TRACK=1
Environment=TWS_LOG_LEVEL=WARNING
Environment=TWS_RAISE_WHEN_NO_ACCOUNT=1
Environment=SCREENER_ATTENTION_PC_LOG_MAX_BYTES=5000000
Environment=SCREENER_ATTENTION_PC_LOG_FILES=5
ExecStartPre=/usr/bin/find /tmp -maxdepth 1 -name 'twscrape*' -delete
ExecStart=<uv-path> run --project api --frozen python -m uvicorn api.main:app --host 127.0.0.1 --port 8000

[Install]
WantedBy=multi-user.target
```

Notes: with `PrivateTmp=true` the `/tmp` the cleaner sees is the service's private one, which is where the library's dumps go. The two log variables are optional (defaults shown). Other app variables the Windows script sets (`SCREENER_CORS_ORIGINS`, `SCREENER_WATCHLIST_PATH`, the LSE key) are owner decisions on this OS; `SCREENER_CORS_ORIGINS` and `LSE_API_KEY` are read from the environment by the API, supply them with additional `Environment=` lines or an `EnvironmentFile=` readable only by `<service-user>`, and never write a key into this file.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now attention-api.service
systemctl status attention-api.service
journalctl -u attention-api.service -n 50 --no-pager
```

**L4. No sleep, lid ignored (item 2 on Linux).**

```bash
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
# in /etc/systemd/logind.conf set:  HandleLidSwitch=ignore   (and HandleLidSwitchExternalPower=ignore)
sudo systemctl restart systemd-logind
```

Restarting `systemd-logind` may end graphical sessions; do it from a console or SSH, or simply reboot.

**L5. Clock (item 5).**

```bash
timedatectl status          # expect: System clock synchronized: yes, NTP service: active
sudo timedatectl set-ntp true
```

**L6. Log and disk rotation (item 4).** Worker log rotates by itself (L3 variables). For journald set `SystemMaxUse=` in `/etc/systemd/journald.conf` (or use logrotate) so the journal cannot fill the disk. Check free space monthly with `df -h`; the health line carries it once the code half lands.

**L7. Restart catch-up (item 6).** As W8: automatic.

**L8. Auto-login.** Not needed on Linux (no browser session; twscrape uses cookies).

**L9. Remote viewing and UPS (items 7, 8).** Keep the bind on `127.0.0.1`; reach it with a VPN or an SSH port forward (`ssh -L <local-port>:127.0.0.1:8000 <host>`); no public port. UPS as in W9.

## 6. Owner probe P-W1 (after the code half and the worker are merged)

From PLAN W8e: with only Reddit built, start the API with the flag on for one hour. On Windows the plan's literal form is:

```powershell
$env:SCREENER_ATTENTION_PC_WORKER="1"; python -m uvicorn api.main:app --port 8000
```

(Use `uv run --project api python -m uvicorn ...` if plain `python` is not the project environment; the repo's own launcher uses that form.) The plan then names `python -m api.scripts.probe_pc_sources --source reddit --status` to print stored days, last unit time, pause state and today's request counts.

**Gap found while writing this guide:** `probe_pc_sources.py` has no `--status` flag. Its flags are `--source`, `--symbol`, `--feed-depth`, `--compare-scope`, `--stream-status` (still prints "not built yet (W8c2)" and exits 2 for Reddit) and `--reader-status` (X only). The P-W1 status command as written in the plan therefore cannot run today. Until a status mode exists, read the worker's log (`<cache>/attention/_logs/attention_pc.log`) and, once the health line lands, the Sources data. Pass criterion stays as in the plan: counts within the caps and spaced as locked.

## 7. Reading the health line (once the W8e2 code half lands)

NOT built yet at the time of writing (the code half of W8e2 is a separate task; check its PR). The contract it implements is SPEC AC39 and rules 15-16, AC38, AC47 and AC52. Per source, read from persisted worker state and evidence files only (no network):

| Field | What it tells you | Act when |
|---|---|---|
| last unit time | the UTC time of the last finished unit | far older than the expected gap |
| `stale` flag | no unit for more than 2 x the expected gap | shown stale: check that the service runs, the clock is right, the host is awake |
| pause reason code and its end | why the source is paused and until when | a warning pause: read the reason; a canary or all-accounts-locked pause needs a cookie refresh or waiting |
| attempted and fetched counts | today's work against what arrived | fetched far below attempted |
| effective budget | today's read budget after halving or doubling (X) | persistently halved |
| completeness text | attempted, fetched, missing with reasons (capped), newest age (AC38) | missing counts grow; a missing day is never 0 |
| accounts active over total, cookie age per account (AC47, AC52) | pool state and cookie freshness | cookie age high or an account `paused`: do the cookie refresh in section 3 |
| curl fallback status | off, ok or unsupported platform | unsupported platform: the fallback stays off by design |

The exact field names and wording are defined by that code and may differ from this table; after it merges, correct this table against `api/analytics/attention/sources.py` and `api/models/discovery.py`.

## 8. Item map (Annex J to this guide)

1 auto-start: W3, L3. 2 no sleep and lid: W5, L4. 3 auto-login: W3 (needed on Windows, not on Linux, L8). 4 disk and log rotation: W7, L6 and section 0. 5 clock: W6, L5. 6 restart catch-up: W8, L7. 7 remote access and health line: W9, L9, section 7. 8 UPS: W9, L9. 9 accounts and secrets: section 3. 10 interim: until the laptop exists the owner's PC runs in degraded mode; nothing else changes. 11 Linux: section 5.
