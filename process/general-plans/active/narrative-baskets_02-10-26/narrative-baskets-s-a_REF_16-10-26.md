ROLE: WORKER
Direct lane: no spawning; read only below.

Task: T68 (P5 S-A) - baskets view over screener groups. RT2. Base origin/main. Branch: claude/t68-p5-s-a-baskets
Acceptance: sections "Owner decisions" bullet D-1, "Common rules", "S-A" of process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets_PLAN_16-10-26.md, read from main (owner merged PR #97 before dispatch), plus the AC-35 paragraph of narrative-baskets_SPEC-amendment_16-10-26.md. ACs: AC-35, AC-32, AC-27, AC-9.
Owned: api/data/baskets_view.py, api/models/baskets.py, api/routers/baskets.py, api/routers/watchlist.py, api/main.py (one include_router line), api/tests/data/test_baskets_view.py, api/tests/routers/test_baskets.py, api/tests/routers/test_watchlist_cascade.py, one assertion in api/tests/routers/test_watchlist.py::test_remove_coin.
Forbidden: CLAUDE.md, AGENTS.md, .claude/, .github/, process/ (except the report), any .env/key file, api/data/layout.py, api/data/watchlist.py, api/routers/layout.py, api/analytics/**, web/**, api/data/cache.py.
Read (hard cap 36,000 B for EVERYTHING; plan says 32,903), stop at each cap, over = needs_input:
 1. CLAUDE.md 13,443 B
 2. plan ranges 5,550 (Common rules 2,100; S-A 2,800; D-1 bullet; AC-35 650)
 3. code 9,910: api/data/layout.py constants, _reconcile, read_layout, place_coin (4,300 cap); api/routers/watchlist.py (2,310); api/main.py include lines (900 cap); api/tests/routers/test_layout.py head+fixtures (1,500 cap); api/tests/routers/test_watchlist.py test_remove_coin+client fixture (900 cap)
Unread: everything else (models/layout.py, watchlist.py store, SPEC, all-context).
First: git grep the tests for routes /api/narrative/baskets and for DELETE /api/watchlist response shape; a test that would break = needs_input.
Red-first: write test_baskets_view, test_baskets, test_watchlist_cascade (move, unassign, invalid id/symbol, unknown group, extra field, not-on-screener 404 with file bytes unchanged, add_coin keeps new coin in main, affected_baskets); commit them failing; record the red count.
Baselines: measure on untouched origin/main, no hard-coding: API pytest total (passed/skipped/deselected). Web untouched: do not run vitest or e2e; git diff origin/main -- web must be empty (say so in heading 7).
Gates (commands per process/context/tests/all-tests.md): UV_FROZEN=1 uv run --project api pytest api/ -q; protected tests from plan Common rules green; git diff --stat origin/main -- the protected paths empty; git diff --check origin/main...HEAD; git diff origin/main...HEAD empty for forbidden files; test run leaves real watchlist.json/layout.json/cache untouched (size, mtime, sha256 before/after). After: baseline + new tests (state it).
Must NOT: put secrets or keys in files, commits, logs; make live network or provider calls in tests; call X or any real API; print any key; edit files outside Owned; monkeypatch.undo() with isolated_cache.
Cap 15 USD; ask at 7 (needs_input). needs_input means STOP. One draft PR against main; never merge; after the report stop, do not wait on CI. Commits on your branch only. ASCII.
Report: process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-s-a_REPORT_16-10-26.md
Headings (11): 1 Task ID, 2 Outcome, 3 Summary (with a "Known limits" bullet), 4 Files changed, 5 Commits, 6 Tests run (cmd, result, UTC, SHA, red count, spend), 7 Tests NOT run, 8 Deviations, 9 Blockers, 10 Follow-up, 11 Context cost.
