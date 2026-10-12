"""Seed synthetic equities for the Playwright E2E (T48 / S9D). Writes nothing live.

Run by `web/playwright.config.ts` after `seed_e2e_cache.py` (which empties the
cache root) and before uvicorn starts. It writes, all synthetic:

* daily bars for `SYNA`, `SYNB`, `SYNC` (420 NYSE sessions each, so the
  weekly series is well clear of the 60-bar rule) and `SYNTHIN` (20 sessions,
  below that rule on purpose), each ending on the newest NYSE session whose
  bar is due, plus the weekly bars derived from them, through
  `lse_adapter._write_cache` so every parquet carries the
  `mysite.redistributable=false` tag and a `fetched_at` sidecar;
* `equities.json` at `SCREENER_EQUITIES_PATH`;
* an `equities` key in `web/e2e/.fixture-manifest.json` (every other key is
  kept as `seed_e2e_cache.py` wrote it).

The names are obviously synthetic and the prices are a deterministic wave,
not any real price series. No network call is made and no key is read.

Safety: refuses to run unless `SCREENER_CACHE_ROOT` is set and is not the real
cache root, and `SCREENER_EQUITIES_PATH` is set and is not the real
`api/data/equities.json`.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import sys
from datetime import timedelta
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd

TICKERS = ["SYNA", "SYNB", "SYNC", "SYNTHIN"]
THIN_TICKER = "SYNTHIN"
SESSION_COUNT = 420
THIN_SESSION_COUNT = 20  # below the 60-bar rule on purpose
BASES = {"SYNA": 50.0, "SYNB": 120.0, "SYNC": 300.0, "SYNTHIN": 10.0}

MANIFEST_PATH = _REPO_ROOT / "web" / "e2e" / ".fixture-manifest.json"
MANIFEST_KEY = "equities"


def guard() -> tuple[Path, Path]:
    """The disposable cache root and equities file; exits on a real path."""
    from api.data import cache, equities_store

    raw_root = os.environ.get("SCREENER_CACHE_ROOT")
    if not raw_root:
        sys.exit("REFUSING: SCREENER_CACHE_ROOT is not set; this would write into the real cache.")
    root = Path(raw_root).resolve()
    if root == cache.DEFAULT_CACHE_ROOT.resolve():
        sys.exit(f"REFUSING: SCREENER_CACHE_ROOT points at the real cache ({root}).")
    if Path(cache.CACHE_ROOT).resolve() != root:
        sys.exit("REFUSING: the cache module does not read SCREENER_CACHE_ROOT.")
    raw_path = os.environ.get("SCREENER_EQUITIES_PATH")
    if not raw_path:
        sys.exit("REFUSING: SCREENER_EQUITIES_PATH is not set; this would overwrite the real equities list.")
    path = Path(raw_path).resolve()
    if path == equities_store.DEFAULT_EQUITIES_PATH.resolve():
        sys.exit(f"REFUSING: SCREENER_EQUITIES_PATH points at the real equities list ({path}).")
    return root, path


def sessions(now: pd.Timestamp, count: int) -> list:
    """The `count` newest NYSE sessions up to the newest one whose bar is due."""
    from api.data import equities_calendar, lse_adapter

    d = equities_calendar.last_due_session(now)
    out = []
    while len(out) < count:
        if lse_adapter.is_nyse_session(d):
            out.append(d)
        d -= timedelta(days=1)
    return out[::-1]


def daily_bars(ticker: str, now: pd.Timestamp, count: int) -> pd.DataFrame:
    """A deterministic synthetic wave on NYSE sessions, 00:00 Z like the adapter."""
    from api.data import lse_adapter

    days = sessions(now, count)
    base = BASES[ticker]
    phase = TICKERS.index(ticker)
    closes = [
        base * (1 + 0.0008 * i) + base * 0.08 * math.sin(i / (9 + 3 * phase) + phase)
        for i in range(count)
    ]
    opens = [closes[0]] + closes[:-1]
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime([d.isoformat() for d in days], utc=True),
            "open": opens,
            "high": [max(o, c) * 1.01 for o, c in zip(opens, closes)],
            "low": [min(o, c) * 0.99 for o, c in zip(opens, closes)],
            "close": closes,
            "volume": [1_000_000.0 + 1000.0 * i for i in range(count)],
            "source": lse_adapter.SOURCE,
        }
    )[lse_adapter.OHLCV_COLUMNS]


def update_manifest(manifest_path: Path, entry: dict) -> None:
    """Add or replace the `equities` key only; every other key is kept."""
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8") or "{}")
    manifest[MANIFEST_KEY] = entry
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def seed(now: pd.Timestamp | None = None, manifest_path: Path | None = None) -> dict:
    """Write the synthetic equities; returns the manifest entry."""
    root, equities_path = guard()
    from api.data import equities_calendar, lse_adapter
    from api.data.ccxt_adapter import _derive_weekly_from_daily

    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    now = now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")

    shutil.rmtree(root / "equities", ignore_errors=True)
    bars: dict[str, dict[str, int]] = {}
    for ticker in TICKERS:
        count = THIN_SESSION_COUNT if ticker == THIN_TICKER else SESSION_COUNT
        daily = daily_bars(ticker, now, count)
        weekly = _derive_weekly_from_daily(daily, lse_adapter.SOURCE)
        lse_adapter._write_cache(ticker, "1d", daily, now)
        lse_adapter._write_cache(ticker, "1w", weekly, now)
        bars[ticker] = {"1d": len(daily), "1w": len(weekly)}

    equities_path.parent.mkdir(parents=True, exist_ok=True)
    equities_path.write_text(json.dumps({"tickers": TICKERS}, indent=2) + "\n", encoding="utf-8")

    entry = {
        "tickers": TICKERS,
        "thin_ticker": THIN_TICKER,
        "bars_written": bars,
        "last_session": equities_calendar.last_due_session(now).isoformat(),
        "equities_path": str(equities_path),
        "redistributable": False,
        "seeded_at": now.isoformat(),
    }
    update_manifest(MANIFEST_PATH if manifest_path is None else manifest_path, entry)
    return entry


def main() -> int:
    entry = seed()
    print(f"equities   {entry['tickers']} seeded, last session {entry['last_session']}")
    print(f"bars       {entry['bars_written']}")
    print(f"list       {entry['equities_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
