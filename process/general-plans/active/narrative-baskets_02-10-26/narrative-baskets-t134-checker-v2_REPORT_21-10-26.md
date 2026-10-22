# T134 report: Trends checker v2 and 12 seeded topics

## 1 Task ID
T134. Branch claude/t134-trends-checker-v2, draft PR #157 (do not merge).

## 2 Outcome
done

## 3 Summary
- trends_keywords.json: the 12 owner-run PASS coins move from term to topic and get the note "checker PASS 21-10-26". Labels and all other entries are unchanged.
- Checker v2: wider crypto type list built from real Google strings; name-match preference when several candidates are crypto-typed; a prefix rule with a generic-suffix guard; ticker labels pass only when a title equals the ticker; a verify link for each AMBIGUOUS coin.
- Red first: 8 new or changed tests failed before the code change, then passed.
- PLAN §3.3 and SPEC §8 have T134 follow-up notes. M1 holds: no exception message is printed.

## 4 Files changed
api/data/trends_keywords.json; api/scripts/check_trends_keywords.py; api/tests/scripts/test_check_trends_keywords.py; api/tests/scripts/test_probe_trends.py; api/tests/data/attention/test_trends_keywords.py; the T121 PLAN and T120 SPEC (follow-up notes); this report.

## 5 Commits
461c313 (feature) plus this report commit, on claude/t134-trends-checker-v2.

## 6 Tests run (UTC 2026-10-21, base 8fa2284 to 461c313)
- `UV_FROZEN=1 uv run --project api pytest api/tests/scripts api/tests/data/attention -q`: before 512 passed, after 521 passed.
- `UV_FROZEN=1 uv run --project api pytest api/tests -q`: before 1811 passed, 1 skipped, 5 deselected; after 1820 passed, 1 skipped, 5 deselected.
- ruff on the 4 touched .py files: "All checks passed!" before and after. Repo-wide `ruff check api` reports 396 errors before and after (unchanged, none in touched files).
- G7 sha256 -c on the 3 frozen signals snapshots: 3 OK. G8: `git diff --check` exit 0, the secret scan prints nothing.

## 7 Tests NOT run
Live Google run: not allowed in this task. The owner re-runs the checker (see 10).

## 8 Deviations
- Prefix rule tightened: the leftover part of the name must be a generic suffix (coin, protocol, network, token, chain, blockchain, finance). As specified, "Bitcoin" (Cryptocurrency) would PASS for BCH "Bitcoin Cash" and "Ethereum" for "Ethereum Classic". NEAR and WLD still PASS.
- The new short type words (currency, chain, and the listed phrases) match only the whole type, so "Restaurant chain" and the like stay out. The original words still match anywhere in the type.
- Ticker labels: a PASS needs a title equal to the ticker, case-sensitive. XRP, HTX and OKB pass; RAIN with the title "Rain" stays AMBIGUOUS, which keeps L1.
- BNB: narratives/universe have no coin display name (the universe cache has only the coingecko id "binancecoin"), so BNB stays AMBIGUOUS and the reason line says so.
- 5 probe_trends tests hardcoded the old terms. Seeding topics changes the probe's defaults, as the SPEC intends, so the tests now take their expected keywords from the file.
- The ids for the AMBIGUOUS fixtures (ETH, ALGO, AVAX, ...) are made up, because the envelope gave only the PASS ids. The types match the owner's output.
- XMR: the test runs "Coin" as type Topic and as type Coin. Monero PASSes in both.

## 9 Blockers
None. Registry update requested: T134 is done and its PR is in draft.

## 10 Follow-up
Owner's next command (from the repo root, same as before):
`uv run --project api --with pytrends python -m api.scripts.check_trends_keywords`
Paste back the whole output: the per-coin lines, the counts line, the paste-ready JSON block and the "needs a decision" block with its verify lines.
Note: the 12 seeded coins keep their labels, so they are checked again. They should PASS with the same ids.
Expected PASS on the new run (13): BGB GT KCS VVV XAUT XRP CAKE UNI HBAR XLM HTX NEAR WLD, plus XMR if Google returns Monero (Cryptocurrency) again.
Expected to stay AMBIGUOUS (name-fallback candidates for T100b): ETH (Software), ALGO, AVAX, ATOM, APT, SUI, TRX, JUP, STX, ZEC, KAS, FIL, PI, POL, BNB (ticker label, no display name), and the other coins whose only candidates are Topic or other generic types.
Proposed: T100b uses the topic where one exists and the name as fallback for the coins listed above, after the owner confirms them with the verify links.

## 11 Context cost
Loaded: CLAUDE.md, check_trends_keywords.py, trends_cli_common.py, trends_keywords.json/.py, both test files, test_probe_trends.py, trends_fixtures.py (header only), PLAN §3.3 and G7/G8, SPEC §8 (excerpts), master-planner.md §9 (report template only; not named in the envelope). About 60k tokens. Tools: Bash, file tools, GitHub MCP.
