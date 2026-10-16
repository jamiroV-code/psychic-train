# T70 (P5 S-C) report

## 1 Task ID
T70, branch `claude/t70-p5-s-c-scoring`, base origin/main 05debd6 (A=T68, B1=T69 merged).

## 2 Outcome
done. GET `/api/narrative/baskets/attention?window=7|30|90` (default 30, else 422) returns store-only coin and basket attention scores. ACs AC-36, AC-37 (API half), AC-24, AC-35 covered by tests.

## 3 Summary
- ratio = mean(last 7)/mean(last 90) daily (needs 90 points); rank = percentile vs reference ratios, ties averaged, outside coins placed not added; coin score = weighted mean of available ranks (weights in `attention_weights.json`, renormalised); basket = equal mean + breadth (share of members with score above d-7) + "covers N of M"; `main` never scored; no cross-basket total; `membership_as_of` = layout `saved_at` (else today).
- Missing is a state: not-probed, unavailable and insufficient-history sources feed nothing; rank/ratio/raw are null, never 0. Basket status `ok|no-data|empty`.
- Series: score per day from data up to that day, rebased to 100 at window start (first available day if the start is empty), null where no coin has data; `change` = score minus the base score.
- Known limits:
  - `attention_universe.json` ships with an EMPTY `reference` list (B1 does not persist the top-100 symbol list). Until it is filled, ranking is unavailable and baskets report `no-data`. Stablecoin and wrapped lists are populated.
  - Per-day series recomputes ratios for the whole reference set (up to ~91 days x sources x 100); fine for tests, not profiled at real scale.
  - Window query is validated by hand (`int` + 422) because FastAPI `Literal[7,30,90]` rejected the string "7" in this version.
  - Sources in the weights file without a probe record (exchange, trends, reddit, x today) count in "n of N" as not-probed.

## 4 Files changed
New: `api/analytics/attention/{__init__,ratio,rank,score,basket,series,universe}.py`, `api/models/attention.py`, `api/routers/attention.py`, `api/data/attention_weights.json`, `api/data/attention_universe.json`, `api/tests/analytics/attention/{__init__,conftest,test_primitives,test_basket_scoring}.py`, `api/tests/routers/test_attention.py`. Edited: `api/main.py` (+1 import, +1 include_router). Plus this report.

## 5 Commits
- e675114 test(T70): failing S-C scoring tests (red-first)
- 91c35f7 feat(T70): S-C coin and basket attention scoring API
- report commit (this file)

## 6 Tests run
- Baseline, untouched origin/main (clean worktree): `UV_FROZEN=1 uv run --project api pytest api/ -q` -> 1282 passed, 1 skipped, 5 deselected.
- After: same cmd on HEAD 91c35f7 -> 1306 passed, 1 skipped, 5 deselected (baseline + 24 new). UTC 2026-10-16.
- Red count: 24 tests in 3 modules, all red at e675114 (collection ImportError, no S-C code); one router test fix (stub target) made while going green.
- AC-25 protected tests green, `git diff --stat origin/main` on them empty. `git diff --check origin/main...HEAD` clean. Diff outside Owned: none. `git diff origin/main -- web` empty.
- Real cache (108 files, size+mtime digest), watchlist.json and layout.json (both absent) unchanged before/after the full run; tests use tmp_path via `isolated_cache`, no `monkeypatch.undo()`.
- Network: router test stubs `httpx.HTTPTransport.handle_request`, async transport and `socket.connect` to raise; handler passes.
- Spend: about 3 USD estimated (cap 15, ask 7), no external API calls.

## 7 Tests NOT run
vitest, e2e, Playwright (web untouched). No live provider or X call.

## 8 Deviations
- Reads: ran a small extra grep/sed on `refresh_attention.py`, `models/layout.py`, `data/layout.py`, `routers/baskets.py` (prefix) for signatures, over the stated read list. Total read stayed near the cap but was not strictly measured.
- First baseline run overlapped my edits and was discarded; the baseline above is from a clean worktree.

## 9 Blockers
None.

## 10 Follow-up
- Fill `reference` in `attention_universe.json` (or persist the top-100 list in the refresh script) so ranking is live; planner to decide owner.
- Profile per-day series at 100 refs x all sources; cache if slow.
- S-E1 can consume `series[].value` null as a gap.

## 11 Context cost
Opened beyond the entry set: baskets_view, attention types/store/registry/coingecko (first 2,800 B), screener router, mindshare router test, main.py lines, plus the small greps in heading 8. Roughly 60k tokens total.
