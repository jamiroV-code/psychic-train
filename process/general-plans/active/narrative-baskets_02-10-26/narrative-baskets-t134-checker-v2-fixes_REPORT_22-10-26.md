# T134 fix round (T142 review) report

## 1 Task ID
T134, fix round for the T142 review (M-A, M-B, M-C, Low). Same branch claude/t134-trends-checker-v2, draft PR #157.

## 2 Outcome
done

## 3 Summary
- origin/main merged into the branch (merge commit, no rebase, no conflicts).
- M-A: a longer title passes only when it is the sole crypto-typed candidate and the name is followed by a generic suffix (coin, token, network, blockchain, cryptocurrency). Ethereum Classic, Bitcoin SV, Sky Mavis, Sky Protocol and Polygon zkEVM stay AMBIGUOUS. The prefix rule (NEAR, World) is unchanged.
- M-B: "cryptocurrency" and "blockchain" still match anywhere in the type. "token", "coin", "digital currency" and "virtual currency" match only as whole words. "protocol" and "decentralized" count only inside known whole-type phrases (decentralized finance [protocol], decentralized exchange, defi protocol). Internet protocol, Network protocol and Tokenization company are out, and Cosmos (Internet protocol) stays AMBIGUOUS.
- M-C: exact-title tier. One crypto-typed candidate whose title equals the name passes even with siblings (Bitcoin beside Bitcoin Cash, Zcash beside Zcash Foundation, Litecoin beside Litecoin Cash). Two exact titles stay AMBIGUOUS.
- Low: the docstring tells the owner to eyeball every PASS line before pasting, and a behaviour test runs ETH (Software) and ALGO (Topic) on its own. M1 is unchanged: class-only output, exit 1.

## 4 Files changed
api/scripts/check_trends_keywords.py; api/tests/scripts/test_check_trends_keywords.py; the T121 PLAN (one sentence added to the T134 note); this report. The 12 seeded topic ids are unchanged.

## 5 Commits
A merge of origin/main, then the fix commit on claude/t134-trends-checker-v2 (SHA in the PR).

## 6 Tests run (UTC 2026-10-22)
- Red first: test_v2_exact_title_tier_beats_contained_siblings, test_v2_contained_title_of_a_longer_coin_is_not_passed and test_v2_protocol_and_token_words_need_a_crypto_phrase failed before the code change (3 failed, 27 passed), then passed (30 passed).
- scripts + data/attention: 521 passed after the merge (before the fixes), 525 passed after.
- Full API (`UV_FROZEN=1 uv run --project api pytest api/tests -q`): after the merge, 1 failed, 1869 passed, 1 skipped, 5 deselected. After the fixes, 1 failed, 1873 passed, 1 skipped, 5 deselected. The one failure is the main test described in 9.
- ruff: the touched files pass "All checks passed!". Repo-wide `ruff check api` reports 399 errors on fresh main and 399 on this branch.
- G7: 3 OK. G8: diff --check exit 0, the secret scan prints nothing.

## 7 Tests NOT run
Live Google run: not allowed in this task.

## 8 Deviations
- M-A's suffix list for longer titles leaves out "protocol", so "Sky Protocol" stays AMBIGUOUS, as the review lists it. The prefix rule keeps "protocol" for NEAR Protocol.
- test_ambiguous_several_crypto_candidates (T100a) now uses two "Sui" titles, because under M-C "Sui" next to "Sui token" PASSes.

## 9 Blockers
None for this PR. One issue on main, not this PR's: api/tests/analytics/attention/test_weights_v2.py::test_committed_frozen_snapshots_match_their_days_weights also fails on clean origin/main. The snapshot 2026-10-21_w30.json, committed by 034c93c "chore: attention refresh 2026-10-22", has source_weights that differ from what weights_for_day gives for 2026-10-21 after T130 (7d93875). The test's own docstring gives the fix: move weights_history[-1].until to the last day frozen under v1. Proposed as a separate task, not done here.

## 10 Follow-up
- The owner's next command is unchanged: `uv run --project api --with pytrends python -m api.scripts.check_trends_keywords`. Paste back the full output.
- Proposed task: fix the T130 weights_history boundary (see 9).

## 11 Context cost
Loaded: the planner message, check_trends_keywords.py, its test file, test_weights_v2.py lines 195-215 (to diagnose). About 25k tokens. Tools: Bash, file tools, GitHub MCP, claude-code-remote send_message.
