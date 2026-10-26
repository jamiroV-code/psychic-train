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
- `rising | last7/prior28 R | days above baseline D/7 | one-term spike`: R >= 1.10 and D >= 4 mean a sustained rise,
  not a one-day spike; "spike: yes" means one term carries over 80% of the rise (suspect noise or a namesake).
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
