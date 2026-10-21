"""Shared Google Trends fakes (T100a): scripted client, frame builders, scripted errors. No network."""
from __future__ import annotations

import socket
from datetime import date, timedelta

import pandas as pd

# Built from two parts so no secret-shaped literal sits in the source (G8 scan).
SECRET = "tok_" + "SECRET_SENTINEL_123456"
FORBIDDEN_IN_OUTPUT = (SECRET, "Cookie", "Authorization", "Bearer")
TODAY = date(2026, 10, 21)


class FakeResponse:
    def __init__(self, status_code: int, headers: dict | None = None):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = f"body {SECRET}"


class TooManyRequestsError(Exception):
    """Same class name as pytrends.exceptions.TooManyRequestsError."""

    def __init__(self, message: str, response: FakeResponse):
        super().__init__(message)
        self.response = response


class ResponseError(Exception):
    """Same class name as pytrends.exceptions.ResponseError."""

    def __init__(self, message: str, response: FakeResponse):
        super().__init__(message)
        self.response = response


FakeTooManyRequests = TooManyRequestsError
FakeResponseError = ResponseError


def _secret_headers() -> dict:
    return {"Set-Cookie": SECRET, "Authorization": "Bearer " + SECRET}


def too_many() -> TooManyRequestsError:
    return FakeTooManyRequests(f"The request failed: Google returned a response with code 429 {SECRET}",
                               FakeResponse(429, _secret_headers()))


def forbidden() -> ResponseError:
    return FakeResponseError(f"The request failed: code 403 {SECRET}", FakeResponse(403, _secret_headers()))


class FakeTrendReq:
    """Scripted stand-in for pytrends.request.TrendReq.

    suggestions: name -> list of candidates or an exception (missing name -> []).
    frames: consumed in order by interest_over_time; an exception item is raised.
    """

    def __init__(self, suggestions: dict | None = None, frames: list | None = None):
        self.suggestion_script = dict(suggestions or {})
        self.frames = list(frames or [])
        self.suggestion_calls: list[str] = []
        self.payloads: list[tuple[list[str], str]] = []

    def suggestions(self, keyword: str):
        self.suggestion_calls.append(keyword)
        item = self.suggestion_script.get(keyword, [])
        if isinstance(item, BaseException):
            raise item
        return item

    def build_payload(self, kw_list, cat=0, timeframe="today 5-y", geo="", gprop=""):
        self.payloads.append((list(kw_list), timeframe))

    def interest_over_time(self):
        item = self.frames.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def factory(client: FakeTrendReq):
    return lambda: client


def candidate(mid: str, title: str, type_: str) -> dict:
    return {"mid": mid, "title": title, "type": type_}


def _frame(terms: list[str], index, values: dict | None, partial_last: bool) -> pd.DataFrame:
    n = len(index)
    data = {}
    for i, term in enumerate(terms):
        v = (values or {}).get(term)
        if v is None:
            data[term] = [(10 * (i + 1) + k) % 101 for k in range(n)]
        elif isinstance(v, int):
            data[term] = [v] * n
        else:
            data[term] = list(v)
    data["isPartial"] = [False] * n
    if partial_last and n:
        data["isPartial"][-1] = True
    frame = pd.DataFrame(data, index=pd.DatetimeIndex(index, name="date"))
    return frame


def daily_frame(terms: list[str], days: int = 90, end: date = TODAY - timedelta(days=1),
                values: dict | None = None, partial_last: bool = False) -> pd.DataFrame:
    index = pd.date_range(end=pd.Timestamp(end), periods=days, freq="D")
    return _frame(terms, index, values, partial_last)


def weekly_frame(terms: list[str], weeks: int = 13, end: date = TODAY - timedelta(days=3),
                 values: dict | None = None) -> pd.DataFrame:
    index = pd.date_range(end=pd.Timestamp(end), periods=weeks, freq="7D")
    return _frame(terms, index, values, False)


def frame_with_today(terms: list[str], days: int = 90, values: dict | None = None) -> pd.DataFrame:
    """Daily frame whose last row is today and flagged partial."""
    return daily_frame(terms, days=days, end=TODAY, values=values, partial_last=True)


def block_network(monkeypatch) -> None:
    """Any socket connect in a test fails loudly."""
    def _refuse(*_a, **_k):
        raise AssertionError("network access attempted in a Trends test")

    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)


def tree_snapshot(*roots) -> dict:
    """path -> (size, mtime_ns) for every file under the roots."""
    snap = {}
    for root in roots:
        for p in sorted(root.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                st = p.stat()
                snap[str(p)] = (st.st_size, st.st_mtime_ns)
    return snap
