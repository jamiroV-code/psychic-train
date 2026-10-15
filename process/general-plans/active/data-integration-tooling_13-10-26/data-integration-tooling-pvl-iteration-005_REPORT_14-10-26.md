---
domain: plan
iteration: 5
date: 2026-10-14
plan: data-integration-tooling_PLAN_14-10-26.md
mode: VALIDATE (PVL cycle 5 = final re-validation after fix cycle 2 of max 2, scope = rewritten Amendment A1 / S-T7)
gaps_found: 7
fail_count: 0
concern_count: 7
applied: 0
loop_status: validated_conditional
---

# PVL iteration 005 - Amendment A1 (S-T7, T62), final cycle

Code under test: origin/main `c2b9052` (waves 1-3; T63 and T59 not merged). A1 = plan lines 327-343 (5,668 B). `validate-plan-artifact.mjs`: 0 failures, 1 advisory. `grep -c "Gate: PASS"` = 1 before, 1 after (plan not written). Python 3.12.3 and 3.13.14 argparse and `re` tested directly (scratch script only).

## Verdict: CONDITIONAL (0 FAIL, 7 CONCERN). No addendum (PASS only). Fix cycles exhausted (2 of 2): carry G1-G7 as binding envelope additions (text below), not as further plan edits. G1 is the only one that changes behaviour; G2-G7 are wording, test lists and read ranges.

## 1. C3, C7, F1-F9

| ID | Status | Evidence (A1 line; code on origin/main) |
|---|---|---|
| C3 | RESOLVED (test list: G3) | l.337: baseline = `adaptive.assess(b"<html></html>", sel, url=url).has_baseline`, flag refused with exit 2 when true. adaptive.py:31-34, 36-37 return `has_baseline=False` for no store / no selector baseline; l.42 UNCERTAIN keeps default True, so pipeline.py:62 overwrite is now prevented. `assess` never writes; `adaptive` only imports `scrapling.parser` (allowed by the import-boundary guard) |
| C7 | RESOLVED (rea exit codes: G1c) | l.335: manual split at `--`, `allow_abbrev=False` on every `add_parser`, `approvals` dispatched by hand, `detail='FileNotFoundError'` mapped. Verified: wrapper.py:166 sets `detail=type(exc).__name__`; py3.12.3 and 3.13.14 reject `--rep`, `--acc`, `--dry`, `--confirm-s` with `allow_abbrev=False` per subparser and accept `-- --source x` after a manual split |
| F1 | RESOLVED | l.336: `re.fullmatch`, uppercase only, device-name denylist, before path or SQL. Verified: fullmatch rejects `BTC\n`, `btc`, `..\x`, 33 chars; accepts `BTC-HIST`, 32 chars; `CON`, `COM1` pass the regex and are caught by the denylist (extensions clause is moot, regex has no `.`). approvals `valid_source` already uses fullmatch (approvals.py:35-36) |
| F2 | RESOLVED | same as C3 (flag refused if baseline exists; "for that host and selector" wording absent, harmless) |
| F3 | RESOLVED | see C7 |
| F4 | RESOLVED | l.337: preview = fetch without `ResponseCache` (fetch_tier1.py:95, 123-124 only touch cache when passed), then `parse_table` + `validate_table` directly (pipeline.py not called), no `remember`; `--dry-run`/`--preview` exclusive. Verified: argparse exclusive group exits 2 for `--dry-run --preview`; `--preview --replace` parses, so the manual check the plan states is needed. Logger writes no file (logging_setup.py), robots/politeness write nothing |
| F5 | PARTIAL (G1) | table l.338 covers the 6 Refused reasons (gate.py:18) and 4 of the status families, but see G1 |
| F6 | RESOLVED (G2 wording) | T63 fields now consistent with A1 (`approval_id` = stored id, T63 REF l.14); STOP rule present for tier 2/3 |
| F7 | RESOLVED (nits in G7) | l.336 bounds for url, selector, min_rows, politeness, schema_version present |
| F8 | PARTIAL (G5) | l.330 wave order fixed (W6 T60, W7 T61 after T60); recipe owner and table supersession open |
| F9 | RESOLVED | section 3: 33,0-33,9 KB with the cuts below |

## 2. Findings (all CONCERN; exact fixes = binding envelope additions)

| ID | Sev | Evidence | Exact fix |
|---|---|---|---|
| G1 | CONCERN | (a) `refused` has three origins: pipeline.py:46 off-list URL, fetch_tier1.py:92/94/117 (no pass, URL, off-list redirect), pipeline.py:72 `TargetNotEmpty`. A1 maps only "cache protection" to 7, so the commonest user error (recipe URL not on an approved page) has no code. (b) l.337 dry-run "prints whether `permits` refuses" and l.338 says dry-run exits 0: a dry run that would be refused exits 0. (c) `rea` has no exit codes: `Refusal` (wrapper.py:33, 6 reasons), `ReaResult` INVALID (wrapper.py:166-174: FileNotFoundError, TimeoutExpired, `exit N`, not JSON, shape), OK. (d) 11 statuses are mapped only by family words; `challenge_page`, `http_error`, `invalid`, `refused` are not named | Write the table as an explicit list: ok, cache_hit = 0; refused = 7 (existing data or off-list redirect; message from detail); robots_blocked, timeout, connection_failed, http_error, challenge_page = 4; invalid = 5; changed, uncertain = 6. `run` checks `pass_.permits(url)` right after `request_access`: refusal = exit 3, reason `url_not_approved`, also in `--dry-run` (exit 3, not 0). `rea`: `Refusal` = 2, `ReaResult` INVALID = 5 with plain message by detail (FileNotFoundError = Node/npx message, TimeoutExpired = timeout message, else "REA failed"), OK = 0. Tests: parametrized over `status.ALL_STATUSES` (code + non-empty plain message, one code each), over the 6 Refused reasons plus `url_not_approved`, and one per `rea` branch |
| G2 | CONCERN (low) | l.337 "(same id as `approvals status`)" is false: approval_cli.py:31-41 prints source name, tier, expiry, days_left, no id and no revision; the file cannot be edited. Rate text is not on FetchPass (T63 adds id, revision, approved, expires only) | Replace with: "id = `pass_.approval_id`, revision = `pass_.approval_revision`, expiry = `pass_.expires` (equals the status column); rate text = `ApprovalStore.read(source).rate_policy`; `body_sha256` from `outcome.body_sha256`". Test asserts the expiry string equals the status line |
| G3 | CONCERN (low) | No named tests for the baseline and `--replace` gates (they are C3/C2 proofs) | Add: baseline tests (no store, store + same selector, store + other selector -> flag allowed only in the first and third), `--accept-baseline` with baseline = exit 2 and no write, `--replace` with empty provenance = exit 2 before any fetch (registry call count 0), `--replace` with records allowed |
| G4 | CONCERN (low) | l.340 baseline "tooling 253, guards 41" is stale once T63 and T59 merge | "Record counts on origin/main after T59 (expect >= 253 and >= 41); any failure stops at needs_input" |
| G5 | CONCERN (low) | Table wave column (S-T5b 4, S-T6 5) and l.36/311 spend lines ("23.3-40.5", "86.13 of 100") are not declared superseded; A1 says "Earlier lines unchanged". No owner for `recipes/btc-hist.recipe.json` (S-T6 owns only the btc-history REF folder). T63 cost (cap 15, ask 7) is not in 24.8-43.5. MASTER-PLAN l.27/P9 stale (planner action) | Add: "This wave list and the 93.30/130 USD line supersede the table wave column and l.311; T63 adds 1.5-3.5 USD (total 26.3-47.0)". T61 envelope owns `recipes/btc-hist.recipe.json` (owner writes real host/url at AC-20). Planner updates MASTER-PLAN before dispatching T59 |
| G6 | CONCERN (low) | Read list omits what the code uses: `parse.py` ParseError + `parse_table` (9-10, 17), `validate.py` 24, `approvals.py` 35-36, 103-105, 118 and `ApprovalRecord` fields (52-64), ~900 B. T63 grows gate.py 16-40 and types.py by about 600 B | Add those ranges; the worker reads A1 lines 332-342 only (drop the hint line 343, 605 B, the envelope carries it) |
| G7 | CONCERN (nit) | Recipe: `schema_version` value not stated; `min_delay` has no upper bound (1e9 hangs a run); `max_concurrent` no lower bound (Politeness clamps to 1, harmless); preview prints no baseline line; `--refresh` with preview/dry-run unspecified; `approvals` subcommands keep argparse abbreviations (approval_cli.py:72, file not editable) | `schema_version == 1`; `min_delay` finite 1.0..3600; `max_concurrent` 1..2 ints; preview prints "baseline: present/none"; `--refresh` is a no-op in preview/dry-run; abbreviation on `approvals` is accepted as a known residual |

No contradiction with DIT-1..9, L1-L7, the SPEC or the T63 task: gate unchanged, `request_access` is the only pass source, no second network import site (`adaptive` imports `scrapling.parser` only), key `BTC-HIST` accepted, traversal and device names rejected, no scheduler/API/deploy reference, no new dependency, existing test files untouched (Common rule 4).

## 3. Read bytes (measured on origin/main `c2b9052`)

CLAUDE.md 13,443 + envelope 4,000 + Common (lines 40-75) 6,060 + A1 lines 332-343 5,070 (332-342 = 4,465) + named ranges 3,826 (approval_cli 72, wrapper 33-46 272 + 99-107 230, pipeline 19-24 102 + 30-44 317, gate 16-36 820 + 67-72 276, politeness 225, fetch_tier1 81-83 295, provenance 42-46 208, adaptive 31-32 162, paths 37-38 76, status 1-22 620, types 8-14 151) + tier 2/3 signatures 600 (estimate, T59 unmerged) = **32,999 B as written**.
Realistic: + T63 growth 600 + G6 ranges 900 = **34,499 B** (margin 501 under 35,000; 1,501 under 36,000). With the hint line dropped (-605) and A1 read as 332-342: **33,894 B (margin 1,106)**. If still over: drop `status.py` (620, the envelope lists the 11 names), then `paths.py`/`types.py`. T63's `gate.py` growth is the main uncertainty (recount after merge).

## 4. Cost

Estimate 24.8-43.5 = 23.3-40.5 + 1.5-3.0, arithmetic correct. S-T7 is 3 small modules + 2 test files with parametrized status/reason tests + 1 guard: closest to T57 1.82 and T54 1.61; the 1.5-3.0 band is plausible (actuals run 20-40 pct of estimates: T55 0.88, T58 1.18). Spend 93.30 of 130 leaves 36.70 against about 18-25 USD of remaining high estimates. Programme estimate lines are inconsistent (G5): table 23.3-40.5, l.311 "86.13 of 100", A1 "93.30 of 130"; T63 not costed.

## 5. Not verified

Tier 2/3 shapes, T63 code (unmerged), Windows, any live npx or network call (none made). The `adaptive.assess` no-write behaviour relies on iteration 4's probe plus reading adaptive.py:31-42. Nothing in the repo was changed except this report and results.tsv.
