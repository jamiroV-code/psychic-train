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

    manifest = {
        "regime": regime,
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
    print(f"watchlist  {WATCHLIST} -> {watchlist_path or '(not set)'}")
    print(f"manifest   {MANIFEST_PATH}")
    print(f"store path {watchlist_store.DEFAULT_WATCHLIST_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
