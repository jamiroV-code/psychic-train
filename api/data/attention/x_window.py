"""SPEC AC42, Annex A.1b point 3: the X query and its exact UTC-day window, Latest order, paging stop. Pure; no network.

The window is written in the query either as `since_time:<epoch> until_time:<epoch>` or as UTC dates
`since:D until:D+1` (until exclusive), chosen by `x_window_syntax` because the owner probe P-X9 decides which one X
honours (the library passes the query through unchanged). Whatever the syntax, a tweet is counted only when its own
timestamp is inside [D 00:00, D+1 00:00) UTC. Reads use the Latest product only: the density estimate needs tweets
in time order, and Top is an engagement-ranked sample.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from api.data.attention import density
from api.data.attention.web_queries import X_WINDOW_SYNTAXES, Queries, valid_lang

LATEST = "Latest"
PAGE_ENTRIES = 20  # entries the library asks for per search page
COMPLETE_STOPS = ("window_start", "cursor_exhausted")  # every tweet of the day was read: the count is exact
STALLED = "cursor_stalled"  # the library stopped without proof that the cursor ran out: never exact
QUERY_FILTERS = "-filter:replies -filter:retweets"


def _utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return ts.astimezone(timezone.utc)


def window_operator(day: date, syntax: str) -> str:
    start, end = density.window(day)
    if syntax == "since_time":
        return f"since_time:{int(start.timestamp())} until_time:{int(end.timestamp())}"
    if syntax == "date":
        return f"since:{day.isoformat()} until:{(day + timedelta(days=1)).isoformat()}"
    raise ValueError(f"window syntax must be one of {', '.join(X_WINDOW_SYNTAXES)}")


def build_query(terms: str, day: date, *, syntax: str, lang: str) -> str:
    """Coin terms, the language policy (empty means any), no replies or retweets, the UTC-day window."""
    if not valid_lang(lang):
        raise ValueError("lang must be a 2-3 letter code or empty")
    parts = [terms] + ([f"lang:{lang}"] if lang else []) + [QUERY_FILTERS, window_operator(day, syntax)]
    return " ".join(parts)


def coin_terms(q: Queries, symbol: str) -> str | None:
    """The cashtag first, then the name; None when the coin is ambiguous for X or has no entry."""
    entry = q.coins.get(symbol)
    if entry is None or symbol in q.ambiguous["xsearch_web"]:
        return None
    name = entry["name"]
    if entry.get("cashtag_only") or name.upper() == symbol:
        return f'"${symbol}"'
    return f'("${symbol}" OR "{name}")'


def search_kv(product: str = LATEST) -> dict:
    """The only search product the reader may ask for."""
    if product != LATEST:
        raise ValueError("only the Latest product is allowed")
    return {"product": LATEST}


def in_window(ts: datetime, day: date) -> bool:
    start, end = density.window(day)
    return start <= _utc(ts) < end


def cursor_end(entry_ids, *, seen: set, last_entries: int | None, page_size: int) -> str | None:
    """Whether a page ends the cursor: None (a page of new entries), `cursor_exhausted` or `cursor_stalled`.

    The library stops silently both when the cursor runs out and when it stalls (no new cursor, or ids it has
    already returned), so an empty page proves exhaustion only when the last non-empty page was SHORT (fewer
    than `page_size` entries) or there was none. A page that repeats an id already read is a stall.
    """
    ids = set(entry_ids)
    if ids & seen:
        return STALLED
    if ids:
        return None
    return "cursor_exhausted" if last_entries is None or last_entries < page_size else STALLED


def stop_reason(*, pages: int, entries_read: int, oldest_read: datetime | None, day: date, sample_n: int,
                page_cap: int, exhausted: bool = False, stalled: bool = False) -> str | None:
    """Why paging stops after `pages` pages, or None to read the next page.

    The window start wins over the sample size: once a read tweet is older than the window start every tweet of
    the day has been read, so the count is exact. An exhausted cursor (see `cursor_end`) means the same; a stalled
    one does not. Entries read
    while every read tweet is still at or after the window end never fill the sample: paging goes on to the page
    cap.
    """
    start, end = density.window(day)
    if oldest_read is not None and _utc(oldest_read) < start:
        return "window_start"
    if exhausted:
        return "cursor_exhausted"
    if stalled:
        return STALLED
    if entries_read >= sample_n and oldest_read is not None and _utc(oldest_read) < end:
        return "sample"
    if pages >= page_cap:
        return "page_cap"
    return None
