"""Shared HTTP retry, pacing and safe diagnostics for the attention fetchers."""
from __future__ import annotations

import random
import re
import time

import httpx

REASON_LIMIT = 120

_REDACTIONS = (
    (re.compile(r"https?://\S+", re.I), "<url>"),
    (re.compile(r"\bBearer\s+\S+", re.I), "Bearer <redacted>"),
    (re.compile(r"(?i)\b([\w-]*(?:key|token|secret|auth|password|pwd)[\w-]*)\s*[=:]\s*\S+"), r"\1=<redacted>"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), "<ip>"),
    (re.compile(r"\b(?:[0-9a-fA-F]{0,4}:){3,7}[0-9a-fA-F]{0,4}\b"), "<ip>"),
    (re.compile(r"\b[A-Za-z0-9_\-]{20,}\b"), "<redacted>"),
)


def redact(text: object, limit: int = REASON_LIMIT) -> str:
    """ASCII-only, secret/IP/URL-free, whitespace-collapsed text of at most `limit` characters."""
    out = str(text)
    for pat, repl in _REDACTIONS:
        out = pat.sub(repl, out)
    out = out.encode("ascii", "replace").decode("ascii")
    out = re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]", " ", out)).strip()
    return out[:limit]


def describe_exc(exc: BaseException) -> str:
    """`Class [HTTP n]: redacted message`; never headers or request URLs."""
    resp = getattr(exc, "response", None)
    status = getattr(resp, "status_code", None)
    msg = redact(exc)
    head = type(exc).__name__ + (f" HTTP {status}" if status else "")
    return redact(f"{head}: {msg}" if msg else head)


class Pacer:
    """Keeps at least `min_interval` seconds between calls to one host."""

    def __init__(self, min_interval: float, clock=time.monotonic):
        self.min_interval = min_interval
        self.clock = clock
        self._last: float | None = None

    def wait(self, sleep) -> None:
        if self._last is not None:
            gap = self.min_interval - (self.clock() - self._last)
            if gap > 0:
                sleep(gap)
        self._last = self.clock()


def retry_delay(resp: httpx.Response, attempt: int, base: float, *, cap: float, rng=random.random) -> float:
    """Retry-After (seconds) when sent, else base * 2**attempt; plus jitter; Retry-After capped."""
    raw = resp.headers.get("Retry-After", "")
    try:
        wait = min(float(raw), cap) if raw.strip() else None
    except ValueError:
        wait = None
    if wait is None:
        wait = base * (2 ** attempt)
        return wait + rng() * wait * 0.25
    return wait + rng()


def get_with_retry(client: httpx.Client, url: str, *, sleep, retries: int, base: float, timeout: float,
                   pacer: Pacer | None = None, params: dict | None = None, headers: dict | None = None,
                   retry_after_cap: float = 120.0) -> httpx.Response:
    """GET, retrying only HTTP 429 up to `retries` times; the last response is returned either way."""
    kwargs: dict = {"timeout": timeout}
    if params is not None:
        kwargs["params"] = params
    if headers is not None:
        kwargs["headers"] = headers
    for attempt in range(retries + 1):
        if pacer is not None:
            pacer.wait(sleep)
        resp = client.get(url, **kwargs)
        if resp.status_code != 429 or attempt == retries:
            return resp
        sleep(retry_delay(resp, attempt, base, cap=retry_after_cap))
    raise AssertionError("unreachable")
