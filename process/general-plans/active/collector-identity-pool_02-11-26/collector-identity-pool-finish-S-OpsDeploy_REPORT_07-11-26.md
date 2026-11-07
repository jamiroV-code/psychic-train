# S-OpsDeploy (Stage 12) slice report — 07-11-26

Status: CODE-COMPLETE (UNRUN on the owner machine; no live requests, no Edge launch, no firewall change).
Branch: claude/b2-validate. Finished the first worker's partial, uncommitted work; nothing was thrown away.

## Changed paths
- api/scripts/browser_firewall_rule.py (new): prints text only — PowerShell `New-NetFirewallRule`, the matching
  `netsh` command, removal and verification commands. No `subprocess` import; never reads or changes firewall state.
- api/scripts/probe_owner.py: added `--queries <absolute private path outside the repo>`. A routed config with no
  `--queries` refuses with `private_queries_required`. A direct/off config still uses the committed default.
- api/data/attention/browser_session.py: added `--queries` with the same validation.
- api/scripts/probe_executors.py: PX1 and PX6 use `XRouteProvider` over `ProxyRuntime` (`_x_routes`). PR5 uses
  `RedditRoutes`. PX2–PX5 pass `config_path` to `twscrape_reader.start`. PR5 refuses `route_not_admitted` when
  routing is configured but no private path was given.
- api/scripts/probe_gql.py (PR1): when routing is configured, uses `RedditRoutes` limited to the gql_anon section,
  and refuses with no private path, no ready account, or no admission.
- api/scripts/probe_browser.py (PR2): uses the explicit `config_path` instead of the committed queries path.
- deploy/start-collector.ps1: `-Doctor` offline pre-flight. FAIL refuses the start with exit 5; WARN is logged
  and the start continues.
- deploy/register-collector-tasks.ps1 (new), deploy/examples/* (new, synthetic), deploy/config.example.psd1,
  deploy/README.md ("Collector identity pool runbook", steps 1–9 incl. rollback).
- Tests: api/tests/deploy/test_browser_firewall_rule.py (new), test_deploy_collector_shape.py,
  api/tests/scripts/test_probe_executors.py, test_probe_owner.py, api/tests/data/attention/test_browser_session.py.

## Tests
`UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/tests/deploy api/tests/scripts/test_probe_executors.py api/tests/scripts/test_probe_owner.py api/tests/data/attention/test_browser_session.py api/tests/scripts/test_probe_gql.py api/tests/scripts/test_probe_browser.py api/tests/scripts/test_collector_doctor.py -q -rs`
→ 278 passed, 1 skipped (lane-scope check only runs on claude/p2-deploy).
Failures seen before the fixes:
- The example collector block had 4 `x_accounts` but inherited `x_pool_max: 3`. Fixed by adding `"x_pool_max": 4`.
- `test_probe_gql::test_production_dependencies_default_deny` failed: a routed config with no path refused with
  `no_ready_account`. It now refuses with `route_not_admitted`, which keeps the existing refusal contract.
The first worker had already written the source changes for the remaining new tests (PR1, PR2, PR5, PX6 routed
use and refusals, and passing the probe_owner path through). Those tests passed on their first run; there was no
red run for them.

## Deviations (parent-approved)
- Explicit `--queries` on probe_owner.main and browser_session.main.
- PX1, PX6, PR1, PR2 and PR5 use the real admitted route provider when routing is configured. They still refuse
  when admission is absent. No safety refusal was weakened.

## Not done / owner
Every runbook step is an owner action and has not been run. A failing live gate blocks only LIVE-READY.
