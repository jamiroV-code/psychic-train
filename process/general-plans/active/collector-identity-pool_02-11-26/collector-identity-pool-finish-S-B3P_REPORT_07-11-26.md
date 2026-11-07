# S-B3P report (07-11-26): B3 (a) pure behaviour policy and pool keys

## 1. Status
CODE-COMPLETE for S-B3P (Stage 5). All five B3 switches stay default off; nothing is wired into scheduling yet (that is S-B3I). No live requests, no dependency or `.github` edits.

## 2. Scope delivered
- `api/data/attention/x_quiet.py` (new): `parse_window`, `in_quiet`, `next_outside`, `quiet_until(now, label, windows, enabled=)`. Zone-aware (zoneinfo) window math, midnight crossing, DST gap (resumes at the transition instant), DST fold (first occurrence of the end time). Always returns an aware UTC instant.
- `api/data/attention/x_behaviour.py` (new, pure): warm-up ladder (`warmup_stage`, `effective_cap`, `warmup_start`), seeded variation (`variation(label, day, page_cap=, enabled=)` → `Variation.page_size/pause_multiplier/order/order_groups`), adaptive cooldown (`cooldown(...)` → `Cooldown(reason, until, owner_pause)`, `record_result(...)`), mixed budget (`MIXED_OPS`, `mixed_allowed`, `mixed_charge`, `mixed_today`). Constants: `BEHAVIOUR_REASONS = ("challenge","stripped_strike","rate_limit","shrink")`, `HISTORY_LEN=7`, `SHRINK_RUN_MAX=10000`, `MIXED_DAILY_MAX=3`, `MIXED_RESERVE=20`, `MIXED_EVERY_UNITS=20`, `QUERY_CLASS_RE`.
- `api/data/attention/x_pool.py`: seven B3 keys in `ACCOUNT_KEYS`; `B3_ACCOUNT_DEFAULTS` (contract G literals); `setdefault` migration before the exact-key check; `_valid_b3` types/bounds; fresh accounts get a per-account copy of `result_history`.
- Guard (Table H): `x_behaviour.py` and `x_quiet.py` added to `X_MODULES`; fixed-hour detection exempts only `x_quiet.py` (`FIXED_HOUR_EXEMPT`), with an assertion that the exemption set is exactly that file and the detector still fires on it.

## 3. Interfaces for later slices
- S-B3I: call `x_quiet.quiet_until(now, label, config.x_account_quiet_hours, enabled=config.x_quiet_hours_enabled)` inside `_next_due`; `x_behaviour.effective_cap(config.x_account_daily_cap, a["warmup_start_day"], today, enabled=config.x_warmup_enabled, grandfathered=...)`; persist `warmup_start(...)`; `cooldown(...)` result into `behaviour_cooldown_until`/`behaviour_reason` (challenge → owner pause, no deadline, regardless of switch); `record_result(...)` into `result_history`/`shrink_run`; `mixed_today`/`mixed_allowed`/`mixed_charge` with `mixed_day`/`mixed_calls`.
- Cooldown precedence: challenge first; otherwise the latest timed deadline wins, ties by reason order.

## 4. Pool keys and defaults
`warmup_start_day` null (ISO date), `behaviour_cooldown_until` null (UTC ISO timestamp, offset must be zero), `behaviour_reason` null (allowlisted), `shrink_run` 0 (int 0..10000), `result_history` [] (≤7 `{day, count, query_class}`), `mixed_day` null (ISO date), `mixed_calls` 0 (int 0..3).

## 5. Tests (red first, then green)
Red: new modules missing (2 collection errors), pool/guard 6 failed / 84 passed. Green: `test_x_quiet.py`, `test_x_behaviour.py`, `test_x_pool.py`, `test_pc_collector_guards.py`, `test_x_reader_guards.py` → 144 passed. Neighbour suites: `test_x_proxy_state.py` + `test_x_reader.py` 103 passed; the three `test_attention_pc_refresh*.py` 262 passed + 20 failed during a concurrent S-RCore-B edit, and those 20 passed on rerun (`--lf`).

## 6. Verification commands
`UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/tests/data/attention/test_x_quiet.py api/tests/data/attention/test_x_behaviour.py api/tests/data/attention/test_x_pool.py api/tests/tooling_guards/test_pc_collector_guards.py api/tests/tooling_guards/test_x_reader_guards.py -q -rs`

## 7. Deviations
- None from the plan text. Design choices: `shrink_run` capped at 10000 and `mixed_calls` at 3 as the "validate bounded counts" bounds; `query_class` must match `[a-z0-9_]{1,24}`; a shrink is evaluated only when the seven-record history is entirely of the same query class (minimum seven comparable observations).

## 8. Rollback
Stop the collector, strip exactly the seven `B3_ACCOUNT_DEFAULTS` keys from every account in the pool state, restore pre-S-B3P code (contract G stage 5 row).

## 9. Risks
Variation/quiet/warm-up have no effect until S-B3I wires them. Quiet hours and warm-up have no primary evidence (REF-X §4.3); stated in docstrings.

## 10. Owner actions
None.

## 11. Changed paths
`api/data/attention/x_quiet.py`, `api/data/attention/x_behaviour.py`, `api/data/attention/x_pool.py`, `api/tests/data/attention/test_x_quiet.py`, `api/tests/data/attention/test_x_behaviour.py`, `api/tests/data/attention/test_x_pool.py`, `api/tests/tooling_guards/test_pc_collector_guards.py`, this report.
