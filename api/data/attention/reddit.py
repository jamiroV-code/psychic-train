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


def fetch_series(symbol: str, query: str | None = None, *, client: httpx.Client | None = None,
                 today: date | None = None) -> SourceSeries:
    """One point: posts in the last-day search window, dated the last completed UTC day."""
    today = today or datetime.now(timezone.utc).date()
    if not _has_keys():
        return SourceSeries(SOURCE, symbol, [], "unavailable", "no reddit credentials")
    own = client is None
    client = client or httpx.Client()
    try:
        token = reddit_adapter._get_access_token(client)
        if not token:
            return SourceSeries(SOURCE, symbol, [], "unavailable", "token unavailable")
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
