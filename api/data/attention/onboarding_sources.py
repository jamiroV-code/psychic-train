"""Onboarding name sources (T223 O4, D-31): fetchers and the pure Trends-suggestion verdict functions.

The verdict functions moved here from `api/scripts/check_trends_keywords.py` so `api.data` never imports
`api.analytics`; the script imports them from here and behaves as before. Every fetcher is fail-closed: it never
raises and reports a fixed state (`ok`, `capped` on HTTP 429, `unavailable`, `none`) with no message text.
Live shapes (suggestion entity types, the REST summary fields) are UNVERIFIED until owner probe P-O0.
"""
from __future__ import annotations

import re
import math
import time
from datetime import date
from urllib.parse import quote

import httpx

from api.data.attention import trends, trends_groups, wikipedia
from api.data.attention import trends_keywords as tk

# Google `type` strings seen in the owner's run of 21-10-26 (T134): Currency, Coin, Chain, Blockchain,
# Blockchain platform, Distributed ledger, Payment network, Cryptocurrency, Cryptocurrency exchange company.
# Generic types (Topic, Software, Company, Website, Computer program) stay out: a hit there needs the owner.
# CRYPTO_SUBSTRINGS may sit anywhere in the type, CRYPTO_WORDS only as whole words ("Tokenization company" is
# out), and CRYPTO_PHRASES only as the whole type ("Chain" is in, "Restaurant chain" and "Internet protocol" out).
CRYPTO_SUBSTRINGS = ("cryptocurrency", "blockchain")
CRYPTO_WORDS = ("token", "coin", "digital currency", "virtual currency")
CRYPTO_PHRASES = ("currency", "chain", "distributed ledger", "payment network", "decentralized finance",
                  "decentralized finance protocol", "decentralized exchange", "defi protocol")
CRYPTO_TYPE_WORDS = CRYPTO_SUBSTRINGS + CRYPTO_WORDS + CRYPTO_PHRASES + (
    "blockchain platform", "cryptocurrency exchange company")
PREFIX_MIN = 4
# What may follow a prefix title in the name: "World" -> Worldcoin, "NEAR" -> NEAR Protocol; never "Bitcoin" ->
# Bitcoin Cash or "Ethereum" -> Ethereum Classic.
PREFIX_SUFFIXES = ("coin", "protocol", "network", "token", "chain", "blockchain", "finance")
# What may follow the name in a longer title: "Kaspa Network"; never "Ethereum Classic", "Bitcoin SV",
# "Sky Mavis", "Sky Protocol" or "Polygon zkEVM" (other coins or companies).
CONTAINED_SUFFIXES = ("coin", "token", "network", "blockchain", "cryptocurrency")
BRACKET_QUALIFIERS = ("crypto", "cryptocurrency", "coin", "token", "blockchain")

WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
WIKI_TIMEOUT_S = 10.0
TEXT_MAX = 600


def _usable(raw) -> list[dict]:
    out = []
    for c in raw if isinstance(raw, list) else []:
        if not isinstance(c, dict):
            continue
        mid, title, type_ = c.get("mid"), c.get("title"), c.get("type")
        if tk.is_valid_topic(mid) and isinstance(title, str) and title.strip() and isinstance(type_, str) and type_.strip():
            out.append({"mid": mid, "title": title[:80], "type": type_[:80]})
    return out


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^0-9a-z]+", " ", text.casefold()).split())


def is_crypto_type(type_: str) -> bool:
    t = _norm(type_)
    return (t in CRYPTO_PHRASES or any(w in t for w in CRYPTO_SUBSTRINGS)
            or any(f" {w} " in f" {t} " for w in CRYPTO_WORDS))


def _exact_match(title: str, name: str) -> bool:
    n = _norm(name)
    return bool(n) and _norm(title) == n


def _contained_match(title: str, name: str) -> bool:
    t, n = _norm(title), _norm(name)
    return bool(n) and t.startswith(n + " ") and t[len(n):].strip() in CONTAINED_SUFFIXES


def _prefix_match(title: str, name: str) -> bool:
    t, n = _norm(title), _norm(name)
    return len(t) >= PREFIX_MIN and n.startswith(t) and n[len(t):].strip() in PREFIX_SUFFIXES


def _bracket_match(title: str, name: str) -> bool:
    m = re.fullmatch(r"(.+?)\s*\(([^()]+)\)", title.strip())
    return bool(m) and _exact_match(m.group(1), name) and _norm(m.group(2)) in BRACKET_QUALIFIERS


def _ticker_match(title: str, symbol: str) -> bool:
    return title.strip().casefold() == symbol.casefold()


# --- fetchers (fail-closed) ---

def _is_429(exc: Exception) -> bool:
    return "429" in trends.error_class(exc)


def fetch_suggestions(trendreq, name: str) -> tuple[list[dict] | None, str]:
    """Google Trends suggestions for `name`: (usable candidates, "ok") or (None, "capped" | "unavailable")."""
    try:
        return _usable(trendreq.suggestions(name)), "ok"
    except Exception as exc:  # noqa: BLE001 - class only, never the message
        return None, "capped" if _is_429(exc) else "unavailable"


def fetch_topic_series(symbol: str, mid: str, trendreq, *, today: date) -> tuple[list | None, str]:
    """The daily series of one topic alone (the same pull and checks as the daily runner): (points, state)."""
    try:
        s = trends.fetch_alone(symbol, mid, trendreq, today=today)
    except Exception:  # noqa: BLE001 - fetch_alone never raises; belt and braces
        return None, "unavailable"
    if s.state == "capped":
        return None, "capped"
    return (list(s.points), "ok") if s.state == "ok" else (None, s.state)


def identity(points: list, volume, *, min_days: int = trends_groups.IDENTITY_MIN_DAYS) -> tuple[float | None, int]:
    """Reuse the campaign's smoothing and Pearson math; the onboarding threshold is owner-configured."""
    if not points:
        return None, 0
    vol = {d: math.log1p(v) for d, v in volume or []
           if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0}
    smoothed = trends_groups.smooth([float(v) for _, v in points])
    dates = [d for d, _ in points][trends_groups.SMOOTH_DAYS - 1:]
    pairs = [(value, vol[day]) for value, day in zip(smoothed, dates) if day in vol]
    count = len(pairs)
    return (trends_groups.pearson([a for a, _ in pairs], [b for _, b in pairs])
            if count >= min_days else None), count


def fetch_wiki_page(title: str, *, client: httpx.Client) -> tuple[dict | None, str]:
    """REST summary of `title`, redirects followed: ({canonical, type, description, extract}, "ok"),
    (None, "none") on 404, (None, "capped") on 429, (None, "unavailable") otherwise."""
    url = WIKI_SUMMARY_URL.format(title=quote(title.replace(" ", "_"), safe=""))
    try:
        resp = client.get(url, headers={"User-Agent": wikipedia.USER_AGENT}, timeout=WIKI_TIMEOUT_S,
                          follow_redirects=True)
        if resp.status_code == 404:
            return None, "none"
        if resp.status_code == 429:
            return None, "capped"
        if resp.status_code != 200:
            return None, "unavailable"
        body = resp.json()
        titles = body.get("titles") if isinstance(body.get("titles"), dict) else {}
        canonical = titles.get("normalized") or titles.get("canonical") or body.get("title") or ""
        return {"canonical": str(canonical).replace("_", " ")[:200], "type": str(body.get("type") or "other"),
                "description": str(body.get("description") or "")[:TEXT_MAX],
                "extract": str(body.get("extract") or "")[:TEXT_MAX]}, "ok"
    except Exception:  # noqa: BLE001 - fail closed
        return None, "unavailable"


def fetch_pageview_days(symbol: str, title: str, *, client: httpx.Client, today: date, sleep=time.sleep) -> tuple[int, str]:
    """How many daily pageview points the article has (0 when none): (days, state)."""
    s = wikipedia.fetch_series(symbol, title, client=client, today=today, sleep=sleep)
    if s.state == "capped":
        return 0, "capped"
    return len(s.points), "ok" if s.points else s.state
