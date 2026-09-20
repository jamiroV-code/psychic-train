---
name: plan:liqtide-snapshot-tooling
description: "LiqTide adapter dry-run support, daily snapshot/verify script, gitignore carve-out for liqtide cache, and full-vs-reduced composite agreement diagnostic"
date: 20-09-26
feature: general-plans
---

# LiqTide Snapshot Tooling — Plan

Date: 20-09-26
Status: Ready for VALIDATE review / EXECUTE pending approval
Complexity: SIMPLE (4 small, mostly-independent additive changes; no schema/auth/API surface;
one shared file touched additively). CI/scheduling (`.github/workflows/liqtide-snapshot.yml`) is
explicitly OUT OF SCOPE — that requires separate user sign-off for push-permission automation.

## Acceptance Criteria

- `LiqTidePayload`/`fetch_latest` changes are additive and do not break any existing caller
  (confirmed by grep + full pytest pass).
- `snapshot_liqtide.py` supports normal run, `--coverage`, and `--verify-only`, with exit codes
  0 (clean)/1 (fetch failed)/2 (archived-but-flagged), and never writes to cache under
  `--verify-only`.
- `.gitignore` durably tracks `api/data/cache/liqtide/` while continuing to ignore every other
  `api/data/cache/*` subdir.
- `compare_composite_variants.py` runs end-to-end over the `>= CUTOVER_DATE` window and prints a
  single clear AGREE/PARTIAL/DISAGREE verdict plus a JSON report, without needing a pass/fail
  exit code (diagnostic script).
- Full `api/` pytest suite remains green after all changes.

## Phase Completion Rules

Single-phase SIMPLE plan (not a phase program) — no per-phase gating beyond the Implementation
Checklist below. A checklist item is DONE when its file diff exists AND its corresponding
Verification Evidence gate has been run and passed (or, for `--verify-only`/live-network gates,
run at least once with a captured result in the phase report). The plan as a whole is DONE when
all 4 checklist sections are complete and the full pytest suite gate is green.

## Context

`api/data/liqtide_adapter.py`'s `fetch_latest()` already writes every successful live fetch to
`cache.write_liqtide_payload(date, row_df)` (no-ops if that date is already archived) — there is
no dry-run today, and `_parse_payload` discards `tide_index.components/weights/value/label`,
`data_quality`, and `regime` after computing `tide_score`. `cache.read_liqtide_history()` returns
one flat row per day: `date, generated_utc, tide_score, net_liquidity, dollar, stables, btc_dom`.
`liquidity_composite.build_full_composite()` is valid only `>= CUTOVER_DATE` (2024-01-11);
`build_reduced_composite()` is the only variant with historical depth (used for the 2017/2020-21
backtests). No test exists that checks whether the two composites agree over the one window where
both are computable. `.gitignore` currently has a blanket `api/data/cache/` line that also hides
`cache/liqtide/` — the one subdir this plan exists to make durable (LiqTide has no historical
endpoint; every other cache subdir regenerates from source APIs on demand).

## Touchpoints

- `api/data/liqtide_adapter.py` — additive dataclass field + additive kwarg
- `api/scripts/snapshot_liqtide.py` — new file
- `api/scripts/compare_composite_variants.py` — new file
- `.gitignore` — one line replaced with two

## Public Contracts

- `LiqTidePayload` gains `raw: dict | None = None` (defaulted — no existing constructor call
  site breaks; `_empty_payload`/`_row_to_payload` leave it `None` by design, since cache-replay
  payloads have no fresh raw to verify against).
- `fetch_latest(client=None, dry_run=False)` gains `dry_run` (defaulted `False` — no existing
  caller's behavior changes). No changes to `cache.py`, `liquidity_composite.py`, or
  `leg_boundary.py` public surfaces.

## Blast Radius

4 files (1 shared/edited, 3 new-or-config). Risk class: none of auth/billing/schema/public-API —
this is internal tooling + one diagnostic script reading existing analytics functions. Shared file
(`liqtide_adapter.py`) touched additively only; existing callers are `api/routers/regime.py` (not
directly — via `liquidity_composite`) and `api/scripts/refresh_cache.py`. Grep-verified: no other
caller of `fetch_latest` or `LiqTidePayload` positional-constructs the dataclass (all use kwargs
or read fields), so the added field/kwarg cannot break call sites.

## Implementation Checklist

### 1. `api/data/liqtide_adapter.py` (additive)

- [x] Add `raw: dict | None = None` field to `LiqTidePayload` (after `status`, since dataclass
      fields with defaults must trail non-default fields).
- [x] In `_parse_payload`, set `raw=raw` on the constructed `LiqTidePayload`.
- [x] `_empty_payload` and `_row_to_payload`: leave `raw` at its default `None` — do not pass a
      value (cache-replay/unavailable payloads have no fresh raw to verify against; this is
      intentional, not an oversight — document with a one-line comment at `_row_to_payload`).
- [x] Add `dry_run: bool = False` parameter to `fetch_latest(client=None, dry_run=False)`.
- [x] In `fetch_latest`, after `payload = _parse_payload(raw)` succeeds with a non-empty
      `payload.date`: only call `cache.write_liqtide_payload(...)` when `dry_run` is `False`.
      When `dry_run` is `True`, skip the write but still `return payload` (fully populated,
      including `raw`).
- [x] Grep for all call sites of `fetch_latest(` and `LiqTidePayload(` across `api/` to confirm no
      positional-arg breakage (expected: `api/routers/regime.py` or wherever liquidity_composite
      wires it, plus the new snapshot script). Record the grep result in the phase report.

### 2. `api/scripts/snapshot_liqtide.py` (new)

- [x] Copy `api/scripts/refresh_cache.py`'s repo-root `sys.path` bootstrap block verbatim (adapt
      `parents[N]` if the new script's directory depth differs — it does not, same `api/scripts/`
      dir, so `parents[2]` is correct).
- [x] Module docstring: explain why a schedule matters (LiqTide has no historical endpoint — an
      uncaptured day is gone forever) and give run commands:
      `uv run --project api python api/scripts/snapshot_liqtide.py`
      `uv run --project api python api/scripts/snapshot_liqtide.py --coverage`
      `uv run --project api python api/scripts/snapshot_liqtide.py --verify-only`
- [x] `WEIGHTS` dict exactly as specified (user hand-verified against the live payload
      2026-09-20 — do not re-derive):
  ```python
  WEIGHTS = {
      "net_liquidity_4w": 0.30, "stablecoin_7d": 0.25, "dollar_1m": 0.15,
      "rrp_release_4w": 0.10, "etf_flow_5d": 0.10, "rotation_30d": 0.10,
  }
  ```
- [x] `check_arithmetic(raw: dict) -> list[str]`: read `raw["tide_index"]["components"]`,
      `["weights"]`, `["value"]`. Missing `WEIGHTS` key in `components` → flag. Else recompute
      `score = sum(weights.get(k, WEIGHTS[k]) * components[k] for k in WEIGHTS)`,
      `recomputed = clamp(round(50 + 50*score), 0, 100)`; flag if
      `abs(recomputed - published_value) > 1`. Flag if published weights don't sum to ~1.0
      (tolerance 0.001). Flag if `raw.get("data_quality") != "live"`. Only called when
      `payload.raw is not None`.
- [x] `check_coverage(history: pd.DataFrame) -> list[str]`: for `"tide_score"` and each of
      `liqtide_adapter.METRIC_KEYS`, compute/print `column.notna().sum()` vs `len(history)`.
      Gap detection: sorted-unique `pd.to_datetime(history["date"], utc=True).dt.date`, flag
      consecutive gaps > 1 day (report count + worst gap length).
- [x] `main()`:
      - `--coverage` → call `check_coverage(cache.read_liqtide_history())`, print, `return 0`
        unconditionally (even with problems — this is an inspection mode, not a gate).
      - else: `payload = liqtide_adapter.fetch_latest(dry_run=args.verify_only)`.
        `status == "unavailable"` → print to stderr, `return 1`.
        Run `check_arithmetic(payload.raw)` when `payload.raw is not None`; if
        `args.verify_only` and `payload.raw is None`, that itself is a WARN ("no fresh payload —
        nothing to verify", since `--verify-only` maps to `dry_run=True` and only a fresh live
        parse populates `raw`).
        Print a status line: `tide_score`, `generated_utc`, `status`; when `raw` is present also
        print `tide_index`'s `value`/`label`/`regime` (not on `LiqTidePayload` itself — read
        from `payload.raw`).
        `status == "stale"` → add to problems.
        All problems print as `WARN:` to stderr.
        Exit codes: `0` clean archive, `1` fetch/write failed (`unavailable`), `2`
        archived-but-flagged (any WARN present).
- [x] Do NOT call `cache.write_liqtide_payload` directly — `fetch_latest` already owns that;
      `--verify-only` is implemented purely via `dry_run=True`.

### 3. `.gitignore` carve-out

- [x] Replace the current `api/data/cache/` line with:
  ```
  api/data/cache/*
  !api/data/cache/liqtide/
  ```
  (the `*` is required — git cannot selectively un-ignore a path inside a directory that was
  itself matched by a bare directory-name pattern; the parent must be excluded per-entry, not
  as a whole, for the negation to take effect — this is git's own documented pathspec
  behavior, not a judgment call).
- [x] Verify: create a throwaway file under `api/data/cache/liqtide/`, confirm
  `git status --short` shows it as untracked/trackable; confirm a file under
  `api/data/cache/ohlcv/` still shows as ignored. Delete the throwaway file after verifying
  (do not commit it as part of this change).

### 4. `api/scripts/compare_composite_variants.py` (new)

- [x] Follow `api/scripts/backtest_leg_boundaries.py` conventions exactly: same sys.path
      bootstrap block, same `REPORT_DIR` pattern (but pointed at THIS plan's own task folder —
      `process/general-plans/active/liqtide-snapshot-tooling_20-09-26/`, not the
      momentum-screener folder), same atomic temp-file + `Path.replace()` write, same argparse
      style (read `backtest_leg_boundaries.py` first, already done this session).
- [x] `AGREEMENT_TOLERANCE_DAYS = leg_boundary.CONFIRMATION_WINDOW_DAYS` (currently 10) — reuse
      the codebase's existing "how close in time counts as the same event" constant (already
      used internally by `confirm_boundaries`) rather than inventing a new tolerance. **This is
      a documented judgment call, not a hidden one** — comment explaining the reuse, verbatim
      reasoning: "reuses the same confirmation window `confirm_boundaries` itself already uses
      to decide whether a price-structure pivot counts as confirming a candidate — applying a
      tighter or looser number here would imply the two composites need a different definition
      of 'same event' than the codebase already uses for boundary confirmation, which has no
      basis."
- [x] Compute:
  ```python
  window = (liquidity_composite.CUTOVER_DATE, pd.Timestamp.now(tz="utc"))
  full = liquidity_composite.build_full_composite(date_range=window)
  reduced = liquidity_composite.build_reduced_composite(date_range=window)
  btc_result = ccxt_adapter.fetch_ohlcv("BTC", "1d")
  btc_df = btc_result.df
  ```
  Filter `btc_df` to `window` using its timestamp column (confirm exact column name from
  `OhlcvResult`/`cache.read_ohlcv` shape before writing — matches `backtest_leg_boundaries.py`'s
  own `timestamp` column usage).
- [x] For each of `full`/`reduced`: skip detection when `.available` is `False` (matching
      `backtest_leg_boundaries.py`'s pattern); else run
      `leg_boundary.detect_candidate_boundaries(composite.series)` then
      `leg_boundary.confirm_boundaries(candidates, btc_df)`.
- [x] Agreement/verdict logic (already decided, do not invent a different scheme):
      - Bijective match check: for each full-confirmed boundary, check whether some
        reduced-confirmed boundary's `confirmed_date` (or `candidate_date` if unconfirmed
        fallback is not applicable — use confirmed boundaries only, matching the "confirmed"
        semantics the codebase already uses) falls within `AGREEMENT_TOLERANCE_DAYS`; and
        vice versa.
      - `"AGREE"` — every boundary on each side has a match on the other (full bijection).
      - `"PARTIAL"` — at least one match exists but not full bijection.
      - `"DISAGREE"` — zero matches, including the case where one side has confirmed boundaries
        and the other has none.
- [x] Report matched pairs, full-only unmatched, reduced-only unmatched, and the verdict string.
      Print the verdict as one clear human-readable line to stdout (this script's whole purpose
      is answering one question legibly), and write a JSON report to
      `REPORT_DIR / f"composite-variant-agreement-{timestamp}.json"` using the same atomic
      write pattern as `backtest_leg_boundaries.py.write_report`.
- [x] `main()`: no required args. `raise SystemExit(0)` after printing (diagnostic script, not a
      pass/fail gate — mirrors `backtest_leg_boundaries.py`'s framing where the Hybrid gate is
      manual review, not a script exit code).

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| `cd api && uv run pytest tests/ -x -q` (full suite) | Fully-Automated | No regression from the additive `liqtide_adapter.py` change across the whole `api/` test surface, not just liquidity tests |
| Grep: no positional `LiqTidePayload(...)` construction or `fetch_latest(` positional 2nd-arg call site outside this plan's new files | Fully-Automated (manual grep, recorded in report) | `raw`/`dry_run` additions are genuinely additive |
| `uv run --project api python api/scripts/snapshot_liqtide.py --coverage` runs and exits 0 | Hybrid (needs local `cache/liqtide/` data to be meaningful, but the code path itself is exercisable even empty) | `check_coverage` doesn't crash on a normal or empty history frame |
| `uv run --project api python api/scripts/snapshot_liqtide.py --verify-only` runs against the live endpoint | Hybrid (network required) | End-to-end dry-run path: no cache write occurs, `check_arithmetic` runs against real `raw`, exit code reflects WARN state correctly |
| Manual `git status --short` check after touching `api/data/cache/liqtide/<file>` and `api/data/cache/ohlcv/<file>` | Agent-Probe | `.gitignore` negation pattern behaves per git's own semantics (liqtide un-ignored, other subdirs still ignored) |
| `uv run --project api python api/scripts/compare_composite_variants.py` runs to completion and prints a verdict line | Hybrid (network required — ccxt fetch) | The full-vs-reduced composite agreement question is answerable end-to-end; verdict logic and report-write path both execute without crashing |

## Test Infra Improvement Notes

(none identified yet)

## Resume and Execution Handoff

1. Selected plan file path: `process/general-plans/active/liqtide-snapshot-tooling_20-09-26/liqtide-snapshot-tooling_PLAN_20-09-26.md`
2. Last completed phase/step: PLAN written, VALIDATE run inline below (FAST MODE)
3. Validate-contract status: written below (this session)
4. Supporting context files loaded: `process/context/all-context.md`, `process/context/data-sources/all-data-sources.md` (§Macro Liquidity), `api/data/liqtide_adapter.py`, `api/data/cache.py`, `api/analytics/regime/liquidity_composite.py`, `api/analytics/regime/leg_boundary.py`, `api/scripts/backtest_leg_boundaries.py`, `api/data/ccxt_adapter.py`
5. Next step for a fresh agent: read this plan's Implementation Checklist top to bottom; item 1
   (`liqtide_adapter.py`) must land before items 2 and 4 since both new scripts import from it;
   item 3 (`.gitignore`) is fully independent and can be done in any order. Run the full pytest
   suite gate after item 1 before moving to items 2/4.

## Validate Contract

**generated-by:** outer-pvl
**date:** 2026-09-20

### V1 Pre-check
Plan file exists at the path above. Blast Radius section present (4 files, no high-risk class).
No `## Inner Loop Refresh Note` present (first pass). Proceeding to V2/V3.

### Layer 1 — Four Dimensions

| Dimension | Status | Notes |
|---|---|---|
| Infra/setup fit | PASS | No container/port/runtime surface touched. Script bootstrap pattern copied from an existing, working script (`refresh_cache.py`/`backtest_leg_boundaries.py`). |
| Test coverage | PASS | Verification Evidence table above assigns tiers per gate; full pytest suite is the regression gate for the shared adapter file; new scripts get Hybrid (network-dependent) + Agent-Probe (gitignore) tiers, appropriate since they're diagnostic tooling, not app logic with unit-testable pure functions in isolation — `check_arithmetic`/`check_coverage`/verdict logic ARE pure functions and could get unit tests, flagged as a CONCERN below. |
| Breaking changes | PASS | Both `liqtide_adapter.py` changes are strictly additive/defaulted; grep-verified no positional call sites exist. No public API/schema/auth surface touched. |
| Security surface | PASS | No new secrets, no new network destinations beyond the existing LiqTide endpoint (already fetched by the adapter) and the existing ccxt exchange call (already used elsewhere). No auth/billing/trust-boundary logic. |

### Layer 2 — Per-Section Feasibility

| Section | Status | Mechanical feasibility | Gaps found | Conflicts found | Highest-risk edit + mitigation |
|---|---|---|---|---|---|
| 1. liqtide_adapter.py | PASS | Edit targets (`LiqTidePayload` dataclass, `_parse_payload`, `_empty_payload`, `_row_to_payload`, `fetch_latest`) all confirmed present and uniquely matchable via direct file read this session. | None. | None. | Field-order mistake in the dataclass (defaulted field before non-defaulted) would raise at import time — mitigation: `raw` must be the LAST field added, after `status`. |
| 2. snapshot_liqtide.py | CONCERN | New file, straightforward to write; bootstrap pattern has a working precedent to copy exactly. | `check_arithmetic`/`check_coverage` are pure functions with no dedicated unit test planned — only exercised via the Hybrid/network-dependent CLI run in Verification Evidence. Recommend execute-agent add a small pytest file for these two pure functions using synthetic fixtures (no network needed) if time permits; not blocking. | None. | `clamp`/rounding logic in `check_arithmetic` — mitigation: use a plain `max(0, min(100, ...))` clamp, no external dependency. |
| 3. .gitignore | PASS | Two-line replacement, mechanically simple; git's per-path negation-requires-parent-not-fully-ignored rule is well-established and the plan states the exact required syntax. | None. | None. | Getting the negation order wrong (negation line before the broader ignore) is a git ordering trap — mitigation: negation line MUST come after the `api/data/cache/*` line in `.gitignore`, and the checklist's manual verification step catches this if missed. |
| 4. compare_composite_variants.py | CONCERN | New file with a clear structural precedent (`backtest_leg_boundaries.py`) to copy; core logic (bijective match) is well-specified in the plan. | The exact `OhlcvResult`/`btc_df` timestamp column name is asserted as `timestamp` by analogy with `backtest_leg_boundaries.py`'s CryptoDataDownload-CSV-derived frame, but `ccxt_adapter.fetch_ohlcv`'s cache-backed `OhlcvResult.df` was not independently read this session to confirm its column name matches. Execute-agent must confirm the actual column name from `cache.read_ohlcv`/`OhlcvResult` before writing the filter line — documented as an execute-agent instruction below, not silently assumed. | None. | Confirmed/candidate boundary date-matching logic (bijective, both directions) — mitigation: write it as a small pure helper function so it's testable in isolation before wiring into the full script; use `pandas.Timestamp` arithmetic consistently (avoid naive/aware tz mismatches — both composites' `.series` and `btc_df` are UTC-aware per existing codebase convention, confirm this holds). |

### Net Gate Derivation

**Layer 1:** 4 PASS, 0 CONCERN, 0 FAIL
**Layer 2:** 2 PASS, 2 CONCERN, 0 FAIL
**Totals: 0 FAILs / 2 CONCERNs / 6 PASSes**

**→ Net Gate: CONDITIONAL**

Both CONCERNs are execute-agent instructions, not plan-text fixes (they depend on file
inspection execute-agent will do naturally while writing the new scripts) — no FAILs, no
plan-text changes needed. Proceeding to EXECUTE with these two gaps on record is appropriate.

### Execute-Agent Instructions

| # | Instruction | Trigger condition |
|---|---|---|
| E1 | Before writing the `btc_df` timestamp filter line in `compare_composite_variants.py`, run `python -c "from api.data import ccxt_adapter; r = ccxt_adapter.fetch_ohlcv('BTC','1d'); print(r.df.columns.tolist())"` (or read `cache.read_ohlcv`'s write path) to confirm the actual timestamp column name before assuming `"timestamp"`. Update the filter line to match reality. | Writing item 4, before the window-filter step |
| E2 | Consider adding a small pytest file (e.g. `api/tests/scripts/test_snapshot_liqtide.py`) covering `check_arithmetic` and `check_coverage` with synthetic in-memory fixtures — not required to pass this plan's gate, but flagged as a quality improvement if time permits. | Writing item 2, optional |

### Test Gates (from Verification Evidence, carried verbatim)

- `cd api && uv run pytest tests/ -x -q`
- Grep verification of `LiqTidePayload(`/`fetch_latest(` call sites (manual, recorded in report)
- `uv run --project api python api/scripts/snapshot_liqtide.py --coverage`
- `uv run --project api python api/scripts/snapshot_liqtide.py --verify-only`
- Manual `git status --short` check for `.gitignore` negation behavior
- `uv run --project api python api/scripts/compare_composite_variants.py`

### Gate: CONDITIONAL
