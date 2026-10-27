# T210 W8c Reddit connector: worker report (27-10-26)

## 1 Task ID
T210 = PLAN slice W8c "Reddit connector" (plain HTTP on the public `search.rss` feeds, item ledger, mention metrics). Branch `claude/t210-w8c-reddit-web` from `main` `fa0f5e6`. One draft PR to main, not merged.

## 2 Outcome
done (live Reddit unproven here by design: owner probes in heading 8)

## 3 Summary
- `reddit_web.py`: one `search.rss` request per coin over the 12-subreddit set (`sort=new`, `restrict_sr=1`, `limit=100`, `t` from `reddit_search_time_filter`, default `week`); the single honest UA from `web_queries.HONEST_USER_AGENT`; no JSON endpoint, no redirects, no proxy (`trust_env=False`). Atom parser rejects DOCTYPE/ENTITY, HTML, non-Atom roots and bodies above `MAX_BODY_BYTES` (2 MB, checked while streaming and again before parsing). 403, other non-200 non-5xx, redirect, HTML or a rejected body = `reddit_blocked`, 429 = `rate_limited`: pause for the rest of the UTC day, no retry. 5xx or a network error = `offline`: that coin-day is missing, no pause. A.2 counting (exact / capped density / missing `day_not_reached`, `below_sample_min`, `empty_feed`), stored only via `web_evidence.commit_day` under `reddit_web`. Baseline pacing spreads requests at max(60-120 s, 24 h / coins) within the 250-request budget; degraded mode runs at 60-120 s within 150. Completeness file per day (attempted, fetched, missing, reasons, capped, `budget_cut`, requests, newest entry, `collected_at`, per-coin record).
- `reddit_items.py`: ledger keyed by Reddit id (`t3_`/`t1_`), one file per created UTC day. The first sighting is kept and later sightings only merge matched coins. The author hash is an HMAC-SHA256 under a salt kept outside the repo (`SCREENER_REDDIT_SALT_FILE` or `~/.screener-reddit-salt`; a path inside the repo is refused). Usernames are never stored or logged; the parser hands on only the hash.
- `reddit_metrics.py` (pure): matching (cashtag, name, bare upper-case ticker unless `name_only`); author cap 3; unique authors; low-volume K=3 (missing change); log1p engagement (posts add num_comments); controversy (ratio < 0.3 and votes ≥ 10); deleted-later removal.
- Config keys, `name_only` on the 8 coins, probe `--source reddit --feed-depth / --compare-scope`, and the guard over the explicit Reddit file list.

## 4 Files changed
New: `api/data/attention/reddit_web.py`, `reddit_items.py`, `reddit_metrics.py`; `api/tests/data/attention/test_reddit_web.py` (38), `test_reddit_items.py` (8), `test_reddit_metrics.py` (14); `api/tests/tooling_guards/test_reddit_collector_guards.py` (7).
Edited: `api/data/attention/web_queries.py` (new keys, `name_only` flag), `api/data/attention_queries.json`, `api/scripts/probe_pc_sources.py` (Reddit modes), `api/tests/scripts/test_probe_pc_sources.py` (+4 tests, one test switched to `--stream-status`), `api/tests/data/attention/test_web_queries.py` (locked budget 150 -> 250).
Plus this report. No `.github/`, `api/pyproject.toml`, `uv.lock` or cache files.

## 5 Commits
Branch `claude/t210-w8c-reddit-web`:
- `a1697b2` test (red): named red-first tests and the guard
- `c930e92` feat (green): modules, config, probe; test-harness fixes (heading 8)
- the next commit: boundary tests from the mutation check
- the report commit (head sha in the PR)

## 6 Tests run
All runs on 27-10-26 between 13:30 and 14:40Z, in this sandbox:
- Red at `a1697b2`: the 3 new test modules fail at import (modules absent); probe and guard: 5 failed, 12 passed.
- `uv run --project api pytest api/tests/data/attention api/tests/scripts api/tests/tooling_guards -q`: 1448 passed (post-mutation-tests commit).
- `uv run --project api pytest api -q` at `c930e92`: 2765 passed, 1 skipped, 5 deselected. Main `fa0f5e6`: 2697 passed, 1 skipped, 5 deselected. Delta +68, which equals the new tests then; +3 more were added after this run.
- ruff check on every touched file: All checks passed. Main baseline over the wider set: 37 pre-existing findings, none in the touched files.
- `git diff --check origin/main...HEAD`: clean. Secret scan of the diff: only `import secrets`, the planted-secret test strings and the word "GateToken". Banned-name grep: 0. File set: only the W8c list plus the edits named in heading 4.
- Mutation check (49 hand-made mutants; scratch script, not committed). Killed: matching 11/11, metrics 6/6, density 6/7, completeness 5/5, pacing 9/10, pause 10/10. After the first round 5 survived. Three were real gaps (window-start `<` vs `<=`, published vs updated time, the stream-level size cap) and got tests in the boundary-tests commit. Final: 47 killed, 2 survived:
  - `zero canary always ok` (`canary_ok=out.entries > 0` -> `True`): equivalent, because an exact result needs an entry older than the window, so entries > 0 always holds there.
  - `host stop >` (`due >= stop_at` -> `>`): a float-equality edge, not reachable with random spacing.

## 7 Tests NOT run
- Live Reddit (no network allowed in this sandbox; fake clients via `httpx.MockTransport` only). Feed depth, rate limit, the `+` multi-subreddit path, which `t` values are honoured, and the real content-type are UNVERIFIED (owner probes below).
- No CI run observed yet (draft PR).

## 8 Deviations
- `web_queries.py` and `test_web_queries.py` are outside the literal W8c file list. The config keys cannot exist without the validator, and SPEC rule 15 sets `reddit_daily_request_budget` to 250 with `reddit_degraded_request_budget` 150, while the W8b test pinned 150. The new keys (`reddit_degraded_request_budget`, `reddit_author_cap`, `reddit_min_mentions`, `reddit_search_time_filter`) are optional in the file, so the defaults apply when absent; a degraded budget above the daily budget is rejected.
- `reddit_web.reddit_source` resets `PcSource._s["effective"]` (a private field). `PcSource` clamps a stored effective budget to the configured one, so a day first run degraded (150) would otherwise cap the baseline at 150. Proposed fix in W8e: `pc_pace` lets non-adaptive sources follow the configured budget.
- `reddit_web` adds a `logging.Filter` to the `httpx` logger that drops request lines whose URL is on reddit.com. Found by the planted-secrets test: httpx logs every full URL at INFO, which breaks AC25's rule that logs hold only class and status.
- Test-harness fixes between the red and green commits:
  - The `q` fixture now uses `attention_cache`. The first red run wrote a git-ignored `api/data/cache/attention/_pc_state/reddit_web.json`, which I deleted.
  - `unit()` resets the state file.
  - Ruff fixes.
  - The guard also allows `urllib.parse` in HTTP modules.
- Owner probes, PowerShell from the repo root. Each prints counts and statuses only:
  - P-R6 (now): `$ua="attention-probe/0.1"; foreach ($u in @("https://www.reddit.com/r/CryptoCurrency/new/.rss","https://www.reddit.com/r/CryptoCurrency/new/.rss?limit=100","https://www.reddit.com/r/CryptoCurrency/search.rss?q=solana&restrict_sr=1&sort=new&limit=100")) { $x=[xml](curl.exe -s -A $ua $u); "{0} entries, newest {1}, oldest {2}" -f $x.feed.entry.Count, $x.feed.entry[0].updated, $x.feed.entry[-1].updated; Start-Sleep -Seconds 60 }`
  - P-R6 variant (t=week): `curl.exe -s -A "attention-probe/0.1" -o NUL -w "%{http_code} %{size_download}\n" "https://www.reddit.com/r/CryptoCurrency/search.rss?q=solana&restrict_sr=1&sort=new&t=week&limit=100"`
  - P-R3: `1..10 | ForEach-Object { curl.exe -s -A "attention-probe/0.1" -o NUL -w "%{http_code}\n" "https://www.reddit.com/r/CryptoCurrency/search.rss?q=solana&restrict_sr=1&sort=new"; Start-Sleep -Seconds 60 }` (Ctrl+C at the first 403 or 429)
  - P-R4: `curl.exe -s -A "attention-probe/0.1" -o NUL -w "%{http_code} %{size_download}\n" "https://www.reddit.com/r/CryptoCurrency+CryptoMarkets+altcoin/search.rss?q=solana&restrict_sr=1&sort=new"`
  - P-R2 (after the build): `uv run --project api python -m api.scripts.probe_pc_sources --source reddit --symbol SOL --feed-depth`
  - P-R5 (after the build): `uv run --project api python -m api.scripts.probe_pc_sources --source reddit --symbol SOL --compare-scope`
  - Also useful: `curl.exe -s -A "attention-probe/0.1" -o NUL -w "%{http_code} %{content_type}\n" "https://www.reddit.com/r/CryptoCurrency/search.rss?q=solana&restrict_sr=1&sort=new"`. It checks the content type: a body served as HTML is treated as a block.

## 9 Blockers
None. Open questions:
- Q-a: the PLAN test name `..._t_day_...` against `t=week` (T163 addendum and envelope). The test keeps the PLAN name and checks the URL with whatever `t` the config sets; the default stays `week`.
- Q-b: for `name_only` coins the search query uses the full name only (`"Chainlink"`, no bare `LINK`). The A.2 `reddit_web` value counts every search-result entry in the window, not only entries that pass mention matching; the matched coins go to the ledger. Should the value count matched entries only?
- Q-c: `cashtag_only` (an X flag) is not applied to Reddit matching. Names like Cosmos, Avalanche or Jupiter therefore match as words.
- Q-d: A.2 is followed literally. A feed with fewer than 100 entries whose oldest entry is inside D is not treated as exhaustive (the coin-day is `below_sample_min` or `day_not_reached`), even though with `t=week` such a feed is complete. Should a short feed count as reaching the window start?
- Q-e: under the W8b AC3 zero rule, a zero needs a trailing median below 5. A coin with no stored history therefore never stores 0 (`zero_unconfirmed`), so an always-quiet coin stays missing.
- Registry: T210 W8c done, waiting on the owner probes and review.

## 10 Follow-up
- W8e: non-adaptive budget in `pc_pace` (remove the private reset); the worker picks the baseline or degraded mode and the queue (`pc_pace.build_queue`); the ledger needs `load_salt(create=True)` and `Ledger(AuthorHasher(salt))`.
- W8c2: comments and new feeds reuse `parse_feed`, `Ledger`, `matched_coins`; probe `--stream-status`.
- W8c3: `Item` already carries score, num_comments, upvote_ratio, ups and the removal fields.

## 11 Context cost
Loaded: CLAUDE.md, the envelope, PLAN W8c section and slice table, SPEC rules 10/13-16, A.1, A.2, A.2b, AC22-AC37, W8b modules (density, pc_pace, web_evidence, web_queries, pc_adapter, probe), the W8b guard, test_web_queries / test_probe_pc_sources headers, and parts of x_filters/x_density as a style reference. On demand: master-planner.md sections 6 and 9, all-tests.md (pytest command). Roughly 110k tokens. Tools: Bash, Read/Write/Edit, git; no subagents, no network to Reddit.
