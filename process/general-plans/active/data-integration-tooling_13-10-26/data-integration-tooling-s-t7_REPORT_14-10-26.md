# S-T7 REPORT: command-line front door

## 1 Task ID
T62 (S-T7), branch claude/t62-dit-s-t7-cli, base origin/main (T59 merged).

## 2 Outcome
DONE. All gates green. No needs_input.

## 3 Summary
`python -m data_integration` now has three commands: `approvals` (dispatched by hand to approval_cli.main), `rea` (argv split at `--`, run_rea with an injectable runner, placeholder evidence path only) and `run <recipe>` with `--dry-run`, `--preview`, `--refresh`, `--replace`, `--accept-baseline`. Recipes are JSON data validated by recipe.py (size checked before read, duplicate/unknown keys, NaN, bool-as-int, symbol/timeframe/politeness rules). Exit codes follow G1: 0 ok/cache_hit/dry-run/preview, 2 usage/recipe/flags, 3 gate refusal incl. url_not_approved (also in dry-run), 4 fetch statuses, 5 invalid and rea failures, 6 changed/uncertain, 7 refused. Outcome line prints approval id, revision, expiry and the rate text. `--refresh` is a no-op in dry-run and preview. Fetch tiers, pipeline, adaptive, provenance and the REA wrapper are imported lazily. No proxy option. `_safe()` redacts absolute paths and IPv4; the top-level handler prints the exception type only (exit 1).

## 4 Files changed
New only: tools/data-integration/src/data_integration/{__main__,cli,recipe}.py; tools/data-integration/tests/{test_cli,test_recipe}.py; tools/data-integration/recipes/example.recipe.json; api/tests/tooling_guards/test_cli_guard.py; this report. No existing file edited.

## 5 Commits
8de3641 feat(dit): S-T7 command-line front door (code and tests); report commit follows on the same branch.

## 6 Tests run (cmd, result, UTC, SHA)
Baseline on untouched origin/main (3203fb6), measured, not hard-coded:
- tooling suite: 307 passed, 1 deselected
- guards: 41 passed
- API full: 1184 passed, 1 skipped, 5 deselected
Red-first: test_cli.py + test_recipe.py = 2 collection errors (modules absent); guard file with the three modules removed = 2 failed, 6 passed.
After (SHA 8de3641, 2026-10-15T18:00Z):
- `UV_PROJECT_ENVIRONMENT=$HOME/.cache/dit-env uv run --project tools/data-integration pytest tools/data-integration/tests -q`: 523 passed, 1 deselected (307 + 216 new)
- `UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards -q`: 49 passed (41 + 8)
- `UV_FROZEN=1 uv run --project api pytest api/ -q`: 1192 passed, 1 skipped, 5 deselected (1184 + 8)
- `git diff --exit-code api/uv.lock api/pyproject.toml`: clean
- `git diff --check origin/main...HEAD`: clean; new files ASCII

## 7 Tests NOT run
No real scrape, npx, REA or network (by rule). Real tier 1 through the CLI on loopback cannot run (permits rejects non-default ports); left to the owner's AC-20 run. Browser/antibot markers not run.

## 8 Deviations
- cli.py also carries an `if __name__ == "__main__"` block (harmless; `__main__.py` is the entry).
- `run` with an unexpected exception prints `error: <Type>` and exits 1 (no code was specified for that case).
- Dry-run prints details first, then exits 3 if the url is not permitted.
- `--replace` with an unreadable provenance file exits 2.

## 9 Blockers
None.

## 10 Follow-up
btc-hist recipe is T61 (planner). Wave/spend lines left alone (G5). Owner runs the AC-20 live check.

## 11 Context cost
Opened beyond the envelope list: fetch_tier2/3.py signatures (lines around fetch()), response_cache.py, status.py, store_writer.py, adaptive.py head, tests/_helpers.py, conftest.py, test_pipeline.py head, test_rea_wrapper.py head, existing guards (_common.py, test_import_boundary.py), allowlist.py. No other docs.
