"""Google Trends keyword file: loader and validator (T100a).

One entry per placed coin: exactly one of `topic` (a Trends topic id), `term` (a safe search term) or
`"no-keyword": true` (with a `note`). `_anchor` is the shared scale term, not a coin. Pure: no network,
no pytrends, no import from api.analytics (the caller passes the placed or Discovery-eligible symbols).

T180: `keyword_status` is the one rule for whether a coin has a usable keyword (the daily runner and the
Sources payload both use it); `guard_gaps` and `coverage` report the coins without one.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from api.data.attention import trends

KEYWORDS_PATH = Path(__file__).resolve().parents[1] / "trends_keywords.json"
ANCHOR_KEY = "_anchor"
BAD_FILE_REASON = "bad keyword file"
# Same pattern as api/analytics/attention/narratives.py SYMBOL_RE (a test keeps them equal).
SYMBOL_RE = re.compile(r"[A-Z0-9_]{1,24}")
TOPIC_RE = re.compile(r"^/(m|g)/[A-Za-z0-9_]+$")
TERM_RE = re.compile(r"[A-Za-z0-9 .'&-]{2,40}")
LABEL_MAX = 60
NOTE_MAX = 200
KIND_FIELDS = ("topic", "term", "no-keyword")
ALLOWED_FIELDS = frozenset(KIND_FIELDS + ("label", "note"))
# Tickers nobody has identified yet (T160): they keep a no-keyword entry until the owner names the coin. The
# guard test fails when one gains a topic or term, so this list only shrinks; every other Discovery coin needs one.
# T192: the owner named all seven, so it is empty now; a future unidentified ticker is added here on purpose.
UNIDENTIFIED_TICKERS: frozenset[str] = frozenset()
MISSING_STATUSES = ("no-entry", "no-keyword", "skipped-unqualified", "bad-file")


class KeywordFileError(ValueError):
    pass


def is_valid_topic(value) -> bool:
    return isinstance(value, str) and TOPIC_RE.fullmatch(value) is not None


def is_valid_term(value) -> bool:
    return isinstance(value, str) and TERM_RE.fullmatch(value) is not None and value == value.strip()


def is_valid_label(value) -> bool:
    return (isinstance(value, str) and bool(value.strip()) and len(value) <= LABEL_MAX
            and value.isprintable())


def _text_ok(value, limit: int) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= limit and value.isprintable()


def _check_entry(name: str, entry, *, anchor: bool) -> dict:
    if not isinstance(entry, dict):
        raise KeywordFileError(f"keywords: {name} must be an object")
    unknown = sorted(set(entry) - ALLOWED_FIELDS)
    if unknown:
        raise KeywordFileError(f"keywords: {name} has unknown field(s); allowed: {', '.join(sorted(ALLOWED_FIELDS))}")
    kinds = [f for f in KIND_FIELDS if f in entry]
    if len(kinds) != 1:
        raise KeywordFileError(f"keywords: {name} needs exactly one of topic, term, no-keyword")
    kind = kinds[0]
    if kind == "topic" and not is_valid_topic(entry["topic"]):
        raise KeywordFileError(f"keywords: {name} topic must match {TOPIC_RE.pattern}")
    if kind == "term" and not is_valid_term(entry["term"]):
        raise KeywordFileError(f"keywords: {name} term must be 2-40 safe characters (letters, digits, space . ' & -),"
                               " no leading or trailing space")
    if kind == "no-keyword":
        if anchor:
            raise KeywordFileError(f"keywords: {name} must be a topic or a term")
        if entry["no-keyword"] is not True:
            raise KeywordFileError(f"keywords: {name} no-keyword must be true")
        if not _text_ok(entry.get("note"), NOTE_MAX):
            raise KeywordFileError(f"keywords: {name} no-keyword needs a non-empty note")
    if not is_valid_label(entry.get("label")):
        raise KeywordFileError(f"keywords: {name} label must be 1-{LABEL_MAX} printable characters")
    if "note" in entry and not _text_ok(entry["note"], NOTE_MAX):
        raise KeywordFileError(f"keywords: {name} note must be 1-{NOTE_MAX} printable characters")
    return dict(entry)


def validate(doc, placed_symbols=None) -> dict:
    """Return {"entries", "anchor", "warnings"}; raise KeywordFileError on any rule break."""
    if not isinstance(doc, dict):
        raise KeywordFileError("keywords: file must be a JSON object")
    if ANCHOR_KEY not in doc:
        raise KeywordFileError(f"keywords: {ANCHOR_KEY} is required")
    anchor = _check_entry(ANCHOR_KEY, doc[ANCHOR_KEY], anchor=True)
    entries: dict[str, dict] = {}
    topics: dict[str, str] = {}
    terms: dict[str, str] = {}
    for key, entry in doc.items():
        if key == ANCHOR_KEY:
            continue
        if not isinstance(key, str) or not SYMBOL_RE.fullmatch(key):
            raise KeywordFileError(f"keywords: key {str(key)[:30]!r} must be {ANCHOR_KEY} or match {SYMBOL_RE.pattern}")
        e = _check_entry(key, entry, anchor=False)
        if "topic" in e:
            if e["topic"] in topics:
                raise KeywordFileError(f"keywords: {key} topic must be unique (also used by {topics[e['topic']]})")
            topics[e["topic"]] = key
        if "term" in e:
            folded = e["term"].casefold()
            if folded in terms:
                raise KeywordFileError(f"keywords: {key} term must be unique, case-insensitive (also used by {terms[folded]})")
            terms[folded] = key
        entries[key] = e
    warnings: list[str] = []
    if placed_symbols is not None:
        placed = set(placed_symbols)
        missing = sorted(placed - set(entries))
        if missing:
            raise KeywordFileError(f"keywords: {len(missing)} placed coin(s) have no entry: {', '.join(missing[:5])}")
        not_placed = sorted(set(entries) - placed)
        warnings = [f"keywords: {s} is not a placed coin" for s in not_placed]
    else:
        not_placed = []
    return {"entries": entries, "anchor": anchor, "warnings": warnings, "not_placed": not_placed}


@dataclass
class KeywordMap:
    entries: dict[str, dict]
    anchor: dict
    warnings: list[str] = field(default_factory=list)
    not_placed: list[str] = field(default_factory=list)   # keys outside the placed symbols passed to load

    def keyword_for(self, symbol: str) -> str | None:
        e = self.entries.get(symbol)
        if not e:
            return None
        return e.get("topic") or e.get("term")

    def keyword_symbols(self) -> list[str]:
        return [s for s in self.entries if self.keyword_for(s)]

    def anchor_keyword(self) -> str:
        return self.anchor.get("topic") or self.anchor["term"]


def _no_duplicate_keys(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise KeywordFileError(f"keywords: duplicate key {str(key)[:30]!r}")
        seen[key] = value
    return seen


def load(path: Path | None = None, placed_symbols=None) -> KeywordMap:
    text = (path or KEYWORDS_PATH).read_bytes().decode("utf-8")
    out = validate(json.loads(text, object_pairs_hook=_no_duplicate_keys), placed_symbols)
    return KeywordMap(**out)


def safe_load(path: Path | None = None, placed_symbols=None) -> tuple[KeywordMap | None, str]:
    """Never raises: (map, "") or (None, "bad keyword file"). The reason carries no path or content."""
    try:
        return load(path, placed_symbols), ""
    except Exception:  # noqa: BLE001 - any failure is the same fixed reason
        return None, BAD_FILE_REASON


def keyword_status(km: KeywordMap | None, symbol: str) -> str:
    """"topic" or "term" when the runner pulls the coin, else one of MISSING_STATUSES. A name-risk symbol's bare
    (unqualified) term is not pulled."""
    if km is None:
        return "bad-file"
    e = km.entries.get(symbol)
    if e is None:
        return "no-entry"
    if "topic" in e:
        return "topic"
    if "term" not in e:
        return "no-keyword"
    if symbol in trends.NAME_RISK_SYMBOLS and not trends.is_qualified_term(e["term"]):
        return "skipped-unqualified"
    return "term"


def guard_gaps(km: KeywordMap, eligible) -> dict[str, list[str]]:
    """Eligible coins without a usable keyword, by status, in `eligible` order; an UNIDENTIFIED_TICKERS coin may
    stay no-keyword. `allowlist-has-keyword`: allowlisted coins that now have one (drop them from the list)."""
    gaps: dict[str, list[str]] = {"no-entry": [], "no-keyword": [], "skipped-unqualified": []}
    for s in dict.fromkeys(eligible):
        st = keyword_status(km, s)
        if st in gaps and not (st == "no-keyword" and s in UNIDENTIFIED_TICKERS):
            gaps[st].append(s)
    gaps["allowlist-has-keyword"] = sorted(s for s in UNIDENTIFIED_TICKERS
                                           if keyword_status(km, s) in ("topic", "term"))
    return gaps


@dataclass
class Coverage:
    eligible: int
    with_keyword: int
    counts: dict[str, int]                 # topic, term, keyword-missing
    missing: list[tuple[str, str]]         # (symbol, status) in eligible order


def coverage(km: KeywordMap | None, eligible) -> Coverage:
    """How many eligible coins have a usable keyword; a no-keyword entry counts as missing, not as topic/term."""
    counts = {"topic": 0, "term": 0, "keyword-missing": 0}
    missing = []
    symbols = list(dict.fromkeys(eligible))
    for s in symbols:
        st = keyword_status(km, s)
        if st in ("topic", "term"):
            counts[st] += 1
        else:
            counts["keyword-missing"] += 1
            missing.append((s, st))
    return Coverage(len(symbols), counts["topic"] + counts["term"], counts, missing)


def gap_report(km: KeywordMap | None, eligible) -> str:
    """One non-failing report line for the live eligible set (the guard test checks a pinned set)."""
    cov = coverage(km, eligible)
    line = f"trends keyword: {cov.with_keyword} of {cov.eligible} eligible coins"
    if cov.missing:
        line += "; no keyword: " + ", ".join(f"{s} ({st})" for s, st in cov.missing)
    return line
