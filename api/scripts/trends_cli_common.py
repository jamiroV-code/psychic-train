"""Shared helpers for the Google Trends owner tools (T100a): error reporting and a lazy TrendReq.

Output policy: an exception is reported by its class name and, when it carries one, the integer HTTP
status. Never the message, the response, headers or cookies (pytrends puts the whole response on it).
"""
from __future__ import annotations

import importlib
from importlib import metadata

RUN_COMMAND = "uv run --project api --with pytrends python -m api.scripts.{module}"


class PytrendsMissing(RuntimeError):
    pass


def http_status(exc: BaseException) -> int | None:
    code = getattr(getattr(exc, "response", None), "status_code", None)
    return code if isinstance(code, int) and not isinstance(code, bool) else None


def error_class(exc: BaseException) -> str:
    status = http_status(exc)
    name = type(exc).__name__
    return f"{name}(HTTP {status})" if status is not None else name


def is_rate_limited(exc: BaseException) -> bool:
    return type(exc).__name__ == "TooManyRequestsError" or http_status(exc) == 429


def missing_message(module: str) -> str:
    return f"pytrends is not installed in the api env. Run: {RUN_COMMAND.format(module=module)}"


def start_client(factory, module: str, err) -> tuple[object | None, int]:
    """Build the client: (client, 0), or (None, 3) when pytrends is missing, or (None, 1) on any other
    failure. TrendReq() itself sends one cookie request to Google, so offline, VPN or timeout fails here;
    only the class (and HTTP status) is printed, never the message (it carries the URL)."""
    try:
        return factory(), 0
    except PytrendsMissing:
        print(missing_message(module), file=err)
        return None, 3
    except Exception as exc:  # noqa: BLE001 - the class is reported, never the message
        print(f"cannot start a Google Trends session: {error_class(exc)}", file=err)
        return None, 1


def make_trendreq():
    """Build a TrendReq; pytrends is imported here only. No retries/backoff_factor (urllib3 2.x)."""
    try:
        request = importlib.import_module("pytrends.request")
    except ImportError as exc:
        raise PytrendsMissing("pytrends") from exc
    return request.TrendReq(hl="en-US", tz=0)


def pytrends_version() -> str:
    try:
        return metadata.version("pytrends")
    except metadata.PackageNotFoundError:
        return "unknown"
