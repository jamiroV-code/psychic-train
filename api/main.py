"""FastAPI application entrypoint.

Security posture: this file never binds a socket (there is no `.run()` call
here) — the bind address is a run command concern, set by whoever starts
uvicorn.

* Local development keeps the loopback bind:

      uv run uvicorn api.main:app --reload --host 127.0.0.1 --port 8000

* Phase 1 deployment (the author's own PC) is reachable only over the
  Tailscale interface: the `deploy/start-api.ps1` launcher binds uvicorn to the
  PC's Tailscale IPv4 address, so no listener exists on the LAN or the
  internet. See `deploy/README.md`.

CORS is scoped to an explicit origin list — default `http://localhost:3000`
(the web/ dev server), overridable with `SCREENER_CORS_ORIGINS`
(comma-separated). No credentials, and only the methods and header the API
actually uses.
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

# NOTE (RFC-002/RFC-003 scope): routers/regime.py (item 42) and
# routers/narrative.py (item 56) are now both wired in.
from api.routers import narrative, onchain_activity, pairs, regime, screener, watchlist

app = FastAPI(title="Momentum Screener API")

# Origin-exact, and overridable for the E2E only.
#
# The Playwright run serves the frontend on a non-default port (so it can
# never silently reuse a dev server pointed at the real cache), which makes it
# a different origin. `SCREENER_CORS_ORIGINS` — comma-separated — lets that
# process widen the list without this file's default ever changing. Unset, the
# behaviour is exactly what it was: localhost:3000 alone.
#
# The deploy launcher uses the same variable to allow the Tailscale web
# origin. Unset gives the default; set-but-empty gives an empty list (deny
# all). Entries are stripped and blanks dropped; trailing slashes are not
# normalized (a browser `Origin` header never has one).
_DEFAULT_CORS_ORIGINS = "http://localhost:3000"


def _parse_cors_origins(raw: str | None) -> list[str]:
    value = _DEFAULT_CORS_ORIGINS if raw is None else raw
    return [origin.strip() for origin in value.split(",") if origin.strip()]


def _cors_options(origins: list[str]) -> dict:
    # No credentialed fetch exists in web/, and the API serves only GET plus
    # the watchlist's POST/DELETE. Starlette answers OPTIONS preflight itself.
    return {
        "allow_origins": list(origins),
        "allow_credentials": False,
        "allow_methods": ["GET", "POST", "DELETE"],
        "allow_headers": ["Content-Type"],
    }


CORS_ORIGINS = _parse_cors_origins(os.environ.get("SCREENER_CORS_ORIGINS"))

app.add_middleware(CORSMiddleware, **_cors_options(CORS_ORIGINS))

# RFC-004 decision 5: /api/regime/components returns decades of daily points;
# gzip is transparent to clients (no shape change).
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(screener.router)
app.include_router(watchlist.router)
app.include_router(regime.router)
app.include_router(narrative.router)
app.include_router(onchain_activity.router)
app.include_router(pairs.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
