---
name: context:context-changelog
description: "History of project context: every former Changes Since Last Update entry, the former Open Questions, References and Scan Metadata of all-context.md, and retired text, moved whole on 03-10-26. Not default load."
keywords: changelog, history, changes since last update, past decisions, open questions history, references, scan metadata, retired wording, what changed, when
date: 03-10-26
---

# Context Changelog

**History only, not current truth.** On 03-10-26 (master-planner-recovery Gate 2, task R3) the changelog block and the Open Questions, References and Scan Metadata sections of all-context.md were moved here whole and unedited, from all-context.md at commit `5878b16`. Current state lives in current-state.md; product direction in north-star.md; decisions in decisions.md. Entries are newest first, as they were. Facts below may be stale; never treat them as current without re-verifying.

Read this file only when you need the history of a decision, a past finding, or why something changed.

---

## Former all-context.md header (to 2026-10-01, moved 03-10-26)

Last updated: 2026-09-28, 2nd session (narrative-v2 EVL confirmation + RFC-3 scale-drift fix on
branch `fix/narrative-sufficiency-gating-rfc1`, PR #7 — RFC-1..6 now `✅ VERIFIED`, RFC-7 stays
`✅ CODE DONE` pending the user's AC-14 walkthrough; plan not archived). Also 2026-09-28, on a
separate branch (`claude/vigilant-hamilton-grr18c`, merged into `main` via PR #8 ahead of this PR):
the pytrends partial-hour-zeros fix (`narrative-mindshare`) — isolated single-file bug fix, full
RESEARCH → SPEC → INNOVATE → PLAN → VALIDATE → EXECUTE → EVL, closed via UPDATE PROCESS. This
version merges that PR #8 history into PR #7's branch to resolve a conflict between the two
branches' independent edits to this same section — the previous "Branch note" about needing to
reconcile by hand is now resolved. Prior update same day: merge of two independent branches — pair
screener v1 (`/pairs`, `cointegration-screener`'s first shipped feature, all 5 RFCs VERIFIED and
archived) from `main`, and the 2026-09-27 snapshot cron timing fix (all three nightly workflows
moved earlier to absorb GitHub's ~2h scheduler delay) from `claude/kind-tesla-tat3vo`. See Changes
Since Last Update below, newest first, for all of the above plus everything each branch already had
(narrative v2 SPEC, on-chain chain-growth plan, the 2026-09-25 keyword-keying fix, and earlier).

**2026-10-01 note (P1 pipeline completeness, branch `claude/p1-pipeline`, PR #11):** five scheduled
workflows now exist and all five cron times moved again — every clock time quoted in older entries
below (17:47/18:17/18:47 UTC, "~2h" delay) is superseded; see the newest entry directly below.

## Changes Since Last Update (2026-10-01, P1 pipeline completeness — general-plans)

Task folder: `process/general-plans/active/pipeline-completeness_28-09-26/` (three plans: schedules +
cache story, atomic parquet writes, cron timing). Branch `claude/p1-pipeline`, PR #11. All three are
**CODE DONE, not VERIFIED** — independent `vc-tester` EVL runs were green, but each plan's gate is
CONDITIONAL on recorded gaps that no human has accepted (carried under the autonomous-run policy).
Final full suite: **820 passed / 5 deselected** (714 at baseline → 789 → 817 → 820).

- `[Product]` **Two new nightly workflows**: `pairs-refresh-snapshot.yml` (`refresh_cache` then
  `compute_pairs`, two sequential steps of one job) and `liquidity-backfill-snapshot.yml`
  (`backfill_primaries`). `.github/workflows/` now has **five** workflows. `refresh_cache.py`,
  `backfill_primaries.py`, `compute_pairs.py` gained real exit codes (`exit_code`, `main(argv)`);
  `refresh_cache` also refreshes the 18 pairs-universe coins on `1d` (D7). New
  `api/scripts/bootstrap_watchlist.py` and runbook **`api/scripts/BOOTSTRAP.md`** (fresh checkout →
  populated cache; also the manual-refresh runbook).
- `[Finding]` **Cache decision: nothing new is committed to git.** Committing the OHLCV/liquidity/pairs
  caches would add an estimated ~1.5–3.3 GB/year (every OHLCV file and the whole `pairs/spreads/` dir
  are rewritten nightly, so every file diffs every night). The workflows' tolerant `git add` therefore
  stages nothing.
- `[Finding]` **The two new workflows' commit steps are INERT on GitHub Actions.** The runner is
  ephemeral and those dirs stay gitignored, so the commit step always reports "nothing new to
  commit". Today they are a nightly integration canary (run fails on a real crash/failed-fetch exit
  code), not a refresher. Real value arrives only when P2 supplies a persistent disk. Also: a
  GitHub-hosted `compute_pairs` only sees ≤500 daily bars per coin (`DEFAULT_LIMIT`), vs the ~2,230-bar
  deep-fetched local cache — a canary result, not a quality result.
- `[Correction]` **Atomic parquet writes**: all 9 parquet writers in `api/data/cache.py` now go
  through `_atomic_to_parquet` (same-dir temp → fsync → `os.replace`); `.gitignore` gained
  `api/data/cache/**/*.tmp`. 28 new tests (`test_cache_atomic_writes.py`), 18 red on the old code.
  **Not covered:** `api/data/etf_flows_adapter.py::merge_into_cache` still writes non-atomically, so
  P2's atomicity prerequisite is NOT fully met (backlog note). Real power-loss durability and Windows
  `os.replace` with an open reader are untested.
- `[Correction]` **Cron move + measured delay.** New schedules (UTC): pairs-refresh `17 11`,
  liquidity-backfill `47 11`, chain-growth `17 12`, narrative `47 12`, liqtide `17 13`. Measured GitHub
  start delay was **2h39m–5h01m on 2026-09-27/28 (recorded 2026-09-29)**; it varies by hours rather than growing steadily — on 2026-09-29/30 narrative and liqtide were about 4h late (narrative 4h02m/4h01m, liqtide 3h52m/3h52m) — not
  the "~2h" the 2026-09-27 entry recorded; the guard test now budgets 10h (`SCHEDULER_DELAY_BUFFER_MIN
  = 600`). The three no-history workflows gained a schedule-only step that warns (never fails) if a run
  starts after UTC midnight. **These times take effect only once merged to `main`; real firing is
  unverified** until `gh run list` is checked over the first 2–3 nights. If merged after a workflow's
  new cron time it has no scheduled run that UTC day — dispatch it manually (liqtide before ~00:25
  UTC or that day's file is permanently lost; see the closeout in the task folder).
- Testing: guard file `test_snapshot_workflow_schedules.py` 13 → 41 tests. No live fetch (ccxt,
  Hyperliquid, FRED) was run from this container; first real nightly run is the first live check.
  Closeout: `pipeline-completeness_CLOSEOUT_01-10-26.md` in the task folder.

## Changes Since Last Update (2026-10-01, three lanes merged: pipeline + deploy + Direction D)

Three parallel lanes merged into `main` the same day — PR #11 (pipeline), #10 (deploy), #9 (UI).
They were developed on disjoint blast radii and merged with **zero conflicts**; the only shared file
was `.gitignore`, additively on both sides. Post-merge gates, run together rather than per-branch:
**866 passed / 1 skipped / 5 deselected / 1 xfailed** pytest (was 714/5), **223 passed / 30 files**
vitest (was 181/22), `tsc --noEmit` exit 0, and `pnpm build:islands` succeeds.

- `[Product]` **Direction D — the charting stack was replaced (user-directed).** `lightweight-charts`
  removed; charts are now `layerchart` as **Svelte 5 islands** built by a separate vite step. Adds a
  real app shell for the first time (`AppNav`, `OwlMark` brand mark, design tokens, Tailwind 4,
  Skeleton) where before there were five routes with no navigation, no global stylesheet, and inline
  `style={{}}` in 24 files. Every chart on all five routes was converted. ADR-1 (islands, not
  SvelteKit) is in `process/general-plans/active/ui-shell_28-09-26/ui-shell_DIRECTION-D_28-09-26.md`,
  alongside a 520-line UI audit and rendered prototypes. **Measured cost:** 185 kB gzipped of chart
  runtime vs `lightweight-charts`' 54 kB — ~3.4×. See §Technology Stack.
- `[Product]` **Deployment resolved: home PC + Tailscale.** See §Technology Stack and `deploy/`.
  The licensing angle matters here — Farside, L2BEAT and Hyperliquid are all tagged
  non-redistributable, and a network-layer gate means the app is never on the open internet, which
  is the *strongest* available position on that constraint rather than merely an adequate one.
- `[Product]` **The three unscheduled refresh jobs are now scheduled** —
  `pairs-refresh-snapshot.yml` and `liquidity-backfill-snapshot.yml` join the three existing
  snapshots. Their commit steps are honestly documented as **inert** while `ohlcv/`, `liquidity/`
  and `pairs/` stay gitignored on an ephemeral runner; their present value is a nightly integration
  canary. A hard rule was recorded and honoured: **any job whose source keeps no history stays on
  GitHub Actions** (narrative, liqtide, chain-growth), because moving them to a PC that sleeps would
  turn every powered-off night into a permanent hole.
- `[Correction]` **Every parquet write in `cache.py` is now atomic** (temp-then-rename, the pattern
  the two JSON writers already used). Before this, a write cut off mid-flight could **truncate a file
  and destroy existing history**, not merely lose the new row — and the gitignored caches have no git
  copy to restore from. Latent for months; became a live risk the moment the deploy target became an
  intermittently-powered home PC.
- `[Correction]` **All five snapshot crons moved to 11:17–13:17 UTC**, plus a guard that warns when a
  run crosses UTC midnight. The previous 18:17 narrative slot came within **41 minutes** of losing a
  day: run #5 on 09-28 started 23:18:44Z after a **5h01m** scheduler delay. Observed delays are
  2h03m, 3h06m, 5h01m, 4h01m, 4h01m — **variance, not a trend**, and the earlier "~2h20m" figure in
  this repo's docs was simply too optimistic. The schedule guard test can only pin the *scheduled*
  time, never the observed delay, which is why the midnight-crossing warning exists.
- `[Product]` Live confirmation that the pytrends partial-hour fix works on real data, three nights
  running: `AI crypto` 27/72/50, `memecoin` 51/84/85, `pytrends-blended/ai` 13.5/38.5/25.0.
- `[Finding]` **`layer 2 crypto` / `l2s` returns 0.0 on every night observed**, across both the
  unbatched and batched paths. An earlier guess that `RWA crypto` was likewise too low-volume is
  **refuted** — it returned 74.0 on 09-29. Separately and more interestingly: that same night
  `pytrends/RWA crypto` was 74.0 while `pytrends-blended/rwa` was **0.0 written as `fresh`**. Anchor
  chaining can legitimately rescale a term to ~0 against a larger anchor, so the arithmetic may be
  right — but a `0.0` that means "below the anchor's resolution" has the same *shape* as the bug just
  fixed. Confirm RFC-1's sufficiency gating surfaces these as `insufficient`. Not fixed.

## Changes Since Last Update (2026-09-28, narrative-v2 EVL confirmation — narrative-mindshare)

Plan: `process/features/narrative-mindshare/active/narrative-v2_25-09-26/narrative-v2_PLAN_25-09-26.md`
(branch `fix/narrative-sufficiency-gating-rfc1`, PR #7). This is a documentation/process-only UPDATE
PROCESS closeout session — no `api/` or `web/` source files were edited by this session beyond the
already-committed scale-drift fix below.

- `[Correction]` **RFC-3's primary-keyword pytrends scale drift, flagged 28-09-26 in an earlier
  session, is now fixed (commit `1bec5db`).** Batching (RFC-3) folded the primary keyword into the
  same anchor-chained request as every other keyword for a narrative, which meant the archived
  `pytrends/{keywords[0]}` row — the exact key `trigger.py::compute_narrative_categories` reads for
  `/categories` — silently switched from an independent single-keyword value to an anchor-rescaled
  one. Fix: `snapshot_narrative.py` now writes that row from a separate unbatched `_fetch_live`
  top-up call (first-write-wins on its own `as_of`; a failed top-up skips the row, no batched
  fallback substituted); batched + blended writes are unchanged. Two new regression tests
  (`test_primary_keyword_uses_unbatched_value_blend_uses_batched`,
  `test_primary_topup_failure_skips_row_no_batched_fallback`,
  `api/tests/scripts/test_snapshot_narrative.py`) confirm it, folded into the 708-passed count below.
  This adds up to 15 extra pytrends requests/night at the plan's 15-narrative ceiling (23 total vs.
  the pre-fix 8) — checked against `process/context/data-sources/all-data-sources.md`'s pytrends
  guidance (no numeric hard ceiling documented) and accepted as within "cache aggressively"
  tolerance. Full arithmetic recorded in the plan's new `## Agent-Probe Evidence` section — this also
  satisfies RFC-3's previously-unrun named agent-probe (the 15-narrative worst-case request-count
  check), so RFC-3 reaches `✅ VERIFIED`.
- `[Product]` **RFC-1 through RFC-6 of narrative-v2 promoted to `✅ VERIFIED`** (real-data
  sufficiency gating, the unified `narratives.json` config, RFC-3's fix above, the momentum view,
  the daily mindshare view, and caveat de-duplication) — an independent `vc-tester` EVL confirmation
  run reproduced all fully-automated gates green: `uv run --project api pytest api/ -q` → 708
  passed/5 deselected (up from VALIDATE's 395/3 baseline); the AC-13 contract-snapshot test → 3
  passed unmodified; `pnpm --filter web test` → 193 passed/24 files; `tsc --noEmit` → exit 0; full
  Playwright suite run 3 times → 55/55, 54/55, 55/55 (see the flake finding below). A
  frozen-file check (`git diff` against the pre-plan base commit for `trigger.py`/`mapping.py`) is
  independently reproduced empty, confirming the hard-stop constraint held across all 7 RFCs.
  **RFC-7 stays `✅ CODE DONE`, not VERIFIED** — its named agent-probe, the AC-14 real-machine
  walkthrough (plan Section 14), needs live Google Trends/Reddit/CoinGecko/Hyperliquid access this
  sandbox's egress proxy blocks, the same structural constraint that held up v1's AC-11/AC-12 until
  the user ran them on their own PC. The plan stays in `active/`, not archived, pending that
  walkthrough — same precedent as regime-dashboard and narrative-dashboard v1 above.
- `[Finding]` **One Playwright flake observed, judged pre-existing/unrelated but not yet proven so.**
  `web/e2e/screener.spec.ts:103` ("weekly bars are Monday 00:00 UTC") failed on 1 of 3 full-suite
  runs but passed 15/15 in an isolated `--repeat-each=15` re-run — narrative-v2 touches zero screener
  files, and the identical failure was already present in PR #7's own pre-this-session description.
  Not proven pre-existing by reproducing against the base commit in a clean worktree (unlike the
  `pair-screener_25-09-26` precedent, which did do that proof) — backlog note:
  `process/general-plans/backlog/screener-weekly-bars-flake_NOTE_28-09-26.md`.
- `[Finding]` **`mapping.py`'s tripwire coverage is weaker than `trigger.py`'s.**
  `api/tests/analytics/narrative/test_trigger_tripwire.py` SHA-256-hashes the whole of `trigger.py`
  but only spot-checks `mapping.py` (no file hash, and no coverage at all of
  `map_coin_to_narrative_category`, which this plan's Non-Goals list as frozen). Today's empty git
  diff against the base commit closes the gap for this session only, not for future edits. Backlog
  note: `process/general-plans/backlog/mapping-tripwire-gap_NOTE_28-09-26.md`.

## Changes Since Last Update (2026-09-28, pytrends partial-hour-zeros fix — narrative-mindshare)

Plan: `process/features/narrative-mindshare/completed/pytrends-partial-hour-fix_28-09-26/`. Small,
isolated bug fix — went through the full RESEARCH → SPEC → INNOVATE → PLAN → VALIDATE → EXECUTE →
EVL cycle (SIMPLE plan, `Gate: PASS`, 0 FAILs/0 CONCERNs first pass) rather than being patched ad
hoc, resolving the Open Question flagged 27-09-26 (see below).

- `[Correction]` **`api/data/pytrends_adapter.py::_fetch_live` was archiving Google Trends'
  still-filling-in current hour as if it were a finished reading.** It took `df.iloc[-1]` of the
  hourly `"now 7-d"` `interest_over_time()` frame with no `isPartial` filtering; that last row is
  frequently Google's incomplete current hour, which is often 0 or heavily under-counted — and
  because Google Trends keeps no history, each affected night's real value was permanently lost.
  Confirmed real damage: `memecoins` and `RWA` were writing 0.0 on every nightly snapshot since
  09-24/09-26; only `ai` got real nonzero values.
- `[Product]` **Fix**: `_fetch_live` now drops `isPartial=True` rows before selecting the last
  point — reusing the exact pattern already proven in
  `api/scripts/backfill_pytrends_history.py::daily_points`. Returns `(None, None)` when no complete
  row survives the filter, so `fetch_trend`'s existing `unavailable`/`presumed-dead` handling takes
  over instead of writing a fabricated 0. Behavior is byte-identical to pre-fix when no `isPartial`
  column is present at all. `_fetch_live`'s signature and both call sites (`fetch_trend`,
  `snapshot_narrative.py::snapshot_pytrends`) are unchanged — deliberately, so the not-yet-started
  `narrative-v2` RFC-3 (a separate, still-active plan that will later add an additive batched-fetch
  function to this same file) is unaffected.
- `[Product]` New test file `api/tests/data/test_pytrends_adapter.py` (3 tests) — the first-ever
  direct unit coverage of `_fetch_live`'s row-selection logic. Uses synthetic `pandas.DataFrame`
  fixtures via `sys.modules` injection of a fake `pytrends.request` module (`pytrends` is confirmed
  not installed in the `api` env and not a declared dependency, so this injection is the required
  mechanism, not a fallback).
- `[Correction]` **Deliberately no retroactive correction.** Already-archived zero-valued points
  (09-24 through 09-28) are left as-is, honestly dated — this is a forward-only fix, mirroring the
  stance already taken for the separate, permanently-lost 2026-09-25 narrative-point gap (see the
  2026-09-27 cron-timing entry below).
- Testing: baseline `uv run --project api pytest api/ -q` was **623 passed / 5 deselected** before
  this fix (this branch already carries `narrative-v2` RFC-1-in-progress code on top of the merged
  pair-screener/cron-timing history below, which is why the count differs from the 486/3 recorded
  in the pair-screener entry) → **626 passed / 5 deselected** after (exactly +3 new tests, zero
  regressions). `uv run --project api pytest api/tests/data/test_pytrends_adapter.py -v` (3/3
  passed) run independently as the EVL confirmation gate. `git diff` independently re-confirmed
  AC-5 (no `cache.write_narrative_point`/`read_narrative_series`/migration touch) and AC-6
  (signature/call-site stability) both hold.
- Scoped independently of `narrative-v2` (separate, currently-executing plan) with zero file
  overlap — confirmed by the plan's own touchpoints (only `pytrends_adapter.py` + one new test
  file) and by reading `narrative-v2_PLAN_25-09-26.md`'s RFC-3 design before this fix started.

## Changes Since Last Update (2026-09-28, pair screener v1 — cointegration-screener)

`cointegration-screener/` moves from an empty `_GUIDE.md` placeholder to a shipped v1 feature: a
new, independent `/pairs` screen (`process/features/cointegration-screener/completed/
pair-screener_25-09-26/`), all 5 RFCs code-complete, EVL-confirmed, and user-approved. Zero shared
code, cache, or runtime state with the momentum screener, regime dashboard, or narrative-mindshare
— confirmed by an empty `git diff --stat` against those three surfaces at RFC-005.

- `[Product]` New route **`/pairs`**: tests every pair from a hand-curated, 18-coin crypto universe
  (BTC, ETH, SOL, HYPE, XRP, DOGE, ADA, AVAX, LINK, LTC, BCH, DOT, SUI, NEAR, APT, ARB, OP, ATOM —
  C(18,2) = 153 pairs) for cointegration — Engle-Granger both directions (BH-corrected, primary
  rank) plus Johansen as an always-shown second opinion, never merged into one score. A ranked
  table (`web/app/pairs/page.tsx`) plus a per-pair detail view (`web/app/pairs/[a]/[b]/page.tsx`:
  spread chart, both EG directions, Johansen, AR(1) half-life or `not_mean_reverting`, current
  z-score, sample window). All maths is whole-history (in-sample) diagnostic, never a live signal.
  `web/components/pairs/*`, `web/lib/api/pairs.ts`, `web/lib/types/pairs.ts`,
  `web/lib/format-pairs-value.ts`.
- `[Product]` New API: **`GET /api/pairs`** (table, every pair as one row, default sort ascending
  BH-corrected p-value, tie-break `(eg_p_bh, eg_p_raw, coin_a, coin_b)`) and
  **`GET /api/pairs/{a}/{b}`** (detail, incl. the full spread series; 404 unknown ticker, 422
  self-pair). `api/routers/pairs.py`, registered additively in `api/main.py`.
  `api/analytics/cointegration/{stats.py, pairs_response.py}`, `api/models/pairs.py`.
- `[Product]` **Precompute, not on-request.** A request-time compute of all 153 pairs measured at
  ~46s (p95 513ms/pair, `coint`'s `autolag='aic'`) against a p95 < 3s target for the read path —
  too slow to compute per-request. `api/scripts/compute_pairs.py` (new, manually-run, idempotent)
  now computes offline after backfill and writes a persisted, git-ignored results cache
  (`api/data/cache/pairs/results.parquet` + `provenance.json`); the router only reads it, never
  recomputes. Staleness is detected by comparing provenance against the current universe file,
  each coin's OHLCV cache, and the installed `statsmodels`/`EG_AUTOLAG` — a mismatch on any of
  those serves `computation_status: stale` with the last-known-good rows and a named reason, never
  silently-fresh.
- `[Product]` **Manual deep-fetch script**: `api/scripts/backfill_pairs_universe.py` — the first
  real consumer of the previously-unused `DEEP_LOOKBACK_LIMIT=5000` in `ccxt_adapter.py`. Calls
  `fetch_ohlcv(symbol, "1d", since=<explicit early UTC date>, limit=5000)` with defensive
  cap-hit pagination; extends (never replaces) the existing shallow `cache/ohlcv/{SYMBOL}/1d.parquet`
  files the momentum screener also reads. `api/data/pairs_universe.json` (hand-editable, 18 coins,
  `PAIRS_UNIVERSE_PATH` override for tests) + `api/data/pairs_universe.py` (loader, does not import
  `api/data/watchlist.py`).
- `[Product]` **New dependency**: `statsmodels>=0.14` (installed 0.15.0) —
  `tsa.stattools.coint` (Engle-Granger), `tsa.vector_ar.vecm.coint_johansen` (Johansen),
  `stats.multitest.multipletests` (Benjamini-Hochberg). `arch` was named in the original project
  plan for cointegration/regime work but is **deliberately not added** — nothing in this feature or
  the regime dashboard ended up needing GARCH/volatility modelling.
- `[Product]` `api/data/cache.py` gained three additive helpers (`pairs_results_path()`,
  `pairs_provenance_path()`, `pairs_spread_path()`), all resolving `CACHE_ROOT` at call time
  (mirrors the existing `ohlcv_path()`/`liqtide_*`/`narrative_*` convention) — every existing
  `cache.py` function is unchanged.
- `[Product]` `api/scripts/seed_e2e_cache.py` gained a `pairs` fixture section (6 synthetic coins,
  15 pairs, one of each status) for `web/e2e/pairs.spec.ts` (9 tests) — runs the real
  `compute_and_persist()` path so the fixture is `fresh` by construction, not hand-rolled.
- `[Correction]` A pre-existing screener Playwright flake (`toBeVisible()` 5s timeout on
  `coin-panel-BTC`, cold-start latency) was proven pre-existing (reproduced against the pre-feature
  commit `35e646f` in a temporary worktree) and mitigated with a config-only 15s
  `playwright.config.ts` `expect.timeout` — no test logic changed.
- Testing: **486 passed / 3 deselected** pytest (was 420 after RFC-001, 484 after RFC-005's first
  pass, +2 for the tie-break fix's new cases); **153 passed / 19 files** vitest (3 consecutive green
  runs — one earlier run reported an unreproduced 152/1 fail, not a regression from this feature);
  `tsc --noEmit` exit 0; **35/35 Playwright, run twice** (26 existing + 9 new `pairs.spec.ts`), plus
  a `pairs.spec.ts`-only repeat-each run at 90/90.
- **Real-data result (18-coin universe, 153 pairs, all `ok`):** 21 pairs have raw EG p < 0.05; 0 are
  significant after BH correction at the 5% level (closest is DOGE/BCH, raw 0.00057 → BH-corrected
  0.087). `compute_pairs.py` takes ~56s; the read-path (`GET /api/pairs`) p95 is 135-232ms.
- **Known gap, carried forward, not closed this session:** Hyperliquid appears to have a
  daily-history floor around **2020-08-19** (BTC/ETH/DOGE/LTC/ATOM all start exactly there) — likely
  a server-side limit, not five coincident listing dates; unconfirmed against Hyperliquid's own
  docs. Live cap-hit pagination (the 5000-bar response cap) and bulk rate-limit/backoff behaviour
  across 18 sequential deep-fetch calls were never observed on real data (18/18 succeeded with no
  throttling) — both remain mocked-test-only known-gaps from the original feasibility VERDICT. The
  Johansen-refused row and the "no pair significant" banner are unit-tested only, not reachable in
  the current E2E fixture set.
## Changes Since Last Update (2026-09-25 → 2026-09-27, snapshot cron timing)

Plan: `process/general-plans/active/snapshot-cron-timing_27-09-26/`.

- `[Correction]` **GitHub starts our scheduled workflows ~2h late** (observed up to ~2h20m via
  `gh run list`). The old slots — chain-growth 22:00, narrative 23:00, liqtide 23:30 UTC — actually
  started 23:56Z, 01:03–01:07Z and 01:30–01:52Z. Narrative points are dated by the UTC day the run
  executes, so the post-midnight runs skipped a day: **2026-09-25 has no narrative point and is
  unrecoverable** (Google Trends' short window, Reddit search and CoinGecko trending keep no history).
- `[Product]` New schedules, off the top of the hour, same order, 30-min stagger:
  `chain-growth-snapshot.yml` `47 17 * * *`, `narrative-snapshot.yml` `17 18 * * *`,
  `liqtide-snapshot.yml` `47 18 * * *`. Even a ~2h20m delay now lands every run before ~21:10 UTC.
- `[Product]` `liqtide-snapshot.yml` gained the same `concurrency` group and "nothing new to commit" +
  3-attempt `git pull --rebase`/push retry block the other two workflows already had.
- `[Correction]` **LiqTide publishes ~00:25–01:12 UTC** (observed `generated_utc`), not "~22:45 UTC"
  as previously documented. The archive is keyed by `generated_utc[:10]`, so LiqTide had no gap — the
  earlier schedule just ran only ~40 min after publish; it now runs ~18h after.
- Testing: new guard `api/tests/scripts/test_snapshot_workflow_schedules.py` (13 tests) pins each
  cron ≥3h before UTC midnight, ≥20-min stagger, no `pull_request` trigger, `permissions:
  contents: write` only, a concurrency group, the retry-push block, and per-workflow `git add` scope.
- `[Finding]` pytrends nightly points can be 0 because `df.iloc[-1]` of the hourly "now 7-d" frame is
  Google's incomplete `isPartial` hour (e.g. memecoins 34→0, RWA all 0). Not fixed — see Open
  Questions and `process/general-plans/backlog/pytrends-partial-hour-zeros_NOTE_27-09-26.md`.
- `[Correction]` **Superseded 2026-10-01:** the "~2h" delay and the 17:47/18:17/18:47 UTC times above
  were too optimistic — measured delay was 2h39m–5h01m on 09-27/28 and about 4h on 09-29/30 — it varies by hours rather than growing steadily. All five workflows now
  run 11:17–13:17 UTC with a 10h delay budget (pending merge; unverified). See the 2026-10-01 entry.

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
  originally `0 23 * * *`, 30 min before `liqtide-snapshot.yml`'s `30 23 * * *` — both moved earlier
  on 2026-09-27, see that entry; its own
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
  `.github/workflows/liqtide-snapshot.yml` runs nightly (18:47 UTC from 2026-09-27; moved to 13:17 UTC
  by the 2026-10-01 P1 branch, pending merge), executes
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

---


## Open Questions

- **Resolved, 2026-09-28 (2nd session): RFC-3's primary-keyword pytrends scale drift is fixed.**
  Was: batching (RFC-3) rescaled the `pytrends/{keywords[0]}` archive key `trigger.py`'s
  `/categories` path reads, via the anchor-chaining formula, from 28-09-26 forward. Now: fixed by
  commit `1bec5db` (unbatched top-up write for the primary keyword). See the 2026-09-28
  narrative-v2 EVL confirmation entry above for the full fix + worst-case-request-count arithmetic.
- **New, 28-09-26 (2nd session): `web/e2e/screener.spec.ts:103` flakes inside full-suite Playwright
  runs, judged pre-existing/unrelated to narrative-v2 but not proven so against the base commit.**
  See `process/general-plans/backlog/screener-weekly-bars-flake_NOTE_28-09-26.md`. Don't fix ad hoc
  — needs a clean-worktree reproduction against base first.
- **New, 28-09-26 (2nd session): `mapping.py`'s RFC-7 tripwire test is weaker than `trigger.py`'s** —
  no file hash, and no coverage of `map_coin_to_narrative_category` at all. See
  `process/general-plans/backlog/mapping-tripwire-gap_NOTE_28-09-26.md`. Small, scoped follow-up.
- **New, 2026-09-28: Hyperliquid's apparent daily-history floor (~2020-08-19) is unconfirmed.**
  BTC/ETH/DOGE/LTC/ATOM's deep-fetched OHLCV all start on exactly the same date
  (`api/scripts/backfill_pairs_universe.py`'s real run) — consistent with a server-side history
  limit rather than five coincident listing dates, but this has not been checked against
  Hyperliquid's own documentation. Also unverified on real data: whether the adapter's mocked
  cap-hit pagination test matches Hyperliquid's actual capped-response behaviour, and whether bulk
  rate-limit/backoff kicks in past the 18 sequential deep-fetch calls this feature made (0 failures
  observed so far). See `process/context/data-sources/all-data-sources.md`.
- ~~New, 27-09-26: pytrends nightly points can read 0 from Google's partial hour.~~ **Resolved
  2026-09-28.** `_fetch_live` now drops `isPartial=True` rows before picking the last point (same
  pattern already proven in `backfill_pytrends_history.py`), returning `(None, None)` — not a fake
  0 — when no complete row survives. Went through full RESEARCH → SPEC → INNOVATE → PLAN → VALIDATE
  → EXECUTE → EVL, not fixed ad hoc. See the 2026-09-28 (pytrends partial-hour fix) entry below and
  `process/features/narrative-mindshare/completed/pytrends-partial-hour-fix_28-09-26/`. Already-
  archived zero points (09-24 through 09-28) are left as-is, honestly dated — no retroactive
  correction (deliberate, see the plan's AC-5). The originating backlog note
  (`process/general-plans/backlog/pytrends-partial-hour-zeros_NOTE_27-09-26.md`) is marked resolved
  for Finding 1; Finding 2 (the unrecoverable 09-25 gap) was already closed by the cron-timing fix.
- **Momentum screener lives under `process/general-plans/`, not `process/features/`.** It's
  the first shipped feature, and it draws on macro-liquidity and narrative work that overlaps
  `cycle-regime` and `narrative-mindshare`. **Partially resolved, 24-09-26, for narrative only:**
  the narrative surface (`api/analytics/narrative/`, the pytrends/reddit/coingecko/hyperliquid
  adapters, `api/routers/narrative.py`) is now explicitly planning/documentation-owned by
  `narrative-mindshare/`, per the narrative-dashboard plan's ADR-1 — no source files moved.
  `cycle-regime/` reached the same real-code state independently (the regime dashboard). Still
  open: whether the *rest* of momentum-screener (screener board, confidence badges, leg-boundary/
  liquidity-composite regime maths) ever splits out of `process/general-plans/`, or stays there
  permanently as the cross-cutting integration layer these three features feed into. Don't guess
  — ask before restructuring momentum-screener itself.
- **New, 24-09-26: known pre-existing keying bug in `/categories`' trigger, found but explicitly
  not fixed.** `trigger.py::compute_narrative_categories` reads pytrends/Reddit archived history by
  category id, but `pytrends_adapter.py`/`reddit_adapter.py` write under the keyword key instead
  (e.g. `pytrends/AI crypto.parquet`, not `pytrends/ai.parquet`) — so `/categories`' trigger never
  actually reads back archived pytrends/Reddit history; it effectively runs on CoinGecko alone.
  Predates the narrative-dashboard program (this is RFC-003 of momentum-screener); found during
  narrative-dashboard RFC-3. Fixing it changes `/categories`' own output and needs a deliberate,
  separately-scoped AC-1 re-baseline plus user sign-off — queued as a follow-up plan, not absorbed
  into the narrative-dashboard program. Don't fix ad hoc.
- **New, 24-09-26: Hyperliquid's terms of use for redistributing market data are unverified.**
  `HYPERLIQUID_REDISTRIBUTABLE = False` in `api/data/hyperliquid_narrative_adapter.py` pending the
  user reading Hyperliquid's ToU/API docs — a one-line flip once confirmed. Also unverified: real
  Hyperliquid ticker shapes for `k`-prefixed meme perps beyond what the installed `ccxt` source
  shows (this sandbox's egress proxy blocks the live call). See the narrative-dashboard plan's
  Resume and Execution Handoff for the exact user-PC steps.
- ~~No git repository yet~~ **Resolved 2026-09-20** — `git init` done, initial baseline commit
  captures pre-fix state (including the 3 contaminated backtest reports, preserved for diffing),
  second commit holds the fix below.
- ~~"Numbers are never silently wrong" gap — consumer-level~~ **Fixed 2026-09-20.**
  `build_reduced_composite()`'s `composite_available` now derives from realized weight coverage
  (60% of intended weight, see `COMPONENT_WEIGHTS`/`AVAILABILITY_WEIGHT_THRESHOLD` in
  `liquidity_composite.py`) instead of "at least one component returned data." Re-run against live
  data confirms the old 2020-21 confirmed leg boundaries (`2020-04-07`, `2020-04-21`) do not
  survive with real inputs — they were artifacts of the bug, not real signal. Contamination check:
  those dates never reached any screener config or feature file (`write_confirmed_boundaries()` in
  `cache.py` has no caller), so nothing downstream needs correcting.
- **New, adapter-level half still open (not yet designed):** the consumer-level fix above closes
  the *symptom* (a composite silently claiming availability from a sliver of its inputs) but not
  the *cause* (an adapter — any of the 7 under `api/data/`, not just FRED — going to
  100%-`unavailable` across consecutive calls, with nothing distinguishing that from ordinary
  per-item missing data). Research done 2026-09-20: all 7 adapters share a typed
  `ok`/`unavailable`/`stale` convention, but no failure-counting/circuit-breaker state exists
  anywhere in `api/` (the closest precedent, `pytrends_adapter`'s `presumed-dead`, is time-since-
  last-success, not call-count, and is per-keyword). No scheduler exists in this repo at all —
  every adapter call is either router→analytics request-scoped or a manually-run script — so
  "consecutive calls" only accumulates when something happens to trigger a fetch. Needs a proper
  INNOVATE pass before implementation; do not patch this ad hoc.
- **New finding, 2026-09-20: the 2017 leg-boundary backtest window is largely untestable as
  currently scoped.** The reduced composite has zero usable (≥60%-coverage) dates before
  2018-01-11 — DefiLlama's stablecoin-supply series doesn't start until 2017-11-29, and net
  liquidity + dollar alone (56.25% of intended weight) sits just under the 60% floor. The
  `2017` cycle backtest (`process/general-plans/active/momentum-screener_17-09-26/`,
  `--cycle 2017`) is effectively testing ~7 weeks of early 2018, not the 2017 cycle it's named
  for. Undecided: accept this as a structural limit and document it in the backtest's own output,
  or find another approach for pre-2017-11 dates. Don't guess — ask.
  **Sharpened, still unresolved, 2026-09-20 18:47:** the post-ADR-1-Amendment confirming backtest
  (`leg-boundary-backtest-report-20260920-184700.json`) reproduces exactly this — 2017 → 0
  candidates / 0 confirmed against 34 in-window composite points, unchanged by either ADR-1 fix.
  This rules out "the ROC bug/threshold was masking 2017 signal" as an explanation: the 2017 gap is
  purely the pre-2018 coverage floor described above, not a downstream effect of the amendments.
  The choice between accepting the structural limit vs. finding another pre-2017-11 approach is
  still open — this evidence narrows the cause, it does not answer the question.
- **New, 2026-09-20 18:47: the full-vs-reduced liquidity composite agreement question (the
  LiqTide snapshot tooling's actual purpose) remains unanswered, and may stay that way for a long
  time.** `api/data/cache/liqtide/` now holds one archived day (`2026-09-20.parquet`); LiqTide has
  no historical endpoint, so the archive can only grow forward one day at a time, and
  `compare_composite_variants.py`'s `full.available` stays `false` over the 2024-01-11..2026-09-20
  window until there's materially more than one day of history to compare against. Not a code
  defect — see the 18:47 Amendment above for the mechanics and the corrected reduced-composite
  candidate count. **Update, 2026-09-24: this is not the same composite as the one below, and
  stays open on its own terms** — `compare_composite_variants.py` compares `liquidity_composite.py`'s
  reduced vs. full variant (the leg-boundary input), which is unaffected by the regime dashboard
  work. The archive-accumulation constraint described here is unchanged; don't conflate it with
  the regime dashboard's ADR-1 reproduction, which is a separate module (`components.py`) built to
  sidestep exactly this multi-year wait for a different (but related) purpose. Still undecided:
  whether to accept the wait, backfill LiqTide history from its six underlying sources, or drop
  this specific comparison as a goal. Don't guess — ask.
- **New, 2026-09-24, mostly resolved: does the regime dashboard's reproduced composite agree with
  LiqTide's published index?** Yes, closely, on the overlap window that exists — a real-data check
  during RFC-002 found 5 of 6 components exact and Pearson r = 0.964 between the reproduced and
  published composite. This is a different, narrower question than the `compare_composite_variants.py`
  one above (that one needs the archive to grow for years; this one only needs the overlap that
  already exists between LiqTide's own publish window and our primaries). Not fully closed:
  the exact overlap window is short (LiqTide's own history is ~2024-09 at best) and the 1/6
  mismatched component hasn't been root-caused — see the RFC-002 phase report for the specific
  component and its residual.
- ~~AC-11 real-cache user walkthrough for `/regime` has not run.~~ **Resolved 2026-09-24 (2nd
  UPDATE PROCESS pass).** The user ran the walkthrough on their own PC against the real cache (3y
  default range, zoom/hover/drill-down sync, ETF "not applicable before 2024-01-11" note, ~2000+
  point performance) and confirmed "all seems fine". One question — a blank stretch on the
  BTC-dominance panel — was explained and accepted as correct honest-gap behaviour, not a bug (see
  the two-depth-limits entry below). The regime-dashboard plan and its task folder are archived at
  `process/features/cycle-regime/completed/regime-dashboard_24-09-26/`.
- **Two component depth limits, accepted, not solved (BTC-dominance limit sharpened 2026-09-24).**
  BTC-dominance history has no free, keyless source deeper than LiqTide's own `metrics.btc_dom.series`
  (~2025-06 at best; CoinGecko's historical global market cap, which would let this be reproduced
  independently like the other five components, is paid-tier only). That series also has a real,
  permanent 209-day hole, **2025-12-07 → 2026-07-04** (161 points on either side, otherwise 1-3 day
  steps) — confirmed during the user's AC-11 walkthrough, who noticed the BTC-dominance panel's
  30-day change resumes only on 2026-08-03 (the as-of value 30 days earlier would be the stale
  pre-hole December reading). The nightly archive (RFC-001) prevents any *new* hole from forming;
  this specific historical gap is not backfillable from any known free source and the user chose to
  leave it. Spot-ETF flows separately, structurally cannot exist before 2024-01-11 (product launch
  date). Both panels show honest "no data" / "not applicable" states rather than any fill. Revisit
  only if a free deeper BTC-dominance source appears — don't invent one.

## References

Source files this update was based on: `web/package.json`, `api/pyproject.toml`, `.env.example`,
`api/data/cache.py`, `api/data/fred_adapter.py`, `api/data/liqtide_adapter.py`,
`api/scripts/refresh_cache.py`, `api/scripts/backfill_primaries.py`,
`process/general-plans/active/momentum-screener_17-09-26/momentum-screener_PLAN_17-09-26.md`,
plus directory listings of `api/`, `web/`, and `process/features/*/`.

**Added at the 18:47 amendment (UPDATE PROCESS closeout of two 20-09-26 threads):**
`api/analytics/regime/leg_boundary.py` (via the plan's ADR-1 Amendment + Amendment #2 text, read
directly), `api/scripts/snapshot_liqtide.py`, `api/scripts/compare_composite_variants.py`,
`process/general-plans/active/momentum-screener_17-09-26/leg-boundary-backtest-report-20260920-184700.json`,
`process/general-plans/active/liqtide-snapshot-tooling_20-09-26/liqtide-snapshot-tooling_REPORT_20-09-26.md`,
`process/general-plans/active/liqtide-snapshot-tooling_20-09-26/composite-variant-agreement-20260920-180830.json`
and `...-183336.json`, a `device_list_dir` of `api/data/cache/liqtide/` (one file:
`2026-09-20.parquet`), and
`process/general-plans/active/momentum-screener_17-09-26/update-process-closeout_20-09-26.md`.

**Added at the 2026-09-24 UPDATE PROCESS closeout (regime dashboard, RFC-001..006):**
`process/features/cycle-regime/completed/regime-dashboard_24-09-26/regime-dashboard_PLAN_24-09-26.md`
(full plan incl. Status Strip, ADRs, Validate Contract, Resume and Execution Handoff), all six
`regime-dashboard_24-09-26-RFC-00N-phase-report.md` files in that task folder, the Stage-0 reports
for RFC-001/RFC-002, the Farside `regime-dashboard-farside_FEASIBILITY_24-09-26.md`, the
`regime-dashboard-validate_REPORT_24-09-26.md`, `.github/workflows/liqtide-snapshot.yml`, and
`git log`/`git status` at `db8d854`.

**Added at the 2026-09-24 UPDATE PROCESS closeout (narrative-mindshare `/narrative` dashboard,
RFC-1..6):**
`process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md`
(incl. the new `## Post-EXECUTE Amendments` section), `narrative-dashboard_SPEC_24-09-26.md` (incl.
its `## Post-EXECUTE Amendment`), all six `narrative-dashboard_RFC-00N_REPORT_24-09-26.md` files
and both `*-stage0_REPORT_*.md` files in that task folder,
`narrative-dashboard-pvl-iteration-001_REPORT_24-09-26.md`,
`narrative-dashboard-evl-iteration-001_REPORT_24-09-26.md`, `results.tsv`, `.github/workflows/
narrative-snapshot.yml`, and `git log`/`git status`/`git show --stat` at `7ef8eb3` on branch
`claude/kind-tesla-tat3vo`.

**Added at the same-day 2nd UPDATE PROCESS pass (AC-11 confirmed, regime plan archived):** the
plan's Status Strip (all six RFCs ✅ VERIFIED), `regime-dashboard_CLOSEOUT_24-09-26.md` (updated
classification), and `git log --oneline -- api/data/cache/liqtide/*.parquet` (4 consecutive
automated `github-actions[bot]` commits, 09-21..09-24, cited as evidence the nightly schedule
mechanism runs unattended).

**Added at the 2026-09-28 UPDATE PROCESS closeout (pair screener v1, RFC-001..005):**
`process/features/cointegration-screener/completed/pair-screener_25-09-26/pair-screener_PLAN_25-09-26.md`
(full plan incl. Status Strip, ADRs, ADR-8 Amendments, Validate Contract, Post-EXECUTE Amendments),
`pair-screener_SPEC_25-09-26.md` (incl. its AC-4 Post-EXECUTE amendment),
`pair-screener_FEASIBILITY_25-09-26.md`, all five `pair-screener_RFC-00N_REPORT_25-09-26.md` /
`_28-09-26.md` files and their `-stage0` counterparts, both PVL iteration reports, both EVL
iteration reports (incl. EVL cycle 6's tie-break fix), `results.tsv`, and `git log --oneline` on
`main` at `b2d0fd5`.

**Added at the 2026-09-28 UPDATE PROCESS closeout (pytrends partial-hour-zeros fix,
narrative-mindshare):**
`process/features/narrative-mindshare/completed/pytrends-partial-hour-fix_28-09-26/pytrends-partial-hour-fix_PLAN_28-09-26.md`
(incl. `## Validate Contract`, `Gate: PASS`), `pytrends-partial-hour-fix_SPEC_28-09-26.md`,
`api/data/pytrends_adapter.py` (read directly to confirm the applied diff), `git show d186a08
--stat` and `git log --oneline` on branch `claude/vigilant-hamilton-grr18c` at `d186a08`, and the
originating backlog note
`process/general-plans/backlog/pytrends-partial-hour-zeros_NOTE_27-09-26.md`.

## Scan Metadata

- Generated: 2026-09-20 by `vc-generate-context` (delta update over the 2026-09-17 setup version);
  amended same day after `git init` + the composite availability-floor fix; amended again 18:47
  by `vc-update-process-agent` closing out the ADR-1 leg-boundary and liqtide-snapshot-tooling
  threads; amended again 2026-09-24 by `vc-update-process-agent` closing out the regime dashboard
  program; amended a further time the same day (2026-09-24, 2nd pass) after the user confirmed
  AC-11 on their PC and the regime task folder was archived to `completed/`; amended a third time
  same day (24-09-26) by `vc-update-process-agent` closing out the narrative-mindshare
  `/narrative` dashboard program (no `vc-generate-context` re-run for any of these amendments —
  targeted UPDATE PROCESS edits per this file's own Context Update Protocol); this version is
  further the result of merging two independent same-day sessions' branches together; amended a
  fourth time on 2026-09-28 on the `main` worktree (`my_project-main`, distinct from the
  `claude/kind-tesla-tat3vo` worktree referenced in the pre-merge HEAD note below, which has since
  progressed further with unmerged narrative-v2/on-chain work not reflected here) closing out the
  pair screener v1 (`cointegration-screener`) program — targeted UPDATE PROCESS edit, no
  `vc-generate-context` re-run; amended a fifth time same day (28-09-26) on branch
  `claude/vigilant-hamilton-grr18c` closing out the pytrends partial-hour-zeros fix
  (narrative-mindshare) — targeted UPDATE PROCESS edit (new Changes Since Last Update entry,
  resolved the 27-09-26 Open Question), no `vc-generate-context` re-run (this branch later merged
  into `main` via PR #8); amended a sixth time same day (28-09-26, 2nd session) on branch
  `fix/narrative-sufficiency-gating-rfc1` closing out the narrative-v2 EVL confirmation + RFC-3
  scale-drift fix — targeted UPDATE PROCESS edit, no `vc-generate-context` re-run. Source read for
  this amendment: `process/features/narrative-mindshare/active/narrative-v2_25-09-26/narrative-v2_PLAN_25-09-26.md`
  (full read), `git show 6de2559 c806b9c 1bec5db --stat`, `process/context/data-sources/all-data-sources.md`'s
  pytrends section, `api/data/pytrends_adapter.py` (`plan_batches`/`BATCH_SIZE`), a grep for numeric
  pytrends rate-limit constants (none found), and the independent `vc-tester` EVL run results supplied
  in the orchestrator handoff prompt (not independently re-run by this UPDATE PROCESS session).
  Merged with PR #8's `main` history (this same `all-context.md` amendment) via a merge commit to
  resolve PR #7's conflict against `main`; no source files touched beyond the conflict itself.
- HEAD (pre-merge): `7ef8eb3` (branch `claude/kind-tesla-tat3vo`, narrative-dashboard closeout) and
  `ecb5e39` (branch `claude/compassionate-goldberg-o2iq49`, regime-dashboard AC-11-confirmed
  closeout) — two independent branches/sessions, reconciled here via a `git merge` commit rather
  than a single linear history
- Mode: delta update from real repo scan (directory listings, `package.json`, `pyproject.toml`,
  `.env.example`, adapter/router/analytics source files, active plan folders) — not a line count.
  18:47 and both 2026-09-24 amendments were targeted reads (the plan file(s), their RFC phase
  reports, `git log`/`git status`/`git show --stat`, and directory listings of the new source
  paths for that program) — not a full repo re-scan each time
- Package managers: `pnpm` (web/, lockfile present), `uv` (api/, lockfile present)
- Source scanned (narrative-dashboard amendment): `api/analytics/narrative/{history,
  exchange_attention}.py`, `api/data/hyperliquid_narrative_adapter.py`,
  `api/data/narrative_category_map.json`, `api/routers/narrative.py`, `api/models/narrative.py`,
  `api/scripts/{snapshot_narrative.py,backfill_pytrends_history.py}`,
  `web/app/narrative/`, `web/components/narrative/`, `web/lib/{api,types}/narrative.ts`,
  `web/e2e/narrative.spec.ts`, `.github/workflows/narrative-snapshot.yml`,
  `process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/` (plan, SPEC, all RFC
  reports, results.tsv), `git diff 7ef8eb3~9..7ef8eb3 --stat` (58 files, +5536/-4)
- Source scanned (regime-dashboard amendment, unchanged from prior entry): `api/` (routers,
  analytics incl. `regime/`, data incl. `etf_flows_adapter.py`, models, scripts, tests), `web/`
  (app incl. `regime/`, components incl. `regime/`, lib, e2e),
  `process/general-plans/active/momentum-screener_17-09-26/`,
  `process/features/cycle-regime/completed/regime-dashboard_24-09-26/`, `process/features/*/` (the
  other three still placeholder-only), `.env.example`, `.github/workflows/liqtide-snapshot.yml`
- 2026-09-25 amendment: `vc-update-process-agent` closeout of the narrative-keyword-keying
  fix (targeted edits; `api/analytics/narrative/trigger.py` + its tests), then merged into
  `claude/kind-tesla-tat3vo`


---

## Retired all-context.md text (moved 03-10-26)

The sections below were removed from all-context.md on 03-10-26 because the product direction changed on 02-10-26 (north-star.md, decisions.md D-0 to D-2) or because their detail moved to architecture.md and operating-instructions.md. Kept verbatim for history.

### Former "What This Project Is"

my_site is a personal market-research web app for a solo trader. Four product areas:
charts with technical indicators, a cointegration / pair screener, a cycle & macro regime
dashboard, and narrative / mindshare tracking.

The point of the app is not signal generation for its own sake. The four areas exist to turn
separate signals into a **confidence level** that drives position sizing. Design decisions
should favour showing how strong a read is, and how much it disagrees with the other reads,
over showing a single directional call.

**Audience:** built for the author's own use first, with the explicit intent to open it to
other users later. That means: no hard-coded personal assumptions, no credentials in the
client, and data-provider licensing has to stay redistribution-safe from the start — but
auth, billing and multi-tenancy are deliberately out of scope until the research tooling works.

**Status as of 2026-09-20: real application code exists and is under active development.**
`api/` and `web/` are both built out, with one shipped feature (the momentum screener — see
Changes Since Last Update above) and seven live data-provider adapters. Repository Structure
and Technology Stack below now describe what's actually there, not a target. A few items are
still genuinely OPEN DECISION — do not invent an answer for those; ask.

### Former "Key Patterns and Conventions" (confidence paragraph and full text)

These were decisions made at setup and are now observed in the codebase (`api/data/*_adapter.py`,
`api/data/cache.py`, `api/analytics/`).

**One source of numerical truth.** Every indicator, statistic and derived number is computed
in Python and sent to the frontend as data. TypeScript formats and renders; it never
re-implements an indicator for display. Two implementations of the same calculation is the
single most likely way this project produces quietly wrong numbers.

**Providers live behind adapters.** No route, component or analytics function talks to an
exchange or vendor API directly. Every provider is wrapped in an adapter under `api/data/`
exposing the same shape, so swapping a provider is a one-file change. This matters because
the data-provider decision is deliberately unresolved — see `data-sources/all-data-sources.md`.

**Free tiers are a design constraint, not a detail.** Fetching is cached and rate-limited at
the adapter layer. Assume every provider limit will be hit during development.

**Numbers are never silently wrong.** A calculation with insufficient data, a failed
convergence, or a stale cache returns an explicit "insufficient/unavailable" state that the
UI renders as such. No NaN, no zero-filled series, no silently truncated lookback.

**Confidence over direction.** Where a feature could show either a call or a confidence,
prefer the confidence, and show the disagreement between signals rather than hiding it.

**Naming:** kebab-case files in `web/`, PascalCase React components, snake_case throughout
`api/`.

### Former "Open Decisions" table and closing paragraph

Carry these into any plan that touches them. Do not resolve them silently.

| Decision | Status |
|---|---|
| Crypto data | Settled and implemented — ccxt against a major exchange, no key needed. See data-sources group |
| Macro liquidity / regime input | Implemented, both paths at once (RFC-002): `liqtide_adapter.py` consumes the LiqTide endpoint directly; `fred_adapter.py` reproduces net liquidity + broad dollar + reserves from FRED's keyless CSV export. `api/analytics/regime/liquidity_composite.py` picks a full vs. reduced composite per-date depending on which inputs are available. See data-sources group |
| Equity data provider | Still unresolved — no equity adapter exists in `api/data/` yet. London Strategic Edge remains the leading free candidate **pending verification**; its data is personal-use only, which collides with the public-later goal. See data-sources group |
| Persistence layer | Settled 2026-09-17, confirmed in use — Parquet + DuckDB (`api/data/cache.py`) |
| Narrative / mindshare data source | Implemented on the settled approach: CoinGecko, pytrends, Reddit adapters all exist under `api/data/`, feeding `api/analytics/narrative/`. Still free-proxy-only, still labelled low-confidence. Widened 24-09-26 with a 9th adapter (Hyperliquid, keyless, display-only, `redistributable=False` pending user terms check) and a standalone `/narrative` history dashboard — see Changes Since Last Update |
| Testing strategy | **Resolved** — `pytest` (api, `integration` marker gates real-network tests) + `vitest` + Playwright (web). See `tests/all-tests.md` |
| Deployment target | Still deliberately deferred — the only CI/scheduling config that exists is two single-purpose nightly workflows, `liqtide-snapshot.yml` and `narrative-snapshot.yml` (see Repository Structure); no app deploy pipeline |
| Package managers | Settled 2026-09-17, confirmed in use — pnpm (web) + uv (api) |

**Redistribution is a first-class constraint, not a launch-day detail.** Some free data this
project may depend on is licensed for personal use only and may not be served to other users.
Because the app is intended to open up later, every provider adapter records whether its output
may be redistributed. See Licensing in `data-sources/all-data-sources.md`.

- 03-10-26: T16 and T20 merged (`351f946`, `54157e2`); operating-instructions.md tsbuildinfo sentence now says untracked and ignored; current-state.md tsbuildinfo row and next steps updated; MASTER-PLAN.md trimmed to headroom, T16/T20 `accepted`.
