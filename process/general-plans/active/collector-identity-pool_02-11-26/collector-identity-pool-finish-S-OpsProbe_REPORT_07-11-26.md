# S-OpsProbe slice report (07-11-26)

## 1. Status
CODE-COMPLETE (not LIVE-READY: no owner-approved live probe run). Branch `claude/b2-validate`; committed locally, not pushed.

## 2. Scope
Finish plan §S-OpsProbe (B1–B6, A18): probe protocol layer — strict record schema bound to per-section hash, bootstrap/verify/observe modes, dry-run-by-default CLI, ordered orchestration, owner `--approve <digest>` prompts, refusal states, record storage; surface propose/approve/publish tooling; executor registry with real PX1–PX6, PR5, PR6 executors.

## 3. Changed paths
- `api/scripts/probe_owner.py` (protocol, registry `EXECUTORS`/`register`, `PENDING`, refusals, CLI)
- `api/scripts/probe_executors.py` (PX1–PX6, PR5, PR6 executors; `EXECUTORS_OWNED`; `build_dependencies`)
- `api/scripts/surface_tool.py` (structural capture → proposal → approve → publish)
- `api/tests/scripts/reddit_probe_fixtures.py`, `test_probe_owner.py`, `test_probe_executors.py`, `test_surface_tool.py`
- This report.

## 4. Work completed
Registry keyed by probe id; executors injected callables. PR1 → `executor_pending:S-RGQL`, PR2 → `executor_pending:S-RBrowser` until those slices `register()` them. PR3 → `executor_refused:a17_cookie_boundary` raised before dependencies are built (cookie values never read/persisted). PR4 reserved per plan table (`probe_reserved`; registration refused). Records are only written from an executor `Outcome`; missing dependency or unregistered executor is a refusal with no record. Dry run never builds dependencies.

## 5. Interfaces reviewed
`reddit_surface` section_sha256/validation, browser_session CDP bounds, relay health, x_queryids/x_reader transport, daily facts reader (PR6).

## 6. Tests run
`UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/tests/scripts/test_probe_executors.py api/tests/scripts/test_probe_owner.py api/tests/scripts/test_surface_tool.py -q -rs`
Red: earlier collection errors (modules missing), then 1 failed / 52 passed (`EXECUTORS_OWNED` missing). Green: 53 passed.

## 7. Data verification
Loopback fakes/synthetic fixtures only. No live requests, accounts, credentials, or Edge launch. No dependency or `.github` edits.

## 8. Error handling
Closed reason codes; `ProbeRefused` for approval mismatch, pending/refused/reserved executors, missing dependencies; production `build_dependencies` default-denies unwired routes.

## 9. Deviations
PR4 has no executor: plan table marks it reserved (archive declined), overriding the envelope's "PR4–PR6" wording.

## 10. Review decision needed
None for CODE-COMPLETE. LIVE-READY requires owner-approved runs.

## 11. Handoff
S-RGQL / S-RBrowser register PR1/PR2 via `probe_owner.register`. Main: run the three test files above plus S-B3I targets.
