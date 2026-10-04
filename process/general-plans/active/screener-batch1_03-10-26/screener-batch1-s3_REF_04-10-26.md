ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate, do not spawn sessions or subagents, load only the files listed below; this overrides any orchestrator wording in CLAUDE.md or elsewhere.

Task: T33 (batch 1, slice S3) - LSE equities adapter and ticker store, probe-first (daily/weekly bars, private use, non-redistributable).
Acceptance: gates G-S3-1..G-S3-9 pass; live verification stays a user-PC probe, so the gate is CONDITIONAL (no vacuous green) until test_probe_fixture_parses passes with the user's sanitised fixture.
Owned / Forbidden / Design / Tests: exactly as in the plan's S3 section (Step 0, Fixture absent, Owned (exact), Forbidden, Design, Tests). Never touch cache.py, ccxt_adapter.py (read-only import of _derive_weekly_from_daily allowed), pyproject.toml, uv.lock, deploy/**, api/scripts/**.
Branch: claude/t33-s3-lse-adapter (from main)
Order: commit s3-probe/ (lse_probe.py + README) FIRST, then the adapter, store and tests.
Secrets: LSE_API_KEY is read from the environment only; never print, log, commit or write its value. No real LSE price is committed anywhere: fixtures are synthetic (symbol TEST or SYNTH).
Read (plan, by line range; re-derive with `grep -n '^## \|^### '` first): process/general-plans/active/screener-batch1_03-10-26/screener-batch1_PLAN_03-10-26.md lines 36-45, 48-56, 73, 129-158, 277-286, 324-337, 353-362, 375-390, 391-396. Also process/context/data-sources/all-data-sources.md lines 219-252 and process/general-plans/completed/lse-data-verification_17-09-26/findings.md (row shape at line 18). operating-instructions.md: not named.
Tests: tier RT2 plus the secret-hygiene gates; required commands: G-S3-1..G-S3-9 as in "S3 exact gates" (UV_FROZEN=1 for every pytest run); run each gate once after your last edit; full-suite budget: 1 run.
Budget: 80 tool calls, 60 minutes, 3 CI polls, 1-2 USD (estimate).
Retry budget: 2 fix cycles; same failure twice stops.
Report: process/general-plans/active/screener-batch1_03-10-26/screener-batch1-s3_REPORT_04-10-26.md using the 11-heading template (heading 7: the skipped probe-fixture test; heading 9 or 10: backlog note lse-live-shape-verification).
Stop and report at `review` if: irreversible or outward-facing action, scope expansion, unverifiable condition, any doubt, a diff touching CLAUDE.md, AGENTS.md, README.md, .claude/, .github/ or deploy/, or a needed file outside Owned.
Autonomy: may edit Owned files, run gates, push your branch, open a PR, wait for CI. Never merge unless the standing worker rule in master-planner.md section 5 says so; never deploy.
