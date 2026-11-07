# S-RCore-B slice report: Reddit worker integration (07-11-26)

## 1. Status
CODE-COMPLETE for S-RCore-B. LIVE-READY is not claimed: no method module (`reddit_browser`, `reddit_gql`) exists yet, so a named method resolves to `UnavailableMethod` and its stream only reports `method_unavailable`. Default off: with `reddit_live_methods` empty nothing new is resolved, constructed or run. No live requests; fakes and a virtual clock only. Branch `claude/b2-validate`, worktree `wt-b2-validate`; nothing pushed, no PR action (task envelope).

## 2. Scope
PLAN §S-RCore-B, RC-9 registration (the worker registers the `reddit_core.resolve_methods` table), contract D facts call sites for Reddit polls and the universe snapshot call site for the X and Reddit streams, the S-StatusAPI health contract `_pc_state/reddit_live/<store>_health.json`. `attention_pc_refresh.py` chain link after S-XDrift (26 changed lines, within the ~40-line budget).

## 3. Changed paths
- `api/data/attention_pc_live.py` (new): `LiveStream`, `build`, `deps`, `health_path`.
- `api/data/attention_pc_refresh.py`: base `Stream._snapshot` and its call in `run_pass`; `AttentionPcWorker(live_methods=...)` and the live stream construction.
- `api/tests/data/test_attention_pc_refresh_stream.py`, `api/tests/data/test_attention_pc_refresh.py`, `api/tests/data/test_attention_pc_refresh_collector.py` (tests added; one import line extended).
- This report.

## 4. Implementation
- **Construction.** Only when `reddit_web` runs on the PC (`pc_sources`), the worker reads the config once and, if `reddit_live_methods` is non-empty, calls the factory (`live_methods` injectable; default `reddit_core.resolve_methods(config, deps)`, deps = `SimpleNamespace(clock, sleep)`). One `LiveStream` per returned method, keyed by its store (`reddit_live_browser`, `reddit_live_gql`), so it gets its own thread `attention-pc-<store>`, its own lock (not in `PASS_LOCKS`), state and cap. An unreadable config builds no live stream. Enabling or disabling takes effect at restart.
- **Pass** (own lock; `locked` otherwise): universe snapshot → gate (`gate_state != ready` → that gate code is the outcome) → breaker (`reddit_live.breaker_open` → `breaker`) → daily cap (`request_cap`) → due (`not_due`) → `build_context` (subreddits `web_queries.stream_subreddits`, `reddit_live_threads_per_poll`) with `requests_left` = cap − used → `run_poll` → `record_poll` → facts → commit of the completed days (last 2) that have lanes on D or D+1 and are not settled → health file.
- **Caps.** gql: `reddit_live_gql_daily_request_cap` over persisted requests; browser: `reddit_browser_daily_navigation_cap` over persisted navigations.
- **Schedule.** `next_poll_due = max(reddit_live.poll_due(store, now, reddit_live_polls_per_day), method.next_poll_due(now))`; `locked` +60 s, `failed` +600 s, `breaker`/`request_cap`/`method_unavailable`/`disabled` next UTC day (00:00 + 20 s), other non-ready gates re-checked after 3600 s. `_idle`/`_extra_wake` hooks return the poll due.
- **Health** (`{state, reason, lanes, comments_scope, requests_today, cap, observed_at}`): `ready` → `ok`; `needs_probe` → `needs_probe`; `disabled` → `disabled/method_disabled`; other gates → `blocked/<gate>`; breaker/cap → `degraded/<code>`; `lanes` = {posts: min subreddit posts coverage, comments: comments coverage} of the last committed day doc (null until one exists).
- **Facts.** Per poll `poll_result {source: reddit, method: <store>, account: null, navigations, lanes, stop_reason}` (first failed stop reason, else the most common) and `request_counter {source, method, requests}`. Universe snapshot: base `Stream` at its first pass of each UTC day writes `write_universe_snapshot(day, "xsearch"|"reddit", eligible = pass symbols minus ambiguous, ambiguous = ambiguous ∩ coins, method_order = ["xsearch_web"] | reddit_impl_order)`; live streams call the same helper (first writer wins, once per source/day). Switches are `x_pool.facts_switches(config)` (same as S-XDrift, so provenance lines do not churn). Fact failures are logged by class name and never stop a pass.

## 5. Qualifications / interpretations
- The `LiveStream` class lives in a new module `attention_pc_live.py` (imported lazily by the worker) to keep the shared `attention_pc_refresh.py` edit inside its line budget; the plan names "stream class" without a file.
- `pc_sources()` is unchanged; live streams are added by the worker after it (they require the Reddit PC side).
- The method account label in `poll_result` is null: the `LiveMethod` interface exposes no account; S-RBrowser may add it.
- Commit only runs for days with recorded lanes, so a method never writes completeness documents for days it did not observe (which the status reader would show as a settled day).

## 6. Tests and evidence
Red first: the new tests were run before the implementation: **8 failed** (the `-k live` subset; TypeError on `live_methods`, missing snapshot), recorded before any implementation edit.
Green: new tests subset **10 passed** (first run), then the full three files — see section 11 of the final message for counts.
No full suite, lint or formatter run.

## 7. Interfaces
- `AttentionPcWorker(live_methods=Callable[[CollectorConfig, deps], dict[name, LiveMethod]])`.
- `attention_pc_live.LiveStream(worker, store, rng, method)`: `.method`, `.lock`, `.cap(config)`, `.used(now)`, `.next_poll_due(q, now)`, `.schedule(outcome)`, `.run_pass(stop_at=None)` → `polled|not_due|locked|breaker|request_cap|<gate state>`.
- `attention_pc_live.deps(worker)` → `SimpleNamespace(clock, sleep)` handed to `make_method(config, deps)` (S-RBrowser/S-RGQL).
- Health file per S-StatusAPI contract plus `observed_at`.

## 8. Failure and disclosure behavior
Logs carry the store and an exception class name only. No text, URLs or usernames are written; facts hold codes and counts.

## 9. Deviations
None outside owned files. Module placement noted in §5.

## 10. Rollback
Revert this commit; remove `<cache>/attention/_pc_state/reddit_live/`. Live stores' lanes/state files under `<cache>/attention/reddit_live_*/_meta/` stay valid for S-RCore-A. With `reddit_live_methods` empty the worker is byte-for-byte the S-XDrift behaviour except the universe snapshot fact.

## 11. Next
S-B3I continues the `attention_pc_refresh.py` chain. S-RBrowser/S-RGQL supply `make_method(config, deps)`; S-Report reads `universe_snapshot` and the method completeness docs. Main runs the stage gate (the three worker test files plus `api/tests/analytics/attention/test_sources_finish_status.py`).
