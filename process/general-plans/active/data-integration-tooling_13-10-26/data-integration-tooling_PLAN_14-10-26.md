---
name: plan:data-integration-tooling
description: "Developer-run data integration tooling (allow-listed REA wrapper + Scrapling tiers 1-3) as a separate uv project tools/data-integration, with approval gate, provenance, adaptive store, docs workflow and a first long-BTC-history run. Nine slices S-T0..S-T6 (T3 split a/b, T5 split a/b). Revised after PVL cycle 1."
date: 14-10-26
feature: general-plans
---

# Data Integration Tooling: Plan (S-T0 to S-T6)

Date: 14-10-26 (revised after PVL cycle 1). Base: origin/main b66d9b4. SPEC: `data-integration-tooling_SPEC_13-10-26.md` (same folder).
Status: PLANNED, VALIDATE pending.
Complexity: COMPLEX (nine slices, new tooling project, approval enforcement, docs and router edits).

**TL;DR:** Everything new lives in `tools/data-integration/` (own uv project, never imported by the API, never in CI install). One gate `request_access` must hand out a host-bound `FetchPass` before any HTTP client exists. REA is a pinned, allow-listed wrapper only (setup is never run). Provenance is a separate `<dataset>.provenance.json`. Estimate 23.3-40.5 USD (midpoint 31.9). Worker spend so far 86.13 of 100 USD ceiling; about 13.9 left; the owner must decide a new ceiling before EXECUTE.

Context Envelope: general-plans | PLAN | data integration tooling | claude/plan-data-integration | /home/user/psychic-train | data-sources | tools/data-integration, api/tests/tooling_guards, process/ | this file | pytest (api) then pytest (tooling env) | pending VALIDATE.

## Slice index (line ranges of THIS file; a worker reads CLAUDE.md + envelope + Common rules + its own range + the files named in its Envelope hint)

Read cap 36,000 B = CLAUDE.md 13,443 + envelope 4,000 (assumed) + Common 6,060 B + slice + files. Each slice's hint gives the resulting total. Workers do NOT read the full SPEC.

| Slice | Objective | Lines | Depends | Wave | Est. USD (low-high) |
|---|---|---|---|---|---|
| Common | Locks, gates, safety, envelope rules | 40-75 | none | all | n/a |
| S-T0 | SPEC amendments only | 76-87 | none | 1 | 0.8-1.5 |
| S-T1 | Skeleton, isolation, CI-visible guards, markers, install check | 88-100 | none | 1 | 3.0-5.0 |
| S-T2 | Approval gate, local store, status/add CLI, store guards | 101-113 | T1 | 2 | 2.5-4.0 |
| S-T5a | REA wrapper code, evidence template, tests | 150-162 | T1 | 2 | 2.5-4.0 |
| S-T3a | Tier 1 fetch, robots, politeness, errors, logs, response cache | 114-125 | T1, T2 | 3 | 3.0-5.0 |
| S-T3b | Parse, validate, normalise, cache write, provenance, adaptive | 126-137 | T1, T2 | 3 | 4.0-7.0 |
| S-T4 | Tiers 2 and 3, robots-before-navigation, probe scripts | 138-149 | T3a, T3b | 4 | 3.5-6.0 |
| S-T5b | Docs section, router row, validators | 163-173 | T0, T5a | 4 | 1.5-3.0 |
| S-T6 | First dataset: long BTC history, workflow steps 1-4 | 174-184 | T0, T5a, T5b, T3b | 5 | 2.5-5.0 |
| Rest | Planner-side records, decision record, limits, risks, evidence, handoff | 185-285 | n/a | n/a | n/a |

Total 23.3-40.5 USD, midpoint 31.9. Basis: past workers S9A 3.62, S9B 1.72, S9C 3.38, S9D 3.38, S9F 1.01, S9E 3.59 USD (backend and mixed); S5b 9.99 (large UI slice, passed the 7 USD ask point). Per-slice cap 15 USD, ask point 7 USD. Highs are raised above past analogues for S-T1 (first uv project plus lock, S9B 1.72 is too low), S-T3b (first-use Scrapling adaptive, S9E/S9C undercount) and S-T4 (browser probe loop). Cost check: lows 0.8+3.0+2.5+2.5+3.0+4.0+3.5+1.5+2.5 = 23.3; highs 1.5+5.0+4.0+4.0+5.0+7.0+6.0+3.0+5.0 = 40.5. Wave 1 + wave 2 alone cost 8.8-14.5. Worker spend so far 86.13 of 100 USD ceiling; about 13.9 left; the owner must decide a new ceiling before EXECUTE.

Waves (max 2 workers at once, one slice each, planner merges a wave before the next): 1 = S-T0 + S-T1; 2 = S-T2 + S-T5a; 3 = S-T3a + S-T3b; 4 = S-T4 + S-T5b; 5 = S-T6. S-T3a and S-T3b run together because S-T1 pre-defines the shared interfaces (`types.py`, `status.py`).

## Common rules

### ACs whose wording changes (applied by S-T0 to the SPEC)

AC-19: "A pinned REA version, an allow-listed wrapper, an evidence template (VERIFIED/ASSUMED) and a 'what REA cannot establish' statement exist; the API does not import REA; no agent-config file is changed by this work (worker gate: `git diff origin/main...HEAD` on `.claude/`, `CLAUDE.md`, `AGENTS.md`, `.mcp.json` is empty; NOT a CI check)." AC-23 replaced: "The wrapper rejects setup, update, uninstall, mcp and every non-allow-listed command (test)." OQ-13 closed: web/static commands only. L3 rewritten to wrapper-only (DIT-6). AC-2: guard lives in `api/tests/tooling_guards/`, file-only import scan, new tooling entry points only. AC-4: exact package names in `api/pyproject.toml` and `api/uv.lock`, and workflows contain no `tools/data-integration`. AC-5: Hybrid scripted install check. AC-6: also covers tiers 2 and 3 (robots before navigation). AC-10 and AC-22: "provenance file" instead of "sidecar". AC-11: round trip through the cache read functions unchanged. AC-15: static marker audit plus markers `browser`, `antibot`; CI runs only the API job. AC-16/AC-17: owner-run scripts (AC-17 after the opt-in browser install). AC-20: DIT-9 (new cache key). AC-21: also the approvals folder pattern. OQ-12 closed with the DIT-8 path. SPEC INNOVATE questions 1-8 answered by DIT-1..9.

### Locked decisions (owner APPROVED 14-10-26; one line each; full record with rejected alternatives is in "Decision record")

- DIT-1 separate uv project `tools/data-integration/` (src layout, hatchling build-system `packages = ["src/data_integration"]`, requires-python >=3.12, exact pins `scrapling[fetchers]==0.4.15`; `pandas`, `pyarrow`, `duckdb` pinned to the versions in `api/uv.lock`); imports `api.data.cache` with the repo root on the path via `paths._repo_root()`; never imported by the API; API wheel unchanged; not in any CI step; installed on demand with `uv sync --project tools\data-integration`; `scrapling install` is a separate opt-in.
- DIT-2 one gate `request_access(source, tier, store, clock) -> FetchPass | Refused`; FetchPass is host- and page-bound; refusal before any HTTP client exists; import-boundary test in S-T1.
- DIT-3 `<dataset>.provenance.json` beside the data (list of records, approval facts copied); `.meta.json` and `api/data/cache.py` untouched.
- DIT-4 adaptive SQLite store machine-local outside the repo and outside site-packages; write only after validation.
- DIT-5 mocks plus loopback fixture server; markers `browser`, `antibot`; tier 3 not proven against any real site.
- DIT-6 REA wrapper only: never run `setup`, no MCP, no `.mcp.json`, no agent-config change.
- DIT-7 docs: one section in `all-data-sources.md`, one row in the hand-written Task Routing Table of `all-context.md`.
- DIT-8 approvals: one `<source>.approval.json` per source under `%LOCALAPPDATA%\my_site\approvals\` (env `DIT_APPROVALS_DIR` for tests).
- DIT-9 first dataset: long BTC history, new cache key `BTC-HIST`, never replacing the existing BTC series.

### Gate conventions (all slices)

1. API gates: `UV_FROZEN=1 uv run --project api pytest <paths> -q`; full run `UV_FROZEN=1 uv run --project api pytest api/ -q`. Log baseline counts on the untouched base (report heading 6); a count differing from the slice arithmetic stops at `needs_input`.
2. Tooling gates (after S-T1): `UV_PROJECT_ENVIRONMENT=$HOME/.cache/dit-env uv run --project tools/data-integration pytest tools/data-integration/tests -q`. Never export `UV_FROZEN=1` for the tooling before its `uv.lock` exists. The out-of-repo environment path is required in cloud runs: a harness hook blocks command text containing venv, node_modules, dist, build, target, vendor, coverage; do not use those words in tool commands and do not name tooling folders that way. Read library source with `uv run --project tools/data-integration python -c "import inspect, scrapling; ..."`, not Read/Grep inside the environment (known limit; do not edit the hook config).
3. Red-first: new tests are failing stubs on the untouched base, record the red count, then real tests. Plain test functions only. S-T1 guards must also PASS on the untouched base for the unchanged parts (record green-on-base).
4. No existing test file is edited. Max 2 fix cycles per gate; the same failure twice stops.
5. Known-Gap is a residual (backlog stub, gate stays CONDITIONAL), never PASS. Probes (P-*) belong to the owner.
6. A diff touching `CLAUDE.md`, `AGENTS.md`, `.claude/`, `.mcp.json`, `.github/`, `deploy/`, `api/uv.lock`, `api/pyproject.toml`, `api/data/cache.py`, `process/MASTER-PLAN.md` or `process/context/decisions.md` stops at `review` (exceptions are named in the slice). `git diff origin/main...HEAD` checks are worker gates, never CI tests (shallow checkout).
7. `git diff --check origin/main...HEAD` exits 0; plan, report and envelope files are ASCII.

### Safety rules (every slice)

No secrets, keys, IPs or user names in files, logs or commits (never print a full local path). Synthetic fixtures only. No live network in tests except the loopback fixture server; the single documented exception is the one real `npx -y rea-agents@6.4.0` call, run only by the developer/tester explicitly (S-T5a). Scraping only by explicit developer command; never without an approval record; the cloud sandbox never performs a real scrape. Tooling tests run with an isolated cache root (S-T1 autouse fixture) so the owner's real cache is never touched. No change to production config, credentials, DB or deploy scripts without owner authorisation.

### Worker envelope standing rules

First line `ROLE: WORKER`. Branch `claude/<task-id>-<slice>-<slug>` from main, open a PR. Envelope text: "After your report, stop; do not wait on CI or check in. needs_input means STOP: do NOT merge, do NOT open a new PR." The worker never merges and never edits `process/MASTER-PLAN.md` (only the Master Planner does). The planner measures cost after idle. Spend cap 15 USD, ask at 7 USD. Extra docs a worker opens are noted in report heading 11.

## S-T0: SPEC amendments (docs only, RT0, worker)

**Objective.** Make the SPEC match the approved decisions before code starts.
**Owned:** `process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling_SPEC_13-10-26.md` ONLY.
**Depends:** none. **ACs:** wording of AC-2, 4, 5, 6, 10, 11, 15, 16, 17, 19, 20, 21, 22, 23; closes OQ-12, OQ-13; rewrites L3.
**Steps.** Apply the list "ACs whose wording changes" to the SPEC; add a change-log line dated 14-10-26; keep AC numbering; mark INNOVATE questions answered. Each remaining SPEC line that mentions `rea-agents setup` must contain "rejected" or "superseded".
**Tier.** RT0. Gates: `git diff --stat origin/main...HEAD` lists exactly the SPEC file; `grep -n "rea-agents setup" <SPEC>`: every line has "rejected" or "superseded".
**Done when:** gates pass; owner reviews at `review`.
**Must NOT:** touch code, other plans, MASTER-PLAN, decisions.md, CLAUDE.md or any agent config.
**Cost:** 0.8-1.5 USD; basis S9F 1.01.
**Envelope hint:** read Common + this range and SPEC lines 29, 91-116, 147-148, 150-173 (5,917 B). Total about 13,443+4,000+6,060+1,174+5,917 = 30,594 B.

## S-T1: Skeleton, isolation, CI-visible guards (RT2)

**Objective.** Create the tooling project (importable, with correct pins) and the guards that protect the API install.
**Owned:** `tools/data-integration/{pyproject.toml,uv.lock,README.md}`, `tools/data-integration/src/data_integration/{__init__,types,status,paths}.py`, `tools/data-integration/scripts/check_clean_install.py` (AC-5 script), `tools/data-integration/tests/{conftest,test_skeleton}.py`, `api/tests/tooling_guards/{__init__,test_tooling_isolation,test_import_boundary,test_marker_audit}.py`, `.gitignore` (append only). `uv.lock` is generated.
**Depends:** none. **ACs:** AC-2, AC-4, AC-5, AC-15, AC-21 (gitignore half).
**Contents.** pyproject per DIT-1: scrapling `[fetchers]==0.4.15`, pandas/pyarrow/duckdb equal to `api/uv.lock` versions, dev group pytest, hatchling build-system, pytest `pythonpath = ["../..","src"]`, markers `integration`, `browser`, `antibot`, `addopts = "-m 'not integration and not browser and not antibot'"`. `types.py`: `FetchOutcome`, `Fetcher` protocol `fetch(url, pass_) -> FetchOutcome`, `ParsedTable`. `status.py`: the closed status set (ok, refused, robots_blocked, timeout, connection_failed, http_error, challenge_page, changed, uncertain, invalid, cache_hit; extend only here). `paths.py`: `_repo_root()` (puts the repo root on `sys.path` for CLI and probe runs), approvals dir, scrape dir, evidence dir from `%LOCALAPPDATA%\my_site\` with env `DIT_APPROVALS_DIR`, `DIT_SCRAPE_DIR`, `DIT_EVIDENCE_DIR`. `conftest.py`: autouse fixture sets `SCREENER_CACHE_ROOT` (before first import) and patches `cache.CACHE_ROOT` to `tmp_path`, plus a guard that the real cache path is untouched (like `api/tests/deploy/test_zz_real_data_guard.py`). `.gitignore` adds `*.approval.json`, `**/approvals/`, `**/scrape/*.sqlite*`, `tools/data-integration/.venv/`.
**Guards (stdlib only, never import scrapling; exact names, no substring matching).** Compare normalised requirement names parsed from `[project].dependencies` and `name = "..."` in `uv.lock`: none of `scrapling`, `playwright`, `patchright`, `rea-agents`; `api/pyproject.toml` hatch packages equal `["analytics","data","models","routers"]`; workflows contain no `tools/data-integration` (do NOT scan for the word playwright: ci.yml:9 has a comment); `git ls-files` shows no `*.approval.json` and `.gitignore` carries the pattern; `test_import_boundary.py` (file-only AST/text scan of `tools/data-integration/src`): only `fetch_tier1/2/3.py` and `robots.py` may import scrapling fetchers, urllib.request, http.client, httpx, requests, socket, playwright; and no `.py` under `api/` outside `api/tests/tooling_guards` and no workflow mentions `data_integration`. Marker audit (static): a tooling test file importing scrapling, `data_integration.fetch_tier*` or a network module must mark every test `browser`/`antibot`/`integration` or use the `fixture_server` fixture (owned by S-T3a).
**Tier.** RT2. Gates: red-first; `UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards -q` (green on base for unchanged parts); `uv lock --project tools/data-integration` then the tooling gate; `python tools/data-integration/scripts/check_clean_install.py` (Hybrid: temp env sync, then `uv lock --check --project api` and `git diff --exit-code api/uv.lock` exit 0); import probe `uv run --project tools/data-integration python -c "import sys; from api.data import cache; assert not {'fastapi','ccxt','pandas_ta_classic'} & set(sys.modules)"` exits 0 (if it fails: stop at `needs_input`).
**Done when:** gates green on the head SHA; full api pytest = baseline + new guard tests.
**Must NOT:** edit `api/pyproject.toml`, `api/uv.lock`, workflows, `api/data/cache.py`; add the tooling to any sync step.
**Cost:** 3.0-5.0 USD; basis S9B 1.72 raised for lock generation, 4 guards, install script.
**Envelope hint:** read Common + this range, `api/data/cache.py` lines 1-30 (1,106 B), `.gitignore` (about 2,000 B). Total about 13,443+4,000+6,060+4,012+3,106 = 30,621 B.

## S-T2: Approval gate, local store, store guards (RT2)

**Objective.** Make "no record, no fetch" mechanically true.
**Owned:** `tools/data-integration/src/data_integration/{approvals,gate,approval_cli}.py`, `tools/data-integration/tests/{test_gate,test_approvals_store,test_approval_cli}.py`, `api/tests/tooling_guards/test_approval_store_guard.py`.
**Depends:** S-T1. **ACs:** AC-1, AC-3, AC-21 (store + index), AC-22 (approval facts shape).
**Contents.** `approvals.py`: record (id, source, allowed_tier 1-3, allowed hosts and pages, rate policy, robots check date, alternatives checked, owner, approval date, expiry = approval + 90 days default, revision); expiry stored as UTC ISO-8601 with `Z`; atomic write with revision (pattern of `api/data/layout.py`); corrupt file renamed `.bad`; never creates a default record. Source names must match `^[a-z0-9][a-z0-9_-]{0,63}$` (2-64 chars, no dots, slashes, reserved Windows names) BEFORE any path is built. `gate.py`: `request_access(source, tier, store, clock) -> FetchPass | Refused`; `Refused.reason` in missing|expired|tier_too_low|store_missing|store_corrupt|bad_clock plus source, tier_asked, tier_allowed, expiry; expiry is `now >= expiry`; a naive or missing-tz clock or stored timestamp yields `bad_clock`/`store_corrupt`, never an exception. `FetchPass` is bound to the approved host(s) and allowed pages with a method `permits(url)`; private constructor token; `isinstance` on the real class is required by consumers. `approval_cli.py` (Python): `status` lists source, tier, expiry, days left (shows `%LOCALAPPDATA%\my_site\approvals`, never the real path, says whether the env override is active); `add` refuses without an interactive TTY and requires the owner to type the source name to confirm.
**Tests (plain functions, fixture records in `tmp_path`).** missing store/file, corrupt file, expiry boundary (exactly at, one second before), tier above, tier equal/below, naive clock, future approval date, bad source names (`../x`, `a.b`, `CON`), pass for host A refuses host B, duck-typed pass rejected, zero-client counter on every Refused reason, atomic write failure leaves no partial file, status output has no secret-like strings, `add` refuses non-TTY, approvals dir is gitignored and absent from the index.
**Tier.** RT2. Gates: tooling pytest; `UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards -q`.
**Done when:** both suites green; no `*.approval.json` appears outside `tmp_path`.
**Must NOT:** write to a real `%LOCALAPPDATA%`/home path; ship sample approvals; touch fetch code.
**Cost:** 2.5-4.0 USD; basis S9C 3.38.
**Envelope hint:** read Common + this range, `types.py`, `status.py`, `paths.py` (est. 3,900 B), `api/data/layout.py` lines 106-142 (1,125 B). Total about 13,443+4,000+6,060+2,808+5,025 = 31,336 B.

## S-T3a: Tier 1 fetch, robots, politeness, errors, logs, cache (RT2)

**Objective.** A polite, gated, fully mapped tier-1 fetcher.
**Owned:** `tools/data-integration/src/data_integration/{fetch_tier1,robots,politeness,logging_setup,response_cache}.py`, `tools/data-integration/tests/{fixture_server,test_fetch_tier1,test_robots,test_politeness,test_logging,test_response_cache}.py`, plus the `fixture_server` pytest fixture inside `tools/data-integration/tests/fixture_server.py` (registered by a `tools/data-integration/tests/plugin_fixture_server.py` loaded from `test_*` imports; do not edit `conftest.py`).
**Depends:** S-T1, S-T2. **ACs:** AC-6 (tier 1), AC-7, AC-12 (fetch half), AC-13, AC-14.
**Contents.** `fetch_tier1.fetch(url, pass_)` requires a real `FetchPass`, checks `pass_.permits(url)` and every redirect target (robots per hop), builds the client only afterwards. `robots.py`: the robots.txt fetch itself requires a pass, shares UA, politeness and logging, fails closed (unreachable, timeout or unparsable robots = refuse). `politeness.py`: per-host min delay, global and per-host concurrency, honest user agent without contact data, injectable clock and sleeper. `response_cache.py`: second call returns `cache_hit` with zero requests; forced refresh makes one allowed request. Errors (timeout, refused connection, 4xx/5xx, challenge-page markers) map to the closed status set; no exception escapes. `logging_setup.py`: one structured line per request (host, path, status, duration, tier; no headers, cookies, query strings or IPs). `fixture_server.py`: loopback `http.server` on port 0 with routes ok, slow, 500, redirect (same and other host), robots disallow, robots 500, challenge page.
**Tier.** RT2; the loopback server is allowed (not external). Gates: tooling pytest; burst test with fake clock.
**Done when:** suite green; log capture has no secret-like text; zero-client counter on refusal.
**Must NOT:** import `parse`, `normalise`, `pipeline`; touch `api/`; contact a non-loopback host.
**Cost:** 3.0-5.0 USD; basis S9A 3.62.
**Envelope hint:** read Common + this range, `types.py`, `status.py` (2,400 B), `gate.py` signatures via `grep -n "def \|class "` (about 1,500 B). Total about 13,443+4,000+6,060+2,261+3,900 = 29,664 B.

## S-T3b: Parse, validate, normalise, store, provenance, adaptive (RT2)

**Objective.** Turn a fetched page into validated cache data with provenance and honest change detection.
**Owned:** `tools/data-integration/src/data_integration/{parse,validate,normalise,store_writer,provenance,adaptive,pipeline}.py`, `tools/data-integration/tests/{test_parse,test_validate,test_normalise_roundtrip,test_provenance,test_adaptive,test_pipeline}.py`, synthetic fixtures under `tools/data-integration/tests/fixtures/`.
**Depends:** S-T1, S-T2 (tests use a fake Fetcher, not S-T3a). **ACs:** AC-8, AC-9, AC-10, AC-11, AC-12 (pipeline half), AC-22.
**Contents.** `parse.py`: explicit table helper (Scrapling has none), selectors via Scrapling Selector with adaptive. `validate.py`: required columns, types, ranges (positive prices, monotonic time, high >= low), minimum rows; failure gives `invalid`, nothing written. `normalise.py`/`store_writer.py`: write only through `cache.write_ohlcv` into a cache key supplied by the caller (it replaces the whole series: the pipeline refuses when the target key already holds data unless `replace=True` is passed explicitly). `provenance.py`: append to `<dataset>.provenance.json` beside the data file (fields per DIT-3, approval facts copied from the FetchPass), atomic write; a test proves `cache.write_ohlcv` afterwards leaves it intact. `adaptive.py`: SQLite store via `paths.py` (outside repo and site-packages; test fails inside site-packages); lost store gives `uncertain` on first run; relocated or unmatched gives `changed`/`uncertain`, never a guess, nothing stored. `pipeline.py`: fetch (any Fetcher) -> parse -> validate -> adaptive -> normalise -> store -> provenance; writes only after all checks pass; a re-run with unchanged data leaves identical data and appends no provenance record.
**Tier.** RT2. Gates: tooling pytest; round trip read by `api.data.cache` and its freshness code unchanged.
**Done when:** suite green; a changed fixture yields `changed` and an empty cache dir.
**Must NOT:** edit `api/data/cache.py`; import `fetch_tier*`; write outside `tmp_path`; use the network.
**Cost:** 4.0-7.0 USD (highest risk of passing the 7 USD ask point); basis S9E 3.59/S9C 3.38 raised for first-use adaptive semantics.
**Envelope hint:** read Common + this range, `types.py`, `status.py`, `paths.py` (3,900 B), `api/data/cache.py` lines 118-131 and 158-187 (1,789 B). Total about 13,443+4,000+6,060+2,468+5,689 = 31,660 B.

## S-T4: Tiers 2 and 3, robots-before-navigation, probe scripts (RT2/RT3)

**Objective.** Browser and anti-bot tiers behind the same gate, plus the scripts the owner runs on Windows.
**Owned:** `tools/data-integration/src/data_integration/{fetch_tier2,fetch_tier3}.py`, `tools/data-integration/tests/{test_tier2_browser,test_tier3_gating,test_tier23_robots}.py`, `tools/data-integration/tests/fixtures/js_page/*`, `tools/data-integration/scripts/{probe_tier1.py,probe_tier2.py}`, `tools/data-integration/README.md` (append a probe section; S-T1 owns the file before).
**Depends:** S-T3a, S-T3b. **ACs:** AC-6 (tiers 2 and 3), AC-16 (script), AC-17 (script), tier-3 parts of AC-3 and AC-13.
**Steps.** (0) Probe: can the cloud Chromium (`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`; never run `playwright install`) serve the tier-2 fixture test? Record VERIFIED/UNVERIFIED; if unverified, mark browser tests `browser` and rely on the owner probe. (1) Tier 2: gated by FetchPass with allowed_tier >= 2, `permits(url)` and redirect check, robots first, JS fixture page parsed. (2) Tier 3: option pass-through only when allowed_tier == 3; block-style fixtures (challenge text, 403, captcha marker) map to `challenge_page`; no bypass claim. (3) `test_tier23_robots.py` (unmarked, stub navigator): robots.txt fetched from the loopback server before navigation; zero navigations when disallowed, unreachable or unparsable. (4) Probe scripts: `probe_tier1.py` loopback fetch/parse/store into a temp cache, prints PASS/FAIL; `probe_tier2.py` the same with a JS page and prints download-size hints and timing; each creates its own temp approval record; both call `paths._repo_root()`.
**Tier.** RT2 default run (no browser); `-m browser`/`-m antibot` only where a browser exists. AC-16 and AC-17 stay owner probes. Not proven live against any real site.
**Done when:** default suite green; browser tests green or documented unverified; probe scripts run (tier 1 in cloud).
**Must NOT:** run `playwright install`; touch real sites; claim tier-3 effectiveness; edit S-T3 modules (need a change -> `needs_input`).
**Cost:** 3.5-6.0 USD; basis S9D 3.38 raised for the browser probe loop.
**Envelope hint:** read Common + this range, signatures (grep def/class) of `fetch_tier1.py`, `gate.py`, `robots.py`, `fixture_server.py` (about 4,500 B), `status.py` (900 B). Total about 13,443+4,000+6,060+2,405+5,400 = 31,308 B.

## S-T5a: REA wrapper code, evidence template, tests (RT2)

**Objective.** The allow-listed, pinned REA wrapper.
**Owned:** `tools/data-integration/src/data_integration/rea/{__init__,wrapper,allowlist,evidence_template.md}`, `tools/data-integration/tests/{test_rea_wrapper,test_rea_evidence}.py`, `api/tests/tooling_guards/test_rea_guards.py`.
**Depends:** S-T1. **ACs:** AC-19 (amended), AC-23 (amended).
**Wrapper spec.** Runs `npx -y rea-agents@6.4.0 <command> --json` only. `allowlist.py`: an exact frozenset (case-sensitive, first token, no prefix or regex) of: analyze-javascript-application, recover-javascript-sources, compare-javascript-export-shapes, compare-application-versions, compare-source-to-bundle, trace-javascript-semantics, trace-application-feature, inspect-analysis-view, inspect-evidence-bundle, compare, compare-web-captures, compare-web-screenshots, inspect-web-network-capture, trace-web-module-imports, trace-web-source-location, export-web-scripts, and the live-browser group analyze-web-bundle, capture-web-screenshot, capture-browser-scenario, inspect-web-page. Live commands run only when the owner passes `--confirm-source <name>` and that name appears in a findings file given by `--findings`. Per-command flag allow-list: `--json`, `--source` (validated), an output path pinned inside the evidence folder; any other token starting with `-` (including `--update=x`, `--mcp`) is rejected. Everything else is rejected with a typed refusal and no subprocess: setup, update, uninstall, mcp, completions, native/APK/ADB/firmware/process/Apple/JEB/managed, runtime-capture/electron, unknown. Arguments: strict regex `^[A-Za-z0-9._/:@=-]{1,200}$`, forbid `" % ^ & | < >`; `subprocess.run([...], shell=False)`; on Windows resolve `npx.cmd` explicitly (arguments never pass through a shell); set `npm_config_ignore_scripts=true`. Output: stdout JSON (single object, 15 top-level keys, deterministic) saved to a dated folder OUTSIDE the repo (`%LOCALAPPDATA%\my_site\rea-evidence\<date>\`, env `DIT_EVIDENCE_DIR`, scratch dir in the cloud); redact `subject.local_path` and `normalized_result.input_path`; progress on stderr.
**Evidence template** (one note per source, public repo): header (source, REA version, date, command, raw output path), one line per finding tagged VERIFIED or ASSUMED, footer: "REA cannot see server-side methodology and does not search public datasets. Nothing above says how the numbers are produced on the provider's server."
**Tests.** Fake runner (no npx): every allow-listed command accepted; setup, update, uninstall, mcp, completions, `--update`, `--mcp`, `--update=x`, unknown, prefix and case variants, injection characters rejected with no subprocess call; redaction; evidence folder outside the repo; guard: no `api/` file imports the wrapper, `rea-agents` absent from api lock. The one real `npx` call is a developer/tester-only Hybrid check where Node >= 22.19 exists (static analysis was verified in the cloud workspace; live commands need a Chrome-family browser); it is the documented exception to "no network in tests".
**Tier.** RT2. Gates: tooling pytest; api guards pytest; worker gate (not CI): `git diff origin/main...HEAD -- .claude CLAUDE.md AGENTS.md .mcp.json` empty.
**Must NOT:** run `rea-agents setup`, create `.mcp.json`, edit agent configs, write evidence into the repo.
**Cost:** 2.5-4.0 USD; basis S9D 3.38 (new feature with strict tests).
**Envelope hint:** read Common + this range, `paths.py`, `status.py` (2,400 B). Total about 13,443+4,000+6,060+3,559+2,400 = 29,462 B.

## S-T5b: Docs section, router row, validators (RT0)

**Objective.** One documented workflow, reachable from the router.
**Owned:** `process/context/data-sources/all-data-sources.md` (add one section, at most 3,500 B), `process/context/all-context.md` (one row in the hand-written Task Routing Table only).
**Depends:** S-T0, S-T5a. **ACs:** AC-18.
**Contents.** Section 'New dataset workflow': 4 steps, evidence templates, approval fields, local-store backup guidance, the wrapper how-to, the rule "no scraped data in git-tracked directories without a recorded redistribution check", the statement that the Farside on-demand refresh is outside the tooling. Keywords (REA, scrapling, scrape, approval) go into the `all-data-sources.md` frontmatter. Do NOT hand-edit the `<!-- GENERATED:routing -->` tables. The row cites only existing backticked `process/...` paths.
**Tier.** RT0. Gates: `node .claude/skills/vc-context-discovery/scripts/discover-context.mjs --check-routing`; the planner-budget validator (records headroom; the planner fixed total was 53,040 of 56,000, headroom 2,960 B at plan time; the baseline already exits 1 because `process/context/current-state.md` is over its 8,000 B ceiling: record that as pre-existing, do NOT fix it here); `validate-all-context`; section size check `wc -c`.
**Must NOT:** touch any other doc; exceed 3,500 B; raise the router part of `all-context.md` over its 7,000 B ceiling (5,831 B at plan time).
**Cost:** 1.5-3.0 USD; basis S9F 1.01 plus validators.
**Envelope hint:** read Common + this range, `all-data-sources.md` lines 1-12 and 45-66 (about 3,500 B, E), the Task Routing Table rows of `all-context.md` (about 2,500 B, E). Total about 13,443+4,000+6,060+1,735+6,000 = 31,238 B.

## S-T6: First dataset, long BTC history, workflow steps 1-4 (RT1/RT2)

**Objective.** Run the real workflow once; scraping happens only with an owner approval.
**Owned:** `process/general-plans/active/data-integration-tooling_13-10-26/btc-history/{rea-findings,alternatives,redistribution}_REF_*.md` (types: PLAN|SPEC|REPORT|REF); only if step 2 finds an API/dataset: one adapter module plus test under `api/data/` and `api/tests/data/` whose names the worker proposes at `needs_input` for planner approval before writing code.
**Depends:** S-T0, S-T5a, S-T5b, S-T3b. **ACs:** AC-20 (owner review).
**Steps.** (1) REA findings note via the wrapper on candidate public pages, every line VERIFIED/ASSUMED. (2) Alternatives note: free APIs and public datasets first, with licences. (3) If suitable: integrate through the normal adapter path with provenance into the new cache key `BTC-HIST` (timeframe 1d); the existing BTC series is never replaced; the write refuses when `BTC-HIST` already holds data; output stays in the gitignored cache; redistribution check recorded. (4) If scraping is the only option: STOP at `needs_input` and ask the owner for an approval record; never scrape without one; never in the cloud.
**Tier.** RT1 for notes only; RT2 if an adapter lands (synthetic fixtures). Owner review is the proof for AC-20.
**Must NOT:** scrape; commit data into tracked dirs; create approval records; change cache code; write to any existing cache key.
**Cost:** 2.5-5.0 USD; basis S9E 3.59.
**Envelope hint:** read Common + this range, `evidence_template.md` (1,500 B), `all-data-sources.md` new section (3,500 B), `api/data/cache.py` lines 1-30 (1,106 B). Total about 13,443+4,000+6,060+1,721+6,106 = 31,330 B.

## Planner-side records (NOT worker slices; done by a planner-delegated records agent after S-T0 merges)

(1) `process/MASTER-PLAN.md`: ONE umbrella row P9 for the whole tooling programme (at most 600 B; file is 17,076 of 19,000 B, so eight rows would not fit). (2) `process/context/decisions.md`: add an Index row and entry D-15 "Data integration tooling" (sub-items DIT-1..DIT-9 with the rejected alternatives; ids D-1..D-14 exist; the paused market-framework SPEC's proposed D-15 will be renumbered when it resumes). (3) update `process/context/current-state.md` stamp. No worker edits these files.

## Decision record (rejected alternatives and evidence; workers need not read)

- DIT-1 rejected: optional group/extras in `api/pyproject.toml` (lockfile pollution); code inside the API package (accidental import). Verified recipe: with `scrapling[fetchers]==0.4.15`, pandas, pyarrow, duckdb, pytest, `uv lock` resolves 36 packages; repo root on the path lets `api.data.cache` import without fastapi/ccxt (`api` is a namespace package; `cache.py` needs duckdb, pandas, pyarrow). File-only guards live in `api/tests/tooling_guards/` (run by the existing CI job; never import scrapling); tooling tests that import scrapling run locally/by the tester, not in CI.
- DIT-2 rejected: convention-only, decorator-only. The Farside refresh (`api/analytics/regime/components.py:484` via `api/routers/regime.py:57`) is outside the tooling: neither broken nor covered. Gate and store use only the standard library.
- DIT-3 rejected: extending the `.meta.json` sidecar (existing writers overwrite it), parquet footer (no history). Raw snapshots default off, untracked.
- DIT-4: storage option `storage_args={'storage_file': ..., 'url': ...}` verified earlier by a run. Store path `%LOCALAPPDATA%\my_site\scrape\` (env `DIT_SCRAPE_DIR`).
- DIT-5: Tier 3 scope is gating by the approval record, mapping of block-style fixtures, option pass-through. Cloud Chromium at `/opt/pw-browsers` may serve the tier-2 test (UNVERIFIED; first probe of S-T4).
- DIT-6 rejected: running `setup` (rehearsal wrote USER-scope files: `~/.claude.json` mcpServers.rea, `~/.claude/skills/reverse-engineer-anything/` 7 files 46,471 B, `*.rea.backup`, mode 600; nothing in the project, no network, no telemetry), project `.mcp.json` (cannot enforce the allow-list). Overrides SPEC L3/AC-19/AC-23/OQ-13.
- DIT-8: `status` and `add` are Python (`python -m data_integration.approval_cli`); behaviour like `set-lse-key.ps1 -Status`. Backup guidance in docs.
- DIT-9: steps 1-2 may end the story without scraping.

## Known limits (stated plainly)

Tiers 2 and 3 are NOT proven live against any real protected site. Tooling tests that import scrapling are not in CI (owner-visible choice). The tooling environment is about 676 MB versus about 581 MB for the API environment: NOT lighter; it is installed only on demand, never in CI. Windows and Python 3.12 are unverified until the owner probes (AC-16, AC-17). REA web modes on a real page and the wrapper on Windows are unverified. Scrapling extras (mcp) conflicts are moot (separate project). Pre-1.0 single-maintainer dependencies are pinned exactly (scrapling 0.4.15, rea-agents 6.4.0). Browser download size and antivirus behaviour are unmeasured. In the cloud, a harness hook blocks tool commands naming venv/node_modules/dist/build etc., so workers cannot Read/Grep inside the tooling environment (workaround in Gate conventions 2; hook config untouched).

## Overview and Acceptance Criteria

Build the tooling in slice order. Acceptance Criteria: the 23 SPEC ACs (as amended) are covered per the Verification Evidence table; AC-16, AC-17 and AC-20 stay owner probes/review; AC-5 and AC-18 run in the sandbox/validators, not CI.

## Phase Completion Rules

A slice is VERIFIED only with its gates green on the head SHA plus the planner's EVL re-run (tester re-runs the tooling gates; CI covers only the API guards). Code-only completion is CODE DONE. Known-Gap keeps the gate CONDITIONAL.

## Implementation Checklist

1. S-T0 SPEC. 2. S-T1 skeleton/guards. 3. S-T2 approval gate. 4. S-T5a REA wrapper. 5. S-T3a tier-1 fetch. 6. S-T3b pipeline. 7. S-T4 tiers 2-3 and probes. 8. S-T5b docs and router. 9. S-T6 first dataset. Planner-side records after S-T0.

## Risks and rollback

| Risk | Mitigation |
|---|---|
| Scrapling pre-1.0, one maintainer | exact pins; update only on owner request |
| Tooling tests not in CI | tester runs them in EVL; owner may later add an opt-in CI job |
| Windows/Python 3.12 gaps | owner probes AC-16, AC-17 |
| Wrong adaptive match stores bad data | write only after validation; changed/uncertain stores nothing |
| Overwriting the owner's BTC series | new key `BTC-HIST`; refuse if key holds data; isolated cache in tests |
| Approval records lost with the disk | docs backup guidance |
| Spend over ceiling | owner sets a new ceiling before EXECUTE; ask at 7 USD |

Rollback: additive. Delete `tools/data-integration/`, `api/tests/tooling_guards/`, the docs section, the router row and the `.gitignore` additions; no existing adapter, cache code or workflow is modified.

## Touchpoints

New: `tools/data-integration/**`, `api/tests/tooling_guards/**`, task-folder REF notes. Edited: `.gitignore` (append), the SPEC, `all-data-sources.md`, `all-context.md` (one row), optionally one BTC adapter + test (S-T6); planner-side: MASTER-PLAN row, decisions D-15, current-state. Read only: `api/data/cache.py`, `api/data/layout.py`, `api/pyproject.toml`, `api/uv.lock`, workflows.

## Public Contracts

`request_access(source, tier, store, clock) -> FetchPass | Refused` (reasons incl. `bad_clock`); `FetchPass.permits(url)`; closed status set in `status.py`; `<dataset>.provenance.json` and `<source>.approval.json` shapes; env `DIT_APPROVALS_DIR`, `DIT_SCRAPE_DIR`, `DIT_EVIDENCE_DIR`; markers `integration`, `browser`, `antibot`. No API route, schema or frontend change.

## Blast Radius

About 50 new files, 4 edited files plus 3 planner-side records; risk class: secrets/trust boundary (approval gate) and dependency isolation. API runtime and CI unchanged (guards enforce).

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| test_gate (missing/expired/corrupt/bad_clock, zero client built) | Fully-Automated | AC-1 |
| tooling_isolation + import_boundary guards (CI) | Fully-Automated | AC-2 |
| tier-above-record refusal, tier-3 gating | Fully-Automated | AC-3 |
| exact-name scan of api lock/pyproject, workflow path scan (CI) | Fully-Automated | AC-4 |
| check_clean_install.py, api lock unchanged | Hybrid | AC-5 |
| robots disallow fixture tier 1; stub-navigator test tiers 2/3 | Fully-Automated | AC-6 |
| burst test with fake clock | Fully-Automated | AC-7 |
| changed fixture gives changed, nothing stored | Fully-Automated | AC-8 |
| validation failures write no file | Fully-Automated | AC-9 |
| provenance fields | Fully-Automated | AC-10, AC-22 |
| round trip via api.data.cache | Fully-Automated | AC-11 |
| second run call counter, forced refresh | Fully-Automated | AC-12 |
| error mapping, no exception escapes | Fully-Automated | AC-13 |
| structured log capture | Fully-Automated | AC-14 |
| static marker audit (CI) | Fully-Automated | AC-15 |
| probe_tier1.py on Windows 3.12 | Agent-Probe (owner) | AC-16 |
| probe_tier2.py after browser install | Agent-Probe (owner) | AC-17 |
| docs section, router validators | Fully-Automated | AC-18 |
| REA wrapper allow-list tests, agent-config diff gate | Fully-Automated | AC-19, AC-23 |
| notes, adapter or stop request, owner review | Hybrid | AC-20 |
| git-index and gitignore guard (CI) | Fully-Automated | AC-21 |

Owner probes: AC-16, AC-17, AC-20 review, REA wrapper on Windows. Known-Gap residuals (gate stays CONDITIONAL): tiers 2 and 3 against real sites; REA web modes on a real page; cloud browser test if Chromium stays unverified (backlog stub at EXECUTE).

## Test Infra Improvement Notes

(none identified yet) Candidate: an opt-in CI job for the tooling environment, deliberately not added now.

## Resume and Execution Handoff

1. Selected plan file: this file.
2. Last completed step: PLAN revised 14-10-26 after PVL cycle 1 (F1-F14); no slice executed.
3. Validate-contract status: pending (heading below; the validator writes it).
4. Context loaded: SPEC, PVL iteration 001 report, all-context.md router, api/pyproject.toml, .gitignore, cache.py, data-sources doc.
5. Next: re-VALIDATE; owner sets the new spend ceiling; then wave 1 (S-T0, S-T1). Recompute slice line ranges after any edit to this file. Next instruction: ENTER VALIDATE MODE; execution testing context is `process/context/tests/all-tests.md`.

## Validate contract

Status: PASS
Date: 14-10-26
date: 2026-10-14
generated-by: outer-pvl
Parallel strategy: parallel-subagents (2 opus worker sessions per wave, planner merges between waves; validators/testers sonnet)
Rationale: score 3/7 (S4, S6, S7); dominant S7; owned globs disjoint inside every wave.

A = `UV_FROZEN=1 uv run --project api pytest`. T = `UV_PROJECT_ENVIRONMENT=$HOME/.cache/dit-env uv run --project tools/data-integration pytest tools/data-integration/tests -q`. API baseline at 20b65a2 (14-10-26): 1143 passed, 1 skipped, 5 deselected. Each slice logs its own baseline first; afterwards passed = baseline + its new guard tests, skipped/deselected unchanged, no existing test edited; another count stops at needs_input. Tooling default run: passed = sum of new tests; browser/antibot/integration deselected.

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| S-T0 AC-19,23 | SPEC wording | Fully-Automated | RT0: `git diff --stat origin/main...HEAD` = SPEC only; each `grep -n "rea-agents setup"` line says rejected/superseded | B |
| S-T1 AC-2,4,15,21 | CI guards | Fully-Automated | RT2: `A api/tests/tooling_guards -q` red-first, green on base for unchanged parts; `A api/ -q` | B |
| S-T1 AC-5 | clean install | Hybrid | `uv lock --project tools/data-integration`, T, `python tools/data-integration/scripts/check_clean_install.py`, import probe | B |
| S-T2 AC-1,3,21,22 | gate, host-bound pass | Fully-Automated | RT2: T + `A api/tests/tooling_guards -q` | B |
| S-T5a AC-19,23 | allow-list wrapper | Fully-Automated | RT2: T + A guards + `git diff origin/main...HEAD -- .claude CLAUDE.md AGENTS.md .mcp.json` empty | B |
| S-T3a AC-6(t1),7,12-14 | tier 1 fetch | Fully-Automated | RT2: T (loopback, fake clock) | B |
| S-T3b AC-8-12,22 | pipeline, provenance | Fully-Automated | RT2: T incl. api.data.cache round trip | B |
| S-T4 AC-6(t2,t3),3,13 | tiers 2-3 gated | Fully-Automated | RT2: T default run (stub navigator); `-m browser`/`-m antibot` only where Chromium exists (Hybrid) | B |
| S-T5b AC-18 | docs, router row | Fully-Automated | RT0: `node .claude/skills/vc-context-discovery/scripts/discover-context.mjs --check-routing`; `node .claude/skills/vc-generate-context/scripts/validate-all-context.mjs`; PLANNER-BUDGET block (base rc=1 pre-existing, headroom 2,960 B, record only); section `wc -c` <= 3,500 | B |
| S-T6 AC-20 | first dataset notes | Hybrid | notes with VERIFIED/ASSUMED lines; adapter if any: its test + `A api/ -q`; owner review | C |
| AC-16, AC-17 | Windows tier 1; tier 2 render | Agent-Probe | owner runs probe_tier1.py, probe_tier2.py | C |

Failing stub (each Fully-Automated row): `def test_<scenario>(): raise AssertionError("NOT IMPLEMENTED - TDD stub: <scenario>")`.

EVL (independent vc-tester, after the last merge): (1) `A api/ -q` = baseline + guard tests, 0 failed; (2) T, then T with `-m browser` and `-m antibot` where a browser exists; (3) `A api/tests/tooling_guards -q`; (4) `git diff --name-only origin/main...HEAD` lists none of CLAUDE.md, AGENTS.md, .claude/, .mcp.json, .github/, deploy/, api/uv.lock, api/pyproject.toml, existing api/data adapter or cache code (S-T6: one approved new adapter + test); (5) `git diff --exit-code api/uv.lock`, `git diff --check origin/main...HEAD`, `git ls-files` has no approval.json; (6) check_clean_install.py.

Owner probes: AC-16, AC-17, AC-20 review, wrapper on Windows, BTC-HIST key, S-T6 adapter names at needs_input, new spend ceiling before EXECUTE (86.13 of 100 USD used; plan 23.3-40.5).

Envelope additions (binding; plan body untouched so line ranges hold): E1 S-T1: test_skeleton asserts the pandas/pyarrow/duckdb pins equal api/uv.lock (3.0.6, 25.0.1, 1.5.5); tree scans skip .venv. E2 S-T2: permits() cases for userinfo host, non-http scheme, port; bad source name gives Refused, no exception. E3 S-T3b: also read cache.py line 36. E4 S-T4: tier 2/3 gating and robots tests use fixture_server so they run in the default suite. E5 S-T5a: test a drive-letter path (backslash fails the argument regex; convert). E6 S-T5b: also read evidence_template.md, approval fields (grep approvals.py), wrapper usage; docs say approval records are plain files. E7 S-T6: worker never runs npx or live REA; use owner-supplied artefacts, else ASSUMED or needs_input. E8 planner: P9 row at dispatch; vc-risk-evidence-pack in harness/ for S-T2, S-T5a.

Dimension findings:
- Infra fit: PASS - recipe verified, 36 packages resolve with exact pins
- Test coverage: PASS - 23 ACs mapped to slice and runnable check; no behavior rests on Known-Gap alone
- Breaking changes: PASS - no existing test, validator, glob or CI filter touched
- Security surface: PASS - host-bound pass, exact allow-list, TTY add, UTC expiry
- Section feasibility S-T0..S-T6: PASS - ranges match headings; read 29.5-31.7 KB of 36 KB

Open gaps: none blocking. Residuals (D, backlog stubs at EXECUTE; see Known limits): tiers 2-3 on real sites; REA web modes on a real page; cloud browser test if Chromium stays unverified.
What this coverage does NOT prove: tiers 2-3 on real sites; Windows, Python 3.12, antivirus, browser download size; wrapper on Windows; REA command names on a live npx call; tooling tests in CI (EVL only); that approval records cannot be written by other means.
Gate: PASS
Accepted by: n/a (PASS; E1-E8 are binding envelope additions)

## Amendment A1: S-T7 command-line front door (owner approved 14-10-26)

**Why.** Only `approval_cli` has a command line; `run_rea` and `pipeline.run` are Python functions, and the owner is a non-programmer on Windows. Task T62. Earlier lines unchanged.
**Waves.** W3.5 = T63 (S-T3c supplement: `FetchOutcome.body_sha256`, `FetchPass.approval_id` = the record's stored id plus `approval_revision`, size caps, tier in cache key); W4 = S-T4 (T59); W5 = S-T7 (T62); W6 = S-T5b docs (T60); W7 = S-T6 (T61, also depends on T60). Estimate 24.8-43.5 USD; actual spend through wave 3 is 93.30 of 130 USD.

### S-T7: command-line front door (RT2)

**Owned:** `tools/data-integration/src/data_integration/{__main__,cli,recipe}.py`, `tools/data-integration/tests/{test_cli,test_recipe}.py`, `tools/data-integration/recipes/example.recipe.json` (synthetic, host `example.test`), `api/tests/tooling_guards/test_cli_guard.py`. **Depends:** T2, T3a, T3b, T5a, T63, T59 merged; if `fetch_tier2/3.py` are missing or differ from the registry, STOP at `needs_input`. **Covers:** US-4; AC-1 and AC-3 re-proven via the CLI; AC-20 prerequisite.
1. `python -m data_integration`: `approvals ...` is dispatched by hand to `approval_cli.main`. `rea <command> [--confirm-source N] [--findings F] [-- args]`: split argv at `--` by hand, then `run_rea(..., runner=)` (fake runner in tests, never npx); every `add_parser` sets `allow_abbrev=False` (tests: `--rep`, `--acc`, `--dry` rejected); prints only a placeholder path under the evidence folder; map the returned `detail='FileNotFoundError'` to a plain Node/npx message.
2. Recipe = JSON file (<= 16 KiB, regular file, size checked before read; unknown/duplicate keys, NaN, bool-as-int rejected; no code): `schema_version`, `source` (approvals regex), `tier` 1-3, `url` (<= 2048, http/https, no userinfo; only `pass_.permits` decides), `selector` (<= 500, no control chars), `dataset{symbol,timeframe}`, `min_rows` 2-100000, optional `politeness` (numeric, bounded, only tighter than `Politeness` defaults: `min_delay>=1.0`, `max_concurrent<=2`, `max_per_host<=1`). `symbol` uses `re.fullmatch` on `^[A-Z0-9][A-Z0-9-]{0,31}$` (uppercase only) and a denylist of Windows device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9, also with extensions); `timeframe` in 15m,1h,4h,1d,1w; both checked before any path or SQL. Tests: `..\x`, `BTC\n`, `btc`, `CON` rejected; `BTC-HIST` accepted.
3. `run <recipe> [--dry-run | --preview] [--refresh] [--replace] [--accept-baseline]`: gate (`request_access`), per-tier adapter from an injectable registry (cache_hit maps to ok), then `pipeline.run`. `--replace` only if `provenance.read_records` for the key is non-empty. `--accept-baseline` only when `adaptive.assess(b"<html></html>", sel, url=url).has_baseline` is false, else exit 2. `--dry-run` fetches nothing: prints the request, approval id, revision, expiry, rate text, whether `permits` refuses, baseline presence. `--preview` calls fetch without ResponseCache, then parse and validate directly (not `pipeline.run`), prints rows, first and last 3 rows, columns, status, response_sha256, and writes nothing (test: no file under any `DIT_*` dir). `--dry-run` and `--preview` are exclusive and exit 2 with `--replace` or `--accept-baseline`. The outcome line prints approval id, revision, expiry (same id as `approvals status`).
4. Exit codes: 0 ok/cache_hit/dry-run/preview; 2 usage, bad recipe or flags; 3 gate refusal (one test per reason: missing, expired, tier_too_low, store_missing, store_corrupt, bad_clock); 4 fetch/robots/network statuses; 5 parse or validation failure; 6 changed/uncertain (nothing stored); 7 cache protection. One test per closed status (11) for code and plain message. `_safe()` redacts absolute paths and IPv4 in all output; top-level handler prints the exception type only.
**Guards.** AST ban on `eval`, `exec`, `compile`, `pickle`, `marshal`, `yaml`, `shelve`, `subprocess`, `os.system` in the three modules; fetch tiers, pipeline and wrapper imported lazily in handlers. `test_cli_guard.py` (CI, file-only): no `api/` module, workflow, scheduler or `deploy/` script references the CLI; `recipes/` has no secret/IP pattern. Import-boundary guard unchanged.
**Tests.** RT2, red-first, baseline on untouched origin/main (tooling 253, guards 41). Tests import no `fetch_tier*` (fake registry, call counters), isolate `DIT_*`, `HOME`, `LOCALAPPDATA`; subprocess: `approvals status` (cwd `tmp_path`, `PYTHONPATH=<tool>/src`, 60 s) and `approvals add` with stdin DEVNULL (exit 2, no file). Commands: `UV_PROJECT_ENVIRONMENT=$HOME/.cache/dit-env uv run --project tools/data-integration pytest tools/data-integration/tests -q`; `UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards -q`.
**Limit.** Real tier-1 through the CLI cannot run on loopback (`permits()` rejects non-default ports); it is proven only by the owner's AC-20 run.
**Must NOT:** edit existing modules, workflows or `fixture_server.py`; add a proxy option; use the network in tests. **Cost:** 1.5-3.0 USD (T58 1.18, T55 0.88, T57 1.82 actual).
**Envelope hint.** Envelope <= 4,000 B. Read Common (lines 40-75) and ONLY lines 332-343 of this plan (the S-T7 subsection; skip the Why and Waves lines), plus: `approval_cli.py` 71; `wrapper.py` 33-46, 99-107; `pipeline.py` 19-24, 30-44; `gate.py` 16-36, 67-72; `politeness.py` 11-14; `fetch_tier1.py` 81-83; `provenance.py` 42-46; `adaptive.py` 31-32; `paths.py` 37-38; `status.py` 1-22; `types.py` 8-14 (about 3,800 B) and tier 2/3 signatures (about 600 B). Total about 13,443 + 4,000 + 6,060 + 5,100 + 4,400 = 33,000 B (target <= 34,000). If over, drop `status.py`, `types.py`, then `fetch_tier1.py`.

## Amendment A2: S-T8 cloud-run support (owner decision 15-10-26)

**Why.** Owner decision 15-10-26 supersedes "records and scraping only on the owner PC" for cloud sessions. T64, W8, needs T2. Unchanged: no background scraping, gate, tiers, robots, politeness, provenance, rate limits, Farside, no secrets in records.
**Cloud conditions (all 4).** (1) The owner tells the planner to run a named recipe. (2) The owner approved the site in chat: host, page, tier, expiry days, own robots/terms note; the agent never approves or widens. (3) Records live outside the checkout (`DIT_APPROVALS_DIR`). (4) The owner widens cloud network access.

### S-T8: cloud-run support (RT2)

**Owned:** `tools/data-integration/src/data_integration/{approval_cli,approvals,paths}.py`, `tools/data-integration/tests/{test_approval_cli_cloud,test_paths_private}.py`, `api/tests/tooling_guards/test_cloud_guard.py`, and ONLY lines 415, 420, 427, 439 of `process/context/data-sources/all-data-sources.md`. **Forbidden:** `gate.py`, `cli.py`, `recipe.py`, `pipeline.py`, `fetch_tier*.py`, `provenance.py`, `rea/wrapper.py`, existing tests (incl. `test_evidence_inside_repo_refused`), workflows, `CLAUDE.md`, `.claude/`, `process/MASTER-PLAN.md`, `decisions.md`, `api/data/cache.py`.
1. A. `approvals add --owner-statement TEXT`. TTY matrix: statement+TTY refuse; statement+no TTY allowed; no statement+TTY interactive (unchanged, `approval_cli.py` 46-58); no statement+no TTY refuse (unchanged). The statement path never calls `input_fn`. Refuse (exit 2, no file) unless the text is 20-500 ASCII printable chars and contains the source name AND every `--host` value, AND `DIT_APPROVALS_DIR` is explicitly set (statement path needs BOTH non-TTY and the env var). Stored verbatim, optional `owner_statement` (default "" in `ApprovalRecord` and `_from_dict`; old records load; non-string raises ValueError/StoreCorrupt). `approval_cli.py` and `approvals.py` stay stdlib-only (`GUARDED` in `test_approval_store_guard.py`). `gate.py`, `FetchPass` unchanged.
2. B. The guard lives inside `approvals_dir()` and `scrape_dir()` ONLY (`_dir` and `evidence_dir()` unchanged): resolve symlinks, compare to a new side-effect-free checkout-root helper (do NOT call `paths._repo_root`, it edits `sys.path`), raise `PathInRepo` with a fixed message and no path. Evidence keeps the wrapper's existing guard (`wrapper.py` 112-113) untouched. `approval_cli` catches `PathInRepo` (add and `_status`) and exits 2.
3. C. Docs only: use `/opt/pw-browsers` Chromium first (env `DIT_BROWSER_EXECUTABLE`); `uv sync --project tools/data-integration`; `scrapling install` only if that browser is absent AND the owner asked for that tier 2/3 run; never `playwright install`, never in CI. A blocked host shows as `connection_failed` (exit 4): tell the owner the host to add to Allowed domains; retry once on their word. Scrape output goes to gitignored `api/data/cache/ohlcv/` and is lost when the cloud session ends unless the owner asks for it to be committed after a redistribution check.
4. D. Rewrite 415 (drop "Workers never run live commands"), 420 step 4 (add `--owner-statement`), 427 (drop "stay on the owner's PC": private store outside the repo, never committed; cloud runs need the four conditions), 439 (the statement cannot prove a human wrote it).
**Limit and control.** Control: the statement is the owner's message verbatim; a worker (not the planner inline) runs it; envelope and report quote it with the message time; expiry default 90, max 366 d.
**ACs.** AC-24: valid statement stored verbatim; TTY matrix, short, long, non-ASCII, missing source/host, unset `DIT_APPROVALS_DIR` refused, no file. AC-25: approvals/scrape folders inside the checkout raise `PathInRepo` (exit 2 via CLI); outside work; `test_evidence_inside_repo_refused` still green. AC-26: `git diff origin/main...HEAD` empty for forbidden files; old record loads; interactive add unchanged. AC-27 (docs 413-443): "Workers never run live commands" absent; "--owner-statement", "connection_failed", "scrapling install" present; "stay on the owner's PC" absent; <= 3,500 B.
**Tests.** RT2, red-first (AC-27 asserts fail on base). Fake store in `tmp_path`, fake `isatty`. Guards (CI, file-only): `paths.py` has `PathInRepo`; no `*.approval.json` tracked; no file under `api/` (skip `tooling_guards`), `deploy/` or `.github/workflows` contains `--owner-statement` or `scrapling install` (like `test_cli_guard._scan_files`; needles concatenated: README and `probe_tier2.py` already say it); the scrape cache path is git-ignored (`git check-ignore api/data/cache/ohlcv/x`). Baselines (S-T7 report): tooling >= 523, guards >= 49, API >= 1192/1/5. Commands: Common rule 2.
**Cost:** 1.2-2.5 USD.
**Envelope hint.** Envelope <= 4,000 B. Read: Common 58-75 (3,011 B), plan 350-360 (4,082 B), `approval_cli.py` 44-end (2,167 B), `approvals.py` 51-72, 81-100 (1,597 B), `paths.py` (983 B), docs 413-443 (2,192 B). Total 13,443 + 4,000 + 3,011 + 4,082 + 2,167 + 1,597 + 983 + 2,192 = 31,475 B (<= 35,000).
**Planner-side doc edits (not the worker's):** (a) `decisions.md` ~147: append "(cloud: DIT-10)"; D-15 add `  - DIT-10 cloud-run support (15-10-26): the planner may run the scrape tooling in a cloud session only on an explicit owner instruction naming the recipe, for a site the owner approved per site in chat; records made with 'approvals add --owner-statement' live outside the checkout (DIT_APPROVALS_DIR); the statement cannot prove a human wrote it; the command is executed by a worker, not inline by the planner; the agent never approves or widens. Rejected: agent-approved sites, repo records, background scraping.` Change "DIT-1..DIT-9" to "DIT-1..DIT-10"; append "(owner-PC-only superseded for cloud by DIT-10)" to DIT-8. (b) Plan Safety rules lines 68-71. (c) S-T6 step 4, lines 174-184. (d) SPEC L5.

## Amendment A3 (S-T9 resource-host allowance, T65)

**Why.** Owner decision 15-10-26. The first real tier-2 preview of `charts.bitbo.io/halving-progress/` was refused (`browser request outside the pass was aborted`, exit 7): the guard aborts non-approved hosts without naming them. Wave W9; needs T2, T59, T62, T64. Cost 3-5 USD (total 102.5-104.5 of 130).

### S-T9: resource-host allowance (RT2, plus a marked browser test)

**A. Diagnostics first.** `BrowserResponse` gains `blocked_hosts: tuple[str, ...] = ()`. `route_guard.py` holds `host_label`, `summarise`, `make_handler(pass_, blocked)`. `host_label` gives the lowercase hostname only; an IP gives `(ip)`, odd characters or > 253 chars `(invalid)`. `summarise`: distinct, sorted, max 20; detail max 600 B: `browser request outside the pass was aborted; blocked hosts: a.example, b.example`. `fetch_tier2.py:68` stores full URLs and 95/98 set `blocked_url` from them: store hosts only, pass `blocked_hosts` at both returns, `log.info` after 159. `cli.py` already prints `detail`: not owned.
**B. Record field.** `ApprovalRecord.resource_hosts: tuple[str, ...] = ()` (old records load unchanged). New `check_resource_hosts` in `approvals.py`, called by `_add` before any write (no raw ValueError as at `approvals.py:148`) and at load. Valid: <= 8 distinct exact lowercase hostnames, each <= 253 chars, labels <= 63, 2+ labels of `[a-z0-9-]`, no edge hyphen, LAST label starts with a letter (so `0x7f.0x1` fails); no wildcard, IP, port, scheme or path (https implied). Invalid at load = `StoreCorrupt`. Tier 1 with resource hosts refused at add and load. `approvals add --resource-host H` needs `--owner-statement` naming every resource host too (same substring rule); `statement is None and args.resource_host` exits 2.
**C. Guard.** New stdlib-only `route_guard.py`: `decide(url, resource_type, is_navigation, pass_) -> bool`, used by the `fetch_tier2.py` guard via `make_handler`. It mirrors `permits` (`gate.py:47-58`: non-str, backslash, `@`, port error abort). Allowed: (1) as today, host in `pass_.hosts` (navigations also need `permits`); (2) NEW: host exactly in `pass_.resource_hosts`, https, no port or 443, not a navigation, type in {script, stylesheet, font, image, xhr, fetch}. All else aborts (document, websocket, other, non-page redirects, http, ports). Redirect hops re-enter the guard. Tier 3 inherits. Table test: empty `resource_hosts` equals today's guard (`fetch_tier2.py:64`).
**D. Preserved.** `gate.permits` and `types.py` unchanged. `gate.py` changes ONLY: `__slots__` (add `resource_hosts`), the `__init__` signature plus one `object.__setattr__` line (28-41), and the `FetchPass(...)` return at line 95, passing `rec.resource_hosts if tier >= 2 else ()`. Page host, path, tier checks, politeness unchanged; robots and politeness stay page-host only.
**E. Provenance.** `provenance.build_record` gets a `resource_hosts` key (list) after line 47; it lists approved, not contacted, hosts. Tested in `test_resource_hosts.py`.
**Owned:** `tools/data-integration/src/data_integration/{route_guard,fetch_tier2,gate,approvals,approval_cli,provenance}.py`; new `tools/data-integration/tests/{test_route_guard,test_resource_hosts,test_tier2_resource_browser}.py` and `api/tests/tooling_guards/test_resource_host_guard.py`; ONLY lines 420 and 438 of `process/context/data-sources/all-data-sources.md`. **Forbidden:** `cli.py`, `fetch_tier1.py`, `fetch_tier3.py`, `types.py`, `recipe.py`, `pipeline.py`, `paths.py`, `robots.py`, `fixture_server.py`, other existing tests (incl. `test_provenance_completeness.py`), workflows, `.claude/`, planner-side docs. Disjoint; no worker lane.

**ACs.** AC-28 (`test_route_guard`, browser test; Fully-Automated, Hybrid): blocked hostnames named, sorted, bounded, no path or query. AC-29 (`test_route_guard`, `test_resource_hosts`; Fully-Automated): a listed https host passes for the six types; provenance lists it. AC-30 (same plus browser test; Fully-Automated, Hybrid): navigation to a listed host, a non-listed host, websocket, other, http, a port, a redirect to a non-page host abort (websocket proven in `decide` only: `page.route` misses WebSockets). AC-31 (`test_resource_hosts`; Fully-Automated): wildcard, IP, `0x7f.0x1`, port, scheme, duplicates, 9 hosts, tier 1, statement missing a host, interactive use rejected with no file; old record loads. AC-32 (git diff, docs check; Fully-Automated): `gate.permits` and forbidden files unchanged, gate.py diff limited to the three spots, docs 420 and 438 name `--resource-host`; delta +550 B (`test_docs_ac27` caps 413-443 at 3,500 B, now 2,950); 420+438 measure 961 B; 438 says robots/politeness are page-host only, listed hosts are the owner's call, provenance lists approved not contacted hosts.
**Tests.** Red-first. CI runs `pytest api/` only, so `api/tests/tooling_guards/test_resource_host_guard.py` loads `route_guard.py` and `approvals.py` by path (stdlib, duck-typed pass) and tests `decide`, handler, record checks. `test_route_guard`, `test_resource_hosts` are stdlib-only. Browser file: module `pytest.mark.browser`; HTTPS via an HTTP proxy shows only `CONNECT host:443`, so a `do_CONNECT` recorder defined in the test (`fixture_server.py` forbidden); needs Chromium and scrapling: Hybrid, outside CI. Baselines from origin/main (tooling >= 523, guards >= 49). Commands: Common rule 2.
**Risks.** Listed hosts see the cloud IP; no cookies sent. Forgery limit as in A2. Rollback: revert the PR.
**Planner checklist (not the worker's).** `decisions.md` D-15: add `DIT-11 resource-host allowance (15-10-26): approval records may list up to 8 exact https resource hosts (tier 2/3 only, created via --owner-statement naming each); only sub-resource requests pass, never navigations; robots stays page-host only; no wildcards.` and "DIT-1..DIT-10" to "DIT-1..DIT-11". Tool README: one line. MASTER-PLAN P9: add T65. SPEC: AC-28..32.
**Envelope hint.** Envelope <= 4,000 B. Read, corrected 34,760 B (<= 35,000): CLAUDE.md 13,443; envelope 4,000; Common 58-75 3,011; plan 368-379 4,320; `fetch_tier2.py` 45-100, 157-161 2,452; `gate.py` 28-41, 93-96 1,198; `approvals.py` 51-100 1,831; `approval_cli.py` 44-end 3,544; docs 961. Skip `provenance.py`; the envelope names the key to add after line 47.
