# Report: T65 (S-T9) resource-host allowance

## 1 Task ID
T65 (S-T9), branch claude/t65-dit-s-t9-resource-hosts, base origin/main (e3fcc36).

## 2 Outcome
Done. All gates green; one draft PR opened, not merged.

## 3 Summary
- New stdlib-only `route_guard.py` (`host_label`, `summarise`, `describe`, `decide`, `make_handler`); `fetch_tier2.py` uses it and now stores host labels only (`blocked_url` is a host, new `blocked_hosts`), names blocked hosts in the refusal detail, logs it.
- `ApprovalRecord.resource_hosts` + `check_resource_hosts` (at load and in `approvals add`); `approvals add --resource-host H` needs `--owner-statement` naming each host; `FetchPass.resource_hosts` (tier >= 2 only); provenance `resource_hosts` key; docs lines 420 and 438 (+448 B).
- Red-first: on base the two tooling modules errored at collection and the 3 guard tests failed (browser file needs the new field).
- Known limits: the browser test file is Hybrid (needs Chromium; ran locally via the pre-installed Chromium over loopback, 2 passed) and its second test is a smoke check, not a full CONNECT-target proof; websocket is proven in `decide` only; listed hosts see the cloud IP; no real scrape was run.

## 4 Files changed
route_guard.py (new), fetch_tier2.py, gate.py (slots, init +1 line, line 95 return only), approvals.py, approval_cli.py, provenance.py (one key), docs lines 420/438; tests test_route_guard, test_resource_hosts, test_tier2_resource_browser, api/tests/tooling_guards/test_resource_host_guard.py.

## 5 Commits
One commit on the task branch (see PR).

## 6 Tests run
Baselines on untouched origin/main (2026-10-15T19:41Z, e3fcc36): tooling 544 passed; guards 53; API 1196 passed/1 skipped/5 deselected.
After (2026-10-15T19:50Z, branch head before commit e3fcc36 + changes): tooling 601 passed/3 deselected (544 + 57 new); guards 56 (53 + 3); API 1199 passed/1 skipped/5 deselected (1196 + 3). Browser file with -m browser: 2 passed. `git diff --exit-code api/uv.lock api/pyproject.toml` clean; `git diff --check` clean; cli.py and types.py untouched; gate.py diff in the three allowed spots.

## 7 Tests NOT run
Real scrape, network, npx/REA, scrapling install, playwright install.

## 8 Deviations
Docs delta +448 B, below the +550 B allowance. `fetch_tier2.py` keeps `blocked_url` (now a host label) for existing stubs.

## 9 Blockers
None.

## 10 Follow-up
Planner checklist in A3 (decisions D-15, README line, MASTER-PLAN P9, SPEC AC-28..32). Strengthen the CONNECT-recorder browser test when a loopback HTTPS target exists.

## 11 Context cost
Extra reads beyond the envelope: approvals.py 100-200, test_tier2_browser.py head, _helpers.py, tooling_guards/_common.py. Provenance read only around the key.
