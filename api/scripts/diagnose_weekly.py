"""One-shot diagnostic for the ADR-5 week anchor. Read-only — writes nothing.

Run: uv run --project api python api/scripts/diagnose_weekly.py

Answers, in order, the three things that could make a cached `1w` series come
back Sunday-labelled after the fix landed:

  1. Is the loaded module the fixed one? (prints its file path + constants)
  2. Does resampling produce Monday labels on THIS pandas version?
     (the fix was verified on pandas 3.0.2; the project pins only >=2.2, and
     weekly-resample bin semantics are the thing most likely to differ)
  3. Is the file on disk stale relative to what the code now produces?
     (i.e. written by a still-running old process rather than by this code)

Weekdays are reported BOTH as stored and in UTC. The UTC column is the one
that decides: an exchange weekly open is Monday 00:00 UTC, and Monday in a
local timezone is Sunday 22:00/23:00 UTC.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd

from api.data import cache, ccxt_adapter

SYMBOL = "BTC"
AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def line(title: str) -> None:
    print(f"\n{'=' * 4} {title} {'=' * (60 - len(title))}")


NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _weekdays_utc(stamps: pd.Series) -> list[int]:
    """Weekday IN UTC. Evaluating a local-tz stamp gives the wrong answer:
    Monday 00:00 Europe/Brussels is Sunday 22:00 UTC, and an exchange weekly
    open is defined in UTC. Reading the local weekday here is what made an
    earlier version of this script report a false all-clear."""
    return sorted(pd.to_datetime(stamps, utc=True).dt.dayofweek.unique().tolist())


def describe(stamps: pd.Series, label: str) -> None:
    if stamps.empty:
        print(f"  {label}: EMPTY")
        return
    local = sorted(stamps.dt.dayofweek.unique().tolist())
    utc = _weekdays_utc(stamps)
    local_names = "/".join(NAMES[d] for d in local)
    utc_names = "/".join(NAMES[d] for d in utc)
    flag = "" if utc == [0] else "   <-- not Monday in UTC"
    print(f"  {label}: n={len(stamps)} weekday(as stored)={local_names} "
          f"weekday(UTC)={utc_names}{flag}")
    print(f"      first={stamps.min()} last={stamps.max()}")


def main() -> int:
    line("1. which module is loaded")
    print(f"  pandas            {pd.__version__}")
    print(f"  python            {sys.version.split()[0]}")
    print(f"  ccxt_adapter file {ccxt_adapter.__file__}")
    anchored = all(hasattr(ccxt_adapter, n) for n in ("WEEK_ANCHOR", "WEEK_CLOSED", "WEEK_LABEL"))
    if not anchored:
        print("  !! WEEK_ANCHOR/WEEK_CLOSED/WEEK_LABEL MISSING — this is the PRE-ADR-5 module.")
        print("     The import is resolving to an old copy, not the fixed source file.")
        return 1
    print(f"  WEEK_ANCHOR={ccxt_adapter.WEEK_ANCHOR!r} "
          f"WEEK_CLOSED={ccxt_adapter.WEEK_CLOSED!r} WEEK_LABEL={ccxt_adapter.WEEK_LABEL!r}")

    line("2. the daily input")
    daily = cache.read_ohlcv(SYMBOL, "1d")
    if daily.empty:
        print(f"  no cached {SYMBOL}/1d — nothing to derive from. Stop here.")
        return 1
    ts = pd.to_datetime(daily["timestamp"])
    print(f"  dtype             {daily['timestamp'].dtype}")
    print(f"  tz                {getattr(ts.dt, 'tz', None)}")
    print(f"  times of day seen {sorted(ts.dt.strftime('%H:%M:%S').unique().tolist())[:5]}")
    describe(ts, "daily stamps")
    print(f"  last 3 daily      {[str(x) for x in ts.tail(3).tolist()]}")

    line("3. what resampling does on THIS pandas")
    indexed = daily.set_index("timestamp")
    naive = indexed.resample("W").agg(AGG).dropna(subset=["close"])
    fixed = indexed.resample(
        ccxt_adapter.WEEK_ANCHOR,
        closed=ccxt_adapter.WEEK_CLOSED,
        label=ccxt_adapter.WEEK_LABEL,
    ).agg(AGG).dropna(subset=["close"])
    describe(pd.Series(naive.index), 'resample("W")        ')
    describe(pd.Series(fixed.index), f'resample({ccxt_adapter.WEEK_ANCHOR!r},left,left)')
    same_values = naive.reset_index(drop=True).equals(fixed.reset_index(drop=True))
    print(f"  identical OHLCV membership? {same_values}")
    if len(naive.index) == len(fixed.index):
        offsets = sorted({str(d) for d in (naive.index - fixed.index)})
        print(f"  label offset(s)   {offsets}")

    line("4. what the live function returns right now")
    derived = ccxt_adapter._derive_weekly_from_daily(daily, source="diagnostic")
    describe(pd.to_datetime(derived["timestamp"]), "derived in-memory")

    line("5. what is actually on disk")
    on_disk = cache.read_ohlcv(SYMBOL, "1w")
    describe(pd.to_datetime(on_disk["timestamp"]), "cached 1w.parquet")
    path = cache.ohlcv_path(SYMBOL, "1w")
    print(f"  path              {path}")
    if path.exists():
        print(f"  mtime             {pd.Timestamp(path.stat().st_mtime, unit='s')} (local)")

    line("VERDICT")
    derived_days = set(_weekdays_utc(derived["timestamp"]))
    disk_days = set(_weekdays_utc(on_disk["timestamp"])) if not on_disk.empty else set()

    if derived_days == {0} and disk_days == {0}:
        print("  Both derived and on-disk are Monday-anchored. Nothing wrong.")
        return 0
    if derived_days == {0} and disk_days != {0}:
        print("  The CODE is correct; the FILE is stale.")
        print("  Something else rewrote it with the old module — a uvicorn process still")
        print("  holding the pre-fix import. Restart it, then re-run check_weekly_anchor.py.")
        return 1
    if derived_days != {0}:
        print("  The CODE ITSELF produces non-Monday labels IN UTC.")
        print(f"  derived weekday(s) in UTC = {sorted(derived_days)} (0=Mon ... 6=Sun)")
        print("  If section 2 shows a non-UTC dtype, this is ADR-6: DuckDB converts to the")
        print("  session timezone on read, so the resample anchors on LOCAL midnight.")
        print("  Monday 00:00 local is Sunday 22:00/23:00 UTC. Fix lives in cache._connect().")
        return 1
    print("  Inconclusive — paste the whole output.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
