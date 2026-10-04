"""One-shot London Strategic Edge shape probe (S3 Step 0, run on the user's PC).

Answers what the offline adapter can only assume: the auth header scheme, the
candles row shape and timestamp convention, whether `timeframe="1w"` is served,
how an unknown ticker answers, and the `/vault/usage` shape.

Secret hygiene (repo is public; LSE forbids redistribution):
- the API key is read from the environment only, never a flag;
- the key is never printed, logged or written; it travels only in a header;
- console output is limited to labels, header-scheme names, HTTP status codes,
  key names and type names: never a URL, a header, a body or a price;
- raw responses go to the git-ignored `api/data/cache/equities/_probe/`;
- the committable fixture `out/lse_candles_probe_shape.json` is SANITISED:
  symbol TEST, prices and volumes from a seeded synthetic walk, only the keys,
  value types, wrapper layout and timestamp strings of the real response.

Needs only `httpx`. See README.md.
"""
from __future__ import annotations

import json
import os
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import httpx

# ASSUMED endpoints (inferred from the lse-data SDK's candles/usage calls);
# LSE_BASE_URL may override the host if the default is wrong.
BASE_URL = os.environ.get("LSE_BASE_URL", "https://londonstrategicedge.com/api").rstrip("/")
CANDLES_PATHS = ("/vault/candles", "/candles")
USAGE_PATH = "/vault/usage"
TIMEOUT = httpx.Timeout(15.0)
SCHEMES = ("Bearer", "X-API-Key")
GOOD_SYMBOL = "AAPL"
BAD_SYMBOL = "ZZZZNOTREAL"

REPO_ROOT = Path(__file__).resolve().parents[5]
RAW_DIR = REPO_ROOT / "api" / "data" / "cache" / "equities" / "_probe"
OUT_PATH = Path(__file__).resolve().parent / "out" / "lse_candles_probe_shape.json"


def _headers(scheme: str, key: str) -> dict:
    if scheme == "Bearer":
        return {"Authorization": f"Bearer {key}"}
    return {"X-API-Key": key}


def _say(label: str, status: object) -> None:
    # Only fixed labels and status codes / type names reach the console.
    print(f"{label}: {status}")


def _save_raw(name: str, resp: httpx.Response) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"{name}.json").write_bytes(resp.content)


def _candles(client, scheme, key, path, symbol, timeframe) -> httpx.Response | None:
    params = {
        "symbol": symbol,
        "timeframe": timeframe,
        "start": (date.today() - timedelta(days=60)).isoformat(),
        "limit": 5000,
        "order": "asc",
    }
    try:
        return client.get(BASE_URL + path, params=params, headers=_headers(scheme, key))
    except httpx.HTTPError as exc:
        _say(f"candles {symbol} {timeframe} via {path} [{scheme}]", type(exc).__name__)
        return None


def _rows(payload):
    if isinstance(payload, list):
        return payload, None
    if isinstance(payload, dict):
        for k in ("data", "candles", "rows", "results"):
            if isinstance(payload.get(k), list):
                return payload[k], k
    return None, None


def _synthetic_like(value, rng: random.Random, price: float, key: str):
    """A synthetic value of the same type as `value`; never the real number."""
    if key == "symbol":
        return "TEST"
    if key == "timestamp":
        return value  # calendar position only (the convention under test)
    if key == "volume":
        synth = float(rng.randint(1_000, 100_000))
    else:
        synth = round(price * (1 + rng.uniform(-0.01, 0.01)), 4)
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return int(synth)
    if isinstance(value, float):
        return synth
    if isinstance(value, str):
        return str(synth)
    return None


def _sanitise(payload) -> object:
    rows, wrapper = _rows(payload)
    rng = random.Random(20261004)
    price = 100.0
    clean_rows = []
    for row in rows or []:
        price = max(1.0, price * (1 + rng.uniform(-0.02, 0.02)))
        clean = {k: _synthetic_like(v, rng, price, k) for k, v in row.items()}
        for k in ("open", "high", "low", "close"):
            if k in clean and isinstance(clean[k], (int, float)):
                clean[k] = round(price, 4)
        if isinstance(clean.get("high"), (int, float)):
            clean["high"] = round(price * 1.01, 4)
        if isinstance(clean.get("low"), (int, float)):
            clean["low"] = round(price * 0.99, 4)
        clean_rows.append(clean)
    if wrapper is None:
        return clean_rows
    out = {}
    for k, v in payload.items():
        if k == wrapper:
            out[k] = clean_rows
        elif isinstance(v, bool) or v is None:
            out[k] = v
        elif isinstance(v, (int, float)):
            out[k] = 0
        elif isinstance(v, str):
            out[k] = "TEST" if k == "symbol" else "redacted"
        else:
            out[k] = None
    return out


def main() -> int:
    key = os.environ.get("LSE_API_KEY")
    if not key:
        _say("key", "missing (set it in the environment for this shell only)")
        return 2

    with httpx.Client(timeout=TIMEOUT) as client:
        scheme = path = None
        daily = None
        for s in SCHEMES:
            for p in CANDLES_PATHS:
                resp = _candles(client, s, key, p, GOOD_SYMBOL, "1d")
                if resp is None:
                    continue
                _say(f"candles {GOOD_SYMBOL} 1d via {p} [{s}]", resp.status_code)
                if resp.status_code == 200:
                    scheme, path, daily = s, p, resp
                    break
            if daily is not None:
                break
        if daily is None:
            _say("result", "no scheme/path combination returned 200")
            return 1
        _say("auth scheme", scheme)
        _save_raw("candles_1d", daily)

        try:
            payload = daily.json()
        except ValueError:
            _say("candles 1d body", "not JSON")
            return 1
        rows, wrapper = _rows(payload)
        _say("candles 1d wrapper key", wrapper or "(top-level list)")
        _say("candles 1d row count", len(rows or []))
        if rows:
            _say("row keys", sorted(rows[0].keys()))
            _say("row value types", {k: type(v).__name__ for k, v in sorted(rows[0].items())})
            ts = str(rows[0].get("timestamp", ""))
            _say("timestamp time-of-day suffix", ts[10:] or "(date only)")

        weekly = _candles(client, scheme, key, path, GOOD_SYMBOL, "1w")
        if weekly is not None:
            _say("candles 1w status", weekly.status_code)
            _save_raw("candles_1w", weekly)

        bad = _candles(client, scheme, key, path, BAD_SYMBOL, "1d")
        if bad is not None:
            _say("bad ticker status", bad.status_code)
            _save_raw("candles_bad", bad)

        try:
            usage = client.get(BASE_URL + USAGE_PATH, headers=_headers(scheme, key))
            _say("usage status", usage.status_code)
            _save_raw("usage", usage)
            if usage.status_code == 200:
                body = usage.json()
                if isinstance(body, dict):
                    _say("usage keys", sorted(body.keys()))
        except (httpx.HTTPError, ValueError) as exc:
            _say("usage", type(exc).__name__)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(_sanitise(payload), indent=1) + "\n")
    _say("sanitised fixture", "written to s3-probe/out/lse_candles_probe_shape.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
