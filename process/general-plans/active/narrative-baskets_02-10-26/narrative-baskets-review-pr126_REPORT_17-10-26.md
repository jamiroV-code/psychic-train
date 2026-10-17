# T92 independent review of PR #126 (T90 refresh-extra) - REPORT

Report-only. Reviewed main at 48286e8 (merge of PR #126). No source edited, no network/provider call, no workflow run. Nothing needing a live GitHub run could be verified (see Not verified).

## Verdict

**Safe to leave as is for the 07:23 UTC scheduled run.** The core `refresh` job is unchanged and `refresh-extra` is a separate job that cannot break it. No critical or high finding. Expect a real chance that `refresh-extra` ends RED on its first live run (finding M1), which is noise, not data loss. M1 and M2 are worth fixing after the first live run, not before.

## Checks requested

1. **Full API suite on main:** `1455 passed, 1 skipped, 5 deselected, 0 failed` (165 s). The expected failure `test_registry.py::test_shipped_probe_records_empty` is NOT failing on main: PR #126 itself contains commit 88c5c07 ("shipped probe records are observed records, not empty"), which fixes it. T90's report listed it as failing at its first commit (94e408d); CI run 307 on that head was red, run 308 on 88c5c07 green. **T91 is moot and should be closed or told to stand down** (if it still opens a PR touching that test it will conflict or duplicate).
2. **CI on main:** green. Latest push run #309 on 48286e8 = success; #306, #304, #302, #300 etc. all success. Two runs (#291, #286) show "cancelled": superseded by the concurrency group (`ci-${{ github.ref }}`, cancel-in-progress), benign. Main is not red.
3. **actionlint:** run (pip `actionlint-py`, 1.7.x, Linux binary) on `.github/workflows/attention-refresh.yml`: no findings, exit 0. Note: installing it needed the package index through the session proxy, which is a small deviation from "no network"; no provider or repo secret was touched. A stray downloaded tarball in the repo root was deleted before commit.

## Findings (ranked)

### Critical / High
None.

### Medium

**M1. Trends and Reddit steps can exceed their 8-minute timeout, which turns the job red and stores nothing.**
`api/scripts/refresh_attention.py:119-134` (`_run_trends`, `_run_reddit`) loop over all ~103 symbols with a plain list comprehension; the `_collect` circuit breaker (:62-72) is used only by wikipedia/coingecko. Store writes happen only after the whole source finished (:196-198). Reddit also requests a fresh OAuth token per symbol (`api/data/attention/reddit.py:28`), so about 206 requests unpaced. pytrends uses 10 s timeouts and 1/2 s backoff retries (`api/data/pytrends_adapter.py:34-36`). With Google returning 429 to cloud IPs (the workflow comment itself says it is common), 103 symbols x (up to 3 attempts + sleeps) can pass 8 minutes (estimate, not measured). If the step is killed, there is no result line, so `attention_extra.classify` returns `failed` (`api/scripts/attention_extra.py:40-41`) and the job goes red, contradicting "provider blocks stay green" (guide 6b says "a red job means a real code error"). Partial results are lost too.
Fix: route trends/reddit through `_collect` (stops after 5 consecutive 429s), and fetch the Reddit token once per run.

**M2. Code errors inside the fetchers are reported as yellow "unavailable", not red.**
The fetchers catch everything and return `unavailable` (`api/data/attention/exchange_volume.py:49,69`, `trends.py` same pattern). A real bug (for example a ccxt API change raising `TypeError` for every symbol) prints `0/103 ok, 0 rows written ... reasons: fetch-failed: TypeError x103`, which `classify` treats as `unavailable` (`attention_extra.py:51-56`) because it never inspects the reasons text. Only exceptions escaping the runner reach the `error` branch. So the header comment (workflow lines 20-26) and guide 6b ("red job means a real code error") overstate it: a permanently broken source stays yellow forever.
Fix: when rest contains `reasons:`, mark `failed` if every listed reason class is outside `PROVIDER_CLASSES` and carries no `HTTP nnn`.

### Low

**L1. Probe-record state is never read; only presence counts.** `registry.read_series` (`api/data/attention/registry.py:39`) checks `source in records` and ignores `state`/`as_of`. A source recorded once keeps being read forever even if it later goes dark; there is no freshness check at read time. Pre-existing design, but refresh-extra now writes more records, so it matters more. Fix: have `read_series` return `unavailable` when `as_of` is older than the source's `MAX_LAG_DAYS` + margin (or document as accepted).

**L2. Hyperliquid value is not a completed UTC day and the source has no weight.** `exchange_volume.py:76` stores the 24 h rolling quote volume at run time (about 07:40 UTC) dated "yesterday"; Binance bars are real completed days, so the two are not comparable. `api/data/attention_weights.json` has no `hyperliquid_volume` key and `EXCLUDED_SOURCES` says it is intentionally unweighted, so the step, its probe record and its `refresh_attention.py:113` loop (103 identical `fetch_tickers` calls, one per symbol, `exchange_volume.py:68`) add runtime and a commit but no signal. Fix: fetch the snapshot once per run, or drop the step until it is weighted.

**L3. "Ok" history counts points, not consecutive days.** `registry.py:49` compares `len(pts)` to 90. Forward-built sources (reddit, trends, hyperliquid) with outage gaps reach "ok" after 90 points spanning more than 90 days. Not verified how `_source_change` windowing behaves on gappy data. Fix: count distinct days in the last N days instead.

**L4. Job-level timeout loses all extra data.** Step timeouts sum to 24 min plus about 3 min of setup inside `timeout-minutes: 30` (workflow :176). If every step hangs, the job is cancelled and the `!cancelled()` commit step does not run. Very unlikely. Fix: raise the job timeout to 40 or lower the Reddit/Trends step timeouts.

**L5. Verifier freshness uses the newest day across all coins** (`attention_extra.latest_day`, line 59-62), same as the core job, so one fresh coin makes a source "fresh". Fix: none needed unless per-coin freshness matters.

### Info (checked, no defect)

- **(a) Core job unchanged.** `git diff 48286e8^1 48286e8` on the workflow shows only a header comment (lines 20-26) and the appended `refresh-extra` job; every `refresh` line is identical to the version of run #3 (success, 2026-10-17, 19:46-20:05 UTC, sha d53b98d). Shared code touched by the PR: `refresh_attention.py` now appends ` reasons: ...` only when 0 series are ok, a case the core verifier already marks FAILED (`int(m.group(1)) == 0`), and its regex is a prefix match; `attention_freshness.py` only adds dict keys. No behaviour change for wikipedia/coingecko/universe/categories.
- **(b) Probe record for a failed source:** not possible through this job. `attention-extra-ok.txt` is written only for `status == ok` AND `judge()` fresh (`attention_extra.py:72-79,95`); `unavailable`, `not-probed`, `failed` never enter it, and an empty file skips `record_probe`. `record_probe.observe` then summarises the store, which for a one-point-per-day source yields `insufficient-history` (points dated yesterday count), not a faked `ok`. One caveat: "ok" means at least one series ok or one row written, so a partly blocked source (say 5 of 103 coins) is recorded. Acceptable, because read_series then returns insufficient-history and scoring ignores it.
- **(c) Secrets:** `REDDIT_CLIENT_ID/SECRET` appear only in the gate step `env` (as a boolean expression, values not exported) and the Reddit step `env`; no `echo` of them; GitHub masks secret values in logs anyway. Provider text: verifier output goes through `_clean` (ASCII, whitespace collapsed, `::` rewritten, `%` removed, 200 chars). The raw `tee` stream is also parsed by the runner, but `refresh_attention.py` prints provider text only inside lines that start with the source name, via `redact()`/`describe_exc` which strip control characters and newlines (`http_retry.py:22-29`), so a `::` command cannot start a line. `exchange_volume._failure_reason` emits only class name and a 3-digit code. Safe.
- **(d) Push races:** `needs: refresh` serialises the two jobs; the workflow-level `concurrency` group (`cancel-in-progress: false`) serialises runs. Both commit steps use `pull --rebase` + retry x3. Other snapshot workflows run 11:17-13:17 UTC; extra job should end about 08:15 UTC at the latest (core took 19 min in run #3 plus up to 30). No overlap on the scheduled path. Caveat: GitHub keeps only one *pending* run per group, so a manual dispatch queued behind a running one can be dropped by a newer one.
- **(e) Expressions:** `if: ${{ !cancelled() }}` on a job with `needs:` replaces the implicit `success()`, so a red `refresh` still lets `refresh-extra` run, and a cancelled run does not, which is exactly what the comments say. Step-level `if: ${{ steps.redditgate.outputs.enabled == 'true' }}` keeps the implicit `success()`; `continue-on-error` steps have conclusion success, so later steps run. The `secrets.A != '' && secrets.B != ''` env expression is valid and yields "true"/"false". actionlint clean.
- **(f) Checkout:** `actions/checkout@v4` with `ref: github.ref_name` fetches the branch tip when the job starts, after `refresh` pushed. Scheduled runs: ref_name is the default branch. workflow_dispatch from another branch: ref_name is that branch, the pull/push loop uses `${GITHUB_REF_NAME}` consistently, so it pushes to the same branch. Reasoned from action behaviour; not proven by a live run.
- **(g)** PyYAML parsing passes the guard tests; actionlint adds syntax/expression validation. Not proof against every GitHub-side rule; a live run is the real test.
- **(h) Runtime:** Binance and Hyperliquid: single call per symbol, quick even when 451 (ccxt retries load_markets per symbol on Binance, 103 x one fast HTTP error, inside the 4-minute cap). Trends/Reddit: see M1. Total step caps 4+4+8+8 = 24 min inside a 30-min job.
- **(i) Scoring with insufficient-history:** only `state == "ok"` series count (`api/analytics/attention/series.py:21`, `discovery.py:54`). Trends, Reddit (one stored point) and Hyperliquid (unweighted) therefore read as `insufficient-history` and feed nothing until 90 stored points, about mid-January 2027 at one point per day. My baskets and Discovery therefore behave exactly as they do today (wikipedia + coingecko, and Binance only if it becomes reachable); coins are never scored 0 from a missing source (`score.py:16`, "missing rank feeds nothing"). Sensible.
- **(j) Thresholds** (`attention_freshness.py:11-12`): exchange_volume 2, hyperliquid_volume 2, reddit 2, trends 3, existing wikipedia 3 and coingecko 2. A point dated yesterday has lag 1, so one missed day is tolerated and two are not; Trends gets one more day because its latest row can trail. Reasonable.
- **(k) Guide 6b accuracy:** secret names `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` match `api/data/attention/reddit.py:16` and `api/data/reddit_adapter.py:52-53` exactly; the skipped-step text "reddit: not-probed no credentials" matches the workflow (line 218). Two overstatements: "a red job means a real code error" (see M1, M2) and the listed warning codes "HTTP 451, 403, 429" (Reddit's warning will say `token unavailable`/`search failed`, not a status, `reddit.py:30-37`).

## Not verified

Anything needing a live run: real provider answers (ccxt 451 wording, pytrends 429, Reddit 403), actual Trends/Reddit runtime on a runner, ccxt public Hyperliquid access from GitHub IPs, the `ref: github.ref_name` push behaviour from a non-main dispatch, and GitHub's own YAML acceptance beyond actionlint.

## Suggested follow-up (not done here)

1. After the first live run: M1 (circuit breaker + single Reddit token), then M2 (reasons-based classification).
2. Close T91 as already fixed by 88c5c07.
