"""SPEC Annex A.2b point 3 and 4, AC31, AC32, AC35: Reddit mention and engagement metrics. Pure; no network.

- Matching: a text mentions a coin when it holds the cashtag (`$SOL`, any case) or the coin's full name as a word
  (any case), or, unless the coin is `name_only`, the bare ticker as an upper-case word. The eight word-like
  tickers ETC, LINK, NEAR, HYPE, PI, PUMP, GT and CC are `name_only` in the query file. Coins on the Reddit
  ambiguity list are never matched (they are not in `coin_terms`).
- Mentions per coin-day: distinct Reddit ids created in the UTC day, at most `reddit_author_cap` per author hash
  (an item without an author hash counts against one shared bucket). Unique authors: distinct hashes among them.
- Volume honesty: a coin-day below `reddit_min_mentions` is `low_volume`; the change is missing when the recent or
  the base window mean is below it, computed at exactly the minimum.
- Engagement (settled items only): log1p(max(score, 0)), plus log1p(num_comments) for posts; a comment's
  `num_comments` is its parent post's and is never added. Controversial posts (upvote_ratio below 0.3 and
  ups / upvote_ratio at least 10) leave the sum and form their own count. Items deleted later or with a
  `removal_type` leave the settled counts; the provisional mention count keeps them.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

from api.data.attention import density
from api.data.attention.web_queries import Queries

CONTROVERSY_RATIO = 0.3
CONTROVERSY_MIN_VOTES = 10


@dataclass(frozen=True)
class CoinTerms:
    symbol: str
    name: str
    name_only: bool


@dataclass(frozen=True)
class Item:
    """One ledger item as the metrics see it; votes are None until the archive enrichment (W8c3) adds them."""
    id: str
    author_hash: str | None
    created: datetime
    coins: tuple[str, ...]
    score: float | None = None
    num_comments: int | None = None
    upvote_ratio: float | None = None
    ups: float | None = None
    deleted_later: bool = False
    removal_type: str | None = None

    @property
    def is_post(self) -> bool:
        return self.id.startswith("t3_")


@dataclass(frozen=True)
class MentionDay:
    mentions: int
    unique_authors: int
    low_volume: bool


def coin_terms(q: Queries) -> list[CoinTerms]:
    """Matching terms for every coin in the query file except the Reddit ambiguity list."""
    return [CoinTerms(sym, e["name"], bool(e.get("name_only", False))) for sym, e in sorted(q.coins.items())
            if sym not in q.ambiguous["reddit_web"]]


def _word(text: str) -> str:
    return r"(?<![A-Za-z0-9])" + re.escape(text) + r"(?![A-Za-z0-9])"


def _patterns(coin: CoinTerms) -> list[re.Pattern]:
    pats = [re.compile(r"(?<![A-Za-z0-9$])\$" + re.escape(coin.symbol) + r"(?![A-Za-z0-9])", re.IGNORECASE),
            re.compile(_word(coin.name), re.IGNORECASE)]
    if not coin.name_only:
        pats.append(re.compile(_word(coin.symbol)))
    return pats


def mentions(text: str, coin: CoinTerms) -> bool:
    return any(p.search(text) for p in _patterns(coin))


def matched_coins(text: str, coins: Iterable[CoinTerms]) -> tuple[str, ...]:
    return tuple(sorted({c.symbol for c in coins if mentions(text, c)}))


def _in_day(item: Item, day: date) -> bool:
    start, end = density.window(day)
    return start <= item.created < end


def counted(items: Iterable[Item], symbol: str, day: date, *, author_cap: int) -> list[Item]:
    """The coin-day's counted items: distinct ids in the day, oldest first, at most `author_cap` per author."""
    seen: set[str] = set()
    pool = []
    for it in sorted(items, key=lambda i: (i.created, i.id)):
        if it.id in seen or symbol not in it.coins or not _in_day(it, day):
            continue
        seen.add(it.id)
        pool.append(it)
    per_author: Counter = Counter()
    out = []
    for it in pool:
        if per_author[it.author_hash] >= author_cap:
            continue
        per_author[it.author_hash] += 1
        out.append(it)
    return out


def mention_day(items: Iterable[Item], symbol: str, day: date, *, author_cap: int, min_mentions: int) -> MentionDay:
    kept = counted(items, symbol, day, author_cap=author_cap)
    authors = {i.author_hash for i in kept if i.author_hash is not None}
    return MentionDay(len(kept), len(authors), len(kept) < min_mentions)


def mention_change(recent: list[float], base: list[float], *, min_mentions: int) -> float | None:
    """Percent change of the recent window mean against the base window mean; None (missing) on low volume."""
    if not recent or not base:
        return None
    r, b = sum(recent) / len(recent), sum(base) / len(base)
    if r < min_mentions or b < min_mentions:
        return None
    return (r / b - 1.0) * 100.0


def is_controversial(item: Item) -> bool:
    if not item.is_post or item.upvote_ratio is None or item.ups is None or item.upvote_ratio <= 0:
        return False
    return item.upvote_ratio < CONTROVERSY_RATIO and item.ups / item.upvote_ratio >= CONTROVERSY_MIN_VOTES


def settled(items: Iterable[Item]) -> list[Item]:
    return [i for i in items if not i.deleted_later and not i.removal_type]


def engagement_weighted(items: Iterable[Item]) -> float | None:
    """Engagement-weighted mentions over settled items with a score; None when no item has one (never 0)."""
    total, any_score = 0.0, False
    for it in settled(items):
        if it.score is None or is_controversial(it):
            continue
        any_score = True
        total += math.log1p(max(float(it.score), 0.0))
        if it.is_post and it.num_comments is not None:
            total += math.log1p(max(int(it.num_comments), 0))
    return total if any_score else None


def controversy_count(items: Iterable[Item]) -> int:
    return sum(1 for i in settled(items) if is_controversial(i))
