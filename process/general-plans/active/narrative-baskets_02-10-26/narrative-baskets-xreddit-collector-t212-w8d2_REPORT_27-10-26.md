# T212 W8d2: X reader, twscrape wrapper (REPORT, 27-10-26)

## 1 Task ID
T212, slice W8d2 "X reader: twscrape wrapper, pinned optional dependency group". Branch `claude/t212-w8d2-x-reader` from main `e1305f8`. Owner approval in the envelope (27-10-26, "Approve edit, accounts ready") for `api/pyproject.toml` and `api/uv.lock`, limited to the optional group `xreader`.

## 2 Outcome
DONE (draft PR, not merged). Every gate is green. There are six open questions for the planner (heading 9). Each one is an implementation choice already made and stated, not a blocker.

## 3 Summary
- `api/data/attention/twscrape_reader.py` wraps twscrape behind the W8d1 `XReader`:
  - It imports twscrape lazily, inside `load_library` only, and only after the environment guard has passed.
  - Design A: one SQLite file and one `API(db, raise_when_no_account=True, wait_timeout=0)` per account. It never passes `debug`, a proxy or a user agent.
  - Start refuses with reason codes, never values. It checks the env guard, the configured pin against the code pin, the installed `direct_url.json` commit id against the pinned SHA (the version string is not checked), the accounts directory (absolute, outside the repository, owner-only mode and owner uid on POSIX), the pool size against `x_pool_max`, and unknown or missing account files.
  - Start cleans the `/tmp/twscrape*` dumps.
  - Pages come one at a time from `search_raw`. The reader keeps the bottom cursor and reads entry times from the tweet ids (snowflakes), truncated to whole seconds. Retries are derived from drops in `x-rate-limit-remaining`.
  - Exceptions map to W8d1 failure kinds. `XClIdGen` 404s become `not_found`. Messages are dropped.
  - Cookie refresh is `pool.add_account_cookies`. The cookies come from the env var `X_REFRESH_COOKIES`. The refresh time is recorded for the cookie age shown in health.
  - The curl fallback runs in a child process (`python -m … --curl-fallback`). Only that child's environment has `TWS_HTTP_BACKEND=curl`. The child reads one page from the cursor where the default backend stopped.
  - The curl_cffi gate requires exact name, version 0.16.3, the wheel tag for the detected platform, and an install record whose hash equals the table entry and the `uv.lock` entry. An unknown platform turns the fallback off, and the health line says so.
- `api/pyproject.toml` gets the group `xreader`, plus `[tool.uv] no-build-package = ["curl-cffi"]` (wheels only) and `build-constraint-dependencies = ["hatchling==1.32.4"]`. I regenerated `api/uv.lock` with `uv lock` (uv 0.11.32). It adds 11 packages and changes no version that was already locked.
- Config keys in `attention_queries.json` and `web_queries.py`: `x_accounts_db_path` (default empty, so X does not start), `x_pinned_commit`, `x_pinned_version`, `x_accounts` (labels in registration order, default empty) and `x_pool_max` (default 3). `x_window_syntax` stays `since_time`, which is the epoch form P-X9 showed X honours.
- `probe_pc_sources.py --source xsearch --reader-status` prints counts, labels, states, codes and ISO times only. Any other value is printed as `redacted`. It reads local state only and sends no request.
- I checked the wrapper against the real pinned library in a throwaway scratch venv, with no request to X (heading 8).

## 4 Files changed
| File | Change |
|---|---|
| `api/data/attention/twscrape_reader.py` | new (the wrapper, start, health, fallback child, cookie refresh, CLI) |
| `api/pyproject.toml` | optional group `xreader` and `[tool.uv]` (approved) |
| `api/uv.lock` | regenerated with `uv lock` (approved) |
| `api/data/attention_queries.json`, `api/data/attention/web_queries.py` | five config keys and their validation |
| `api/scripts/probe_pc_sources.py` | `--source xsearch --reader-status` |
| `api/tests/data/attention/test_twscrape_reader.py` | new, 40 tests |
| `api/tests/tooling_guards/test_x_reader_guards.py` | new, 13 tests |
| `api/tests/tooling_guards/test_pc_collector_guards.py` | W8d1 pin guard updated: twscrape allowed only in `xreader` |
| this report | new |

Group pins: `twscrape @ git+https://github.com/vladkens/twscrape@63f61a518e576ea5c132f1156c03dda0520d76c1`, `aiosqlite==0.22.1`, `beautifulsoup4==4.15.0`, `soupsieve==3.0.3`, `fake-useragent==2.2.0`, `loguru==0.7.3`, `py-machineid==1.0.0`, `pyotp==2.10.0`, `curl-cffi==0.16.3`. `uv.lock` holds the sha256 of every wheel and sdist, the git source `…?rev=<SHA>#<SHA>`, and the three curl wheels at the W8a2 hashes. I re-read those hashes from PyPI JSON on 27-10-26 and they are equal.

## 5 Commits
- `18af83d` test(x): red tests (both new test files; collection fails without the module).
- `891c86d` feat(x): wrapper, group, lock, config, probe, W8d1 guard update.
- report commit (this file).

## 6 Tests run
| Gate | main `e1305f8` | branch |
|---|---|---|
| `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention api/tests/scripts api/tests/tooling_guards -q` | 1378 passed | 1431 passed (+53) |
| `UV_FROZEN=1 uv run --project api pytest api -q` | 2750 passed, 1 skipped, 5 deselected | 2803 passed, 1 skipped, 5 deselected |
| `UV_FROZEN=1 uv sync --project api --frozen` (no group) | ok | ok; `find_spec` twscrape and curl_cffi are None in the default env |
| ruff on touched `.py` files | clean | clean |
| `git diff --check`, V5 secret scan, banned-name grep | n/a | print nothing (the banned names exist only as split strings) |
| no network import outside the lazy module | n/a | guard tests: module level has no network or library import; `subprocess` only in `run_child`; the library only in `load_library` |
| file set | n/a | heading 4 (beyond the envelope list: `web_queries.py`, `test_pc_collector_guards.py`; see heading 8) |

Red first: `18af83d` fails at collection (`ModuleNotFoundError`); `891c86d` passes. All 46 PLAN red-first names exist, plus 7 extra tests.

Mutation check: 39 hand-written mutants on the guards and the decision wiring (env guard, pin, identity url and commit, raising switches, flag, curl name, version, tag, hash and platform, lock-hash check, child backend env, proxy strip, exception kinds, accounts path, permissions, uid, pool bounds, unknown and missing files, dump cleaner, retry derivation, cursor to child, short SHA, near-names, banned names, exact pins, refresh label, env and chmod, missing-row mapping, naive locks, status redaction, refresh message leak). The first run killed 37 and 2 survived: "config pin not checked at start" and "status words not redacted". I added assertions for both and re-ran them: both now killed. Final result: 39 of 39 killed, no survivors.

## 7 Tests NOT run
- No request to X (envelope: none from the sandbox). The real `search_raw`, the Cloudflare and HTML block path, and the curl child on a real block are owner-side (P-X9 re-run, heading 10).
- The `run_child` subprocess path is not run in tests. The fallback is tested through an injected child callable. The child's own `_child` and `main` are not run against a real block.
- Windows paths and ACLs: the code skips the mode-bit check on Windows and reports `windows_acl_not_checked`.

## 8 Deviations
1. Files beyond the envelope list:
   - `web_queries.py`: the collector block refuses unknown keys, so new config keys need its validation.
   - `test_pc_collector_guards.py`: the W8d1 guard asserted "twscrape not in pyproject/uv.lock". Its own comment said "the project files are W8d2's". It now asserts twscrape appears only in `xreader`.
2. Added config keys `x_accounts` and `x_pool_max`. The envelope did not list them, but SPEC AC47 (pool size bounds, unknown label refused) needs a label list and a maximum.
3. Shared packages keep the main lock's versions rather than the W8a2 report 9.1 versions:
   - certifi 2026.6.17 (W8a2: 2026.10.19)
   - idna 3.18 (3.20)
   - cffi 2.0.0 (2.1.1)
   - pycparser 3.0 (3.11)
   - httpx, httpcore, h11 and anyio are equal.

   Pinning the W8a2 versions would have changed the main environment ("no other dependency change"). They are still hash-pinned in `uv.lock`.

   soupsieve is pinned at 3.0.3 (W8a2) instead of the resolver's newer 3.0.4. `winregistry 2.1.5` (Windows only, from py-machineid) and `win32-setctime 1.2.1` (Windows only, from loguru) came in transitively. W8a2 did not list either.
4. Hash pinning for curl_cffi: pyproject cannot hold hashes, but `uv.lock` does, and uv checks them at install. `no-build-package` forbids the sdist. uv does not record which wheel it installed, so `--write-curl-record` writes the record from the detected platform. It refuses unless `uv.lock` holds the table's hash for that wheel. Startup also checks the installed `WHEEL` tag and the version. This binds the table, the lock and the installed wheel. It does not re-hash the installed files.
5. A smoke check against the REAL pinned library, in a scratchpad venv built with `uv sync --frozen --group xreader`. There was no request to X, and the tests still use only the fake module. It checked:
   - identity: commit match
   - curl_status: `ok` on manylinux
   - cookie upsert: the file is created with mode 600
   - `pool_row` and the exception mapping
   - the library's own mocked search page (`tests/mocked-data/raw_search.json`): 20 entries, 20 parsed, and snowflake times equal to `created_at` in all 20 after second truncation (fixed in this slice)
   - `curl_cffi` is not imported in the main process
   - `twscrape.telemetry` IS imported, by the library's own `queue_client`, not by us. `capture` returns early under `TWS_TELEMETRY=0`.
6. `SETUP_REQUESTS_ESTIMATE = 3` is the transaction-id setup overhead per process and account: an estimate from W8a2 9.1, not measured.
7. I made small fixes to the red tests in the green commit (fixture `parents=True`, PcSource constructor, two units for "zero usable accounts", proxy variables cleared for the probe test). The test names are unchanged.

## 9 Blockers
None. Open questions for the planner:
- **Q1** Do you accept the shared-package versions and the two Windows-only transitives in heading 8.3, or do you want W8a2-version pins (which change the main environment)?
- **Q2** Do you accept the curl_cffi hash binding in heading 8.4 as the rule 19(h) implementation?
- **Q3** Windows ACL: should the code stay at "not checked, said in health", with the owner setting the ACL using `icacls` (heading 10)? Or do you want a `icacls` parse check (more code, fragile)?
- **Q4** Do you accept the new config keys `x_accounts` and `x_pool_max` (SPEC AC47 names `x_pool_size`; the size here is `len(x_accounts)`)?
- **Q5** Retries are derived from drops in `x-rate-limit-remaining` between pages of one account. That also counts the library's silently skipped empty pages, and it is exact only while no other process uses that account. OK?
- **Q6** The envelope says `x_window_syntax` default "epoch". The existing value `since_time` is that form, and I did not rename it, because renaming would change W8d1. OK?

## 10 Follow-up
**Deferred (not built):**
- **W8d3, stratified 4-slice daily sampling.** It needs a SPEC amendment and changes to `x_window` and `x_density`. `window_query(terms, start=, end=, lang=)` already takes an explicit [start, end) in epoch seconds, so slices can be added later without changing the reader.
- **W8e, worker wiring.** It owns starting the X process with `service_env` (private temporary directory), running `start`, the dump cleaner per run, the canary and units with `XStart.fallback`, the health line, and per-account real screen names for raw-page scrubbing (`account_names`).

**Owner steps on the 24/7 host (PowerShell).** The drive `E:`, the user `xsvc`, the repo path and the cookie files are examples to adapt. Never use the main or Premium account.

```powershell
# 1. Encrypted disk outside the repository, access for the service user and SYSTEM only
manage-bde -status E:            # must show "Protection Status: Protection On"
New-Item -ItemType Directory -Force E:\xpool | Out-Null
icacls E:\xpool /inheritance:r /grant:r "xsvc:(OI)(CI)F" "SYSTEM:(OI)(CI)F"
# 2. Config (api\data\attention_queries.json, collector block): "x_accounts_db_path": "E:\\xpool",
#    "x_accounts": ["acct1", "acct2"]   (labels only; x_allow_curl_backend stays false unless you decide otherwise)
# 3. Install the pinned group (hashes from uv.lock; curl-cffi wheel only)
cd C:\srv\psychic-train
uv sync --project api --frozen --group xreader
# 4. Environment for every X command (the reader refuses to start otherwise)
$env:TWS_TELEMETRY="0"; $env:DO_NOT_TRACK="1"; $env:TWS_LOG_LEVEL="WARNING"; $env:TWS_RAISE_WHEN_NO_ACCOUNT="1"
foreach ($v in "TWS_PROXY","HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","TWS_HTTP_BACKEND") { Remove-Item "Env:$v" -ErrorAction SilentlyContinue }
uv run --project api --frozen python -m api.data.attention.twscrape_reader --write-curl-record   # prints status=ok platform=win_amd64
# 5. Cookies per account (upsert; also the refresh procedure later); never on the command line
foreach ($l in "acct1","acct2") {
  $env:X_REFRESH_COOKIES=(Get-Content "C:\secrets\x_$l.txt" -Raw).Trim()
  uv run --project api --frozen python -m api.data.attention.twscrape_reader --refresh-cookies $l
  Remove-Item Env:X_REFRESH_COOKIES }
icacls E:\xpool\* /inheritance:r /grant:r "xsvc:F" "SYSTEM:F"
# 6. Health (local only): expect commit_match=true env_ok=true accounts_path=ok, both labels active
uv run --project api --frozen python -m api.scripts.probe_pc_sources --source xsearch --reader-status
# 7. P-X9 re-run with the INSTALLED pinned build (same script C:\vet\probe_x9.py, repo environment instead of the vet venv)
foreach ($l in "acct1","acct2") { $env:X_PROBE_LABEL=$l; $env:X_PROBE_COOKIES=(Get-Content "C:\secrets\x_$l.txt" -Raw).Trim(); uv run --project api --frozen python C:\vet\probe_x9.py }
Remove-Item Env:X_PROBE_COOKIES
```

Pass for step 7: the same per-page header numbers and the epoch summary lines as P-X9 of 27-10-26. Cookie refresh later means repeating step 5 for one label. Health then shows `cookie_age_days=0`.

On Linux, step 1 is a LUKS volume with `chmod 700` on the directory. The reader enforces mode 600 on files, owner uid, and `PrivateTmp=yes` in the systemd unit. Steps 3 to 7 are the same with `export` and `unset`.

## 11 Context cost
Read: CLAUDE.md; the envelope; the PLAN on `origin/claude/t163-reddit-engagement-spec` (W8a2, W8d1, W8d2 and sections 6 to 8); SPEC rules 17 to 20, Annex A.1b and AC41 to AC55; the W8a2 report (sections 4, 9 and 10); the W8d1 modules `x_reader.py`, `x_pool.py` (parts), `x_raw.py`, `x_window.py` and `x_filters.py` (types); `web_queries.py`; `probe_pc_sources.py`; `test_pc_collector_guards.py`; `_common.py`; `pyproject.toml`; and the source text of the installed pinned twscrape, which I read but did not run except for the smoke check. I opened no other on-demand doc.
