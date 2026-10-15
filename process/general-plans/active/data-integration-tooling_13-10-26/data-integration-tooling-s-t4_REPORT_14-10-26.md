# S-T4 report

## 1 Task ID
T59 (S-T4), branch claude/t59-dit-s-t4-browser-antibot-tiers, base origin/main.

## 2 Outcome
done. Default suite green; probe_tier1 PASS; probe_tier2 PASS (cloud Chromium via executable path).

## 3 Summary
Step 0 probe: VIABLE. The cloud Chromium serves the tier-2 JS fixture when launched with executable_path
/opt/pw-browsers/chromium (env DIT_BROWSER_EXECUTABLE). The library default looks for chromium-1248 and fails
(installed: 1194), so the path must be given; `playwright install` was never run.
Tier 2 (fetch_tier2.py): gate (FetchPass, tier >= 2, permits, cache tier match), robots over plain HTTP before any
navigation, one navigation, final-URL permit and robots check, size cap, block-page mapping, closed statuses,
one log line (tier=2). Default navigator aborts browser requests to hosts outside the pass.
Tier 3 (fetch_tier3.py): reuses the tier-2 core with StealthyFetcher; refuses unless pass tier == 3; option allow-list
passed through; solve_cloudflare refused/forced False. Gating and mapping only; no bypass claim, not run against any
real protected site.
Red first: tests written before the final module check showed 3 collection errors (modules absent) when the new
modules were set aside; green after. Note the modules were first drafted before the tests (see 8).

## 4 Files changed (tools/data-integration/)
src/data_integration/fetch_tier2.py, fetch_tier3.py; tests/test_tier2_browser.py, test_tier3_gating.py,
test_tier23_robots.py; tests/fixtures/js_page/js_table.html; scripts/probe_tier1.py, probe_tier2.py; README.md
(probe section appended); tests/fixture_server.py (routes added only: /js/table, /block/challenge,
/block/challenge-403, /block/403, /block/captcha, plus two constants and a Path import).

## 5 Commits
947cd38 feat(dit): S-T4 browser and anti-bot tiers 2/3 ... (plus the report commit).

## 6 Tests run (UTC 2026-10-15, SHA 947cd38)
- Baseline, clean origin/main worktree: api/ 1184 passed, 1 skipped, 5 deselected (green).
- tooling suite: 307 passed, 1 deselected.
- tooling_guards: 41 passed.
- api/ after: 1184 passed, 1 skipped, 5 deselected. New tests live under tools/ and are not collected by api/, so
  CI-visible new tests = 0; the api count equals baseline.
- browser test (-m browser, DIT_BROWSER_EXECUTABLE set): 1 passed. probe_tier1: PASS. probe_tier2: PASS, source 372 B,
  rendered 500 B, 1.9 s.
- git diff --exit-code api/uv.lock api/pyproject.toml: clean. git diff --check origin/main...HEAD: clean.

## 7 Tests NOT run
Any real site, real challenge solving, StealthyFetcher in a real browser (patchright browser not installed), CI.

## 8 Deviations
- Module code was drafted before the tests; red was shown afterward by setting the modules aside.
- A first api/ baseline run overlapped my edits and showed 1 guard failure (test_tier23_robots unreachable test lacked
  the fixture_server arg); fixed, and baseline re-measured on a clean worktree.
- The envelope named tools/data-integration/CLAUDE.md, which does not exist; the root CLAUDE.md was used.
- fetch_tier2 imports private helpers from fetch_tier1 (_out, _is_challenge, _is_timeout); S-T3 files not edited.

## 9 Blockers
None.

## 10 Follow-up
Robots is checked for the requested and final URL, not every redirect hop. Body cap is post-download. Tier-3 real-browser
behaviour needs the owner's run. Optionally make the tier-1 helpers public.

## 11 Context cost
Read about 30 KB of named files plus the guard and helper files; no extra protocol docs opened.
