"""Candidate Google Trends term groups per coin (T201) for the owner's `probe_trends --all-eligible` campaign.

Built from repo data only: the coin's keyword entry (topic or term, the baseline) and its names (keyword label,
attention_queries.json display name, CoinGecko id, ticker). Every generated term passes the loader's safe-term check;
a name-risk coin (trends.NAME_RISK_SYMBOLS) only ever gets qualified terms. Pure: no network, no store.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from api.data.attention import trends
from api.data.attention import trends_keywords as tk

# Loader qualifier words, best-fitting first (all are in trends.QUALIFIER_WORDS).
QUALIFIERS = ("crypto", "coin", "token", "protocol", "network", "chain")
MAX_BUNDLE = 3  # terms in the bundle group (pytrends allows 5)
DEFAULT_MAX_GROUPS = 3
MAX_GROUPS = 6
NEEDS_QUALIFIER = "needs qualifier word"
MIN_NAME = 2  # a one-letter name or ticker ("m crypto") matches anything


@dataclass(frozen=True)
class Candidate:
    terms: tuple[str, ...]
    kind: str  # baseline | variant | bundle | bare-name | bare-ticker
    note: str = ""

    @property
    def key(self) -> str:
        return "|".join(self.terms)


def _norm(name) -> str:
    return re.sub(r"\s+", " ", name).strip().lower() if isinstance(name, str) else ""


def _names(symbol: str, label, query_name, coingecko_id) -> list[str]:
    """Label first (owner-curated for Trends), then the display name, the CoinGecko id, the ticker; deduped."""
    cg = coingecko_id.replace("-", " ") if isinstance(coingecko_id, str) else None
    out: list[str] = []
    for raw in (label, query_name, cg, symbol):
        n = _norm(raw)
        if len(n) >= MIN_NAME and n not in out and not all(w in trends.QUALIFIER_WORDS for w in n.split()):
            out.append(n)
    return out


def _variants(names: list[str]) -> list[str]:
    """Qualifier-major: every name with 'crypto', then every name with 'coin', ...; a name that already holds a
    qualifier word is used as is, in the first round."""
    out: list[str] = []
    for i, q in enumerate(QUALIFIERS):
        for n in names:
            if trends.is_qualified_term(n):
                if i == 0:
                    out.append(n)
            else:
                out.append(f"{n} {q}")
    return out


def candidate_groups(symbol: str, entry: dict | None, *, query_name: str | None = None,
                     coingecko_id: str | None = None, max_groups: int = DEFAULT_MAX_GROUPS) -> list[Candidate]:
    """Up to max_groups groups, in test order: the current keyword (baseline), the best single variant, a bundle of
    the current term plus the best variants (at most MAX_BUNDLE terms), the bare name and bare ticker (not for a
    name-risk coin; marked 'needs qualifier word'), then further single variants. Dedupe is case-insensitive."""
    if not 1 <= max_groups <= MAX_GROUPS:
        raise ValueError(f"max_groups must be 1 to {MAX_GROUPS}")
    entry = entry or {}
    current = entry.get("topic") or entry.get("term")
    seen = {current.casefold()} if isinstance(current, str) else set()
    variants: list[str] = []
    for v in _variants(_names(symbol, entry.get("label"), query_name, coingecko_id)):
        if tk.is_valid_term(v) and v.casefold() not in seen:
            seen.add(v.casefold())
            variants.append(v)
    groups: list[Candidate] = []
    if isinstance(current, str) and (tk.is_valid_topic(current) or tk.is_valid_term(current)):
        groups.append(Candidate((current,), "baseline"))
    if variants:
        groups.append(Candidate((variants[0],), "variant"))
    bundle = ([current] if tk.is_valid_term(current) else []) + variants
    if len(bundle) >= 2:
        groups.append(Candidate(tuple(bundle[:MAX_BUNDLE]), "bundle"))
    if symbol not in trends.NAME_RISK_SYMBOLS:
        bare_name = next((n for n in _names("", entry.get("label"), query_name, coingecko_id)
                          if not trends.is_qualified_term(n)), None)
        if bare_name is not None:
            groups.append(Candidate((bare_name,), "bare-name", NEEDS_QUALIFIER))
        groups.append(Candidate((symbol,), "bare-ticker", NEEDS_QUALIFIER))
    groups += [Candidate((v,), "variant") for v in variants[1:]]
    out: list[Candidate] = []
    keys: set[frozenset[str]] = set()
    for g in groups:
        k = frozenset(t.casefold() for t in g.terms)
        if all(tk.is_valid_topic(t) or tk.is_valid_term(t) for t in g.terms) and k not in keys:
            keys.add(k)
            out.append(g)
    return out[:max_groups]
