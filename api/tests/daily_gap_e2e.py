"""Test-only D18 storage fixture and fail-closed real-app entrypoint.

Run as ``python -m api.tests.daily_gap_e2e seed|repair|restore|serve``.
No production offline behavior is introduced.
"""
import json
import os
from pathlib import Path
import socket
import sys
import tempfile


def root():
    value = Path(os.environ["SCREENER_CACHE_ROOT"]).resolve()
    temp = Path(tempfile.gettempdir()).resolve()
    if value.parent != temp or not value.name.startswith("d18-e2e-") or len(value.name) < 18:
        raise RuntimeError("D18 requires a unique d18-e2e-* directory directly beneath temp")
    return value


def seed(action):
    import pandas as pd
    from api.data import cache, fred_adapter
    from api.scripts.seed_e2e_cache import _bars, seed_regime
    target = root()
    target.mkdir(parents=True, exist_ok=True)
    if action == "seed":
        cache.bootstrap_cache_dirs()
        seed_regime()
        # The legacy BTC-leg consumer uses weekly-average WTREGEN, while
        # the dashboard fixture seeds Wednesday-level WDTGAL. Both are
        # synthetic fixture series; materialize the legacy key as well.
        cache.write_liquidity_series(
            fred_adapter.TGA, cache.read_liquidity_series(fred_adapter.TGA_WEDNESDAY),
        )
        for symbol in ("BTC", "ETH", "THIN", "HYPE"):
            for tf in ("15m", "1h", "4h", "1d"):
                frame = _bars(tf, 20 if symbol == "THIN" else 500 if tf == "1d" else 120, 100.)
                cache.write_ohlcv(symbol, tf, frame)
                if symbol == "BTC" and tf == "1d":
                    frame.to_parquet(target / "complete.parquet", index=False)
        (target / "watchlist.json").write_text(json.dumps({"coins": ["BTC", "ETH", "THIN"]}))
        (target / "attempts.jsonl").write_text("")
    frame = pd.read_parquet(target / "complete.parquet")
    if action != "repair":
        frame = frame.drop(index=[100, 101, 300]).reset_index(drop=True)
    cache.write_ohlcv("BTC", "1d", frame)
    manifest = {"missing_days": 3, "ranges": []}
    complete = pd.read_parquet(target / "complete.parquet")
    for start, end in ((100, 101), (300, 300)):
        manifest["ranges"].append({"start": complete.timestamp.iloc[start].date().isoformat(),
                                    "end": complete.timestamp.iloc[end].date().isoformat()})
    (target / "manifest.json").write_text(json.dumps(manifest))


def serve():
    import ccxt
    import httpx
    import requests
    target = root()
    def fail(kind):
        def blocked(*args, **kwargs):
            with (target / "attempts.jsonl").open("a") as out:
                out.write(json.dumps({"attempt": kind}) + "\n")
            raise RuntimeError("D18 offline proof blocked provider access: " + kind)
        return blocked
    ccxt.Exchange.__init__ = fail("exchange-construction")
    # Some cache-first aggregate adapters allocate an unused generic client
    # before reading cached inputs. That allocation is not provider traffic.
    # Fail before every actual HTTP send instead; never return fake data.
    httpx.Client.send = fail("http-provider-request")
    httpx.AsyncClient.send = fail("async-http-provider-request")
    requests.Session.request = fail("requests-provider-request")
    # Windows asyncio needs its loopback socketpair. Provider requests above
    # remain blocked even when a provider URL happens to target loopback.
    original_connect = socket.socket.connect
    def connect(sock, address):
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return original_connect(sock, address)
        return fail("outbound-socket")(sock, address)
    socket.socket.connect = connect
    import uvicorn
    uvicorn.run("api.main:app", host="127.0.0.1", port=int(os.environ["D18_API_PORT"]))


if __name__ == "__main__":
    if sys.argv[1] == "serve":
        serve()
    else:
        seed(sys.argv[1])
