# S-Cookie-X slice report (07-11-26)

## 1. Status
The slice is CODE-COMPLETE on fixtures. It used a fake twscrape library, fake session results, fake runtimes and a fake browser host. No browser was launched and no request was sent.
It is not LIVE-READY. Real X harvest stays refused until BG-1..BG-3 pass, PX6 is run and one owner `--interactive` login is done per profile.
The feature is off by default: `x_cookie_harvest_enabled` is `false`, so the worker never calls the hook and the status shows no `harvest` block.
Work is on branch `claude/b2-validate` and has not been pushed.

## 2. Scope executed
This slice covers plan §S-Cookie-X CX-1..CX-3, the three harvest pool keys (contract G literals) and the X `DayGuard`. It also covers the X `RouteProvider` over the B2 runtime (CK-6), the unit-boundary trigger, the `session_check` facts call site, the owner CLI and its guard-chain link.

## 3. Changed paths
- `api/data/attention/x_pool.py`:
  - Pool keys: `HARVEST_ACCOUNT_DEFAULTS`, `HARVEST_STATES` and `HARVEST_REASONS`, with the keys added to `ACCOUNT_KEYS`, fresh-account defaults, `setdefault` migration and strict validation.
  - Methods: `try_claim`, `harvest_due` and `note_harvest`.
  - Canary: `_canary_pending`, which a harvest also sets.
  - Status: `harvest_status` and the health `harvest` block.
- `api/data/attention/twscrape_reader.py`:
  - Upsert and age helpers: `_upsert_account`, the single upsert with reason-checked `reactivate`, and `_record_age`. `refresh_cookies` uses both and gains `reactivate=`.
  - Harvest wiring: `XRouteProvider`, `harvest_cookie_string`, `harvest_account`, `session_check` and `harvest_cli`.
  - `XStart`: `_rebuild`, which evicts the reader and bootstrap cache and is shared with `reconcile`, and `harvest`.
  - CLI: `--harvest-cookies LABEL [--interactive]`. The module docstring is updated.
- `api/data/attention_pc_refresh.py`: an 8-line hook at the X unit boundary, run after reconcile and the query boundary and before the canary.
- Tests:
  - New file `api/tests/data/attention/test_x_harvest.py` (24 tests).
  - One new test in `api/tests/data/test_attention_pc_refresh.py`.
  - In `api/tests/tooling_guards/test_x_reader_guards.py`, the cookie-flag guard now expects `--refresh-cookies` and `--harvest-cookies`, both with `metavar=LABEL`.

## 4. Interfaces
- `XPool.try_claim("x", label, day) -> bool` is the atomic X day guard. It holds the pool state lock, so the worker and the CLI share it.
- `XPool.harvest_due(ages, *, enabled, refresh_age_days) -> [label]`.
- `XPool.note_harvest(label, state, reason)`.
- `XRouteProvider(runtime).admitted_route("x", label) -> AdmittedRoute | "proxy_not_admitted"`. The `admission()` snapshot is re-read on every relay CONNECT and returns `None` once the admission is withdrawn or expires.
- `harvest_account(label, *, config, pool, check, upsert, evict, mode) -> (state, reason)`.
- `XStart.harvest(config, pool, now, *, check=None) -> {label: state}`.
- Health: `accounts[i].harvest = {state, reason, last_at}`, shown only when the switch is on. This matches `XAccountHarvest`. `last_at` is the claimed UTC day.
- Facts: `session_check{source=xsearch_web, account, result_class, cookie_age_class}`.

## 5. Tests run
- **Red first (run):** I ran the new file, the guard file and the worker test together with `-x`. It stopped at the first failure: `AttributeError: x_pool has no attribute HARVEST_ACCOUNT_DEFAULTS`. The guard and worker tests depend on the missing flag and hook, but I did not watch each one fail on its own (`-x` stopped first).
- **Green:** `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/tests/data/attention/test_x_harvest.py -q -rs` gave 24 passed.
- **Broader targeted run:** `test_x_harvest.py`, `test_x_pool.py`, `test_twscrape_reader.py`, `test_identity_transport.py`, `test_x_b3_integration.py`, `test_browser_session.py`, `test_x_reader_guards.py`, `test_pc_collector_guards.py`, the three `test_attention_pc_refresh*.py` files, `test_sources_health.py` and `test_probe_executors.py` gave **502 passed, 1 skipped** (the skip is POSIX mode bits) in 578 s.

## 6. Acceptance mapping
- **AC2:**
  - The login-required trigger and the age trigger are both covered.
  - The DB upsert uses exactly one validated `auth_token`/`ct0` pair; conflicting duplicates are refused.
  - The reader is rebuilt after the upsert (a second `API` opens on the account file), so the next real read uses the new cookie.
  - `cookie_ages` is updated.
- **AC3:**
  - A logged-out or challenge result leaves the account `needs_owner` and paused `x_login_required`.
  - There is no second attempt the same day, or on later days until the owner acts.
  - The day guard survives a restart and is shared by the CLI and the worker.
  - The other account is unaffected.
- **AC17:**
  - The secret scan of the state file, health, logs, facts and `cookie_ages` is clean.
  - The CLI prints codes only.

## 7. Data verification
Fixtures write only under pytest tmp and the isolated cache. No cookie value reaches `x_pool.json`, health, the pool log, facts or `cookie_ages.json` (asserted).

## 8. Error handling
- A harvest never stops collection: the worker hook logs the exception class only.
- Upsert failures become `failed/refresh_failed`, malformed cookies `failed/cookie_invalid`, and gate refusals `refused/<CK-7 reason>`.
- Unknown reason codes are stored as `session_failed`.
- A suspended account is never checked or revived, and its `note_harvest("ok")` leaves it suspended.

## 9. Deviations
- **CX-3 order.** A successful harvest reactivates an account that was `x_login_required` immediately, but sets `last_canary=None`. That makes `canary_passed_today()` false and puts the account first in `canary_accounts()`, so its canary runs at the same boundary before any unit. A failing canary pauses or flags it through the existing canary path. I chose this so the account can take part in the canary, because `usable()` excludes inactive accounts.
- **Hand-off scope.** Only `auth_token` and `ct0` are handed to the upsert. Other X cookies are ignored, and values must be alphanumeric, 16–512 characters.
- **`needs_owner` stops automatic triggers.** Automatic triggers stay stopped until an owner-initiated harvest succeeds. "No second attempt" is read as lasting beyond the day.
- **`--interactive` needs `--harvest-cookies`.** It is an argparse error otherwise. An owner `--interactive` harvest works with the switch off. An automatic harvest, from the CLI or the worker, needs the switch.
- **S-Cookie-C's own CLI is unchanged.** `browser_session --site x` without `--interactive`/`--probe` still answers `day_guard_unavailable`, because I don't own that file. The supported X owner entry point is `twscrape_reader --harvest-cookies`.
- **Worker upsert.** The worker upserts through the account's live reader (its installed adapter and loop) rather than `refresh_cookies`, so the process never installs a second identity adapter. Both paths share `_upsert_account` (the guard counts one `add_account_cookies`) and `_record_age`.

## 10. Gate honesty
BG-1 FAIL, BG-2 pending and BG-3 NOT-MET, so real use returns `refused` with the matching reason and records `harvest_state=refused`. PX6 has not been exercised, and the real two-account transport has not been tested.

## 11. Next
- S-Report reads `session_check` facts. S-OpsDoctor can show `harvest` health and recommend the switch.
- S-OpsDeploy README fragment, at most 40 lines: "X session harvest: `uv run --project api --frozen --group xreader python -m api.data.attention.twscrape_reader --harvest-cookies <label> --interactive --queries <abs config>` once per profile after `browser_session --init-profile`; then enable `x_cookie_harvest_enabled` (optionally `x_cookie_refresh_age_days`)."
- Rollback (contract G, stage 8): strip `harvest_day`, `harvest_state` and `harvest_reason` from every account and revert these paths.
