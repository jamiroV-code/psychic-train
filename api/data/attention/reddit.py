"""Reddit mention-count source: wraps `reddit_adapter`; no keys = unavailable, no network."""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

import httpx

from api.data import reddit_adapter
from api.data.attention.types import SourceSeries

SOURCE = "reddit"


def _has_keys() -> bool:
    return bool(os.environ.get("REDDIT_CLIENT_ID") and os.environ.get("REDDIT_CLIENT_SECRET"))


class Session:
    """One OAuth token per run: fetched lazily, reused across symbols, refreshed at most once (after a 401)."""

    def __init__(self) -> None:
        self.token: str | None = None
        self.fetched = False
        self.refreshed = False

    def get(self, client: httpx.Client) -> str | None:
        if not self.fetched:
            self.token, self.fetched = reddit_adapter._get_access_token(client), True
        return self.token

    def refresh(self, client: httpx.Client) -> str | None:
        """A new token, or None when this run already refreshed once."""
        if self.refreshed:
            return None
        self.refreshed = True
        self.token = reddit_adapter._get_access_token(client)
        return self.token


def fetch_series(symbol: str, query: str | None = None, *, client: httpx.Client | None = None,
                 today: date | None = None, session: Session | None = None) -> SourceSeries:
    """One point: posts in the last-day search window, dated the last completed UTC day."""
    today = today or datetime.now(timezone.utc).date()
    if not _has_keys():
        return SourceSeries(SOURCE, symbol, [], "unavailable", "no reddit credentials")
    own = client is None
    client = client or httpx.Client()
    session = session or Session()
    try:
        token = session.get(client)
        if not token:
            return SourceSeries(SOURCE, symbol, [], "unavailable", "token unavailable")
        status: dict = {}
        data = reddit_adapter._fetch_with_backoff(
            client, reddit_adapter.DEFAULT_SUBREDDIT, query or symbol, token, status)
        if data is None and status.get("status") == 401:
            token = session.refresh(client)
            if token:
                data = reddit_adapter._fetch_with_backoff(
                    client, reddit_adapter.DEFAULT_SUBREDDIT, query or symbol, token)
        if data is None:
            return SourceSeries(SOURCE, symbol, [], "unavailable", "search failed")
        count = float(len(data.get("data", {}).get("children", [])))
        return SourceSeries(SOURCE, symbol, [(today - timedelta(days=1), count)], "ok", "")
    except Exception:
        return SourceSeries(SOURCE, symbol, [], "unavailable", "search failed")
    finally:
        if own:
            client.close()
