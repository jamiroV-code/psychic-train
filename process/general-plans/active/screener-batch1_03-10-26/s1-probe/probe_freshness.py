"""P-S1-1 — read-only freshness probe for the user PC (T32 / S1).

Run from the repo root:

    uv run --project api python process/general-plans/active/screener-batch1_03-10-26/s1-probe/probe_freshness.py

Prints:
  (a) the OHLCV cache table: bars, newest bar, its age, and the fetch time
      from the sidecar (or the parquet mtime when there is no sidecar);
  (b) host UTC, Hyperliquid `fetch_time`, and the skew in seconds
      (host midpoint minus exchange time; `unknown` if it fails);
  (c) which end of history `fetch_ohlcv(since=None, limit=5)` and
      `fetch_ohlcv(since=3 days ago, limit=5)` return for BTC 1h;
  (d) wall-clock seconds and live ccxt call count for one board build at
      timeframe=1h with every TTL expired, against the web client's 10 s
      abort.

Read-only: the live cache is never written. (d) runs the board in-process on
a temporary COPY of the cache tree whose sidecars are removed and parquet
mtimes aged, so every fetch is due; the copy is deleted afterwards. Calls in
(b) and (c) go straight to ccxt and touch no cache file. Pass `--skip-board`
to leave out (d).
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO))

from api.data import cache, freshness  # noqa: E402

WEB_TIMEOUT_SECONDS = 10.0


def _fmt_age(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    if seconds < 3600:
        return f"{seconds / 60:.1f}m"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


def section_a(now: pd.Timestamp) -> None:
    print("\n(a) OHLCV cache  root =", cache.CACHE_ROOT)
    root = cache.CACHE_ROOT / "ohlcv"
    files = sorted(root.glob("*/*.parquet")) if root.exists() else []
    if not files:
        print("    (no cached OHLCV files)")
        return
    print(f"    {'symbol':<10}{'tf':<5}{'bars':>6}  {'newest bar (UTC)':<22}{'bar age':>9}  "
          f"{'fetched_at':<22}{'fetch age':>10}  {'source':<8}{'stale':>6}")
    for path in files:
        symbol, tf = path.parent.name, path.stem
        if tf not in freshness.TIMEFRAME_SECONDS:
            continue
        bars, last = cache.ohlcv_footer_stats(symbol, tf)
        fetched = cache.read_fetched_at(symbol, tf)
        source = "sidecar" if cache.ohlcv_meta_path(symbol, tf).exists() else "mtime"
        bar_age = (now - last).total_seconds() if last is not None else None
        fetch_age = (now - fetched).total_seconds() if fetched is not None else None
        stale = "-" if tf == "1w" else freshness.is_stale(last, tf, now)  # 1w: judged on its 1d row
        print(f"    {symbol:<10}{tf:<5}{bars:>6}  {freshness.iso_z(last) or '-':<22}{_fmt_age(bar_age):>9}  "
              f"{freshness.iso_z(fetched) or '-':<22}{_fmt_age(fetch_age):>10}  {source:<8}{str(stale):>6}")


def _exchange():
    import ccxt

    ex = ccxt.hyperliquid()
    ex.load_markets()
    return ex


def section_b(ex) -> None:
    print("\n(b) clock skew")
    before = time.time()
    try:
        exchange_ms = ex.fetch_time()
    except Exception as exc:  # unknown, not an error
        exchange_ms = None
        print(f"    fetch_time failed: {type(exc).__name__}: {exc}")
    after = time.time()
    print("    host UTC      :", freshness.iso_z(pd.Timestamp(after, unit="s", tz="UTC")))
    if exchange_ms is None:
        print("    exchange time : unknown")
        print("    skew          : unknown")
        return
    skew = (before + after) / 2.0 - exchange_ms / 1000.0
    print("    exchange time :", freshness.iso_z(pd.Timestamp(exchange_ms, unit="ms", tz="UTC")))
    print(f"    skew          : {skew:+.3f} s (host minus exchange; warning above 120 s: "
          f"{'YES' if abs(skew) > 120 else 'no'})")
    print(f"    round trip    : {after - before:.3f} s")


def section_c(ex) -> None:
    print("\n(c) which end of history does each request return? (BTC/USDC:USDC, 1h)")
    now = pd.Timestamp.now(tz="UTC")
    tf_ms = freshness.TIMEFRAME_SECONDS["1h"] * 1000
    since_3d = int((now - pd.Timedelta(days=3)).timestamp() * 1000)
    for label, since in (("since=None, limit=5", None), ("since=3d ago, limit=5", since_3d)):
        try:
            raw = ex.fetch_ohlcv("BTC/USDC:USDC", timeframe="1h", since=since, limit=5)
        except Exception as exc:
            print(f"    {label:<24} failed: {type(exc).__name__}: {exc}")
            continue
        opens = [pd.Timestamp(r[0], unit="ms", tz="UTC") for r in raw]
        if not opens:
            print(f"    {label:<24} returned no bars")
            continue
        newest_gap = (now.timestamp() * 1000 - raw[-1][0]) / tf_ms
        print(f"    {label:<24} {len(opens)} bars  {freshness.iso_z(opens[0])} .. {freshness.iso_z(opens[-1])}  "
              f"(newest is {newest_gap:.2f} timeframes before host now)")
        if since is None:
            verdict = "LATEST bars (B3 holds)" if newest_gap <= 1.0 else "NOT the latest (use the _tail_since fallback)"
        else:
            verdict = ("OLDEST bars after since (as assumed)" if opens[0] >= pd.Timestamp(since, unit="ms", tz="UTC")
                       and newest_gap > 5 else "unexpected end of history")
        print(f"    {'':<24} -> {verdict}")


def section_d() -> None:
    print("\n(d) one board build, timeframe=1h, every TTL expired (in-process, on a temporary cache copy)")
    from api.analytics import screener_board
    from api.data import ccxt_adapter

    src = cache.CACHE_ROOT
    tmp = Path(tempfile.mkdtemp(prefix="probe-freshness-"))
    copy = tmp / "cache"
    try:
        if src.exists():
            shutil.copytree(src, copy)
        else:
            copy.mkdir(parents=True)
        aged = time.time() - 7 * 86400
        for meta in copy.glob("ohlcv/*/*.meta.json"):
            meta.unlink()
        for parquet in copy.glob("ohlcv/*/*.parquet"):
            os.utime(parquet, (aged, aged))

        calls = {"n": 0}
        real_fetch = ccxt_adapter._fetch_with_backoff

        def counting(*args, **kwargs):
            calls["n"] += 1
            return real_fetch(*args, **kwargs)

        cache.CACHE_ROOT = copy
        ccxt_adapter._fetch_with_backoff = counting
        ccxt_adapter.reset_exchange_cache()
        started = time.perf_counter()
        try:
            board = screener_board.build_screener_board("1h")
        finally:
            elapsed = time.perf_counter() - started
            ccxt_adapter._fetch_with_backoff = real_fetch
            cache.CACHE_ROOT = src
        stale = sum(1 for c in board.coins if c.chart.stale)
        print(f"    coins           : {len(board.coins)} ({stale} with a stale 1h chart)")
        print(f"    live ccxt calls : {calls['n']} (load_markets not counted)")
        print(f"    wall clock      : {elapsed:.2f} s vs web timeout {WEB_TIMEOUT_SECONDS:.0f} s -> "
              f"{'OVER the timeout (S8 needed before deploy)' if elapsed > WEB_TIMEOUT_SECONDS else 'within the timeout'}")
        print(f"    clock skew      : {board.clock_skew_seconds} s, warning={board.clock_skew_warning}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skip-board", action="store_true", help="leave out section (d)")
    args = parser.parse_args()

    now = pd.Timestamp.now(tz="UTC")
    print("P-S1-1 freshness probe  host now:", freshness.iso_z(now))
    section_a(now)
    try:
        ex = _exchange()
    except Exception as exc:
        print(f"\n(b)/(c) skipped: exchange unavailable ({type(exc).__name__}: {exc})")
    else:
        section_b(ex)
        section_c(ex)
    if not args.skip_board:
        section_d()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
