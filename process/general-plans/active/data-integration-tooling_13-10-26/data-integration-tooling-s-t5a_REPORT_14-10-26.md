# T56 S-T5a report

## 1 Task ID
T56 (slice S-T5a), branch claude/t56-dit-s-t5a-rea-wrapper

## 2 Outcome
Done. Wrapper, allow-list, evidence template and tests implemented; all gates green. Draft PR opened; not merged.

## 3 Summary
run_rea(command, args, confirm_source, findings, runner) refuses anything not in the exact frozenset (typed Refusal, no subprocess), allows only --json/--source/--output flags, validates every argument with the strict regex plus forbidden characters, converts Windows drive-letter paths to forward slashes, pins --output inside the evidence folder, requires --confirm-source listed in --findings for the live group, runs npx via subprocess.run(shell=False) with npm_config_ignore_scripts=true (npx.cmd resolved on Windows), redacts subject.local_path and normalized_result.input_path, and saves deterministic JSON outside the repo (DIT_EVIDENCE_DIR). Refuses if the evidence dir is inside the repo. The evidence template ends with the fixed footer; render_evidence_note enforces VERIFIED/ASSUMED tags. All tests use a fake runner; npx was never run.

## 4 Files changed
tools/data-integration/src/data_integration/rea/{__init__.py,allowlist.py,wrapper.py,evidence_template.md}; tools/data-integration/tests/{test_rea_wrapper.py,test_rea_evidence.py}; api/tests/tooling_guards/test_rea_guards.py; this report.

## 5 Commits
See PR (report-only commit, then the implementation commit).

## 6 Tests run (command, result, UTC, SHA)
- Corrected baseline, untouched base c46fe1a: UV_FROZEN=1 uv run --project api pytest api/ -q -> 1160 passed, 1 skipped, 5 deselected (2026-10-14T14:52Z).
- Red-first: tooling pytest -> 2 collection errors (0 passed); guards -> 2 failed, 20 passed (3 new guard tests pass trivially on base: no API import, no rea-agents in lock, no mcp config).
- Tooling: UV_PROJECT_ENVIRONMENT=$HOME/.cache/dit-env uv run --project tools/data-integration pytest tools/data-integration/tests -q -> 111 passed (2026-10-14T15:01Z, head = implementation commit).
- Guards: UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards -q -> 22 passed.
- Full API: UV_FROZEN=1 uv run --project api pytest api/ -q -> 1165 passed, 1 skipped, 5 deselected (1160 + 5 new guards = new total 1165).
- git diff origin/main...HEAD -- .claude CLAUDE.md AGENTS.md .mcp.json -> empty; git diff --exit-code api/uv.lock -> clean; git diff --check -> clean; new files ASCII.

## 7 Tests NOT run
The one real npx -y rea-agents@6.4.0 call (developer/tester only, Node >= 22.19). No live network.

## 8 Deviations
Envelope baseline correction: expected 1143 was wrong; correct baseline is 1160 (1143 + 17 S-T1 guards), confirmed by the planner. --output may point anywhere inside the evidence root (not only the dated subfolder). Underscore is allowed by the specified regex.

## 9 Blockers
None. No MASTER-PLAN update requested.

## 10 Follow-up
Developer to run the single real npx check later (Hybrid). Findings file format chosen: JSON object {"sources": [names]} or a plain list of names; confirm or adjust in the docs slice.

## 11 Context cost
No extra docs opened beyond the envelope list.

## Supplement 1 (branch claude/t56-dit-s-t5a-supplement-1)

What changed:
- wrapper.py and allowlist.py: any argv token (flag, flag value or positional) containing `--update` or `--mcp`, case-insensitive, is refused with reason bad_flag and zero runner calls (FORBIDDEN_SUBSTRINGS). Tests cover `x=--update`, `a=--mcp`, `--update=1`, flag values and harmless dash tokens.
- test_rea_guards.py: every string constant in all rea/*.py is scanned for `rea-agents` followed by setup, update, uninstall, mcp or completions (case-insensitive), unless the text says rejected or superseded. Self-test flags a temp file with X = "rea-agents setup"; the current tree is clean.
- Acknowledged: tools/data-integration/tests/_helpers.py is a shared test helper outside this slice's owned glob list; this supplement does not touch it.
- Input-path handling unchanged (known limit: ../ and absolute positionals accepted).

Counts: tooling pytest 165 passed (baseline 150); guards 28 passed (baseline 26); API full 1171 passed, 1 skipped, 5 deselected (baseline 1169 + 2). uv.lock and pyproject.toml unchanged. UTC 2026-10-14T15:18Z.
