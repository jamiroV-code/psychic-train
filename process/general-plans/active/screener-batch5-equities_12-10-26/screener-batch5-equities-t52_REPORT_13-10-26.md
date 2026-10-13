---
name: report:screener-batch5-equities-t52
description: "T52 LSE API key persisted as a DPAPI file, loaded by start-api.ps1"
date: 13-10-26
---
# T52: persistent LSE API key

## Outcome
Done (draft PR, not merged). PC run still needed.

## Summary
The LSE API key is now stored once in a Windows-protected (DPAPI) file outside the repo, `%LOCALAPPDATA%\my_site\lse-api-key.dat`, by the new `deploy\set-lse-key.ps1`. `deploy\start-api.ps1` loads it into its own process before starting uvicorn. A key already set in the environment wins. The value is never printed, logged or written in plain text.

## Files
- deploy/set-lse-key.ps1 (new): clipboard input (default) or `-Prompt`, plus `-Status` and `-Remove`; length >= 20 and no whitespace/quotes check; icacls set to current user only; clears the clipboard
- deploy/_common.ps1: `LseKeyPath`, `Get-LseKeySource` (no decrypt), `Import-LseApiKey`
- deploy/start-api.ps1: `Import-LseApiKey` before launch; DryRun prints the source only; two comment em-dashes changed to `--` (ASCII)
- deploy/README.md: section "LSE API key (equities prices)"
- api/tests/deploy/test_deploy_lse_key_shape.py (new, 8 tests)
- api/tests/deploy/test_deploy_r12_guards_shape.py: guard amendment (see Deviations), +1 test
- process/general-plans/backlog/lse-api-key-deploy-handling_NOTE_13-10-26.md: status IMPLEMENTED

## Tests run with SHA/UTC
Base origin/main 96eb9a7, 2026-10-13T16:14Z.
- `UV_FROZEN=1 uv run --project api pytest api/tests/deploy -q`: 77 passed, 1 skipped
- `UV_FROZEN=1 uv run --project api pytest api -q`: 1143 passed, 1 skipped, 5 deselected (baseline 1134 + 9 new)
- `git diff --check`: clean. Changed .ps1 files are ASCII only; the new README section is ASCII.
- PowerShell parse check: not possible (no pwsh in this sandbox); text-level checks only.

## Not verified
- None of the .ps1 changes has been parsed or run. On the PC, run `set-lse-key.ps1 -FromClipboard`, then `-Status`, `start-api.ps1 -DryRun`, and restart the `mysite-api` task. Then check that `api.log` shows "LSE key: from key file" and that an `/api/equities` refresh works.
- The icacls grant syntax and the Get-Clipboard/Set-Clipboard behaviour under Windows PowerShell 5.1.

## Deviations
- Planner-approved amendment to an existing guard test: `test_no_credentials_or_literal_remote_hosts_in_deploy_scripts` forbade "securestring" in every deploy .ps1, which the DPAPI design needs.
  - "securestring" is now allowed only in set-lse-key.ps1 and inside the `Import-LseApiKey` function of _common.ps1. The rest of _common.ps1 is still checked.
  - The other forbidden words (authorization, bearer, credential, password) still apply to all scripts.
  - New test `test_securestring_still_forbidden_in_other_scripts` proves the word stays forbidden elsewhere, including start-web.ps1.
- `-FromClipboard` is the default; prompt mode is the `-Prompt` switch.

## Blockers
None.
