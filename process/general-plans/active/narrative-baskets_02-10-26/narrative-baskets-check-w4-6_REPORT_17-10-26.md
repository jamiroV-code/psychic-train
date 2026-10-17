# T82 P5 check (Waves 4-6) report, 17-10-26

Independent, report-only test of what merged to `main` in Waves 4-6 of the narrative-baskets programme. Nothing was edited except this file. No provider call, no scraping, no secret read.

## 1 Task ID and scope

T82, branch `claude/t82-p5-check-report`, one draft PR, never merged. Tested commit: `main` at `e3e6b63` (merge of PR #116). Plan baseline for diffs: `38bb43e` (the commit the PLAN was written against).

In scope: `BasketAttentionChart`, `BasketTable`, `NarrativeTabs`, `BasketCoins`, `GET /api/narrative/baskets/attention`, `GET /api/narrative/discovery`, `DiscoveryTab`, deletion of `trigger.py` and `momentum.py`, `baskets_view`.

## 2 TL;DR

- **Baselines are green and match expectations.** pytest 1377 passed, 1 skipped, 5 deselected. vitest 481 passed (60 files). `tsc --noEmit` exit 0. Playwright 86 passed, 0 failed. Lockfile unchanged.
- **No critical finding. One high:** the shipped weights file names two sources (`exchange`, `x`) that the fetchers and store write as `exchange_volume` and `xsearch`. After the owner's live probes (slice G), exchange volume and X can never feed a score. Reproduced on fixtures (F-1).
- **Medium:** breadth ignores the window selector and can contradict "Change" on the same row (F-2); one unreadable parquet file turns the whole attention endpoint into a 500 (F-3); the e2e never joins the real scoring API to the UI, and the as-shipped state renders a legend with no chart (F-4, F-5).
- **Owner requirement "well organised and clean, no noise": mostly met, not fully.** Layout is calm and there is no horizontal scroll at 375/768/1280. Concrete defects remain (section 6): a bright white chart slab on a dark page, no visible expand affordance, raw unformatted numbers and raw source ids inside the expand, an orphan legend when no data, a raw API path in the error line, a Discovery tab with no chart and a different selector style. This part is a judgement (HY); the planner or owner decides.
- **Behaviour probes pass:** percentile ranking against the reference, missing is never 0, outside-universe coins are placed not added, all four outlier rules, one coin per basket, rename, cap 12, `/history` and `/mindshare` byte-identical to the plan baseline (including `trust_weight`), AC-25 tests unedited and green.

## 3 Baselines (untouched main, `e3e6b63`)

| Check | Command | Result |
|---|---|---|
| API tests | `UV_FROZEN=1 uv run --project api pytest api/ -q` | `1377 passed, 1 skipped, 5 deselected, 2 warnings in 261.11s`, exit 0 (matches the expected 1377+/1/5) |
| Web install | `pnpm install --frozen-lockfile` (in `web/`) | done in 10.5 s, `git status` clean afterwards (lockfile unchanged) |
| vitest | `pnpm exec vitest run` | `Test Files 60 passed (60)`, `Tests 481 passed (481)` |
| Types | `pnpm exec tsc --noEmit` | exit 0, no output |
| e2e | `UV_FROZEN=1 PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium SCREENER_REFRESH_WORKER=0 pnpm exec playwright test` | `86 passed (5.4m)`, exit 0. Includes `contrast.spec.ts` (9 cases) and `narrative.spec.ts` (10 cases) |

Working tree stayed clean after all four runs. `playwright install` was never run.

## 4 Findings, ranked

### High

**F-1. Two of six attention sources can never reach a score (source-name mismatch).**
- Files: `api/data/attention_weights.json:4` (`exchange`) and `:8` (`x`); `api/data/attention/registry.py:15,19` (`exchange_volume`, `xsearch`) and `:22` (`SOURCE_WEIGHTS`, unused); `api/data/attention/exchange_volume.py:15`; `api/data/attention/xsearch.py:26-27`; `api/data/discovery.json:8` (`source_groups` also says `exchange`).
- `build_attention` and `build_discovery` take their source list from the weights file (`api/analytics/attention/basket.py:76`, `api/analytics/attention/discovery.py:92`) and read `registry.read_series("exchange", ...)`. The fetchers write the store and the probe record under `exchange_volume` and `xsearch`.
- Repro (fixtures only, tmp cache, scratch script `probe_attention.py`): probe record lists `wikipedia, coingecko, exchange_volume, trends, reddit, xsearch`; parquet written for `exchange_volume` and `xsearch`; shipped weights file.
  ```
  weights_keys            ["wikipedia","coingecko","exchange","trends","reddit","x"]
  registry_fetcher_keys   ["wikipedia","coingecko","exchange_volume","hyperliquid_volume","trends","reddit","xsearch"]
  weights_not_in_registry ["exchange","x"]
  coin A sources: wikipedia ok 25.0 | coingecko ok 25.0 | exchange not-probed null | trends ok 25.0 | reddit unavailable null | x not-probed null
  ```
- Impact: today nothing is probed (`probe_records.json` is `{}`), so no user sees a wrong number. After slice G the owner records probes under the fetcher names, the store fills, and exchange volume and X stay `not-probed` forever with no error. Hyperliquid volume has no weight at all. Also the weight conflict: `xsearch.WEIGHT = 0.25` vs `"x": 0.5` in JSON (plan says "X lower"; either is lower, but there are two sources of truth).
- Why tests miss it: the S-C and S-F1 tests build their own weights with `wikipedia, coingecko, trends` (`api/tests/analytics/attention/conftest.py:13`), never the shipped file.
- Trap when fixing: Discovery's independence rule groups `coingecko` and `exchange` as one "volume" group. If only the weights key is renamed to `exchange_volume`, that group entry silently stops matching and two volume sources would count as independent (violates AC-41). Rename in both files, add a test that reads the shipped files.

### Medium

**F-2. Breadth ignores the window; "Change" and "Breadth" can contradict on one row (AC-36).**
- `api/analytics/attention/basket.py:16` (`BREADTH_LAG_DAYS = 7`), `:52-59`. AC-36 says "share of members whose score rose over the window".
- Repro (`probe_attention2.py`, one coin, 10-coin reference): window 7 → breadth 1.0, change +20.0; window 30 → breadth 1.0, change -30.0; window 90 → breadth 1.0, change -30.0. The 30d and 90d row says every member rose while the basket fell by 30 points.
- Fix direction: lag = window (or state "7-day breadth" in the label). Not changed here.

**F-3. One unreadable store file makes the whole endpoint a 500 instead of a per-coin `unavailable`.**
- `api/data/attention/store.py:26-31` (no error handling around `pd.read_parquet`), called from `api/data/attention/registry.py:40`. Same path serves Discovery.
- Repro: write non-parquet bytes to `<cache>/attention/wikipedia/BAD.parquet`, call `build_attention` with a basket holding `BAD`: raises `ArrowInvalid`. In the running app that is HTTP 500, and the UI shows "API request failed: ... -> 500". Plan rule: "unavailable data is an explicit state". A half-written or truncated file (the store writes atomically, but the owner PC copies files) breaks every basket, not just one coin.

**F-4. The Playwright coverage never joins the real scoring API to the UI.**
- `web/e2e/narrative.spec.ts:114,133,144` route-mock `**/baskets/attention*`. Baskets are created through the real layout API, but every score, series and state comes from a hand-written body. AC-37 and AC-40 list Playwright as proof; the join (API payload shape → chart → table) is only proven by vitest with injected data. F-1 and F-5 are the kind of defect this gap hides.
- One mocked state is not producible by the API: `ranking-off-*` shows Score "no data" with Change +12.5 and Breadth 80% and a drawn chart. The real API returns all of score, change, breadth and every series point as null in that state (see F-5).

**F-5. As-shipped state shows a legend with no chart.**
- Repro: real API and `next dev` on a seeded throwaway cache (fixtures), two baskets, shipped config (`probe_records.json` is `{}`). Payload: `score/change/breadth` null, `coverage` "covers 0 of 1", every series value null, Discovery `status: no-data, reason: reference-missing`.
- Rendered at 1280 px: header, selector, a legend chip listing "Majors" and "Layer2" with colour swatches, "membership as of 2026-10-17", "Ranking is off: the reference is missing.", a table of "no data" in every numeric cell. No chart area at all, so the legend labels lines that do not exist. Code: `web/components/narrative/BasketAttentionChart.tsx:78-106`.
- This is the state the owner sees until slice G and the refresh script have run (plan risks R1, R2). It is honest, but the legend is noise.

**F-6. Coin expand prints raw numbers and raw ids.**
- `web/components/narrative/BasketCoins.tsx:29-31`: `{s.source}` and `{s.raw}` are printed as-is. Real source ids are `wikipedia`, `coingecko`, `exchange`, `trends`, `reddit`, `x` (an `x` row is meaningless to a reader), and `raw` is the last stored day as a JS number: a CoinGecko volume would print as `1234567890.123456` (not run live; arithmetic on the fixture type). No unit, no rounding, no rank shown beside it. The UI standard asks for "one plain label per number". The screenshots use short fixture ids (`wiki`, `trends`) and integers, so they hide this.

### Low

**F-7. A forbidden file was edited.** T80 (`57b77bf`) changed two docstring lines in `api/analytics/narrative/mapping.py` (`git diff 38bb43e HEAD -- api/analytics/narrative/mapping.py`: "triggered" → "active", lines 6 and 43). The plan's "Forbidden for all" list names `mapping.py`. Behaviour unchanged; `test_mapping.py` is untouched and green. Scope breach only.

**F-8. Stale comments name deleted code.** `api/data/narrative_categories.json:2` still says the file "drives /api/narrative/categories and /screener via trigger.py"; `api/analytics/narrative/mapping.py:23`, `narrative_config.py:7-8`, `exchange_attention.py:4` also name `trigger.py` or `/api/narrative/categories`. Both endpoints and the module are gone (verified: files absent, `git grep` finds only these comments). The plan's checklist item "fix docs naming removed symbols" is open.

**F-9. Reference universe is cut to 100 before exclusions, and its size is shown nowhere.** `api/analytics/attention/universe.py:35-36,41`. A 115-coin snapshot with 5 stablecoin/wrapped entries in the top 100 gives 95 reference coins (probe output `95 snapshot`). D-3 reads either way ("top-100 ... stablecoin and wrapped lists excluded"); say which. `universe_size` is in the payload but the UI does not show it.

**F-10. Two units for "change".** Table "Change" is in score (percentile) points (`basket.py:51`); the chart lines are the score rebased to 100 (`basket.py:48-50`). Rebasing a 0-100 percentile also makes a low base amplify and a base of 0 give a gap. Not reproduced as a visible explosion; flagged as design risk only.

**F-11. My baskets error has no Retry and prints a developer string.** Error line: "API request failed: /api/narrative/baskets/attention?window=30 → 500" (`web/lib/api/attention.ts:14`, screenshot `error-375.png`). Discovery's error has plain text plus a Retry button (`DiscoveryTab.tsx:49`). Inconsistent.

**F-12. Discovery lists every configured category.** `api/data/discovery.json:9-19` always yields nine rows; with sparse data eight show "no data" and "0" coins used (`discovery.py:101-112`). Noise for a "no noise" page; consider hiding empty categories or collapsing them into one line.

**F-13. Dead and duplicate config.** `registry.SOURCE_WEIGHTS` (`registry.py:22`) is read nowhere. `hyperliquid_volume` has a fetcher and a runner but no weight (see F-1).

### Info

- **I-1. `/history` and `/mindshare` are byte-identical** before and after Waves 5-6 (see section 5, P6). `trust_weight` is still served in every composite point (`api/models/narrative.py:61`, `api/routers/narrative.py:79`). The PLAN's AC-11 text says no `trust_weight` in `/history`; the D2 test (`test_no_narrative_verdict_fields.py:5`) and the tester brief say it stays. The plan text is out of date, not the code.
- **I-2.** `RedistributionBadge.tsx` stays in `web/components/narrative/` but only on-chain components import it; the narrative page has no badge class (vitest asserts it).
- **I-3.** `NarrativeDashboard` no longer imports the old views; grep gate `trust_weight|triggered|confirmed` over `web/components/narrative`, `web/lib/*narrative*`, `web/lib/*/attention*` returns nothing. Colour and font-size literal grep over the new narrative `.tsx` files returns nothing.
- **I-4.** The screener page (outside Waves 4-6) still shows a dense technical block (`change_14d`, `T`, `std (ddof 1)`, "Rule: rising when ...") directly above the removal notice (`removal-notice-1280.png`). Out of scope, noted because the notice screenshot is framed by it.
- **I-5.** Next.js dev indicator (round button bottom left) overlaps the last table row in 375 px shots. Dev-only, not a product defect.
- **I-6.** No "before" screenshots exist in `screens_17-10-26/`; the UI standard gate asks for before/after.
- **I-7.** Secret scan: no bearer-token pattern in `api/`, `web/lib`, `web/components`; `xsearch.py` reads `X_BEARER_TOKEN` at call time (`xsearch.py:121`); `X_LIVE` off by default (`:54`).

## 5 Probe results (fixtures only, no network)

Scripts live in the session scratchpad, not in the repo. Each used a tmp cache root and tmp config files. No file in the repo was written.

| # | Probe | Result |
|---|---|---|
| P1 | Percentile vs reference. 4 reference coins with ratios r1..r4; coins A (1.5x) and B (3.5x) | Ranks 25.0 and 75.0, equal to hand computation `(below + 0.5*equal)/n*100`. Coin outside the reference (`OUT`) scored 50.0 and `universe_size` stayed 4; a coin above all references scored 100.0. PASS |
| P2 | Missing sources | Coin with only Wikipedia: score 75.0, `sources_used 1`, `sources_total 3`, other sources `unavailable`, rank null. Basket whose coins all lack data: score, change, breadth null, `status no-data`, `coverage "covers 0 of 2"`, every series value null (never 0). Mixed basket: `covers 1 of 2`. PASS |
| P3 | Discovery outlier rules (shipped `discovery.json` thresholds) | Snapshot of 8 coins: stablecoin, wrapped, exchange token excluded (universe 5); volume 19,999,999 excluded, 20,000,000 included, missing volume excluded (eligible 3); coin with one usable source dropped; coin rising in two sources of one group gets `gaining false`, `sources_gaining 1`; 21-coin category with one coin at +9900% is capped to +200.0 (p95), `raw_change` kept, mean 109.5 beside median 110.0, `coins_used 21`. PASS |
| P4 | Empty, partial, error | Empty basket and all-missing basket: `status empty` / `no-data`. As-shipped (empty probe records, no snapshot): all null, Discovery `no-data / reference-missing`. Error: corrupt store file → exception (F-3) |
| P5 | Baskets and layout through the real routers | 2 baskets saved; same coin in two groups → 422 "coin in more than one place"; name repeated ignoring case → 422; 41-char name → 422, 40 → 200; 12 groups incl. `main` → 200 (11 baskets), 13 → 422 "at most 12 groups"; move coin returns `{basket, previous_basket}` incl. null both ways; coin not on screener → 404 with the plan's sentence; extra body field 422; bad id 422; unknown group 404; 16-char symbol 422; rename `g1` → attention payload name "Renamed", `main` never a basket; deleting a group moves its coins to a neighbour (`ai` → `memes`), UI warns and names it (`CoinGroup.tsx:213-215`); `DELETE /api/watchlist/SOL` returned `affected_baskets ["L1"]`; coin added without a group lands in Unassigned. PASS |
| P6 | `/history` and `/mindshare` unchanged | Same seeded fixture cache served from a worktree at `38bb43e` and one at `e3e6b63`, `generated_utc` removed: both 200, history JSON identical, mindshare JSON identical (32,618 bytes each). Composite point keys `coverage, date, gap_before, mixed_scale, sources_present, trust_weight, value`; `trust_weight 0.6`. PASS |
| P7 | AC-25 | `git diff --stat 38bb43e HEAD` over the seven protected test files: empty. The files ran in the green 1377 suite. PASS. (`mapping.py` itself changed, F-7) |
| P8 | Deleted code | `api/analytics/narrative/{trigger,momentum}.py` absent; `/api/narrative/categories` and `/momentum` are gone; guard test `test_no_narrative_verdict_fields.py` green in the suite. PASS |
| P9 | Source naming vs shipped weights | See F-1. FAIL |
| P10 | Breadth vs window | See F-2. FAIL |

## 6 Visual review (screenshots under `screens_17-10-26/`, 375 / 768 / 1280)

Viewed: `ok`, `coin-expand`, `partial`, `ranking-off`, `loading`, `empty`, `error`, `removal-notice`, `discovery-ok`, `discovery-error`, `discovery-nodata-reference-missing` at the widths named in section 4. Plus one real-API render of the as-shipped state (F-5, 1280 px). A real-app 375 px capture made with the headless CLI was cropped by the browser's minimum window width, so it is not used as evidence; the 375 px overflow check rests on the Playwright assertions (`scrollWidth <= clientWidth`, passing).

What is good: one page title, two tabs, one selector, a one-line header, chart first, a five-column table with right-aligned numbers, "no data" in plain muted text, one empty line with a link, no badges, no verdict words, no horizontal scroll, consistent state copy.

Concrete defects (judge against "well organised and clean, no noise"):

1. **White chart slab on a dark page** (all `ok-*`, `partial-*`, `coin-expand-*`). The chart panel and the legend chip are pure white against a near-black page; it is the loudest element and the only one not on the page's surface tokens. Chart axis text is small grey on white.
2. **No expand affordance.** Basket names are bold text. Nothing says they open (no chevron, no hover mark in the shots); the name only turns blue once open (`coin-expand-1280.png`). `BasketTable.tsx:46`.
3. **Expand block is hard to read.** Source names left, values right-aligned in a wide gap, state word ("unavailable") floating in a third spot (`coin-expand-1280.png`: "no data   unavailable"). At 375 px the state word sits against the right edge. Raw numbers and ids per F-6.
4. **Orphan legend, no chart, in the real as-shipped state** (F-5). In `partial-375.png` the legend also lists "Layer2" although its line is not drawn, and the table says "covers 2 of 2" beside "no data" in every number (fixture inconsistency, but it is what the screenshot gate shows).
5. **Chart has no axis title or unit and no 100 baseline.** The y axis reads 20-60; AC-37 says series are rebased to 100 at window start. The mock does not rebase, so the screenshot cannot confirm the real look (real lines all start at 100 and fan out). The page never says what "Score" is.
6. **Error line** is raw developer text and has no Retry (`error-375.png`).
7. **Discovery tab differs from My baskets.** No chart (the standard says "chart first"), a selector drawn as three separate outlined buttons instead of the joined control, no page-level title like "Attention by basket", no "as of" date, four columns instead of five. Coin rows use inline text ("AAA +35.2% 2 of 3 sources rising") so the values do not line up in a column (`discovery-ok-1280.png`). "Score" and "Median" are percent changes with no unit label in the header.
8. **Mobile top bar height is unstable.** At 375 px the top navigation band is about 145 px tall in `ok-375.png` and 130 px in `partial-375.png`, but about 260 px (`discovery-ok-375.png`) and 355 px (`error-375.png`, `discovery-*-375.png`) tall with an empty dark block above the nav items, so the page content starts at 40% of the screen. Cause not found (may be the shot's scroll state); needs a repro. The nav row is also clipped at the right edge ("P" of Pairs), which is normal horizontal nav scroll.
9. **Removal notice** (`removal-notice-*.png`) is a plain line with a slight left indent inside the screener add-coin form; it does not stand out and sits under a technical block (I-4). Present and visible, but quiet.

Verdict on AC-42 (HY): structure and states pass; defects 1-4 and 7 stop it from being "no noise". Not accepted by this tester; the planner or owner makes the call.

## 7 Pass/fail per acceptance criterion

PASS = proven here on fixtures or by the baseline runs. PARTIAL = holds with a stated gap. FAIL = a probe contradicts the criterion.

| AC | What | Result | Evidence |
|---|---|---|---|
| AC-9 | Groups are baskets, survive reload | PASS | layout router tests in the green suite; P5 re-read through the API |
| AC-11 | Old verdict code and endpoints gone, no verdict fields | PASS | P6, P8; web grep gate empty. Plan text on `trust_weight` is stale (I-1) |
| AC-24 | Unavailable is a state, never 0 | PASS (API and UI formatters); F-3 shows a hard failure where `unavailable` was expected | P2, `lib/attention-lines.ts` `NO_DATA` |
| AC-25 | Protected tests unedited and green | PASS for tests; F-7 for `mapping.py` | P7 |
| AC-27 | Coin must be on the screener | PASS | P5 (404 text) |
| AC-32 | Removal names affected baskets; delete group warns | PASS | P5 (`affected_baskets`), `CoinGroup.tsx:213`, `removal-notice-*.png` |
| AC-34 | No signal feeds a score before a probe record | PASS as shipped (all `not-probed`, all null). Becomes moot for two sources after F-1 | real API payload, F-1 |
| AC-35 | One coin per basket, move response names old basket | PASS | P5 |
| AC-36 | Open method: ratio, percentile, weighted mean, missing never 0, breadth | PARTIAL | P1, P2 pass; breadth is 7-day not window (F-2) |
| AC-37 | Lines per basket, rebased, gaps, membership line | PARTIAL | payload and gap logic unit-proven; never proven end to end against the real API (F-4); legend with no chart (F-5) |
| AC-38 | X low-trust, caps, token hygiene | PASS by code read and suite; X cannot reach a score (F-1) | `xsearch.py:27,54,121`, I-7 |
| AC-39 | Reddit optional, unavailable without keys | PASS | F-1 repro output shows `reddit unavailable` |
| AC-40 | Discovery tab, top 100, public categories, ranked | PASS functionally; PARTIAL on UI standard | P3; section 6 item 7; F-9, F-12 |
| AC-41 | Outlier rules | PASS (all four) | P3 |
| AC-42 | Clean page | PARTIAL (HY, owner decides) | section 6; no horizontal scroll and design-token gates pass; no "before" shots (I-6) |
| D-1 | Baskets = screener groups, `main` Unassigned, cap 12, rename | PASS | P5 |
| D-3 | Percentiles vs top-100 reference, outside coins placed | PASS (see F-9 on the 100 vs 95 reading) | P1 |
| D-4 | Weights, windows 7/30/90, `insufficient-history` under 90 points | PASS for windows and history; weights file has the F-1 defect | `ratio.py:13`, router enum 422 |

## 8 Tests run and limits

- Everything above ran on `e3e6b63` with no network call to a provider (all attention reads came from tmp parquet and JSON; the API was started with an empty `LSE_API_KEY` and a throwaway cache root).
- Scope not covered: live probes (slice G, owner PC), real provider data shapes (no fixtures of real responses were fetched), CI configuration, behaviour above 12 groups through the UI, the screener page beyond the removal notice.
- Cost: no model spend tracking is exposed to this session; no provider spend. Work was reading, fixture scripts, and the three standard test runs, which dominate wall time, not cost.
- Files I created outside the repo: probe scripts and screenshots in the session scratchpad. Two temporary git worktrees were created for P6 and removed. Servers started for the as-shipped render were stopped.

## 9 Suggested follow-ups for the planner (not done here)

1. Fix F-1 first (rename `exchange`→`exchange_volume`, `x`→`xsearch` in `attention_weights.json` and `discovery.json`, add `hyperliquid_volume` or drop it, delete `SOURCE_WEIGHTS`, add a test that loads the shipped files and asserts every key exists in `registry.FETCHERS`). Do it before slice G probes are recorded.
2. F-2 and F-3 are small API fixes with clear tests.
3. One e2e case that seeds store parquet and probe records, then uses the real attention route (closes F-4).
4. A UI polish slice for section 6 items 1-7, then a before/after screenshot gate.
