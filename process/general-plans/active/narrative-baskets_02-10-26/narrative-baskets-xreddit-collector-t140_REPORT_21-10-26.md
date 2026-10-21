---
name: report:narrative-baskets-xreddit-collector-t140
description: "T140 worker report: slice W8b (pure collector core) of the X and Reddit PC collector."
date: 21-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: report
---

# T140 report: W8b pure collector core

## 1 Task ID

T140 = slice W8b of `narrative-baskets-xreddit-collector_PLAN_21-10-26.md` (PLAN and SPEC on branch
`claude/t126-xreddit-collector-spec`, PR #153, read with `git show`). Branch `claude/t140-w8b-collector-core`.

## 2 Outcome

done

## 3 Summary

Built the W8b rows of PLAN section 3, red tests first, all pure (no network import):
- `density.py`: SPEC A.1 formula (exact, capped, 0.25 h floor, page cap / budget cut uses k, below N_min missing),
  dedupe (identical text, 3 per author), yesterday-only gate, canary-gated zero, spike flag.
- `pc_pace.py`: seeded-RNG trickle, `plan_run` (20 s behind start, never faster than the min delay, also across
  a restart), persisted per-source state (daily budget with UTC-midnight reset, adaptive halve/double for X,
  pause rest-of-day or until owner action), priority queue (yesterday first, then backfill newest first),
  `run_x_unit` (budget checked before each page load, every loaded post counted, no retry after a warning).
- `web_queries.py` + `api/data/attention_queries.json`: collector config block with validator (locked defaults),
  subreddits, per-source ambiguity lists, one name per placed coin; coin set = placed symbols minus ambiguity.
- `web_evidence.py`: evidence sidecar under `<cache>/attention/<source>/_meta/`, `commit_day` (first write wins).
- `pc_adapter.py`: Protocol, error classes, fake adapter, `SafeAdapter` refusing registry/publish/cookie import,
  shipped-recipe refusal, pinned commit constant, `npm ci --ignore-scripts`, profile dir outside the repo,
  15 USD monthly self-repair meter, class-and-status-only log helper.
- `api/scripts/probe_pc_sources.py`: parser and number-only report helpers; every mode exits 2 "not built yet".

## 4 Files changed

All new: `api/data/attention/{density,pc_pace,web_queries,web_evidence,pc_adapter}.py`,
`api/data/attention_queries.json`, `api/scripts/probe_pc_sources.py`,
`api/tests/data/attention/test_{density,pc_pace,web_queries,web_evidence,pc_adapter}.py`,
`api/tests/scripts/test_probe_pc_sources.py`, `api/tests/tooling_guards/test_pc_collector_guards.py`, and this
report. No `.github/`, `api/pyproject.toml`, `api/uv.lock` or `api/data/cache/` change.

## 5 Commits

One commit on `claude/t140-w8b-collector-core`, based on `origin/main` 8fa2284 (SHA in the PR).

## 6 Tests run

All `UV_FROZEN=1 uv run --project api ...`, gate run started 2026-10-21T22:14:42Z, tree = the commit of this PR, base 8fa2284.

| Gate | Command | Before (main 8fa2284) | After |
|---|---|---|---|
| Red first | `pytest <7 slice files> -q` | 7 collection errors (modules absent) | 93 passed |
| Slice tests | same | n/a | 93 passed |
| Attention suite | `pytest api/tests/analytics/attention -q` | 231 passed, 2 warnings | 231 passed, 2 warnings |
| Scripts + data/attention + guards | `pytest api/tests/scripts api/tests/data/attention api/tests/tooling_guards -q` | 589 passed, 2 warnings | 682 passed (589 + 93), 2 warnings |
| Full API (once) | `pytest api -q` | 1811 passed, 1 skipped, 5 deselected | 1904 passed (1811 + 93), 1 skipped, 5 deselected, 2 warnings |
| File set | `git diff --name-only origin/main...HEAD` | | the 14 files above plus this report; forbidden-path count 0 |
| Hygiene | `git diff --check origin/main...HEAD` | | exit 0 |
| Secret scan (Validate Contract G8 pattern) | `git diff -U0 origin/main...HEAD \| grep -nE "^\+.*(Bearer ...\|API_KEY...)"` | | prints nothing |
| Banned names | `git diff -U0 origin/main...HEAD \| grep -niE "xscrape\|kloxeld\|gunkonchi"` | | prints nothing (guard builds them from split strings) |
| No network import | `grep -nE "^\s*(import\|from)\s+(requests\|httpx\|socket\|urllib\|playwright)"` over the 5 modules and the probe | | prints nothing |
| Lint | `ruff check --line-length 120` on the 13 Python files | | all checks passed |

Mutation spot checks on `pc_pace.py` (each reverted): no halving -> 6 failed; no pause check -> 2 failed; no
restart min delay -> 2 failed; no warn -> 4 failed; posts not counted -> 4 failed.

Baselines differ from the PLAN's (main 007d53c: 492 and 1714 total) only by merged PRs: 7 commits since, adding
`test_trends_keywords.py`, `test_check_trends_keywords.py`, `test_probe_trends.py` and `trends_fixtures.py`
(+97 tests in the scripts/data/attention group, same +97 in the full run).

## 7 Tests NOT run

No provider, API Anything or live network call (none exists in W8b). Owner probes needed by this slice: none.

## 8 Deviations

- Reddit daily budget 150 and delay 60-120 s from the latest SPEC (T138); `reddit_sample_min` 10 (SPEC A.2/AC2)
  is in the config block because the A.2 counting reuses it; the Reddit counting itself is W8c.
- Config keys beyond the PLAN list, all from the SPEC: `x_page_gap_min_s`/`x_page_gap_max_s` (5-15 s, rule 1),
  `x_backfill_days` 14 (Annex C). Per-coin `cashtag_only` flag for X names that are common words (A.1 "use the
  cashtag only").
- A page load cut by the daily budget with k >= N_min uses the page-cap formula and flag (`pagecap`), per AC21
  ("keeps a unit whose count already reached x_sample_min").
- The Reddit stream coverage rule (>= 0.8, partial) is W8c2 in the PLAN, not W8b: not built. X rotation scoring
  (W8f) not built.
- Coin names and ambiguity lists are a starting proposal from `trends_keywords.json` labels, UNVERIFIED until
  the owner reviews them.
- Fixed during the run: one test first wrote a state file into the real (git-ignored) cache; removed it and made
  cache isolation autouse in the three state-writing test files.

## 9 Blockers

None. Risks: live behaviour is unproven until W8c/W8d probes; `run_x_unit` is a core the W8d connector and W8e
worker still have to wire.

## 10 Follow-up

W8c (Reddit connector) can start on this core; W8e persists nothing new (state already persisted here). PR #153
must merge before or with these slices so the PLAN and SPEC are on main.

## 11 Context and cost

Opened: CLAUDE.md, envelope, PLAN (sections 2-8), SPEC (Locked pacing rules, AC list, Annexes A-D),
`store.py`, `attention_narratives.json`, `trends_keywords.py`, `narratives.py`, `cache.py` helpers, tooling
guard helpers, master-planner.md section 9 (report template). `equities_refresh.py` not needed for W8b (no
worker). Cost: unmeasured (well under the 7 USD ask point by token estimate).
