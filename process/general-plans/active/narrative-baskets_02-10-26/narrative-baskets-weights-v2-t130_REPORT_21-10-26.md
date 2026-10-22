---
name: report:narrative-baskets-weights-v2-t130
description: "T130 worker report: weights v2 for the Discovery weighted signal (search vote group, early-source gate, github_dev parked, per-day weights versions). Draft PR, not merged."
date: 21-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: report
---

# T130 weights v2: REPORT

## 1 Task ID

T130: weights v2 for the weighted attention signal. Branch `claude/t130-weights-v2`. Plan: `narrative-baskets-weights-v2-t130_PLAN_21-10-26.md` (FAST MODE, Gate: PASS).

## 2 Outcome

done (draft PR open, not merged)

## 3 Summary

- `discovery.json` has the owner-locked v2 weights (total 90), `source_groups.search = [trends, wikipedia]`, `early_sources = [trends, reddit, xsearch]`, `weights_version: 2`, and v1 kept in `weights_history` with `until: 2026-10-21`.
- Group rule (plan D2): the group is rising iff its rising members hold at least 50% of its available weight. A rising group adds that whole weight to `rising_weight`. Score and covered weight are unchanged.
- Early gate (D3): no trigger unless an early source's own raw change is >= `rising_threshold_pct`. Confirming-only coins never trigger.
- Weight 0 (D4): not read, not counted, and the Sources row is `off` with the note "parked: weight 0, not fetched". It is excluded from `total_sources`.
- Per-day versions (D5): `weights_for_day(cfg, day)` drives live scoring, snapshots and the history chart. Past days keep v1, so no chart day changes retroactively and no frozen file is recomputed.
- Additive `weights_version` on the Discovery response, history days, new snapshot records and snapshot rows read back (1 when absent). There is no web change.
- `min_covered_weight` 30 is kept. It equals one early source plus one confirming source at minimum (xsearch 15 + exchange 15). On real data, under v2 max covered is 25 (exchange + wikipedia only), so there are 0 triggers until trends, reddit or xsearch data exists (under v1 the max was 35 with 1 trigger).

## 4 Files changed

- `api/data/discovery.json`
- `api/analytics/attention/discovery.py`: validation, `weights_for_day`, `_rising_weight`, early gate, `series_names`
- `api/analytics/attention/discovery_history.py`, `signal_snapshots.py`, `sources.py`
- `api/models/discovery.py`: additive fields, comments
- Tests: new `api/tests/analytics/attention/test_weights_v2.py` (50 tests). Edited: `test_discovery.py` (3 tests that encoded the retired sum-to-100 rule), `api/tests/routers/test_discovery.py` and `test_discovery_history.py` (key sets plus `weights_version`).
- Docs: the plan, this report, and a one-line addendum in `narrative-baskets-weighted-signal_SPEC_18-10-26.md` decision 1. `all-context.md` has no weights line, so it is untouched.

## 5 Commits

`7d93875` (implementation, tests, plan, SPEC line) plus the report commit on `claude/t130-weights-v2`, base `main` 24b1d5e.

## 6 Tests run

- Red first, new file on main code: `UV_FROZEN=1 uv run --project api pytest api/tests/analytics/attention/test_weights_v2.py -q` gave 19 failed, 31 passed (the passing cases were mostly invalid configs that the old sum-to-100 rule also rejected).
- Baseline on main 24b1d5e: `UV_FROZEN=1 uv run --project api pytest api -q` gave 1811 passed, 1 skipped, 5 deselected.
- After, on 7d93875: same command gave 1861 passed, 1 skipped, 5 deselected, 0 failed (2026-10-21 ~20:40 UTC). Delta +50 = the new file.
- G7 frozen snapshots, `cd api/data/cache/attention/signals && sha256sum -c`, before and after the full run: 12 lines OK.
```
eb4730e44d5f7f17d86fc1e704a87c69b1a247d4fc1ab41aca0555f226bbcdde  2026-10-17_w30.json
597fb394fcfc3207c5f8adfc35e57827f39cf81e6cff031787678a2e76d6aef1  2026-10-17_w7.json
09946558044b0bfa7093dfeb5fe1ab586eca6b762fd89301b807eb01ec9909ac  2026-10-17_w90.json
fdbb7401920807edeb3e47cd1c0d5cca7fca4ed94128020eeca7251c3a355477  2026-10-18_w30.json
ee120bfd03204136e6c0fc0b897b39ed78ea399b1aa1e758eb779fba0047c886  2026-10-18_w7.json
ae58a70d41ead6c933715f47bced3a615f2a37b96362d9dbdac69e2da05a90fe  2026-10-18_w90.json
b63eee4ee5fc142ab0efdb2db7ad43291578291c10cad9b020c39cfdb75dd138  2026-10-19_w30.json
d6045cbd3d0ac20869ccf628bff2c42b9a3e2990f436f26e028cbfe20c4a0697  2026-10-19_w7.json
9d60169c843433b739dd993d41681edff52fc14acf3e7e6692b6ad4572d1842d  2026-10-19_w90.json
fe57a71878435f78eef4edd1ad00d6625991dd5e37130cab46b7cc1476ae3f9e  2026-10-20_w30.json
674c166245a53f66b118df75b1b11688e719ae2cdebbd1ff3307860a2dc21143  2026-10-20_w7.json
bb8badc85b2779217f60df2fc0031bb3833a96567005f9cb8e96e3122a9911e8  2026-10-20_w90.json
```
- G8: `git diff --check origin/main...HEAD` exit 0. The secret scan over the added lines printed nothing.
- G3: `git diff --stat origin/main...HEAD -- web .github` is empty.
- Smoke on real data (read-only): `build_discovery(30, today=2026-10-22)` gave v1, max covered 35, 1 trigger; `today=2026-10-23` gave v2, max covered 25, 0 triggers.

## 7 Tests NOT run

Web checks (vitest, tsc, e2e) were not run because the web is untouched; the new fields are additive and ignored by the current types. No live provider calls were made.

## 8 Deviations

- The envelope said `source_groups` "already exists in the old model". It does not: T98 removed it, so the group mechanism is new (key `source_groups`, rule D2).
- Strict load now also rejects unknown TOP-LEVEL keys, not only unknown `source_weights` keys. Retired keys keep their specific messages because that check runs first.
- The history chart recomputes every day with the config, so plain recomputation with v2 would have changed past chart days. Instead of "do not recompute", versions are selected by day (D5), which keeps every past day's value identical (tested by `test_v1_chart_day_unchanged_by_v2_switch`).

## 9 Blockers

- Merge timing (D10): `until: 2026-10-21` is correct only if this merges before the refresh that freezes day 2026-10-22 under v1. Guard: `test_committed_frozen_snapshots_match_their_days_weights` goes red after main is merged in if that happens. The fix is to set `weights_history[0].until` to the last v1-frozen day.
- Registry update request: T130 is `in review` with the draft PR.

## 10 Follow-up

- Web: mark v1 vs v2 points on the history chart (using `weights_version`), and change the Sources header "of 100 weight" now that the total is 90.
- Decide whether `rising_weight` in the coin table needs a tooltip explaining the group vote.
- Once trends, reddit or xsearch has data, re-check trigger counts under v2.

## 11 Context cost

Loaded: CLAUDE.md (system), the envelope, `discovery.py`, `sources.py`, `signal_snapshots.py`, `discovery_history.py`, `models/discovery.py`, test fixtures (parts), the sibling T100a PLAN (head plus G7/G8 lines), the weighted-signal SPEC (grep only), and master-planner.md section 9. Approximate: 60k tokens of context. Spend was well under the 7 USD ask point (unmeasured exactly). Tools: Bash, Read/Write/Edit, GitHub MCP (PR), no web access used.
