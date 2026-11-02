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
    from api.data import cache
    from api.scripts.seed_e2e_cache import _bars, seed_regime
    target = root()
    target.mkdir(parents=True, exist_ok=True)
    if action == "seed":
        cache.bootstrap_cache_dirs()
        seed_regime()
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
    httpx.Client.__init__ = fail("http-provider-construction")
    httpx.AsyncClient.__init__ = fail("async-http-provider-construction")
    requests.Session.__init__ = fail("requests-provider-construction")
    # Windows asyncio creates a real loopback socketpair for its self-pipe.
    # Permit that local OS transport, never an external connection. Provider
    # construction above still fails even if a provider targets loopback.
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
