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
  pause rest-of-day or until owner action, never downgraded), priority queue (yesterday first, then backfill
  newest first; X rotation order = oldest newest-stored day first, the W8b part of AC23), `run_x_unit` (pause and
  budget checked before each page load, every loaded post counted, no retry after a warning, a failed attempt
  still stamps the time the next delay runs from).
- `web_queries.py` + `api/data/attention_queries.json`: collector config block with validator (locked defaults),
  subreddits, per-source ambiguity lists, one name per placed coin; coin set = placed symbols minus ambiguity.
- `web_evidence.py`: evidence sidecar under `<cache>/attention/<source>/_meta/`, `commit_day` (first write wins).
- `pc_adapter.py`: Protocol, error classes, fake adapter, `SafeAdapter` refusing registry/publish/cookie import,
  shipped-recipe refusal, pinned commit constant, `npm ci --ignore-scripts`, profile dir outside the repo,
  15 USD monthly self-repair meter (an unknown repair cost spends the rest of the cap), class-and-status-only
  log helper.
- `api/scripts/probe_pc_sources.py`: parser and number-only report helpers; every mode exits 2 "not built yet".

## 4 Files changed

All new: `api/data/attention/{density,pc_pace,web_queries,web_evidence,pc_adapter}.py`,
`api/data/attention_queries.json`, `api/scripts/probe_pc_sources.py`,
`api/tests/data/attention/test_{density,pc_pace,web_queries,web_evidence,pc_adapter}.py`,
`api/tests/scripts/test_probe_pc_sources.py`, `api/tests/tooling_guards/test_pc_collector_guards.py`, and this
report. No `.github/`, `api/pyproject.toml`, `api/uv.lock` or `api/data/cache/` change.

## 5 Commits

Branch `claude/t140-w8b-collector-core`, based on `origin/main` 8fa2284: e1c73fe (core), 6c94380 (report
wording), then the review-fix commit that also carries this final report (SHAs in the PR).

## 6 Tests run

All `UV_FROZEN=1 uv run --project api ...`. Final gate run started 2026-10-21T22:24:47Z on the final tree
(the head of this PR), base 8fa2284. Baselines measured on fresh main 8fa2284 at the start of the session.

| Gate | Command | Before (main 8fa2284) | After |
|---|---|---|---|
| Red first | `pytest <7 slice files> -q` | 7 collection errors (modules absent) | 93 passed (first green) |
| Slice tests | same | n/a | 98 passed (93 + 5 review-fix tests) |
| Attention suite | `pytest api/tests/analytics/attention -q` | 231 passed, 2 warnings | 231 passed, 2 warnings |
| Scripts + data/attention + guards | `pytest api/tests/scripts api/tests/data/attention api/tests/tooling_guards -q` | 589 passed, 2 warnings | 687 passed (589 + 98), 2 warnings |
| Full API (once) | `pytest api -q` | 1811 passed, 1 skipped, 5 deselected | 1909 passed (1811 + 98), 1 skipped, 5 deselected, 2 warnings |
| File set | `git diff --name-only origin/main...HEAD` | | the 14 files above plus this report; forbidden-path count 0 |
| Hygiene | `git diff --check origin/main...HEAD` | | exit 0 |
| Secret scan (Validate Contract G8 pattern) | `git diff -U0 origin/main...HEAD \| grep -nE "^\+.*(Bearer ...\|API_KEY...)"` | | prints nothing |
| Banned names | the PLAN section 6 banned-name grep over `git diff -U0 origin/main...HEAD` (the three names of PLAN section 7) | | prints nothing (the guard builds them from split strings) |
| No network import | `grep -nE "^\s*(import\|from)\s+(requests\|httpx\|socket\|urllib\|playwright)"` over the 5 modules and the probe | | prints nothing |
| Lint | `ruff check --line-length 120` on the 13 Python files | | all checks passed |

Mutation spot checks (each reverted): `pc_pace.py` no halving -> 6 failed; no pause check -> 2 failed; no
restart min delay -> 2 failed; no warn -> 4 failed; posts not counted -> 4 failed; no owner-pause guard ->
1 failed; no rotation sort -> 1 failed; no attempt stamp -> 1 failed; `pc_adapter.py` no fail-closed cost ->
1 failed. The 5 review-fix tests were written after their fixes (not red first); the mutations above are the
evidence that each one fails without its fix.

After the PR opened, main moved to 4675f82 (T130 weights v2 and two data refreshes; no file overlap with this
PR, clean merge). Full API on a local merge of 4675f82 into this head: 1959 passed, 1 skipped, 5 deselected,
0 failed. PR CI on that merge ref: `api — pytest` and `web — vitest, tsc, island build` both success.

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
  (W8f) not built; only the rotation queue order (PLAN section 8 maps that part of AC23 to W8b).
- SPEC Annex H lists "parsers" and "stores" under W8b; the PLAN section 3 rows (this envelope's scope) do not,
  so no parser was built (the Atom parser is W8c) and the existing `store.py` is reused unchanged.
- AC28's pure part only: a guard that no pure module reads `.hour`/`.minute` or builds a non-midnight `time()`.
  The four-start-times feed test is W8c.
- Coin names and ambiguity lists are a starting proposal from `trends_keywords.json` labels, UNVERIFIED until
  the owner reviews them.
- Fixed during the run: one test first wrote a state file into the real (git-ignored) cache; removed it and made
  cache isolation autouse in the three state-writing test files.

## 9 Blockers

None for W8b. Risks:
- Live behaviour is unproven until the W8c/W8d probes; `run_x_unit` is a core the W8d connector and the W8e
  worker still have to wire.
- PLAN R-3 relies on `api/data/cache/*` being git-ignored, but `.github/workflows/attention-refresh.yml`
  (lines 158 and 253) runs `git add -f api/data/cache/attention/`, which force-adds everything under that root,
  `_pc_state/` and `<source>/_meta/` included, if they ever exist on the runner. They do not today (the PC code
  runs only on the owner's PC; tests use a temporary cache). W8e (worker never on runners) and the later
  "how PC values reach the repo" decision must keep it that way, or narrow that `git add` (a `.github/` edit,
  owner approval first). Not changed here: `.github/` is a hard stop for this slice.

## 10 Follow-up

W8c (Reddit connector) can start on this core. W8e wires `PcSource`, `Trickle` and `build_queue` into the
worker, passes each unit's end time to `next_due`, and handles an unreadable state file (here it raises).
PR #153 must merge before or with these slices so the PLAN and SPEC are on main.

## 11 Context and cost

Opened: CLAUDE.md, envelope, PLAN (sections 2-8), SPEC (Locked pacing rules, AC list, Annexes A-D),
`store.py`, `attention_narratives.json`, `trends_keywords.py`, `narratives.py`, `cache.py` helpers, tooling
guard helpers, master-planner.md section 9 (report template). `equities_refresh.py` not needed for W8b (no
worker). Cost: unmeasured (no cost meter is visible in this session).
