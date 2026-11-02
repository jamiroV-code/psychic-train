"""Onboarding name resolver: pure checks (T223 O4, D-31). No I/O, no network.

Each check returns a `Verdict`: `applied` (goes to the bot overlay), `pending` (waits for the owner with
evidence), `none` (no candidate: a reason, and the signal stays missing, never 0), or `candidate` (an internal
step of the Trends rule). Only the STRICT rules apply anything:
- Trends: exactly one suggestion whose title equals the name and whose type is a cryptocurrency type, a topic used
  by no other symbol nor the anchor, a daily series that passes the runner's checks, and a stored CoinGecko volume
  series that overlaps at least `identity_min_days` days and correlates at least `identity_min_corr`. Lead rules
  (ticker title, bracket, contained, prefix), several equal entities, a name guessed from the id and a short
  volume history all go to pending. No automatic term is ever proposed, so an `_ambiguous` coin gets none.
- Wikipedia: the REST page title equals the candidate (no redirect), not a disambiguation page, the name or symbol in
  the first sentence, whole-word crypto terms, a title not assigned to another symbol, enough pageview days.
- Reddit/X: always `cashtag_only`; a name that fails the query-file name pattern waits.
"""
from __future__ import annotations

import re
import math
from dataclasses import dataclass, field

from api.data.attention import onboarding_sources as src
from api.data.attention import trends_keywords as tk
from api.data.attention import web_queries

CRYPTO_TERMS = re.compile(r"\b(cryptocurrenc(?:y|ies)|blockchains?|tokens?|coins?|protocols?|decentrali[sz]ed|"
                          r"networks?|crypto)\b", re.I)


@dataclass
class Verdict:
    action: str                     # applied | pending | none | candidate
    value: dict | None = None
    reason: str = ""
    evidence: dict = field(default_factory=dict)


def _norm_title(t: str) -> str:
    t = " ".join(str(t).replace("_", " ").split())
    return t[:1].upper() + t[1:]


def _word(text: str, word: str) -> bool:
    return bool(word) and re.search(rf"(?<![0-9a-z]){re.escape(word.casefold())}(?![0-9a-z])", text.casefold()) is not None


def first_sentence(extract: str) -> str:
    m = re.match(r"(.+?[.!?])(\s|$)", extract.strip(), re.S)
    return m.group(1) if m else extract.strip()


# --- Wikipedia ---

def wiki_verdict(symbol: str, name: str | None, page: dict | None, *, taken: dict[str, str], pageview_days: int,
                 min_days: int) -> Verdict:
    """`taken`: casefolded title -> symbol over the owner file and the overlay."""
    if not name:
        return Verdict("none", reason="no name in the snapshot")
    if page is None:
        return Verdict("none", reason="no article for the name")
    canonical, cand = _norm_title(page.get("canonical", "")), _norm_title(name)
    ev = {"candidate": cand, "title": canonical, "type": page.get("type"),
          "first_sentence": first_sentence(page.get("extract", ""))[:200]}
    if page.get("type") == "disambiguation":
        return Verdict("pending", reason="disambiguation page", evidence=ev)
    if page.get("type") != "standard":
        return Verdict("none", reason="not an article", evidence=ev)
    if canonical != cand:
        return Verdict("pending", reason="redirect to another title", evidence=ev)
    if not (_word(ev["first_sentence"], name) or _word(ev["first_sentence"], symbol)):
        return Verdict("pending", reason="name not in the first sentence", evidence=ev)
    if not CRYPTO_TERMS.search(f"{page.get('description', '')} {page.get('extract', '')}"):
        return Verdict("pending", reason="no crypto terms", evidence=ev)
    other = taken.get(canonical.casefold())
    if other and other != symbol:
        return Verdict("pending", reason=f"title already assigned to {other}", evidence=ev)
    if pageview_days < min_days:
        return Verdict("pending", reason=f"pageviews {pageview_days} of {min_days} days", evidence=ev)
    return Verdict("applied", {"title": canonical}, evidence=ev)


def merge_wiki(owner: dict, overlay) -> tuple[dict, list[tuple[str, str]]]:
    """Owner symbol -> title map plus valid overlay titles for symbols the owner file does not list; a title used by
    another symbol (owner or earlier overlay entry) is dropped. Never raises."""
    merged = dict(owner) if isinstance(owner, dict) else {}
    entries = overlay.get("entries") if isinstance(overlay, dict) else None
    if not isinstance(entries, dict):
        return merged, []
    used = {str(t).casefold() for t in merged.values() if t}
    dropped = []
    for sym, raw in entries.items():
        title = raw.get("title") if isinstance(raw, dict) else None
        if not (isinstance(sym, str) and tk.SYMBOL_RE.fullmatch(sym)) or not isinstance(title, str) or not (
                0 < len(title) <= 200 and title.isprintable()) or set(raw) - {"title", "source", "resolved_at"}:
            dropped.append((str(sym)[:24], "invalid entry"))
        elif sym in merged:
            dropped.append((sym, "owner entry wins"))
        elif title.casefold() in used:
            dropped.append((sym, "title already used"))
        else:
            merged[sym] = title
            used.add(title.casefold())
    return merged, dropped


# --- Google Trends ---

def trends_pick(symbol: str, name: str | None, candidates: list[dict] | None, *, taken_topics: set[str],
                name_from_id: bool = False) -> Verdict:
    """First half of the strict rule, from the suggestions alone: `candidate` with the topic, or pending / none."""
    if not name:
        return Verdict("none", reason="no name in the snapshot")
    if not candidates:
        return Verdict("none", reason="no Google entity for the name")
    crypto = [c for c in candidates if src.is_crypto_type(c["type"])]
    exact = [c for c in crypto if src._exact_match(c["title"], name)]
    ev = {"name": name, "candidates": [f"{c['mid']} {c['title']} ({c['type']})" for c in candidates[:5]]}
    if name_from_id:
        return Verdict("pending", reason="name from CoinGecko id", evidence=ev)
    if len(exact) > 1:
        return Verdict("pending", reason="several equally likely entities", evidence=ev)
    if not exact:
        for c in crypto:
            for rule, hit in (("ticker-title", src._ticker_match(c["title"], symbol)),
                              ("bracket", src._bracket_match(c["title"], name)),
                              ("contained", src._contained_match(c["title"], name)),
                              ("prefix", src._prefix_match(c["title"], name))):
                if hit:
                    return Verdict("pending", reason=f"lead only ({rule})", evidence=ev)
        return Verdict("none", reason="no cryptocurrency entity with the exact name", evidence=ev)
    if exact[0]["mid"] in taken_topics:
        return Verdict("pending", reason="topic already used by another symbol", evidence=ev)
    return Verdict("candidate", {"topic": exact[0]["mid"], "label": exact[0]["title"]}, evidence=ev)


def trends_confirm(pick: Verdict, *, series_state: str, corr: float | None, overlap_days: int, settings) -> Verdict:
    """Second half of the strict rule: the topic's daily series and the identity check against stored volume."""
    ev = {**pick.evidence, "series": series_state, "volume_days": overlap_days,
          "correlation": None if corr is None else round(corr, 3)}
    if series_state != "ok":
        return Verdict("pending", reason=f"trends series {series_state}", evidence=ev)
    if overlap_days < settings.identity_min_days:
        return Verdict("pending", reason=f"volume history {overlap_days} of {settings.identity_min_days + src.trends_groups.SMOOTH_DAYS - 1} days",
                       evidence=ev)
    if corr is None or not math.isfinite(corr) or corr <= settings.identity_min_corr:
        return Verdict("pending", reason="does not track this coin's volume", evidence=ev)
    return Verdict("applied", dict(pick.value), evidence=ev)


# --- Reddit / X ---

def reddit_x_verdict(symbol: str, name: str | None) -> Verdict:
    if not name:
        return Verdict("none", reason="no name in the snapshot")
    if not web_queries.NAME_RE.fullmatch(name):
        return Verdict("pending", reason="name not safe for queries", evidence={"name": name[:60]})
    return Verdict("applied", {"name": name, "cashtag_only": True})
