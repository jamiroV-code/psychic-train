# T89 (P5) verifier fix report

## 1 Task ID
T89 (P5), branch `claude/t89-p5-verifier-fix`.

## 2 Outcome
Done. Draft PR opened against main; not merged.

## 3 Summary
- Verifier now fails a series source on freshness only when its latest stored completed day is stale: older than today UTC minus 3 days (wikipedia) or 2 days (coingecko). It compares to that threshold, not to the pre-refresh day. Error line and 0-ok rules are kept. Per source it prints the result line (state counts), latest day and threshold. The "before" snapshot step was removed as unused.
- Decision logic is `api/scripts/attention_freshness.py` (`judge`), called from the inline python.
- Probe: `record_probe.py` reads the store only, has no prompts, so a new step runs it after the verifier with `--sources` limited to wikipedia/coingecko sources the verifier passed (list in `$RUNNER_TEMP/attention-ok.txt`). No `--state`. Commit step now also force-adds `api/data/attention/probe_records.json`.
- Known limits: the probe records whatever state the store shows (e.g. `insufficient-history` if no coin has enough days); I did not verify what the Narrative tabs gate on beyond the AC-34 description. The probe step is skipped if the verifier job step is cancelled. Not run live.
- Narrative tabs: scores should appear after the next run IF the recorded state for each source is `ok` (with the stored history). No owner step is expected, but check `probe_records.json` after that run.

## 4 Files changed
.github/workflows/attention-refresh.yml; api/scripts/attention_freshness.py (new); api/tests/test_attention_freshness.py (new); api/tests/tooling_guards/test_attention_workflow_guard.py; this report.

## 5 Commits
One commit on the branch.

## 6 Tests run
Baseline on untouched origin/main: 1420 passed, 1 skipped, 5 deselected. After: 1428 passed, 1 skipped, 5 deselected (+8 new freshness tests; guard tests updated). New tests were red (import error) before the module existed. Diff checks (see gates) run before the PR.

## 7 Tests NOT run
The workflow itself, any live refresh or network call.

## 8 Deviations
Removed the "before" snapshot step (no longer needed). Guard no longer asserts "record_probe not in workflow" (now required, once, without `--state`).

## 9 Blockers
None.

## 10 Follow-up
If the owner prefers a manual probe: `uv run --project api python api/scripts/record_probe.py` then commit `api/data/attention/probe_records.json`. Rare pre-existing case: a probe could still be recorded for a source whose refresh was ok but history is short.

## 11 Context cost
Read CLAUDE.md, workflow, guard test, record_probe.py; about 30 KB total.
