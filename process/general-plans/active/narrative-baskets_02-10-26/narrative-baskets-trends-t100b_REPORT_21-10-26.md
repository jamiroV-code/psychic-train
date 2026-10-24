---
name: report:narrative-baskets-trends-t100b
description: "T144 report: FAST MODE PLAN for T100b/T100c (how the daily Google Trends pull is batched). Owner summary, then the 11-heading worker report."
date: 21-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: report
---

# T144 report: Trends batching plan (T100b, T100c)

## Owner summary (plain words)

- **Answer to your key question: you are right.** The trigger compares each coin only with its own past (last 7 days against the days before). Multiplying a coin's whole series by any constant changes nothing in that comparison, so we do not need to compare coins with each other on Trends, and we do not need the Bitcoin anchor of the T120 SPEC. Nothing in the code reads a Trends "level" at all. The only thing a coin needs is enough resolution and ONE scale across the roughly 97 days a window compares.
- **The anchor would make things worse.** Dividing a small coin by Bitcoin turns "1 out of 37" into rounding noise, and any Bitcoin move would push every coin up or down.
- **Recommended design: ask Google about one coin at a time.** A coin alone always peaks at 100, which is the best resolution possible. About 43 requests a day now (up to 75 when more coins get a keyword), 3 to 6 minutes at 3 seconds apart. Each daily run replaces the whole stored series for a coin with the 100 days it just pulled, so there is nothing to stitch. Each day's pull is also archived by date, so history can later be read "as it was that day".
- **"Too little interest":** alone, a coin cannot "stay at 0 or 1" (it peaks at 100), so the rule looks at the coin's own series instead: mostly zero days or a very low median means the coin is marked missing (never 0). The two numbers in the rule are placeholders until you run the probe.
- **12 risky names** (TRON, Ondo, Morpho, Internet Computer, Shiba Inu, Pepe coin, BNB, Cronos, Hedera, Chainlink, Aptos, Solana) are not fetched by plain name; they wait for a topic id from the checker.
- **What you decide / do:** (1) approve or overrule the departures from the SPEC (no anchor, replace the whole series, explicit 100-day range, archive); (2) ENTER EXECUTE MODE for T100b (estimate 5 to 7 USD, ask at 6, cap 10); (3) run the PC probes in the PLAN section 8 (two work today, the single-coin one needs T100b first); (4) T100c touches `.github/` and only starts after your separate approval. This session wrote no workflow text.

PLAN: `process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-trends-t100b_PLAN_21-10-26.md` (Gate: PASS for T100b).

## 1 Task ID
T144 (FAST MODE for T100b and T100c planning), branch `claude/t144-trends-t100b-plan` from `origin/main` 4675f82.

## 2 Outcome
done (docs only; no EXECUTE; Google not contacted).

## 3 Summary
- Read the T120 SPEC, T121 PLAN, the T100a code, the Trends store and discovery code.
- Answered the key question from code: `discovery._source_change` and `attention_ratio` are per-coin ratios, so scale constants cancel; no consumer reads a Trends level.
- Compared four designs (alone, tiers, anchor ladder, SPEC) with request counts, seconds, resolution, stability, interest rule, failure handling, tests.
- Recommended design 1 (one coin per request) with replace-series store mode, explicit 100-day range, per-pull archive, sparsity rule, name-risk skip.
- Wrote a COMPLEX PLAN with slices T100b (opus) and T100c (blocked on owner approval), red-first test names (45), gates G1 to G12, baselines on fresh main, owner probes.
- Plan validator: 0 failures. Gate: PASS for T100b.

## 4 Files changed
- `process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-trends-t100b_PLAN_21-10-26.md` (new)
- `process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-trends-t100b_REPORT_21-10-26.md` (new)
No code, no `.github/`, no registry edit.

## 5 Commits
Branch `claude/t144-trends-t100b-plan`; SHA in the draft PR (one commit). Base `origin/main` 4675f82.

## 6 Tests run
All on 4675f82, 2026-10-21 UTC, `UV_FROZEN=1`:
- `uv run --project api pytest api/ -q`: 1861 passed, 1 skipped, 5 deselected, 2 warnings, 144.6 s.
- `uv run --project api pytest api/tests/data/attention api/tests/data/test_pytrends_adapter.py api/tests/scripts/test_backfill_pytrends_history.py -q`: 195 passed.
- `uv run --project api pytest api/tests/scripts -q`: 346 passed.
- `uv run --project api pytest api/tests/analytics/attention -q`: 281 passed.
- store + trends tests: 17 passed; workflow guards: 22 passed.
- `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs <PLAN>`: 0 failures, 0 warnings (first run found 2 failures, missing Acceptance Criteria and checklist sections, fixed).
- `git diff --check`: exit 0.
- `node .claude/skills/vc-audit-context/scripts/validate-context-discovery.mjs`: one failure `.agents/skills does not resolve to .claude/skills`, the known baseline, not from this change.

## 7 Tests NOT run
Web tests, tsc, Playwright (no web change). Any live Google call (forbidden; owner probes in the PLAN). `validate-backlog-notes`, agent-parity (known older baseline failures, unrelated).

## 8 Deviations
None from scope. Content departures from the T120 SPEC are deliberate and listed in PLAN section 3 for the owner: no anchor or per-day ratio, replace-series instead of replace-window, explicit 100-day range, per-pull archive.

## 9 Blockers
- T100c needs the owner's approval of the `.github/` change before any worker starts it.
- The probe for single-coin resolution needs the new `--alone` option, which belongs to slice T100b; until then only P-CHK and P-BATCH can run.
- UNVERIFIED live facts: explicit 100-day range returns daily rows; 75 requests at 3 s avoid a 429; GitHub runners are answered.
- Registry update request: add T100b (opus, ask 6, cap 10 USD, branch `claude/t100b-trends-fetch`) and T100c (sonnet, ask 3, cap 5, owner approval of `.github/` required first).

## 10 Follow-up
- T100b EXECUTE after the owner's ENTER EXECUTE MODE.
- Owner: run P-CHK now; run P-RES after T100b merges; set the two interest-rule numbers.
- T100c after approval (workflow step, probe record, panel line).
- Later task: history reader that uses the pull-date archive for point-in-time (T103/T105).

## 11 Context cost
Loaded: CLAUDE.md, T120 SPEC (about 22 KB), T121 PLAN (parts), weighted-signal SPEC (grep), `trends.py`, `store.py`, `trends_keywords.py`, `probe_trends.py`, `trends_cli_common.py`, `check_trends_keywords.py` (head), `discovery.py` (parts), `ratio.py`, `series.py`, `registry.py`, `refresh_attention.py` (parts), `pytrends_adapter.py` (parts), `master-planner.md` section 8 and 9, `operating-instructions.md` (grep), `current-state.md` (head). Approximate 75,000 tokens read. Opened on demand: master-planner.md, operating-instructions.md. Tools: file tools, Bash, Skill, Agent, GitHub MCP; no subagents were spawned. Cost well under the 7 USD ask.
