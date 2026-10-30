# Narrative Baskets: 24/7 server host guide (W8e2, 30-10-26)

Slice W8e2 of `narrative-baskets-xreddit-collector_PLAN_21-10-26.md`; turns SPEC Annex J items 1-11 into owner steps for the spare laptop that runs the X and Reddit collector worker. Windows comes first (the owner's existing OS and the repo's existing `deploy/` scripts); Linux is an optional alternative (section 5).

**Status of every command in this guide: UNRUN.** Nothing here was executed on the host by the author. Each command is an example to adapt. Words in angle brackets (`<repo-root>`, `<service-user>`, `<accounts-dir>`) are placeholders you replace. No secret, cookie value or real path belongs in this file, in a commit, in a prompt or in a log.

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

There is no requirement to migrate. Windows is the owner's existing OS, `deploy/start-api.ps1`, `deploy/register-tasks.ps1` and `deploy/README.md` already exist for it, and the plan (T179, Q29) supports both: the installer picks the `curl_cffi==0.16.3` wheel by platform, and the reader's startup guard refuses an unknown platform (the fallback then stays off and the health line says so). The final choice is the owner's.

| | Windows (default path) | Linux (optional, systemd) |
|---|---|---|
| Repo support | Launcher, task registration and Tailscale binding exist | No launcher; the unit in section 5 is new and unrun |
| Start without a person at the keyboard | See W3: a log-on task needs a log-on; a boot-time task needs the user's password stored by Windows | A service starts at boot, no login |
| Crash restart | Task settings in `register-tasks.ps1`: 3 tries, 1 minute apart, then it stops | `Restart=always` |
| Library parse-error dumps | Written under a literal `/tmp` path (`LIBRARY_DUMP_ROOT` in `twscrape_reader.py`); on Windows that resolves to a `\tmp` folder at the root of the current drive, so a cleaner is still needed (W4b) | `PrivateTmp=true` keeps them private; cleaner in the unit |
| Account file permissions | The reader does not check the ACL on Windows (`windows_acl_not_checked` in health); you set it with `icacls` | Reader enforces mode 600 and owner uid |
| Updates | Set active hours so restarts avoid long idle gaps | You choose when to reboot |
| Effort | Lowest: known tools, existing scripts | Higher the first time |

**Recommendation (judgement, not measurement):** stay on Windows. It reuses the existing launcher, Tailscale binding and DPAPI key helper, and nothing forces a move. Choose Linux only if you want boot-time start with no stored Windows password, unlimited restarts and enforced file permissions on a machine you will rarely touch. Whichever you pick: a dedicated non-admin local user (`<service-user>`), full-disk encryption, and never your main accounts or password on this machine.

## 2. Install the X reader (both OS)

Run from `<repo-root>` on the host. The optional group is `xreader` in `api/pyproject.toml`.

```powershell
uv sync --project api --frozen --group xreader
uv run --project api --frozen --group xreader python -m api.data.attention.twscrape_reader --write-curl-record
```

The second command writes the install record for the curl wheel of this platform (flag exists in `twscrape_reader.py`; it refuses unless `uv.lock` holds the table hash). `x_allow_curl_backend` stays `false` unless you decide otherwise (SPEC rule 19, AC53).

**Keep the group installed.** Always pass `--group xreader` to every `uv sync` and `uv run` that touches X. A throwaway-project test of uv 0.12.21 (not this repo, nothing contacted) showed: `uv sync --group xreader` installs the group; a later `uv run --frozen` without the group RETAINED it; `uv run --frozen --exact` REMOVED it; `uv run --frozen --group xreader` reinstalled it. So the existing launcher (`uv run --project api python -m uvicorn ...`, no `--exact`) does not strip the group on that uv version and needs no product fix, but any exact sync without `--group xreader` (including a plain exact `uv sync`) would remove it and X would then refuse to start. Do not set `UV_NO_SYNC` as a workaround.

## 3. Accounts and cookies stay only on this host

Do not copy cookies, account files or the pool directory anywhere else, and do not put them in the repository, a commit, a prompt, a ticket or a log. This guide deliberately contains no cookie example.

- Account files live in a directory outside the repository on an encrypted disk, readable by the service user only. Config keys `x_accounts_db_path` (the directory) and `x_accounts` (labels only, registration order) are in `api/data/attention_queries.json`, collector block. With an empty path X does not start.
- Throwaway accounts only, never the main or a Premium account.
- Cookies: `python -m api.data.attention.twscrape_reader --refresh-cookies <label>` with the cookie string in the environment variable `X_REFRESH_COOKIES` (never on the command line), then remove the variable. It records the refresh time used for the cookie age in the health line. The exact PowerShell sequence (encrypted disk check, `icacls`, per-account upsert, local health check) is the "Owner steps on the 24/7 host" block under heading 10 of `narrative-baskets-xreddit-collector-t212-w8d2_REPORT_27-10-26.md`; follow it there rather than copying it here (add `--group xreader` to its `uv run` lines).
- Local reader health, no request to X: `uv run --project api --frozen --group xreader python -m api.scripts.probe_pc_sources --source xsearch --reader-status` (flag verified in `probe_pc_sources.py`).

Environment the X reader requires (`REQUIRED_ENV` in `twscrape_reader.py`; it refuses to start without them): `TWS_TELEMETRY=0`, `DO_NOT_TRACK=1`, `TWS_LOG_LEVEL=WARNING`, `TWS_RAISE_WHEN_NO_ACCOUNT=1`. No `TWS_PROXY`, `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` and no `TWS_HTTP_BACKEND` may be set in the service environment (only the curl fallback child gets `TWS_HTTP_BACKEND=curl`, set by the code).

## 4. Windows steps (W1-W9)

PowerShell, UNRUN. Elevation is needed only for `powercfg` and `w32tm /resync`.

**W1. User and disk.** Create a local standard user for the collector. Turn on BitLocker (`manage-bde -status C:` should show protection on).

**W2. Deploy config.** Copy `deploy/config.example.psd1` to the real config; set `CacheRoot` if the cache should live on the encrypted disk. The API stays bound to the Tailscale address (`start-api.ps1`), never a public port.

**W3. Auto-start (Annex J item 1) and the log-on question (item 3).** `deploy/register-tasks.ps1` registers `mysite-api` and `mysite-web`, started at log-on of the current user with limited rights, 3 restarts 1 minute apart, no time limit:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\register-tasks.ps1
Get-ScheduledTask -TaskName mysite-api
```

Register it while logged in as the collector user. The Annex J single-task form (`schtasks /Create /TN "AttentionApi" /SC ONLOGON /RL LIMITED /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File <repo-root>\deploy\start-api.ps1"`) is an alternative; use one form, not both, or two API processes fight for the port.

The cookie-based X reader does NOT require an interactive or browser session, so nothing in the collector forces auto-logon. What decides it is how the task starts:

| Option | After a power cut | Trade-off |
|---|---|---|
| Log-on trigger (existing script) without auto-logon | Nothing runs until someone logs on | The worker is down until you log in |
| Log-on trigger plus auto-logon | Runs again by itself | Anyone with physical access gets that user's session; use a dedicated non-admin user, full-disk encryption, nothing of yours on the box (Sysinternals Autologon stores the password as an LSA secret; the plain registry method leaves it readable). Never your main Windows password |
| Task at start-up set to run whether the user is logged on or not | Runs by itself, no session | Windows stores the user's password for the task; the task runs in a non-interactive session; `start-api.ps1` waits for Tailscale and reads a DPAPI-protected key, and neither is tested in that mode here; the existing script registers only the log-on form, so you would register this task yourself |

Pick one; all three are the owner's choice.

**W4. Enable the worker.** Set the variables for the collector user so the task inherits them (read at process start; log on again or reboot after `setx`):

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

`powershell -NoProfile -ExecutionPolicy Bypass -File deploy\start-api.ps1 -DryRun` prints host, port, CORS, cache and watchlist but not the worker variables; confirm those with `Get-ChildItem Env:SCREENER_ATTENTION_PC_WORKER` in a new session.

**W4b. Library dump cleanup.** The library writes parse-error dumps (raw tweet JSON) under a literal `/tmp` and never removes them. On Windows that path is drive-rooted, so dumps appear in `\tmp` at the root of the drive the API process runs on [INFERENCE from `pathlib`: `PureWindowsPath('/tmp')` has root `\` and no drive; the dump itself is not observed]. Check for it and clear only `twscrape*` entries inside that folder, for example weekly:

```powershell
Get-ChildItem "<drive>:\tmp" -Filter 'twscrape*' -ErrorAction SilentlyContinue
Get-ChildItem "<drive>:\tmp" -Filter 'twscrape*' -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
```

Review the listing before running the second line. The accounts directory must never be under `<drive>:\tmp`.

**W5. No sleep, no hibernate, lid (item 2).**

```powershell
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0
powercfg /setactive SCHEME_CURRENT
```

Keep the laptop on AC; the `-dc` equivalents are your choice. Set Windows Update active hours so restarts avoid long idle gaps.

**W6. Clock (item 5).** Day windows are UTC; a large clock error breaks them. The health line does NOT report clock sync (its `clock_sync_age_seconds` is always null), so check yourself:

```powershell
w32tm /query /status
w32tm /resync
```

**W7. Log and disk rotation (item 4).** The worker log rotates by itself (W4 variables). The cache is git-ignored and pruned by retention config (`x_raw_retention_days`, ledger 400 days by default). Free space is in the health line (`free_disk_bytes`, section 6).

**W8. Restart catch-up (item 6).** Automatic: after a restart or power cut the worker resumes through `_behind` at the configured pace, missing is never 0, a unit cut by a power loss is retried.

**W9. Remote viewing (item 7) and UPS (item 8).** Keep the Tailscale binding of `start-api.ps1`; view over Tailscale or a remote-desktop tool; no public port, no router forward. A small UPS is recommended, not required.

## 5. Linux steps (optional, L1-L8)

UNRUN examples for a systemd distribution; `sudo` where shown. No Linux launcher exists in the repo, so the unit is new.

**L1. User and disk.** Dedicated `<service-user>`; repository, cache and accounts directory on a LUKS volume; accounts directory `chmod 700` (the reader enforces file mode 600 and owner uid and refuses otherwise).

**L2. Install** as `<service-user>` from `<repo-root>` (section 2).

**L3. Service unit** `/etc/systemd/system/attention-api.service` (adapt paths; bind stays loopback):

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
ExecStartPre=/usr/bin/find /tmp -mindepth 1 -maxdepth 1 -name 'twscrape*' -exec rm -rf -- {} +
ExecStart=<uv-path> run --project api --frozen --group xreader python -m uvicorn api.main:app --host 127.0.0.1 --port 8000

[Install]
WantedBy=multi-user.target
```

Notes: the cleaner uses `rm -rf` because `find -delete` fails with "Directory not empty" on a nonempty `twscrape*` directory (observed in a throwaway tree under Git Bash; not on Linux/systemd). It is bounded to direct children of `/tmp` named `twscrape*`; with `PrivateTmp=true` that `/tmp` is the service's private one. `SCREENER_CORS_ORIGINS`, `SCREENER_WATCHLIST_PATH` and `LSE_API_KEY` are the other app variables `start-api.ps1` supplies on Windows; supply them on Linux with `Environment=` lines or an `EnvironmentFile=` readable only by `<service-user>`; never write a key into this file.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now attention-api.service
systemctl status attention-api.service
journalctl -u attention-api.service -n 50 --no-pager
```

**L4. No sleep, lid ignored.**

```bash
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
# in /etc/systemd/logind.conf set:  HandleLidSwitch=ignore  (and HandleLidSwitchExternalPower=ignore)
```

Then reboot (restarting `systemd-logind` can end sessions).

**L5. Clock.** `timedatectl status` (expect "System clock synchronized: yes"); `sudo timedatectl set-ntp true`.

**L6. Logs and disk.** Worker log rotates itself (L3 variables); cap the journal with `SystemMaxUse=` in `/etc/systemd/journald.conf` or use logrotate. Free space is in the health line.

**L7. Restart catch-up, auto-login.** Automatic; no auto-login needed (cookies, no browser session).

**L8. Remote viewing and UPS.** Bind stays `127.0.0.1`; use a VPN or `ssh -L <local-port>:127.0.0.1:8000 <host>`; no public port. UPS as in W9.

## 6. Owner probe P-W1 and reading the health line

Health reads files only: no provider is called (`get_sources` in `api/routers/discovery.py`). P-W1, replacing the plan's nonexistent `probe_pc_sources ... --status` (that script has no `--status` flag; Reddit `--stream-status` prints "not built yet (W8c2)"):

1. Start the API with the worker flag for one hour (on Windows via the task above, or manually in a PowerShell session: `$env:SCREENER_ATTENTION_PC_WORKER="1"; uv run --project api --frozen --group xreader python -m uvicorn api.main:app --host <tailscale-or-loopback-ip> --port <api-port>`).
2. Read the health line from the route `GET /api/narrative/sources` (health fields below exist once the W8e2 code half, PR #195, is merged):

```powershell
$r = Invoke-RestMethod "http://<api-host>:<api-port>/api/narrative/sources"
$r.sources | Where-Object { $_.health } | ForEach-Object { $_.id; $_.health | ConvertTo-Json -Depth 5 }
```

3. Read the end of the worker log: `Get-Content "<cache>\attention\_logs\attention_pc.log" -Tail 50`.

Pass: the request counts and the spacing of unit times stay within the caps and pace locked in the SPEC. A summary alone does not prove that: compare the unit times in the log with the configured spacing and the counts with the budgets.

`sources[].health` (present only for worker sources with state; absent otherwise; an unknown value is `null`, never 0; X days recorded before this change show unknown):

| Field | Meaning | Act when |
|---|---|---|
| `last_unit_at` | UTC time of the last unit | far older than `expected_gap_s` |
| `paused`, `pause_reason`, `pause_until` | pause and cause; `pause_until` null while paused means owner action needed or state unreadable | read the reason; owner-action pauses need a cookie refresh or a clear |
| `collection_day`, `attempted`, `fetched` | distinct coin-days attempted and stored on the collection day; canaries excluded | fetched far below attempted |
| `completeness_day`, `completeness_attempted`, `completeness_fetched`, `missing`, `missing_reasons`, `capped`, `newest_age_hours` | completeness for the target day and the age of the newest collection | growing `missing`; a missing day is never 0 |
| `completeness` | the same as one text line | |
| `mode` | `baseline` or `degraded` | degraded on a 24/7 host: the host was not up all day |
| `expected_gap_s`, `stale` | the worker's persisted gap; stale when no unit for more than 2 x that gap | stale: check service, clock, power |
| `budget_used`, `effective_budget`, `budget_spent` | today's use (X posts loaded, Reddit requests; includes canaries) against the effective budget | persistently halved budget |
| `accounts_active`, `accounts_total`, `accounts[]` (`label`, `state`, `reason`, `last_used`, `cookie_age_days`) | X pool; state active, locked, inactive or suspect | high cookie age or inactive: refresh cookies (section 3) |
| `free_disk_bytes` | free space on the cache disk | low |
| `clock_sync_age_seconds` | always null: this worker persists no clock-sync evidence | use `w32tm /query /status` or `timedatectl status` |

## 7. Item map (Annex J to this guide)

1 auto-start: W3, L3. 2 no sleep and lid: W5, L4. 3 auto-login: W3 (optional; not required by the cookie reader). 4 disk and log rotation: W7, L6, section 0. 5 clock: W6, L5. 6 restart catch-up: W8, L7. 7 remote access and health line: W9, L8, section 6. 8 UPS: W9, L8. 9 accounts and secrets: section 3. 10 interim: until the laptop exists the owner's PC runs in degraded mode; nothing else changes. 11 Linux: section 5.
