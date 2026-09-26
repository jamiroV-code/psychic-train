"""Provider verification script for the LSE data-verification plan.

Plan: process/general-plans/active/lse-data-verification_17-09-26/lse-data-verification_PLAN_17-09-26.md

Usage (on the user's PC, never in the cloud container -- its proxy blocks LSE/Stooq):
    python verify_provider.py --phase 1   # access + quota cost of one small request
    python verify_provider.py --phase 2   # depth/coverage + delisted probe
    python verify_provider.py --phase 3   # cross-source diff, split probes, OHLC integrity
    python verify_provider.py --phase 4   # 50-symbol backfill + DuckDB query

Keys come ONLY from the environment: LSE_API_KEY (and ALPACA_API_KEY /
ALPACA_API_SECRET for the Stooq fallback). No key is ever accepted as a flag,
printed, or written to disk by this script.

Structure: pure functions (tested offline in test_verify_provider.py) + thin
provider I/O functions (fetch_*), each isolated so a wrong assumed call shape
is a one-function fix.

Provider API shape status:
  - lse-data 0.14.0 was inspected from its PyPI wheel (client.py / vault.py):
    LSE(api_key=...), .candles(symbol, timeframe, start, end, limit<=5000, order)
    -> list[dict] with key "timestamp" (bar open), .history(symbol, timeframe=,
    start=, dest=, dataframe=) -> DataFrame, .splits(symbol) -> list[dict],
    ._vault_call("/usage") -> dict. VERIFIED against source.
  - ASSUMED (not verifiable offline): candle rows carry open/high/low/close/volume
    keys; the /usage JSON is a (possibly nested) dict of numbers; Stooq CSV and
    Alpaca bars endpoints (see fetch_stooq / fetch_alpaca). Phase 1 prints raw
    shapes so a wrong assumption shows up on the first run.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

# --------------------------------------------------------------------------
# Fixed inputs (frozen in the plan; do not recompute)
# --------------------------------------------------------------------------

FIXED_SYMBOLS = ["AAPL", "MSFT", "SPY", "XOM", "KO", "NVDA"]
DELISTED_PRIMARY = "SIVB"   # delisted 2023-03-28
DELISTED_BACKUP = "FRC"     # delisted 2023-05-01

PHASE4_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AVGO", "ORCL", "CRM", "ADBE",
    "JPM", "BAC", "WFC", "GS", "MS",
    "UNH", "JNJ", "LLY", "PFE", "ABBV",
    "KO", "PEP", "WMT", "PG", "MCD", "NKE", "SBUX", "HD", "TGT", "COST",
    "BA", "CAT", "GE", "HON", "UPS",
    "XOM", "CVX", "COP", "SLB", "OXY",
    "DIS", "NFLX", "CMCSA", "VZ", "T",
    "LIN", "FCX", "NEM",
    "NEE", "SPY",
]

SPLITS = [
    # (symbol, split effective date, ratio)
    ("AAPL", "2020-08-31", 4.0),
    ("NVDA", "2024-06-10", 10.0),
]

EARLIEST = "1990-01-01"      # request floor; the vault reports US stocks from 2003
CROSS_SOURCE_YEARS = 5
STORE_QUERY_YEARS = 3
OHLC_COLS = ["open", "high", "low", "close"]


# --------------------------------------------------------------------------
# Pure functions (offline-tested)
# --------------------------------------------------------------------------

def normalize_candles(rows: Iterable[dict] | pd.DataFrame) -> pd.DataFrame:
    """Rows -> DataFrame with a tz-naive daily `date` column + lower-case OHLCV.

    Accepts the lse-data `timestamp` key, the raw vault `ts`, or `date`/`Date`.
    Returns an empty frame with the right columns for empty input.
    """
    df = rows.copy() if isinstance(rows, pd.DataFrame) else pd.DataFrame(list(rows))
    cols = ["date", *OHLC_COLS, "volume"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    df.columns = [str(c).lower() for c in df.columns]
    time_col = next((c for c in ("timestamp", "ts", "date", "time", "t") if c in df.columns), None)
    if time_col is None:
        raise ValueError(f"no time column in candle rows; columns={list(df.columns)}")
    ts = pd.to_datetime(df[time_col], utc=True)
    df["date"] = ts.dt.tz_convert(None).dt.normalize()
    for c in OHLC_COLS:
        if c not in df.columns:
            raise ValueError(f"missing column {c!r}; columns={list(df.columns)}")
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if "volume" not in df.columns:
        df["volume"] = 0.0
    return df[cols].reset_index(drop=True)


def compute_coverage(df: pd.DataFrame, sessions: Iterable) -> dict:
    """Coverage vs an exchange calendar.

    `sessions` = expected trading dates. Only sessions within [first, last] of
    the data count as missing. `longest_gap` = longest run of consecutive
    missing sessions.
    """
    if df.empty:
        return {"first_date": None, "last_date": None, "rows": 0,
                "missing_sessions": None, "longest_gap": None}
    have = pd.DatetimeIndex(pd.to_datetime(df["date"])).normalize().unique()
    first, last = have.min(), have.max()
    expected = pd.DatetimeIndex(pd.to_datetime(list(sessions))).normalize()
    expected = expected[(expected >= first) & (expected <= last)].unique().sort_values()
    present = expected.isin(have)
    longest = run = 0
    for p in present:
        run = 0 if p else run + 1
        longest = max(longest, run)
    return {"first_date": first.date(), "last_date": last.date(), "rows": int(len(df)),
            "missing_sessions": int((~present).sum()), "longest_gap": int(longest)}


def classify_delisted(df: pd.DataFrame) -> dict:
    """Empty history for a delisted ticker => the universe is survivorship-biased."""
    if df is None or df.empty:
        return {"rows": 0, "last_date": None, "survivorship_bias": "present"}
    return {"rows": int(len(df)), "last_date": pd.to_datetime(df["date"]).max().date(),
            "survivorship_bias": "absent"}


def cross_source_diff(a: pd.DataFrame, b: pd.DataFrame) -> dict:
    """Absolute % diff of closes on dates both sources have: median/p99/max."""
    m = a[["date", "close"]].merge(b[["date", "close"]], on="date", suffixes=("_a", "_b"))
    m = m.dropna()
    m = m[m["close_b"] != 0]
    if m.empty:
        return {"n": 0, "median": None, "p99": None, "max": None}
    pct = (m["close_a"] - m["close_b"]).abs() / m["close_b"].abs() * 100.0
    return {"n": int(len(pct)), "median": float(pct.median()),
            "p99": float(pct.quantile(0.99)), "max": float(pct.max())}


def detect_split_discontinuity(df: pd.DataFrame, split_date: str, expected_ratio: float,
                               tol: float = 0.15) -> dict:
    """Ratio of last close before the split to first open on/after it.

    ~expected_ratio => series is RAW (unadjusted) across the split;
    ~1 => ADJUSTED; else ambiguous. `tol` is relative.
    """
    d = pd.Timestamp(split_date)
    s = df.sort_values("date")
    before = s[s["date"] < d]
    after = s[s["date"] >= d]
    if before.empty or after.empty:
        return {"observed_ratio": None, "classification": "insufficient-data"}
    ratio = float(before["close"].iloc[-1]) / float(after["open"].iloc[0])
    if abs(ratio / expected_ratio - 1) <= tol:
        cls = "raw"
    elif abs(ratio - 1) <= tol:
        cls = "adjusted"
    else:
        cls = "ambiguous"
    return {"observed_ratio": ratio, "classification": cls}


def split_window(df: pd.DataFrame, split_date: str, n: int = 3) -> pd.DataFrame:
    """n bars either side of the split date, for human inspection."""
    d = pd.Timestamp(split_date)
    s = df.sort_values("date").reset_index(drop=True)
    idx = int((s["date"] < d).sum())
    return s.iloc[max(0, idx - n): idx + n]


def assert_ohlc_integrity(df: pd.DataFrame) -> dict:
    """Count violations per rule. All-zero = clean."""
    o, h, l, c = (df[k] for k in OHLC_COLS)
    dates = pd.to_datetime(df["date"])
    return {
        "low_gt_min_open_close": int((l > pd.concat([o, c], axis=1).min(axis=1)).sum()),
        "high_lt_max_open_close": int((h < pd.concat([o, c], axis=1).max(axis=1)).sum()),
        "non_positive_price": int((df[OHLC_COLS] <= 0).any(axis=1).sum()),
        "nan_price": int(df[OHLC_COLS].isna().any(axis=1).sum()),
        "duplicate_timestamp": int(dates.duplicated().sum()),
        "non_monotonic": int((dates.diff().dt.total_seconds() <= 0).sum()),
    }


def _flatten(d: Any, prefix: str = "") -> dict:
    out: dict = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(_flatten(v, f"{prefix}{k}."))
    elif isinstance(d, (int, float)) and not isinstance(d, bool):
        out[prefix.rstrip(".")] = d
    return out


def quota_delta(before: dict, after: dict) -> dict:
    """Numeric fields that changed between two /usage snapshots (after - before)."""
    b, a = _flatten(before), _flatten(after)
    return {k: a[k] - b[k] for k in sorted(set(a) & set(b)) if a[k] != b[k]}


def write_store(frames: dict[str, pd.DataFrame], root: Path) -> int:
    """One Parquet file per symbol under root/symbol=XXX/. Returns bytes on disk."""
    root = Path(root)
    for sym, df in frames.items():
        part = root / f"symbol={sym}"
        part.mkdir(parents=True, exist_ok=True)
        df.assign(symbol=sym).to_parquet(part / "data.parquet", index=False)
    return sum(p.stat().st_size for p in root.rglob("*.parquet"))


def query_store(root: Path, start: str, end: str) -> pd.DataFrame:
    """DuckDB: per-symbol row count / date span / mean close in [start, end]."""
    import duckdb
    glob = str(Path(root) / "*" / "*.parquet").replace("\\", "/")
    sql = f"""
        SELECT symbol, count(*) AS rows, min(date) AS first, max(date) AS last,
               avg(close) AS mean_close
        FROM read_parquet('{glob}')
        WHERE date >= ?::TIMESTAMP AND date <= ?::TIMESTAMP
        GROUP BY symbol ORDER BY symbol
    """
    con = duckdb.connect()
    try:
        return con.execute(sql, [start, end]).df()
    finally:
        con.close()


def to_markdown(rows: list[dict]) -> str:
    """Paste-friendly markdown table (no tabulate dependency)."""
    if not rows:
        return "_(no rows)_"
    cols = list(rows[0].keys())
    fmt = lambda v: f"{v:.4f}" if isinstance(v, float) else ("" if v is None else str(v))
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(fmt(r.get(c)) for c in cols) + " |" for r in rows]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Thin provider I/O (NOT tested offline; never run in the cloud container)
# --------------------------------------------------------------------------

def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        sys.exit(f"ERROR: environment variable {name} is not set (keys are env-only).")
    return val


def lse_client():
    from lse import LSE  # VERIFIED: lse-data 0.14.0 exposes lse.LSE
    return LSE(api_key=_require_env("LSE_API_KEY"))


def fetch_candles(client, symbol: str, start: str, end: str | None = None) -> pd.DataFrame:
    """Daily candles, paging past the 5000-row per-call cap by advancing `start`.

    VERIFIED call: client.candles(symbol, "1d", start=, end=, limit=5000, order="asc").
    ASSUMED: rows carry open/high/low/close keys (normalize_candles raises if not).
    """
    frames, cursor = [], start
    for _ in range(50):
        rows = client.candles(symbol, "1d", start=cursor, end=end, limit=5000, order="asc")
        if not rows:
            break
        df = normalize_candles(rows)
        frames.append(df)
        if len(rows) < 5000:
            break
        cursor = (df["date"].max() + timedelta(days=1)).strftime("%Y-%m-%d")
    if not frames:
        return normalize_candles([])
    out = pd.concat(frames).drop_duplicates("date").sort_values("date")
    return out.reset_index(drop=True)


def fetch_usage(client) -> dict:
    """GET /vault/usage. VERIFIED transport (_vault_call is the SDK's own helper);
    ASSUMED: response is a JSON object. Private method -- no public wrapper in 0.14.0."""
    return client._vault_call("/usage")


def fetch_history_bulk(client, symbol: str, dest: str) -> pd.DataFrame:
    """Bulk Parquet export job. VERIFIED signature: history(symbol, timeframe=, start=,
    dest=, dataframe=). One export job each -- the plan's hourly export budget applies."""
    df = client.history(symbol, timeframe="1d", start=EARLIEST, dest=dest, dataframe=True)
    return normalize_candles(df)


def fetch_stooq(symbol: str, start: str, end: str) -> pd.DataFrame:
    """ASSUMED endpoint: https://stooq.com/q/d/l/?s={sym}.us&d1=YYYYMMDD&d2=YYYYMMDD&i=d
    returning CSV Date,Open,High,Low,Close,Volume (split-adjusted closes)."""
    import httpx
    url = (f"https://stooq.com/q/d/l/?s={symbol.lower()}.us&i=d"
           f"&d1={start.replace('-', '')}&d2={end.replace('-', '')}")
    r = httpx.get(url, timeout=30, follow_redirects=True)
    r.raise_for_status()
    text = r.text.strip()
    if not text or not text.lower().startswith("date"):
        raise RuntimeError(f"Stooq returned non-CSV for {symbol}: {text[:120]!r}")
    return normalize_candles(pd.read_csv(io.StringIO(text)))


def fetch_alpaca(symbol: str, start: str, end: str) -> pd.DataFrame:
    """ASSUMED endpoint: GET https://data.alpaca.markets/v2/stocks/{sym}/bars
    ?timeframe=1Day&adjustment=all&feed=iex, headers APCA-API-KEY-ID/SECRET-KEY,
    JSON {"bars":[{"t","o","h","l","c","v"}], "next_page_token"}."""
    import httpx
    headers = {"APCA-API-KEY-ID": _require_env("ALPACA_API_KEY"),
               "APCA-API-SECRET-KEY": _require_env("ALPACA_API_SECRET")}
    params = {"timeframe": "1Day", "start": start, "end": end, "adjustment": "all",
              "feed": "iex", "limit": 10000}
    bars: list[dict] = []
    while True:
        r = httpx.get(f"https://data.alpaca.markets/v2/stocks/{symbol}/bars",
                      params=params, headers=headers, timeout=30)
        r.raise_for_status()
        j = r.json()
        bars += j.get("bars") or []
        if not j.get("next_page_token"):
            break
        params["page_token"] = j["next_page_token"]
    rows = [{"timestamp": b["t"], "open": b["o"], "high": b["h"], "low": b["l"],
             "close": b["c"], "volume": b.get("v", 0)} for b in bars]
    return normalize_candles(rows)


def nyse_sessions(start, end) -> pd.DatetimeIndex:
    import pandas_market_calendars as pmc
    return pmc.get_calendar("NYSE").schedule(start_date=start, end_date=end).index


def _shape(obj: Any) -> str:
    """Describe a response's shape without printing values that might be sensitive."""
    if isinstance(obj, list):
        return f"list[{len(obj)}] of " + (_shape(obj[0]) if obj else "?")
    if isinstance(obj, dict):
        return "dict{" + ", ".join(f"{k}: {type(v).__name__}" for k, v in obj.items()) + "}"
    return type(obj).__name__


# --------------------------------------------------------------------------
# Phases
# --------------------------------------------------------------------------

def phase1() -> None:
    client = lse_client()
    today = date.today()
    start = (today - timedelta(days=30)).isoformat()
    u0 = fetch_usage(client)
    print("## Phase 1 — access and client sanity\n")
    print(f"usage response shape: `{_shape(u0)}`\n")
    print("usage BEFORE:\n```json\n" + json.dumps(u0, indent=2, default=str) + "\n```\n")
    raw = client.candles("AAPL", "1d", start=start, limit=5000, order="asc")
    print(f"candles raw shape: `{_shape(raw)}`\n")
    if raw:
        print("first raw row:\n```json\n" + json.dumps(raw[0], indent=2, default=str) + "\n```\n")
    df = normalize_candles(raw)
    u1 = fetch_usage(client)
    print(f"AAPL 1d since {start}: {len(df)} rows\n")
    print(to_markdown(df.assign(date=df["date"].dt.date).to_dict("records")) + "\n")
    print("usage AFTER:\n```json\n" + json.dumps(u1, indent=2, default=str) + "\n```\n")
    print("quota delta (after - before): `" + json.dumps(quota_delta(u0, u1)) + "`")


def phase2() -> None:
    client = lse_client()
    today = date.today().isoformat()
    sessions = nyse_sessions(EARLIEST, today)
    print("## Phase 2 — depth and coverage\n")
    rows = []
    for sym in FIXED_SYMBOLS:
        try:
            cov = compute_coverage(fetch_candles(client, sym, EARLIEST, today), sessions)
        except Exception as e:  # recorded as a finding, not swallowed
            cov = {"error": f"{type(e).__name__}: {e}"}
        rows.append({"symbol": sym, **cov})
    print(to_markdown(rows) + "\n")
    print("### Delisted-ticker probe\n")
    probe = []
    for sym in (DELISTED_PRIMARY, DELISTED_BACKUP):
        try:
            df = fetch_candles(client, sym, EARLIEST, today)
            probe.append({"symbol": sym, **classify_delisted(df),
                          **{k: v for k, v in compute_coverage(df, sessions).items()
                             if k in ("first_date", "missing_sessions")}})
        except Exception as e:
            probe.append({"symbol": sym, "error": f"{type(e).__name__}: {e}"})
    print(to_markdown(probe))


def phase3() -> None:
    client = lse_client()
    end = date.today()
    start = end.replace(year=end.year - CROSS_SOURCE_YEARS).isoformat()
    end_s = end.isoformat()
    print("## Phase 3 — accuracy and corporate actions\n")
    second = "stooq"
    diffs, integrity, lse_full = [], [], {}
    for sym in FIXED_SYMBOLS:
        lse_df = fetch_candles(client, sym, EARLIEST, end_s)
        lse_full[sym] = lse_df
        integrity.append({"symbol": sym, "rows": len(lse_df), **assert_ohlc_integrity(lse_df)})
        win = lse_df[lse_df["date"] >= pd.Timestamp(start)]
        try:
            other = fetch_stooq(sym, start, end_s) if second == "stooq" else None
        except Exception as e:
            print(f"> Stooq failed for {sym} ({type(e).__name__}: {e}); switching to Alpaca.\n")
            second = "alpaca"
            other = None
        if other is None:
            try:
                other = fetch_alpaca(sym, start, end_s)
            except Exception as e:
                diffs.append({"symbol": sym, "source": second, "error": f"{type(e).__name__}: {e}"})
                continue
        diffs.append({"symbol": sym, "source": second, **cross_source_diff(win, other)})
    print(f"### Cross-source close diff ({start}..{end_s}, abs %)\n")
    print(to_markdown(diffs) + "\n")
    print("### Split probes\n")
    for sym, d, ratio in SPLITS:
        df = lse_full.get(sym)
        res = detect_split_discontinuity(df, d, ratio)
        print(f"**{sym} {ratio:g}:1 on {d}** -> {res}\n")
        w = split_window(df, d)
        print(to_markdown(w.assign(date=w["date"].dt.date).to_dict("records")) + "\n")
        try:
            print(f"LSE splits() reference rows: `{json.dumps(client.splits(sym)[:5], default=str)}`\n")
        except Exception as e:
            print(f"splits() failed: {type(e).__name__}: {e}\n")
    print("### OHLC integrity (full pull, violation counts)\n")
    print(to_markdown(integrity))


def phase4(store_dir: str | None) -> None:
    client = lse_client()
    root = Path(store_dir) if store_dir else Path(tempfile.mkdtemp(prefix="lse-store-"))
    if "process" in root.resolve().parts:
        sys.exit("ERROR: refusing to write the scratch store under process/ (never committed).")
    dl = root / "_downloads"
    dl.mkdir(parents=True, exist_ok=True)
    print("## Phase 4 — screener-scale feasibility\n")
    print(f"store: `{root}`\n")
    u0 = fetch_usage(client)
    t0 = time.perf_counter()
    frames, failures, method = {}, [], {}
    for sym in PHASE4_UNIVERSE:
        try:
            frames[sym] = fetch_history_bulk(client, sym, str(dl))
            method[sym] = "history"
        except Exception as e:
            try:
                frames[sym] = fetch_candles(client, sym, EARLIEST)
                method[sym] = f"candles (history failed: {type(e).__name__})"
            except Exception as e2:
                failures.append({"symbol": sym, "error": f"{type(e2).__name__}: {e2}"})
    elapsed = time.perf_counter() - t0
    u1 = fetch_usage(client)
    size = write_store(frames, root)
    end = date.today()
    q0 = time.perf_counter()
    q = query_store(root, end.replace(year=end.year - STORE_QUERY_YEARS).isoformat(), end.isoformat())
    qt = time.perf_counter() - q0
    summary = [{"symbols_ok": len(frames), "symbols_failed": len(failures),
                "elapsed_s": round(elapsed, 1), "store_mb": round(size / 1e6, 2),
                "duckdb_query_s": round(qt, 3), "query_symbols": len(q)}]
    print(to_markdown(summary) + "\n")
    print("quota delta: `" + json.dumps(quota_delta(u0, u1)) + "`\n")
    print("usage AFTER:\n```json\n" + json.dumps(u1, indent=2, default=str) + "\n```\n")
    print("fetch method: `" + json.dumps({m: sum(1 for v in method.values() if v == m)
                                          for m in set(method.values())}) + "`\n")
    if failures:
        print(to_markdown(failures) + "\n")
    print(f"### DuckDB {STORE_QUERY_YEARS}-year window\n")
    print(to_markdown(q.astype({"first": str, "last": str}).to_dict("records")))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--phase", type=int, choices=[1, 2, 3, 4], required=True)
    ap.add_argument("--store-dir", help="Phase 4 scratch store (default: new temp dir; never under process/)")
    a = ap.parse_args(argv)
    {1: phase1, 2: phase2, 3: phase3}.get(a.phase, lambda: phase4(a.store_dir))()


if __name__ == "__main__":
    main()
