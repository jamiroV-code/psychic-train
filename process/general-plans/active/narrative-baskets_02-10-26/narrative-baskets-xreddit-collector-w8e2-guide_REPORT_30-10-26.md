# W8e2 server host guide (REPORT, 30-10-26)

## 1 Task ID

W8e2 docs half (server host guide) plus recording of accepted decisions, branch `claude/w8e2-host-guide`, based on `origin/main` 0d669f4f. Worker `W8e2Guide`.

## 2 Outcome

Done (docs only). Nothing in the guide was run on a host; every command is marked unrun. Windows first, Linux optional; no forced migration.

## 3 Summary

- `narrative-baskets-server-host-guide_30-10-26.md`: Annex J items 1-11 as Windows steps (W1-W9, incl. W4b dump cleanup) and optional Linux steps (L1-L8), worker variables, `xreader` install with explicit `--group xreader`, accounts and cookies by pointer only, OS decision table (recommendation: stay on Windows), boot-task tradeoffs without a cookie-driven auto-logon requirement, P-W1 rewritten on `GET /api/narrative/sources` plus the worker log, and the actual `sources[].health` contract of PR #195.
- PLAN: P-W1 line replaced (the `--status` flag does not exist); new section "Decisions recorded 30-10-26" with W8d2 Q1-Q6 and the W8f choices. SPEC: change-log row and a section with the same decisions, including that `x_pool_size` reads `len(x_accounts)` bounded by `x_pool_max`.
- Review fixes applied: (1) health table replaced with the real model; (2) uv behaviour tested; (3) Linux cleaner made recursive and bounded; (4) Windows `/tmp` claim corrected; (5) Windows-first; (6) P-W1 replaced; (7) auto-logon not claimed as required.

## 4 Files changed

In `process/general-plans/active/narrative-baskets_02-10-26/`: the guide (new), this report (new), the collector PLAN and SPEC (edited: decision records, P-W1).

## 5 Commits

Two commits on `claude/w8e2-host-guide` (first: guide and report; second: review fixes and decision records). Draft PR #194.

## 6 Tests run

No repo tests (docs). Local evidence, all in throwaway directories that were removed:
- uv 0.12.21, throwaway project: `uv sync --group xreader` installs; `uv run --frozen` without the group retains it; `uv run --frozen --exact` removes it; `uv run --frozen --group xreader` reinstalls it.
- GNU find under Git Bash: `-delete` fails with "Directory not empty" on a nonempty `twscrape-*` directory; `-exec rm -rf -- {} +` removes it and leaves an unrelated sibling.
- `PureWindowsPath('/tmp')` has root `\` and no drive.
Code facts checked by reading: env vars and flags in `attention_pc_refresh.py`, `twscrape_reader.py`, `probe_pc_sources.py`; route `get_sources`; health model on `origin/claude/w8e2-health-line`.

## 7 Tests NOT run

No guide command was run on the host (powercfg, schtasks, setx, w32tm, systemd, timedatectl, uv in this repo). Not proven: the systemd unit and cleaner on Linux, the boot-time task with the DPAPI key helper and Tailscale wait, where the library's dumps actually land on Windows (inferred from path semantics), the health route against the merged health code, P-W1.

## 8 Deviations

- The uv probe used a throwaway project, not this repo's lock; the repo's Windows launcher was judged by that result and by the scout's report, so no product fix is claimed or needed on uv 0.12.21.
- SPEC rule 18(a) and AC47 wording of `x_pool_size` was not rewritten in place; a dated note in the SPEC gives the reading. The planner may fold it in later.
- SPEC Annex J items 1 and 3 still describe a browser session for auto-start/auto-login; T179 already says that applied only to a browser reader, and the guide follows T179. Item text not edited.

## 9 Blockers

None. Owner: choose the OS and the boot/log-on option; run P-W1 after PR #195 and the worker land.

## 10 Follow-up

- Recheck guide section 6 field names if PR #195 changes before merge.
- Decide whether the registry/current-state docs (owned by open PR #190) need the T212 and W8f decisions; not touched here.

## 11 Context cost

Read: envelope, PLAN W8e/W8e2, SPEC Annex J and rules 18-20, AC38/39/47/52/53, W8d2 report heading 10, `deploy/*.ps1`, `twscrape_reader.py`, `attention_pc_refresh.py`, `probe_pc_sources.py`, `discovery.py` router, and the health models on PR #195's branch. Moderate.
