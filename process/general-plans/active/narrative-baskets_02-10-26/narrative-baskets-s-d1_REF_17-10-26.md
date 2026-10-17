ROLE: WORKER
Direct lane: no spawning; read only below.

Task: T79 (P5 S-D1) - decouple the old verdict code. RT2. Base origin/main. Branch: claude/t79-p5-s-d1-decouple
Acceptance: process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets_PLAN_16-10-26.md lines 23-32 (Common rules) and 74-79 (S-D1). Goal: after D1 only api/routers/narrative.py and files D2 deletes import trigger or momentum. No deletion here (D2 deletes later).
First: run git grep -n "narrative.trigger\|narrative.momentum\|import trigger\|import momentum" -- api and compare with the plan's importer list. An importer outside the plan list and the owned files = needs_input (STOP).
Owned: api/analytics/narrative/history.py (own the constants MIN_AVAILABLE_SOURCES, BASE_TRUST_WEIGHT, REDUCED_SOURCE_TRUST_CAP locally; drop composite trust_weight), api/analytics/narrative/scoring.py (docstring only), api/scripts/seed_e2e_cache.py (build_narrative_fixture only: read narrative_categories.json through a small local helper, not trigger.load_seed_categories), api/tests/scripts/test_seed_narrative_fixture.py, api/tests/analytics/test_history.py (stop reading trigger constants; trust_weight asserts removed).
Forbidden: CLAUDE.md, AGENTS.md, .claude/, .github/, process/ (except the report), process/MASTER-PLAN.md, decisions.md, api/routers/narrative.py, trigger.py and momentum.py (read only), A-C files, web/**, api/data/cache.py, api/data/pytrends_adapter.py, api/scripts/snapshot_narrative.py, mapping.py, narrative_category_map.json, migrate_narrative_config.py, narrative_config.py, .env/key files.
Read (hard cap 36,000 B for EVERYTHING; est. 31,100), stop at each cap, over = needs_input:
 1. CLAUDE.md 13,443 B
 2. plan lines 23-32 (2,072) + 74-79 (1,813)
 3. code 11,500: history.py lines 1-30, 255-300, 410-420 (3,000 cap); trigger.py lines 28-42 and 69-78 (1,100 cap); seed_e2e_cache.py lines 383-420 (2,000 cap); test_seed_narrative_fixture.py lines 1-40 (1,613); api/tests/analytics/test_history.py lines 1-20, 70-110, 280-295 (2,000 cap)
Unread: everything else.
Rules: composite trust_weight column dropped from history output only if no live consumer reads it (git grep first; a consumer outside the list = needs_input); the history test that scans trigger.py text must still pass or be rewritten to the new fact (history does not import trigger). /history and /mindshare JSON stays otherwise unchanged.
Red-first: write failing tests (history.py and seed script do not import trigger or momentum; history constants are local; no trust_weight in composite); commit them failing; record red count.
Baselines: measure on untouched origin/main, no hard-coding: expect api 1402 passed/1 skipped/5 deselected. Web untouched: do not run vitest or e2e (vitest 472, e2e 84 expected unchanged); git diff origin/main -- web must be empty (say so in heading 7).
Gates (commands per process/context/tests/all-tests.md): UV_FROZEN=1 uv run --project api pytest api/ -q (baseline + new tests, state it); protected AC-25 tests green, unedited (git diff --stat origin/main empty on them); git diff --check origin/main...HEAD; forbidden-file diff empty; real cache untouched (size, mtime, sha256 before/after).
Must NOT: secrets, live network or provider calls; delete files; edit outside Owned; monkeypatch.undo() with isolated_cache.
Cap 15 USD; ask at 7 (needs_input). needs_input means STOP. One draft PR against main; never merge; after the report stop, do not wait on CI. ASCII.
Report: process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-s-d1_REPORT_17-10-26.md
Headings (11): 1 Task ID, 2 Outcome, 3 Summary (with a "Known limits" bullet), 4 Files changed, 5 Commits, 6 Tests run (cmd, result, UTC, SHA, red count, spend), 7 Tests NOT run, 8 Deviations, 9 Blockers, 10 Follow-up, 11 Context cost.
