---
domain: plan
iteration: 4
date: 2026-10-14
plan: data-integration-tooling_PLAN_14-10-26.md
mode: VALIDATE (PVL cycle 4 = re-validation after fix cycle 1 of max 2, scope = rewritten Amendment A1 / S-T7)
gaps_found: 9
fail_count: 0
concern_count: 9
applied: 0
loop_status: validated_conditional
---

# PVL iteration 004 - Amendment A1 rewritten (S-T7, T62)

Code under test: origin/main `c2b9052` (waves 1-3 merged; same tree as local HEAD `70939f9` for tools/ and api/). A1 = plan lines 327-348, 6,437 B. `validate-plan-artifact.mjs`: 0 failures, 1 advisory. `grep -c "Gate: PASS"` = 1 before, 1 after (plan not written). Python 3.12.3 argparse tested directly.

## Verdict: CONDITIONAL (0 FAIL, 9 CONCERN). No addendum (PASS only). One fix cycle remains (cycle 2 of 2). All fixes are text edits to A1 plus an envelope trim; none needs a design change.

## 1. C1-C11 status

| ID | Status | Evidence in rewritten A1 |
|---|---|---|
| C1 | RESOLVED (residual F1) | l.340 regex + timeframe set, "validated before any path or SQL is built" |
| C2 | RESOLVED | l.341 `--replace` only when `provenance.read_records` non-empty |
| C3 | PARTIAL (F2) | `--accept-baseline` present; how "no baseline" is computed before a fetch is not stated, and `pipeline.run` alone cannot enforce it |
| C4 | RESOLVED (F7 bounds) | l.340 closed schema, no column/threshold/source_label keys |
| C5 | RESOLVED | l.340 bounded vs `Politeness(1.0, 2, 1)` (politeness.py:12); dry-run prints rate text |
| C6 | RESOLVED | single `url`, only `permits` decides |
| C7 | PARTIAL (F3) | l.339 syntax right; two argparse facts wrong on 3.12 |
| C8 | RESOLVED (F6 note) | lazy per-tier adapters, injectable registry, `cache_hit` to `ok` |
| C9 | RESOLVED in A1 (F8) | l.330 + l.336 order and STOP rule; MASTER-PLAN still stale (planner action) |
| C10 | RESOLVED | l.342-343 lazy imports, no `fetch_tier*` in tests, env fixture, non-TTY subprocess test |
| C11 | RESOLVED | `recipes/example.recipe.json` owned, guard skips missing folder, AST ban, deploy/workflow scan |

## 2. New findings

| ID | Sev | Evidence | Exact fix (edit A1 text) |
|---|---|---|---|
| F1 | CONCERN | `re.match(r'^...$', "BTC\n")` is True, `fullmatch` False (run). `CON`, `NUL`, `PRN`, `AUX`, `COM1` match; owner is on Windows. `ohlcv_path` upper-cases (cache.py:118), so `btc` and `BTC` are one file. Test list has `../x`, `a/b`, `a'b` only | "validated with `re.fullmatch`"; reject Windows device names (case-insensitive CON PRN AUX NUL COM1-9 LPT1-9); tests add `..\x`, `"BTC\n"`, `btc` vs `BTC` same key, `BTC-HIST` accepted, 33 chars rejected |
| F2 | CONCERN | pipeline.py:62 `first_run = UNCERTAIN and accept_baseline`; adaptive.py:42 returns UNCERTAIN with `has_baseline=True` (selector matches nothing), so `--accept-baseline` would overwrite an existing baseline. Dry-run fetches nothing, yet must show "baseline exists". Verified probe: `adaptive.assess(b"<html></html>", selector, url=url).has_baseline` is public, creates no file when the store is missing, leaves store bytes and mtime unchanged when present; baseline key is host + selector, not source. Building a `Selector` directly would create the sqlite file, and `cli.py` may not import scrapling (import guard) | State: baseline check = that call, made before any fetch; `--accept-baseline` with an existing baseline exits 2 "a baseline already exists"; wording "for that host and selector"; tests: no store, store + selector, store + other selector, flag refused when present |
| F3 | CONCERN | Python 3.12.3: `allow_abbrev=False` on the top parser does NOT reach subparsers: `run r.json --rep`, `--acc`, `--dry` and `rea c --confirm-s a` were accepted. `rea c --confirm-source a -- --source x` fails "unrecognized arguments: --". Wrapper catches OSError and returns `ReaResult(INVALID, detail="FileNotFoundError")` (wrapper.py:165-166), it does not raise | `allow_abbrev=False` in the top parser and every `add_parser`; split argv at the first `--` by hand before argparse (tokens after it stay a list into `args`); dispatch `approvals` by hand: `argv[0]=="approvals"` then `approval_cli.main(argv[1:])`; Node message chosen when `result.detail == "FileNotFoundError"`; tests: abbreviations rejected (exit 2), `--` after flags works |
| F4 | CONCERN | "`--preview` writes nothing" is not achievable as worded: `fetch_tier1.fetch` calls `cache.put` on OK whenever a `ResponseCache` is passed (l.123-124) and `pipeline.run` writes series, provenance and baseline. `--dry-run`/`--preview` with `--replace`, `--accept-baseline`, `--refresh` is undefined | Preview: adapter built with no `ResponseCache`; does not call `pipeline.run` (parse_table, validate_table, normalise only); never calls `adaptive.remember`. `run` builds `ResponseCache()`. `--dry-run` and `--preview` are a mutually exclusive group; either with `--replace`/`--accept-baseline` exits 2; `--refresh` is a no-op in preview. Preview output states "baseline: present/none". Test: cache, scrape and evidence trees byte-identical before and after preview; preview counts one registry call |
| F5 | CONCERN | l.341 "Exit 0 for ok, 1 for other statuses, 2 for ... refusal" is ambiguous: pipeline `refused` (non-empty key, url) vs gate "refusal"; pipeline `invalid` vs "invalid recipe"; `cache_hit` "data unchanged" (pipeline.py:68, the safe re-run of US-5) now falls in "other" = 1, iteration 3 wanted 0; dry-run exit when `permits` would refuse unspecified. Messages: no test per Refused reason (6: missing, expired, tier_too_low, store_missing, store_corrupt, bad_clock) or per status (11) | Table: 0 = ok, cache_hit, successful dry-run/preview; 2 = usage, recipe invalid, any gate Refused, `--replace` or `--accept-baseline` refused, dry-run that "would be refused"; 1 = every other status incl. pipeline `refused`/`invalid`. Add parametrized tests over the six reasons and `status.ALL_STATUSES` (non-empty plain sentence, no raw identifier). A non-empty key without `--replace` is left to `pipeline.run` (so an unchanged re-run exits 0); `--replace` without provenance is refused before any fetch |
| F6 | CONCERN (low) | T58 supplement is named consistently (l.330, l.336 Depends), S-T7 does not re-implement it. But no S-T7 step uses its shapes. `approval_cli.py:61` writes `id='<source>-<YYYYMMDD>'`; the supplement's `approval_id` is `'<source>@r<revision>'` (record has `revision`, approvals.py) | Name the uses: dry-run prints `pass_.approval_id`, `approved_on`, `expires_on` (never `rec.id`), rate text via `ApprovalStore.read` (FetchPass does not carry it); preview prints `body_sha256`; `cache_hit`->`ok` via `dataclasses.replace(outcome, status="ok")` so the new field survives; STOP at `needs_input` if `FetchPass` on origin/main lacks `approval_id`. Cost line: supplement cost is not in 24.8-43.5 |
| F7 | CONCERN (low) | No bounds for `min_rows`, `selector`, `url`, `schema_version`, ints in `politeness`. A recipe can set `min_rows` 0 and weaken validation (validate default 2) | `min_rows` int 2..100000; `selector` <=500 chars, `url` <=2,000; `schema_version` == 1; `max_concurrent` 1..2, `max_per_host` == 1 (ints, bool rejected), `min_delay` finite >=1.0 |
| F8 | CONCERN | l.330 puts T60 and T61 in W6, but S-T6 `Depends: S-T5b` (plan l.177, table l.22-36), so T61 cannot start before T60 merges. Table wave column (S-T5b=4, S-T6=5) and MASTER-PLAN l.27 + P9 row (W4 = T59+T60, T61 W5, no T62) are stale. The real BTC-HIST recipe path has no owner | A1: "W6 = T60; T61 starts after T60 merges (S-T6 depends on S-T5b); this wave list supersedes the table"; T61 envelope names `recipes/btc-hist.recipe.json`; planner updates MASTER-PLAN before dispatch |
| F9 | CONCERN | Read total over the cap, see section 3 | Section 3 |

No contradiction with DIT-1..9, L1-L7 or the SPEC found: gate unchanged, `request_access` is the only pass source, tiers bounded by the record, no scheduler/API/deploy reference, no new network import site, no new dependency, key `BTC-HIST` accepted, traversal rejected. No recipe field widens the approval (`source` picks another approval, each gated; `tier` capped by the record; `url` by `permits`; politeness may only tighten; F7 closes the validation side).

## 3. Read bytes (measured, `wc -c` on `git show origin/main:` ranges)

Fixed: CLAUDE.md 13,443 + envelope 5,200 (assumed) + Common 6,060 = 24,703.
- A1 section lines 327-348 = **6,437 B** (plan says 6,367; S-T7 subsection 332-347 = 5,113; hint line 348 = 537).
- Named ranges as written: `approval_cli.py` main 71-93 = 983; `wrapper.py` 99-106 = 204; `wrapper.py` 168-194 = 1,296; `pipeline.py` 30-44 = 317; `gate.py` 67-72 = 276 -> **3,076 B** (not 1,701). `paths` 983 + `status` 620 + `types` 579 = 2,182. Tier 2/3 signatures about 600 (estimate).
- **Total as written = 13,443 + 5,200 + 6,060 + 6,437 + 3,076 + 2,182 + 600 = 36,998 B, 998 B OVER the 36,000 cap.** Even with the plan's own 1,701 B figure it is 35,640 B (360 B under).
- `wrapper.py` 168-194 is the wrong range: it is the error returns plus the start of `render_evidence_note`. The CLI needs `Refusal`/`ReaResult` 33-46 (272).
- Hint omits ranges A1 relies on: `gate.Refused` 16-23 (234), `politeness.py` 11-14 (225), `fetch_tier1.fetch` signature 81-83 (295), `provenance.read_records` 42-46 (208), `adaptive.assess` 31-32 (162).

Cut advice (target <= 34,800, margin >= 1,000): envelope <= 4,000 B (not 5,200); worker reads A1 lines 332-347 only (5,113; the "Why/Waves" lines and hint go to the envelope); replace `wrapper.py` 168-194 and `paths.py`/`types.py` whole files by: `approval_cli.py` 71; `wrapper.py` 33-46 and 99-107; `pipeline.py` 19-24 and 30-44; `gate.py` 16-23, 25-36 (585), 67-72; `politeness.py` 11-14; `fetch_tier1.py` 81-83; `provenance.py` 42-46; `adaptive.py` 31-32; `paths.py` 37-38 (76); `status.py` 1-22 (620); `types.py` 8-14 (151) = 3,825 B, plus T58 supplement growth 400 and tier 2/3 signatures 600. **Measured total = 13,443 + 4,000 + 6,060 + 5,113 + 3,825 + 400 + 600 = 33,441 B (margin 2,559).** With the whole A1 (6,437) it is 34,765 B (margin 1,235): still acceptable, but only with the 4,000 B envelope. The F1-F8 fixes add roughly 1,500 B to A1: then read lines 332-347 only and keep the envelope at 4,000 B, giving about 34,900 B; if over, drop `status.py` (620) first.

## 4. Waves and estimate

Order W3.5 T58 supplement -> W4 T59 -> W5 T62 -> W6 T60 (+ T61 only after T60, F8) is consistent between l.330 and l.336 and with the import-order need (`fetch_tier2/3` must exist). Estimate 24.8-43.5 USD = 23.3-40.5 + 1.5-3.0: arithmetic correct; excludes the T58 supplement worker. Per-slice actuals (T55 0.88, T58 1.18, T57 1.82) are far below the 2.5-7.0 estimates. The 93.30 USD is cumulative worker spend; headroom to the 130 ceiling is 36.70 against about 17-20 USD of remaining high estimates. Plan l.311 still says "86.13 of 100" (stale body text, harmless).

## 5. Not verified

Tier 2/3 shapes (T59 not merged), the T58 supplement (in progress), Windows, any live npx or network call (none made). Scratch tests used `~/.cache/dit-env` (Python 3.13.14) for the adaptive probe and `/usr/bin/python3.12` for argparse; nothing in the repo was changed.
