# Regime Dashboard — VALIDATE Findings (V1–V4)

**Date**: 24-09-26
**Plan**: `process/features/cycle-regime/completed/regime-dashboard_24-09-26/regime-dashboard_PLAN_24-09-26.md`
**Mode**: Simple (single feature, 2 packages: `api/`, `web/`; no container/infra lifecycle)
**Execution of fan-out**: sequential, in-session (Layer 1 + Layer 2 run inline, no sub-agents)

> **TL;DR** — Net gate **CONDITIONAL**: no blocking findings, 7 concerns. The biggest three:
> (1) the endpoint must read LiqTide from the archive only — `fetch_latest` always tries the network
> first (up to 3 × 10 s); (2) synced time axes across panels with different start dates will drift
> apart in lightweight-charts unless every panel shares one date grid (whitespace points);
> (3) the existing composite's "28-day" windows count **rows**, and FRED daily rows are business
> days, so they are really ~5.5 weeks — the new module must use calendar windows.
> fredapi: not adopted for this plan (needs an API key, no release since May 2024); worth a
> backlog note for point-in-time (ALFRED) data in the future insights engine.

---

## V1 — Pre-Check

| Check | Result |
|---|---|
| Plan file readable | ✅ PASS |
| `validate-plan-artifact.mjs --strict` | ✅ PASS — 0 failures, 0 warnings |
| Referenced read-only paths exist (`liquidity_composite.py`, `leg_boundary.py`, `fred_adapter.py`, `defillama_adapter.py`, `liqtide_adapter.py`, `cache.py`, `routers/regime.py`, `models/regime.py`, `seed_e2e_cache.py`, `snapshot_liqtide.py`, `backfill_primaries.py`, `MiniChart.tsx`, `RelativePerformanceChart.tsx`, `DeadDataNotice.tsx`, `web/lib/api/screener.ts`) | ✅ PASS — all resolve |
| Blast Radius / Public Contracts present | ✅ PASS |
| Existing validate-contract | none (placeholder only) |
| Umbrella plan with `## Stable Program Goal` | none found → BRANCH A (goal block goes in this plan) |
| `lightweight-charts` installed version | not readable (pnpm hard-link) — `package.json` pins `^5.0.0`; Stage 0 of RFC-005 confirms |

---

## V2 — Layer 1 Dimensions

### Infra/setup fit — CONCERN (confidence HIGH)

| Finding | Severity | Proposed fix |
|---|---|---|
| `liqtide_adapter.fetch_latest` is network-first (not cache-first): every call tries `latest.json` with 3 retries × 10 s timeout before falling back to the archive. ADR-4/ADR-6 let the endpoint call it "opportunistically" → a slow or down LiqTide makes `/regime` hang up to ~30 s | CONCERN | P1: endpoint and `components.py` read LiqTide **only** via `cache.read_liqtide_history()` + raw archive; fetching stays in the scheduled snapshot |
| FRED and DefiLlama adapters are cache-first with a 6 h TTL — fine for the endpoint; but a cold cache on first load triggers 5 sequential CSV downloads (same cold-start class as the backlogged board latency) | CONCERN | E1: endpoint calls adapters as today; RFC-004 records cold vs warm timing; if cold > 10 s, add a note to `board-endpoint-cold-start-latency_20-09-26.md` rather than blocking |
| `.gitignore` `!api/data/cache/liqtide/` un-ignores the whole folder, so `raw/` and `backfill_*.parquet` are tracked | ✅ PASS | — |
| Task Scheduler job runs `uv`; Scheduler's environment may not have `uv` on PATH | CONCERN | P2: Ops Runbook uses the absolute path to `uv.exe` (`where uv`) and "Start in" = repo root |
| Ports/CORS unchanged (API 127.0.0.1:8000, web 3000; E2E 8001/3100) | ✅ PASS | — |

### Test coverage — CONCERN (confidence HIGH)

| Finding | Severity | Proposed fix |
|---|---|---|
| `isolated_cache` fixture is **opt-in** (conftest docstring, after the live-cache incidents). Adding a raw-JSON write inside `fetch_latest` means any existing or new test that drives `fetch_latest` without that fixture writes into the real `api/data/cache/liqtide/` (which is git-tracked) | CONCERN | E2: before wiring the raw write, grep `api/tests` for `fetch_latest`/`write_liqtide` callers; every such test must request `isolated_cache`. New RFC-001/002/003/004 tests request it too |
| vitest mocks `lightweight-charts` with a minimal chart object (`addSeries`, `removeSeries`, `applyOptions`, `remove`). The sync code needs `timeScale().subscribeVisibleTimeRangeChange/setVisibleRange` and `subscribeCrosshairMove/setCrosshairPosition` | CONCERN | P3: RFC-005 test stage extends the mock with those methods and asserts subscriptions are wired and cleaned up on unmount |
| Sync behaviour itself (range + crosshair across 7 real charts) cannot be proven in jsdom | CONCERN | Covered by Playwright (RFC-006) + Agent-Probe walkthrough — already in plan; P3 makes the E2E assert that all panels report the same visible range after a zoom |
| Golden-value tests planned per transform | ✅ PASS | — |
| Baseline count: plan cites 179 passed (all-context, 20-09-26); `all-tests.md` still says 165 | ✅ PASS (context drift only) | Update `all-tests.md` at UPDATE PROCESS |

### Breaking changes — PASS (confidence HIGH)

| Finding | Severity | Proposed fix |
|---|---|---|
| All API changes additive; `/api/regime/legs`, `LegBoundaryResponse`, `CurrentLegState`, both composites untouched | ✅ PASS | — |
| `fetch_latest` return type unchanged; new side effect skipped on `dry_run` | ✅ PASS | — |
| New module does not import from or modify `leg_boundary.py` | ✅ PASS | — |

### Security surface — PASS (confidence HIGH)

| Finding | Severity | Proposed fix |
|---|---|---|
| No keys, no auth, no user data; local bind unchanged | ✅ PASS | — |
| Farside is scraped HTML → terms/robots must be checked before use; plan already gates this at RFC-001 Stage 0 and records `redistributable` | ✅ PASS | — |
| fredapi would introduce the first FRED API key (a secret in `.env`) — see fredapi assessment | ✅ PASS (not adopted) | — |

---

## V2 — Layer 2 Sections

### RFC-001 — archive + backfill + research — CONCERN

- **Mechanical feasibility**: `cache.py` has `liqtide_payload_path`/`write_liqtide_payload` to mirror; `fetch_latest` has a single fresh-parse branch to hook; `LiqTidePayload.raw` already carries the JSON. Feasible.
- **Gaps**: ADR-4's "endpoint fetch as second opportunistic path" contradicts the infra finding → remove (P1). Raw JSON should be written compact + UTF-8, one file per `generated_utc[:10]`.
- **Conflicts**: none.
- **Highest-risk edit + mitigation**: raw write inside `fetch_latest` hitting the live, git-tracked archive from tests → E2.
- `VC-FEASIBILITY-PROBE-NEEDED: live latest.json carries tide_series and metrics.*.series with usable depth, and tide_index.value is the 0–100 score — cost-class: network-read` → already Stage 0 of RFC-001; stays there.

### RFC-002 — component maths — CONCERN

- **Mechanical feasibility**: inputs available via `fred_adapter.fetch_series`, `fetch_net_liquidity`, `defillama_adapter.fetch_stablecoin_supply`, `cache.read_liqtide_history`. Feasible.
- **Gaps / conflicts**:
  1. **Row windows vs calendar windows.** `liquidity_composite._roc` uses `pct_change(periods=N)` with comments saying "calendar days", but FRED daily series (RRPONTSYD, DTWEXBGS) have business-day rows and `fetch_net_liquidity` is indexed on RRP's business-day rows. So "28 days" is ~28 business days ≈ 5.5 weeks, and "30 days" ≈ 6 weeks. The new module must compute changes against the value **as of date − N calendar days** (`merge_asof` backward). → P4. The existing composite is out of scope; logged as a backlog note (P7) because it affects leg-boundary numbers.
  2. **"Weekly stays weekly" conflicts with the existing net-liquidity series**, which is already daily with WALCL/TGA carried as-of the latest weekly reading (`merge_asof backward`). That is as-of alignment, not invention, and it is what the leg-boundary composite uses. → P5: keep the as-of daily series, say so in the drill-down ("WALCL/TGA as of latest weekly release"), and reword Rule "no forward-fill" to "no fill beyond as-of alignment, always labelled". Fix the RFC-002 example in the Phased Execution Workflow accordingly.
  3. **Expanding z-score with `min_periods=5`** makes the first weeks of short series (BTC dominance from ~2025-06, ETF flows from 2024-01) swing wildly. → P6: `min_periods` = 90 observations for normalisation; earlier points show the impulse but no contribution (reason: "warming up").
- **Highest-risk edit + mitigation**: the calendar-window helper — golden tests with a business-day fixture that includes a holiday gap.

### RFC-003 — ETF flows adapter (conditional) — PASS

- Gated on Stage 0 verdict; adapter pattern well established. No gaps.

### RFC-004 — endpoint — CONCERN

- **Mechanical feasibility**: `routers/regime.py` has a prefix router; adding `/components` is additive. `test_regime.py` documents the TestClient fallback. Feasible.
- **Gaps**: ADR-6 wording allows a live LiqTide call (P1). Response-time target needs a cold and a warm number (E1).
- **Conflicts**: none.
- **Highest-risk edit**: none beyond P1.

### RFC-005 — `/regime` page — CONCERN

- **Mechanical feasibility**: `MiniChart` shows the v5 `createChart` + `addSeries(LineSeries)` pattern; `getJson` reusable. Feasible.
- **Gaps / conflicts**:
  - `VC-FEASIBILITY-PROBE-NEEDED: lightweight-charts v5 setVisibleRange on a chart whose data starts later than the requested range clamps to the data, so panels with different first dates (net liquidity 2002, BTC dominance ~2025) will not line up; setCrosshairPosition needs a time present in that chart's data — cost-class: browser-run`. Known remedy: give every panel the **same date grid**, using whitespace points (`{ time }` with no value) where a component has no value. This keeps gaps visibly empty (no fill) and makes range + crosshair sync exact. → P3 (API returns `grid_dates` once; panels pad with whitespace) and E3 (probe in Stage 0 before building all panels).
  - Payload: net liquidity back to 2002 on a daily grid is ~6,000 dates × 7 series; still well under 1 MB of JSON, acceptable.
- **Highest-risk edit + mitigation**: the sync hook — build it once in `RegimeDashboard`, prove on two panels first (E3).

### RFC-006 — E2E — CONCERN

- **Gaps**: the seeder only writes OHLCV + watchlist. The regime endpoint will reach the network in E2E unless the seeder writes FRED/DefiLlama parquet (fresh mtime inside the 6 h TTL), a LiqTide archive row + raw JSON, and ETF fixture if built. → P8.
- **Highest-risk edit**: seeder format drift — the playwright-e2e report's defect was exactly a fixture written in a shape the reader didn't expect. Mitigation: seeder writes via the same `cache.write_*` functions the adapters use.

---

## V3 — Synthesis

### Layer 1 dimensions

| Layer 1 dimensions | Status |
|---|---|
| Infra fit | CONCERN |
| Test coverage | CONCERN |
| Breaking changes | PASS |
| Security surface | PASS |

### Layer 2 sections

| Layer 2 sections | Status |
|---|---|
| RFC-001 — archive + backfill + research | CONCERN |
| RFC-002 — component maths | CONCERN |
| RFC-003 — ETF flows adapter | PASS |
| RFC-004 — endpoint | CONCERN |
| RFC-005 — `/regime` page | CONCERN |
| RFC-006 — E2E | CONCERN |

**Totals: 0 blocking / 7 CONCERNs / 3 PASSes**

**→ Net gate: CONDITIONAL**

No contradictions between dimensions. Vacuous-green check: every developed behaviour has a
Fully-Automated or Hybrid gate; chart sync relies on Playwright (Fully-Automated) plus a
walkthrough, so no behaviour rests on a known gap alone.

---

## Section III — Test Gates

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-1 | raw JSON written once, never overwritten, skipped on dry run | Fully-Automated | `api/tests/data/test_liqtide_raw_archive.py` | B |
| AC-1 | scheduled task produces next-day file | Agent-Probe | user lists `api/data/cache/liqtide/raw/` next morning | A |
| AC-2 | payload history extracted to backfill parquet | Hybrid | `test_backfill_liqtide_series.py` + DuckDB coverage query on live payload | B |
| AC-3 | six transforms match golden values, calendar windows | Fully-Automated | `api/tests/analytics/test_components.py` | B |
| AC-3 | sign conventions match LiqTide components | Hybrid | sign cross-check script over archived raw payloads | B |
| AC-4 | no NaN/0 stand-ins; as-of alignment only | Fully-Automated | `test_components.py` | B |
| AC-5 | coverage, 60% floor, 90-obs warm-up | Fully-Automated | `test_components.py` | B |
| AC-6 | ETF flows parse/degrade | Hybrid | `test_etf_flows_adapter.py` + `pytest -m integration -k etf` | B |
| AC-7 | endpoint shape, degradation, `/legs` unchanged, no live LiqTide call | Fully-Automated | `api/tests/routers/test_regime_components.py` | B |
| AC-8/9/10 | panels, readout, drill-down, gap text, sync wiring | Fully-Automated | vitest `web/components/regime/__tests__/*` | B |
| AC-8 | seven panels share one visible range after zoom | Fully-Automated | `web/e2e/regime.spec.ts` | B |
| AC-11 | real-cache walkthrough | Agent-Probe | user walkthrough checklist | A |

---

## Section IV — Proposed Plan Updates

| # | What changes | Where in plan | Why |
|---|---|---|---|
| P1 | Endpoint + `components.py` read LiqTide from archive only; drop "opportunistic fetch" | ADR-4, ADR-6, RFC-004 | `fetch_latest` is network-first, up to ~30 s |
| P2 | Runbook uses absolute `uv.exe` path + "Start in" repo root | Ops Runbook | Scheduler PATH differs from shell |
| P3 | Shared date grid: API returns `grid_dates`; panels pad with whitespace points; vitest mock gains sync methods; E2E asserts equal visible range | ADR-7, §11, RFC-005, RFC-006 | lightweight-charts clamps ranges to each chart's own data |
| P4 | All windows are calendar windows via as-of lookup, not row counts | ADR-2, RFC-002 | FRED daily rows are business days |
| P5 | Net liquidity uses existing as-of daily series, labelled; reword forward-fill rule; fix RFC-002 example | ADR-2, Rules, Phased Execution Workflow example | Conflict with `fetch_net_liquidity` |
| P6 | Normalisation warm-up = 90 observations; earlier points show impulse, no contribution | ADR-5, RFC-002 | Short series swing at `min_periods=5` |
| P7 | Backlog notes: (a) existing composite's row-count windows; (b) fredapi / ALFRED point-in-time data for the insights engine | new backlog notes | Out of scope, must not be lost |
| P8 | Seeder writes FRED/DefiLlama/LiqTide(/ETF) fixtures via `cache.write_*`, fresh mtime | RFC-006 | E2E would otherwise hit the network |

### Execute-Agent Instructions

| # | Instruction | Trigger condition |
|---|---|---|
| E1 | Record cold and warm response time for `/api/regime/components`; if cold > 10 s, append to the board cold-start backlog note, do not block | RFC-004 Step 4 |
| E2 | Grep `api/tests` for `fetch_latest` / `write_liqtide` callers; every one must use `isolated_cache` before the raw write is wired | RFC-001 Step 3 entry |
| E3 | Prove range + crosshair sync on two panels with different first dates before building all seven | RFC-005 Stage 0 |

### Backlog Artifacts

| Artifact | Location | What it tracks |
|---|---|---|
| `liquidity-composite-calendar-windows_24-09-26.md` | `process/general-plans/backlog/` | Row-count vs calendar windows in `liquidity_composite._roc` (affects leg boundaries) |
| `fredapi-alfred-vintages_24-09-26.md` | `process/features/cycle-regime/backlog/` | Point-in-time FRED data for honest backtests in the insights engine |

---

## fredapi assessment (user request)

| Question | Answer |
|---|---|
| What it is | Python wrapper around the official FRED/ALFRED web API; Apache-2.0; ~1.7k stars |
| Key needed? | **Yes** — free FRED API key. The repo currently uses the keyless `fredgraph.csv` export on purpose (data-sources Standing Rule 1, RFC-002) |
| Maintenance | Latest PyPI release 0.5.2 on 2024-05-05 — no release in over two years |
| Does the dashboard need anything it adds? | No. All four FRED series the dashboard uses (WALCL, WTREGEN, RRPONTSYD, DTWEXBGS) already arrive with full history, cache-first, through `fred_adapter.py` |
| What it would add | ALFRED vintages (`get_series_as_of_date`, `get_series_first_release`, `get_series_all_releases`): the value **as it was known on a past date**. That matters for the insights engine's history checks — scanning revised data can make a pattern look better than it was in real time (look-ahead). Also server-side date filtering and series search |
| Verdict | **Not for this plan.** Keep the keyless path. Revisit when the insights engine starts testing patterns against history; even then, calling the ALFRED REST endpoints from `fred_adapter.py` with `httpx` (already a dependency) avoids a stale wrapper. Logged as backlog note (P7b) |

---

## Execution strategy

RFCs are strictly sequential (each depends on the previous one's Stage 0 or outputs).
Recommendation: **sequential**, 1 executor agent, estimated 6 RFC cycles. Parallel sub-agents
would only help inside RFC-005 (panel components) and are not worth the coordination cost.
