"""GET /api/refresh/status, POST /api/refresh/now (T35 / S8).

The status endpoint reports the background refresh worker's state, and
`disabled_reason` when it is not running. `POST /now` only wakes the worker
(202); it never fetches inside the request, and at most one run is pending.
With the worker off it answers 503 `worker-not-running` rather than a false
202.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.data import refresh_worker

router = APIRouter(prefix="/api/refresh", tags=["refresh"])


@router.get("/status")
def get_status() -> dict:
    return refresh_worker.status()


@router.post("/now", status_code=202)
def post_refresh_now() -> dict:
    worker = refresh_worker.current_worker()
    if worker is None or not worker.running:
        raise HTTPException(status_code=503, detail="worker-not-running")
    queued = worker.request_now()
    return {"accepted": True, "already_pending": not queued}
