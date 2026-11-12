---
name: momentum-screener_17-09-26-RFC-002-phase-report
feature: momentum-screener
phase: RFC-002
date: 18-09-26
generated-by: orchestrator (post-EVL, this session)
---

## EVL HANDOFF SUMMARY

```yaml
EVL HANDOFF SUMMARY:
gates_green: ["api/tests/analytics/test_liquidity_composite.py", "api/tests/analytics/test_leg_boundary.py",
  "api/tests/analytics/test_benchmark.py", "api/tests/routers/test_regime.py (via direct handler call)"]
known_gaps:
  - {gate: "api/routers/regime.py (FastAPI TestClient / real app wiring)", backlog_note_path: "process/general-plans/active/momentum-screener_17-09-26/stub_rfc002-backend-integration-tests_18-09-26.md (not yet written)"}
  - {gate: "live adapter fetch paths (liqtide_adapter.py, fred_adapter.py, defillama_adapter.py)", backlog_note_path: "process/general-plans/active/momentum-screener_17-09-26/stub_rfc002-backend-integration-tests_18-09-26.md (not yet written)"}
  - {gate: "api/scripts/backtest_leg_boundaries.py (2017 / 2020-21 cycles, Hybrid gate, AC-8)", backlog_note_path: "process/general-plans/active/momentum-screener_17-09-26/stub_rfc002-backend-integration-tests_18-09-26.md (not yet written)"}
  - {gate: "pnpm --filter web test -- LegTimelineBanner", backlog_note_path: "process/general-plans/active/momentum-screener_17-09-26/stub_rfc002-frontend-tests_18-09-26.md (not yet written)"}
follow_up_stubs:
  - {section: "RFC-002 backend (FastAPI/live adapters/backtest)", stub_path: "process/general-plans/active/momentum-screener_17-09-26/stub_rfc002-backend-integration-tests_18-09-26.md (not yet written — see Resume and Execution Handoff)"}
  - {section: "RFC-002 frontend (LegTimelineBanner)", stub_path: "process/general-plans/active/momentum-screener_17-09-26/stub_rfc002-frontend-tests_18-09-26.md (not yet written — see Resume and Execution Handoff)"}
context_partial: []
preliminary_packet_path: process/general-plans/reports/momentum-screener_17-09-26-RFC-002-phase-report.md
closeout_classification: "Keep in active/ — needs further testing"
```

## Delta Check

Section 2 (RFC-002, items 30–46): all 17 checklist items implemented and checked off in `momentum-screener_PLAN_17-09-26.md`. 10 items independently verified green this session via a real pytest run (29 passed: `test_liquidity_composite.py`, `test_leg_boundary.py`, `test_benchmark.py`, `test_regime.py`). The remaining items are code-complete but genuinely unexecuted — same root cause as RFC-001 (this cloud sandbox's package-registry blockage: `pypi.org` returns `403 Host not in allowlist`, blocking `duckdb`/`ccxt`/`pandas-ta-classic`/`pyarrow`/`fastapi` installation) plus one item (the 2017/2020-21 backtest) that additionally needs live network access this sandbox does not have.

## Step 3 — Gate Re-verification

This session's environment does not expose a literal `vc-execute-agent` subagent type in the Agent tool, so EXECUTE was performed directly by the orchestrator rather than delegated to a spawned subagent and re-checked by a second reader — a standing deviation from the plan's "no inline execution" rule, carried forward from RFC-001 and disclosed again in `## Deviations` rather than silently repeated. The 29 passing tests were therefore run once, by the same actor that wrote them, not independently re-verified by a separate pass. Per `09-execute.md`'s DONE_WITH_CONCERNS handling, this is treated as uncertain by default: the user's own real-dependency test run (as happened for RFC-001, which caught three real bugs the sandbox could not — see RFC-001 Deviations #8, #9, #12) is the next required independent check, not yet performed.

## Step 5 — Classification

**"Keep in active/ — needs further testing."**

Rationale (Hard E2E classification rule, same as applied to RFC-001's first pass): RFC-002 has real developed behavior in `api/routers/regime.py` (FastAPI layer), three live-network adapters, a backtest script, and one frontend component (`LegTimelineBanner.tsx` + its 4-test suite) — all written to spec, all with **zero passing fully-automated execution** this session. This holds regardless of how clean the 29 pure-logic tests are, per this plan's own precedent. Two follow-up stubs are needed (see Resume and Execution Handoff — not yet written as separate files this pass, flagged explicitly so they aren't silently dropped) rather than blocking RFC-003 from starting, consistent with RFC-001's handling.

## What Is Now Functional and Testable

- Leg-boundary candidate detection (`leg_boundary.detect_candidate_boundaries`) — expanding z-score on rate-of-change, run-length sustained-threshold logic, first-bar-of-run extraction — real, tested, including a flat-series no-false-positive case.
- Structure-shift confirmation (`leg_boundary.confirm_boundaries`) — higher-high/higher-low (and mirrored lower) structure check within a bounded confirmation window; confirmed subset always a subset of candidates by construction (ADR-3) — real, tested, both directions (confirms when structure shifts, does not confirm when it doesn't).
- Composite variant selection (`liquidity_composite.select_composite_variant`) — 2024-01-11 cutover boundary, and the "post-cutover but an input is missing that day" fallback to reduced — real, tested, 6 scenario cases.
- Reduced and full composite construction — expanding z-score, ROC windows, dollar/btc-dominance sign inversion, outer-join-then-skipna-average merge — real, tested.
- Regime-dependent benchmark selection (`benchmark.select_active_benchmark`) — "most recent event wins" tie-breaking between the latest confirmed boundary and the latest unconfirmed candidate — real, tested, including the specific case of a newer unconfirmed candidate reverting the benchmark to BTC after an older confirmation.
- `screener_board.py` now calls real leg-boundary computation instead of RFC-001's fixed-BTC stub; RFC-001's own screener-board tests were proactively patched to stay network-isolated (not broken, not discovered via failure — reasoned through the call graph before it could regress).

## What Is NOT Yet Proven

- Nothing requiring FastAPI, real network calls, or the Next.js/vitest toolchain has been executed even once: `api/routers/regime.py`'s actual HTTP wiring, all three adapters' live-fetch/retry/staleness paths (`liqtide_adapter.py`, `fred_adapter.py`, `defillama_adapter.py`), and `LegTimelineBanner.tsx` are written but unverified by any automated run this session.
- The 2017/2020-21 backtest (`api/scripts/backtest_leg_boundaries.py`, item 40, the Hybrid gate for AC-8) has not been run at all — its BTC-history CSV source URL could not be confirmed live (JS-rendered download table), and no live network + full toolchain were available together in this sandbox. This is the one RFC-002 gap that's more than "untested" — it's unattempted, and it directly gates AC-8's closure.
- `httpx`'s actual retry/backoff behavior against a real 429/timeout from LiqTide, FRED, or DefiLlama has not been exercised — only mocked failure paths were tested.
- No Agent-Probe visual pass of `LegTimelineBanner`'s confirmed/unconfirmed visual distinction has been done (no dev server available).

## Commit Timing Note

Per `09-execute.md`: "Never leave verified-working source changes uncommitted at phase close." This cloud sandbox has no git repository and no direct device shell access for this device; the normal `vc-git-manager` commit step runs against a local mirror built via the device bridge instead. Per the plan's own "Operational note for future device-bridge pushes," each pushed file is re-staged and spot-checked after `device_commit_files` reports success, rather than trusting the "written" response alone — see the commit step immediately following this report.
