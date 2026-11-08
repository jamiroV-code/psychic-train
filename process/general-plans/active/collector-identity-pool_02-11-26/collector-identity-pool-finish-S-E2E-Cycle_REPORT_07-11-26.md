# S-E2E-Cycle slice report (Stage 12, written 08-11-26)

## 1. Status
CODE-COMPLETE on synthetic loopback services. `python -m api.tests.cycle.acceptance` exits 0 with C1-C14 passed and no skips. It ran in 114.4 s with a peak of 280 MB in the parent process; the nested self-test child is counted in the time but not in the memory figure. Not LIVE-READY: no live request was sent, real Edge was never launched, and the probe records are synthetic recordings. C15 (consolidated regression) was NOT run here; it is a separate gate. Branch `claude/b2-validate`, committed locally, not pushed.

## 2. Scope
Plan section "The one end-to-end acceptance", C1-C15. The partial uncommitted work left by earlier workers was kept and finished: `services.py`, `world.py` (C1/C2 and the start of C4), `test_real_reader.py` and `test_daily_cycle.py`.

## 3. Changed paths
New, all under `api/tests/cycle/`:
- `services.py`: loopback TLS origin for fake X, the feed and gql-fed, plus the seam installer.
- `world.py`: the X days, C1-C7 and C9.
- `browser.py`: fake-browser hosts and the real self-test admission.
- `relay.py`: C8.
- `reddit.py`: C10 and C11.
- `closing.py`: C12-C14.
- `acceptance.py`: the CLI.
- `test_daily_cycle.py` and `test_real_reader.py`.

Also this report. No production, shared-fixture, dependency or `.github` file was edited.

## 4. Implementation
The real `TwscrapeReader`/`search_raw`/bootstrap, `XStart`, `XPool`/`run_unit`, `run_daily_canary`, `evaluate_candidate`, harvest, `LiveStream`, `reddit_browser`, `RedditRoutes`, `BrowserSessions`, `BrowserHost`, `Relay`, `CdpClient`, `browser_selftest`, `reddit_gql` (production `HttpTransport`), `ProxyRuntime`, `daily_report`, the FastAPI app and `collector_doctor.main` all run unmodified.

Seams used, all from S-Fixtures or test-only:
- DNS/port mapping to loopback.
- Synthetic trust roots, injected into httpx clients.
- Deterministic transaction-key parsing (`xclid.load_keys`), with its per-process cache reset for each origin.
- The spawn launcher for `browser_fake_main`.
- The self-test TCP-table enumerator.
- The A6b resolver and dialer.
- The fake CONNECT proxy.
- The virtual clock and wait.
- The owner query-file path (`web_queries.QUERIES_PATH`, for status and doctor).

Helpers are imported from existing test modules; none of those files was edited. Each scenario records the real behaviour it observed, plus a `not_exercised` list where something was not covered.

`acceptance.py` does the following:
- Writes `cycle_report.json`. The default location is the temp dir; `--report` overrides it.
- Prints per-step results, the budget and the "cannot prove" statement.
- `--regression` prints the C15 command and a recorded result (`--regression-record`). Without a record it shows `not_recorded` and exits non-zero. It never derives C15 from this run.
- `--ui` fails explicitly with exit 2, because that is S-E2E-UI.

C13 drives the real doctor with `--selftest`. Its real `default_selftest_runner` spawns `python -m api.tests.cycle.acceptance`. The child gets `MYSITE_CYCLE_NESTED=1`, runs the full cycle without re-entering the self-test, and the parent requires `selftest PASS acceptance_passed`.

## 5. Acceptance results (last run)
| Step | Observed |
|---|---|
| C1 | All optional switches off. Real `XStream.run_pass`: 380 reads over 4 accounts, canary passed, spread over time, ceiling 800. |
| C2 | Accounts locked on `account_cap`. One account per coin-day (no split). Total ≤ global ceiling. |
| C3 | The server rotates the ID. The bundle sentinel records the candidate. The unit 404s on 2 accounts, then the forced evaluation gives `passed, passed`. The ID is adopted (`source bundle`), drift streak stays 0, there is no stop, and the next read carries the rotated ID. On day 3 the bundle advertises a newer ID before the server switches; the evaluation is `inconclusive, inconclusive` and the active ID is unchanged. |
| C4 | Day 2: `acc_b` is `locked/endpoint_restricted`, the unit reruns once on `acc_a`, and drift is unchanged. Day 3: the second event gives `locked/endpoint_404` (24 h). |
| C5 | `(64)` gives `inactive/x_account_suspended`. The unit fails over once (restarts 1), and the 40 reads are charged once. |
| C6 | Expired session gives `x_login_required`. After the REAL self-test admission (`tested_clean`), the automatic harvest runs through the spawned fake over the real host, relay and CDP with the real `XRouteProvider` and the pool day guard, and returns `ok`. Every renewed request carries exactly one `ct0`. The canary then runs, and the next real read uses the renewed cookie. A second harvest the same day gives `daily_check_used`. The age trigger makes `acc_d` due; it is logged out, so it ends `needs_owner/login_page`. The suspended account is never revived. |
| C7 | `acc_e` is registered with a 1-day rest: `locked/resting`, 0 requests. The owner marks it ready. Next UTC day it is active and in the canary. |
| C8 | B2: failed admission gives `proxy_quarantined`; the replacement is admitted afresh. Relay direct mode: pinned numeric dial; 6 hostile authorities refused; 4 private answers refused. Proxy mode: the spawned fake browser loads only through the relay, the only dial is to the proxy, the CONNECT is numeric, and the hostile page is refused. Partial config gives `refuse` and no launch. Admission expiry closes the open tunnel. |
| C9 | Each measure was run alone over the real reader: quiet-hours hold, mixed call charged 20 with no coin writes, variation page size bounded, cooldown hand-off, warm-up cap 100 against 1000 for a grandfathered account. Then all five together. Facts record each switch provenance. The analyzer, over seeded days, gives warm-up (7 days) `keep` and mixed (3 days) `inconclusive`, deterministic across two runs. |
| C10 | No verify record or a bootstrap-only record gives `needs_probe` and no launch. An HTML surface gives `unsupported_format`. With a verify record: the `rd_a` poll, then the close poll on `rd_b` after midnight. D1 settles: 5 coins fetched, Z1 true zero stored (7 positive days), Z2 `zero_unverified` (3 days), first write wins. Login wall on `rd_a` gives `paused/reddit_login_required` and one retry on `rd_b`. `rd_b` per-account cap gives `cap` lanes. Owner relogin restores `rd_a`. Block page gives `empty_shell` (an error, not zero). D2 commit is `lane_incomplete`, with 0 values. `rd_c` stays resting. No post text, username or cookie appears in any cache file. |
| C11 | Feed pass after 13-11: 1 RSS request answered 403, outcome `paused`, no value or zero. gql refusals: no record, stale record and hash/revision mismatch all give `needs_probe`. With every live gate refused there is no live value or zero for the day. With a fresh PR1 record, gql runs over loopback TLS as `reddit_live_gql_v1`: settled, 3 fetched, browser store untouched. Selection: the live-seeded coin gets `reddit_live_browser` and the feed-only coin gets `reddit_web`. |
| C12 | Reports for 6 days. Every method satisfies eligible = stored + missing and stored = exact + estimated; `100%` appears only when everything is stored; missing coins are printed as `SYM missing (reason)`; every coin has `selected_method`. D1 browser: 14 eligible, 6 stored, 8 `zero_unverified`. Late Reddit evidence revises the D2 report to revision 2 (`completeness/reddit_live_browser`). |
| C13 | Real `/api/narrative/sources`: Reddit method rows `browser needs_probe` (the surface was republished in C11), `gql ok`, `reddit_stream unknown`; X accounts present; no doctor block before the doctor runs. The real doctor (`--live --selftest`) gives FAIL (exit 2); `feed_methods WARN feed_methods_stale`; PX1-6 and PR5 `UNKNOWN`; selftest PASS from the real runner's child; afterwards the status shows the doctor state. |
| C14 | 222 cache files, the repo files that are new during the run (none), 2 status JSON responses, captured logs and the pool log: 0 leaks. The authorized private stores (5 account DBs) were scanned separately and do hold cookies. |

## 6. Tests and evidence
- **Red first, actually run:** before any new code, `test_daily_cycle` failed with `{'C1','C2'} != {C1..C14}`. Each later step was added red, then made green; the assertion failures were observed along the way.
- **Green:** `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/tests/cycle/ -q` gave **2 passed** (58 s).
- **Acceptance:** `UV_FROZEN=1 uv run --project api --frozen --group xreader python -m api.tests.cycle.acceptance` gave exit 0; C1-C14 passed; 114.4 s, within the ≤ 180 s / ≤ 1 GiB budget.
- `--ui` gives exit 2 (explicit).

## 7. What it cannot prove
The cycle does not prove:
- real X or Reddit behaviour;
- real Chrome/Edge behaviour;
- route quality;
- Windows deployment ACLs or Task Scheduler;
- ban avoidance;
- that real Reddit responses fit the grammar;
- the real transaction-ID parser (it is substituted; the real bootstrap request path runs).

Native sockets are not observed (BP13). The probe records are synthetic.

## 8. Not exercised (recorded per step in `cycle_report.json`)
- **C3:** the query ID on the routed B2 child envelope. The cycle uses the all-null direct configuration, so no routed child is spawned. That case is covered by `test_x_proxy_spawn` only.
- **C8:** the B2 quarantine/replacement half runs in a separate temporary cache with the S-RAcct-B fixture documents (label `ra_one`).
- **C8:** for the partial-config case, the session's route answer comes from a fixed `proxy_not_admitted` provider, while the relay mode itself comes from the real `select_mode`.
- **C10:** the `rd_*` accounts run direct, not over per-account proxy routes. Comment counts are fixed. The config lowers the canary minimum to 1 and sets 24 polls per day to suit the synthetic 4-hour post cadence.
- **C11:** selection is checked through `daily_report.selected_methods` (the real `pick_source_impl` over the real history series), not a full `build_discovery`. The feed's probe admission uses a synthetic `probe_records.json`.
- **C13:** the `--ui` screenshots and the seeded `x_sizing_shortfall` status-box text belong to S-E2E-UI.
- **C14:** no child argv/env (no routed child is spawned). CDP frames are not persisted by the client.

## 9. Deviations and findings
- The cycle spans 6 simulated UTC days (11-12..11-17), not 3: three X days, then the Reddit days on the same monotonic virtual clock.
- `cycle_report.json` defaults to the temp directory (the nested child writes `cycle_report_selftest.json`), so no file is written into the repo.
- **Finding for G-FINAL / S-OpsDoctor:** `--live` shows `live_PR1`/`live_PR2` PASS from the cycle's synthetic records. The doctor cannot tell a synthetic record from an owner-approved one; in production only `probe_owner --approve` writes them.
- The cycle restores the process-global `twscrape.api.OP_SearchTimeline` binding and the library's `XClIdGenStore` cache through monkeypatch. Without this, a later test in the same process would see the rotated ID.

## 10. Rollback
Revert the commit (test-only paths). Remove `%TEMP%/cycle_report*.json`.

## 11. Next
- S-E2E-UI (Stage 13) adds `--ui` over this cycle's cache.
- G-FINAL runs C15: `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/ -q -rs`, then records the result for `--regression --regression-record`.
- Main: rerun the two commands in §6.
