# T196 REPORT: Trends term-group tester (`probe_trends --try`)

## 1 Task ID

T196, stage 1 of the Trends term-GROUP work: a read-only term tester inside the owner's probe.
Branch `claude/t196-term-tester`, one draft PR to `main`.

## 2 Outcome

done (fake clients only; real Google results are the owner's run).

## 3 Summary

- New `probe_trends --try 'SYM=term1|term2|...'` (repeatable, at most 12 groups, 1 to 5 terms each; topic ids or
  free text). Each group is ONE request over the daily run's explicit 100-day range ending yesterday, so all terms
  of a group share one 0-100 scale.
- New pure module `api/data/attention/trends_groups.py` (no network, no pandas, no store): group sum, per-term
  stats and shares, the daily usable rule (`trends.interest_verdict`, same constants), rising measure, one-term
  spike, pairwise smoothed correlation, volume identity hint, clean-rising verdict, ranking, and the fail-closed
  frame check (same checks as `fetch_alone` plus exactly 100 rows).
- Breaker: stop at the first HTTP 429 or after 3 failed requests in a row (exit 4, never a retry); Ctrl-C prints
  the partial summary (exit 130). Exit 0 / 1 / 2 / 3 as before. 3 s + up to 1 s jitter between requests.
- Prints numbers only; an error is its class and HTTP status, a bad frame its reason class. Writes nothing.
- `--alone` and the default mode are unchanged; the existing test file is untouched and green.

## 4 Files changed

- `api/data/attention/trends_groups.py` (new, pure metrics)
- `api/scripts/probe_trends.py` (`--try` mode, docstring)
- `api/tests/data/attention/test_trends_groups.py` (new)
- `api/tests/scripts/test_probe_trends_try.py` (new)
- this report

`trends_cli_common.py` was not needed. No `.github/`, pyproject, uv.lock, data, cache or keyword-file edit.

## 5 Commits

Branch `claude/t196-term-tester` from `main` @ `27d0a2d`:

- `d322dc0` test(T196): red tests (collection fails: module missing)
- `b44b53f` feat(T196): `--try` term groups and `trends_groups` metrics (plus the mutation-kill tests)
- docs(T196): this report (head of the PR)

## 6 Tests run

All on the tree of `b44b53f` (plus this report), UTC 2026-10-26 ~21:20:

- `uv run --project api pytest api/tests/scripts api/tests/data/attention -q`: 925 passed.
- `uv run --project api pytest api -q`: 2325 passed, 1 skipped, 5 deselected. `main` @ `27d0a2d` (clean worktree):
  2253 passed, 1 skipped, 5 deselected. +72 = the new tests (38 metrics + 34 CLI); no test changed or lost.
- New files only: `pytest test_trends_groups.py test_probe_trends_try.py`: 72 passed; existing
  `test_probe_trends.py`: unchanged (0-line diff) and green.
- `ruff check` on the 4 touched Python files: all checks passed. `git diff --check main`: clean.
- Secret scan (key/secret/token/password/bearer patterns in the new code): no hit. Tests assert the sentinel
  secret, cookies, Authorization, response bodies and tracebacks never reach the output.
- File set vs main: exactly the 4 Python files above plus this report.
- No network import in the pure module: an AST test bans pytrends/requests/httpx/urllib/socket/http/pandas/store.

Mutation check (34 hand-written mutants on the module thresholds/comparisons, the frame checks, the ranking, the
CLI limits, the breaker, the jitter, the loader flag, the JSON filter and the exit codes; run against the three
probe test files): first pass 31 killed, 3 survived (`share > SPIKE_SHARE` -> `>=`, the floor at 0 in the per-term
increase, `corr < MOVES_ALONE_CORR` -> `<= -1`) plus one redundant `isprintable()` check (removed: the regex already
excludes control characters). Tests added for each; second pass 33/34, the survivor (JSON ignoring the usable
verdict) got a test; final pass **34 killed, 0 survived**.

## 7 Tests NOT run

- Any real Google request (envelope: no Google contact from this sandbox). Real terms, real scales and real
  correlations are only provable by the owner's run.
- The identity line against a real stored volume series: the test uses a synthetic store reader; the default reader
  reads `cache/attention/exchange_volume/<SYM>.parquet` read-only, and prints `n/a: no stored volume` when absent.

## 8 Deviations

- Third loader flag: a term that passes the loose check but not the loader's `TERM_RE` (e.g. `pax+gold`, a term over
  40 characters) prints `not loader-safe (length or characters)`; "needs qualifier word" would be wrong for it.
  "needs qualifier word" follows the runner's real rule: only the name-risk symbols (MORPHO, SOL, LINK, ...) need it.
- One-term spike is `n/a: one term` for a single-term group (one term always carries 100% of the increase, so the
  check would block every single-term group). It is `missing` when the group has no increase over its baseline.
- `--try` refuses `--alone` and `--timeframe` (the frame checks need the explicit range).
- Loose term check: 2-60 characters of letters, digits, space and `. ' & + : -` (Unicode letters allowed), no
  leading/trailing space; topic ids `/m/...` `/g/...`. Terms must differ (case-insensitive) within a group.
- Bad frames do not count toward the 3-in-a-row breaker; only failed requests do.

## 9 Blockers

No blockers. Open questions for the owner:

1. The spike rule as specified (largest term's share of the increase > 80%) flags a group whose dominant term is
   simply most of the volume (one term at 90% of searches will often carry > 80% of the rise). Compare the term's
   share of the increase with its share of the group instead?
2. The ranked summary's "highest median" compares groups fetched in different requests, each scaled to its own
   peak; it orders but does not measure. A shared anchor term would fix that (stage 2?).
3. The paste-ready JSON uses `{"SYM": {"terms": [...]}}`, which the current loader does not accept (fields are
   `topic` / `term` / `no-keyword`). The loader change belongs to the other task touching the keyword file.
4. Should `quiet-then-surge` count as usable for clean rising? Today only `ok` does (same as the daily run).

5. Planner amendment received mid-task (cross-session message, 21:05Z): campaign mode (`--all-eligible`,
   resumable `--state FILE`, `--max-requests`, `--report`), spend cap raised to 12 USD. NOT built in this PR: it
   reverses the envelope's "no file writes at all" (state file) and roughly triples the scope, and a cross-session
   message is not a worker envelope. Request: a fresh envelope (T196b, stacked on this branch or after merge) or
   the owner's direct confirmation; the pure metrics module and `--try` runner are written to be reused by it
   (`trends_groups.analyze`, `check_group_frame`, `rank_key`). Design hook noted: a per-coin state of
   `last_tested`, `best_group`, `verdict` would let the Discovery gate require "keyword tested".

Registry update request: T196 -> review (draft PR open); T196b (campaign) -> needs envelope.

## 10 Follow-up

- Stage 2: a loader `terms` field and a group pull in the daily runner, once the owner picks groups from real runs.
- Tune the placeholders (`MIN_RISE_RATIO`, `MIN_DAYS_ABOVE`, `SPIKE_SHARE`, `MOVES_ALONE_CORR`,
  `IDENTITY_MIN_DAYS`, `IDENTITY_MIN_CORR`) after the first batch.

### Owner: first batch (8 groups, 8 requests, about 30 s)

From the repo root (PowerShell or bash; keep the single quotes):

```
uv run --project api --with pytrends python -m api.scripts.probe_trends --try 'GRAM=toncoin crypto|ton coin|toncoin' --try 'AKE=akedo|akedo token' --try 'BTW=bitway|bitway token' --try 'PEARL=pearl crypto|pearl research|pearl ai' --try 'OKB=okb token|okx okb' --try 'ETHFI=etherfi|ether.fi' --try 'PAXG=pax gold|paxos gold|paxg' --try 'MORPHO=morpho protocol|morpho labs'
```

How to read each group:

- `term X: loader-valid | needs qualifier word | not loader-safe`: whether the daily loader would take it as is.
- `outcome` / `latency`: `ok`, or the error class and HTTP status. A 429 stops the run (exit 4); wait 30-60 min.
- Per-term table `term | median | zero % | share of group`: a term with a tiny share adds little; a term with a high
  zero % is mostly empty days.
- `group | days | min | median | max | zero % | verdict`: the summed series under the daily rule (median >= 3 and
  zero share < 40%). `too-little-interest` or `quiet-then-surge` means the daily run would store nothing.
- `rising | ratio (mean, as the daily run) M | ratio (median, used for clean-rising) R | days above baseline D/7 |
  one-term spike`: the daily run uses the mean; clean-rising uses the median. R >= 1.10 and D >= 4 mean a sustained
  rise, not a one-day spike; "spike: yes" means one term carries over 80% of the rise (suspect noise or a namesake).
- `correlation (7-day smoothed) vs best term`: terms that rise and fall together describe the same crowd; `moves
  alone` (< 0.2) suggests a term catches other searches (a namesake, a product, news).
- `identity`: correlation with the coin's own stored trading volume (log). A hint, not proof; `n/a` without at
  least 60 stored days.
- `clean rising: yes`, or `no (reasons)`.
- Ranked summary per coin (usable, then clean rising, then highest median; each group on its own scale) and the
  paste-ready JSON of the best usable group whose terms are all loader-valid (informational, written nowhere).

## 11 Context cost

Loaded: CLAUDE.md, the envelope, `probe_trends.py`, `trends_cli_common.py`, `trends.py`, parts of
`trends_keywords.py`, `store.py`, `registry.py`, `check_trends_keywords.py` (breaker and exit-code conventions),
`api/tests/trends_fixtures.py`, parts of `test_probe_trends.py`, master-planner.md section 9 (report template).
About 60k tokens. Tools: shell, file edit, GitHub MCP. No subagents spawned.

## Round 2 (T201)

Envelope T201 (owner ENTER EXECUTE MODE for stage 1, 26-10-26). Same branch and PR; `origin/main` merged first
(merge commit, no rebase). Red commit, then green commit, then this report.

### Decisions on the round-1 questions

1. One-term spike: flagged only when the top term's share of the last-7-day rise is >= `SPIKE_SHARE` (0.8) AND >=
   its share of the group's prior-28-day baseline + `SPIKE_TAKEOVER` (0.2). A dominant but steady term (90% of the
   searches, 90% of the rise) is not flagged; a term that jumps from 10% to most of the rise is. The output prints
   both shares. Boundary is now `>=` (was `>`); the old boundary test was updated to the new rule.
2. Groups are separate requests on separate 0-100 scales: medians are never compared. Ranking is usable verdict,
   then clean rising, then lower zero-day share, then more distinct values, then higher volume correlation (missing
   last). Every median prints as "(own scale only)" and the --try header says "never compared across groups".
3. The paste-ready JSON is labelled "stage-2 shape, not accepted by the loader yet". Loader unchanged.
4. (Q4, quiet-then-surge) not decided by the envelope: still only `ok` counts as usable.

### Campaign mode

- `--all-eligible`: the coins `eligible_discovery_symbols()` returns (excluded / not-tradeable / stablecoin / fund
  coins are never tested). Per coin, `trends_candidates.candidate_groups` (pure) builds up to
  `--max-groups-per-coin` (default 3, max 6) groups from repo data only: the current topic/term (baseline), the best
  single name variant, a bundle (current term + best variants, at most 3 terms), then the bare name and bare ticker
  ("needs qualifier word"; never for `NAME_RISK_SYMBOLS`), then more variants. Names: keyword label, then the
  attention_queries display name, then the CoinGecko id, then the ticker; qualifier words crypto, coin, token,
  protocol, network, chain. Every term passes the loader's `is_valid_term`; one-letter names are skipped.
- Priority: keyword missing / no stored series / weak first (latest `cache/attention/trends_runs/*.json` outcome
  when that file exists, else the stored series under the daily rule), then the rest, universe (cap) order inside.
- `--state FILE` (default `~/trends_campaign.json`): refused inside the repository (any path under the repo root,
  so api/data/cache and every tracked dir). Per coin: groups {terms, kind, note, loader_flags, outcome, metrics,
  tested_at, tester_version}, plus last_tested, best_group, verdict. Saved atomically after every group (temp +
  fsync + rename). A corrupt file is refused (exit 2) and left untouched. A missing file starts a new campaign for
  `--all-eligible` (its folder must exist) and is refused by `--report`.
- `--max-requests` (default 40, 1-60), 3 s + up to 1 s jitter, 20 s pause every 40. Breaker as before: first 429 or
  3 failed requests in a row -> exit 4; Ctrl-C -> exit 130; state kept to the last finished group. A failed request
  is retried next run; a rejected frame counts as tested. Groups tested within `--max-age-days` (default 14) skip.
- `--report FILE` (or `--report - --state FILE`): table from the state file, never starts a Trends client. Per
  eligible coin: current keyword and its verdict, best tested group, clean rising, identity hint, recommendation
  (keep / switch to [group] / needs owner). Switch only for a gain in usability or clean rising, and only to an
  all-loader-valid group. "tested X of N eligible coins"; untested coins listed separately, never as passed; coins
  in the state but no longer eligible are listed as "no longer eligible".
- Stage-2 hook (not built): the report notes that the Discovery gate could require "keyword tested"; the state's
  last_tested / best_group / verdict carry what it needs.

### Files (round 2)

- `api/data/attention/trends_groups.py` (spike rule, `distinct`, `rank_values`, `metrics_record`)
- `api/data/attention/trends_candidates.py` (new, pure)
- `api/scripts/trends_campaign.py` (new: state file, health, priority, plan, report)
- `api/scripts/probe_trends.py` (flags, campaign loop, report, labels)
- tests: `test_trends_candidates.py`, `test_probe_trends_campaign.py` (new); `test_trends_groups.py`,
  `test_probe_trends_try.py` (updated for the two decided behaviour changes)

### Owner commands

From the repo root (PowerShell; create `C:\vet` first, the state file's folder must exist). Repeat the first until it says every group is tested (about 231 groups for 77
coins: 6 runs of 40; wait 30-60 min after an exit 4):

```
uv run --project api --with pytrends==4.9.2 python -m api.scripts.probe_trends --all-eligible --state C:\vet\trends_campaign.json --max-requests 40
uv run --project api --with pytrends==4.9.2 python -m api.scripts.probe_trends --report C:\vet\trends_campaign.json
```

The hand-typed first batch from round 1 still works as is (`--try`, 8 requests).

### Tests (round 2, UTC 2026-10-26)

- `pytest api/tests/scripts api/tests/data/attention`: 1189 passed.
- `pytest api`: 2609 passed, 1 skipped, 5 deselected. `main` @ `a155901` (clean worktree): 2468 passed, 1 skipped,
  5 deselected. +141 = round-1 72 + round-2 69 new tests; two existing round-1 assertions changed for decided
  behaviour (spike boundary `>=` with the takeover rule; group/rising line now prints own scale, distinct and the
  baseline share); none removed.
- ruff on the 8 touched Python files: clean. `git diff --check`: clean. Secret scan of the new code: no hit; tests
  assert the sentinel secret, cookies and bodies never reach the output or the state file.
- No network import in `trends_candidates` (AST test, same ban list as `trends_groups`).
- File set vs main: the 8 Python files above plus this report. No `.github/`, pyproject, uv.lock, data, cache or
  keyword-file edit. All tests use fake clients; no Google contact.
- Mutation check (50 hand mutants on the spike rule, ranking, candidates, state validation/atomic write/path
  refusal, freshness, priority, health, report rules, caps, pause, breaker, argument rules): first pass 38 killed,
  12 survived. Two survivors were redundant guards (removed: the variant qualified-check and the topic check before
  bundling; both always true by construction). Tests added for 9. Final: **46 of 47 killed**, 1 equivalent survivor
  (`len(bundle) >= 2` -> `>= 1`: a one-term bundle equals the single variant and is deduped).

### Deviations (round 2)

- A missing state file starts a new campaign for `--all-eligible` (otherwise the first run could never start);
  `--report` refuses it. Its folder must exist.
- Path refusal covers the whole repository, not only api/data/cache and the tracked dirs (an untracked file at the
  root could be committed by accident).
- A rejected frame counts as tested (Google answered); only a failed request is retried next run.
- Recommendation rule (not in the envelope): switch only for a gain in usability or clean rising, and only to an
  all-loader-valid group; ties keep the current keyword.

### Open questions

1. Q4 from round 1 (quiet-then-surge as usable) is still open.
2. Bare-name / bare-ticker candidates rank after the bundle, so with the default 3 groups they are only tested when
   a coin has few variants; raise `--max-groups-per-coin` to include them.
3. `trends_runs/*.json` is read with an assumed shape (`{"coins": {SYM: {"outcome"}}}`); align once that PR lands.

## Round 3 (T202)

Three planner decisions on PR #182. Red commit a70b49c, green commit 7a2f2cd (plus a small test/lint follow-up).

1. **Quiet-then-surge ("waking up").** Ranking classes, best first: usable clean rising, usable, quiet-then-surge,
   too-little-interest, anything else (`trends_groups.verdict_class`; failed or rejected groups never rank). It is
   still not usable and never counted as passed. The report and `--try` show `quiet-then-surge (waking up)`; a coin
   whose best group is a surge is recommended `keep watching: waking up`, never `switch`. The report adds a line:
   usable N, waking up M (shown, never counted as passed), too little interest or none K.
2. **Adaptive depth.** A coin whose current keyword is usable (health `ok`: latest trends_runs outcome, else the
   stored series, else unknown = weak) gets at most `--max-groups-usable` (default 2, range 1-2): baseline plus the
   bundle (the best single variant when no bundle exists). Every other coin gets up to `--max-groups-per-coin`
   (default 4, now the weak ceiling). Weak order: baseline, best variant, bare name, bare ticker, bundle, more
   variants; name-risk coins never get a bare candidate. Bound asserted on a 78-coin fixture: total <= 4 x weak +
   2 x usable.
3. **trends_runs reader** (`trends_campaign.read_runs`), written against the real writer in PR #181
   (`trends_runs.append_run`): a single run is the file itself, a second run the same UTC day gives
   `{"runs": [...]}`; the latest run of the latest `YYYY-MM-DD.json` is used. Outcome strings outside the daily run's
   set become `unknown` (treated as weak). A corrupt, oversized or unknown-shape latest file is ignored with a note
   (file name only, never content) printed by the campaign and the report; the run is never blocked.
   `--report` on a missing state exits 2 and says `state file not found: <path>; no campaign has been started there`
   (the missing-state refusal already existed; the message now names the path).

### Deviations (round 3)

- Default depth changed, so the old tests that assumed 3 groups per coin were updated (weak health by default in
  the test helper; explicit `--max-groups-per-coin 3` where counts matter). One old expectation changed:
  `rate-limited` in a run record now reads as `unknown`.
- Candidate order for weak coins changed (bare name and ticker before the bundle) so that both fit in 4.
- `health_reader` keeps its signature; a new `runs_reader` kwarg supplies the note.

### Open questions (round 3)

- Q3 above is closed (shape taken from #181); Q2 above is closed (default 4 includes the bare candidates).
- Q4 (quiet-then-surge as usable) stays no: it is "waking up", watched, not passed.

## Round 4 (T207)

Review T205 (MERGE-AFTER-FIXES, no blocker). Main merged in first; red commit `39e48e2` before the green commit.

### Changes

1. **Two ratios, kept apart (MEDIUM).** The daily run's / PR #181 `last7_vs_prior28_ratio` is a MEAN ratio
   (`trends.series_stats`); the tester's old `last7/prior28` was a MEDIAN ratio under a similar name. Now:
   - Output header: `ratios: the daily run uses the mean; clean-rising uses the median (robust against a single-day
     spike); both are shown`. The group line prints `ratio (mean, as the daily run) M | ratio (median, used for
     clean-rising) R`.
   - The mean comes from `trends.series_stats` itself (same number, same 2-decimal rounding, missing when the
     prior-28 mean is 0 or under 35 days). It stays visible when the median baseline is 0.
   - Renamed: `Rising.ratio` -> `Rising.median_ratio` (+ new `Rising.mean_ratio`); `MIN_RISE_RATIO` ->
     `MIN_MEDIAN_RISE_RATIO` (still 1.10); campaign-state record key `rise_ratio` -> `last7_median_vs_prior28_median`
     plus `last7_mean_vs_prior28_mean`. No field named `last7_vs_prior28_ratio` exists in the tester. The not-clean
     reason now reads `last7 median / prior28 median R < 1.1`. Clean-rising is unchanged: median ratio >= 1.10.
   - Tests: spiky series (flat 10, last day 100: mean 2.29, median 1.0) and a ramp 1..100 (both 1.22), also through
     `--try` output and `metrics_record`.
2. **One-term-spike boundary (LOW).** Tests at exactly baseline share + 0.2 (60%/40% base, 80% of the rise: flagged),
   just below (61% base: not flagged), above (59%), exactly 0.8 with a low baseline (flagged), 79.6% (not flagged),
   and a float-noise case (6/7 vs 23/35 + 1/5, equal in exact math, not in floats) that pins `SHARE_EPS`.
3. **Own-diff re-read.** Renames above applied everywhere (code, output, tests, report line for the `rising` row);
   no unused code left; ruff clean on the touched files (no UP017). No behaviour changed beyond the above.

### Gates (UTC 2026-10-27)

- Red first: 13 failed, 73 passed on the red commit (the boundary tests pass on old code; they pin it for mutation).
- `pytest api/tests/scripts api/tests/data/attention`: 1277 passed. Full `pytest api`: 2697 passed, 1 skipped,
  5 deselected. ruff on the 4 touched Python files: clean. `git diff --check`: clean. No secret or network import
  added (`trends_groups` still has none; a test asserts it).
- Mutation check on the changed logic, 22 mutants: 20 killed, 2 survived, both equivalent: `>=` -> `>` on the share
  checks while `SHARE_EPS` slack is kept (`x > y - 1e-9` and `x >= y - 1e-9` differ only inside 1e-9). Together with
  `SHARE_EPS = 0` the combined mutant is killed. First run also had `SHARE_EPS`-removed and record mean/median swap
  surviving; both now killed by the new tests.

### Owner commands

Unchanged and still correct: `--try 'SYM=term1|term2'` groups; `--all-eligible --state C:\vet\trends_campaign.json
--max-requests 40`; `--report`. The campaign state written by earlier runs may hold the old `rise_ratio` key; it is
not read back by the campaign, so nothing needs migrating.
