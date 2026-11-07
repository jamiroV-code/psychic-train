# S-B3R report (07-11-26)

## 1. Status
CODE-COMPLETE (targeted tests green). Offline only, so there is no LIVE-READY gate. Nothing makes network calls, and the module reads only facts.

## 2. Scope delivered
New `api/data/attention/x_behaviour_report.py`. It reads durable facts through `daily_facts.read_events` and never reads pool state. It puts each UTC day into one arm based on its switch provenance:
- `baseline`: all five measures were off all day.
- One measure's name: only that measure was on all day.
- `combined`, `changed` and `no_provenance`: counted but excluded from comparisons.

Switches that are not measures do not affect the arm.

Per-day metrics for `xsearch_web`:
- units
- accounts and units per account
- spent reads: unit reads plus `mixed_call` charges
- challenges
- lock/pause/quarantine events
- missing coin-days: eligible symbols in the universe snapshot with no unit that day. When there is no snapshot this is `None` (unknown), not 0.
- shrink events: replayed with `x_behaviour.record_result` over the per-account `raw_results` in the range.

Decision rule:
- `inconclusive` when either arm has fewer than 7 days.
- `keep` when mean harm (challenges plus lock/pause) is strictly lower than baseline and missing coin-days are not higher.
- `remove` in every other case.

The result is deterministic. CLI: `python -m api.data.attention.x_behaviour_report --from D --to D` exits 0 and prints keep/remove/inconclusive with `baseline_days`/`measure_days` and the per-metric means. A bad range exits 2. The range is capped at 366 days.

## 3. Interfaces for later slices
`MEASURES`, `MIN_DAYS`, `classify(events) -> arm`, `day_metrics(events) -> dict`, `analyze(start, end) -> {from,to,min_days,arms,days,rows}`, `render(report) -> str`, `main(argv) -> int`. S-Report and S-OpsDoctor can call `analyze`/`render`.

## 4. Pool keys and defaults
None added. No switches changed. The module is read-only.

## 5. Tests (red first)
`api/tests/data/attention/test_x_behaviour_report.py` (10 tests):
- Red run: collection ImportError (module missing).
- Green run, with test_daily_facts and test_x_behaviour: 78 passed.

The tests cover:
- the C9 seeding: 7-day arm gives `keep`, 3-day arm gives `inconclusive`, and combined days are excluded
- a measure with no benefit gives `remove`, with the spent reads compared
- shrink replay
- missing universe gives unknown
- unreadable pool state is ignored
- range validation
- CLI output

## 6. Verification commands
From the repo root: `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/tests/data/attention/test_x_behaviour_report.py api/tests/data/attention/test_daily_facts.py api/tests/data/attention/test_x_behaviour.py -q -rs`

## 7. Deviations and review blockers
- The `cooldown` fact has no reason field, and the facts schema is owned by S-Facts. So shrink events are recomputed from `unit_completed.raw_results` with the same rule the pool uses, not read from cooldown facts.
- "Missing coin-days" for day D means eligible symbols with no unit completed on D. Backfill completions on later days do not count for D.

## 8. Rollback
Revert this commit. Nothing else depends on the module yet.

## 9. Risks
The keep/remove rule is a simple comparison of means, not a significance test. Results are only meaningful with matched conditions across arms, and 7 days is a floor, not proof.

## 10. Owner actions
None.

## 11. Changed paths
api/data/attention/x_behaviour_report.py, api/tests/data/attention/test_x_behaviour_report.py, this report.
