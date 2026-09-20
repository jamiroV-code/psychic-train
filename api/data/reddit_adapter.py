"""Reddit mention-count proxy adapter (item 48).

Free-tier Reddit API via an OAuth client-credentials grant (app-only,
read-only search — no user context needed). Security Posture: credential
names only are documented, never values, server-side env vars only,
`web/` never receives or proxies them — `REDDIT_CLIENT_ID` /
`REDDIT_CLIENT_SECRET`. If either is unset, this adapter treats every
fetch as an immediate `unavailable` (never raises) rather than attempting a
call Reddit's search endpoint does not support anonymously.

Same failure discipline as the other adapters (typed result, explicit
`unavailable`/`stale`, never raises past this boundary) — Reddit's API is
not confirmed dead the way `pytrends` is (Risk Prediction #2a names
`pytrends` specifically), so no presumed-dead escalation is implemented
here; a single failed call and a long-unavailable source are both surfaced
the same way (`unavailable`/`stale`), matching the other non-pytrends
sources.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

import httpx

from api.data import cache

REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
REDDIT_SEARCH_URL = "https://oauth.reddit.com/r/{subreddit}/search"
USER_AGENT = "momentum-screener/0.1 (personal research tool)"
DEFAULT_SUBREDDIT = "CryptoCurrency"
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 1.0
TIMEOUT_SECONDS = 10.0
STALENESS_HOURS = 24

Status = Literal["ok", "unavailable", "stale"]


@dataclass
class MentionResult:
    query: str
    mention_count: float | None  # matching posts in the last-day search window
    as_of: str | None
    status: Status


def _get_access_token(client: httpx.Client) -> str | None:
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
    try:
        resp = client.post(
            REDDIT_TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception:
        return None


def _fetch_with_backoff(client: httpx.Client, subreddit: str, query: str, token: str) -> dict | None:
    url = REDDIT_SEARCH_URL.format(subreddit=subreddit)
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.get(
                url,
                params={"q": query, "restrict_sr": "true", "t": "day", "limit": "100"},
                headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT},
                timeout=TIMEOUT_SECONDS,
            )
            if resp.status_code == 429:
                if attempt == MAX_RETRIES - 1:
                    return None
                time.sleep(BACKOFF_BASE_SECONDS * (2**attempt))
                continue
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException:
            return None
        except httpx.HTTPStatusError:
            return None
        except httpx.NetworkError:
            return None
        except Exception:
            return None
    return None


def _hours_since(date_str: str) -> float | None:
    try:
        then = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
    return (datetime.now(timezone.utc) - then).total_seconds() / 3600.0


def fetch_mentions(
    subreddit_or_keyword: str, subreddit: str = DEFAULT_SUBREDDIT, client: httpx.Client | None = None
) -> MentionResult:
    """Fetch (or serve cached) a 1-day mention count for
    `subreddit_or_keyword` within `subreddit`. Missing credentials, a
    request failure, or a malformed payload all degrade to the same
    cached-fallback path — never raises past this boundary.
    """
    cache.bootstrap_cache_dirs()
    own_client = client is None
    client = client or httpx.Client()
    raw = None
    try:
        token = _get_access_token(client)
        if token is not None:
            raw = _fetch_with_backoff(client, subreddit, subreddit_or_keyword, token)
    finally:
        if own_client:
            client.close()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if raw is not None:
        try:
            count = float(len(raw.get("data", {}).get("children", [])))
        except Exception:
            count = None
        if count is not None:
            cache.write_narrative_point("reddit", subreddit_or_keyword, today, count)
            return MentionResult(query=subreddit_or_keyword, mention_count=count, as_of=today, status="ok")

    history = cache.read_narrative_series("reddit", subreddit_or_keyword)
    if history is None or history.empty:
        return MentionResult(query=subreddit_or_keyword, mention_count=None, as_of=None, status="unavailable")

    last_row = history.sort_values("date").iloc[-1]
    age_hours = _hours_since(str(last_row["date"]))
    status: Status = "ok" if (age_hours is not None and age_hours <= STALENESS_HOURS) else "stale"
    return MentionResult(
        query=subreddit_or_keyword,
        mention_count=float(last_row["raw_value"]),
        as_of=str(last_row["date"]),
        status=status,
    )
