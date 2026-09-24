"""FastAPI application entrypoint.

Security Posture (PLAN.md): binds to 127.0.0.1 only, never 0.0.0.0 — this is
a personal, single-machine tool. Run with:

    uv run uvicorn api.main:app --reload --host 127.0.0.1 --port 8000

CORS is scoped to the web/ dev server's origin only (http://localhost:3000),
per the VALIDATE infra-dimension finding — without this, the very first
manual test in RFC-001 (load /screener, confirm panels render) fails on a
browser CORS error before any real functionality can be checked.
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

# NOTE (RFC-002/RFC-003 scope): routers/regime.py (item 42) and
# routers/narrative.py (item 56) are now both wired in.
from api.routers import narrative, regime, screener, watchlist

app = FastAPI(title="Momentum Screener API")

# Origin-exact, and overridable for the E2E only.
#
# The Playwright run serves the frontend on a non-default port (so it can
# never silently reuse a dev server pointed at the real cache), which makes it
# a different origin. `SCREENER_CORS_ORIGINS` — comma-separated — lets that
# process widen the list without this file's default ever changing. Unset, the
# behaviour is exactly what it was: localhost:3000 alone.
_DEFAULT_CORS_ORIGINS = "http://localhost:3000"
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("SCREENER_CORS_ORIGINS", _DEFAULT_CORS_ORIGINS).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# RFC-004 decision 5: /api/regime/components returns decades of daily points;
# gzip is transparent to clients (no shape change).
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(screener.router)
app.include_router(watchlist.router)
app.include_router(regime.router)
app.include_router(narrative.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
