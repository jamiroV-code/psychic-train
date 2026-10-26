## 1 Task ID
T192: Google Trends terms for 8 owner-named tickers (9 entries), shrink the unidentified allowlist. Data-only.

## 2 Outcome
done (pending owner probe)

## 3 Summary
- 9 entries set to qualified `term`, note "owner-named 26-10-26, qualified-term, not checker PASS": AKE, BTW, GRAM, LIT, STABLE, RAIN, PRL, PEARL (replaced "pearl crypto"), OKB (replaced "okb token").
- `UNIDENTIFIED_TICKERS` is now an empty frozenset (constant and its guard kept). Coverage: 78 of 78 pinned eligible coins have a keyword.
- The 40 topic entries and all other entries are untouched (topics test passes byte-for-byte).
- These are untested search phrases; nothing here claims they work.
- PEARL and PRL are the same CoinGecko project (pearl-2 / pearl-research), so Discovery counts it twice while both stay eligible. Eligibility NOT changed.

## 4 Files changed
- api/data/trends_keywords.json (9 entries)
- api/data/attention/trends_keywords.py (allowlist constant + comment only)
- api/tests/data/attention/test_trends_keywords.py, test_trends_keyword_guard.py, api/tests/scripts/test_probe_trends.py
- this report

## 5 Commits
Branch claude/t192-named-tickers (SHA in the PR).

## 6 Tests run
See PR body for exact counts. `uv run --project api pytest api/tests/data/attention api/tests/scripts api/tests/analytics/attention`: 1169 passed after the probe-test fix. Red first: 6 new/updated tests failed before the data change. Also ruff on touched files, JSON validity, `git diff --check`, secret scan: clean.

## 7 Tests NOT run
Any live Google Trends call (no network by order).

## 8 Deviations
Loader rules forced three shapes; the loader was not loosened:
- LIT "lighter exchange" -> "lighter crypto" ("exchange" is not a qualifier word).
- STABLE "stable blockchain" -> "stable chain" ("blockchain" is not one).
- PRL "pearl ai crypto" -> "pearl ai coin": the loader rejects a term shared by two coins (case-insensitive). PEARL keeps "pearl ai crypto".
GRAM "the open network toncoin" passes as is ("network" is the qualifier). Tests adapted: guard tests that needed a non-empty allowlist now monkeypatch it; test_probe_trends used GRAM as its no-keyword example and now uses an absent symbol.

## 9 Blockers
None. Registry-update request: T192 done, awaiting owner probe.

## 10 Follow-up
Owner probe, then adjust any term that does not resolve. Decide whether PRL/PEARL should both stay Discovery-eligible.

## 11 Context cost
Loaded CLAUDE.md, envelope, trends_keywords.json/.py, guard and keyword tests, trends.py (qualifier rule), master-planner.md section 9. About 40k tokens. Owner probe command (no network here):
`uv run --project api --with pytrends==4.9.2 python -m api.scripts.probe_trends --alone 'AKE,BTW,GRAM,LIT,STABLE,RAIN,PRL,PEARL,OKB'`
Read it: for each coin, an outcome of ok with non-zero rows/complete days means the phrase returns data; empty or all-zero or an error means replace that term (the phrase may be too rare or too ambiguous). Judge each alone, not relative to the anchor.
