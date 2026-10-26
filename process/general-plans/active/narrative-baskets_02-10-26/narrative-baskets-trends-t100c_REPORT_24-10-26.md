# T100c REPORT: Trends step in the daily workflow (24-10-26)

## 1. Summary
The `refresh-extra` Trends step now installs `pytrends==4.9.2` per run, has a 14 minute limit, never aborts the other extra steps, and logs a `trends failure-class:` line. Guard tests pin all four points. Not proven here: whether Google answers a GitHub runner (P-GH, owner step).

## 2. Scope and branch
Slice T100c of T173, branch `claude/t100c-trends-workflow`, one draft PR to main, not merged. Files: `.github/workflows/attention-refresh.yml`, `api/tests/tooling_guards/test_attention_workflow_guard.py`, this report. No api/ code, pyproject, uv.lock, cache, probe_records.json, other workflow or secret touched.

## 3. Changes
- Command: `uv run --project api --with pytrends==4.9.2 python api/scripts/refresh_attention.py --sources trends`, output teed to `extra-trends.log` as before.
- `timeout-minutes` 8 to 14.
- After the fetch the step prints the `trends detail:` line (or `trends detail: not printed`) and then `trends failure-class: <class> - <detail>`, then exits with the fetch's own exit code (`rc` captured with `|| rc=$?`; the file has no `|| true`, which a guard forbids).
- The class comes from `attention_extra.classify`, the same classifier the verify step uses: `none`, `provider block (429/ConnectionError/capped)`, `code error`, `not probed`.

## 4. Why an exact pin via --with
pytrends stays out of `api/pyproject.toml` and `uv.lock` (T100b plan; declaring it is the owner's call). Latest stable on PyPI metadata (checked 24-10-26): 4.9.2, released 2023-04-13. An exact `==` makes the run reproducible; a range could change behaviour between days. Tradeoff: the pin is resolved at install time each run (small download, no lockfile hash). `UV_FROZEN` is not set in the workflow, so `--with` resolves normally.

## 5. Timeout arithmetic
Fetcher budget `TRENDS_TIME_BUDGET_S` = 540 s (9 min). The budget is checked before each coin and a backoff wait that would end past it is not started, so the overrun is at most one in-flight request. Estimate: 540 s + pytrends install about 60 s + one last request about 60 s (timeouts) + store write and archive about 60 s = about 12 min. Limit 14 min leaves 2 min margin (guard: `>= 540 + 120` s).
Job limit 40 min. Step limits: Binance 4 + Hyperliquid 4 + Trends 14 + Reddit 8 = 30; plus install, verify, probe, commit (push retries sleep 10 s + 20 s) about 5 min; 35 <= 40. Guard: sum of step limits + 5 <= 40. No step shortened, no coin skipped.

## 6. Non-abort and code-failure behaviour
Step has `continue-on-error: true`, so a Google refusal (non-zero exit, yellow step) does not stop Reddit, verify, probe or commit. The verify step (`attention_extra.py`, no `continue-on-error`, `if: !cancelled()`) is unchanged: a `store-failed: <non-provider class>` last line or a missing result line (crash/timeout) is `failed` and turns the job red; provider blocks are a `::warning::`. Verified with the classifier on sample lines (local simulation of the step's Python block): `error HTTP 429` and `0/75 ok ... HTTP 429 x75` give `provider block`; `error store-failed: ValueError x3` gives `code error`.

## 7. Tests (RED first)
Added 4 guards; 3 failed before the YAML change (pin, timeout, failure-class), the 4th (verify still catches code errors) passes on both sides by design. The old blanket `timeout-minutes <= 8` check now exempts Trends.
- Gate `UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards/test_attention_workflow_guard.py api/tests/scripts/test_ci_workflow.py -q`: baseline 22 passed; after: 26 passed, 0 failed.
- Full `pytest api`, diff scope, `git diff --check` (clean), secret scan of the added lines (nothing), YAML `safe_load` ok: see the PR description for final counts.

## 8. Owner steps: P-GH (does Google answer a GitHub runner)
1. After the PR is merged to main (or on the branch), open Actions > "Attention daily refresh" > Run workflow (branch main, leave categories at default) and start it.
2. Wait for job `refresh-extra` (up to about 40 min worst case). The Trends step may be yellow/failed: that is allowed and is not a reason to worry.
3. Open the "Refresh Google Trends" step log and copy these lines: `trends detail: ...`, `trends failure-class: ...`, and the `trends: ...` summary line.
4. Open the "Verify the extra sources" step and copy the `summary trends: ...` line (and any `::warning::` for trends).
5. Note the step duration (the 14 min limit leaves 2 min margin; report if it ended by timeout).
Paste the lines back. Then the owner records the probe (`probe_records.json`) as a separate task; this PR does not touch it.

## 9. What to expect and how to read it
- `failure-class: none` and `trends detail: ok N, ...`: Google answered; check ok count against the 75 coins.
- `provider block`: Google refused the runner (429, ConnectionError or capped). Expected possibility; the other sources are unaffected and the job stays green with a warning.
- `code error`: a bug (store-failed or no result line); the job goes red; paste the lines.
- `pytrends not installed` in reasons would mean the `--with` install failed; paste the step log head.

## 10. Risks and unknowns
- Google reachability from runners: UNVERIFIED (no provider call made here).
- Whether 540 s is enough for 75 coins with backoff: the fetcher caps the remainder as `time budget reached`; not changed.
- `--with` re-downloads pytrends daily (about 1 min worst case, within the margin).
- Report not opened: no web/ panel work (T100d candidate, out of scope).

## 11. Extra docs opened
T100b PLAN (T100c sections), `attention_extra.py`, `refresh_attention.py` (Trends section), the two guard test files named in the envelope. No other docs.

## 12. Fix round (T181, review T176: MERGE-AFTER-FIXES)
- Finding: a Google refusal shows per coin as `fetch-failed: ConnectionError`; `attention_extra` called it a CODE error (red) while the workflow's failure-class line said "provider block".
- Fix: `PROVIDER_CLASSES` now lists the requests/urllib3/builtin transport class names (ConnectionError, Timeout, SSLError, ProxyError, ChunkedEncodingError, TimeoutError, ...; names only). `fetch-failed` and `session-failed` with a network class, `capped`, `rate-limited: ...`, `time budget reached` are PROVIDER (yellow). `parse-failed` and `store-failed` are always CODE (red), as are fetch-failed with TypeError/KeyError/AttributeError/ValueError/unknown classes.
- Single source: the workflow's failure-class label comes from `attention_extra.failure_class` (one `FAILURE_CLASS` table); a guard test fails if the step carries its own copy.
- Exit code: new guard test runs the Trends step's shell with a fake `uv` and requires the step to exit with the fetcher's status (`exit "$rc"` -> `exit 0` is killed).
- Tests: both directions of the classifier, class set shape, label table, step exit code.
