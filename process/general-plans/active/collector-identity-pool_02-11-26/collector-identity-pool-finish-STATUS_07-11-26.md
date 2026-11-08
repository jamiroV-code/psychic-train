# Finish program status and resume handoff (07-11-26)

Branch `claude/b2-validate` (draft PR #246). Plan: `collector-identity-pool-finish_PLAN_06-11-26.md` (revision 3 + F1-F10 + probe fold-ins, strict validator green). Paused at an Anthropic rate limit (retry window about 3.8 h from 07-11-26 evening); nothing is lost, everything below is committed and pushed.

## Owner decisions on record
- Reddit = live identity route only (archive declined). Gateway parked. Option B on old feed methods not wanted. Commit + draft PR approved. Fix scope: B2-only production changes beyond the plan; the equities/signal test failures belong to another session.

## Landed (committed)
| Stage | Slice | Commit |
|---|---|---|
| prior | B2 | 7bbd48ca |
| 0 | S-Canon | de1d2629 |
| 1 | S-Config | de1d2629 |
| 2 | S-Facts | b0272171 |
| 2 | S-Fixtures | 45ab4e9f |
| 2 | S-StatusAPI | f931d037 |
| 2 | S-RCore-A | d42da2e5 |
| 3 | S-XProto | a4d3509b |
| 3 | S-BrowserHost | d22779e9 (+ report c837c6ef) |
| 3 | S-RAcct-A | baed32cd (+ guard fix: print removal in reddit_accounts.py, 40 tests green) |
| 3 | S-RDisc | 729125c1 |

Each slice has an 11-heading report in this folder: `collector-identity-pool-finish-<SLICE>_REPORT_07-11-26.md`.

## Not started (resume here)
Stage 4: S-XDrift, S-BrowserCDP (both died instantly on the rate limit, no edits).
Stage 5: S-XCookie, S-B3P, S-RCore-B, S-Relay. Stage 6: S-RAcct-B, S-Cookie-C, S-StatusUI. Stage 7: S-OpsProbe, S-B3I. Stage 8: S-RGQL, S-Cookie-X, S-B3R. Stage 9: S-RBrowser. Stage 10: S-Report. Stage 11: S-OpsDoctor. Stage 12: S-OpsDeploy, S-E2E-Cycle. Stage 13: S-E2E-UI. Stage 14: G-FINAL.

## How to resume
1. Read the plan slice section, the shared contracts it cites, and the prior slice reports for interfaces.
2. Dispatch Stage 4 workers with the same envelope used for Stage 3 (see the plan; owned files only, red tests first, targeted tests only, commit own paths, no push).
3. Stage gate after each stage: run `api/tests/analytics/attention/`, `api/tests/data/attention/`, `api/tests/tooling_guards/` once on the combined tree.

## Contracts later slices must honour
- S-StatusAPI fixed on-disk layouts: `reddit_live/<store>_health.json`, `reddit_accounts.json`, `reddit_account_ready.json`, `x_queryids.json`, `daily_report_<D>.json`, `doctor.json`, `browser_health.json` (report section 7). Writers match them or the status shows `unknown`.
- S-RAcct-A admission seam: `admission(site,label) -> "proxy"|"direct"|"unadmitted"`, default-deny; S-RAcct-B supplies the authoritative provider.
- S-XProto standalone `x_queryids_fetch.run_check(config,cache_root,now,route=None,policy=None)`; S-XDrift wires it at unit boundaries and implements forced candidate evaluation. S-RAcct-B must keep the approved amendments to `x_proxy_runtime.one_shot` and `test_x_proxy_spawn.py`.
- S-RDisc `discovery_history.method_switches()` is a read-only diagnostic for S-StatusUI / S-Report.
- S-BrowserHost: `BrowserHost.launch(...).pipe`, `write_admission/read_admission`; Windows launch only (POSIX path not done, plan decision pending); relay port is passed in by S-Relay.

## Live gates (block LIVE-READY only, never CODE-COMPLETE)
- BG-1 FAIL on Edge 157: Edge browser process makes direct TCP 443 connections to Microsoft addresses the relay cannot see; Cast/MediaRouter LAN leak fixed by flags.
- BG-3 NOT-MET: capability-SID ACEs (`DeriveCapabilitySidsFromName("lpacEdgeStableNetworkSandbox")`) and an Everyone execute-only ACE on LevelDB files.
- BG-2 pipe verified on Edge 156, re-confirm on 157.

## Owner decisions pending (do not block code)
- O-1 accept/reject CE-1 (capability-SID ACEs). O-1b accept/reject CE-2 (Everyone execute-only on LevelDB). O-2 browser-process residual: accept hash-bound residual / apply generated firewall rule / neither (browser Reddit then stays missing-not-zero).
- If PR1/PR2 fail or real Reddit responses do not fit the grammar: accept missing-not-zero, authorize a grammar extension, or revive the archive.
- Owner to create 2 (max 3) Reddit throwaway accounts now so the one-week rest runs during the build; accounts/proxies for X as in the SPEC.

## Verification state
Slice-level targeted tests green per reports. No full-suite or browser run on the combined tree since B2. Known unrelated failure: `test_equities_store::test_path_override_honoured_at_call_time` (another session). CI on PR #246 not yet checked.

## Update 07-11-26 (later): Stages 4-6 landed
S-XDrift 3510c1e4, S-BrowserCDP 8b2a2eb2, S-XCookie e0ac966b, S-B3P bdee4513, S-RCore-B 6540bc0e/7b78bb13, S-Relay 1f4447a7, S-StatusUI 1707c958, S-Cookie-C f18b8f42, S-RAcct-B 27faf8dd/3005a055. Stage 5 gate on combined tree: 3509 passed, 1 failed (known unrelated equities Windows test), 4 skips. Resume at Stage 7: S-OpsProbe, S-B3I; then Stage 8 S-RGQL, S-Cookie-X, S-B3R; Stage 9 S-RBrowser; Stage 10 S-Report; Stage 11 S-OpsDoctor; Stage 12 S-OpsDeploy, S-E2E-Cycle; Stage 13 S-E2E-UI; Stage 14 G-FINAL.
Open wiring items: Reddit admission provider/route adapter (AdmittedRoute from snapshot.reddit_assignments + revisions) is S-RBrowser/S-Cookie-X; X day guard wiring is S-Cookie-X; method_switches diagnostic not on the API (S-Report/S-StatusAPI follow-up); X new status fields not yet produced (S-B3I/S-Cookie-X); POSIX browser launch path undone.

## Update 07-11-26 (Stage 7 paused at a second rate limit)
Stage 7 (S-OpsProbe, S-B3I) is IN PROGRESS with substantial UNCOMMITTED work in the tree (also saved to branch `claude/b2-wip`, commit a1847597, not for merge): api/scripts/probe_owner.py, probe_executors.py, surface_tool.py + tests (test_probe_owner/test_probe_executors/test_surface_tool, reddit_probe_fixtures); S-B3I partial edits to twscrape_reader.py, x_pool.py, x_proxy_snapshot.py, x_raw.py, x_reader.py, attention_pc_refresh.py and test_x_b3_integration.py, plus draft reports for both slices. Neither slice has been run green or committed; treat as WIP and have the next worker read `git status`/`git diff` first.
Parent decisions to honour: S-OpsProbe = protocol layer + executors for PX1-PX6 and PR4-PR6; PR1/PR2 executors registered later by S-RGQL/S-RBrowser (executor_pending state meanwhile); PR3 = executor_refused:a17_cookie_boundary. S-B3I authorized: low-level single-page mixed-op helper in twscrape_reader.py bypassing Ctx.req and _check_rep, child envelope v2 variation fields, x_raw.py page-size exactness (all recorded deviations; security re-read needed).
Tip: re-dispatch on FRESH sessions (resumed sessions fall back to an exhausted model).

## Update 07-11-26: owner created 2 Reddit throwaway accounts
Owner reports 2 Reddit throwaway accounts created on 07-11-26 (usernames/passwords held privately by the owner, never in the repo). One-week rest runs to 14-11-26 (config `reddit_account_rest_days` applies). Profiles are created by the collector (browser_profile) and logged in once via `browser_session --init-profile` then `--interactive`; that stays refused until O-1/O-1b/O-2 are decided. S-OpsProbe committed 818c3bd6 (53 tests green).

## Owner decisions 07-11-26 (recorded)
- O-2 containment: FIREWALL RULE (generate-only text from S-OpsDeploy `browser_firewall_rule.py`; owner reviews and applies; note it applies to the Edge executable path for every use unless scoped to a dedicated Windows user).
- O-1 and O-1b: ACCEPTED (CE-1 derived capability-SID ACEs at the pinned locations/masks; CE-2 Everyone S-1-1-0 execute-only mask 32 on LevelDB files). Sandbox stays on. Still pending: BP3c pin verification at first admitted session; owner `--approve` for the acceptance record is a runtime step.
- Reddit fit: EXTEND PARSER authorized once real captures exist (grammar extension via the capture-to-surface workflow; archive route stays declined).
- Reddit accounts: 2 created 07-11-26 (rest to 14-11-26). X accounts/proxies: owner asked how many are needed (sizing: about 4 X accounts, 6 worst case at the 800-read cap for the 72-coin universe; Reddit browser needs 2, one active at a time).
Stage 7 done: S-OpsProbe 818c3bd6, S-B3I efaceab7 (security re-read pending for child envelope `count` and single-page `ordinary()` helper).

## Update 08-11-26: stages 7-12 landed except S-E2E-Cycle (paused at rate limit)
Landed: S-OpsProbe 818c3bd6, S-B3I efaceab7, S-B3R 15b37868, S-RGQL 203f4b5a, S-Cookie-X 742727e6, S-RBrowser 98645de5, S-Report 57ec4293, S-OpsDoctor 399ccddc, S-OpsDeploy 32eb1da5 (runbook in deploy/README.md; firewall tool generate-only).
IN PROGRESS: S-E2E-Cycle (api/tests/cycle/*): UNCOMMITTED partial (C1-C2 pass, C4 being fixed, C3/C5-C14 not written); saved on branch `claude/b2-wip`. Resume on a FRESH session (resumed sessions fall back to an exhausted model). Then Stage 13 S-E2E-UI, Stage 14 G-FINAL (evidence pack, consolidated regression C15, security re-reads for: child envelope count field, single-page ordinary() helper, open_browser/RedditRoutes, relay).
Owner actions pending: create 2 more X accounts (rest week), firewall rule apply, private files per runbook, probes with --approve.
