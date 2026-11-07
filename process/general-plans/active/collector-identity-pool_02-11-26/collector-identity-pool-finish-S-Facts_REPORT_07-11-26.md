# collector-identity-pool-finish S-Facts report (Stage 2), 07-11-26

## 1. Status
CODE-COMPLETE for S-Facts on `claude/b2-validate` (worktree `wt-b2-validate`). Committed locally, not pushed. No live request; pure file I/O, no network.

## 2. Scope executed
PLAN contract D and slice "S-Facts: durable daily facts": new `daily_facts.py` (pure writer/reader, summarizer, retention, universe snapshot writer/reader) and its tests. No call sites (owned by S-XDrift, S-B3I, S-Cookie-X, S-RCore-B, S-RBrowser, S-RGQL).

## 3. Changed paths
- `api/data/attention/daily_facts.py` (new)
- `api/tests/data/attention/test_daily_facts.py` (new)
- this report

## 4. Contract surface (for consumers)
- `facts_dir()`, `events_path(day)` -> `<cache>/attention/_facts/events_<day>.jsonl` (resolved at call time from `cache.CACHE_ROOT`).
- `append(event, *, now, switches) -> bool`: `now` must be aware UTC; event keyed by the UTC day of `now`; False when `MAX_FILE_BYTES` (8 MiB) would be exceeded; `ValueError` on any non-allowlisted kind/field/value.
- Kinds (`KINDS`): `unit_completed`, `handoff`, `account_state` (state ∈ loss/pause/lock/quarantine/resume), `challenge` (class ∈ challenge/login_required), `cooldown` (action ∈ set/cleared, optional `until`), `session_check` (`result_class`, `cookie_age_class`), `queryid_state`, `mixed_call`, `poll_result` (per method/account: navigations, lanes, stop_reason), `request_counter`. Internal only: `switch_provenance`, `universe_snapshot`. Strings are tokens `[A-Za-z0-9_.:-]{1,64}`, ints non-negative non-bool.
- Switch provenance: written before the first event of a day and whenever the effective switch values differ from the last recorded ones; switch names `[a-z][a-z0-9_]*` with no secret-like part, values scalar/token/list/one-level map.
- `read_events(day)`, `summarize(events)` (pure: `kinds`, `accounts[source][account]` units/reads/pages/raw_results, `requests[source][method]`, `reasons`, `switches` in order, `universe[source]`).
- `prune(*, now, retention_days)`: int ≥ 30; deletes `events_<day>.jsonl` (and its lock) with day < today − retention; other files untouched.
- `write_universe_snapshot(day, source, *, eligible_symbols, ambiguous_symbols, method_order, now, switches) -> bool` once per source per UTC day (day must equal `now`'s UTC day; symbols `[A-Z0-9]{1,20}` unique; methods `[a-z][a-z0-9_]*` unique); `read_universe_snapshot(day, source) -> dict | None`.

## 5. Implementation notes
Append: thread lock + OS lock on adjacent `<file>.lock` (msvcrt/fcntl, bounded 5 s wait, same convention as `x_proxy_private.state_lock`), one `O_APPEND` write + fsync; reader skips a torn tail; next append starts on a fresh line. Files are never rewritten, so rollover cannot overwrite yesterday.

## 6. Tests (red first)
Test file written before the module (red: module absent). Covers append/provenance, switch change, rollover, non-UTC clock, allowlist and secret fields/values, switch secrecy, written-bytes marker scan, every kind, enumerated values, summarizer, size bound, torn tail, 4-thread concurrency, retention pruning and floor, universe snapshot once/absent/validation/day.

## 7. Commands and results
`UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/tests/data/attention/test_daily_facts.py -q -rs` -> `42 passed` (0 skipped).

## 8. Guard/test amendments
None.

## 9. Deviations
None. Interpretations: an over-size append is refused (returns False) rather than raising, so a worker never crashes on facts; the "unit completed" event carries `coin` and `coin_day` separately; `account_state` adds `resume` so pause/lock ends are recordable.

## 10. Risks / follow-ups for later slices
Call-site slices pass `switches` = the effective optional-switch values from `CollectorConfig` and call `prune(retention_days=cfg.facts_retention_days)`. Size refusals are silent beyond the False return; callers may log them. Rollback: delete `_facts/` (stage-2 row of the rollback table).

## 11. Next
Stage 3/4 consumers: S-XDrift (facts call sites), S-RCore-B (universe snapshot call site).
