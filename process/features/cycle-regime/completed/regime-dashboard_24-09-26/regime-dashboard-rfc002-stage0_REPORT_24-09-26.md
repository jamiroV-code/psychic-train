# RFC-002 Stage 0 — Pre-Phase Research Findings (+ RFC-001 live test, yfinance)

**Date**: 24-09-26
**Status**: 🧪 Stage 0 complete — awaiting user approval before implementation

> **TL;DR** — LiqTide's "unpublished" normalisation is reproduced exactly: every component is
> `sign × tanh(impulse / scale)` with round-number scales. On today's live payload all six match
> LiqTide to 4 decimals, and the impulses themselves reproduce from FRED/DefiLlama/LiqTide series
> to the published figures (stablecoins within 0.2%). Proposal: replace ADR-5's z-score assumption
> with this exact formula, and build net liquidity on the Wednesday grid with FRED `WDTGAL`
> (matches LiqTide's net liquidity to the $M on all 4 dates checked). yfinance: not useful for this
> dashboard.

How: the sandbox can't reach these hosts, so data was read in the browser pane on the user's PC
(LiqTide payload downloaded with permission, SHA-256 `c0af7912…c0d22a`, 77,569 bytes; FRED and
DefiLlama values computed in-page).

---

## 1. RFC-001 live test (real payload, 2026-09-24T00:53:56Z)

Replayed through the new `fetch_latest` + `snapshot_liqtide.py` + `backfill_liqtide_series.py`
against a copy of the real archive (existing `2026-09-20.parquet` + new day):

| Check | Result |
|---|---|
| Run 1 | exit 0, `tide_value 55.0`, label SLACK WATER, arithmetic check clean, raw file written |
| Run 2 (same day) | exit 0, raw + parquet unchanged (append-only holds) |
| Raw JSON vs download | identical content |
| Old + new schema read together | ✅ (`tide_value` NaN for 09-20, 55.0 for 09-24) |
| Backfill | 17 series; `tide_value` 107 weekly points 2024-09-04→2026-09-16; `btc_dom` 161 points from 2025-06-10; `etf_flows` 12 daily points 2026-09-08→09-23 |
| `--coverage` | 2 days, 1 raw day, gap 09-20→09-24 flagged |

These three files were then written into the real archive (new files only, nothing overwritten):
`api/data/cache/liqtide/2026-09-24.parquet`, `raw/2026-09-24.json`, `backfill/2026-09-24.parquet`.

Not possible from here: running `pytest` on the PC (Windows allows click-only control of
terminals) and creating the Task Scheduler job — both remain user steps. The downloaded temp file
`Downloads\20eb02d4-c65e-4d4d-861c-9c82897c548a.tmp` can be deleted.

Note: the web-fetch tool used in RFC-001 Stage 0 served a cached payload (value 52); the live one
today is 55, score 0.0911 — arithmetic re-verified: Σ w·c = 0.09109 → 50 + 50 × 0.0911 = 54.55 → 55.

## 2. LiqTide normalisation — reproduced exactly

`signals` in the payload carries the raw impulses. Fitting `component = sign × tanh(impulse/scale)`:

| Component | Impulse (signals) | Scale | Sign | Model | Published | Implied scale |
|---|---|---|---|---|---|---|
| net_liquidity_4w | netliq_d4w −$59.511bn | $150bn | + | −0.3772 | −0.3772 | 149.98bn |
| stablecoin_7d | stables_pct7 0.7124% | 1% | + | 0.6122 | 0.6122 | 0.99995% |
| dollar_1m | dollar_pct1m 0.9976% | 2% | − | −0.4612 | −0.4612 | 1.99986% |
| rrp_release_4w | rrp_d4w −$0.241bn | $75bn | − | 0.0032 | 0.0032 | ~75bn (small-value) |
| etf_flow_5d | etf_flow5 $2.3386bn | $1bn | + | 0.9816 | 0.9816 | 0.9995bn |
| rotation_30d | btc_dom_d30 −0.445pp | 2pp | − | 0.2190 | 0.2190 | 1.99955pp |

One payload, but six independent exact fits with round scales is strong evidence. The daily raw
archive re-checks it every day (proposed cross-check script, §5).

## 3. Impulses — reproduced from primaries

| Impulse | Our definition | Check against LiqTide (09-24 payload) |
|---|---|---|
| Net liquidity | Wednesday grid: `WALCL − WDTGAL − RRPONTSYD×1000` (all FRED, keyless) | $6,004.208bn (2024-09-04), 5,808.976 (08-19), 5,896.482 (09-09), 5,749.465 (09-16) — **exact on all 4** |
| netliq_d4w | value − value 28 days earlier (weekly grid) | 5,749.465 − 5,808.976 = −59.511 ✓ |
| dollar_pct1m | DTWEXBGS / DTWEXBGS as-of 30 calendar days earlier − 1 | 119.5133 / 118.3328 − 1 = 0.9976% ✓ (LiqTide's `dollar` **is** DTWEXBGS: 122.5144 on 2024-09-04 both) |
| rrp_d4w | RRPONTSYD − as-of 28 days earlier | 0.461 − 0.702 = −0.241 ✓ |
| btc_dom_d30 | btc_dom − as-of 30 days earlier (pp) | 58.7920 − 59.2372 = −0.4451 ✓ |
| etf_flow5 | sum of last 5 daily net flows | 159.5 + 433.0 + 999.0 + 714.7 + 32.4 = 2,338.6M ✓ |
| stables_pct7 | DefiLlama total / as-of 7 days earlier − 1 | 0.7110% vs 0.7124% (LiqTide's total is ~0.5% higher — different coin set). Component 0.6113 vs 0.6122 |

Consequences:
- The existing `fetch_net_liquidity` (WTREGEN weekly **average**, daily as-of) differs from
  LiqTide's by up to $115bn on 09-16. The new module uses WDTGAL on the Wednesday grid; the
  existing function stays untouched (leg path) and is added to the backlog note.
- `WDTGAL` starts 2002-12-18 → net liquidity has 20+ years.
- All windows are calendar as-of lookups (VALIDATE P4) — confirmed to be what LiqTide does.

## 4. yfinance assessment

| Question | Finding |
|---|---|
| Licence / key | Apache-2.0, no key. Latest 1.7.0 (2026-08-26), releases every few weeks |
| Terms | Not affiliated with Yahoo; "the Yahoo! finance API is intended for personal use only" |
| Works? | Yes from your PC — chart endpoint returned DXY from 1985, BTC-USD from 2014, IBIT from 2024-01-08, S&P 500 from 1984. (`range=max` silently falls back to monthly bars; daily needs explicit periods) |
| Adds for this dashboard | **Nothing.** LiqTide's dollar input is FRED DTWEXBGS, not ICE DXY; Yahoo has no ETF **flows** (only prices/volume) and no BTC dominance |
| Other use | Equities/indices if the "crypto only" decision is revisited — but personal-use-only, same licensing wall as LSE at public launch; the data-sources doc already says "avoid Yahoo Finance (unsupported, unpredictable)" |

Verdict: not adopted. Backlog note written for the equity decision.

## 5. Proposed RFC-002 changes (need approval)

1. **ADR-5 replaced:** normalisation = `sign × tanh(impulse / scale)` with the §2 scales;
   composite = `50 + 50 × Σ wᵢxᵢ / Σ wᵢ(present)`, rounded like LiqTide for the published-scale
   value (unrounded kept for the chart). The 90-obs z-score warm-up (P6) is dropped — no longer needed.
2. **Net liquidity on the Wednesday grid with `WDTGAL`** (new constant in `fred_adapter`,
   fetched by the existing generic `fetch_series`).
3. **Component frequencies:** net liquidity weekly (Wednesdays); dollar, RRP, stables, BTC dom,
   ETF daily. The shared date grid (P3) handles the mix.
4. **ETF flows:** RFC-002 reads LiqTide's `etf_flows` backfill (12 days) + daily archive; RFC-003
   (Farside) adds history from 2024-01-11.
5. **New cross-check script** `api/scripts/check_component_reproduction.py`: for each raw archived
   day, compare our six components with LiqTide's published ones and print the differences.

Approval needed before implementation.
