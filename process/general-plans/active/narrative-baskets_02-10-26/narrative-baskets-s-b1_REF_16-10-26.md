ROLE: WORKER
Direct lane: no spawning; read only below.

Task: T69 (P5 S-B1) - attention store, Wikipedia and CoinGecko sources. RT2. Base origin/main. Branch: claude/t69-p5-s-b1-attention-store
Acceptance: sections "Owner decisions" bullet D-3, "Common rules", "S-B1" of process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets_PLAN_16-10-26.md, read from main (owner merged PR #97 before dispatch). ACs: AC-34, AC-24.
Owned: api/data/attention/{__init__,types,store,registry,wikipedia,coingecko_attention}.py, api/data/attention/probe_records.json ({}), api/data/wiki_articles.json, api/scripts/refresh_attention.py, api/tests/data/attention/ (with __init__.py and fixtures), api/tests/scripts/test_refresh_attention.py.
Forbidden: CLAUDE.md, AGENTS.md, .claude/, .github/, process/ (except the report), any .env/key file, api/main.py, existing adapters (wrap coingecko_adapter, never edit), api/data/cache.py, api/data/pytrends_adapter.py, api/scripts/snapshot_narrative.py, api/analytics/**, api/routers/**, web/**, slice A files.
Read (hard cap 36,000 B for EVERYTHING; plan says 31,347), stop at each cap, over = needs_input:
 1. CLAUDE.md 13,443 B
 2. plan ranges 4,800 (Common rules 2,100; S-B1 2,700; D-3 bullet)
 3. code 9,104: api/data/coingecko_adapter.py (3,804); api/data/cache.py CACHE_ROOT + atomic write helper (1,800 cap); api/scripts/refresh_cache.py arg parsing + exit codes (2,000 cap); api/tests/conftest.py isolated_cache fixture (1,500 cap)
Unread: everything else (SPEC, all-context, other adapters).
Rules: store keeps only completed UTC days (date < today), one row per day, first observation wins, path resolved at call time under cache.CACHE_ROOT/attention; refresh_attention.py is the only fetcher (--dry-run writes nothing; exit 0/2/1; per-source isolation); a source without a row in probe_records.json reads as not-probed. If coingecko_adapter lacks the top-100 markets call, add a thin fetcher inside coingecko_attention.py.
Red-first: write the fixture tests (ok, empty, short history, HTTP error, rate limit, store round trip, completed-days-only, first-wins, tmp_path isolation, dry run writes nothing); commit them failing; record the red count.
Baselines: measure on untouched origin/main, no hard-coding: API pytest total (passed/skipped/deselected). Web untouched: do not run vitest or e2e; git diff origin/main -- web must be empty (say so in heading 7).
Gates (commands per process/context/tests/all-tests.md): UV_FROZEN=1 uv run --project api pytest api/ -q; protected tests from plan Common rules green and git diff --stat origin/main on them empty; git diff --check origin/main...HEAD; git diff origin/main...HEAD empty for forbidden files; real cache and watchlist.json untouched (size, mtime, sha256 before/after). After: baseline + new tests (state it).
Must NOT: put secrets or keys in files, commits, logs; make live network or provider calls in tests (fixtures only); call X or any real API; print any key; edit files outside Owned; monkeypatch.undo() with isolated_cache; run refresh_attention.py live.
Cap 15 USD; ask at 7 (needs_input). needs_input means STOP. One draft PR against main; never merge; after the report stop, do not wait on CI. Commits on your branch only. ASCII.
Report: process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-s-b1_REPORT_16-10-26.md
Headings (11): 1 Task ID, 2 Outcome, 3 Summary (with a "Known limits" bullet), 4 Files changed, 5 Commits, 6 Tests run (cmd, result, UTC, SHA, red count, spend), 7 Tests NOT run, 8 Deviations, 9 Blockers, 10 Follow-up, 11 Context cost.
