---
name: report:narrative-baskets-trends-t180
description: "T180: every coin that passes into Discovery must have a Google Trends keyword (guard test, loader counts, runner reason, Sources panel text)."
date: 24-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: report
---

# T180 Trends keyword guard: REPORT

## 1 Task ID
T180, branch `claude/t180-trends-keyword-guard`, cut from `claude/t160-trends-qualified-terms` (PR #171, not merged). One draft PR, base = that branch (stacked on #171; retarget to main after #171 merges). Not merged.

## 2 Outcome
Done. The rule "every eligible Discovery coin has a usable Google Trends keyword" is now a test over the real shipped files. The runner and the Sources payload use one shared function to decide which coins have a keyword, and the Sources panel shows the coverage and the coins without one in plain words. Discovery eligibility is unchanged and no coin is dropped. No data file was edited.

Real files today (snapshot in `api/data/cache/attention/universe.json`): 78 eligible coins, 73 with a topic or term. The 5 without one are AKE, BTW, GRAM, LIT and RAIN: all `no-keyword` and all on the allowlist. BDX: #171 added `beldex crypto`, so the guard passes for it. PRL, STABLE and STX have entries but are not eligible today.

## 3 Summary
1. `discovery.eligible_discovery_symbols()` (new, in `api/analytics/attention/discovery.py`) wraps the existing `eligibility(load_config(), load_universe_rows())`, so the eligibility logic is not copied. The guard test in `test_trends_keyword_guard.py` calls `trends_keywords.guard_gaps(load(), PINNED_ELIGIBLE)` and checks it equals the empty result. `PINNED_ELIGIBLE` is the reviewed 78-coin set from the 2026-10-24 snapshot, BDX included (planner decision, follow-up commit); it is updated on purpose when the universe changes. The live eligible set never fails CI: `trends_keywords.gap_report(km, eligible)` gives a non-failing line ("trends keyword: N of M eligible coins; no keyword: SYM (status), ..."), and a test proves a new live coin without a keyword only shows up there. On failure it prints the exact symbols, grouped as `no-entry`, `no-keyword`, `skipped-unqualified` and `allowlist-has-keyword`.
2. The allowlist is one constant, `trends_keywords.UNIDENTIFIED_TICKERS` = {AKE, BTW, GRAM, LIT, PRL, RAIN, STABLE}, with a comment. An allowlisted coin may only stay `no-keyword`. If it gains a topic or term, the guard fails under `allowlist-has-keyword` until it is removed from the list, whether or not it is eligible that day. An allowlisted coin with no entry at all is still a gap.
   Interpretation: all seven tickers already have a `no-keyword` entry. So "the allowlist contains a symbol that now HAS an entry" is read as "now has a usable keyword (topic or term)". Read literally, the test would fail today.
3. Loader: `validate`/`load`/`safe_load` now return `not_placed`, a sorted list of the keys outside the placed symbols passed in. The existing warning strings are kept, and nothing raises. `keyword_status(km, sym)` returns `topic`, `term`, `no-entry`, `no-keyword`, `skipped-unqualified` (a name-risk coin with a bare term) or `bad-file`. `coverage(km, eligible)` counts `topic`, `term` and `keyword-missing`; a `no-keyword` entry counts as missing, apart from topic and term.
4. Runner (`_run_trends`): the skip branch now calls `keyword_status`. Reasons are mapped by `MISSING_KEYWORD_REASON`, which keeps the existing strings that tests pin: "no keyword mapped" for no-entry and no-keyword, and `trends.NAME_AMBIGUOUS` for skipped-unqualified. The `trends detail:` line already counts these as `no-keyword` / `skipped-unqualified`; its format is unchanged. These series are `unavailable` with no points, so they are never stored as 0 (new test).
5. Payload: `GET /api/narrative/sources` gains the field `trends_keyword: {eligible_size, with_keyword, missing: [{symbol, reason: "no-trends-keyword", detail}]}`, where `detail` is the `keyword_status` value. Only fields were added. Discovery has no per-coin reasons for sources that are missing, so the Sources payload is where these reasons live.
6. Web: the Trends row's Note cell (text only, no layout change) reads "Trends keyword: N of M eligible coins. No Google Trends keyword yet: AKE, ...". The copy `no-trends-keyword` → "No Google Trends keyword yet" is in the shared `formatNarrativeReason` map. The types gained `DiscoveryTrendsKeyword` and `DiscoveryKeywordGap`.

## 4 Files changed
- `api/data/attention/trends_keywords.py`, `api/analytics/attention/discovery.py`, `api/analytics/attention/sources.py`, `api/models/discovery.py`, `api/scripts/refresh_attention.py`
- tests: `api/tests/data/attention/test_trends_keyword_guard.py` (new, 20 tests), `api/tests/analytics/attention/test_sources.py` (+2), `api/tests/scripts/test_refresh_attention_trends.py` (+3, parametrized), `api/tests/routers/test_discovery.py` (key set of the sources route + `trends_keyword`)
- web: `web/components/narrative/DiscoverySourcesPanel.tsx`, `web/lib/format-unavailable-reason.ts`, `web/lib/types/discovery.ts`, `web/components/narrative/__tests__/DiscoveryTab.test.tsx` (+2), `web/lib/__tests__/format-unavailable-reason.test.ts` (+1)
- this report

## 5 Commits
`9486449` code, tests and this report; a follow-up commit pins the eligible set and adds `gap_report` (planner answers to Q1/Q2). See the PR head.

## 6 Tests run
- Red first: guard and loader 18/18 failed, runner 3/3 failed, sources 2/2 failed, web 3/3 failed. All pass after the change.
- `pytest api/tests/data/attention api/tests/analytics/attention api/tests/scripts api/tests/routers`: 1239 passed, 1 deselected.
- Full `pytest api`: 2052 passed, 2 skipped, 5 deselected, 0 failed (first commit: 2050). Base (#171 head): 2027 passed, 2 skipped, 5 deselected. +25 = the new tests. The `gap_report` test was red first (1 failed), then green.
- Web: `pnpm test` 63 files, 573 tests passed. `tsc --noEmit` clean. `pnpm build:islands` builds (CI runs it).
- ruff on the touched files: 22 findings, identical to the base; 0 new, and the new test file is clean. `git diff --check` clean.
- Secret scan of the diff: clean. File-set check: no `.github/`, pyproject, uv.lock, `api/data/cache` or `trends_keywords.json` change.
- Mutation check (each mutant applied, its tests run, file restored): 20/20 killed. The mutants covered: the `gap_report` missing list and its N-of-M count, the allowlist (adding a coin, removing a coin), the allowlist exemption (widened, removed), `allowlist-has-keyword` (topic only, emptied), name-risk skip, no-keyword→term, no-entry→no-keyword, coverage counting no-keyword as a keyword, `not_placed` emptied, the runner reason map, the runner treating unqualified as pullable, the Sources gaps dropping no-entry, eligibility replaced by all universe rows, the web copy, the missing-list threshold and the N-of-M numbers. One first-pass mutant was equivalent and was replaced. The missing-list threshold first survived; adding a single-gap web test killed it.

## 7 Tests NOT run
No network and no provider contact. Whether Google returns data for any keyword is not provable here; the owner probes later. Playwright e2e was not run (no route or flow changed).

## 8 Deviations
- Runtime reason: the existing strings already cover every missing case, so no new runtime reason was added and the pinned strings are kept. `no-trends-keyword` is the payload reason only, and the runner's skip detail is in `detail`.
- The allowlist rule is read as "has a usable keyword", not "has any entry" (see 3.2).
- `test_routers/test_discovery.py`: the exact key set of the sources route was extended by `trends_keyword`. That additive field is the reason for the edit.
- The guard checks a pinned eligible set, not the live snapshot (planner answer to Q1), so a daily snapshot commit cannot turn CI red. The live gap is shown at runtime, in the Sources coverage line and by `gap_report`.

## 9 Blockers
None.

## 10 Follow-up / open questions
- Q1 answered by the planner: pinned set plus a live report that never fails. Done.
- Q2 answered by the planner: PRL and STABLE stay on the allowlist. Unchanged.
- When the universe changes, update `PINNED_ELIGIBLE` on purpose.
- The owner names AKE, BTW, GRAM, LIT, RAIN (and PRL, STABLE); each one named shrinks the allowlist.

## 11 Context cost
Extra docs opened: `process/context/operating-instructions.md` (test commands and tiers). Code read beyond the envelope: `api/data/attention/trends.py`, `api/analytics/attention/sources.py`, `api/models/discovery.py`, `universe.py`, `universe_store.py`, `web/lib/format-unavailable-reason.ts`, `web/components/narrative/DiscoverySourcesPanel.tsx`, the T160 report (for the format). The SPEC was not needed.
