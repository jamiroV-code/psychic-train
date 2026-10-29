"""SPEC AC43, AC44, Annex A.1b point 2: X post-filters, exclusion counts and quality metrics. Pure; no network.

The query is only a candidate generator; a tweet is COUNTED when it passes every filter below, in this order, and
an excluded tweet is counted once under the first reason that applies: outside the UTC-day window, retweet, reply
(both are already excluded in the query and re-checked on the fields), language, placeholder user, protected
user, young account, low followers, cashtag spam, no coin match, duplicate text, per-author cap.

Coin match: the tweet's `cashtags` field holds the coin (the library's entries carry no `$`: strip it and
case-fold), or the coin's full name appears as a word. For the word-like tickers in `NAME_ONLY` the bare ticker
word never matches, so a name that only repeats the ticker does not count.

`Tweet` and `XUser` are this module's own records; the X reader (W8d2) maps the library's objects onto them.
"""
from __future__ import annotations

import math
import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from api.data.attention import x_window
from api.data.attention.web_queries import CollectorConfig, valid_lang

NAME_ONLY = frozenset({"ETC", "LINK", "NEAR", "HYPE", "PI", "PUMP", "GT", "CC"})
AUTHOR_CAP = 3
ENGAGEMENT_SOURCE = "xsearch_engagement"  # stored apart from `xsearch_web`; Discovery does not read it
EXCLUSION_REASONS = ("not_in_window", "retweet", "reply", "lang", "placeholder", "protected", "young_account",
                     "low_followers", "cashtag_spam", "no_coin_match", "name_only_no_match", "duplicate_text",
                     "author_cap")


@dataclass(frozen=True)
class XUser:
    id: int
    created: datetime
    followers: int | None  # None when the library omits the count; never read as 0
    statuses: int | None
    profile_image_url: str
    protected: bool = False


@dataclass(frozen=True)
class Tweet:
    id: int
    date: datetime
    text: str
    user: XUser
    lang: str
    cashtags: tuple[str, ...] = ()
    retweeted_id: int | None = None
    reply_to_id: int | None = None
    like: int | None = 0  # engagement counts are None when missing; never read as 0
    reply: int | None = 0
    quote: int | None = 0
    retweet: int | None = 0
    views: int | None = None  # missing on some tweets; never read as 0


@dataclass(frozen=True)
class Coin:
    symbol: str
    name: str


@dataclass(frozen=True)
class FilterPolicy:
    lang: str = "en"  # empty means any language
    min_account_age_days: int = 30
    min_followers: int = 10
    max_cashtags: int = 5

    @classmethod
    def from_config(cls, config: CollectorConfig, coin_entry: dict | None = None) -> FilterPolicy:
        lang = (coin_entry or {}).get("x_lang", config.x_lang)
        if not valid_lang(lang):
            raise ValueError("bad x_lang")
        return cls(lang, config.x_min_account_age_days, config.x_min_followers, config.x_max_cashtags)


@dataclass(frozen=True)
class FilterResult:
    counted: list[Tweet]
    exclusions: dict[str, int] = field(default_factory=dict)
    unique_authors: int = 0
    top_author_share: float | None = None

    def as_evidence(self) -> dict:
        return {"exclusions": dict(self.exclusions), "unique_authors": self.unique_authors,
                "top_author_share": self.top_author_share}


def cashtag_matches(cashtags, symbol: str) -> bool:
    want = symbol.casefold()
    return any(str(c).lstrip("$").casefold() == want for c in cashtags)


def _word(text: str, phrase: str) -> bool:
    return re.search(r"(?<![A-Za-z0-9])" + re.escape(phrase) + r"(?![A-Za-z0-9])", text, re.IGNORECASE) is not None


def coin_matches(tweet: Tweet, coin: Coin) -> bool:
    if cashtag_matches(tweet.cashtags, coin.symbol):
        return True
    if coin.symbol in NAME_ONLY and coin.name.casefold() == coin.symbol.casefold():
        return False  # the name is the bare ticker word, which never counts for these coins
    return _word(tweet.text, coin.name)


def is_placeholder(user: XUser) -> bool:
    """The library's stand-in for a missing user: empty profile image and zero counts. An unknown count cannot
    rule it out, so it counts as possibly zero here."""
    return not user.profile_image_url and user.followers in (0, None) and user.statuses in (0, None)


def _text_key(text: str) -> str:
    return " ".join(text.split()).casefold()


def _reason(t: Tweet, coin: Coin, day: date, policy: FilterPolicy) -> str | None:
    """The first exclusion that applies, or None when the tweet passes the per-tweet filters."""
    if not x_window.in_window(t.date, day):
        return "not_in_window"
    if t.retweeted_id is not None:
        return "retweet"
    if t.reply_to_id is not None:
        return "reply"
    if policy.lang and (t.lang or "").casefold() != policy.lang:
        return "lang"
    if is_placeholder(t.user):
        return "placeholder"
    if t.user.protected:
        return "protected"
    if t.date - t.user.created < timedelta(days=policy.min_account_age_days):
        return "young_account"
    if t.user.followers is None or t.user.followers < policy.min_followers:  # unknown never clears the bar
        return "low_followers"
    if len(t.cashtags) > policy.max_cashtags:
        return "cashtag_spam"
    if not coin_matches(t, coin):
        return "name_only_no_match" if coin.symbol in NAME_ONLY else "no_coin_match"
    return None


def filter_tweets(tweets, coin: Coin, day: date, policy: FilterPolicy) -> FilterResult:
    """Counted tweets (input order kept, newest first as read), exclusions by reason and author metrics."""
    excl = dict.fromkeys(EXCLUSION_REASONS, 0)
    seen: set[str] = set()
    per_author: Counter = Counter()
    counted = []
    for t in tweets:
        reason = _reason(t, coin, day, policy)
        if reason is None:
            key = _text_key(t.text)
            if key in seen:
                reason = "duplicate_text"
            elif per_author[t.user.id] >= AUTHOR_CAP:
                reason = "author_cap"
            else:
                seen.add(key)
                per_author[t.user.id] += 1
                counted.append(t)
                continue
        excl[reason] += 1
    top = max(per_author.values()) / len(counted) if counted else None
    return FilterResult(counted, excl, len(per_author), top)


def engagement_sum(tweets) -> float:
    """log1p(likes) + log1p(replies) + log1p(quotes) + log1p(retweets) over counted tweets; views are not in it.
    A missing (None) count adds no term."""
    return float(sum(math.log1p(n) for t in tweets for n in (t.like, t.reply, t.quote, t.retweet) if n is not None))


def median_views(tweets) -> float | None:
    """Median over the tweets that carry a view count; None when none does (a missing count is never 0)."""
    views = [t.views for t in tweets if t.views is not None]
    return statistics.median(views) if views else None


def read_age_hours(tweets, now: datetime) -> float | None:
    """Mean age of the counted tweets at read time, in hours (engagement keeps growing after posting)."""
    if not tweets:
        return None
    return sum((now - t.date).total_seconds() for t in tweets) / len(tweets) / 3600.0
