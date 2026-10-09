ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate, do not spawn sessions, load only the files listed below; this overrides any orchestrator wording in CLAUDE.md. Capped lane (plan S7 "Lane"): at most 3 sonnet subagents, 15 USD, one level, each listed in report heading 11.

Task: T38 (batch 2, slice S7) - BTC leg chart on the BTC chart with confirmed legs over all cached BTC history, the D-14 estimate label (headed "Estimate (rule over the numbers shown)", inputs shown), and the /api/regime/legs + new /api/regime/btc-legs inline-fetch fix (S8 open item a).
Acceptance: all G-S7-* pass; P-S7-1 (live PC check) stays a user probe (review). The chart states the span it covers; no backfill code (Q6).
Owned / Forbidden / Design / Tests: exactly as in the plan's S7 section incl. Risks-accepted residual: the BTC OHLCV read is cache-only, FRED and DefiLlama may still fetch on TTL expiry; both cache-only tests stub the composite builders; _leg_inputs uses only .df. Any other test that breaks: stop at needs_input.
Advisories: (k) std = 0 (T = 0) is N/A with a reason like the NaN std, never rising/falling/flat; (m) the S7 word-scan test uses the full S7-verdict-words list incl. outperforming|underperforming; use Series.std() (ddof 1) and integer age comparisons.
Base: main after S6 (merge 8858469; later commits are data snapshots). Baselines: pytest 934/2/5/0, vitest 239 in 32 files. Expected S7 end: 951 pytest, 251 vitest in 34 files. A differing count: stop at needs_input.
Branch: claude/t38-s7-btc-leg-chart (from main)
Read (plan, re-derive with `grep -n '^## \|^### '`): process/general-plans/active/screener-batch2_04-10-26/screener-batch2_PLAN_04-10-26.md lines 39, 44, 47-50, 52, 54-61, 178-198, 280-281, 298-303, 338, 340-350, 355-357, 359-360, 365-366, 380-381, 383-385, 387, 389. Nothing else.
Tests: RT3; record red runs first (UV_FROZEN=1 on every pytest); each gate once after the last edit. Spike results in report heading 9.
Budget: 100 tool calls, 80 min, 4 CI polls, 2-5 USD. Retry: 2 fix cycles; same failure twice stops.
Report: process/general-plans/active/screener-batch2_04-10-26/screener-batch2-s7_REPORT_09-10-26.md (11 headings; 6 = gates with SHA and UTC).
Stop at review if: irreversible or outward action, scope expansion, doubt, a diff touching CLAUDE.md, AGENTS.md, README.md, .claude/, .github/, deploy/, or a file outside Owned.
Autonomy: edit Owned, run gates, push, open PR, wait for CI. Never deploy; no secrets.
