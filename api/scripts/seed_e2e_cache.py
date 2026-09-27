"""Seed a throwaway Parquet cache for the Playwright E2E. Writes nothing live.

Run by `web/playwright.config.ts` immediately before uvicorn starts, with
`SCREENER_CACHE_ROOT` and `SCREENER_WATCHLIST_PATH` pointing at a temp tree.

Why seeding rather than mocking: the E2E exists to cover the boundaries the
unit suites structurally cannot — the real client, real CORS, real FastAPI
routing, real adapter, real DuckDB read. Intercepting HTTP in the browser
would test the UI against a fixture of what we *believe* the API returns,
which is the same mistake the vitest suites already make by injecting
`fetchBoard`. So every layer stays real and only the exchange is absent.

The exchange is absent because the seeded bars are FRESH: `fetch_ohlcv`'s
cache-fresh check now runs above exchange construction, so a warm cache is
served without a market list being loaded. The bars are therefore anchored to
*now*, not to a fixed date — a fixture ending last Tuesday would be stale and
the API would reach for the network.

Safety: refuses to run unless `SCREENER_CACHE_ROOT` is set AND differs from
`cache.DEFAULT_CACHE_ROOT`. Three live-data incidents in two days (the
watchlist deletion, the cache-writing tests, the weekly overwrite) is enough
to justify an explicit guard rather than a convention.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd

# Symbols. BTC and HYPE are the two benchmark candidates and must exist
# whichever way the regime switch falls; THIN deliberately carries fewer than
# MIN_BARS_REQUIRED bars so the "not enough history" path is exercised.
WATCHLIST = ["BTC", "ETH", "THIN"]
BENCHMARKS = ["BTC", "HYPE"]
THIN_SYMBOL = "THIN"

# 500 daily bars is chosen, not arbitrary: `1w` is derived from `1d`, and
# MIN_BARS_REQUIRED is 60, so the weekly series needs >= 60 weeks behind it or
# every panel reports insufficient history and the board proves nothing.
BAR_COUNTS = {"15m": 120, "1h": 120, "4h": 120, "1d": 500}
THIN_BAR_COUNT = 20  # below MIN_BARS_REQUIRED (60) on purpose

FLOOR_FREQ = {"15m": "15min", "1h": "1h", "4h": "4h", "1d": "D"}
STEP = {"15m": "15min", "1h": "1h", "4h": "4h", "1d": "D"}

MANIFEST_PATH = _REPO_ROOT / "web" / "e2e" / ".fixture-manifest.json"

# --- /regime fixture (RFC-006) ---------------------------------------------
# Every input `/api/regime/components` reads, synthetic and deterministic,
# written through the same cache functions the adapters use so the API is
# served entirely from cache:
#   - FRED + DefiLlama parquet files are written now, so their mtime is inside
#     the adapters' 6h FRESH_TTL_SECONDS and no live re-fetch happens;
#   - the Farside parquet plus today's `<date>|ok` attempt marker make
#     `fetch_btc_spot_flows` serve its cache without requesting the page;
#   - LiqTide is only ever read from its archive by this endpoint.
# Each series starts on a different date (like reality), the history spans
# more than 3 years so the default 3-year view is a real sub-range, and the
# dollar index carries ONE deliberate multi-week hole so the API emits a
# `gap_before` flag the E2E can find.
REGIME_YEARS = 4
REGIME_FIRST_DATES = {  # days before today that each input starts
    "DTWEXBGS": 4 * 365 + 60,
    "RRPONTSYD": 4 * 365 + 20,
    "WALCL": 4 * 365,
    "WDTGAL": 4 * 365 - 21,
    "stablecoin_supply": 3 * 365 + 200,
    "btc_dom": 450,
    "tide_series": 2 * 365,
}
GAP_SERIES = "DTWEXBGS"
GAP_COMPONENT = "broad_dollar"
GAP_START_DAYS_AGO = 400  # hole: [today-400, today-400+GAP_LENGTH_DAYS)
GAP_LENGTH_DAYS = 28
ETF_FIRST_DATE = "2024-01-11"  # US spot-BTC ETF launch; the component is n/a before it
LIQTIDE_ARCHIVE_DAYS = 5


def _guard() -> Path:
    from api.data import cache

    raw = os.environ.get("SCREENER_CACHE_ROOT")
    if not raw:
        sys.exit(
            "REFUSING: SCREENER_CACHE_ROOT is not set.\n"
            "Without it this would seed fixture bars into the real cache and "
            "overwrite live market data."
        )
    root = Path(raw).resolve()
    if root == cache.DEFAULT_CACHE_ROOT.resolve():
        sys.exit(
            f"REFUSING: SCREENER_CACHE_ROOT points at the real cache ({root}).\n"
            "Point it somewhere disposable."
        )
    return root


def _bars(timeframe: str, count: int, base: float) -> pd.DataFrame:
    """A deterministic rising series whose newest bar is the current, still-open
    one for this timeframe — so `_cache_is_fresh` is True and no exchange is
    contacted."""
    end = pd.Timestamp.now(tz="UTC").floor(FLOOR_FREQ[timeframe])
    idx = pd.date_range(end=end, periods=count, freq=STEP[timeframe], tz="UTC")
    n = range(count)
    return pd.DataFrame(
        {
            "timestamp": idx,
            "open": [base + i for i in n],
            "high": [base + i + 5 for i in n],
            "low": [base + i - 5 for i in n],
            "close": [base + i + 1 for i in n],
            "volume": [1000 + i for i in n],
            "source": ["e2e-fixture"] * count,
        }
    )


def _wave(n: int, base: float, amp: float, period: float) -> list[float]:
    """Deterministic smooth series (no randomness): base + amp*sin(2*pi*i/period) + slow drift."""
    return [base + amp * math.sin(2 * math.pi * i / period) + base * 0.0002 * i for i in range(n)]


def build_regime_fixture(today: pd.Timestamp) -> dict:
    """Pure: the synthetic regime inputs for `today` (tz-naive, normalised) plus
    the facts the E2E asserts against. Writes nothing."""
    def start(key: str) -> pd.Timestamp:
        return today - pd.Timedelta(days=REGIME_FIRST_DATES[key])

    def frame(dates: pd.DatetimeIndex, values: list[float]) -> pd.DataFrame:
        return pd.DataFrame({"date": dates, "value": values})

    bdays = lambda key: pd.bdate_range(start(key), today)  # noqa: E731
    wednesdays = lambda key: pd.date_range(start(key), today, freq="W-WED")  # noqa: E731

    dollar_dates = bdays("DTWEXBGS")
    hole_start = today - pd.Timedelta(days=GAP_START_DAYS_AGO)
    hole_end = hole_start + pd.Timedelta(days=GAP_LENGTH_DAYS)  # exclusive
    dollar_dates = dollar_dates[(dollar_dates < hole_start) | (dollar_dates >= hole_end)]
    expected_gap_date = dollar_dates[dollar_dates >= hole_end][0]  # tz-naive here; formatted below

    walcl = wednesdays("WALCL")
    tga = wednesdays("WDTGAL")
    rrp = bdays("RRPONTSYD")
    stable = pd.date_range(start("stablecoin_supply"), today, freq="D", tz="UTC")
    # UTC-aware dates, exactly like `fred_adapter._parse_csv` stores them —
    # a tz-naive seed breaks `liquidity_composite`'s merge with the (UTC)
    # DefiLlama series, which the real cache never does.
    utc = lambda idx: idx.tz_localize("UTC")  # noqa: E731
    walcl, tga, rrp, dollar_dates = utc(walcl), utc(tga), utc(rrp), utc(dollar_dates)
    fred = {
        "WALCL": frame(walcl, _wave(len(walcl), 7.2e6, 2.5e5, 26)),        # millions USD
        "WDTGAL": frame(tga, _wave(len(tga), 7.5e5, 1.2e5, 13)),            # millions USD
        "RRPONTSYD": frame(rrp, _wave(len(rrp), 400.0, 150.0, 90)),         # billions USD
        "DTWEXBGS": frame(dollar_dates, _wave(len(dollar_dates), 120.0, 3.0, 60)),
    }
    stablecoin = frame(stable, _wave(len(stable), 1.5e11, 4e9, 45))

    etf_dates = pd.bdate_range(ETF_FIRST_DATE, today - pd.Timedelta(days=1))
    etf = pd.DataFrame({"date": etf_dates, "net_flow_usd_m": _wave(len(etf_dates), 50.0, 400.0, 20)})

    tide_dates = pd.date_range(start("tide_series"), today, freq="W-MON")
    tide_values = _wave(len(tide_dates), 50.0, 20.0, 30)
    dom_dates = pd.date_range(start("btc_dom"), today, freq="D")
    dom_values = _wave(len(dom_dates), 57.0, 3.0, 70)

    raws = []
    for back in range(LIQTIDE_ARCHIVE_DAYS - 1, -1, -1):
        day = today - pd.Timedelta(days=back)
        iso = day.strftime("%Y-%m-%d")
        value = round(50 + 10 * math.sin(back), 2)
        raws.append((iso, {
            "generated_utc": f"{iso}T12:00:00Z",
            "tide_index": {"value": value, "score": (value - 50) / 50, "label": "neutral"},
            "tide_series": [[d.strftime("%Y-%m-%d"), round(v, 4)] for d, v in zip(tide_dates, tide_values) if d <= day],
            "metrics": {
                "btc_dom": {"value": dom_values[-1 - back],
                            "series": [[d.strftime("%Y-%m-%d"), round(v, 4)] for d, v in zip(dom_dates, dom_values) if d <= day]},
            },
            "source": "e2e-fixture",
        }))

    return {
        "fred": fred,
        "stablecoin": stablecoin,
        "etf": etf,
        "liqtide_raw": raws,
        "facts": {
            "today": today.strftime("%Y-%m-%d"),
            "input_first_dates": {
                **{sid: df["date"].min().strftime("%Y-%m-%d") for sid, df in fred.items()},
                "stablecoin_supply": stable.min().strftime("%Y-%m-%d"),
                "etf_flows": etf_dates.min().strftime("%Y-%m-%d"),
                "btc_dom": dom_dates.min().strftime("%Y-%m-%d"),
                "tide_series": tide_dates.min().strftime("%Y-%m-%d"),
            },
            "gap": {
                "series": GAP_SERIES,
                "component": GAP_COMPONENT,
                "hole_start": hole_start.strftime("%Y-%m-%d"),
                "hole_end_exclusive": hole_end.strftime("%Y-%m-%d"),
                "expected_gap_date": expected_gap_date.strftime("%Y-%m-%d"),
            },
            "etf_first_date": ETF_FIRST_DATE,
            "liqtide_archive_dates": [iso for iso, _ in raws],
            "default_years": 3,
            "panel_ids": ["net_liquidity", "stablecoin_supply", "broad_dollar", "rrp_release",
                          "etf_flows", "btc_dominance", "composite"],
        },
    }


def seed_regime(today: pd.Timestamp | None = None) -> dict:
    """Write the regime fixture through the adapters' own cache functions.
    Caller must already have passed `_guard()`. Returns the manifest facts."""
    from api.data import cache, etf_flows_adapter, liqtide_adapter

    today = today if today is not None else pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    fixture = build_regime_fixture(today)
    for series_id, df in fixture["fred"].items():
        cache.write_liquidity_series(series_id, df)
    cache.write_liquidity_series("stablecoin_supply", fixture["stablecoin"])
    etf_flows_adapter.merge_into_cache(fixture["etf"])
    etf_flows_adapter._record_attempt("ok")  # today's attempt done -> no Farside request
    for iso, raw in fixture["liqtide_raw"]:
        cache.write_liqtide_raw(iso, raw)
        payload = liqtide_adapter._parse_payload(raw)
        cache.write_liqtide_payload(iso, liqtide_adapter._payload_to_row(payload))
    return fixture["facts"]


# --- /narrative fixture (narrative dashboard RFC-6) ------------------------
# Every store `GET /api/narrative/history` reads, written through the REAL
# cache writers (`write_narrative_point`, `write_exchange_market_snapshot`,
# `write_exchange_point`) so the E2E crosses the real writer/reader boundary
# (Standing Lesson #7). Keying matches `history.load_category_series`:
# pytrends/reddit by the seed's keywords[0], everything else by category id.
# Dates are UTC calendar dates — the same clock `/history` uses for "today"
# (ADR-6 timezone boundary).
#
# Designed-in shape (the expected ranks/signs below are derived by hand from
# this shape, NOT by calling history.py, so the E2E is not self-validating):
#   ai        rising to its max on day 0 (composite 1.0 -> rank 1); pytrends
#             nightly has a hole (days -12..-9) -> gap_before on day -8;
#             60 days of backfilled pytrends before the nightly start, of
#             which days -29..-20 overlap coingecko-narrative -> 10 mixed-scale
#             composite points; legacy coingecko rows; 2 new listings on day 0.
#   l2s       flat (every source normalises to 0.5 -> rank 2), composite only
#             from day -2 -> no 7..9-day baseline -> change delta null.
#   memecoins falling to its min on day 0 (composite 0.0 -> rank 3, delta < 0).
#   rwa       only exchange volume, unavailable (no-hyperliquid-market) ->
#             < 2 composite sources on every date -> comparison rank null.
#   reddit    never written for any category (RFC-4 C1: no credentials, no row)
#             -> `unavailable / no-archived-data`.
#   exchange  day -1 = first market snapshot, listings `no-baseline-yet`;
#             day 0 = second snapshot with two new ai perps.
# `coingecko_trending.parquet` is deliberately NOT seeded: with no trending
# snapshot, `/categories` (hit by /screener's NarrativeStrip) cannot fall back
# to a cached snapshot and write legacy coingecko rows mid-run.
NARRATIVE_NIGHTLY_DAYS = 20          # days 0..-19
NARRATIVE_GAP_DAYS = (9, 10, 11, 12)  # ai pytrends nightly hole
NARRATIVE_BACKFILL_DAYS = 60         # days -20..-79, ai only
NARRATIVE_AI_CG_DAYS = 30            # ai coingecko-narrative days 0..-29
NARRATIVE_L2S_DAYS = 3               # l2s days 0..-2
NARRATIVE_LEGACY_DAYS = 5
NARRATIVE_NEW_AI_PERPS = ["TAO", "WLD"]
NARRATIVE_BASE_PERPS = ["BTC", "ETH", "HYPE", "SOL", "DOGE", "ARB"]


def build_narrative_fixture(today: pd.Timestamp) -> dict:
    """Pure: the synthetic narrative rows for UTC `today` (tz-naive date) plus
    the facts the E2E asserts against. Writes nothing."""
    from api.analytics.narrative import mapping, trigger

    seeds = {c["id"]: c for c in trigger.load_seed_categories()}
    kw = {cid: c["keywords"][0] for cid, c in seeds.items()}
    day = lambda k: (today - pd.Timedelta(days=k)).strftime("%Y-%m-%d")  # noqa: E731

    points: list[tuple[str, str, str, float, str]] = []  # source, key, date, raw, status

    def add(source: str, key: str, ks, value, status: str = "fresh") -> None:
        for k in ks:
            points.append((source, key, day(k), float(value(k)), status))

    nightly = [k for k in range(NARRATIVE_NIGHTLY_DAYS) if k not in NARRATIVE_GAP_DAYS]
    add("pytrends", kw["ai"], nightly, lambda k: 100 - 3 * k)
    add("pytrends", kw["ai"], range(NARRATIVE_NIGHTLY_DAYS, NARRATIVE_NIGHTLY_DAYS + NARRATIVE_BACKFILL_DAYS),
        lambda k: 90 - (k - NARRATIVE_NIGHTLY_DAYS) % 30, status="backfilled")
    add("coingecko-narrative", "ai", range(NARRATIVE_AI_CG_DAYS), lambda k: 40 - k)
    add("coingecko", "ai", range(NARRATIVE_LEGACY_DAYS), lambda k: 1)
    add("pytrends", kw["memecoins"], range(NARRATIVE_NIGHTLY_DAYS), lambda k: 20 + 3 * k)
    add("coingecko-narrative", "memecoins", range(NARRATIVE_NIGHTLY_DAYS), lambda k: 1 + k)
    add("pytrends", kw["l2s"], range(NARRATIVE_L2S_DAYS), lambda k: 50)
    add("coingecko-narrative", "l2s", range(NARRATIVE_L2S_DAYS), lambda k: 3)

    d1, d0 = day(1), day(0)
    markets = {d1: list(NARRATIVE_BASE_PERPS), d0: list(NARRATIVE_BASE_PERPS) + NARRATIVE_NEW_AI_PERPS}
    volume = {"ai": (0.02, 0.05), "l2s": (0.10, 0.10), "memecoins": (0.08, 0.03)}  # (day -1, day 0)
    exchange: dict[str, list[dict]] = {}
    for cid in seeds:
        rows = []
        for when, idx in ((d1, 0), (d0, 1)):
            vs = volume.get(cid)
            first = when == d1
            rows.append({
                "date": when,
                "volume_share": vs[idx] if vs else None,
                "volume_status": "ok" if vs else "unavailable",
                "volume_reason": None if vs else "no-hyperliquid-market",
                "new_listing_count": None if first else (len(NARRATIVE_NEW_AI_PERPS) if cid == "ai" else 0),
                "listing_status": "unavailable" if first else "ok",
                "listing_reason": "no-baseline-yet" if first else None,
                "baseline_date": None if first else d1,
            })
        exchange[cid] = rows

    curated = mapping.load_category_map()
    narrative_only = sorted(
        s for s, cid in curated.items() if cid == "ai" and mapping.map_coin_to_narrative_category(s)[1]
    )

    return {
        "points": points,
        "markets": markets,
        "exchange": exchange,
        "facts": {
            "today": d0,
            "day_minus_1": d1,
            "category_ids": sorted(seeds),
            "keywords": kw,
            "gap": {"category": "ai", "series": "pytrends-nightly-7d", "gap_date": day(8)},
            "ai_backfill_range": [day(NARRATIVE_NIGHTLY_DAYS + NARRATIVE_BACKFILL_DAYS - 1), day(NARRATIVE_NIGHTLY_DAYS)],
            "ai_chart_points": NARRATIVE_NIGHTLY_DAYS + NARRATIVE_BACKFILL_DAYS,  # days 0..-79, hole filled by coingecko-narrative
            "ai_mixed_scale_points": NARRATIVE_AI_CG_DAYS - NARRATIVE_NIGHTLY_DAYS,
            "ai_new_listings": len(NARRATIVE_NEW_AI_PERPS),
            "ai_legacy_count": 1,
            "narrative_only_symbol": narrative_only[0] if narrative_only else None,
            # Hand-derived from the designed shape above.
            "comparison": [
                {"category_id": "ai", "rank": 1}, {"category_id": "l2s", "rank": 2},
                {"category_id": "memecoins", "rank": 3},
                {"category_id": "rwa", "rank": None, "reason": "no-composite-on-as-of"},
            ],
            "change": [
                {"category_id": "ai", "rank": 1, "sign": 1},
                {"category_id": "memecoins", "rank": 2, "sign": -1},
                {"category_id": "l2s", "rank": None, "reason": "no-baseline-in-window"},
                {"category_id": "rwa", "rank": None, "reason": "no-composite-on-as-of"},
            ],
            "no_market_category": "rwa",
            "panel_cap_note": "only 4 seed categories exist; the 10-panel cap/overflow is unit-tested only",
        },
    }


def seed_narrative(today: pd.Timestamp | None = None) -> dict:
    """Write the narrative fixture through the real cache writers. Caller must
    already have passed `_guard()`. Returns the manifest facts."""
    from api.data import cache

    today = today if today is not None else pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    fixture = build_narrative_fixture(today)
    for source, key, when, raw, status in fixture["points"]:
        cache.write_narrative_point(source, key, when, raw, source_status=status)
    for when, names in fixture["markets"].items():
        cache.write_exchange_market_snapshot(when, names)
    for cid, rows in fixture["exchange"].items():
        for row in rows:
            cache.write_exchange_point(cid, row)
    return fixture["facts"]


# --- /onchain fixture (chain-growth RFC-6) ---------------------------------
# Every series ends on a FIXED date, not "now" (RFC-6 Stage 0, decision D1).
# `chains.json` launch dates are fixed and cannot be redirected, so a
# now-anchored fixture would let Robinhood pass its 194-day history gate on
# 2027-01-10 and silently flip the limited-history scenario. Only the fetch
# stamps (`first_seen_utc`/`as_of_utc`) use the real clock, because the API's
# stale rule compares them with the real clock.
ONCHAIN_SEED_TODAY = "2026-09-26"
ONCHAIN_STALE_CHAIN = "optimism"
ONCHAIN_STALE_DAYS = 10
ONCHAIN_GAP = ("base", "2026-05-10", "2026-05-14")  # missing days, inclusive
ONCHAIN_TX_SCALE = 10.0  # transactions = active_addresses * 10 (same shape)
ONCHAIN_L2BEAT_FACTOR = 1.02  # l2beat tx = growthepie tx / 1.02 -> +2.0 % divergence
ONCHAIN_L2BEAT_DAYS = 120
ONCHAIN_NO_TX_ARCHIVE = "polygon"  # D3: forced per-source failure on the tx metric

# (chain, first seeded date, [(end date inclusive, from, to), ...]) — piecewise
# linear. The first segment always ends the day before `launch_date`, so every
# live chain has pre-launch points (D2).
_ONCHAIN_SHAPES: dict[str, tuple[str, list[tuple[str, float, float]]]] = {
    # Flat, then a 22 % rise over the last ~6 months: >10 % above the 180-day
    # low (not `floor`) but <25 % above the flat floor candidate (no event).
    "ethereum": ("2015-07-01", [("2015-07-29", 20_000, 20_000), ("2026-03-31", 400_000, 400_000),
                                ("2026-09-26", 400_000, 490_000)]),
    # Flat with a 5-day hole (ONCHAIN_GAP): exercises gap_before.
    "base": ("2023-07-10", [("2023-08-08", 25_000, 25_000), ("2026-09-26", 500_000, 500_000)]),
    # The designed floor-then-ramp: flat, -60 % over 120d, flat 60d, +125 % over 90d, flat.
    # Segment ends are the last in-segment step (not the next level), matching
    # the Stage 0 scratch run: floor 2026-03-01, ramp 2026-04-14.
    "arbitrum": ("2021-08-01", [("2021-08-30", 10_000, 10_000), ("2025-09-01", 200_000, 200_000),
                                ("2025-12-30", 200_000, 81_000), ("2026-02-28", 80_000, 80_000),
                                ("2026-05-29", 80_000, 178_888.8889), ("2026-09-26", 180_000, 180_000)]),
    "optimism": ("2021-11-16", [("2021-12-15", 5_000, 5_000), ("2026-09-26", 100_000, 100_000)]),
    # Long decline into a flat bottom: current state `floor`.
    "polygon": ("2020-05-01", [("2020-05-29", 50_000, 50_000), ("2025-12-31", 2_000_000, 800_000),
                               ("2026-09-26", 800_000, 800_000)]),
    # Short series, under the 194-day gate.
    "robinhood": ("2026-06-20", [("2026-06-30", 100, 100), ("2026-09-26", 1_000, 5_000)]),
}
# Hand-derived from the shapes above, then confirmed against the real
# detector by api/tests/scripts/test_seed_onchain_fixture.py.
_ONCHAIN_EXPECTED_STATES = {
    "ethereum": "neutral", "base": "floor", "arbitrum": "ramping",
    "optimism": "floor", "polygon": "floor", "robinhood": "not-enough-history",
}


def _onchain_piecewise(first: str, segments: list[tuple[str, float, float]]) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    seg_start = pd.Timestamp(first)
    for end, a, b in segments:
        days = pd.date_range(seg_start, pd.Timestamp(end), freq="D")
        n = len(days)
        for i, d in enumerate(days):
            out.append((d.strftime("%Y-%m-%d"), round(a + (b - a) * (i / max(1, n - 1)), 4)))
        seg_start = pd.Timestamp(end) + pd.Timedelta(days=1)
    return out


def build_onchain_fixture(seed_today: str = ONCHAIN_SEED_TODAY) -> dict:
    """Pure: the synthetic onchain rows plus the facts the E2E asserts. Writes nothing.

    rows: list of (source, chain_id, metric, [(date, value), ...], stale)."""
    from api.data.chain_growth_config import load_chains

    chains = {c.id: c for c in load_chains()}
    gap_chain, gap_from, gap_to = ONCHAIN_GAP
    rows: list[tuple[str, str, str, list[tuple[str, float]], bool]] = []
    facts_chains: dict[str, dict] = {}
    for cid, (first, segments) in _ONCHAIN_SHAPES.items():
        pts = [(d, v) for d, v in _onchain_piecewise(first, segments) if d <= seed_today]
        if cid == gap_chain:
            pts = [(d, v) for d, v in pts if not (gap_from <= d <= gap_to)]
        stale = cid == ONCHAIN_STALE_CHAIN
        tx = [(d, v * ONCHAIN_TX_SCALE) for d, v in pts]
        rows.append(("growthepie", cid, "active_addresses", pts, stale))
        if cid != ONCHAIN_NO_TX_ARCHIVE:
            rows.append(("growthepie", cid, "transactions", tx, stale))
        launch = chains[cid].launch_date
        facts_chains[cid] = {
            "label": chains[cid].label,
            "launch_date": launch,
            "first_date": pts[0][0],
            "points": len(pts),
            "pre_launch_points": sum(1 for d, _ in pts if launch and d < launch),
            "state": _ONCHAIN_EXPECTED_STATES[cid],
            "has_transactions": cid != ONCHAIN_NO_TX_ARCHIVE,
        }
    cross_check = [cid for cid in ("base", "arbitrum")]
    for cid in cross_check:
        tx = next(r[3] for r in rows if r[1] == cid and r[2] == "transactions")
        rows.append(("l2beat", cid, "transactions",
                     [(d, v / ONCHAIN_L2BEAT_FACTOR) for d, v in tx[-ONCHAIN_L2BEAT_DAYS:]], False))

    today = pd.Timestamp(seed_today)
    facts = {
        "seed_today": seed_today,
        "default_start": (today - pd.Timedelta(days=365)).strftime("%Y-%m-%d"),
        "start_2y": (today - pd.Timedelta(days=730)).strftime("%Y-%m-%d"),
        "live_ids": list(_ONCHAIN_SHAPES),
        "unavailable_ids": [c.id for c in chains.values() if c.enabled and c.id not in _ONCHAIN_SHAPES],
        "chains": facts_chains,
        "designed": {"chain": "arbitrum", "events": [{"floor_date": "2026-03-01", "ramp_date": "2026-04-14"}]},
        "gap": {"chain": gap_chain, "gap_before_date": (pd.Timestamp(gap_to) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")},
        "stale": {"chain": ONCHAIN_STALE_CHAIN, "days": ONCHAIN_STALE_DAYS},
        "limited": {"chain": "robinhood", "gate_met_on": "2027-01-10", "history_days": 88,
                    "rebase_date": chains["robinhood"].launch_date},
        "cross_check": {"chains": cross_check, "divergence_pct": round((ONCHAIN_L2BEAT_FACTOR - 1) * 100, 4)},
        "no_tx_archive": {"chain": ONCHAIN_NO_TX_ARCHIVE, "reason": "no-archived-data"},
        "attribution": "Source: growthepie, https://www.growthepie.com.",
        "attribution_url": "https://www.growthepie.com",
    }
    return {"rows": rows, "facts": facts}


def seed_onchain(seed_today: str = ONCHAIN_SEED_TODAY, now: pd.Timestamp | None = None) -> dict:
    """Write the onchain fixture ONLY through `cache.merge_onchain_series`.
    Caller must already have passed `_guard()`. Returns the manifest facts."""
    from api.data import cache

    now = now if now is not None else pd.Timestamp.now(tz="UTC")
    fresh = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    stale = (now - pd.Timedelta(days=ONCHAIN_STALE_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fixture = build_onchain_fixture(seed_today)
    for source, cid, metric, pts, is_stale in fixture["rows"]:
        cache.merge_onchain_series(source, cid, metric, pts, today=seed_today,
                                   now_utc=stale if is_stale else fresh)
    return fixture["facts"]


def main() -> int:
    root = _guard()
    from api.data import cache, watchlist as watchlist_store

    if root.exists():
        shutil.rmtree(root)
    cache.bootstrap_cache_dirs()

    written: dict[str, dict[str, int]] = {}
    for offset, symbol in enumerate(sorted(set(WATCHLIST) | set(BENCHMARKS))):
        written[symbol] = {}
        for timeframe, count in BAR_COUNTS.items():
            bars = THIN_BAR_COUNT if symbol == THIN_SYMBOL else count
            df = _bars(timeframe, bars, base=100.0 + offset * 1000)
            cache.write_ohlcv(symbol, timeframe, df)
            written[symbol][timeframe] = bars
        # `1w` is deliberately NOT seeded. It is derived from `1d` on request,
        # which is what makes the Monday-anchor assertion (ADR-5/ADR-6) an
        # end-to-end one rather than a check of whatever we wrote here.

    watchlist_path = os.environ.get("SCREENER_WATCHLIST_PATH")
    if watchlist_path:
        Path(watchlist_path).parent.mkdir(parents=True, exist_ok=True)
        # `watchlist.py::_load_raw` expects `{"coins": [...]}`, not a bare
        # array — it calls `data.setdefault("coins", [])` on whatever
        # `json.load` returns, which raises `AttributeError: 'list' object
        # has no attribute 'setdefault'` on a bare list. That exception fires
        # on `build_screener_board`'s very first line (`read_watchlist()`),
        # before any per-coin or per-timeframe code runs — which is why
        # every board request 500'd identically regardless of `timeframe`.
        Path(watchlist_path).write_text(json.dumps({"coins": WATCHLIST}), encoding="utf-8")
    else:
        print("WARNING: SCREENER_WATCHLIST_PATH unset — the API will read the real watchlist.")

    regime = seed_regime()
    narrative = seed_narrative()
    t0 = time.perf_counter()
    onchain = seed_onchain()
    onchain_seconds = round(time.perf_counter() - t0, 2)

    manifest = {
        "regime": regime,
        "narrative": narrative,
        "onchain": onchain,
        "cache_root": str(root),
        "watchlist": WATCHLIST,
        "benchmarks": BENCHMARKS,
        "thin_symbol": THIN_SYMBOL,
        "min_bars_required": 60,
        "bars_written": written,
        "seeded_at": pd.Timestamp.now(tz="UTC").isoformat(),
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"seeded {len(written)} symbols into {root}")
    print(f"regime     inputs seeded; gap at {regime['gap']['expected_gap_date']}")
    print(f"narrative  {len(narrative['category_ids'])} categories seeded; gap at {narrative['gap']['gap_date']}")
    print(f"onchain    {len(onchain['live_ids'])} chains seeded in {onchain_seconds}s; designed floor/ramp on {onchain['designed']['chain']}")
    print(f"watchlist  {WATCHLIST} -> {watchlist_path or '(not set)'}")
    print(f"manifest   {MANIFEST_PATH}")
    print(f"store path {watchlist_store.DEFAULT_WATCHLIST_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
