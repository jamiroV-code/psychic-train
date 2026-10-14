"""One structured log line per request: host, path, status, duration, tier. Nothing else."""
from __future__ import annotations

import ipaddress
import logging
import re

LOGGER_NAME = "data_integration.fetch"
_UNSAFE = re.compile(r"[^\x21-\x7e]")


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def _safe_host(host: str) -> str:
    host = (host or "").strip("[]")
    try:
        ipaddress.ip_address(host)
        return "ip-redacted"
    except ValueError:
        return _UNSAFE.sub("_", host)[:100]


def _safe_path(path: str) -> str:
    path = (path or "/").split("?", 1)[0].split("#", 1)[0]
    return _UNSAFE.sub("_", path)[:200] or "/"


def log_request(host: str, path: str, status: object, duration_s: float, tier: int, logger: logging.Logger | None = None) -> None:
    (logger or get_logger()).info(
        "request host=%s path=%s status=%s duration_ms=%d tier=%s",
        _safe_host(host), _safe_path(path), _UNSAFE.sub("_", str(status))[:40], int(duration_s * 1000), int(tier),
    )
