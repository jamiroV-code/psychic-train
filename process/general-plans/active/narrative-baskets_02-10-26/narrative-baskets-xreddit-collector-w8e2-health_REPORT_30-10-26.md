---
name: report:narrative-baskets-xreddit-collector-w8e2-health
description: "W8e2 code slice: read-only health line on the X and Reddit Sources rows (AC38, AC39, AC47, AC52)"
date: 30-10-26
metadata:
  node_type: memory
  type: report
  feature: narrative-baskets
  phase: W8e2
---

## 1 Task ID
W8e2 (code part): server health line. Branch `claude/w8e2-health-line`. The host guide is a separate PR (#194).

## 2 Outcome
done (CI result is in heading 6)

## 3 Summary
- `GET /api/narrative/sources`: the X and Reddit rows now have an optional `health` object. It is read only from the worker's state and evidence files. There is no network call and no write, and `PcSource`, which writes during its day roll, is never constructed.
- Without a worker state file the row has no `health` key at all, so the rows match main byte for byte. A wrap serializer drops the key when it is None, so the exact key-set test in `api/tests/routers/test_discovery.py` stays unchanged.
- Fields: `last_unit_at`, `paused`/`pause_reason`/`pause_until` (None while paused = waits for the owner to act); `collection_day` with `attempted`/`fetched` (distinct coin-days collected today, canaries excluded); `completeness_day` (yesterday UTC) with `completeness_attempted`/`completeness_fetched`/`missing`/`missing_reasons`/`capped`/`newest_age_hours` and the `completeness` text; `budget_used`/`effective_budget`/`budget_spent`; `mode`/`expected_gap_s`/`stale` (stale = no unit for more than 2 x the persisted gap); for X, `accounts_active`/`accounts_total`, plus label, state, reason, last_used and `cookie_age_days` for each account (labels only, never a cookie); `free_disk_bytes` (from `shutil.disk_usage` on the cache root); `clock_sync_age_seconds` is always null because no sync evidence is persisted.
- Missing or older evidence is reported as `unknown`/null, never as 0.
- Producer changes (approved by Main during the task):
  - The worker now persists `<cache>/attention/_pc_state/<store>_health.json` (mode, expected gap) from its real trickle and baseline-spread rule.
  - X now writes per-day completeness files in the same schema as Reddit's (`<cache>/attention/xsearch_web/_meta/_completeness/<day>.json`, pruned like X raw pages).
  - Both X and Reddit record an attempted `unit_interrupted` entry before the first request and replace it with the final outcome. A failed attempt is recorded as `failed`, and a retry of the same coin-day overwrites that coin-day's single entry.

## 4 Files changed
- api/analytics/attention/sources.py (health reader)
- api/models/discovery.py (DiscoverySourceHealth, DiscoveryAccountHealth, `health` on the row)
- api/data/attention_pc_refresh.py (schedule snapshot, X completeness, record before dispatch, prune) — **outside the original envelope; Main approved it during the task**
- api/data/attention/reddit_web.py (record before dispatch, failed on an unexpected exception, `count_request`) — **outside the original envelope; Main approved it during the task**
- api/tests/analytics/attention/test_sources_health.py (new)
- api/tests/data/test_attention_pc_refresh.py (smoke from the worker through the files to Sources, durable attempts, restart without double counting, failed classification, mode/gap, bounded files)
- this report

## 5 Commits
`claude/w8e2-health-line`: f2a1abd3 (red-first tests), adcdbe6b (implementation), plus the report and test cleanup commit (see the PR).

## 6 Tests run
- Red-first: `UV_FROZEN=1 uv run --project api pytest api/tests/analytics/attention/test_sources_health.py -q`: 6 failed at f2a1abd3 (missing `now` and `_collector`), as intended.
- `UV_FROZEN=1 uv run --project api pytest api/tests/analytics/attention api/tests/data/attention api/tests/tooling_guards api/tests/data/test_attention_pc_refresh.py -q` at adcdbe6b, 2026-10-30 ~11:00Z: 1325 passed, 1 skipped, 2 failed.
  - Failure 1: `test_worker_state_does_not_attach_to_unrelated_selected_store`. My test was invalid: config validation already rejects that `source_impl`. I removed the test.
  - Failure 2: `test_universe_classes.py::test_discovery_end_to_end_on_fixture`. It fails inside the Starlette TestClient portal (the Windows ProactorEventLoop against the no-network guard) before reaching our code. This is the known Windows host failure.
  - Before that: `test_sources.py::test_100_coin_fixture_is_fast_and_cached` failed once while the machine was loaded (cold 11.4 s). On its own it passed (cold 1.7 s).
- CI on PR #195 at 53094a81 (Linux): `api — pytest` pass (3m48s), `web — vitest, tsc, island build` pass (58s). This covers the router tests that cannot run on this Windows host.
- After removing the invalid test: `test_sources_health.py` 11 passed.

## 7 Tests NOT run
- `api/tests/routers` on this Windows host (known ProactorEventLoop failures on plain main). CI on Linux is the judge.
- No live X or Reddit traffic: fakes only, by design.

## 8 Deviations
- Two producer files beyond the original envelope (attention_pc_refresh.py, reddit_web.py). Reason: the worker did not persist the attempted and missing reasons for X coin-days, the expected gap or the mode. Main approved minimal producer changes.
- `attempted`/`fetched` count distinct coin-days collected today (`collection_day`). The completeness counts are for yesterday (`completeness_day`). Activity units are not used as attempts, because they include canaries.
- The test `test_existing_sources_rows_unchanged_when_no_worker_state` also checks that the `health` key is absent from the dump.

## 9 Blockers
- None. Risk: X completeness files written before this change do not exist, so earlier days show `unknown`. Clock-sync age stays null until the host exposes it.

## 10 Follow-up
- Guide (#194): to watch the worker, read local `GET /api/narrative/sources` → `sources[].health` (no new probe flag; #191 owns probe_pc_sources.py).

## 11 Context cost
Loaded AGENTS.md, the plan section W8e2, SPEC AC38/AC39/AC47/AC52/Annex J, master-planner.md section 9, and the worker, pc_pace, x_pool, reddit_web, web_evidence, twscrape_reader and sources modules plus their tests. About 120k tokens. Tools: shell, read/edit, pytest via uv, gh.
