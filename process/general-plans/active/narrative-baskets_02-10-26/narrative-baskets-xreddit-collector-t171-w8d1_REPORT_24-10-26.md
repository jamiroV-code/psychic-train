# T171 report: W8d1 X pure core for twscrape, including the account-pool logic (24-10-26)

## 1 Task ID

T171, slice W8d1 "X pure core for twscrape (incl. account-pool logic)". Worker session. Branch
`claude/t171-w8d1-x-core`, created from W8b (`claude/t140-w8b-collector-core`, PR #161, head `691c923`). #161 has
since been squash-merged into `main`, and PR #173 targets `main`. `origin/main` was merged into the branch twice
with merge commits, no rebase: first `833340a`, then on 26-10 the second merge. In the second merge, three
add/add conflicts (`web_queries.py`, `attention_queries.json`, `test_pc_collector_guards.py`) were resolved to this
branch, because main's copies were byte-identical to the W8b base `691c923`. The PR diff against `main` is now
exactly the 15 W8d1 files. Approval: the owner's
ENTER EXECUTE MODE W8d1 of 24-10-26, relayed in the envelope.

## 2 Outcome

DONE, with the interpretations listed in heading 8 and the open questions in heading 9. All code is pure logic
plus fakes. Nothing from twscrape, curl_cffi, httpx or any other network library is imported, and no network
call is made. `api/pyproject.toml`, `api/uv.lock` and `.github/` are untouched.

## 3 Summary

Six new pure modules under `api/data/attention/`, as the PLAN's W8d1 file list asks:

- `x_window.py` (AC42): the query builder for both window syntaxes (`since_time:/until_time:` epochs, or
  `since:D until:D+1` with until exclusive), the `lang:` policy (empty means any), the query-side
  `-filter:replies -filter:retweets`, the coin terms (cashtag first), the timestamp filter to [D, D+1) UTC,
  Latest as the only product, and the paging stop conditions (window start, sample N, page cap).
- `x_filters.py` (AC43, AC44): the record types `Tweet`, `XUser` and `Coin` (W8d2 maps the library's objects onto
  them), and the post-filters in a fixed order with one exclusion reason per tweet: not_in_window, retweet,
  reply, lang, placeholder, protected, young_account, low_followers, cashtag_spam, no_coin_match,
  name_only_no_match, duplicate_text, author_cap. Cashtags are matched without `$` and case-folded. For the
  `name_only` tickers (ETC, LINK, NEAR, HYPE, PI, PUMP, GT, CC) the bare ticker word never matches. Also unique
  authors, top-author share, the log1p engagement sum (views not in it), the median of the views that exist
  (a missing view count is never 0), and `read_age_hours`.
- `x_density.py` (AC42, AC54): the read-sample value. N counts raw entries READ, k counts tweets COUNTED, and the
  span runs from the window end to the oldest READ tweet, with a floor of 0.25 h. The flags are `capped` and
  `pagecap`. A coin-day is missing, never 0, when neither the window start, N nor the page-cap minimum is
  reached. `summarize` runs the filters and the density for one attempt.
- `x_raw.py` (AC45, AC54): raw pages are stored gzipped under the cache at
  `attention/xsearch_raw/<date>/<SYMBOL>/r<run>_a<attempt>_p<page>.json.gz`. Each page carries `collected_at`,
  the parser and reader versions, the entry ids, the retries and the two rate-limit numbers. All other header
  values are dropped, and keys that could hold a cookie or token are removed from the body. Also: retention
  that deletes date folders only, a completion manifest, and `reparse`, which rebuilds the X evidence row from
  the raw pages. The live unit builds its row through `reparse` too, so a re-parse with the same parser gives
  the same row by construction. X evidence rows are first-wins per (date, parser version), so a new parser
  version adds a row. `mark_suspect` flags an account's stored rows with `suspect_since`.
- `x_reader.py` (AC41, AC46, AC53-AC55):
  - The pin, held as data only: `TWSCRAPE_PINNED_COMMIT = 63f61a518e576ea5c132f1156c03dda0520d76c1`, the package
    name and repo URL, and `CURL_CFFI_PIN 0.16.3`.
  - The one-account `XReader` Protocol (design A), plus `RawPage`, `PoolRow` and `ReaderFailure`. A failure
    keeps only its abort class, never the response text.
  - `no_account_cause`, which reads the cause of a NoAccountError from the pool row: inactive, a future
    `SearchTimeline` lock, or a server error.
  - The code-to-alert mapping, `fallback_decision`, `parse_drop`, `env_problems` (a pure check over a dict of
    environment variables) and `FakeXReader`.
  - Per the owner decision relayed by the planner (T179, SPEC rule 19, AC46 and AC53 amended on PR #167), the
    fallback is triggered by `Blocked by Cloudflare` OR `Blocked by HTML` on the default backend. This replaces
    the envelope line "HTML blocks do NOT trigger the fallback". The trigger still needs the flag (default
    false), gets one retry, and pauses the UTC day for the whole pool if still blocked. Each use is logged with
    reason `cloudflare_block` or `html_block`. The change was made red first (heading 5).
- `x_pool.py` (AC46, AC49-AC54):
  - Pool state persisted in `_pc_state/x_pool.json`, which survives a restart. A label that is not configured
    is refused.
  - Selection: least recently used, ties broken by registration order (not alphabetical), and every choice is
    logged by label.
  - Account states active, locked (until the next 00:00 UTC), inactive (with a persisted owner alert) and
    suspect. The day is paused only at zero usable accounts. The library's `reset_locks` is never called.
  - `run_unit` keeps one account per unit end to end. It restarts once on another account after a ban, logout
    or lock, discards the aborted tweets and still counts their reads. A second failure gives `account_failed`.
  - Budget and spacing are global through the one shared `PcSource`.
  - Cloudflare and HTML blocks, including the one-retry fallback hook for the separate curl process, are
    logged in the evidence and in the pool health. The drift stop triggers after 3 failures and the parse-drop
    stop on `layout_changed`.
  - `run_daily_canary` runs before any unit on the least recently canaried accounts, three when three or more
    are usable. It uses the same query and the same last complete hour for each account, with 25 percent
    tolerance and 0.6 overlap measured on the smaller set. It has a majority rule for three and the
    minimum-results gate, and it skips the comparison for a single account with a note in the health payload.

Config: the 8 PLAN keys and the 5 further SPEC keys the logic needs were added to `attention_queries.json`,
typed and validated in `web_queries.py`, with a per-coin `x_lang` override (heading 8 D2). Tooling guards were
extended in `test_pc_collector_guards.py` for:
- no twscrape, curl_cffi or network import in the six modules (with a planted-import self-test);
- no evasion vocabulary, no fixed-hour comparison and no logger use;
- no `reset_locks` and no `debug=` keyword (with a planted self-test);
- the pin held as data only, and absent from the dependency files.

## 4 Files changed

| File | Change |
|---|---|
| `api/data/attention/x_window.py`, `x_filters.py`, `x_density.py`, `x_raw.py`, `x_reader.py`, `x_pool.py` | new |
| `api/data/attention/web_queries.py` | X keys (`X_DEFAULTS`, typed validation), per-coin `x_lang` |
| `api/data/attention_queries.json` | 13 X keys in `collector` |
| `api/tests/data/attention/test_x_window.py`, `test_x_filters.py`, `test_x_density.py`, `test_x_raw.py`, `test_x_reader.py` | new (73 tests) |
| `api/tests/tooling_guards/test_pc_collector_guards.py` | 5 W8d1 guard tests added |
| this report | new |

File-set check: `git diff --stat 691c923..HEAD` lists exactly these files. There are no edits to `api/pyproject.toml`,
`api/uv.lock`, `.github/` or any other W8b module (`density.py`, `pc_pace.py`, `web_evidence.py` and
`pc_adapter.py` were read and imported, not changed).

## 5 Commits

1. `1ef1197` test: red tests. All five new test files fail at import, and 4 of the 5 new guard tests fail; the
   planted-import self-test passes on the helper alone.
2. `6bcb6a4` feat: the implementation. Green.
3. `6469d16` style: a trailing blank line in `x_pool.py`.
4. `9475e94` test: boundary tests from the mutation check, and removal of an equivalent (dead) unit-wide drop
   check.
5. `6f40425` docs: this report.
6. `833340a` merge of `origin/main` (#161 not yet merged at that time).
7. Red: HTML block triggers the fallback (T179), and an inconclusive canary sits out its accounts (planner QA).
8. `f432b33` feat: green for 7.
9. `3ddfa89` docs: report update.
10. Merge of `origin/main` on 26-10 (#161, #166, #170 and #172 merged).
11. This report update (docs).

## 6 Tests run

- New files: `test_x_window` 9 functions (24 cases with the parametrized config test), `test_x_filters` 14,
  `test_x_density` 5, `test_x_raw` 7, `test_x_reader` 38. All pass.
- `api/tests/data/attention` + `api/tests/scripts` + `api/tests/tooling_guards`: 813 passed, 1 skipped.
- Full `uv run --project api pytest api -q` after the second main merge (26-10): 2302 passed, 0 failed, 1 skipped,
  5 deselected. Also on that tree: ruff on the touched files passes, `git diff --check` is clean, the secret scan,
  banned-name grep and guards are clean, and no logic changed, so there was no mutation re-run.
- Full `uv run --project api pytest api -q` on the merged tree at `f432b33`: 2242 passed, 0 failed, 1 skipped,
  5 deselected. On `origin/main` (`d968e44`, a separate worktree): 2028 passed, 1 skipped, 5 deselected. The +214
  is W8b's 118 tests (main does not have #161 yet) plus this slice's 96 (91 cases in the five new files plus 5
  guard tests). The earlier `test_weights_v2` failure came from the old base; it does not happen on main.
- Before the merge, at `9475e94` on the W8b base: 2084 passed, 1 failed (that `test_weights_v2` failure), 2
  skipped. The W8b base before any change had 1991 passed, 1 failed, 2 skipped.
- After the merge, `api/tests/data/attention`, `api/tests/scripts` and `api/tests/tooling_guards` together gave
  958 passed. The one failure,
  `analytics/attention/test_weights_v2.py::test_committed_frozen_snapshots_match_their_days_weights`, is
  pre-existing and unrelated to the X files.
- Mutation check, done by hand by applying mutants to the decision logic and running the five new test files:
  - First pass: 34 mutants, 29 killed and 5 survived. The survivors were the lock end 1 h early, the canary
    tolerance `>` changed to `>=`, the overlap divided by the larger set, "several entries" set to more than 2,
    and the unit-wide parse-drop check removed.
  - Four of the survivors were test gaps; boundary tests were added for each. The fifth was an equivalent mutant:
    a unit-wide rate above the threshold implies a page above it, so that check was dead code and was removed.
  - Second pass: 33 mutants, 33 killed, 0 survived.
  - Third pass, after the T179 and QA changes on the merged tree: 35 mutants, 35 killed. It added mutants for the
    HTML trigger, the inconclusive-canary lock, and the decision on whether any account is still usable.
  - Covered areas: selection, state machine and restarts, UTC-day lock, drift stop and reset, canary
    (tolerance, overlap, two-account rule, majority, account count, minimum results, gate before units), window
    and stop conditions, density (exact, floor, page cap), parse drop, fallback decision, NoAccountError cause,
    environment guard, budget accounting and author cap.
- Hygiene:
  - `git diff --check 691c923..HEAD` is clean.
  - Secret scan over the diff: the only hits are the planted test markers and the scrub key list.
  - The banned-name grep uses names built from split strings and finds no hit.
  - No-network-import grep: none.
  - `ruff check` on all new and changed files passes. The base already has 48 ruff findings elsewhere, so ruff is
    not a gate.

- T187 review fix round (26-10), on the tree with `origin/main` merged in again:
  - `pytest api`: 2321 passed, 0 failed, 1 skipped, 5 deselected.
  - 12 new test functions: 4 in density, 2 in window, 6 in reader. Red came first (17 failing), then green.
  - Mutation check on the changed logic and the reworded lines: 49 of 49 mutants killed (45 + 4).
  - Ruff, `git diff --check`, the secret scan and the banned-name grep are clean.

## 7 Tests NOT run

- Anything live: X is not reachable from the sandbox, and nothing from twscrape is installed.
- The owner probe P-X9 (AC48) is not run, so it is still open. Whichever window syntax X honours, the shape of
  `viewCount` and the cashtags, and the real `x-rate-limit-*` headers all stay UNVERIFIED.
- No CI result on this branch yet.
- AC41 parts left to W8d2: the pin, name and near-name guard, the installed-commit check and the optional
  dependency group.
- AC47 is all W8d2.
- AC52 health-line wiring and AC53 install and hash guards are W8d2 and W8e2.
- The engagement series is computed here but stored separately only once W8d2 wires it.

## 8 Deviations

Interpretations where the SPEC or PLAN was silent or ambiguous. Each one is small and listed so the planner can
overrule it.

- D1: Pool tests are in `test_x_reader.py`, because the PLAN file list has no `test_x_pool.py`.
- D2: The PLAN lists 8 config keys. I also added `x_unit_max_restarts` (1), `x_canary_tolerance` (0.25),
  `x_canary_min_overlap` (0.6), `x_parse_drop_threshold` (0.2) and `x_allow_curl_backend` (false), which are
  named by SPEC rules 18-19 and used by this logic. The X keys are required in the file, and the existing
  dataclass gets defaults so W8b callers are unchanged. `x_pool_size` and the labels are left to W8d2 (AC47).
- D3: When the window start is reached on the same page that brings the reads to N, the value is EXACT (k). The
  "capped otherwise" wording would use a span over 24 h and undercount.
- D4: A cashtag coin with no cashtag and no name match is excluded as `no_coin_match`, because A.1b lists only
  `name_only_no_match`.
- D5: Alert mapping for an inactive row. 32, a bare 403 (no text) and text without a code map to
  `x_login_required`; 88, 326 and any other code map to `x_account_suspended`. Both are owner-action alerts.
- D6: "Several" raw entries is 2 or more. The drop rate is checked per page (D-mutation note in heading 6).
- D7: Canary details (inconclusive case changed by the planner's QA decision, see heading 9):
  - One page per account. The result is the set of parsed tweet ids inside the last complete clock hour (the
    "fixed past hour", the same for every account; no fixed UTC hour, per the hour guard).
  - With three or more usable accounts, three are canaried. A suspect is an account that agrees with fewer than
    half of the others.
  - An inconclusive result (two equal-size results that disagree, or no majority) locks the canaried accounts
    for the rest of the UTC day. They are not flagged suspect and get no alert, and they are back the next day.
    The other usable accounts continue, with the canary marked passed and a health note. When no usable
    account is left (for example a two-account pool), the day pauses with reason `canary_disagree`, and the
    units are missing with no usable account.
  - My reading of the planner's "pause that account's use" for an inconclusive result: the accounts that were
    canaried are the ones that sit out the day.
  - A Cloudflare or HTML block during the canary pauses the day without the curl fallback.
  - Canary reads respect the global spacing and the global budget.
- D8: Account age is measured at tweet time, so a re-parse gives the same result whenever it runs.
- D9: A NoAccountError on an active row with no future lock (server error) leaves the coin-day missing with
  reason `failed`, and nothing restarts. Rule 18f lists only ban, logout or lock as restart causes.
- D10: Pool day pauses live in the pool state, not in `PcSource.warn`, whose owner-action pause would stop the
  whole source on one banned account. The W8e worker must check `XPool.is_paused()` and `PcSource.is_paused()`.
- D11: All pages of a unit carry the unit's start time as `collected_at`. The run id is that time in epoch
  seconds.
- D12: The environment guard also refuses lowercase proxy variables and `ALL_PROXY`, and it requires
  `TWS_RAISE_WHEN_NO_ACCOUNT=1` (rule 20b).
- D13: `reparse` uses the first completed run of a coin-day, matching the first-wins value.

- T187 fixes, from the planner's relay of the independent review (verdict MERGE-AFTER-FIXES: 3 Medium,
  6 Low):
  - M1: when every read tweet is at or after the window end, the coin-day is missing with
    `window_not_reached`, never a capped 0. Entries read that way never fill the sample, so paging continues
    to the page cap.
  - M2: the canary uses a fixed past hour, the last hour of the previous UTC day. The date form
    `since:D-1 until:D` reads it newest first, so `x_window_syntax="date"` no longer fails `empty_results`.
  - M3: an empty page, or None (rule 20b), is an exhausted cursor. It counts as a complete read of the window,
    so k is exact even below N_min. A 0 is kept only with the day's canary (`canary_ok`, also stored in the
    completion manifest); otherwise it is missing with `zero_without_canary`. The reasons `none_result` and
    `empty_page` no longer exist.
  - M10: a boundary test for the page cap at `n_read == x_sample_min`.
  - Low findings: their text was not in the relay or on the PR, so I did not fix them.

## 9 Blockers

Envelope owner questions answered with the SPEC's recommended value:

- Q21: twscrape primary, API Anything not built.
- Q22: `x_lang` defaults to `en`, with a per-coin override; empty means any language.
- Q23: account age 30 days, 10 followers, protected and placeholder users excluded, author cap 3, more than 5
  cashtags excluded.
- Q28: design A.
- Q29: decided by the owner as "both OS". W8d1 has no platform code; the wheel hashes are W8d2's.

My questions QA-QE were decided by the planner on 24-10-26 (recorded as decided-by-planner):

- QA: an inconclusive canary sits the canaried accounts out for the day, and the units go missing, but not for
  the whole pool unless NO usable account remains (corrected in T190 round 2: the earlier "fewer than 2" wording
  was wrong; the planner's decision and the code are "pause only at 0 usable", pinned by a test: 1 usable
  continues, 0 usable pauses). Implemented as described in D7.
- QB: a bare 403 makes the account inactive with `x_login_required` and raises an alert. This was already the
  behaviour.
- QC: "several" means 2 or more. Already the behaviour.
- QD: `no_coin_match` is accepted. Already the behaviour.
- QE: the window start wins over N on the same page. Already the behaviour.

## 10 Follow-up

W8d2 needs to:
- wrap the library onto `XReader` (`search_raw` to `RawPage` with tweet-entry ids only, `parse_tweets` to
  `x_filters.Tweet`, `pool.get` to `PoolRow`, exception classes to `ReaderFailure` kinds);
- add the pin, name, near-name and installed-commit guards, the optional group, and the curl fallback process
  that `run_unit(fallback=...)` calls;
- call `env_problems(os.environ)` at start;
- store `xsearch_engagement`, and add the labels and `x_pool_size` config and the AC47 file checks.

W8e or W8e2 needs to:
- run the canary, then the units, honouring `XPool.is_paused()`, `XPool.health()` and `x_raw.prune`;
- commit values via `web_evidence.commit_day` with `canary_ok` from the canary.

The PR already targets `main`; #161 is merged.

## 11 Context and cost

Read: CLAUDE.md, the envelope, the PLAN's W8d1 section and AC rows (git show on
`claude/t163-reddit-engagement-spec`), SPEC rules 17-20, Annex A.1 and A.1b, AC41-AC55 and Q21-Q29 (same ref),
and the W8a2 report sections 9.3 and 10 (C1-C11). W8b modules were opened as needed: `density.py`, `pc_pace.py`,
`web_evidence.py`, `web_queries.py`, `pc_adapter.py`, `test_pc_pace.py` and `test_web_queries.py` (fixtures),
`test_pc_collector_guards.py` (extended), and `conftest.py`. Extra docs opened beyond the envelope:
`process/context/tests/all-tests.md` (a grep for the pytest command only) and the T140 report (heading layout
only). The session cannot meter USD; no stop threshold was signalled.

## Round 2 (T190)

Fresh worker, fix round 2 on the independent review T187 (re-check at `40f9068`). `origin/main` merged first
(merge commit, no rebase). Red commit first (46 failing), then green. The PR diff against `main` is still exactly
the 15 W8d1 files (14 code and test files plus this report).

Fixes:

- B-1 (blocker), stalled cursor. `x_window.cursor_end` decides when a page ends the cursor. An empty page or None
  counts as EXHAUSTED only when the last non-empty page was SHORT (fewer than `PAGE_ENTRIES` = 20 entries) or
  there was no earlier page. An empty page after a FULL page, or a page that repeats an id already read, is
  `cursor_stalled`. A stall is never exact: the value is capped `24 * k / span` when `n_read >= N_min`, else the
  unit is missing with `cursor_stalled`. The repeated page still counts against the read budget but is not
  counted twice. `x_raw.reparse` applies the same rule.
- M-A (medium), canary gate. The pool now records the LABELS of the accounts that passed today's canary
  (`canary_labels`, persisted; a state file from before this change loads with none).
  - An inconclusive canary passes no account, and a suspect account does not pass.
  - Planner decision after round 2 (quality first): EVERY stored value (exact, capped, window start, zero)
    needs the unit's account in that set, else the unit is missing with `account_not_canaried` and nothing else
    is computed. This replaces `zero_without_canary`, which became unreachable and was removed.
  - The unit's `canary_ok` is written to `_complete.json` and to the X row. The re-parse uses that recorded
    value and is never forced to True, so N9 is killed.
- L1, curl retry (planner decision after round 2, SPEC rule 19). ONE curl retry per UTC day for the whole pool,
  canary and units together (`XPool.curl_used_today`, from the persisted last-use time). The next Cloudflare or
  HTML block anywhere pauses the UTC day for the pool, with reason `cloudflare_block` or `html_block` by the
  block's kind. Every unit still tries the default backend first while the day is not paused (AC53).
- L2, canary blocks. A block inside the canary goes through the same `_on_block` / `fallback_decision` path:
  same flag, the same pool-wide daily retry, still blocked pauses the day.
- L3, parse drop. The drop-RATE test applies only to pages with at least 10 entries
  (`PARSE_DROP_RATE_MIN_ENTRIES`). "Several entries (2 or more), zero parsed" still stops X. A drop on a smaller
  page (`small_page_drop`) makes the unit missing with `drift` and counts toward the 3-failure `layout_changed`
  streak.
- L4, scrub by value. `x_raw.scrub(body, names)` replaces the account's real screen names and ids with its label
  anywhere in the body: whole tokens, case-insensitive, nested text, and integer ids. The names come from the
  reader's `account_names` (a new `XReader` attribute that the W8d2 wrapper fills in).
- L5, oldest read. `RawPage.entry_times`, archived as `entry_times`, carries the raw entries' own timestamps when
  the wrapper can read them. The oldest read is the older of those and the oldest parsed tweet
  (`x_density.oldest_read`). The bias that remains when only parsed tweets are available (span short, capped
  value high) is documented in the `x_density` docstring. The parse-drop guard bounds it to 20 percent of a page
  of 10 or more entries.
- L6, pause wording. QA in heading 9 is corrected to "pause only when no usable account remains". The code was
  already right; a test now pins it: 1 usable continues, 0 usable pauses. The SPEC has no "fewer than 2"
  wording: rule 18(d) and AC46/AC49 already say "zero usable accounts".

Test fixture changes, made in the green commit so the existing tests fit the new rules:

- `pass_canary` now passes labels (all accounts by default).
- The `x_raw` test manifest helper now records `canary_ok` True, as every real completed unit does.
- The old zero-canary density test became the "every value needs the canary" test. The round-1 curl test now
  expects the second unit's block to pause the day with no second retry, and the next UTC day to get a new
  retry.
- The `short_result` case used the same page object three times. Under B-1 that is repeated ids, which is a
  stall, so the case now uses three distinct short pages.

Tests:

- 22 new test functions: 15 in reader, 3 in density, 3 in raw, 1 in window. The planner-answer round committed
  its failing tests first (`cbab49e`, 5 failing).
- `pytest api/tests/data/attention api/tests/scripts api/tests/tooling_guards`: 1039 passed, 0 failed.
- Full `pytest api`: 2342 passed, 0 failed, 1 skipped, 5 deselected. `origin/main` (separate worktree): 2213
  passed, 1 skipped, 5 deselected. The +129 are the W8d1 tests (2321 at round 1 plus the 21 new ones).
- After the planner answers and a further `origin/main` merge (main brought 40 new tests of its own):
  `pytest api` 2383 passed, 0 failed, 1 skipped, 5 deselected; attention+scripts+tooling_guards 1078 passed.
- Mutation check on all changed logic, by hand (mutant applied, `tests/data/attention` run): 28 mutants.
  - First pass: 23 killed and 5 survived. The survivors were the token boundary in scrub, the pool ignoring the
    raw oldest time, canary labels kept from another day, the re-parse not tracking seen ids, and the legacy
    state default.
  - Each survivor was a test gap, so a test was added for each.
  - Re-run: 28 of 28 killed. N9 (re-parse forces `canary_ok` True) is M8 and is killed.
  - After the planner answers, the mutants were updated to the new code and two were added: the canary gate
    moved after the computation, and the curl use not recorded. 30 of 30 killed, N9 included.
- Hygiene: `git diff --check`, the secret scan over the diff, and the no-network-import grep are clean. The
  banned-name guard tests pass.
- Ruff on the touched files: no new findings beyond the base's existing UP017 and I001 style findings. Those
  match the files' existing `timezone.utc` idiom and are not a gate. Ruff's C408 and UP034 findings in the new
  tests were fixed.

Not provable here: live X (P-X9 belongs to the owner).

Open questions: none. The L1 and M-A questions were answered by the planner and applied as above.
