---
name: plan:data-integration-tooling
description: "Developer-run data integration tooling (REA wrapper + Scrapling tiers 1-3) as a separate uv project tools/data-integration, with approval gate, provenance, adaptive store, docs workflow and a first BTC-history run. Eight slices S-T0..S-T6 (S-T3 split a/b)."
date: 14-10-26
feature: general-plans
---

# Data Integration Tooling: Plan (S-T0 to S-T6)

Date: 14-10-26. Base: origin/main b66d9b4. SPEC: `data-integration-tooling_SPEC_13-10-26.md` (same folder). Status: PLANNED, VALIDATE pending.
Status: PLANNED
Complexity: COMPLEX (eight slices, new tooling project, approval enforcement, docs and router edits).

**TL;DR:** Everything new lives in `tools/data-integration/` (own uv project, never imported by the API, never in CI install). A single gate `request_access` must hand out a `FetchPass` before any HTTP client exists. REA is a pinned, allow-listed wrapper only (setup is never run). Provenance goes in a separate `<dataset>.provenance.json`. Estimate 20.5-36.0 USD (expected about 27) for 8 slices. Worker spend so far 86.13 of 100 USD ceiling; about 13.9 left; the owner must decide a new ceiling before EXECUTE.

Context Envelope: general-plans | PLAN | data integration tooling | claude/plan-data-integration | /home/user/psychic-train | data-sources | tools/data-integration, api/tests/tooling_guards, process/ | this file | pytest (api) then pytest (tooling venv) | pending VALIDATE.

## Slice index (line ranges of THIS file; workers read Common rules + their own range only)

Worker read budget: 36,000 B = CLAUDE.md 13,443 + envelope (keep under 4,000) + Common rules + one slice range + named code files. Workers do NOT read the full SPEC; each slice states the AC wording it needs.

| Slice | Objective | Lines | Depends | Wave | Est. USD (low-high) |
|---|---|---|---|---|---|
| Common | Decisions D1-D9, gates, safety, envelope rules | 39-78 | none | all | n/a |
| S-T0 | Records: SPEC amendments, decisions.md, MASTER-PLAN rows | 79-90 | none | 1 | 1.0-2.0 |
| S-T1 | Skeleton, dependency isolation, CI-visible guards, markers, .gitignore | 91-103 | none | 1 | 2.0-3.5 |
| S-T2 | Approval gate, local store, status command, store guards | 104-116 | T1 | 2 | 2.5-4.0 |
| S-T5 | REA wrapper, evidence template, docs section, router row | 153-166 | T0, T1 | 2 | 3.0-5.0 |
| S-T3a | Tier 1 fetch, robots, politeness, errors, logs, response cache | 117-128 | T1, T2 | 3 | 3.0-5.0 |
| S-T3b | Parse, validate, normalise, cache write, provenance, adaptive | 129-140 | T1, T2 | 3 | 3.5-6.0 |
| S-T4 | Tiers 2 and 3, fixture server tests, owner probe scripts | 141-152 | T3a, T3b | 4 | 3.0-5.5 |
| S-T6 | First dataset: workflow steps 1-4 for long BTC history | 167-178 | T0, T5, T3b | 4 | 2.5-5.0 |
| Tail | Touchpoints, contracts, verification table, handoff | 179-256 | n/a | n/a | n/a |

Total 20.5-36.0 USD, expected about 27. Basis: past workers S9A 3.62, S9B 1.72, S9C 3.38, S9D 3.38, S9F 1.01, S9E 3.59 USD (backend and mixed); S5b 9.99 (large UI slice, passed the 7 USD ask point). Per-slice cap 15 USD, ask point 7 USD. Worker spend so far 86.13 of 100 USD ceiling; about 13.9 left; the owner must decide a new ceiling before EXECUTE. Even the low end (20.5) exceeds the 13.9 left.

Concurrency (max 3 workers, one slice each; this plan uses at most 2): wave 1 = S-T0 and S-T1 together (disjoint files); wave 2 = S-T2 and S-T5; wave 3 = S-T3a and S-T3b; wave 4 = S-T4 and S-T6. A wave starts only after the previous wave is merged by the planner. Why S-T3 is split: one slice would own about 12 files and pass the 15 USD cap; the split shares only interfaces that S-T1 pre-defines (`types.py`, `status.py`).

## Common rules

### Locked decisions (owner APPROVED 14-10-26; rejected alternatives in one line)

- **D1 Layout.** Separate uv project `tools/data-integration/` (own `pyproject.toml`, `uv.lock`, venv, requires-python >=3.12), importing `api.data.cache` for normalise/store; never imported by the API; not in the API wheel (`api/pyproject.toml` hatch packages unchanged); not added to any CI install step; owner installs on demand on Windows with `uv sync --project tools\data-integration`; `scrapling install` (browsers) is a separate opt-in. Rejected: extras/dependency group in `api/pyproject.toml` (lockfile pollution); code inside the API package (accidental import). File-only guard tests live in `api/tests/tooling_guards/` (run by the existing CI job, never import scrapling). The tooling's own tests that import scrapling run locally/by the tester in the tooling venv, NOT in CI: known limit and an owner-visible choice.
- **D2 Approval enforcement.** One gate `request_access(source, tier, store, clock)` returns a `FetchPass` or typed `Refused(reason in missing|expired|tier_too_low|store_missing|store_corrupt, source, tier_asked, tier_allowed, expiry)`. Every fetcher requires a FetchPass (private constructor). Refusal happens before any HTTP client is built (call counter zero). Expiry is `now >= expiry`, injectable clock. Plus import-boundary tests scoped to the new tooling only. The Farside on-demand refresh (`api/analytics/regime/components.py:484` via `api/routers/regime.py:57`) is outside the tooling: neither broken nor covered. Gate and store use the standard library only. Rejected: convention-only, decorator-only.
- **D3 Provenance.** Separate `<dataset>.provenance.json` (list of records) beside the data, written only by the tooling. Record: source URL, fetch time (UTC), response hash, scrapling version, parser version, approval id AND copied approval facts (source name, allowed tier, approval date, expiry, id), tier used. `.meta.json` sidecars and `api/data/cache.py` are NOT modified; a test proves `cache.write_ohlcv` does not wipe the provenance file. Raw snapshots default off, untracked. Rejected: extending the sidecar (writers overwrite it), parquet footer (no history).
- **D4 Adaptive store.** Gitignored machine-local SQLite under `%LOCALAPPDATA%\my_site\scrape\...` (env override for tests), passed via Scrapling's `storage_args={'storage_file': ..., 'url': ...}` (verified by an earlier run). A test fails if the resolved path is inside site-packages. A lost store makes the first run report "uncertain". A relocated or unmatched element always yields explicit changed/uncertain; store/cache write happens only after validation passes.
- **D5 Testing.** Mocks of fetchers for CI-able tests plus a tiny local fixture HTTP server for real-fetch tests. Markers `browser` and `antibot` deselected by default via the same addopts pattern as `integration`; an audit test that no unmarked test does network or browser work. Tier 3 honest scope: gating by the approval record, mapping block-style fixture pages to the closed status set, option pass-through; NOT proven against any real protected site. Owner probes: AC-16 (tier 1 on Windows + Python 3.12 against a local fixture server) and AC-17 (tier 2 renders a local JS fixture page after the opt-in install; note download size and antivirus behaviour). The cloud workspace has Chromium at `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers` (present: chromium, chromium-1194, headless shell); never run `playwright install`; whether it can serve the tier-2 fixture test is UNVERIFIED and is the first probe of S-T4, fallback = owner-run probe.
- **D6 REA = wrapper only** (overrides SPEC L3/AC-19/AC-23/OQ-13). Never run `setup`, register no MCP server, create no `.mcp.json`, no agent-config change. Pinned wrapper `rea-agents@6.4.0` calls `npx -y rea-agents@6.4.0 <command> --json` with an ALLOW-LIST of web/static commands (listed in S-T5). It REJECTS everything else including setup, update, uninstall, mcp, completions, argv tokens `--update` and `--mcp`, native/APK/ADB/firmware/process/Apple/JEB/managed and runtime-capture/electron commands, and unknown commands. Evidence: `setup --client claude_code` rehearsal wrote USER-scope files (`~/.claude.json` mcpServers.rea, `~/.claude/skills/reverse-engineer-anything/` 7 files 46,471 B, `*.rea.backup`, mode 600), nothing in the project, no network, no telemetry (scratch evidence is session-local and may vanish). Rejected: running setup (user scope, exposes all 127 commands); project `.mcp.json` (cannot enforce the allow-list). Unverified: Windows behaviour of the wrapper and REA web modes, REA output on a real page.
- **D7 Docs.** One 'New dataset workflow' section in `process/context/data-sources/all-data-sources.md`, one routing-table row and keywords in `all-context.md`, per-dataset notes folders under the task folder. No new skill, no second doc system. Both files keep their size budgets (all-context.md is 11,496 B, all-data-sources.md 27,574 B at plan time; check the validators and the entry-set cap).
- **D8 Approval store.** One JSON per source `<source>.approval.json` under `%LOCALAPPDATA%\my_site\approvals\` (env override for tests), atomic write with a revision field (like `api/data/layout.py`), corrupt file renamed `.bad`, missing store or file gives Refused, tooling never creates a default approval, a status command (like `set-lse-key.ps1 -Status`) lists records/tiers/expiry without secrets, backup guidance in docs, AC-21 guard checks the git index for `*.approval.json` and `.gitignore` patterns. Cloud tests use fixture records in a temp folder only.
- **D9 First dataset.** Longer BTC price history. Steps 1-2 may end the story without scraping; integrate an API/dataset through the normal adapter path with provenance, or, if scraping is the only option, STOP and ask the owner for an approval record. Output lands in the PC-local gitignored `api/data/cache/ohlcv`; redistribution check recorded before any tracked directory is used.

### Known limits (stated plainly)

Tiers 2 and 3 are NOT proven live against any real protected site. Tooling tests that import scrapling are not in CI. Windows and Python 3.12 are unverified until the owner probes (AC-16, AC-17). REA web modes on a real page are unverified. Scrapling extras (mcp) conflicts are moot (separate project). Single-maintainer pre-1.0 dependencies are pinned exactly (scrapling 0.4.15, rea-agents 6.4.0). Browser download size and antivirus behaviour are unmeasured.

### Gate conventions (all slices)

1. API-side gates: `UV_FROZEN=1 uv run --project api pytest <paths> -q`; full: `UV_FROZEN=1 uv run --project api pytest api/ -q`. Baseline counts are taken by the worker on the untouched base and logged in report heading 6; a count differing from the slice arithmetic stops at `needs_input`.
2. Tooling gates (after S-T1): `uv sync --project tools/data-integration` then `uv run --project tools/data-integration pytest tools/data-integration/tests -q` (default deselects `integration`, `browser`, `antibot`).
3. Red-first: write the slice's new tests as failing stubs, run on the untouched base, record the red count, then write real tests. New tests are plain functions.
4. No existing test file is edited unless the slice says so. Max 2 fix cycles per gate; the same failure twice stops.
5. Known-Gap is a residual (backlog stub, gate stays CONDITIONAL), never PASS. Probes (P-*) are the owner's and never claimed by a worker.
6. A diff touching `CLAUDE.md`, `AGENTS.md`, `.claude/`, `.mcp.json`, `.github/`, `deploy/`, `api/uv.lock`, `api/pyproject.toml`, or any existing adapter/cache code stops at `review`. Exceptions are named in the slice.
7. `git diff --check origin/main...HEAD` exits 0; plan, report and envelope files are ASCII.

### Safety rules (every slice)

No secrets, keys, IPs or user names in files, logs or commits. Synthetic fixtures only. No live network in tests (loopback fixture server only). Scraping only by explicit developer command; never scrape without an approval record. No change to production config, credentials, DB or deploy scripts without owner authorisation (an optional deploy install script needs its own explicit mention and shape test; it is NOT planned here). The cloud sandbox never performs a real scrape.

### Worker envelope standing rules

First line `ROLE: WORKER`. Branch `claude/<task-id>-<slice>-<slug>` from main, open a PR. Envelope text: "After your report, stop; do not wait on CI or check in. needs_input means STOP: do NOT merge, do NOT open a new PR." The worker never merges. The planner measures cost after idle. Spend cap 15 USD, ask at 7 USD. A worker that opens a doc beyond its list notes it in report heading 11.

### SPEC amendments (done by S-T0; wording to apply)

AC-19: "A pinned REA version, an allow-listed wrapper, an evidence template (VERIFIED/ASSUMED) and a 'what REA cannot establish' statement exist; the API does not import REA; no agent-config file is changed by this work (git diff check on `.claude/`, `CLAUDE.md`, `AGENTS.md`, `.mcp.json`)." AC-23 replaced by: "The wrapper rejects setup, update, mcp and every non-allow-listed command (test)." OQ-13 closed: web/static commands only. L3 rewritten to the wrapper-only decision (D6). Other wording changes: AC-2 guard lives in `api/tests/tooling_guards/` (file-only import scan of api routers/main/workers, workflows and the new tooling's entry points). AC-4 proven by inspecting `api/uv.lock`, `api/pyproject.toml` and workflows for scrapling/playwright/patchright/rea. AC-5 is a Hybrid scripted install check (clean temp env, then API lock unchanged). AC-10 and AC-22 say "provenance file" instead of "sidecar" (D3). AC-11 round trip uses the cache read functions unchanged. AC-15 = static marker audit plus the `browser`/`antibot` markers; CI only runs the API job, so tooling tests are not CI-run. AC-16/AC-17 become scripts the owner runs (AC-17 after the opt-in browser install). AC-20 follows D9. AC-21 also covers the approvals folder pattern. OQ-12 closed with the D8 path. SPEC INNOVATE questions 1-8 marked answered by D1-D9.

## S-T0: Records (docs only, RT0)

**Objective.** Make the SPEC, decisions log and registry match the approved decisions before code starts.
**Owned:** `process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling_SPEC_13-10-26.md` (edit), `process/decisions.md` (append one entry), `process/MASTER-PLAN.md` (rows for S-T0..S-T6 and the new ceiling question). Check the real paths of decisions.md and MASTER-PLAN.md in the root context docs (they live next to all-context.md; the entry-set doc names them). Nothing else.
**Depends:** none. **ACs covered:** AC-19, AC-23 (wording), plus the amendment list above; closes OQ-12, OQ-13.
**Steps.** (1) Apply the amendments in "SPEC amendments"; add a change-log line dated 14-10-26; keep AC numbering. (2) Append one decisions entry "Data integration tooling D1-D9" with the rejected alternatives. (3) Add registry rows with ids, status planned, dependencies, estimates. (4) Run the process validators named in all-context.md.
**Tier.** RT0 (no code). Commands: `grep -c "rea-agents setup" <SPEC>` must show setup only in the historical/rejected context; `git diff --stat origin/main...HEAD` lists only the three files; the router/protocol validators from all-context.md exit 0.
**Done when:** diff limited to the 3 files; owner reviews at `review` (docs-only slice, owner-reviewed).
**Must NOT:** touch code, other plans, CLAUDE.md, AGENTS.md; change AC numbering; run anything against the network.
**Cost:** 1.0-2.0 USD; basis S9F 1.01 (docs/small), margin for three files.
**Envelope hint:** read Common rules + this range + the SPEC lines 23-35, 91-116, 132-148 (about 8 KB).

## S-T1: Skeleton, dependency isolation, CI-visible guards (RT2)

**Objective.** Create the tooling project and the guards that protect the API install, so every later slice builds inside a fenced area.
**Owned:** `tools/data-integration/pyproject.toml`, `tools/data-integration/uv.lock`, `tools/data-integration/README.md`, `tools/data-integration/src/data_integration/{__init__,types,status,paths}.py`, `tools/data-integration/tests/{conftest,test_skeleton}.py`, `api/tests/tooling_guards/{__init__,test_tooling_isolation,test_marker_audit}.py`, `.gitignore` (append only). (Under 12 files; `uv.lock` is generated.)
**Depends:** none. **ACs:** AC-2 (guard), AC-4, AC-5 (script), AC-15 (static audit), AC-21 (gitignore half; index test is built here, store test in S-T2).
**Contents.** `pyproject.toml`: name data-integration, requires-python >=3.12, exact pins `scrapling==0.4.15` plus the fetcher extra its docs require, pandas/pyarrow with the same ranges as `api/pyproject.toml`, dev group pytest; pytest config `pythonpath = ["../.."]` (so `api.data.cache` imports), markers `integration`, `browser`, `antibot`, `addopts = "-m 'not integration and not browser and not antibot'"`. `types.py` pre-defines the interfaces S-T3a/S-T3b share: `FetchOutcome`, `Fetcher` protocol (`fetch(url, pass_) -> FetchOutcome`), `ParsedTable`. `status.py`: the closed status set (ok, refused, robots_blocked, timeout, connection_failed, http_error, challenge_page, changed, uncertain, invalid, cache_hit; extend only here). `paths.py`: resolves approvals/scrape folders from `%LOCALAPPDATA%\my_site\` with env overrides `DIT_APPROVALS_DIR`, `DIT_SCRAPE_DIR`. `.gitignore` adds `*.approval.json`, `**/approvals/`, `**/scrape/*.sqlite*`, `**/*.provenance.snapshots/`, `tools/data-integration/.venv/`.
**Guards (in `api/tests/tooling_guards/`, stdlib only, never import scrapling):** api lock/pyproject contain none of scrapling, playwright, patchright, rea; `api/pyproject.toml` hatch packages equal `["analytics","data","models","routers"]`; `.github/workflows/*` contain no `tools/data-integration` and no `uv sync --project tools`; no python file under `api/` (outside `api/tests/tooling_guards`) mentions `data_integration`; no workflow, `main.py`, router or worker imports it; `.gitignore` carries the approval pattern and `git ls-files` shows no `*.approval.json`; marker audit statically scans `tools/data-integration/tests/**` and fails if a file importing `scrapling`, `http.client`, `urllib.request`, `socket`, `requests`, `httpx` or `playwright` has any unmarked test function (allow-list: tests using the injected fixture server carry no marker only when they use the `fixture_server` fixture name; the audit accepts that fixture).
**Tier.** RT2. Gates: red-first on the guard tests; `UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards -q`; `uv sync --project tools/data-integration && uv run --project tools/data-integration pytest tools/data-integration/tests -q`; AC-5 Hybrid script: create a temp dir, run the sync there, then `git diff --exit-code api/uv.lock` and `uv lock --check --project api` exit 0; `git diff origin/main...HEAD --stat` shows no `.github/` or api code change.
**Done when:** all gates green on the head SHA; full api pytest count = baseline plus new guard tests.
**Must NOT:** edit `api/pyproject.toml`, `api/uv.lock`, workflows, `api/data/cache.py`; add the tooling to any sync step; import scrapling in `api/tests`.
**Cost:** 2.0-3.5 USD; basis S9B 1.72 plus generated lock and several guards.
**Envelope hint:** read Common rules + this range; open `api/pyproject.toml`, `.gitignore`, `.github/workflows/ci.yml`, `api/data/cache.py` (head).

## S-T2: Approval gate, local store, store guards (RT2)

**Objective.** Make "no record, no fetch" mechanically true.
**Owned:** `tools/data-integration/src/data_integration/{approvals,gate,approval_cli}.py`, `tools/data-integration/tests/{test_gate,test_approvals_store,test_approval_cli}.py`, `api/tests/tooling_guards/test_approval_store_guard.py`.
**Depends:** S-T1. **ACs:** AC-1, AC-3, AC-21 (store path + index), AC-22 (approval facts shape, consumed by S-T3b).
**Contents.** `approvals.py`: record schema (id, source, allowed_tier 1-3, allowed_pages, rate policy, robots check date, alternatives checked, owner name, approval date, expiry default 90 days, revision), atomic write (temp file plus replace), corrupt file renamed `.bad`, store path via `paths.py`, never creates a default record. `gate.py`: `request_access(source, tier, store, clock) -> FetchPass | Refused`; `FetchPass` has a private-constructor guard (module-private token); `Refused` carries reason and the five fields from D2; expiry `now >= expiry`. `approval_cli.py`: `python -m data_integration.approval_cli status` prints source, tier, expiry, days left; `add` writes a record from flags and requires `--owner` and `--approved-on`; neither prints secrets.
**Tests (plain functions):** missing store dir, missing file, corrupt file, expired at exactly expiry, one second before, tier 2 asked on a tier-1 record, tier equal and below pass; Refused fields; a fetcher stub that builds a client counter proves zero construction on every Refused reason; FetchPass cannot be built directly; atomic write leaves no partial file when the replace is patched to fail; status output has no key-like strings; store path never inside site-packages (feeds D4 check); the guard test asserts the approvals dir is gitignored and the index holds no record (using `git check-ignore`). Fixture records live in `tmp_path` only.
**Tier.** RT2. Gates: tooling pytest as in Common; `UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards -q`.
**Done when:** both suites green; REAL-DATA check: `find "$HOME" -name "*.approval.json" -newer <stamp>` prints nothing.
**Must NOT:** write to a real `%LOCALAPPDATA%` or `$HOME` path; ship any default or sample approval outside `tmp_path`; touch fetch code.
**Cost:** 2.5-4.0 USD; basis S9C 3.38 (new module plus guard plus CLI).
**Envelope hint:** read Common rules + this range; open S-T1 outputs `types.py`, `status.py`, `paths.py` and `api/data/layout.py` (atomic write pattern only).

## S-T3a: Tier 1 fetch, robots, politeness, errors, logs, cache (RT2)

**Objective.** A polite, gated, fully mapped tier-1 fetcher.
**Owned:** `tools/data-integration/src/data_integration/{fetch_tier1,robots,politeness,logging_setup,response_cache}.py`, `tools/data-integration/tests/{fixture_server,test_fetch_tier1,test_robots,test_politeness,test_logging,test_response_cache}.py`.
**Depends:** S-T1, S-T2. **ACs:** AC-6, AC-7, AC-12 (fetch half), AC-13, AC-14.
**Contents.** `fetch_tier1.Fetcher.fetch(url, pass_)` requires a FetchPass; builds the client only afterwards (Scrapling HTTP fetcher). Robots check on every call through `robots.py` (own parse via stdlib `urllib.robotparser`, fetched once per host and cached); blocked gives `robots_blocked`, no page request. `politeness.py`: per-host min delay, global and per-host concurrency caps, honest user agent (`data-integration/<version>` with no contact data), injectable clock and sleeper. `response_cache.py`: on-disk cache keyed by URL hash beside the scrape dir; second call returns `cache_hit` with zero requests; forced refresh does one allowed request. Errors: timeout, refused connection, HTTP 4xx/5xx, challenge-page markers (block-style fixture strings) map to the closed status set; no exception escapes the module. `logging_setup.py`: one structured line per request (host, path, status, duration, tier; never headers, cookies, query strings with tokens, IPs). `fixture_server.py`: loopback `http.server` fixture bound to port 0 with routes for ok, slow, 500, redirect, robots disallow, challenge page.
**Tier.** RT2 for mocks; the fixture server runs on loopback, allowed because it is not an external network call. Marks: tests using the real client carry the `fixture_server` fixture (audit-accepted). Gates: tooling pytest; burst test with fake clock: N requests never exceed configured delay/concurrency.
**Done when:** tooling suite green; log capture contains no secret-like text; call counters prove AC-1 style zero-client on refusal in the fetcher.
**Must NOT:** import `data_integration.parse`, `normalise`, `pipeline` (owned by S-T3b); touch `api/`; contact any non-loopback host.
**Cost:** 3.0-5.0 USD; basis S9A 3.62 (new module family with fixtures).
**Envelope hint:** read Common rules + this range; open `types.py`, `status.py`, `gate.py`.

## S-T3b: Parse, validate, normalise, store, provenance, adaptive (RT2)

**Objective.** Turn a fetched page into validated cache data with provenance and honest change detection.
**Owned:** `tools/data-integration/src/data_integration/{parse,validate,normalise,store_writer,provenance,adaptive,pipeline}.py`, `tools/data-integration/tests/{test_parse,test_validate,test_normalise_roundtrip,test_provenance,test_adaptive,test_pipeline}.py`, fixture HTML/JSON under `tools/data-integration/tests/fixtures/` (synthetic).
**Depends:** S-T1, S-T2 (interfaces only; tests use a fake Fetcher, not S-T3a). **ACs:** AC-8, AC-9, AC-10, AC-11, AC-12 (pipeline half), AC-22.
**Contents.** `parse.py`: table helper (header-keyed rows, explicit; Scrapling has no table helper), selectors via Scrapling `Selector`/adaptive. `validate.py`: required columns, types, ranges (positive prices, monotonic time, high >= low), minimum rows; failure gives `invalid` with reasons, nothing written. `normalise.py` + `store_writer.py`: build the frame in the `api.data.cache` OHLCV shape and write only through `cache.write_ohlcv` (read `cache.py` first; do not edit it). `provenance.py`: append records to `<dataset>.provenance.json` (fields in D3; approval facts copied from the FetchPass), atomic write, plus test that `cache.write_ohlcv` after the tooling write leaves the provenance file intact. `adaptive.py`: SQLite store path from `paths.py`; refuses a path inside site-packages; lost store gives `uncertain` on first run; relocated or unmatched element gives `changed`/`uncertain`, never a guess, and nothing is stored (AC-8). `pipeline.py`: fetch (via any Fetcher) -> parse -> validate -> adaptive check -> normalise -> store -> provenance; the write happens only after every check passes; second run with the same data leaves identical data and provenance count rule documented (a re-run appends a record only when data changed).
**Tier.** RT2. Gates: tooling pytest; round trip: tooling output read by `api.data.cache` read functions and its freshness code unchanged.
**Done when:** suite green; a deliberately changed fixture yields `changed` and no file written (assert directory empty).
**Must NOT:** edit `api/data/cache.py` or any `.meta.json` writer; import `fetch_tier1`; write outside `tmp_path`; call the network.
**Cost:** 3.5-6.0 USD; basis S9E 3.59 / S9C 3.38 with extra surface (adaptive plus provenance).
**Envelope hint:** read Common rules + this range; open `types.py`, `status.py`, `paths.py`, `api/data/cache.py`.

## S-T4: Tiers 2 and 3, fixture-server tests, owner probe scripts (RT2/RT3)

**Objective.** Browser and anti-bot tiers behind the same gate, plus the scripts the owner runs on Windows.
**Owned:** `tools/data-integration/src/data_integration/{fetch_tier2,fetch_tier3}.py`, `tools/data-integration/tests/{test_tier2_browser,test_tier3_gating}.py`, `tools/data-integration/tests/fixtures/js_page/*`, `tools/data-integration/scripts/{probe_tier1.py,probe_tier2.py}`, `tools/data-integration/README.md` (append probe section; README owner moves from S-T1 to S-T4 here).
**Depends:** S-T3a, S-T3b. **ACs:** AC-16 (script), AC-17 (script), plus tier-3 parts of AC-3 and AC-13.
**Steps.** (0) Probe first: can `/opt/pw-browsers` Chromium serve the tier-2 fixture test in the cloud workspace (point Scrapling's browser fetcher at it; never run `playwright install`)? Record VERIFIED or UNVERIFIED in the report. If unverified, mark the browser test `browser`, keep it deselected, and rely on the owner probe AC-17. (1) Tier 2: browser fetch gated by FetchPass with allowed_tier >= 2; robots check first; JS fixture page rendered content parsed. (2) Tier 3: stealth/anti-bot options passed through only when allowed_tier == 3; block-style fixture pages (challenge text, 403, captcha marker) map to `challenge_page`; tier 3 never claims to bypass. (3) Probe scripts: `probe_tier1.py` starts the loopback server, fetches, parses, stores into a temp cache, prints PASS/FAIL; `probe_tier2.py` same with a JS page and prints browser download size hints and timing; both create a temp approval record in their own temp dir.
**Tier.** RT2 for gating/mapping tests (default run, no browser); `-m browser` and `-m antibot` run only where a browser exists; the owner runs the probes (AC-16, AC-17 stay owner probes). Honest scope: not proven live.
**Done when:** default suite green; browser-marked tests run green where possible or are documented unverified; probe scripts run (tier 1 in cloud; tier 2 only if Chromium works).
**Must NOT:** call `playwright install`; touch real sites; claim tier-3 effectiveness; edit S-T3 modules (extend via new files; need a change there -> `needs_input`).
**Cost:** 3.0-5.5 USD; basis S9D 3.38 (new feature plus owner probe scripts).
**Envelope hint:** read Common rules + this range; open `fetch_tier1.py`, `gate.py`, `fixture_server.py`, `status.py`.

## S-T5: REA wrapper, evidence template, docs, router row (RT2)

**Objective.** The allow-listed REA wrapper and the one documented workflow.
**Owned:** `tools/data-integration/rea/{wrapper.py,allowlist.py}` (under the project, python), `tools/data-integration/tests/{test_rea_wrapper,test_rea_evidence}.py`, `tools/data-integration/rea/evidence_template.md`, `process/context/data-sources/all-data-sources.md` (add one section), `process/context/all-context.md` (one routing row plus keywords), `api/tests/tooling_guards/test_rea_guards.py`.
**Depends:** S-T0, S-T1. **ACs:** AC-18, AC-19 (amended), AC-23 (amended).
**Wrapper.** Calls `npx -y rea-agents@6.4.0 <command> --json` (exact pin) only when the command is on the allow-list: analyze-javascript-application, recover-javascript-sources, compare-javascript-export-shapes, compare-application-versions, compare-source-to-bundle, trace-javascript-semantics, trace-application-feature, inspect-analysis-view, inspect-evidence-bundle, compare, compare-web-captures, compare-web-screenshots, inspect-web-network-capture, trace-web-module-imports, trace-web-source-location, export-web-scripts, and the live-browser group analyze-web-bundle, capture-web-screenshot, capture-browser-scenario, inspect-web-page (live commands need `--source` naming a source from the findings note). REJECTS everything else: setup, update, uninstall, mcp, completions, any argv token `--update` or `--mcp`, native/APK/ADB/firmware/process/Apple/JEB/managed, runtime-capture/electron, unknown. Saves stdout JSON into a dated evidence folder (valid single JSON object, 15 top-level keys, deterministic across runs; redact the two absolute paths `subject.local_path` and `normalized_result.input_path`); progress stays on stderr. Tests use a stub runner (no npx call); the real call is a tester check where Node >=22.19 exists (static analysis verified in the cloud workspace; live-browser needs a Chrome-family browser).
**Evidence template** (one per source, public repo): header (source, REA version, date, command, raw output path), one line per finding tagged VERIFIED or ASSUMED, fixed footer: "REA cannot see server-side methodology and does not search public datasets. Nothing above says how the numbers are produced on the provider's server."
**Docs.** The 'New dataset workflow' section: 4 steps, evidence templates, approval fields, local-store backup guidance, the wrapper how-to, the rule "no scraped data in git-tracked directories without a recorded redistribution check", the statement that Farside's on-demand refresh is outside the tooling. Router row and keywords (REA, scrapling, scrape, approval). Keep both files within budget; run the router/context validators from all-context.md.
**Tier.** RT2. Gates: tooling pytest; `UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards -q` (guard: no api file imports rea; `git diff origin/main...HEAD -- .claude CLAUDE.md AGENTS.md .mcp.json` empty); context validators.
**Done when:** all green; allow-list test rejects setup, update, mcp, `--update`, `--mcp` and an unknown command with a typed refusal and no subprocess call.
**Must NOT:** run `rea-agents setup`, create `.mcp.json`, edit `.claude/` or agent configs, write real evidence into the repo, exceed the doc size budgets.
**Cost:** 3.0-5.0 USD; basis S9D 3.38 plus docs and validators.
**Envelope hint:** read Common rules + this range; open `all-data-sources.md` and the router part of `all-context.md`.

## S-T6: First dataset, long BTC history, workflow steps 1-4 (RT1/RT2)

**Objective.** Run the real workflow once; scraping happens only with an owner approval.
**Owned:** `process/general-plans/active/data-integration-tooling_13-10-26/notes/btc-history/{rea-findings,alternatives,redistribution}_NOTE_*.md`; if (and only if) step 2 finds an API/dataset: one adapter module plus test under `api/data/` and `api/tests/data/` whose exact names the worker proposes and the planner approves at `needs_input` before writing code (unknown now, depends on the finding).
**Depends:** S-T0, S-T5, S-T3b. **ACs:** AC-20 (owner review).
**Steps.** (1) Step 1 REA findings note using the wrapper on candidate public pages (static commands; live commands only on sources named in the note); every line VERIFIED or ASSUMED. (2) Step 2 alternatives note: free APIs and public datasets first, with licences. (3) If a suitable source exists: integrate through the normal adapter path with provenance (via S-T3b pipeline or a normal adapter, per the finding), output to the gitignored cache only, redistribution check recorded; no scraping. (4) If scraping is the only option: STOP at `needs_input` asking the owner for an approval record; never scrape without one, never in the cloud.
**Tier.** RT1 for docs-only outcome; RT2 if an adapter lands (pytest for the adapter on synthetic fixtures). Owner review is the proof for AC-20.
**Done when:** both notes exist; either integrated with tests and provenance, or a stop request with the evidence is filed.
**Must NOT:** scrape; commit data into tracked dirs; create approval records; change cache code.
**Cost:** 2.5-5.0 USD; basis S9E 3.59, research-heavy, adapter optional.
**Envelope hint:** read Common rules + this range; open the evidence template, `all-data-sources.md` new section, `api/data/cache.py` head.

## Overview and Acceptance Criteria

Overview: build the developer-run tooling in the order of the slice index. Acceptance Criteria: the 23 SPEC ACs (as amended above) are covered by slices per the Verification Evidence table; AC-16, AC-17 and AC-20 stay owner probes/review.

## Phase Completion Rules

A slice is VERIFIED only with its gates green on the head SHA plus the planner's EVL re-run; code-only completion is CODE DONE. Known-Gap rows keep the gate CONDITIONAL.

## Implementation Checklist

1. S-T0 records. 2. S-T1 skeleton and guards. 3. S-T2 approval gate. 4. S-T5 REA wrapper and docs. 5. S-T3a tier-1 fetch. 6. S-T3b parse/store/provenance. 7. S-T4 tiers 2-3 and probes. 8. S-T6 first dataset.

## Risks and rollback

| Risk | Mitigation |
|---|---|
| Scrapling pre-1.0, one maintainer | exact pins; update only on owner request |
| Tooling tests not in CI | stated limit; tester runs them in the tooling venv at EVL; owner may later add an opt-in CI job |
| Windows/Python 3.12 gaps | owner probes AC-16, AC-17 |
| Wrong adaptive match stores bad data | D4: write only after validation; changed/uncertain stores nothing |
| Approval records lost with the disk | docs backup guidance; records are small JSON |
| Public repo redistribution | rule in docs; redistribution note in S-T6 |
| Spend over ceiling | owner sets a new ceiling before EXECUTE; ask point 7 USD per slice |

Rollback: the work is additive. Delete `tools/data-integration/`, `api/tests/tooling_guards/`, the docs section and router row, the `.gitignore` additions; restores the prior state. No existing adapter, cache code or workflow is modified.

## Touchpoints

New: `tools/data-integration/**`, `api/tests/tooling_guards/**`, task-folder notes. Edited: `.gitignore` (append), `process/context/data-sources/all-data-sources.md`, `process/context/all-context.md`, the SPEC, `process/decisions.md`, `process/MASTER-PLAN.md`, optionally one new BTC adapter + test (S-T6). Read only: `api/data/cache.py`, `api/data/layout.py`, `api/pyproject.toml`, workflows.

## Public Contracts

`request_access(source, tier, store, clock) -> FetchPass | Refused`; closed status set in `status.py`; `<dataset>.provenance.json` record shape; `<source>.approval.json` shape; env overrides `DIT_APPROVALS_DIR`, `DIT_SCRAPE_DIR`; pytest markers `integration`, `browser`, `antibot`. No API route, no schema, no frontend change.

## Blast Radius

About 45 new files, 6 edited process/config files; risk class: secrets/trust boundary (approval gate) and dependency isolation. API runtime and CI unchanged (guards enforce).

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| test_gate (missing/expired/corrupt, zero client built) | Fully-Automated | AC-1 |
| tooling_isolation guard (no import from api, workflows) | Fully-Automated | AC-2 |
| tier-above-record refusal | Fully-Automated | AC-3 |
| api lock/pyproject/workflow scan | Fully-Automated | AC-4 |
| clean-env install script, api lock unchanged | Hybrid | AC-5 |
| robots disallow fixture on each tier | Fully-Automated | AC-6 |
| burst test with fake clock | Fully-Automated | AC-7 |
| changed fixture gives changed, nothing stored | Fully-Automated | AC-8 |
| validation failures write no file | Fully-Automated | AC-9 |
| provenance fields | Fully-Automated | AC-10, AC-22 |
| round trip via api.data.cache | Fully-Automated | AC-11 |
| second run call counter, forced refresh | Fully-Automated | AC-12 |
| error mapping, no exception escapes | Fully-Automated | AC-13 |
| structured log capture | Fully-Automated | AC-14 |
| static marker audit | Fully-Automated | AC-15 |
| probe_tier1.py on Windows 3.12 | Agent-Probe (owner) | AC-16 |
| probe_tier2.py after browser install | Agent-Probe (owner) | AC-17 |
| docs grep + router validators | Fully-Automated | AC-18 |
| REA allow-list wrapper test, git diff on agent config | Fully-Automated | AC-19, AC-23 (amended) |
| notes, adapter or stop request, owner review | Hybrid | AC-20 |
| git-index and gitignore guard | Fully-Automated | AC-21 |

Owner probes (not provable in cloud): AC-16, AC-17, AC-20 review, Windows behaviour of the REA wrapper. Known-Gap residuals (gate stays CONDITIONAL): tiers 2 and 3 against real sites; REA web modes on a real page; browser test in cloud if Chromium unverified (backlog stub to write at EXECUTE).

## Test Infra Improvement Notes

(none identified yet) Candidate: an opt-in CI job for the tooling venv, deliberately not added now.

## Resume and Execution Handoff

1. Selected plan file: this file.
2. Last completed step: PLAN written 14-10-26; no slice executed.
3. Validate-contract status: pending (see heading below).
4. Context loaded: SPEC, all-context.md router, operating-instructions.md, api/pyproject.toml, .gitignore, ci.yml, cache.py, data-sources doc.
5. Next: VALIDATE; owner sets the new spend ceiling; then wave 1 (S-T0, S-T1). Planner re-checks slice line ranges after any edit to this file.

## Validate contract

pending VALIDATE
