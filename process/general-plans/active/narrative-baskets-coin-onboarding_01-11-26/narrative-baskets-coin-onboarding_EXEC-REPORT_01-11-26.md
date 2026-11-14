---
name: report:narrative-baskets-coin-onboarding-exec
description: "EXECUTE report for T223 automatic coin onboarding (O0-O7), shadow mode."
date: 01-11-26
metadata:
  node_type: memory
  type: report
  feature: narrative-baskets
  phase: EXECUTE
---

# T223 automatic coin onboarding - EXEC-REPORT

## 1. Summary

O0-O7 are CODE DONE in `shadow` mode on branch `claude/coin-onboarding`. The work adds the ledger, the classifier, strict resolver overlays with pending and log handling, a reverse tool, narrative proposals and a read-only approve tool, `GET /api/narrative/onboarding`, the New coins tab, and D-31 docs. Nothing was pushed and no PR was opened. Parent review comes next.

## 2. Scope delivered

- O0/O1, kept from the earlier worker and hardened after parent review. A ledger is refused as corrupt if any value has the wrong type, a count is negative, a class, source or date is invalid, or the file is over the size cap. Reads of the ledger and of other bot JSON files are size-bounded. A snapshot is refused if a coin id or a rank appears twice, or if a date, symbol or id is invalid. Symbols use exactly `[A-Z0-9_]{1,24}`, as the plan says. The earlier worker had also allowed `-`; that is removed.
- O3: `coin_class.py` gives the class. A stablecoin needs two signals plus a tight price band, and the band needs at least `price_min_days` days of prices (an owner setting). Detail and price fetches make one paced request each, with no retry. A refusal stops the step and the coin stays `unknown`.
- O4: Wikipedia applies only when the canonical page title matches exactly (no redirect). Trends applies only when exactly one exact-name crypto topic exists AND its series passes the checks AND the stored-volume identity check passes. Reddit/X entries are always `cashtag_only`. Before resolving, the refresh writer moves colliding overlay entries to pending, with a log line. The read-only loaders never write. The first HTTP 429 stops the remaining onboarding network sources for that run. Each network step has a 180 s budget.
- O5: proposals come from `categories.json` and list every mapped match. `onboarding_approve.py` writes nothing.
- O6: the route only reads local files. The New coins tab renders all values as text and shows the shadow banner.
- Approved extra consumer touchpoint: `api/data/attention_pc_refresh.py` default `web_queries.load` changed to `load_merged`. Without this, an overlay Reddit/X entry for a coin the owner has placed never reaches the real collector. Injection through `queries=` is unchanged.

## 3. Files changed

New: `api/analytics/attention/onboarding.py`, `api/data/attention/{coin_class,narrative_proposals,onboarding_resolver,onboarding_sources}.py`, `api/scripts/onboarding_{approve,reverse}.py`, `web/components/narrative/NewCoinsPanel.tsx`, and the tests `test_coin_class.py`, `test_onboarding_{overlay,resolver,sources}.py`, `test_narrative_proposals.py`, `test_onboarding.py`, `test_onboarding_{approve,reverse}.py`, `NewCoinsPanel.test.tsx`.

Changed: the plan touchpoints, plus `api/analytics/attention/sources.py` (the Trends coverage panel now uses the merged loader), `api/data/attention_pc_refresh.py` (the approved amendment), the D-31 docs, and the owner-settings key `price_min_days` in `api/data/coin_onboarding.json`.

## 4. Test literal changes

- `test_refresh_attention.py`: `RUNNERS` adds `ledger`, `classify`, `resolve_wiki` and `resolve_trends`; `DEFAULT_SOURCES` adds `ledger` before `signals`.
- `test_universe_classes.py`: the exact key sets gain three zero-count reasons. The enforce exit-band fixture now carries valid symbols (`C110`, `C111`, `C5`), because ledger validation is now strict.
- `routers/test_discovery.py`: `OLD_REASONS` gains `watching`, `inactive` and `unclassified`.
- Web exclusion tests: the length and exact list grow by those three reasons.
- `test_narratives.py:43`, `test_web_queries.py:84` and `test_trends_keywords.py:43-49`: count pins replaced by property checks. The `3/75` line in the workflow guard is unchanged.
- `test_check_wiki_titles.py`: a redirect to a different canonical title is now refused. Test fixtures carry the returned title.
- `test_onboarding_resolver.py`: the short-volume reason now shows effective days, `66` (60 identity days plus the 7-day smoothing window).
- `NarrativeTabs.test.tsx` and `web/e2e/narrative.spec.ts`: three tabs.

## 5. Gate results

The saved baseline is in the OS temp folder `t223/basefail_api_ids.txt`: 41 API failures. The web baseline is one failure, `lib/__tests__/plot-ink.test.ts`.

- Web vitest: 1 failed, 408 passed (409). The only failure is the baseline `plot-ink.test.ts`. `tsc --noEmit`: exit 0.
- API gate, run 1: three new failures caused by this code (RUNNERS literal, strict ledger fixture, quarantine retention), all fixed. The `test_snapshot_narrative.py` failures in run 1 were environmental: the run crossed UTC midnight and the test's `TODAY` is fixed at import. The file then passed alone, 14 passed.
- API gate, repair run 2: three new failures, all from one cause, a `dict | set` TypeError in the trends filter. Fixed.
- API gate, final repair run (the second repair cycle): 44 failed, 2861 passed, 2 skipped. 41 of the 44 are baseline failures. The other three are subprocess tests that hit `OpenBLAS memory allocation failed` and a subprocess timeout on the busy host. Run once targeted together with `test_refresh_attention.py`: 66 passed. One baseline failure (`test_synthetic_100_coins_x_100_days_is_fast`) passed in this run.

After the final gate started, one constant changed: the onboarding per-step budget went from 600 s to 180 s, so all three network steps fit inside the 12-minute owner-applied workflow step. The targeted 66-test run above covered the changed module.

## 6. Smoke evidence

The smoke ran offline against a temporary cache. Socket connects were limited to loopback and the httpx transport was patched to refuse every call. The real refresh entrypoint printed `ledger: ok seeded 100`, then `ledger: ok advanced, entered 1`, with exit codes 0 and 0. Read-back showed 101 ledger coins, and the new coin is `watching`, count 1, class `unknown`. The real route returned 200, mode `shadow`, status `ok`, and the coin shows `watching`, 1, `unknown`, Trends `missing`. The second day logged 1 entry. The New coins panel was tested in vitest with a fixture response.

## 7. Acceptance evidence

| AC | Evidence |
|---|---|
| AC1-AC5 | `test_coin_ledger.py`, `test_universe_classes.py` enforce cases, `test_refresh_attention.py::TestLedgerStep`, smoke |
| AC6-AC7 | `test_coin_class.py`, `TestClassifyStep`, eligibility enforce cases |
| AC8 | `TestResolveStep::test_strict_trends_applies_with_stored_volume_and_logs`, resolver unit tests |
| AC9 | Wikipedia resolver and checker tests, refresh redirect test |
| AC10-AC12 | resolver pending and none tests, overlay ambiguity and collision tests, the refresh quarantine test |
| AC13 | `test_narrative_proposals.py`, `test_onboarding_approve.py`, converted pins |
| AC14 | `test_onboarding.py`, route test, `NewCoinsPanel.test.tsx`, `NarrativeTabs.test.tsx` |
| AC15 | log and reverse tests, log assertions in the quarantine and apply tests |
| AC16 | overlay and collector tests, refresh never decides the exit code, shipped-file property tests |
| AC17 | `test_onboarding_settings.py`, settings-driven ledger and class tests |
| AC18 | NOT RUN: owner live probe P-O1 |

## 8. Owner-applied workflow diff (not applied; `.github` untouched)

```diff
@@ jobs.refresh-extra
-    timeout-minutes: 40
+    timeout-minutes: 52
@@ after "Refresh Google Trends"
+      - name: Onboard new coins (shadow mode)
+        continue-on-error: true
+        timeout-minutes: 12
+        run: |
+          set -o pipefail
+          uv run --project api --with pytrends==4.9.2 python api/scripts/refresh_attention.py --sources classify,resolve_wiki,resolve_trends 2>&1 | tee "$RUNNER_TEMP/extra-onboarding.log"
```

Guard-test edits that go with it: `test_extra_job_runs_after_core_even_when_it_is_red` changes from `== 40` to `== 52`. Add this test:

```python
def test_onboarding_step_is_isolated_bounded_and_after_trends() -> None:
    steps = _steps("refresh-extra")
    onboard = [s for s in steps if "--sources classify,resolve_wiki,resolve_trends" in s.get("run", "")]
    assert len(onboard) == 1 and onboard[0]["continue-on-error"] is True and onboard[0]["timeout-minutes"] == 12
    assert "pytrends==4.9.2" in onboard[0]["run"] and "pipefail" in onboard[0]["run"]
    assert steps.index(_trends_step()) < steps.index(onboard[0])
```

No verify-listing change is proposed. The onboarding lines are fixed-token status lines and must not turn the extra job red.

## 9. Operator notes

- The log is at `api/data/cache/attention/onboarding/log/<UTC date>.json`. Pending evidence is in `pending.json`. Proposals are in `narrative_proposals.json`.
- To reverse an entry, run `python -m api.scripts.onboarding_reverse SYMBOL SOURCE`, then paste the printed `blocked_sources` value. Stored series are not purged.
- To confirm a class, edit `confirmed_classes` in `api/data/coin_onboarding.json`.
- To approve a narrative, run `python -m api.scripts.onboarding_approve SYMBOL NARRATIVE` and paste the printed coin entry into that narrative.
- To enforce, the owner edits `mode` to `enforce` only after P-O2. No code flips it.

## 10. Not run and risks

- P-O0, P-O1 (AC18) and P-O2: NOT RUN. They need live providers or the owner.
- The live shapes of CoinGecko coin detail, the 120-row markets response, Google suggestions and the Wikipedia summary are UNVERIFIED.
- A full API gate with no resource or environment failures was not repeated after repair cycle 2, as the maximum of two repair cycles requires.
- This was written on the configured fallback-capable lane. The parent's independent review is required.

## 11. Next actions

1. Parent independent review.
2. With explicit authorization: push the existing branch and open one draft PR.
3. The owner applies the workflow diff, then runs P-O0, P-O1 and P-O2.
