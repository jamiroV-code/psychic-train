---
name: spec:narrative-baskets-trends-by-name
description: "T120 (for T100): Google Trends attention by coin NAME for the in-universe coins as comparable daily series with history: keyword design (topic id vs name), anchored batches, backfill, replace-window store mode, where it runs, probes, ACs and slices. Docs only; no code changed."
date: 21-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: spec
---

[MODE: SPEC]

# Narrative Baskets: Google Trends by coin name (T120 for T100, 21-10-26)

Code references were read on `main` (branch `claude/t120-trends-spec`). Providers are unreachable from the author's sandbox, so every live fact is marked UNVERIFIED and has an owner probe in section 4.

## 1. Goal, non-goals, current behaviour

**Goal.** Trends (weight 25, `api/data/discovery.json` `source_weights`) becomes a working attention source: one daily series per in-universe coin, keyed by the coin NAME (unambiguous), all on ONE comparable scale, with about 90 days of history after the first run, fetched in the background with no user workload.

**Non-goals.** No search-volume claims in absolute numbers; no X or Reddit work; no change to the weights; no calibration or backtest work (T103/T105 consume the result); no paid Trends API in this SPEC (listed as an option in the open questions).

**Current behaviour (verified by reading).**
- Runner keyword is the ticker: `_run_trends` calls `trends.fetch_series(s, s.lower(), ...)` (`api/scripts/refresh_attention.py:177-178`). Ambiguous for link, near, sui, pi, gas, sand, render.
- `trends.fetch_series` returns at most ONE point `[(day, value)]` with state `insufficient-history` (`api/data/attention/trends.py:35`); a row dated today is dropped as partial (`trends.py:33-34`). Nothing ever reaches `MIN_HISTORY_DAYS = 90` (`types.py:10`, gate at `registry.py:49`), so Trends contributes nothing to Discovery.
- The adapter asks pytrends for ONE keyword with `timeframe="now 7-d"` (`api/data/pytrends_adapter.py:62`). `now 7-d` rows are hourly (UNVERIFIED), so "last non-partial row" (`pytrends_adapter.py:66-73`) is an hour value, not a day value. Each coin is its own request, so each is scaled 0-100 to itself: two coins' values are NOT comparable.
- `write_series` is first-observation-wins and keeps only days `< today` (`store.py:41-56`, docstring `store.py:3-4`). Stored values from different pulls would therefore sit on different scales and never be corrected.
- `registry.read_series` returns `not-probed` unless `probe_records.json` has the source (`registry.py:39-40`), `ok` only with >= 90 points (`registry.py:49-51`).
- **Likely root cause of the 1-second Trends step (code-verified, log UNVERIFIED):** `pytrends` is NOT in `api/pyproject.toml` dependencies (lines 6-17), and `attention-refresh.yml` runs `uv run --project api python api/scripts/refresh_attention.py --sources trends` (line 207) WITHOUT `--with pytrends`. `_fetch_live` swallows the ImportError and returns `(None, None)` (`pytrends_adapter.py:54-57`), so every coin is `unavailable` instantly. Only `narrative-snapshot.yml:59` passes `--with pytrends`. So the step may never have reached Google at all; a 429 is possible but not proven. This must be fixed before any provider verdict is drawn (AC-T1).
- `pytrends` is archived/unmaintained since 2025-04 per the adapter docstring (`pytrends_adapter.py:3-5`); its own repo status was not re-checked (UNVERIFIED). Google can change the unofficial endpoints at any time.
- **Reusable code already exists** (narrative-v2 RFC-3, for category keywords, not coins): `plan_batches` (anchor + up to 4 others, `pytrends_adapter.py:145`), `chain_batches` (rescale batch b onto batch 0 by `anchor_b0 / anchor_b`, with `ANCHOR_EPSILON = 1.0` guard), `fetch_trends_batched`, and `backfill_pytrends_history.py` (`chained_daily`, 269-day daily window, drops `isPartial`, rejects non-daily frames). This SPEC extends that pattern to coins with a per-day, per-batch anchor ratio; it does not invent a new one.

## 2. Keyword design

**Options.**
- (a) Full coin name as a plain term ("Chainlink"). Cheap, but "Near", "Sui", "Pi", "Sky", "Render", "Link", "Gas", "Sand" collide with common words and unrelated entities.
- (b) Trends TOPIC id (entity mid, e.g. "/g/11..." from the suggestions endpoint; the label shows "Chainlink - Cryptocurrency"). Unambiguous, language independent, one entity per coin.
- (c) Plain term plus category filter (`cat=` Finance) in the request. Reduces but does not remove ambiguity; the category applies to the whole request, so one batch cannot mix filtered and unfiltered terms.

**Recommendation: (b) topic id by default, (a) full name as the explicit fallback for coins that have no good topic, never the ticker.** Reasons: only (b) solves Near/Sui/Pi/Render/Sky/Aave deterministically; a topic also merges spellings and languages; (a) is allowed only where the owner confirms the name is distinctive (for example "Chainlink", "Aave"). Topic ids are UNVERIFIED until the check tool runs on a machine that can reach Google. Caveat: a topic counts searches for the entity, not only the literal word, which is the wanted behaviour for attention.

**File `api/data/trends_keywords.json`** (hand-edited, owner-owned, committed):
```
{"LINK": {"topic": "/m/0....", "label": "Chainlink (Cryptocurrency)", "note": ""},
 "SUI":  {"term": "Sui blockchain", "label": "Sui", "note": "no topic found"},
 "XAUT": {"no-keyword": true, "note": "gold token, no own search interest"}}
```
Rules (validator, run in tests and at load; a bad file makes the Trends source `unavailable` with reason `bad keyword file`, never a crash):
- keys uppercase symbols; each entry has exactly one of `topic`, `term`, `no-keyword: true`;
- `topic` matches `^/(m|g)/[A-Za-z0-9_]+$`; `term` is 2-40 chars of letters, digits, space, `.`, `-`, `'`, `&` (no commas: a comma splits terms in the request URL; no quotes, no slashes);
- all `topic` values unique and all `term` values unique, case-insensitive; `label` non-empty;
- every symbol in `api/data/attention_narratives.json` (75 placed coins today) is present, either with a keyword or `no-keyword` plus a `note`; extra symbols outside the universe are allowed (warn).
- The anchor (section 3) is stored in the same file under a reserved key `_anchor` and is NOT a coin.

**Check tool `api/scripts/check_trends_keywords.py`** (mirrors `check_wiki_titles.py`: owner runs once on their PC, `uv run --project api --with pytrends python -m api.scripts.check_trends_keywords`; reads a candidate map `symbol -> name`, writes nothing to the repo, exit 0 unless the input is unreadable). For each coin it calls pytrends `suggestions(name)` (UNVERIFIED endpoint, same library), prints candidates with `title` and `type` (e.g. "Cryptocurrency", "Blockchain platform"), auto-proposes the first candidate whose type matches a crypto word list (analogue of `CRYPTO_WORDS`, `check_wiki_titles.py:25`), marks `PASS` (one crypto-typed candidate), `AMBIGUOUS` (several or none crypto-typed: owner picks) or `FAIL` (no suggestion, falls back to `term`), sleeps >= 2 s between calls, stops after 3 consecutive 429s, and prints a paste-ready JSON block of the PASS entries plus the list needing a human decision. Tests use a fake client; the real run is an owner step.

## 3. Comparable series

**Anchor method.** Every request carries the anchor plus up to 4 coins (5 terms, the pytrends cap, `BATCH_SIZE = 5`, `pytrends_adapter.py:132`). Within one request all values share a scale, so for a coin c in batch b on day d:

`value(c,d) = raw(c,b,d) / raw(anchor,b,d) * 100`  (anchor expressed as 100 on every day; coin value is "percent of anchor")

Using the SAME-day anchor value in the SAME request makes every batch and every pull comparable, because a re-normalisation of the request rescales coin and anchor together and cancels in the ratio. This is stronger than the existing `chain_batches` (which pins to batch 0's single anchor value, `pytrends_adapter.py:159-187`); per-day ratio also keeps a series on one scale across pulls (AC-T3).
- Guard: if `raw(anchor,b,d) < ANCHOR_EPSILON` (1.0) the day is `insufficient` for that batch, never a fabricated ratio. Integer rounding in Trends (values are ints 0-100, UNVERIFIED) makes small coins coarse: a coin at raw 1 against an anchor at 100 reads 1.0; many small caps will read 0-3. State this honestly in the sources panel as "low resolution".
- **Anchor choice.** The anchor must be searched far more than any coin, stably, and not trend itself. Recommended: the topic "Bitcoin" (UNVERIFIED id; the check tool prints it). Risk: a Bitcoin anchor near 100 crushes small coins to 0-2 (resolution loss). Alternative: a mid-sized stable topic such as "Ethereum" (coins above it then saturate at 100 and clip, losing BTC itself). Section 8 asks the owner; the probe prints raw values for both candidates for 5 sample coins so the choice is evidence-based. BTC and ETH then need their own series; they ride in a batch whose anchor is the other, or the anchor series is stored as raw 100 (constant, useless for change): so BTC is fetched against ETH as a second anchor only (one extra request).
- **Batch math.** Top-100 tradeable coins minus `no-keyword` is about 75-100 keywords: 4 per request gives 19-25 requests per refresh, plus 1 anchor-probe request. At >= 3 s between requests and a jitter, a full pass is about 1.5-3 minutes when there is no throttling. Backfill is the same batch count, one pull per batch (not per coin).
- **Rate limit and retry.** Per-request sleep 3 s plus up to 2 s jitter (UNVERIFIED which rate Google tolerates; probe measures it). On HTTP 429: backoff 30 s, 60 s, 120 s (3 tries), then the batch is marked `rate-limited`; after 3 batches rate-limited in a row the run stops (circuit breaker, the same idea as `CIRCUIT_BREAKER_AFTER = 5`, `refresh_attention.py:34`). The existing adapter backoff (1 s base, 3 tries, `pytrends_adapter.py:34-35`) is too short for 429 and is not reused for this path.
- **Partial failure.** A failed batch leaves the previous stored values for its coins and reports them `unavailable` with reason; it never writes 0 or a NaN-filled day. A coin absent from the frame (all-zero rows come back as 0 or missing, UNVERIFIED) is written only when the anchor is valid; a valid anchor with coin 0 is a real 0.
- **Daily value rule.** Only completed UTC days (`date < today`), `isPartial` rows dropped, matching `store.py:3-4` and `trends.py:33`. Never take today's partial day. Timeframe-to-granularity (UNVERIFIED, from experience with the endpoint): `today 3-m` returns daily points (about 90), `today 12-m` returns weekly points, `now 7-d` hourly, windows up to about 270 days daily (the existing backfill script assumes 269, `backfill_pytrends_history.py` header). Rule: use `today 3-m` for refresh and backfill; reject any frame whose index step is > 1 day (as `_batch_daily` already does) instead of storing weekly values as daily.
- **Backfill.** First run pulls `today 3-m` per batch: about 90 daily points per coin in one pass, so the 90-day gate passes on the first run if the frame has >= 90 complete days (3 months can be 89-92 days: if short, use `today 12-m`-style 270-day daily window `YYYY-MM-DD YYYY-MM-DD` with explicit dates, UNVERIFIED). Daily refresh afterwards repeats the same `today 3-m` pull and REPLACES the overlapping window (below), which also re-anchors every day to the latest normalisation: this is why replace beats append.

**Store semantics: replace-window.**
- Append (today) cannot work: each pull is rescaled, and per-day ratios cancel scale but Google also revises recent days (sampling noise, UNVERIFIED), so first-wins would freeze noisy values.
- Proposed minimal change: `store.write_series(series, today=None, mode="first")` gains `mode="replace-window"`: rows with `d < today` from the new series overwrite stored rows with the same date; stored dates outside the new window are kept; result sorted; atomic write unchanged (`cache._atomic_to_parquet`). Only the Trends runner passes the new mode; other sources keep first-wins, so their tests and files do not change (AC-T6).
- **Frozen snapshots (T105):** signals snapshot files are copies of computed output, not recomputed from the store, so replacing stored Trends values does not alter them (UNVERIFIED which module writes them: the slice must confirm with a hash test over a frozen file before and after, AC-T7).
- **Point-in-time history (T103):** the history chart recomputes each past day from stored points, so a replaced window revises past Trends scores. Decision for the owner: (1) "stored as first seen" = keep a second per-day column `first_value`, never overwritten, used by history and calibration; `value` carries the latest revised series used by live Discovery; or (2) "revised" = history uses the revised series (simple, better scale consistency, but past scores can change after the fact and a backtest sees later information). Recommendation: (1) for calibration honesty, but it costs a store column and a reader flag, so ship (2) in T100b with a recorded `revision_count` log and add (1) only if the owner wants backtests on Trends. Open question 3.

## 4. Where it runs, and evidence first

- **A. GitHub runner (`refresh-extra`).** No new code location. Needs `--with pytrends` (the missing flag above) and a time budget longer than the current `timeout-minutes: 8` is NOT needed if the pass is about 3 minutes; cloud IPs are commonly 429ed by Google (workflow comment `attention-refresh.yml:23`, UNVERIFIED for this repo).
- **B. Owner's PC, in-API background worker (W8, not built).** Same worker pattern as `refresh_worker.py` / `equities_refresh.py` (`narrative-baskets-weighted-signal_SPEC` section W8): `fetch_side = pc_side` for `trends`. Residential IP is likely not blocked (UNVERIFIED). Catch-up after days off works for Trends because a `today 3-m` pull refills the gap. Cost 4-6 USD for W8 itself.
- **C. Manual owner-run script writing into the cache.** `uv run --project api --with pytrends python -m api.scripts.refresh_attention --sources trends` on the PC; no new infrastructure. The cache is not committed, so the dashboard must run on that PC (as W8 assumes).
- **Evidence first.** Design two probes, one script `api/scripts/probe_trends.py` (read-only, writes nothing): ONE anchored request `[anchor, 4 coins]`, `today 3-m`, prints HTTP/exception class, latency, row count, index step (daily or not), the number of complete days, and the first 5 and last 5 rows of the frame. No secrets, no cache write. Probe P-PC: owner runs it on their PC with `--with pytrends`. Probe P-GH: a `workflow_dispatch` step (`probe-trends` in a new small workflow, or an input on `attention-refresh.yml`) running the same script; its log answers "is it blocked from GitHub, or was it only the missing package". Both print `pytrends` version.
- **Order.** (1) Run P-GH and P-PC. (2) If GitHub succeeds with latency < 5 s and >= 90 daily rows: option A. (3) If GitHub 429s and PC succeeds: B (needs W8) or C meanwhile. (4) If both fail: stop; evaluate alternatives (a paid or official-API Trends data source, owner decision; out of scope here) and mark Trends `unavailable` honestly. Only then build T100b/T100c.

## 5. Interaction with the weighted system, universe, calibration

- **Weight 25 and history gates.** The series feeds `_source_change` (recent mean vs prior mean, rising threshold `rising_threshold_pct` 10; lag cap `max_source_lag_days` 3, `discovery.json`). Trends needs >= 90 points to be `ok` (`registry.py:49`), which the backfill satisfies on day one; the lag rule needs the newest stored day within 3 days of `end`, so a failed refresh for 3+ days drops Trends from that coin (correct, visible).
- **Ratio-to-anchor and the +10 percent rule.** A percent change of "percent of anchor" mixes coin and anchor movement: if Bitcoin interest spikes, every coin's ratio falls. That is a real property (relative attention), but it can hide a market-wide rise. Slice T100b records the anchor's own raw level beside each batch in the log so the owner can see anchor-driven drops (risk R2). `min_covered_weight` 30 is unaffected.
- **Universe/exchange work.** 19 coins show no source data today (T108 universe work, `narrative-baskets-universe-narratives_SPEC`); Trends by name covers coins with no Wikipedia article, no Binance listing and no CoinGecko attention row, since it needs only a name. It should lift covered weight by up to 25 for those coins. Coins marked `no-keyword` stay uncovered and are counted in the sources panel.
- **Calibration (T103/T105).** Frozen signal files must not change (AC-T7). Because replace-window revises history, calibration plans that read Trends from the store must use the first-seen column once decided (question 3); until then a note on the calibration plan says Trends history is "revised".

## 6. Acceptance criteria, out of scope

- **AC-T1** The refresh workflow's trends step runs with `pytrends` installed (`--with pytrends` or a declared extra), and its log line states the failure class (`import-failed`, `http-429`, `empty-frame`, `ok`) instead of one generic `unavailable`.
- **AC-T2** `api/data/trends_keywords.json` passes the validator: unique non-empty topic/term values, safe characters, every symbol of the 75 placed coins present or `no-keyword` with a note; test fails when one is added to `attention_narratives.json` without an entry.
- **AC-T3** With a fake transport that renormalises each request differently (scale 0.5, 2.0), the anchored values for the same coin are identical across batches and across two pulls (tolerance 1e-9).
- **AC-T4** A batch whose anchor is below `ANCHOR_EPSILON` yields no value for its coins on that day; no 0 is written.
- **AC-T5** A fake 429 on one batch leaves that batch's coins unchanged in the store (previous values intact), other batches update, the run exit is success with a `rate-limited` count, and 3 consecutive 429s stop the run.
- **AC-T6** `write_series(..., mode="replace-window")` overwrites overlapping dates, keeps older dates, drops `d >= today`; the default mode behaves exactly as before (existing store tests unchanged and green).
- **AC-T7** Hash of every existing signals snapshot file is identical before and after a Trends replace run (frozen snapshots untouched).
- **AC-T8** A frame with a step > 1 day is rejected as `non-daily`; the day equal to today and `isPartial` rows are never stored.
- **AC-T9** A 90-day fake frame yields state `ok` through `registry.read_series` on the first run (probe record permitting); an 80-day frame yields `insufficient-history` with the day count.
- **AC-T10** `check_trends_keywords` with a fake client prints PASS/AMBIGUOUS/FAIL per coin and a paste-ready block, and writes no file.
- **AC-T11** `probe_trends` prints status, latency, row count, step and first/last rows for a fake and for an injected failure; the output contains no header, cookie or token.
- **AC-T12** The sources panel shows, per source, the last stored day and the last failure class for Trends (T100c).

**Out of scope.** Choosing a paid Trends API; per-region or per-language series; related-queries or rising-queries; Reddit/X; weights; web redesign beyond the status line; building W8 itself.

## 7. Slices, tiers, rough cost

| Slice | Files | Tier | USD |
|---|---|---|---|
| T100a keyword file, validator, check tool, probe script | `api/data/trends_keywords.json` (starts as `no-keyword`/term placeholders), `api/data/attention/trends_keywords.py`, `api/scripts/check_trends_keywords.py`, `api/scripts/probe_trends.py`, tests | RT1 | 2-3 |
| T100b anchored batches + backfill + replace-window | `api/data/attention/trends.py`, `api/data/pytrends_adapter.py` (additive), `api/data/attention/store.py`, `api/scripts/refresh_attention.py` runner, tests with a fake transport | RT1-RT2 | 4-6 |
| T100c wiring and status | `.github/workflows/attention-refresh.yml` (`--with pytrends`, failure classes, optional `probe-trends` dispatch), `probe_records.json` via `record_probe.py`, sources panel line (`web/`, UNVERIFIED file) | RT2 | 2-3 |
| W8 dependency | in-API worker for `pc_side` (only if option B wins) | RT2-RT3 | 4-6 |

Order: probes (owner, after T100a) then T100b then T100c; W8 only if the probes say GitHub is blocked.

## 8. Risks and open questions

**Risks.** R1 `pytrends` is archived and Google can break the endpoint at any time (a presumed-dead path already exists, `pytrends_adapter.py:37` (`PYTRENDS_DEAD_THRESHOLD_DAYS`)). R2 anchor movement leaks into every coin's change. R3 low resolution for small coins (integer 0-100 against a large anchor). R4 sampling noise: Google samples, so day values can differ by a few points between pulls (UNVERIFIED size), which can by chance cross the +10 percent threshold: the 7-day recent mean smooths this. R5 revised history changes past scores (question 3). R6 Trends terms of use for automated access are unclear (UNVERIFIED); keep volume low. R7 topic ids can be retired or changed; the validator cannot detect that, the probe/check tool re-run does.

**Open questions for the owner.**
1. Anchor: Bitcoin topic (recommended default, crushes small caps) or Ethereum topic (saturates BTC) or two anchors (one per size band, more requests)? The probe prints evidence for both.
2. Topic id by default with name fallback (recommended), or names only (simpler, ambiguous for about 8 listed coins)?
3. History: revised (simple, recommended first) or first-seen column too (honest backtests, more code)?
4. Run location: decide after probes; are you willing to run the PC probe and keep the API running on that PC if B wins?
5. If both probes fail: accept Trends as permanently `unavailable` (weight 25 rescaled away per the weighted rule) or fund a paid data source?

**Follow-up T134 (21-10-26).** Question 2 is answered by evidence for 12 coins: the owner's checker run gave 12 topic ids (AAVE ADA ARB BCH BTC DOGE DOT INJ LINK LTC SHIB SOL), seeded in `trends_keywords.json`. Checker v2 widens the accepted Google types (Currency, Coin, Chain, Blockchain platform, Distributed ledger, Payment network, Cryptocurrency exchange company) and adds name-match and prefix rules; coins still AMBIGUOUS after the owner's re-run are the name-fallback candidates for T100b.
