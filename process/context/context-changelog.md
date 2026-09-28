---
name: context:context-changelog
description: "Historical 'Changes Since Last Update' entries moved out of all-context.md, oldest project history first"
keywords: history, changelog, past, changes, timeline, prior session, why, decision history
date: 28-09-26
---

# my_site - Context Changelog

Historical "Changes Since Last Update" entries moved out of `process/context/all-context.md` on
2026-09-28 to keep that file under its ~800-line guideline. The newest entry always stays in
`all-context.md`; when a new entry is added there, move the previous newest entry here (prepend it
above the existing entries, so this file stays newest-first, oldest at the bottom).

## Changes Since Last Update (2026-09-24 → 2026-09-25)

Small, self-contained bug fix on branch `claude/narrative-keyword-keying` (task folder now at
`process/features/narrative-mindshare/completed/narrative-keyword-keying_25-09-26/`) — not part of
the still-unmerged narrative dashboard work described below, but touches the same reader function.

- `[Correction]` **`api/analytics/narrative/trigger.py`'s `compute_narrative_categories` was
  reading pytrends/reddit history under the wrong key.** The adapters
  (`pytrends_adapter.py`/`reddit_adapter.py`) write cached rows keyed by `keywords[0]`, but the
  reader looked them up by `category_id`, so pytrends/reddit contributed nothing real to
  `/api/narrative/categories` under real (non-stubbed) conditions — `history.py`'s sibling read
  path already got this right. Fixed with a small `_source_history_key` helper; coingecko is
  unaffected (correctly keyed by `category_id`). Production effect confirmed via a before/after
  diff report: `trust_weight` 0.4→0.6 and `n_available` 1→3 for all 4 seed categories; no
  screener badge/`narrative_state` changes in the fixture scenarios. Golden contract fixture
  regenerated and confirmed byte-identical after user sign-off.
  See `narrative-keyword-keying_25-09-26/narrative-keyword-keying_REPORT_25-09-26.md` in the
  completed task folder for the full closeout.
- Testing: counts moved to **381 passed / 3 deselected** pytest, 75 vitest (12 files) — see
  `tests/all-tests.md` for the fresh-worktree `pnpm install --frozen-lockfile` (run inside `web/`,
  not the repo root) note discovered during this fix.
- **Reminder, still open:** the narrative dashboard feature (RFC-1..5 stage-0/plan work under
  `process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/`) lives on the
  separate, still-unmerged branch `claude/kind-tesla-tat3vo` (this worktree's branch,
  `claude/narrative-keyword-keying`, is based on it but is a distinct branch/worktree) — this
  keyword-keying fix's amendment note was added to that plan's AC-1 section directly.

## Changes Since Last Update (2026-09-24, narrative-mindshare `/narrative` dashboard)

Same day as the regime dashboard entry below, a second program shipped: the narrative-mindshare
`/narrative` dashboard (`process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/`),
all 6 RFCs code-complete and EVL-confirmed, committed and pushed to branch
`claude/kind-tesla-tat3vo` (HEAD `7ef8eb3`, 58 files, +5536/-4). This graduates the narrative
backend that shipped inside momentum-screener's RFC-003 into its own first-class feature — the
first time `narrative-mindshare/` (previously an empty `_GUIDE.md` placeholder, same as
`charting-indicators`/`cointegration-screener`) has real code. This also answers the earlier
`momentum-screener-vs-features` Open Question, but **only for narrative** — the narrative surface
(`api/analytics/narrative/`, `api/data/{pytrends,reddit,coingecko,hyperliquid_narrative}_adapter.py`,
`api/routers/narrative.py`) is now planning/documentation-owned by `narrative-mindshare/`, while the
rest of momentum-screener stays under `process/general-plans/`. No files moved — this is an
ownership/documentation change, not a code relocation.

- `[Product]` New route **`/narrative`**: one growing attention-history chart per tracked seed
  category (ai/rwa/l2s/memecoins), a comparison view, a change-in-attention view, a display-only
  Hyperliquid exchange-volume/new-listing proxy, and a visible data-quality caveat on every view.
  `web/app/narrative/page.tsx`, `web/components/narrative/{NarrativeDashboard,CategoryHistoryPanel,
  ComparisonView,ChangeInAttentionView,DataQualityCaveat,RedistributionBadge}.tsx`.
- `[Product]` New API: **`GET /api/narrative/history`** (`api/routers/narrative.py::get_history`,
  additive to `api/models/narrative.py`) — category-first response with per-category composite,
  comparison rank, change-in-attention delta, `coingecko-narrative` as a new composite slot
  alongside `pytrends`/`reddit`/`exchange_volume_share`, and the legacy CoinGecko-trending count
  shown for reference but excluded from the composite. `GET /api/narrative/categories` is
  byte-identical before/after (contract-snapshot-tested, including a newly-mapped-coin-in-trending
  scenario) — proven, not assumed.
- `[Product]` **Ninth adapter**: `api/data/hyperliquid_narrative_adapter.py` — keyless `ccxt`
  Hyperliquid perps via the existing `_exchange()` singleton, `redistributable=False` pending a
  user terms check, handles `k`-prefixed meme-perp symbols (`kPEPE`→`KPEPE`). See
  `data-sources/all-data-sources.md`.
- `[Product]` **Second scheduled workflow**: `.github/workflows/narrative-snapshot.yml` (cron
  `0 23 * * *`, 30 min before `liqtide-snapshot.yml`'s `30 23 * * *`; its own
  `concurrency: narrative-snapshot` group) runs `api/scripts/snapshot_narrative.py` nightly,
  forward-archiving one point per (source, category) to `api/data/cache/narrative/` (new
  `.gitignore` carve-out, same per-entry mechanic as `liqtide/`). AC-3 (the cron actually firing) is
  a user-PC step, same shape as the LiqTide precedent.
- `[Product]` **User-editable curated coin map, "option B"**: `api/data/narrative_category_map.json`
  (32 entries) drives a new `mapping.map_coin_to_narrative_category()` used only by `/history` and
  `/narrative`; the original 3-coin `LEGACY_COIN_CATEGORY_MAP` stays frozen and continues to drive
  `/categories`/`/screener` unchanged. This is the mechanism that keeps AC-1 byte-compatible while
  still widening coverage — see the plan's `## Post-EXECUTE Amendments` for the full ADR-7
  correction.
- `[Product]` pytrends' own `interest_over_time()` backfills a 269-day daily window per seed
  category on day one (`api/scripts/backfill_pytrends_history.py`, `--with pytrends` required, not
  a project dependency); every other source starts thin and grows forward only. Backfilled points
  are flagged `mixed_scale` in the composite/change figures because they're on a different
  Google-Trends request scale than the nightly 7-day window.
- `[Correction]` **Pytrends and Reddit's archived history is keyed by keyword, not category id** —
  `pytrends/AI crypto.parquet`, not `pytrends/ai.parquet` — matching how the pre-existing forward
  writers already worked. RFC-1's plan text assumed category-id keying; corrected in the plan's
  `## Post-EXECUTE Amendments`.
- `[Correction]` A real product bug was found and fixed by the E2E proof (RFC-6): a pandas
  `None`→`NaN` coercion in `history.py::_exchange_frames` 500'd `/history` from the second nightly
  archive day onward (fixed with `dtype=object`, regression test added). See
  `tests/all-tests.md` for the generalized lesson.
- `[Correction]` **Known pre-existing bug, found but not fixed in this program — since FIXED
  2026-09-25 (see the 2026-09-25 entry above, PR #2):**
  `trigger.py::compute_narrative_categories` reads pytrends/Reddit history by category id, but
  those adapters write under the keyword key (see above) — so `/categories`' own trigger never
  actually sees archived pytrends/Reddit history; it runs on CoinGecko alone. Predates this
  program (RFC-003 of momentum-screener). Fixing it changes `/categories`' output and needs its own
  deliberate AC-1 re-baseline — queued as a separate follow-up, not silently absorbed here.
- Testing: `pytest api/ -q` 392 passed / 3 deselected (was 294 pre-narrative); `pnpm --filter web
  test` 110 passed (16 files, was 75/12); `tsc --noEmit` exit 0; `cd web && pnpm test:e2e` 26/26
  passed, run twice (14 new `narrative.spec.ts` + 6 `regime.spec.ts` + 6 `screener.spec.ts`).
- **Known gap, carried forward, not closed this session:** AC-3 (cron firing) and AC-12 (real-cache
  walkthrough) have not run — this container's egress proxy blocks Google Trends, Reddit,
  CoinGecko and Hyperliquid, same constraint as the regime dashboard's AC-11. Two manual-first
  risk-pack review decisions (`harness/review-decision.json`,
  `harness/rfc-004/review-decision.json`) are `PENDING`. The narrative-dashboard plan stays in
  `active/` until the user completes the checklist in its Resume and Execution Handoff.

## Changes Since Last Update (2026-09-20 → 2026-09-24)

The regime dashboard (`process/features/cycle-regime/completed/regime-dashboard_24-09-26/`) shipped
across six RFCs, all code-complete and committed to `main` (`db8d854`), and all six are now
✅ VERIFIED — the user confirmed the AC-11 real-cache walkthrough on their PC on 24-09-26 ("all
seems fine"; see Open Questions for the one clarified item, a BTC-dominance data hole). This is the
second real feature after the momentum screener, and the first to live in
`process/features/cycle-regime/` (previously an empty `_GUIDE.md` placeholder).

- `[Product]` New route **`/regime`**: seven synced `lightweight-charts` panels (six liquidity
  components + one composite panel with two labelled lines — reproduced vs. LiqTide-published),
  a shared hover readout, per-panel drill-down, and a reserved 280px column for a future insights
  box. `web/app/regime/page.tsx`, `web/components/regime/{RegimeDashboard,ComponentPanel,Readout,
  DrillDown}.tsx`.
- `[Product]` New API: **`GET /api/regime/components`** (`api/routers/regime.py`,
  `api/models/regime.py`) — returns all six components + the composite, a shared `grid_dates`
  union for synced panels, per-point `gap_before` flags and per-series `max_gap_days`, gzip'd via
  `GZipMiddleware` in `api/main.py`. `/api/regime/legs` (the existing leg-boundary endpoint) is
  byte-for-byte unchanged.
- `[Product]` New analytics: `api/analytics/regime/components.py` + `components_response.py`
  compute the six impulses (net liquidity, stablecoin supply, broad dollar, ON-RRP, spot-ETF
  flows, BTC dominance) as calendar-window transforms, normalise with `sign × tanh(impulse/scale)`
  (LiqTide's own formula, reverse-engineered and matched to 4 decimals), and build both a
  reproduced composite (with coverage/60%-floor) and a passthrough of LiqTide's own published
  index for comparison. `liquidity_composite.py`, `leg_boundary.py` and the screener are untouched
  — this is a second, parallel maths path, not a replacement.
- `[Product]` **Eighth adapter**: `api/data/etf_flows_adapter.py` (Farside Investors, spot BTC-ETF
  daily flows, personal-use only, `redistributable=false`, at most one request per UTC day —
  LiqTide's own archive fills gaps between Farside fetches). See
  `data-sources/all-data-sources.md`.
- `[Product]` **LiqTide raw-JSON archive landed and is scheduled**: `cache.py` gained
  `write_liqtide_raw`/`read_liqtide_raw` (append-only, no-overwrite); `liqtide_adapter.fetch_latest`
  writes the full payload alongside the existing flattened parquet row. This is scheduled, not
  manual — see the `.github/workflows/` correction below.
- `[Correction]` **`.github/workflows/` is no longer empty.** Earlier versions of this file said
  "no CI/deploy config exists" — that was true through 2026-09-20 but is stale now.
  `.github/workflows/liqtide-snapshot.yml` runs nightly at 23:30 UTC, executes
  `snapshot_liqtide.py`, and commits `api/data/cache/liqtide/` to `main` — discovered mid-session
  on 2026-09-24 (it had already captured 09-21 through 09-24 by the time this was found). This is
  the **only** scheduled fetch of LiqTide; the Windows Task Scheduler step in the regime plan's Ops
  Runbook is consequently not needed. Deployment/CI beyond this one workflow is still open — see
  Open Decisions.
- `[Correction]` **The LiqTide full-vs-reduced composite comparison open question (raised
  2026-09-20) is now substantially addressed, not fully closed.** RFC-001/002 didn't wait for the
  archive to accumulate years of history the way `compare_composite_variants.py` needed — instead
  they reproduce LiqTide's six components independently from FRED/DefiLlama/Farside primaries
  (ADR-1 in the regime plan) and show LiqTide's own published index as a second line for direct
  visual/statistical comparison wherever both exist. A real-data check found 5/6 components exact
  and Pearson r = 0.964 against LiqTide's published index. This doesn't replace the original
  archive-accumulation approach (still running nightly, still the only way to ever get true
  pre-archive LiqTide history) — it's a second, faster path to the same "do our numbers agree with
  theirs" question. See Open Questions for what's still open (real-cache walkthrough, ETF/BTC-dom
  depth limits).
- Testing: full-suite counts changed materially — see the amendment to `tests/all-tests.md`
  pointer below; **294 pytest passed / 2 deselected, 75 vitest passed (12 files, 0 failed), 12/12
  Playwright** (6 new `regime.spec.ts` + 6 existing `screener.spec.ts`), run twice.
- **Known gap, carried forward, not closed this session:** AC-11 (the real-cache user walkthrough)
  has not run — this container's egress proxy blocks FRED/DefiLlama/stablecoins.llama.fi (403), so
  it must run on the user's own PC. The regime-dashboard plan stays in `active/` until that
  confirmation lands; see the plan's Resume and Execution Handoff section for the exact PC steps.

## Changes Since Last Update (2026-09-17 → 2026-09-20)

The 2026-09-17 version of this file was written from the setup interview, before any code
existed, and said so explicitly ("no application code exists yet"). That is no longer true —
real application code has landed and this update replaces intentions with observations. `[Product]`

- `[Product]` `api/` (FastAPI, Python 3.12, uv) and `web/` (Next.js 15, pnpm) both exist and are
  substantially built out — see Repository Structure below.
- `[Product]` First real feature shipped: a relative-strength **momentum screener** board
  (`process/general-plans/active/momentum-screener_17-09-26/`), with a locked SPEC, a Complex
  plan, and multiple completed RFCs. It is tracked under `process/general-plans/`, not under any
  of the four `process/features/*` folders named below — see Open Questions.
- `[Product]` Seven provider adapters exist under `api/data/`: `ccxt_adapter.py`,
  `coingecko_adapter.py`, `defillama_adapter.py`, `fred_adapter.py`, `liqtide_adapter.py`,
  `pytrends_adapter.py`, `reddit_adapter.py` — all behind the common adapter pattern described
  under Key Patterns.
- `[Product]` Macro liquidity is no longer just "leading candidate: LiqTide" — RFC-002 built
  **both** paths the data-sources group described: consuming the LiqTide endpoint directly
  (`liqtide_adapter.py`) and reproducing the composite from FRED primaries
  (`fred_adapter.py`, WALCL/TGA/RRP/broad-dollar/reserves via FRED's **keyless** `fredgraph.csv`
  export — no API key, matching data-sources' Standing Rule 1).
- Testing strategy is resolved, not deferred: `pytest` for `api/` (with an `integration` marker
  gating real-network tests, deselected by default) and `vitest` + Playwright for `web/`. See
  `tests/all-tests.md`.
- Persistence (Parquet + DuckDB) and package managers (pnpm/uv) were already settled on
  2026-09-17 and are now confirmed in use (`api/data/cache.py`, `api/uv.lock`,
  `web/pnpm-lock.yaml`).
- Equity data provider remains genuinely unresolved — no equity adapter exists yet in `api/data/`.
- Deployment target remains genuinely unresolved — no `.github/workflows/` or other CI/deploy
  config exists.
- The repo was **not a git repository** as of this file's original 2026-09-20 write-up; `git init`
  plus a baseline commit landed later the same day — see Open Questions for what's now resolved.

### Amendment, 2026-09-20 18:47 — ADR-1 leg-boundary fixes + LiqTide snapshot tooling

Two more sessions closed the same day, after this file's 17:46 version. Both are UPDATE PROCESS
closeouts for threads that had already gone through EXECUTE; see
`process/general-plans/active/momentum-screener_17-09-26/update-process-closeout_20-09-26.md` for
the full reconciliation.

- `[Product]` **ADR-1 leg-boundary detection was fixed twice, post-EXECUTE, in
  `api/analytics/regime/leg_boundary.py`'s `detect_candidate_boundaries`:**
  1. **Formula fix** — the rate-of-change step is now `df["composite"].diff(periods=ROC_WINDOW_DAYS)`
     (an absolute difference), not `.pct_change(...)`. The liquidity composite is itself a blended
     z-score (mean ≈ 0, legitimately crosses zero), so dividing by the prior value exploded at every
     zero-crossing (`roc.std() = 21.95`, range -455.9..+189.8, `max|z| = 19.14`) while still
     producing zero candidates. A control replay against a strictly-positive series (stablecoin
     supply) gave clean z-scores (max 3.78) and 10 candidates, confirming the divisor was the cause.
     `liquidity_composite.py`'s own component-level `_roc` is unaffected — it's deliberately left
     `pct_change`-based because it runs on raw, strictly-positive economic series, not the composite.
  2. **Constant re-tune** — `SUSTAINED_DAYS` is now **2**, not 5 (`ZSCORE_THRESHOLD` stays 1.5,
     unchanged). Sweeping `SUSTAINED_DAYS` against `confirm_boundaries` price-structure confirmation
     (not candidate count) gave 5→2/2 (100% precision, too few), 3→4/3 (75%), **2→6/5 (83%,
     chosen)**, 1→12/9 (75%). At 2, the previously dark H2-2020..2021 stretch gets two new,
     independently price-confirmed events: `2020-11-20` and `2021-04-20`.
  - Full rationale, evidence tables and both amendments' exact text are in the plan's own
    `## Architecture Decisions (Final)` section (ADR-1 Amendment + ADR-1 Amendment #2) — read there
    before touching this function again; do not restate the numbers from memory.
  - Confirming backtest (`leg-boundary-backtest-report-20260920-184700.json`): 2017 → 0
    candidates / 0 confirmed (34 composite points in-window — see Open Questions, unchanged
    structural gap); 2020-21 → 6 candidates / 5 confirmed.
- `[Product]` **LiqTide snapshot tooling shipped** (`liqtide-snapshot-tooling_20-09-26` task
  folder, EXECUTE `COMPLETE_WITH_GAPS`): `LiqTidePayload.raw: dict | None` added (additive, last
  field) to `api/data/liqtide_adapter.py`; `fetch_latest(client=None, dry_run=False)` added so a
  dry run never writes; two new scripts under `api/scripts/` —
  `snapshot_liqtide.py` (arithmetic + coverage checks, `--coverage`/`--verify-only`) and
  `compare_composite_variants.py` (full-vs-reduced composite agreement check, reused
  `CONFIRMATION_WINDOW_DAYS` as its match tolerance); a new `api/tests/scripts/` test package (11
  synthetic-fixture tests, no network); `.gitignore` changed from a blanket
  `api/data/cache/` ignore to `api/data/cache/*` + `!api/data/cache/liqtide/` so the LiqTide daily
  archive is git-tracked going forward (Standing Rule 8 in the data-sources group, now implemented).
  All 6 test gates passed (179 passed / 1 deselected, final `uv run pytest tests/ -x -q`).
  **But the tool's actual purpose — proving the full and reduced composites agree — is still
  unanswered, not because of a bug but because LiqTide has no historical endpoint**: the archive
  can only be populated forward from the day the snapshot script actually runs, and as of this
  amendment it holds exactly one day (`api/data/cache/liqtide/2026-09-20.parquet`). The comparison
  script's `full.available` is still `false` for the 2024-01-11..2026-09-20 window with that single
  day present — one day is not enough history for the full composite to be considered available
  over a multi-year window. **Reconciliation of a stale report number:** the EXECUTE report's own
  comparison run (18:08, before the `SUSTAINED_DAYS` re-tune above) says the reduced composite
  found 0 candidates in that window; a later re-run at 18:33 (after the re-tune landed) found
  **4 candidates, 3 confirmed** (`2026-03-17`, `2026-04-20`, `2026-06-02`). The verdict is still
  `DISAGREE` either way, for the same reason (the full side has no data to compare against) — but
  the report's "0 candidates" line should not be read as current; treat the 18:33 run as the
  live number until a fresh comparison is run.

