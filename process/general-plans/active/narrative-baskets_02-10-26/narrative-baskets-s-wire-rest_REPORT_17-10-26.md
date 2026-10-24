# T90 (P5) wire the remaining attention sources - REPORT

## 1. Task ID
T90 (P5), branch claude/t90-p5-wire-rest, base origin/main.

## 2. Outcome
done. Draft PR against main, not merged, nothing run live.

## 3. Summary
New job `refresh-extra` (needs: refresh, if !cancelled(), timeout 30) in attention-refresh.yml. The `refresh` job is untouched (git diff shows only appended text plus a header comment). Steps: checkout of the branch head (ref: github.ref_name, so it sees the core push), one continue-on-error step per source, Reddit gate, verifier `api/scripts/attention_extra.py`, probe for ok sources only, commit with the same retry-rebase loop. Shared concurrency group; the job runs only after `refresh` ends, so no double push.
Code: attention_extra.py (pure classify/verify), per-source lag thresholds in attention_freshness.py (exchange_volume 2, hyperliquid_volume 2, reddit 2, trends 3), refresh_attention.py prints `reasons: ...` after the outcome list only when 0 series are ok, exchange_volume.py reason now `fetch-failed: Class HTTP nnn` (status only, never the message).
Classes: ok (>=1 series ok or rows stored; Hyperliquid and Trends store insufficient-history rows, counted as refreshed), unavailable (all series blocked, or an error line with HTTP 4xx/5xx or a provider exception class; yellow ::warning::, no probe, job green), not-probed (no Reddit credentials), failed (other exceptions, missing line, stale data; job red).
Per source on a GitHub runner (expected): Binance: unavailable, HTTP 451. Reddit: not-probed until the two secrets exist; then likely 403/429 -> unavailable, may work. Trends: likely 429 -> unavailable, may work. Hyperliquid: should be ok.
Proven by tests: workflow shape, classification of 451/403/429/timeouts as unavailable, code errors as failed, probe list only ok, warning injection safety, thresholds. Only by the first live run: real provider answers, real wording of ccxt/pytrends errors (an unknown error class would show as a red job, which is the safe direction), ccxt hyperliquid public access, runtime of Reddit/Trends (step timeouts 8 min).
Known limits: Trends/Hyperliquid probes are recorded with the observed state (insufficient-history), not ok; pytrends reasons were not changed so their status may not appear in the line; the first red job would mean a new error class to add to PROVIDER_CLASSES.

## 4. Files changed
.github/workflows/attention-refresh.yml; api/scripts/attention_extra.py (new); api/scripts/attention_freshness.py; api/scripts/refresh_attention.py; api/data/attention/exchange_volume.py; tests: tooling_guards/test_attention_workflow_guard.py, scripts/test_attention_extra.py (new), scripts/test_refresh_attention.py, test_attention_freshness.py, data/attention/test_exchange_volume.py; owner guide (+section 6b); this report.

## 5. Commits
One commit on the branch (see PR).

## 6. Tests run
`UV_FROZEN=1 uv run --project api pytest api/ -q`: 1454 passed, 1 skipped, 5 deselected, 1 failed. The failure `test_registry.py::test_shipped_probe_records_empty` fails identically on untouched origin/main (committed probe_records.json now holds T89 probes); not mine, not touched. New tests: about 40 (guard, extra, freshness, exchange 451, reason_summary).

## 7. Tests NOT run
Workflow run, any live provider call, web tests.

## 8. Deviations (adversarial review)
(a) Core job: refresh job text identical; only a comment was added above it and a job after. Shared script changes only add output text after the outcome list when 0 ok; the core verifier regex is a prefix match. Checked.
(b) Probe for a failed source: probe list comes only from verify() status ok after the freshness check; unavailable, not-probed, failed never enter attention-extra-ok.txt; an empty file means no record_probe call. Tested.
(c) Secrets: only in redditgate env (boolean expression) and the Reddit step env; no echo; existing guard test extended. Reasons are redacted and "::" stripped.
(d) Race: needs: refresh plus the shared non-cancelling group; the commit loop uses pull --rebase before push.
(e) YAML: parsed by PyYAML in tests; actions pinned identical; permissions unchanged. Deviation: protected-test files untouched; exchange_volume.py reason text changed (envelope allowed the fetch paths). The registry test failure is pre-existing.

## 9. Blockers
None.

## 10. Follow-up
After the first live run, add any new provider error class seen as red to PROVIDER_CLASSES. Owner adds REDDIT secrets. Decide whether trends/hyperliquid probes should wait for ok.

## 11. Context cost
Roughly 80 KB read; one full suite run plus targeted runs.
