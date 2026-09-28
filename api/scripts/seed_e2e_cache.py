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


# --- /pairs fixture (pair screener RFC-005) --------------------------------
# Six fake coins, daily closes only, written through `cache.write_ohlcv` and
# then run through the PRODUCTION compute path (`compute_and_persist`), so the
# results/provenance/spreads the API serves are exactly what production would
# write for these inputs, and `computation_status` is "fresh" by construction.
# The universe is a fixture file at PAIRS_UNIVERSE_PATH; the real
# api/data/pairs_universe.json is never read or written.
#
# Designed states (asserted after compute; any miss exits non-zero, which
# fails the Playwright webServer start instead of producing a quiet green):
#   CINTA/CINTB  strongly cointegrated -> significant after BH, half-life computed
#   CINTA/WEAKB  weakly cointegrated   -> raw p < 0.05 but BH p >= 0.05 (raw-only tag)
#   CINTA/DRIFT  explosive spread      -> half-life not_mean_reverting; EG not
#                significant while Johansen says rank >= 1 (AC-6 disagreement)
#   SHORT/*      200 bars < MIN_OVERLAP_DAYS -> insufficient_overlap
#   GHOST/*      in the universe, no cache file -> coin_unavailable (AC-12)
# Values come from seeded RNGs and do not depend on today's date; only the
# date index is anchored to today (like the other fixtures).
PAIRS_COINS = ["CINTA", "CINTB", "WEAKB", "DRIFT", "SHORT", "GHOST"]
PAIRS_BARS = 900
PAIRS_SHORT_BARS = 200
PAIRS_MISSING = "GHOST"
PAIRS_SHORT = "SHORT"
PAIRS_SEEDS = {"base": 7, "cintb": 101, "weakb": 10, "drift": 1, "short": 3}
PAIRS_WEAK_PHI = 0.975
PAIRS_DRIFT_RATE = 1.006
PAIRS_SIGNIFICANT = ("CINTA", "CINTB")
PAIRS_RAW_ONLY = ("CINTA", "WEAKB")
PAIRS_NOT_MEAN_REVERTING = ("CINTA", "DRIFT")
PAIRS_SIGNIFICANCE_LEVEL = 0.05


def _pairs_universe_path() -> Path:
    """Resolve PAIRS_UNIVERSE_PATH, refusing unset or the real universe file."""
    from api.data import pairs_universe

    raw = os.environ.get(pairs_universe.UNIVERSE_PATH_ENV)
    if not raw:
        sys.exit(
            f"REFUSING: {pairs_universe.UNIVERSE_PATH_ENV} is not set.\n"
            "Without it the API would serve the real pairs universe against fixture results."
        )
    path = Path(raw).resolve()
    if path == pairs_universe.real_universe_path().resolve():
        sys.exit(
            f"REFUSING: {pairs_universe.UNIVERSE_PATH_ENV} points at the real universe file ({path}).\n"
            "Point it somewhere disposable."
        )
    return path


def build_pairs_fixture(today: pd.Timestamp) -> dict[str, pd.DataFrame]:
    """Pure: daily OHLCV frames per fixture coin (GHOST deliberately absent)."""
    import numpy as np

    n = PAIRS_BARS
    idx = pd.date_range(end=today, periods=n, freq="D", tz="UTC")

    def rng(key: str):
        return np.random.default_rng(PAIRS_SEEDS[key])

    def ar(key: str, phi: float, sd: float):
        e = rng(key).normal(0, sd, n)
        x = np.zeros(n)
        for t in range(1, n):
            x[t] = phi * x[t - 1] + e[t]
        return x

    base = np.cumsum(rng("base").normal(0, 0.03, n))
    drift = np.zeros(n)
    drift[0] = 0.01
    shocks = rng("drift").normal(0, 0.002, n)
    for t in range(1, n):
        drift[t] = PAIRS_DRIFT_RATE * drift[t - 1] + shocks[t]
    logs = {
        "CINTA": base,
        "CINTB": 0.5 + 0.8 * base + ar("cintb", 0.80, 0.02),
        "WEAKB": 0.2 + base + ar("weakb", PAIRS_WEAK_PHI, 0.02),
        "DRIFT": base + drift,
    }

    def frame(log_close, index) -> pd.DataFrame:
        close = np.exp(log_close) * 100.0
        return pd.DataFrame({
            "timestamp": index, "open": close, "high": close * 1.01, "low": close * 0.99,
            "close": close, "volume": 1000.0, "source": "e2e-fixture",
        })

    frames = {sym: frame(lg, idx) for sym, lg in logs.items()}
    short = np.cumsum(rng("short").normal(0, 0.03, PAIRS_SHORT_BARS))
    frames[PAIRS_SHORT] = frame(short, idx[-PAIRS_SHORT_BARS:])
    return frames


def check_pairs_results(table: pd.DataFrame) -> list[str]:
    """Every designed state, checked against what compute actually wrote.
    Returns a list of problems; empty means the fixture is as designed."""
    problems: list[str] = []
    alpha = PAIRS_SIGNIFICANCE_LEVEL
    expected_n = len(PAIRS_COINS) * (len(PAIRS_COINS) - 1) // 2
    if len(table) != expected_n:
        problems.append(f"row count {len(table)} != {expected_n}")

    by_pair = {(r["coin_a"], r["coin_b"]): r for r in table.to_dict("records")}
    for (a, b), r in by_pair.items():
        want = ("coin_unavailable" if PAIRS_MISSING in (a, b)
                else "insufficient_overlap" if PAIRS_SHORT in (a, b) else "ok")
        if r["status"] != want:
            problems.append(f"{a}/{b}: status {r['status']}, designed {want}")

    def get(pair):
        r = by_pair.get(pair)
        if r is None:
            problems.append(f"{pair[0]}/{pair[1]}: missing row")
        return r

    r = get(PAIRS_SIGNIFICANT)
    if r is not None and not (r["status"] == "ok" and r["eg_p_bh"] < alpha and r["half_life_state"] == "computed"):
        problems.append(f"{PAIRS_SIGNIFICANT}: not significant with a computed half-life "
                        f"(bh={r['eg_p_bh']}, hl={r['half_life_state']})")
    r = get(PAIRS_RAW_ONLY)
    if r is not None and not (r["status"] == "ok" and r["eg_p_raw"] < alpha <= r["eg_p_bh"]):
        problems.append(f"{PAIRS_RAW_ONLY}: not raw-only (raw={r['eg_p_raw']}, bh={r['eg_p_bh']})")
    r = get(PAIRS_NOT_MEAN_REVERTING)
    if r is not None and r["status"] == "ok":
        if r["half_life_state"] != "not_mean_reverting":
            problems.append(f"{PAIRS_NOT_MEAN_REVERTING}: half-life {r['half_life_state']}, designed not_mean_reverting")
        if not (r["eg_p_bh"] >= alpha and bool(r["johansen_rank_at_least_1"])):
            problems.append(f"{PAIRS_NOT_MEAN_REVERTING}: EG and Johansen do not disagree "
                            f"(bh={r['eg_p_bh']}, johansen rank>=1={r['johansen_rank_at_least_1']})")
    return problems


def seed_pairs(today: pd.Timestamp | None = None) -> dict:
    """Write the pairs fixture, run the production compute, verify it, and
    return the manifest facts. Caller must already have passed `_guard()`."""
    from api.analytics.cointegration import pairs_response
    from api.data import cache

    universe_path = _pairs_universe_path()
    today = today if today is not None else pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    universe_path.parent.mkdir(parents=True, exist_ok=True)
    universe_path.write_text(json.dumps({"coins": PAIRS_COINS}), encoding="utf-8")
    for sym, df in build_pairs_fixture(today).items():
        cache.write_ohlcv(sym, "1d", df)

    summary = pairs_response.compute_and_persist()
    table = pd.read_parquet(cache.pairs_results_path())
    problems = check_pairs_results(table)
    if problems:
        sys.exit("PAIRS FIXTURE DID NOT COME OUT AS DESIGNED:\n  " + "\n  ".join(problems))

    # Display order of ranked rows (plan AC-4, web sortPairs): corrected p, ties
    # on raw p, then coin names. The three DRIFT pairs tie on corrected p (BH
    # step-up), so the raw-p tie-break is exercised end to end.
    ok = table[table["status"] == "ok"].sort_values(["eg_p_bh", "eg_p_raw", "coin_a", "coin_b"])
    # Display order of the non-ok group (plan AC-4): insufficient_overlap, then
    # coin_unavailable, each alphabetical.
    rest = table[table["status"] != "ok"].assign(
        _group=lambda t: t["status"].map({"insufficient_overlap": 0, "coin_unavailable": 1})
    ).sort_values(["_group", "coin_a", "coin_b"])
    sig = table[(table["coin_a"] == PAIRS_SIGNIFICANT[0]) & (table["coin_b"] == PAIRS_SIGNIFICANT[1])].iloc[0]
    alpha = PAIRS_SIGNIFICANCE_LEVEL
    return {
        "universe": PAIRS_COINS,
        "pair_count": int(summary.pair_count),
        "status_counts": {k: int(v) for k, v in summary.status_counts.items()},
        "status_by_pair": {f"{a}-{b}": s for a, b, s in zip(table["coin_a"], table["coin_b"], table["status"])},
        "ok_order": [f"{a}-{b}" for a, b in zip(ok["coin_a"], ok["coin_b"])],
        "non_ok_order": [f"{a}-{b}" for a, b in zip(rest["coin_a"], rest["coin_b"])],
        "tested_count": int(len(ok)),
        "significant_count": int((ok["eg_p_bh"] < alpha).sum()),
        "raw_only_pairs": [f"{a}-{b}" for a, b, raw, bh in zip(ok["coin_a"], ok["coin_b"], ok["eg_p_raw"], ok["eg_p_bh"])
                           if raw < alpha <= bh],
        "significant_pair": list(PAIRS_SIGNIFICANT),
        "raw_only_pair": list(PAIRS_RAW_ONLY),
        "not_mean_reverting_pair": list(PAIRS_NOT_MEAN_REVERTING),
        "missing_coin": PAIRS_MISSING,
        "short_coin": PAIRS_SHORT,
        "significant_sample": {
            "start": str(sig["sample_start"])[:10],
            "end": str(sig["sample_end"])[:10],
            "overlap_days": int(sig["overlap_days"]),
        },
    }


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
    pairs = seed_pairs()

    manifest = {
        "regime": regime,
        "narrative": narrative,
        "pairs": pairs,
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
    print(f"pairs      {pairs['pair_count']} pairs, {pairs['status_counts']}")
    print(f"watchlist  {WATCHLIST} -> {watchlist_path or '(not set)'}")
    print(f"manifest   {MANIFEST_PATH}")
    print(f"store path {watchlist_store.DEFAULT_WATCHLIST_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
