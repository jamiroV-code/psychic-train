---
domain: plan
iteration: 1
date: 2026-10-14
plan: data-integration-tooling_PLAN_14-10-26.md
mode: VALIDATE first pass (PVL cycle 1)
gaps_found: 14
fail_count: 1
concern_count: 13
applied: 0
loop_status: validated_blocked
---

# PVL iteration 001 - data-integration-tooling (first pass; results.tsv row 1)

Code under test: origin/main `b66d9b4` plus plan commit `bca9764`. Plan read: 259 lines, 39,213 B; `validate-plan-artifact.mjs` 0 failures, 2 warnings (no testing-context mention, no closing next-instruction). One sequential validator ran Layer 1 and Layer 2 inline. No repo file was edited except this report and results.tsv; the plan still says "pending VALIDATE" (no Gate stamped).

## Verdict: BLOCKED (1 BLOCKER, 9 MAJOR, 4 MINOR groups). Return to the plan agent, fix cycle 1 of 2.

| Layer 1 dimension | Status | Why |
|---|---|---|
| Infra fit | FAIL | S-T0 breaks the one-registry-writer rule (F1); `data_integration` is not importable as specified, duckdb missing (F4) |
| Test coverage | CONCERN | AC-6 on tiers 2/3 has no owner/test (F8); guards fail at baseline (F5); tooling tests are EVL-only, not CI |
| Breaking changes | CONCERN | no existing test breaks (checked, see below); planner budget gate would go over cap (F10); live cache overwrite risk (F11) |
| Security surface | CONCERN | FetchPass is not bound to URL/host, record minting and source-name handling open (F6, F7, F9) |

## Findings (id, severity, evidence, exact fix)

**F1 BLOCKER - S-T0 makes a WORKER edit the registry.** Evidence: plan line 82 (Owned: `process/MASTER-PLAN.md` rows) vs `process/MASTER-PLAN.md:19` ("only the Master Planner session edits this file. Workers request updates in report headings 9 and 10") and `master-planner.md:38` ("One registry writer"). It is also circular: a task needs its registry row (status `approved` = standing EXECUTE consent) before dispatch, so S-T0 cannot create its own row. Fix: S-T0 owns the SPEC only (worker, RT0). The Planner adds the registry rows at dispatch (one umbrella row, see F10). The decisions entry goes to a planner-side records step (or the worker drafts it in report heading 9/10 and the planner commits it); the S-T0 gate becomes `git diff --stat` lists exactly the SPEC.

**F2 MAJOR - wrong paths.** Plan lines 25, 82, 207 name `process/decisions.md`; the real file is `process/context/decisions.md` (the router, `all-context.md`, puts decisions.md next to itself; north-star.md and current-state.md are also in `process/context/` but the plan cites them by bare name only, fine). `process/MASTER-PLAN.md` is correct. Also: decisions.md has an Index table (lines 14-31) plus entries D-1..D-14, so "append one entry" must add an Index row and use ID D-15; the plan's own D1-D9 collide with existing D-1..D-9 (rename to DIT-1..DIT-9 in the entry). Fix: correct the three paths, specify Index row + D-15 + DIT-n naming.

**F3 MAJOR - worker read cap (36,000 B).** Base = CLAUDE.md 13,443 + envelope 4,000 (assumed) + Common rules lines 39-78 (10,122) = 27,565 B, leaving 8,435 B. Slice index line ranges match the headings (79, 91, 104, 117, 129, 141, 153, 167, 179). Tail range "179-256" is stale (file has 259 lines; `## Validate contract` is at 257). `sed -n 'a,bp' | wc -c` results (E = estimate for files that do not exist yet: types 1.5 KB, status 0.9, paths 1.5, gate 3.5, fetch_tier1 5, fixture_server 3, template 1.5, new docs section 3.5):

| Slice | Slice B | As written (total) | Cut | After cut |
|---|---|---|---|---|
| S-T0 | 1,654 | 37,155 (+ unlisted MASTER-PLAN/decisions reads, about 41 KB) | SPEC lines 29, 91-116, 147-148, 150-173 only (5,917 instead of 7,936); no registry/decisions in the worker | 35,136 |
| S-T1 | 3,684 | 40,194 (ci.yml 3,388, cache.py head 2,913) | drop ci.yml; cache.py lines 1-30 (1,106) | 34,999 |
| S-T2 | 2,500 | 45,684E (layout.py whole 11,719) | layout.py lines 106-142 (1,125) | 35,090E |
| S-T3a | 2,330 | 35,795E | tight; gate.py signatures only | about 34.5k |
| S-T3b | 2,519 | 62,746E (cache.py whole 28,762) | cache.py 118-131 + 158-187 (1,789) | 35,773E |
| S-T4 | 2,373 | 42,338E | signatures only (grep def/class) | about 33.8k |
| S-T5 | 3,473 | 64,443 (all-data-sources.md 27,574 + router 5,831) | even with line ranges (frontmatter, Standing Rules 45-66, triggers 397-411, routing rows) 36,252: split docs + router row into S-T5b (RT0) | code part 31,038; docs part small |
| S-T6 | 1,849 | 37,327E | cache.py lines 1-30 | 35,520E |

**F4 MAJOR - import feasibility (probe run, VIABLE).** The plan specifies pytest `pythonpath = ["../.."]` (repo root) only, `pandas/pyarrow` ranges, no duckdb, no build-system. Findings: (a) `api/data/cache.py:17` imports `duckdb` at module top; the plan's dependency list omits it. (b) `api` has no `__init__.py` (namespace package); `api/data/__init__.py` is empty; cache.py needs only duckdb, pandas, pyarrow (lazy, line 240), stdlib. (c) A path dependency on `api` would pull all 64 locked packages and would not give `api.data.cache` anyway (hatch packages `analytics/data/models/routers` install as top-level `data`), so the repo-root path is the right mechanism. (d) Verified in scratch: with only `scrapling[fetchers]==0.4.15`, pandas, pyarrow, duckdb, pytest: `uv lock` resolves 36 packages in 4 s; `uv sync` 38 s; with the repo root on the path `from api.data import cache` works and loads none of fastapi, ccxt, pandas_ta_classic, statsmodels, pydantic, httpx. (e) The tooling venv is NOT lighter: 676 MB site-packages versus 581 MB for the API venv (Python 3.13 in this sandbox; the sandbox default python3 is 3.11, uv finds 3.13). "Light" means not in the default API install and CI, not small. (f) Verified: with no build-system and only `../..` on the path, `import data_integration` fails (ModuleNotFoundError), so S-T1's own tests cannot run as specified. (g) `python -m data_integration.approval_cli` and the probe scripts run outside pytest; no repo-root mechanism is specified. (h) Resolved versions drift from the API lock (pyarrow 26.0.0 vs 25.0.1, duckdb 1.5.6 vs 1.5.5). (i) S-T5 puts the wrapper at `tools/data-integration/rea/`, outside `src/`, so it is not importable. Fix: add duckdb; add `src` to pythonpath or a hatchling build-system with `packages = ["src/data_integration"]`; add one `_repo_root()` helper in `paths.py` that puts the repo root on `sys.path` for CLI/probe use; pin pandas, pyarrow, duckdb to the api/uv.lock versions and guard parity; move the wrapper to `src/data_integration/rea/`; add a test that importing `api.data.cache` loads none of fastapi/ccxt/pandas_ta_classic. Probe meaning for S-T1 if the worker doubts: `uv lock` + `uv sync` + `python -c "import sys; from api.data import cache; assert not {'fastapi','ccxt'} & set(sys.modules)"`; VIABLE = exits 0, NOT-VIABLE = ImportError or heavy module loaded (then vendor a 40-line parquet writer and drop the round-trip claim).

**F5 MAJOR - S-T1 guards fail on the untouched base.** "api lock/pyproject contain none of scrapling, playwright, patchright, rea": substring `rea` matches `api/pyproject.toml` ("real"), and the workflow scan for playwright hits `.github/workflows/ci.yml:9` (comment "Playwright E2E"). The SPEC amendment for AC-4 repeats the workflow scan. Fix: match exact distribution names (parse `[project].dependencies` and `name = "..."` in uv.lock; `rea-agents` is npm, not Python, so check only scrapling, playwright, patchright, rea-agents); workflows: assert only absence of `tools/data-integration` and `uv sync --project tools`.

**F6 MAJOR - the gate can be bypassed by design.** (a) D2 promises import-boundary tests "scoped to the new tooling"; no slice owns one. Add to S-T1 or S-T2: only `fetch_tier1/2/3.py` (and `robots.py` via the pass) may import scrapling fetchers, urllib.request, http.client, httpx, requests, socket, playwright. (b) `request_access(source, tier, store, clock)` has no URL; `allowed_pages` is stored but never enforced. FetchPass must carry host/allowed pages; every fetcher checks the URL and every redirect target against it (and robots per hop); add tests (pass for host A refuses host B and a redirect to B). (c) A module-private token is convention only: acceptable, but the test must also assert the fetchers reject a duck-typed pass (isinstance on the real class).

**F7 MAJOR - records, source names, expiry.** (a) `<source>.approval.json` is built from a free `source`: validate `^[a-z0-9][a-z0-9_-]{0,63}$`, reject separators, Windows reserved names, and case-fold. (b) `approval_cli add` lets any shell session (agent) mint a record; require an interactive TTY confirmation (typed source name) and refuse when stdin is not a TTY; print whether `DIT_APPROVALS_DIR` override is active and never print the full path (it holds the Windows user name; show `%LOCALAPPDATA%\my_site\approvals`). (c) Expiry: store UTC ISO-8601 with `Z`, reject naive datetimes and a naive clock as `store_corrupt`/typed Refused (no TypeError; "no exception escapes"); define the 90 days from the approval datetime; add tests for naive clock and approval date in the future. The `status` command is Python (`python -m data_integration.approval_cli status`); "like `set-lse-key.ps1 -Status`" only describes the behaviour. Say so in D8.

**F8 MAJOR - AC-6 on tiers 2/3.** S-T4 ACs list AC-16, AC-17, tier-3 parts of AC-3/AC-13, not AC-6; the tier-3 step never states a robots check; browser-marked tests are deselected, so no default test proves robots-before-navigation. `robots.py` fetches via stdlib `urllib.robotparser` (no pass, no politeness, no UA, no log; robotparser treats 4xx as allow-all, 5xx as disallow-all, timeout unspecified). Fix: add AC-6 to S-T4; unmarked test with a stub navigator proving robots.txt is fetched (loopback) before navigation and zero navigations when disallowed, for tiers 2 and 3; robots fetch requires a FetchPass, shares the UA/politeness/logging, fails closed on error or timeout.

**F9 MAJOR - REA wrapper exactness not specified.** Required: exact frozenset match on the first token (no prefix, no regex, case-sensitive); per-command flag allow-list (only `--json`, validated `--source`, an output path pinned inside the evidence folder), reject any other token starting with `-` including `--update=x`; subprocess list with `shell=False`; on Windows `npx` resolves to `npx.cmd`, which re-parses arguments (batch argument injection), so also restrict every value to a conservative regex and forbid `"%^&|<>`; set `npm_config_ignore_scripts=true`. "Live commands need `--source` naming a source from the findings note" is not mechanical: define it (source must appear in a given findings file) or make it an owner flag. The dated evidence folder has no stated location: default outside the repo plus gitignore it. The tester's real `npx -y rea-agents@6.4.0` call downloads from the npm registry, which contradicts the Safety rule "no live network"; list it as an owner/tester-only Hybrid check with that exception.

**F10 MAJOR - planner budget and routing.** Baseline `PLANNER-BUDGET` run: planner_fixed 53,040 of 56,000 (headroom 2,960), rc=1 already because `current-state.md` is 11,465 > 8,000 (pre-existing, not caused by the plan). `process/MASTER-PLAN.md` is 17,076 of 19,000 (D-12); eight new rows at about 350-450 B would exceed the ceiling and the 56,000 cap. Router part of `all-context.md` is 5,831 of 7,000 (ok for one row). The "Current Root Entry Points / Context Groups" tables are GENERATED (`<!-- GENERATED:routing -->`): the new row goes in the hand-written Task Routing Table, and keywords go in the `all-data-sources.md` frontmatter, then `discover-context.mjs --check-routing`. `all-data-sources.md` (27,574 B) has no validator cap; the plan says "budget" without a number: set the new section at most 3,500 B. Fix: one umbrella registry row (at most 600 B), or archive rows first per the trim rule.

**F11 MAJOR - live cache overwrite.** `write_ohlcv` replaces the whole series (`api/data/cache.py:158-187`; `api/tests/conftest.py:2-12` records the RFC-005 incident). Tooling tests do not see `api/tests/conftest.py::isolated_cache`. Fix: tooling `conftest.py` autouse fixture sets `SCREENER_CACHE_ROOT` before the first import and monkeypatches `cache.CACHE_ROOT`; add a real-data-untouched guard like `api/tests/deploy/test_zz_real_data_guard.py`. S-T6: the BTC write must use a key that does not exist yet (or refuse when a longer/other-source series exists, with backup note), because D9 writes to the owner's real `api/data/cache/ohlcv`.

**F12 MINOR - harness hook.** `.claude/.vcignore` does NOT exist, so `DEFAULT_PATTERNS` apply (`.claude/hooks/scout-block/pattern-matcher.cjs:15-34`): node_modules, dist, build, .next, .nuxt, __pycache__, .venv, venv, vendor, target, .git, coverage; segment-exact, and the hook scans the whole command text (it blocked my own greps containing those words). Commands whose sub-command starts with `uv`, `python`, `npx`, `npm run ...` (`scout-checker.cjs:25-28`) or run from `.venv/bin|Scripts` are allowed, so the plan's gates (`uv run --project ...`, `UV_FROZEN=1 uv run ...`) pass; `grep`, `ls`, `find`, `du`, `git` on those names are blocked, as are Read/Glob/Grep on the default `tools/data-integration/.venv` (S-T3b/S-T4 workers cannot read Scrapling source there). Verified: `UV_PROJECT_ENVIRONMENT=<path outside the repo>` works. Fix without touching the hook: plan sets `UV_PROJECT_ENVIRONMENT=$HOME/.cache/dit-env` for cloud/tester runs (the `.gitignore` `.venv/` line stays for the owner's default), tells workers to read library source via `uv run --project ... python -c "import inspect, scrapling..."`, forbids directory names build, dist, target, vendor, coverage, venv under `tools/`, and lists "no Read/Grep inside the env" as a known limit. REA evidence/npm cache live under `node_modules`; same rule.

**F13 MINOR - cost.** Sums reconcile: lows 1.0+2.0+2.5+3.0+3.0+3.5+3.0+2.5 = 20.5; highs 2.0+3.5+4.0+5.0+5.0+6.0+5.5+5.0 = 36.0; midpoint sum 28.25 (plan says about 27). Waves 1+2 alone cost 8.5-14.5, above the 13.9 left at the high end. Highest risk of passing the 7 USD ask point: S-T3b (7 modules, Scrapling adaptive semantics unknown, cache round trip; basis S9E 3.59 / S9C 3.38 undercounts a first-use dependency), S-T4 (browser probe loop in the sandbox, two tiers, scripts), S-T1 (first uv project plus generated lock, 3 guards, AC-5 script; basis S9B 1.72 is too low, expect 3-5), S-T5 unsplit (wrapper + docs + router + Node check; expect 4-6, split fixes it). No slice has a past analogue near S5b 9.99 (UI iteration), so >15 USD is unlikely.

**F14 MINOR - small items.** (1) The S-T5 guard `git diff origin/main...HEAD` cannot run in a shallow CI checkout: keep it a worker gate command, not a CI test. (2) Marker audit is import-text based: also treat `data_integration.fetch_tier*` as network modules. (3) The `fixture_server` pytest fixture has no owner (S-T3a does not own `conftest.py`). (4) S-T6 notes named `*_NOTE_*.md`; task-folder types are PLAN|SPEC|REPORT|REF. (5) Provenance location unspecified (say `api/data/cache/ohlcv/<symbol>/<tf>.provenance.json`). (6) `grep -c "rea-agents setup" <SPEC>` is not mechanical (5 SPEC mentions: lines 29, 115, 128, 159, 163); require each remaining line to contain "rejected" or "superseded". (7) AC-5 script is in no Owned list; README.md ownership is stated twice (S-T1, S-T4). (8) Spend ceiling: the owner must set it before EXECUTE (plan states it). (9) `UV_FROZEN=1` must not be exported before the tooling lock exists.

## Hidden-break search (no existing check breaks; evidence)

- `.gitignore`: `api/tests/data/test_lse_adapter.py:196` (check-ignore of cache paths) and `api/tests/scripts/test_snapshot_workflow_schedules.py:304` (own temp `.gitignore`) are unaffected; no tracked file matches `*.approval.json`, `**/approvals/`, `**/scrape/*.sqlite*` (`git ls-files` empty).
- Tree scanners: `api/tests/analytics/test_no_verdict_symbols.py:41` walks `api/` and `web/` .py files (new guard files contain none of its tokens; `.venv` is skipped); no test enumerates top-level folders or counts workflows except `test_ci_workflow.py` / `test_snapshot_workflow_schedules.py` (workflows untouched). Deploy guards (`securestring`) scan `deploy/*.ps1` only.
- Hatch packages `["analytics","data","models","routers"]` (`api/pyproject.toml:40`): unchanged, guard passes on base. `uv.lock`: `uv sync --project api --frozen` works untouched; `git status` stayed clean after my scratch syncs.
- CI: `ci.yml` has no path filter on pull_request (a `tools/`-only PR runs both jobs; harmless); `paths-ignore` is only `api/data/cache/**`. `uv run --project api pytest api/ -q` collects `api/tests/tooling_guards/` (needs `__init__.py`, as the other test dirs have).
- Validators: `validate-all-context` has no size cap; it warns on missing backticked `process/...` paths (router row must cite existing paths). The 56,000 B planner cap is F10.

## AC coverage (AC -> slice -> proof; where it runs)

| AC | Slice | Proof | Runs in |
|---|---|---|---|
| 1 | S-T2 | test_gate, zero-client counter | tooling venv |
| 2 | S-T1 | test_tooling_isolation | CI |
| 3 | S-T2, S-T4 | tier-above-record, test_tier3_gating | tooling venv |
| 4 | S-T1 | lock/pyproject/workflow scan | CI (fix F5) |
| 5 | S-T1 | Hybrid install script (no owner/file) | sandbox, network |
| 6 | S-T3a (tier 1), S-T4 missing | test_robots | tooling venv; tiers 2/3 gap (F8) |
| 7 | S-T3a | burst, fake clock | tooling venv |
| 8, 9, 10, 11, 22 | S-T3b | test_adaptive / validate / provenance / roundtrip | tooling venv |
| 12 | S-T3a + S-T3b | call counter | tooling venv |
| 13 | S-T3a, S-T4 | error mapping | tooling venv |
| 14 | S-T3a | log capture | tooling venv |
| 15 | S-T1 | marker audit | CI |
| 16, 17 | S-T4 | probe scripts | owner PC only |
| 18 | S-T5 | docs grep + validators (no named test) | node validators, not CI |
| 19, 23 (amended) | S-T0 wording, S-T5 | test_rea_wrapper, test_rea_guards | tooling venv + CI guard |
| 20 | S-T6 | owner review | owner |
| 21 | S-T1, S-T2 | gitignore + git-index guard | CI |

Summary: 23 ACs, 0 orphans, 1 partial (AC-6 tiers 2/3), 4 CI-run (2, 4, 15, 21), 14 tooling-venv/EVL only, 2 sandbox or validator (5, 18), 3 owner (16, 17, 20). Windows REA wrapper behaviour stays an owner probe. D6 amendments (L3, AC-19, AC-23, OQ-13) are covered by S-T0 wording plus S-T5 test.

## Decisions consistent with the SPEC

L1-L7 and D1-D9 match: REA wrapper only (no `rea-agents setup` run anywhere in the plan; mentions are rejections), Farside untouched (D2, D7 docs statement), approvals outside the repo, no per-use go for tier 3 (AC-3), first dataset long BTC history (D9). Remaining SPEC text still contradicts until S-T0 lands (L3 line 29, AC-23 line 115, risks 128, INNOVATE Q8 159).

## Fix routing

Plan agent: F1-F11 into the plan body (no overlay), F12-F14 as text edits; keep slice line ranges and byte numbers consistent after edits (recompute with `sed -n a,bp | wc -c`). Re-VALIDATE from V1 afterwards.
