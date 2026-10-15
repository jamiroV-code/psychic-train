---
domain: plan
iteration: 3
date: 2026-10-14
plan: data-integration-tooling_PLAN_14-10-26.md
mode: VALIDATE (PVL cycle 3, scope = Amendment A1 / S-T7 only)
gaps_found: 11
fail_count: 0
concern_count: 11
applied: 0
loop_status: validated_conditional
---

# PVL iteration 003 - Amendment A1 (S-T7 command-line front door, T62)

Code under test: local HEAD `cc239c7` (waves 1-3 merged, plan commit with A1). A1 = plan lines 327-343 (4,005 B), 18 lines added, 0 removed, earlier lines and the single `Gate: PASS` untouched (`grep -c "Gate: PASS"` = 1 before; 1 after, nothing written to the plan). `validate-plan-artifact.mjs`: 0 failures, 1 advisory warning (same as iteration 2). Baselines measured: tooling suite 253 passed; `api/tests/tooling_guards` 41 passed.

## Verdict: CONDITIONAL (0 FAIL, 11 CONCERN). No addendum written (PASS only). First-pass CONDITIONAL is not terminal: supplement A1 text, then re-validate.

The design fits the locked decisions (gate unchanged and still the only FetchPass source, run goes through `request_access`, tiers bounded by the record, no new network import site). The concerns are specification gaps against the merged code, two of them security-relevant.

## Check 1: locked decisions DIT-1..9, L1-L7

Consistent: `approvals` delegates to `approval_cli.main` (TTY rule `sys.stdin.isatty()` preserved); `request_access(source, tier, store, clock)` (gate.py:67) is the only FetchPass source and checks tier <= allowed_tier (gate.py:86); `pipeline.run` and `fetch_tier1._fetch` re-check `permits(url)` (pipeline.py:42, fetch_tier1.py:94); L2 satisfied (explicit command only); `__main__` is a new entry point inside the AC-2 guard scope. Gaps below: C3-C6.

## Check 2: signatures vs reality, read total

| Claim | Reality | Result |
|---|---|---|
| `run_rea` callable | `run_rea(command, args=(), *, confirm_source, findings, runner, today)` wrapper.py:99; live commands need `confirm_source` + `findings` (wrapper.py:168), and `--findings` is NOT an allowed flag | C7 |
| pipeline entry | `pipeline.run(fetcher, pass_, *, url, selector, symbol, timeframe, source_label, min_rows, replace, accept_baseline, adaptive_path, clock)` pipeline.py:30; takes a `Fetcher` object with `.fetch(url, pass_)` (types.py:21) | C4, C8 |
| tier-1 fetch | `fetch_tier1.fetch(url, pass_, *, cache, refresh, politeness, robots, proxy, timeout, max_redirects, logger)` is a function, not a Fetcher | C8 |
| `--refresh` | exists on `fetch` (fetch_tier1.py:81) | ok |
| paths | env `DIT_APPROVALS_DIR`, `DIT_SCRAPE_DIR`, `DIT_EVIDENCE_DIR`, `LOCALAPPDATA` (paths.py:17-37) | ok |
| tiers 2-3 | `fetch_tier2/3.py` do not exist; S-T4 plan section (l.138-149) defines no entry signature | C8, C9 |

Exact worker read total (CLAUDE.md 13,443 + envelope 5,200 + Common lines 40-75 6,060 = 24,703 fixed):
- A1 lines 327-343 = 4,005 B (S-T7 subsection alone 332-343 = 3,311 B); the "about 4,400" is high.
- `grep -n "def \|class "` of approval_cli, wrapper, pipeline, gate = 183 + 487 + 65 + 351 = 1,086 B (measured), not "about 5,500". Whole files would be 17,818 B.
- As written: 24,703 + 4,005 + 1,086 = **29,794 B** (plan says 34,603; both under 36,000).
- But that grep shows only the first line of each `def`, so the keyword parameters (the thing the worker needs) are hidden. Use named ranges: `approval_cli.py` main block, `wrapper.py` 99-106, `pipeline.py` 30-44, `gate.py` 67-72 = 1,701 B, plus `paths.py` 983, `status.py` 620, `types.py` 579 = 2,182. Total = 24,703 + 4,005 + 1,701 + 2,182 = **32,591 B**. If the supplement grows A1 to 5,500 B: 34,086 B (still < 36,000). Cut order if over: `_helpers.py` (908), `fetch_tier1.py` 81-89 (543). Never read whole files (46,526 B, over cap).

## Check 3: import-boundary guard

`test_import_boundary.py` flags only network roots (scrapling, urllib.request, http.client, httpx, requests, socket, playwright, curl_cffi, patchright) outside `fetch_tier1/2/3.py`, `robots.py` (+ `scrapling.parser` in parse/adaptive). `cli.py`, `recipe.py`, `__main__.py` importing `data_integration.fetch_tier1/2/3` and `pipeline` pass (module names are not network roots; `ast.walk` also sees lazy imports, so lazy imports are fine). They must not use `urllib.request` or `http.client` (`urllib.parse` is fine). The guard stays unchanged and green.

A registry importing `fetch_tier2/3` works only after T59 merges: the modules do not exist on `cc239c7`. Order: W4 T59 merged, then W5 T62. If S-T7 starts first, importing fails or tier 2-3 cannot be proven; the worker must stop at `needs_input` (no stub modules, no edit of S-T4 files). MASTER-PLAN still reads "Wave 4 of P9 (T59, T60) about to be dispatched" (line 27) and P9 row has no T62: planner must correct before dispatch.

## Check 4: subprocess smoke test (verified)

The tooling env is an editable install (`_editable_impl_data_integration.pth` in `~/.cache/dit-env`), so `sys.executable -m data_integration ...` imports from any cwd; pytest's `pythonpath = ["../..", "src"]` does NOT reach a subprocess. Verified: `python -m data_integration.approval_cli status` with a clean `HOME` prints "no approvals", rc 0, creates nothing (store missing is handled). `python -I` ignores `PYTHONPATH`, so do not use `-I` with PYTHONPATH. Spec for the test: `sys.executable`, `cwd=tmp_path`, minimal env with `DIT_APPROVALS_DIR`, `DIT_SCRAPE_DIR`, `DIT_EVIDENCE_DIR`, `HOME`, `LOCALAPPDATA` all under `tmp_path`, `PYTHONPATH=<tool>/src` as fallback, timeout 60 s. `conftest.py` (S-T1 owned) isolates only the cache, so `test_cli.py` needs its own autouse env fixture.

## Check 5: owned globs

S-T7 creates: `src/data_integration/{__main__,cli,recipe}.py`, `tests/{test_cli,test_recipe}.py`, `api/tests/tooling_guards/test_cli_guard.py` - none exists, none owned by a merged slice (all merged owners are S-T0..S-T3b, S-T5a, disjoint). Disjoint from T59 (fetch_tier2/3, 3 tests, js_page, probe scripts, README append, one extend-only `fixture_server.py` edit - S-T7 does not touch it) and from T60 (process/context docs) and T61 (`btc-history/*_REF_*`, optional adapter). Gap: a `recipes/` folder is named but nobody owns it (C11). Gate convention 6 list not touched.

## Check 6: hidden breaks

- Marker audit (`test_marker_audit.py:13-15`): any tooling test file importing a network module or `data_integration.fetch_tier*` needs every test to carry a marker or take `fixture_server`. `test_cli.py` must therefore not import `fetch_tier*`; it uses an injected fake registry (C10).
- `test_api_code_never_references_data_integration` scans `api/` only and exempts `tooling_guards`: no break. Existing guards do not scan `deploy/`, where the Windows scheduler lives (`deploy/register-tasks.ps1`); `grep` shows no reference today.
- uv.lock/pyproject untouched (no new dependency: stdlib `json`, `re`, `argparse`). Workflows untouched. pytest paths exist. CLI is not in CI (tooling tests EVL-only, as for all tooling).
- Real tier-1 end to end through the CLI cannot be tested on loopback: `permits()` rejects non-default ports (gate.py:52) and the CLI must not take a proxy. So real fetch via CLI is proven only by AC-20 on the owner PC (named residual D).

## Check 7: AC mapping and cost

US-4 (explicit run) and AC-20 prerequisite: yes. AC-1: `run` with missing/expired/corrupt/absent store -> Refused, fake fetcher called 0 times, exit non-zero. AC-3: recipe tier above record -> `tier_too_low`, 0 calls; tier 2/3 registered only after T59. Cost 1.5-3.0 USD plausible against T55 0.88, T57 1.82, T58 1.18 (three modules plus two test files plus a guard, with security-heavy tests); the supplement items below keep it inside, upper end more likely. The "93.30 of 130 USD" spend line is not recorded in MASTER-PLAN (owner/planner item).

## Findings (supplement required in A1 text; plan body untouched)

| ID | Sev | Evidence | Exact fix wanted |
|---|---|---|---|
| C1 | CONCERN (security) | `api/data/cache.py:118-119` `ohlcv_path` = `CACHE_ROOT/ohlcv/<symbol.upper()>/<tf>.parquet`, no validation; `read_ohlcv` interpolates the path into SQL `read_parquet('...')` (l.127-129); A1 l.337 "dataset/cache key" unconstrained | Recipe `dataset` = `symbol` matching `^[A-Za-z0-9][A-Za-z0-9-]{0,31}$` (no `.`, `/`, `\`, `'`) and `timeframe` in {15m,1h,4h,1d,1w}; reject before any cache call; tests: `../x`, `a/b`, `a'b`, `..\\x`, `btc` vs `BTC` collision (upper-cased) |
| C2 | CONCERN (data loss) | `store_writer.write_series(..., replace=True)` overwrites any series (store_writer.py:20); DIT-9 "never replace existing BTC series" | `--replace` allowed only when `provenance.read_records(symbol, tf)` is non-empty (series written by this tool); else refuse "key belongs to the live cache" |
| C3 | CONCERN (function) | pipeline.py:56-58: no baseline -> `uncertain`, nothing stored unless `accept_baseline`; A1 flags `--dry-run --refresh --replace` only, so the first real run (AC-20) can never succeed | Add `--accept-baseline` (CLI flag only, never a recipe key); dry-run states whether a baseline exists |
| C4 | CONCERN | A1 l.337 recipe has "column mapping", "expected columns", "validation thresholds"; `pipeline.run` takes `selector`, `min_rows` only; `validate.REQUIRED` fixes six column names (validate.py:8); `source_label` also free | Recipe schema = `schema_version`, `source`, `tier`, `url`, `selector`, `dataset{symbol,timeframe}`, `min_rows`, optional `politeness`; delete column mapping/expected columns/thresholds (or state unsupported, header must be the six names); no `source_label` key (default = pass source) |
| C5 | CONCERN | `rate_policy` is free text (approvals.py:56, `--rate` required string): "never above the approval's rate policy" cannot be computed | Bound against `Politeness` defaults (politeness.py:15): `min_delay >= 1.0`, `max_concurrent <= 2`, `max_per_host <= 1`, finite numbers, bool rejected; no `proxy`/`timeout`/`max_redirects` keys; dry-run prints the approval's rate text for the owner |
| C6 | CONCERN | A1 "allowed URLs/pages" in the recipe reads as authority; `pipeline.run` handles one URL and `write_series` replaces the whole key | Single `url`; no hosts/pages keys (unknown-key rejection covers it); only `pass_.permits(url)` decides; dry-run prints "would be refused" if `permits` is false; test: recipe URL outside the record -> refused, 0 fetcher calls; userinfo/port/backslash URLs refused |
| C7 | CONCERN | wrapper.py:99-106, 168-173, 190-194: live commands need `confirm_source`/`findings` that cannot go through `args`; `ReaResult.evidence_path` and `argv` are absolute paths; missing npx shows as `detail="FileNotFoundError"` (wrapper.py:140) | `rea <command> [--confirm-source N] [--findings F] [-- wrapper args]`; `ArgumentParser(allow_abbrev=False)`; tokens passed as a list, never joined or shlex-split; print only `%LOCALAPPDATA%\my_site\evidence\<day>\<file>` (relative to `paths.evidence_dir()`), never argv or output body; map `FileNotFoundError` to the Node message; exit 2 for `Refusal`, 1 for `invalid`; tests with fake runner assert `setup`, `mcp`, `--update` refused and runner never called |
| C8 | CONCERN | `Fetcher` protocol (types.py:21) vs function `fetch`; `ResponseCache.get` returns status `cache_hit` which `pipeline.run` returns as non-OK (pipeline.py:49-50), so a rerun after `uncertain`/`invalid` stops before parsing; tier-2/3 signatures undefined | Small adapter class per tier (`fetch(url, pass_)`) built lazily; map a cached outcome to `ok` with the same body for the pipeline; `--refresh` bypasses the cache; registry factory injectable in `main()`; tier 2-3 adapters follow the merged T59 signatures (envelope names them; mismatch -> `needs_input`) |
| C9 | CONCERN (order) | fetch_tier2/3 absent; MASTER-PLAN l.27 still dispatches T59+T60 together, P9 row has no T62 | State "W4 T59 merged before W5 T62; if `fetch_tier2.py` absent on origin/main the worker stops at needs_input"; planner updates P9 row and moves the T60 envelope to W6 |
| C10 | CONCERN (hidden break) | `test_marker_audit.py:13-15`; cli.py imports at top level would load scrapling/duckdb for `approvals status` | `cli.py` imports fetch tiers, pipeline, wrapper lazily inside handlers; `test_cli.py`/`test_recipe.py` import no `fetch_tier*` or network module (fake registry, call counters); autouse env fixture for `DIT_*`, `HOME`, `LOCALAPPDATA`; add one non-TTY subprocess test `approvals add` (stdin=DEVNULL -> exit 2, no file) |
| C11 | CONCERN | `recipes/` has no owner (A1 Owned list, S-T6 Owned l.177); guard on a missing folder | Add `tools/data-integration/recipes/example.recipe.json` (synthetic, host `*.example.test`, source `example-src`) to Owned; guard skips a missing folder; `test_cli_guard.py` also scans `deploy/` and `.github/workflows` for `data_integration`/`tools/data-integration`, and `recipe.py`/`cli.py` AST ban on `eval`, `exec`, `compile`, `pickle`, `marshal`, `yaml`, `shelve`, `subprocess`, `os.system`; T61 envelope names its recipe path |

Advisories (carry as envelope text): exit codes 0 (`ok`, `cache_hit`), 1 (other pipeline statuses), 2 (usage, recipe invalid, refused); top-level `except Exception` prints the type name only; one `_safe()` filter on every printed line replaces absolute paths and IPv4 with placeholders; each of the six `Refused` reasons maps to a plain sentence (test per reason, including `store_missing`, `store_corrupt`, `bad_clock`); recipe loader: size cap checked before read, regular file only, duplicate keys and `NaN` rejected, bool not accepted as int, error text shows the file name only; the read-set hint must use the named ranges above; the 93.30/130 USD line needs a MASTER-PLAN record.

## Security summary

Gate bypass: none found (CLI has no second pass constructor; `FetchPass` still needs the private token). Residual: approval records are plain files (documented E6). npx start: only through `run_rea` after exact allow-list membership; CLI must not pre-process tokens (C7). Path traversal: open until C1. Live-data overwrite: open until C2.

Not verified by this pass: real tier-2/3 behaviour (T59 not merged), Windows, any live npx call, any network call (none made).
