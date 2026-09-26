"""DuckDB-over-Parquet cache layer.

Centralizes the DuckDB connection + Parquet path construction so no other
module hand-rolls a cache path (Component Details: `api/data/cache.py`
"centralizes the DuckDB connection + query helpers so no other module
hand-rolls a Parquet path").
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Literal

import duckdb
import pandas as pd

Timeframe = Literal["15m", "1h", "4h", "1d", "1w"]
TIMEFRAMES: tuple[Timeframe, ...] = ("15m", "1h", "4h", "1d", "1w")

# The cache root is overridable so a test run — notably the Playwright E2E,
# which needs a real API serving fixture data — can point the whole API at a
# throwaway tree instead of the developer's live market data.
#
# Read from the environment at import, which is when a uvicorn process starts
# and therefore when the E2E sets it. It remains a plain module attribute, so
# `monkeypatch.setattr(cache, "CACHE_ROOT", tmp_path)` (the `isolated_cache`
# fixture) keeps working, and every consumer reads it through a function
# (`ohlcv_path`, etc.) at call time rather than binding it as a default
# argument — the RFC-005 watchlist defect.
DEFAULT_CACHE_ROOT = Path(__file__).resolve().parent / "cache"
CACHE_ROOT = Path(os.environ["SCREENER_CACHE_ROOT"]) if os.environ.get("SCREENER_CACHE_ROOT") else DEFAULT_CACHE_ROOT

OHLCV_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume", "source"]

# --------------------------------------------------------------------------
# Every read goes through `_connect()`, never a bare DuckDB connection.
#
# Why (ADR-6, 19-09-26): `_raw_to_df` builds timestamps in UTC, but DuckDB
# converts a TIMESTAMP WITH TIME ZONE to the *session* timezone on read, and
# that defaults to the machine's local zone. On a Europe/Brussels machine every
# cached series came back as `datetime64[us, Europe/Brussels]`: daily bars read
# as 01:00 or 02:00 instead of 00:00, and `resample("W-MON")` anchored on
# Brussels midnight — 22:00 UTC in summer, 23:00 UTC in winter. Weekly bars
# were labelled Monday locally and Sunday in UTC, and the anchor shifted by an
# hour across each DST transition (one week a year is then 167 or 169 hours).
#
# The consequence was worse than the offset itself: the meaning of the cached
# data depended on the timezone of whoever ran the code. Two machines reading
# the same Parquet files got different weeks. Pinning the session to UTC makes
# the read boundary timezone-independent.
#
# This was found only after ADR-5's 13 golden-value tests were green: they call
# `_derive_weekly_from_daily` directly on UTC fixtures and never cross the
# Parquet/DuckDB boundary where the conversion happens. See
# `api/tests/data/test_cache_timezone.py`, which does cross it.
# --------------------------------------------------------------------------
def _connect():
    """A DuckDB connection pinned to UTC. Use for every read in this module."""
    conn = duckdb.connect()
    conn.execute("SET TimeZone='UTC'")
    return conn


def _as_utc(df: pd.DataFrame, column: str = "timestamp") -> pd.DataFrame:
    """Re-assert the UTC contract in pandas as well as in DuckDB.

    `_connect()` should already have handled it. Doing it again means a future
    DuckDB that ignores or renames the setting degrades to a no-op here rather
    than to silently local timestamps.
    """
    if column in df.columns and len(df):
        df[column] = pd.to_datetime(df[column], utc=True)
    return df



def bootstrap_cache_dirs() -> None:
    """Create the cache/ directory tree if it doesn't exist yet."""
    for sub in ("ohlcv", "liquidity", "liqtide", "legs", "narrative"):
        (CACHE_ROOT / sub).mkdir(parents=True, exist_ok=True)


def ohlcv_path(symbol: str, timeframe: Timeframe) -> Path:
    return CACHE_ROOT / "ohlcv" / symbol.upper() / f"{timeframe}.parquet"


def read_ohlcv(symbol: str, timeframe: Timeframe) -> pd.DataFrame:
    """Read cached OHLCV bars for one (symbol, timeframe). Empty df if no cache yet."""
    path = ohlcv_path(symbol, timeframe)
    if not path.exists():
        return pd.DataFrame(columns=OHLCV_COLUMNS)
    df = _connect().sql(
        f"SELECT * FROM read_parquet('{path.as_posix()}') ORDER BY timestamp"
    ).df()
    return _as_utc(df)


def write_ohlcv(symbol: str, timeframe: Timeframe, df: pd.DataFrame) -> None:
    """Write (overwrite) the full cached OHLCV series for one (symbol, timeframe)."""
    path = ohlcv_path(symbol, timeframe)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.sort_values("timestamp").drop_duplicates(subset="timestamp", keep="last")
    out = out[OHLCV_COLUMNS]
    out.to_parquet(path, index=False)


def ohlcv_bar_count(symbol: str, timeframe: Timeframe) -> int:
    path = ohlcv_path(symbol, timeframe)
    if not path.exists():
        return 0
    result = _connect().sql(
        f"SELECT COUNT(*) AS n FROM read_parquet('{path.as_posix()}')"
    ).df()
    return int(result["n"].iloc[0])


def ohlcv_last_refresh(symbol: str, timeframe: Timeframe) -> pd.Timestamp | None:
    path = ohlcv_path(symbol, timeframe)
    if not path.exists():
        return None
    result = _connect().sql(
        f"SELECT MAX(timestamp) AS last_ts FROM read_parquet('{path.as_posix()}')"
    ).df()
    val = result["last_ts"].iloc[0]
    if pd.isna(val):
        return None
    # Always tz-aware UTC — callers compare it against `pd.Timestamp.now(tz="UTC")`.
    stamp = pd.Timestamp(val)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


# --- RFC-002: LiqTide append-only archive (Standing Rule 8) ---------------
#
# One immutable file per date, never overwritten once written — LiqTide's
# own history is not otherwise recoverable if the (self-described beta)
# endpoint changes or disappears. Contrast `write_ohlcv` above, which
# overwrites the whole series every refresh: OHLCV bars are re-fetchable
# from the exchange forever, a LiqTide day's payload is not.


def liqtide_payload_path(date: str) -> Path:
    return CACHE_ROOT / "liqtide" / f"{date}.parquet"


def write_liqtide_payload(date: str, row_df: pd.DataFrame) -> None:
    path = liqtide_payload_path(date)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        row_df.to_parquet(path, index=False)


def read_liqtide_history() -> pd.DataFrame:
    """Read every archived daily LiqTide payload, sorted by date. Empty
    (columnless) df if nothing has been archived yet.
    """
    liqtide_dir = CACHE_ROOT / "liqtide"
    if not liqtide_dir.exists() or not any(liqtide_dir.glob("*.parquet")):
        return pd.DataFrame()
    # union_by_name: rows archived before 24-09-26 lack the additive
    # `tide_value`/`tide_label` columns (RFC-001, regime dashboard). Without
    # it DuckDB rejects the schema mismatch; with it, old rows read those
    # columns as NULL — absent, never a fabricated value.
    return _connect().sql(
        f"SELECT * FROM read_parquet('{(liqtide_dir / '*.parquet').as_posix()}', union_by_name=true) ORDER BY date"
    ).df()


# --- Regime dashboard RFC-001: raw LiqTide payload archive + history backfill
#
# The parquet row above keeps only the flattened fields the composites read.
# The upstream JSON also carries the six signed component impulses, their
# weights, the 0-100 `value`, the label, `signals` and thinned history series
# — none recoverable after the day passes. Each fresh payload is therefore
# also kept verbatim, append-only, one file per `generated_utc` date.
#
# Both live in SUBFOLDERS of `liqtide/` on purpose: `read_liqtide_history`
# globs `liqtide/*.parquet`, so a backfill parquet placed next to the daily
# rows would be unioned into them as if it were a day's payload. The
# `.gitignore` carve-out (`!api/data/cache/liqtide/`) tracks both subfolders.


def liqtide_raw_path(date: str) -> Path:
    return CACHE_ROOT / "liqtide" / "raw" / f"{date}.json"


def write_liqtide_raw(date: str, raw: dict) -> bool:
    """Write one day's upstream JSON verbatim. Append-only: returns False and
    writes nothing when that date is already archived."""
    path = liqtide_raw_path(date)
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(raw, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)
    return True


def read_liqtide_raw(date: str) -> dict | None:
    path = liqtide_raw_path(date)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_liqtide_raw_dates() -> list[str]:
    raw_dir = CACHE_ROOT / "liqtide" / "raw"
    if not raw_dir.exists():
        return []
    return sorted(p.stem for p in raw_dir.glob("*.json"))


def liqtide_backfill_path(date: str) -> Path:
    return CACHE_ROOT / "liqtide" / "backfill" / f"{date}.parquet"


def write_liqtide_backfill(date: str, df: pd.DataFrame) -> None:
    """Long-format history (`series_key, date, value`) extracted from one raw
    payload. Re-running for the same source date rewrites the same content."""
    path = liqtide_backfill_path(date)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


# --- RFC-002: macro-liquidity input series (FRED, DefiLlama) --------------
#
# Full overwrite-per-refresh cache, one file per series id — these
# providers are themselves the durable primary archive (decades of FRED
# history; DefiLlama's own aggregate series back to 2017), not a derived
# composite that could disappear, so (unlike LiqTide above) there is
# nothing to lose by overwriting on every successful refresh.


def liquidity_series_path(series_id: str) -> Path:
    return CACHE_ROOT / "liquidity" / f"{series_id}.parquet"


def read_liquidity_series(series_id: str) -> pd.DataFrame:
    path = liquidity_series_path(series_id)
    if not path.exists():
        return pd.DataFrame(columns=["date", "value"])
    return _connect().sql(
        f"SELECT * FROM read_parquet('{path.as_posix()}') ORDER BY date"
    ).df()


def write_liquidity_series(series_id: str, df: pd.DataFrame) -> None:
    path = liquidity_series_path(series_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.sort_values("date").drop_duplicates(subset="date", keep="last")
    out[["date", "value"]].to_parquet(path, index=False)


def liquidity_series_age_seconds(series_id: str) -> float | None:
    """Seconds since this series' cache file was last written, or None if it
    has never been cached. FRED/DefiLlama publish at most daily, so
    `fred_adapter`/`defillama_adapter` use this to skip a live re-fetch
    (which re-downloads each series' FULL history, not just the tail) when
    the cache is still within their TTL (Standing Rule 4: "cache by
    default... only fetch the tail" — re-fetching everything on every
    request is exactly what that rule exists to prevent).
    """
    path = liquidity_series_path(series_id)
    if not path.exists():
        return None
    return time.time() - path.stat().st_mtime


# --- RFC-002: confirmed leg boundaries (item 41/42 support) ----------------


def confirmed_boundaries_path() -> Path:
    return CACHE_ROOT / "legs" / "confirmed_boundaries.parquet"


def write_confirmed_boundaries(df: pd.DataFrame) -> None:
    path = confirmed_boundaries_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def read_confirmed_boundaries() -> pd.DataFrame:
    path = confirmed_boundaries_path()
    if not path.exists():
        return pd.DataFrame()
    return _connect().sql(f"SELECT * FROM read_parquet('{path.as_posix()}')").df()


# --- RFC-003: narrative proxy series (pytrends/reddit/coingecko) ----------
#
# One file per (source, category_id) pair, full overwrite-per-refresh (like
# the RFC-002 liquidity-series cache above, deduplicated on date) — these
# are today's-snapshot proxy reads accumulated day by day into a durable
# local history, not a once-per-day irrecoverable archive like LiqTide, so
# there is nothing to lose by overwriting the combined series on every
# write. Schema matches Database/Storage Schema's `cache/narrative/{source}/
# {category}.parquet`: `date, raw_value, normalized_value, source_status`.

NARRATIVE_COLUMNS = ["date", "raw_value", "normalized_value", "source_status"]


def narrative_series_path(source: str, category_id: str) -> Path:
    return CACHE_ROOT / "narrative" / source / f"{category_id}.parquet"


def read_narrative_series(source: str, category_id: str) -> pd.DataFrame:
    path = narrative_series_path(source, category_id)
    if not path.exists():
        return pd.DataFrame(columns=NARRATIVE_COLUMNS)
    return _connect().sql(
        f"SELECT * FROM read_parquet('{path.as_posix()}') ORDER BY date"
    ).df()


def write_narrative_point(source: str, category_id: str, date: str, raw_value: float, source_status: str = "fresh") -> None:
    """Write (dedup-on-date) today's raw proxy value for (source,
    category_id). A same-day re-fetch replaces, never double-counts.
    """
    path = narrative_series_path(source, category_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = read_narrative_series(source, category_id)
    new_row = pd.DataFrame([{
        "date": date, "raw_value": raw_value, "normalized_value": None, "source_status": source_status,
    }])
    combined = pd.concat([existing, new_row], ignore_index=True) if not existing.empty else new_row
    combined = combined.sort_values("date").drop_duplicates(subset="date", keep="last")
    combined[NARRATIVE_COLUMNS].to_parquet(path, index=False)


# --- RFC-003: CoinGecko trending snapshot (item 49) ------------------------
#
# Trending is a live "right now" snapshot, not a per-day archive the way
# LiqTide is — cached under one fixed key, overwritten on every successful
# fetch. Per-category counts derived from this snapshot are what actually
# feed the narrative cache above (via write_narrative_point), not this
# snapshot file itself.


def trending_snapshot_path() -> Path:
    return CACHE_ROOT / "narrative" / "coingecko_trending.parquet"


def write_trending_snapshot(date: str, symbols: list[str]) -> None:
    path = trending_snapshot_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"date": date, "symbols": ",".join(symbols)}]).to_parquet(path, index=False)


def read_trending_snapshot() -> tuple[str, list[str]] | None:
    path = trending_snapshot_path()
    if not path.exists():
        return None
    df = _connect().sql(f"SELECT * FROM read_parquet('{path.as_posix()}')").df()
    if df.empty:
        return None
    row = df.iloc[0]
    symbols = row["symbols"].split(",") if row["symbols"] else []
    return row["date"], symbols


# --- Narrative dashboard RFC-2: exchange (Hyperliquid) attention -----------
#
# Two stores, both append-only / forward-written (ADR-6, decision D2):
#   cache/narrative/exchange/markets/{YYYY-MM-DD}.json  daily active-perp list
#   cache/narrative/exchange/{category_id}.parquet      daily per-category row
# Neither is ever overwritten for a date that already exists — a second run
# on the same UTC day is a no-op, so the first observation of a day stands.
# Display-only: nothing here feeds trigger.compute_trigger or /categories.

EXCHANGE_SERIES_COLUMNS = [
    "date",
    "volume_share",
    "volume_status",
    "volume_reason",
    "new_listing_count",
    "listing_status",
    "listing_reason",
    "baseline_date",
]


def exchange_market_snapshot_path(date: str) -> Path:
    return CACHE_ROOT / "narrative" / "exchange" / "markets" / f"{date}.json"


def write_exchange_market_snapshot(date: str, names: list[str]) -> bool:
    """Archive one UTC day's active-perp name list. Append-only: returns False
    and writes nothing when that date already exists."""
    path = exchange_market_snapshot_path(date)
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(sorted(set(names)), ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return True


def read_exchange_market_snapshot(date: str) -> list[str] | None:
    path = exchange_market_snapshot_path(date)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_exchange_market_snapshot_dates() -> list[str]:
    snap_dir = CACHE_ROOT / "narrative" / "exchange" / "markets"
    if not snap_dir.exists():
        return []
    return sorted(p.stem for p in snap_dir.glob("*.json"))


def exchange_series_path(category_id: str) -> Path:
    return CACHE_ROOT / "narrative" / "exchange" / f"{category_id}.parquet"


def read_exchange_series(category_id: str) -> pd.DataFrame:
    path = exchange_series_path(category_id)
    if not path.exists():
        return pd.DataFrame(columns=EXCHANGE_SERIES_COLUMNS)
    return _connect().sql(
        f"SELECT * FROM read_parquet('{path.as_posix()}') ORDER BY date"
    ).df()


def write_exchange_point(category_id: str, row: dict) -> bool:
    """Append one day's exchange-attention row for `category_id`.

    Forward-written and append-only: returns False (writes nothing) if the
    row's date is already present. Missing values are stored as nulls, never
    zero-filled.
    """
    date = row["date"]
    existing = read_exchange_series(category_id)
    if not existing.empty and (existing["date"].astype(str) == date).any():
        return False
    path = exchange_series_path(category_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    new_row = pd.DataFrame([{col: row.get(col) for col in EXCHANGE_SERIES_COLUMNS}])
    new_row = new_row.astype({
        "date": "string", "volume_share": "float64", "volume_status": "string",
        "volume_reason": "string", "new_listing_count": "Int64", "listing_status": "string",
        "listing_reason": "string", "baseline_date": "string",
    })
    if existing.empty:
        combined = new_row
    else:
        existing = existing.astype(new_row.dtypes.to_dict())
        combined = pd.concat([existing, new_row], ignore_index=True)
    combined = combined.sort_values("date", kind="stable")
    combined[EXCHANGE_SERIES_COLUMNS].to_parquet(path, index=False)
    return True


# --------------------------------------------------------------------------
# On-chain growth archive (chain-growth RFC-3). One Parquet file per
# (source, chain_id, metric). Providers return full history each night, so a
# write is a merge with a revision window, not a single-point append:
#   - new dates are inserted;
#   - dates inside the window whose value changed are replaced, marked
#     revised=True, and the old value kept in previous_value;
#   - older dates are never overwritten (a change there is counted as drift);
#   - nothing is ever deleted;
#   - the file is rewritten only when something was inserted or revised, so
#     no-change nights produce no git diff.
# --------------------------------------------------------------------------
ONCHAIN_COLUMNS = ["date", "value", "first_seen_utc", "as_of_utc", "revised", "previous_value"]
ONCHAIN_REVISION_WINDOW_DAYS = 14
_ONCHAIN_DTYPES = {
    "date": "string", "value": "float64", "first_seen_utc": "string",
    "as_of_utc": "string", "revised": "bool", "previous_value": "float64",
}


class OnchainMergeResult:
    __slots__ = ("inserted", "revised", "unchanged", "out_of_window_drift", "dropped_future", "wrote_file", "rows")

    def __init__(self) -> None:
        self.inserted = 0
        self.revised = 0
        self.unchanged = 0
        self.out_of_window_drift = 0
        self.dropped_future = 0
        self.wrote_file = False
        self.rows = 0

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (f"OnchainMergeResult(inserted={self.inserted}, revised={self.revised}, "
                f"unchanged={self.unchanged}, drift={self.out_of_window_drift}, "
                f"dropped_future={self.dropped_future}, wrote_file={self.wrote_file}, rows={self.rows})")


def onchain_series_path(source: str, chain_id: str, metric: str) -> Path:
    return CACHE_ROOT / "onchain" / source / chain_id / f"{metric}.parquet"


def _empty_onchain_frame() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=t) for c, t in _ONCHAIN_DTYPES.items()})[ONCHAIN_COLUMNS]


def read_onchain_series(source: str, chain_id: str, metric: str) -> pd.DataFrame:
    """Stored series sorted by date; an empty frame with ONCHAIN_COLUMNS if absent."""
    path = onchain_series_path(source, chain_id, metric)
    if not path.exists():
        return _empty_onchain_frame()
    df = _connect().sql(f"SELECT * FROM read_parquet('{path.as_posix()}') ORDER BY date").df()
    return df[ONCHAIN_COLUMNS].astype(_ONCHAIN_DTYPES).reset_index(drop=True)


def _values_differ(old: float, new: float) -> bool:
    return abs(old - new) > 1e-9 * max(1.0, abs(old))


def merge_onchain_series(
    source: str,
    chain_id: str,
    metric: str,
    points: list[tuple[str, float]],
    *,
    today: str,
    now_utc: str,
    window_days: int = ONCHAIN_REVISION_WINDOW_DAYS,
) -> OnchainMergeResult:
    """Merge a provider's full series into the stored archive (rules above).

    `today` is the UTC date (YYYY-MM-DD); dates after it are dropped. The
    window covers `today - window_days` .. `today` inclusive.
    """
    from datetime import date as _date, timedelta as _timedelta

    result = OnchainMergeResult()
    today_d = _date.fromisoformat(today)
    window_start = (today_d - _timedelta(days=max(0, int(window_days)))).isoformat()

    incoming: dict[str, float] = {}
    for d, v in points:
        d = str(d)
        if _date.fromisoformat(d) > today_d:
            result.dropped_future += 1
            continue
        incoming[d] = float(v)  # duplicate dates: last one wins

    existing = read_onchain_series(source, chain_id, metric)
    stored = {row.date: row for row in existing.itertuples(index=False)}
    rows = [dict(zip(ONCHAIN_COLUMNS, r)) for r in existing.itertuples(index=False)]
    index = {r["date"]: i for i, r in enumerate(rows)}

    for d in sorted(incoming):
        v = incoming[d]
        if d not in stored:
            rows.append({"date": d, "value": v, "first_seen_utc": now_utc, "as_of_utc": now_utc,
                         "revised": False, "previous_value": float("nan")})
            result.inserted += 1
            continue
        old = float(stored[d].value)
        if not _values_differ(old, v):
            result.unchanged += 1
        elif d >= window_start:
            r = rows[index[d]]
            r.update(value=v, previous_value=old, revised=True, as_of_utc=now_utc)
            result.revised += 1
        else:
            result.out_of_window_drift += 1

    result.rows = len(rows)
    if result.inserted or result.revised:
        path = onchain_series_path(source, chain_id, metric)
        path.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(rows, columns=ONCHAIN_COLUMNS).astype(_ONCHAIN_DTYPES)
        df = df.sort_values("date", kind="stable").reset_index(drop=True)
        df.to_parquet(path, index=False)
        result.wrote_file = True
    return result
