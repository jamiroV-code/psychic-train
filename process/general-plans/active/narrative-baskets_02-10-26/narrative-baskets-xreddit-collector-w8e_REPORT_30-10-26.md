# W8e: PC worker wiring (REPORT, 30-10-26)

## 1 Task ID

W8e worker wiring (PLAN `narrative-baskets-xreddit-collector_PLAN_21-10-26.md`, section "W8e: worker wiring", with the T163, T135 and T133 additions; SPEC rules 1-3, 6, 7, 9, 10, 15, 16; AC8, AC10, AC21, AC22, AC24, AC37, AC38, AC40). Branch `claude/w8e-pc-worker`, based on `origin/main` 4b3f70a9.

## 2 Outcome

done (with the deviations in heading 8; the owner probe P-W1 and live provider behaviour are not run)

## 3 Summary

- New `api/data/attention_pc_refresh.py`: the PC-side worker modelled on `equities_refresh.py` (`PASS_LOCKS`, `_behind` start, `start_from_env`, `stop_worker`, `current_worker`). Off unless `SCREENER_ATTENTION_PC_WORKER=1` (exactly `1`); no test, conftest or workflow sets it.
- Two streams on two threads (`attention-pc-xsearch_web`, `attention-pc-reddit_web`), each with its own lock. X runs only through the `XReader` seam: `twscrape_reader.start` is imported lazily inside the default `x_start`, and the canary and units are `x_pool.run_daily_canary` and `x_pool.run_unit`. Reddit runs `reddit_web.run_pass`.
- Schedule: a source with work is due 20 s after start, and never earlier than `x_query_delay_min_s` (or the Reddit minimum) after its last unit, including after a restart. A source that is up to date, paused or out of budget waits until 00:00 UTC + 20 s. A pass that raised is retried after 600 s. Unreadable state pauses the source, keeps the file and is re-checked after 3600 s.
- Modes: BASELINE when the worker has been up since before 00:00 UTC of the current day, else DEGRADED. A restart is therefore degraded for the rest of that UTC day. BASELINE spreads the X units over the day (24 h / (effective budget / `x_sample_n`), 72 min at 800/40) and uses the Reddit budget 250. DEGRADED uses the configured 3-6 min and 60-120 s pace and the Reddit budget 150.
- Work: the X queue is yesterday first, ordered for rotation (oldest newest-stored day first), then `x_backfill_days`. It is rebuilt from the store before every unit, so an unfinished coin-day stays queued. The Reddit queue is yesterday plus 5 backfill days (what `t=week` reaches). X runs only while its budget lasts. Values are stored only through `web_evidence.commit_day`. A unit that has started reads all its pages. Nothing runs while the host is off.
- Unattended weeks: a rotating log `<cache>/attention/_logs/attention_pc.log` (size and count from environment variables), `x_raw.prune` after each X pass, and pruning of Reddit ledger partitions, canary files and completeness files after `ledger_retention_days` (default 400). No in-memory structure grows with the number of days. Clocks are UTC; a naive clock is refused.
- `api/main.py`: the lifespan starts the worker after the equities worker and stops it last, in nested `finally` blocks.
- 29 tests in `api/tests/data/test_attention_pc_refresh.py`: all 27 PLAN names plus `test_corrupt_state_pauses_source_and_keeps_file` and `test_naive_clock_refused`. All pass.

## 4 Files changed

- `api/data/attention_pc_refresh.py` (new, 700 lines)
- `api/main.py` (lifespan start/stop, import, docstring paragraph)
- `api/tests/data/test_attention_pc_refresh.py` (new, 728 lines; the inherited uncommitted draft, reviewed and fixed, see heading 8)
- this report

`git diff --name-only origin/main...HEAD` lists only these four files. I did not touch `.github/`, `pyproject`, `uv.lock`, `api/data/cache/`, `discovery.json`, `discovery.py`, `sources.py`, `registry.py`, `web/`, `web_queries.py` or `attention_queries.json`.

## 5 Commits

Branch `claude/w8e-pc-worker`:
- `8132ff58` test: W8e PC worker wiring red tests (attention_pc_refresh, red). Collection failed with ImportError because the module did not exist yet.
- `f29f6166` feat: W8e PC worker wiring (attention_pc_refresh, lifespan start/stop; green). This commit also carries the test-file fixes found while going green (heading 8, item 6).
- the report commit (this file)

## 6 Tests run

All runs on Windows (win32 10.0.19045), Python 3.12, worktree at the content of `f29f6166`.

- `UV_FROZEN=1 uv run --project api pytest api/tests/data/test_attention_pc_refresh.py -q -p no:cacheprovider`: **29 passed** in 187 s (about 2026-10-29T22:55Z). The slowest tests are the two 90-day simulations (98 s and 48 s; atomic JSON and parquet I/O in the merged modules dominate).
- Red state before the module existed: the same command gave `1 error during collection` (ImportError) at `8132ff58`.
- Gate run, 2026-10-29T23:03:24Z to 23:09:57Z: `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention api/tests/tooling_guards api/tests/routers api/tests/deploy api/tests/data/test_refresh_worker.py api/tests/data/test_equities_refresh.py api/tests/data/test_equities_refresh_worker.py -q -p no:cacheprovider` gave **1218 passed, 40 failed, 2 skipped, 1 deselected**.
  - The 40 failures are 7 in `routers/test_attention.py`, 12 in `routers/test_discovery.py`, 11 in `routers/test_discovery_history.py`, 9 in `routers/test_discovery_price.py` and 1 in `routers/test_equities_router.py::test_concurrent_adds_store_exactly_thirty`.
  - **The same 40 fail without this change.** I re-ran exactly those 40 node ids with `api/main.py` restored to `origin/main` (`git show origin/main:api/main.py > api/main.py`; then the new module is not imported anywhere) and got 40 failed (about 2026-10-29T23:15Z), then restored the branch file.
  - Cause, inferred from the assertion text "handler must not reach the network" and the same symptom in my own tests: on Windows, asyncio builds its self-pipe socket pair with a loopback `connect`, which those tests' `socket.socket.connect` guard rejects. [INFERENCE] They should pass on Linux CI; CI has not run on this branch yet.
  - `api/tests/data/attention` (all), `api/tests/tooling_guards` (both workflow guards), `api/tests/deploy`, and the refresh and equities worker tests had **no failures**.

## 7 Tests NOT run

- The full `api/tests` suite and `web/` checks: out of the envelope's gate list.
- Owner probe P-W1 (`$env:SCREENER_ATTENTION_PC_WORKER="1"; python -m uvicorn api.main:app --port 8000` for one hour, then the status probe). It needs the owner's host and network.
- Live Reddit or X traffic, the real `twscrape_reader.start` path and the real salt file. The tests use fakes only, and sockets off the loopback are blocked.
- A Linux run of the 40 pre-existing router failures (heading 6).

## 8 Deviations

1. **`discovery.json` and `discovery.py` not edited (owner-approved).** Adding `fetch_side` would break `discovery.validate_config`, whose `CONFIG_KEYS` set is closed and belongs to W8f. Instead the worker has a default map `FETCH_SIDE` (`xsearch` and `reddit` on `pc_side`, the other five Discovery sources on `github`). It reads a `fetch_side` object from `discovery.json` with a raw JSON read, only when the key is present; a value other than `pc_side` keeps that source off here. W8f adds the key and validates it (AC7 strict validation is W8f's).
2. **Config keys W8e needs but did not add.** `attention_queries.json` and `web_queries.py` are owned by open PR #191 (W8c2), so I report these keys instead of adding them:
   - `x_spread_over_day` (SPEC rule 15a): a worker argument and attribute, default true.
   - `reddit_ledger_retention_days` (AC40, default 400): the worker argument `ledger_retention_days`.
   - Log rotation size and file count: read from the environment variables `SCREENER_ATTENTION_PC_LOG_MAX_BYTES` (default 5,000,000) and `SCREENER_ATTENTION_PC_LOG_FILES` (default 5), not from the config file.
   - `x_discovery_mode` rotation: the X queue always uses the rotation order (owner Q10), through the worker argument `x_rotation`, default true.
   - Proposed: W8c2 or W8f adds the first two keys to the collector block and the worker reads them; the log keys can follow.
3. **Reddit backfill depth.** No config key exists for it, so it comes from the `t` filter: `min(5, span_days - 2)`. That is 5 days for `week`, 0 for `day` and `hour`, and 5 for `month`, `year` and `all`.
4. **X values are stored by the worker.** `x_pool.run_unit` writes the raw pages and the `_xmeta` row but does not store the series value. W8e commits it through `web_evidence.commit_day` with method `xsearch_web_read_sample_v1`. `canary_ok` comes from the unit's row, and the trailing median covers 28 days of stored X points. The `backfilled` flag is left false, as in `reddit_web`; W8f owns that flag.
5. **The `stop_at` (host stops) semantics in tests.** No new unit starts at or after `stop_at`, but a unit that already started reads its pages (5-15 s apart), so it can end a few seconds after `stop_at`. In production `stop_at` is never set; the real host stop is the process ending, and an unfinished unit is retried later.
6. **Changes to the inherited draft tests**, each to make the test state the PLAN rule rather than a placeholder:
   - In the red commit:
     - `test_rotation_queue_oldest_stored_first`: the unfinished placeholder tail (`order is None and units is None`) was replaced by a real check of the unit order ADA, ETH, SOL.
     - `test_mode_switch_baseline_degraded`: a tautological assertion was replaced by "degraded for the rest of the start day".
     - `test_pc_off_stores_nothing`: slack for an in-flight unit's page gaps was added (item 5), plus a check that both sources stored something.
     - `test_unfinished_coin_day_carries_over`: the stop moved from 5 min to 381 s, so the outcome "exactly one unit" holds for any random draw instead of depending on the seed.
   - In the green commit:
     - The autouse socket guard now lets loopback connects through. The Windows asyncio socket pair needs one, and without it `TestClient` could not start.
     - `test_no_network_in_tests` now checks an off-host address (192.0.2.1).
     - The log rotation test writes to a subfolder, because `tmp_path` is the cache root.
     - `test_no_network_in_tests` resets the fake clock before the Reddit pass.
     - The two 90-day tests use a `no_fsync` fixture (fsync takes about a quarter of their time and proves nothing here).
     - The state-files test also bounds the completeness files.
7. **Mode detection** uses the worker's own start time. A laptop that sleeps without restarting the process is not detected as an outage. [INFERENCE] W8e2's health line or a heartbeat would be needed for that.
8. **Item ledger default.** When the flag is on, the first Reddit pass calls `reddit_items.load_salt(create=True)`, which creates the salt file outside the repository (`~/.screener-reddit-salt` or `SCREENER_REDDIT_SALT_FILE`), as the `reddit_items` docstring intends. If the salt is refused, the ledger is off and counting still works with the in-memory hasher.
9. **Not built here (other slices):**
   - The BASELINE comments and posts feed polling and the archive enrichment (AC37 c and d): W8c2 and W8c3.
   - A per-day X completeness file (attempted, fetched, missing by reason) for AC38: W8e writes the X evidence rows only through `x_pool` and `x_raw`, so X completeness reporting is unproven. Reddit's completeness is written by `reddit_web`.
   - The health or status payload: W8e2.

## 9 Blockers

None for this slice. Risks and open items:
- The 40 router failures on this Windows host predate this change (heading 6) but have not been confirmed green on Linux CI.
- The kept deviation in `reddit_web.reddit_source`, which writes `_s["effective"]` directly, says "remove once W8e lets `pc_pace` follow the configured budget for non-adaptive sources". I did not change `pc_pace.py` because it is outside this envelope's file list, so the workaround stays.
- Registry update request: mark W8e as delivered pending review and independent re-run. Reviewers should note that the PLAN's G-file-set gate ("only `api/main.py`, `discovery.json` and new files") is met without `discovery.json`, per deviation 1.

## 10 Follow-up

- W8f: add `fetch_side` to `discovery.json` and to `CONFIG_KEYS` with strict validation, and switch `pc_sources` to the validated config.
- W8c2 or W8f: add the `x_spread_over_day` and `reddit_ledger_retention_days` collector keys (and optionally the log size and count keys), and have the worker read them.
- Remove the `reddit_web.reddit_source` effective-budget workaround through a `pc_pace` change: a non-adaptive source follows its configured budget.
- W8e2: the health line (last unit, pause reason and end, budget, stale flag), X per-day completeness, and a heartbeat for mode detection across host sleep.
- Owner: run P-W1 after merge.

## 11 Context cost

Files loaded:
- the PLAN W8e section, plus SPEC rule 15, AC37 and the grep results for other ACs
- `pc_pace.py`, `reddit_web.py`, `x_pool.py`, `x_reader.py`, `x_filters.py`, `x_window.py`, `x_density.py`, `x_raw.py`, `density.py`, `web_queries.py`, `web_evidence.py` and `reddit_items.py` in full
- parts of `twscrape_reader.py`, plus `equities_refresh.py` and `main.py`
- the draft test file and the conftests
- the `master-planner.md` report template

About 180k tokens. Tools: read, bash, edit, write, grep, glob; no subagents.
