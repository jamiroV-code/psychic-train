# W8e2 server host guide (REPORT, 30-10-26)

## 1 Task ID

W8e2 docs half (server host guide), branch `claude/w8e2-host-guide`, based on `origin/main` 0d669f4f. Worker `W8e2Guide`.

## 2 Outcome

Done. One guide written; no code touched. Nothing was run (every command in the guide is marked unrun). The OS choice stays with the owner, with a recommendation.

## 3 Summary

`narrative-baskets-server-host-guide_30-10-26.md` turns SPEC Annex J items 1-11 into owner steps for Windows (W1-W9) and Linux (L1-L9): auto-start, powercfg standby and hibernate, lid action, auto-logon trade-off, w32tm, log and disk rotation, restart catch-up, remote viewing without a public port, UPS; and systemd with `Restart=always`, `PrivateTmp=true`, the TWS environment variables, masked sleep targets, `HandleLidSwitch=ignore`, `timedatectl`. It also covers enabling `SCREENER_ATTENTION_PC_WORKER=1` with the two optional log variables, the `xreader` install, accounts and cookies (pointers only, no secrets), an OS decision table with a recommendation (Linux for unattended weeks, Windows to reuse `deploy/`), probe P-W1, and a table for reading the health line once the code half lands.

Every cited name was checked in code: `SCREENER_ATTENTION_PC_WORKER`, `SCREENER_ATTENTION_PC_LOG_MAX_BYTES` (default 5000000), `SCREENER_ATTENTION_PC_LOG_FILES` (default 5) in `attention_pc_refresh.py`; `--refresh-cookies`, `--write-curl-record`, `X_REFRESH_COOKIES`, the four `REQUIRED_ENV` names in `api/data/attention/twscrape_reader.py`; `--reader-status` in `probe_pc_sources.py`; `SCREENER_CACHE_ROOT`, `-DryRun`, Tailscale binding in `deploy/start-api.ps1`; task settings in `deploy/register-tasks.ps1`.

## 4 Files changed

In `process/general-plans/active/narrative-baskets_02-10-26/`: `narrative-baskets-server-host-guide_30-10-26.md` (new), this report (new).

## 5 Commits

One docs commit on `claude/w8e2-host-guide`; draft PR opened (see Main's hand-off).

## 6 Tests run

Doc checks by reading and grep only (no code gates apply): flags and variables verified against the code files above; secret and real-path scan of the guide; banned-name grep.

## 7 Tests NOT run

No command in the guide was executed (powercfg, schtasks, setx, w32tm, systemd, timedatectl, uv). Not proven: the systemd unit, the `ExecStartPre` cleaner, the DPAPI helper under a "run whether logged on or not" task, auto-logon behaviour, the Linux paths of `start`. P-W1 not run.

## 8 Deviations

- The PLAN's P-W1 status command `probe_pc_sources --source reddit --status` does not exist: the probe has no `--status` flag, and Reddit `--stream-status` prints "not built yet (W8c2)". The guide says so and names the log file as the interim read. The plan text was not edited (out of file set).
- The existing `deploy/register-tasks.ps1` is cited for Windows instead of only the Annex J one-line `schtasks` example; both are given, with a warning not to use both.
- The health table is written from SPEC AC38, AC39, AC47, AC52; the code half is not merged, so field names may differ and the guide says to re-check them.

## 9 Blockers

None for this half. The owner chooses the OS and auto-logon method.

## 10 Follow-up

- After the W8e2 code half merges, correct the section 7 table against `sources.py` and `models/discovery.py`.
- Planner decision: add a `--status` mode to `probe_pc_sources.py` or amend P-W1 in the plan.
- Owner: pick the OS, run the steps, run P-W1.

## 11 Context cost

Read: the envelope, PLAN W8e and W8e2, SPEC Annex J and AC38, AC39, AC47, AC52, the W8d2 report heading 10, `deploy/start-api.ps1`, `deploy/register-tasks.ps1`, `config.example.psd1`, and greps of `attention_pc_refresh.py`, `twscrape_reader.py`, `probe_pc_sources.py`. Small.
