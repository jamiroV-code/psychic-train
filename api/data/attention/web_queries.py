"""Query terms and the collector config block for the PC-side web sources (`attention_queries.json`). Pure; no network.

The file holds the collector pace and budget values (Locked pacing rules; owner-editable, defaults in
`DEFAULTS`), the X reader keys (SPEC rules 17-20, typed, defaults in `X_DEFAULTS`, a per-coin `x_lang` override), the Reddit subreddit set, per-source ambiguity lists and one display name per narrative coin.
The collected coin set is the placed symbols of `attention_narratives.json` minus that source's ambiguity
list (AC20); widening it is a narratives or query-file change, never code. The file holds no secrets.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1]
QUERIES_PATH = DATA_DIR / "attention_queries.json"
NARRATIVES_PATH = DATA_DIR / "attention_narratives.json"
SOURCES = ("xsearch_web", "reddit_web")
# The one identity the collectors send: plain and descriptive (SPEC rule 11; owner probes used it).
HONEST_USER_AGENT = "attention-probe/0.1"
SYMBOL_RE = re.compile(r"[A-Z0-9_]{1,24}")
NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 .'&-]{0,38}[A-Za-z0-9.]|[A-Za-z0-9]")
SUBREDDIT_RE = re.compile(r"[A-Za-z0-9_]{2,21}")
TOP_KEYS = {"version", "note", "collector", "subreddits", "ambiguous", "coins"}
COIN_KEYS = {"name", "cashtag_only", "note", "x_lang"}
X_FILTERS = "lang:en -filter:replies -filter:retweets"

DEFAULTS = {
    "x_query_delay_min_s": 180,
    "x_query_delay_max_s": 360,
    "x_page_gap_min_s": 5,
    "x_page_gap_max_s": 15,
    "x_daily_post_budget": 800,
    "x_sample_n": 40,
    "x_sample_min": 20,
    "x_page_cap": 3,
    "x_backfill_days": 14,
    "reddit_request_delay_min_s": 60,
    "reddit_request_delay_max_s": 120,
    "reddit_daily_request_budget": 150,
    "reddit_sample_min": 10,
}
# X reader keys (SPEC rules 17-20, Annex A.1b; W8d1). Typed: validated one by one in `_x_value`.
X_DEFAULTS = {
    "x_lang": "en",
    "x_window_syntax": "since_time",
    "x_min_account_age_days": 30,
    "x_min_followers": 10,
    "x_max_cashtags": 5,
    "x_raw_retention_days": 180,
    "x_canary_query": "bitcoin",
    "x_canary_min_results": 15,
    "x_unit_max_restarts": 1,
    "x_canary_tolerance": 0.25,
    "x_canary_min_overlap": 0.6,
    "x_parse_drop_threshold": 0.2,
    "x_allow_curl_backend": False,
}
_INT_KEYS = tuple(DEFAULTS)
DEFAULTS = {**DEFAULTS, **X_DEFAULTS}
X_WINDOW_SYNTAXES = ("since_time", "date")
LANG_RE = re.compile(r"[a-z]{2,3}")
CANARY_QUERY_RE = re.compile(r"[A-Za-z0-9$#][A-Za-z0-9 $#._-]{0,59}")
_X_COUNTS = {"x_min_account_age_days": 0, "x_min_followers": 0, "x_max_cashtags": 1, "x_raw_retention_days": 1,
             "x_canary_min_results": 1, "x_unit_max_restarts": 0}
_X_FRACTIONS = ("x_canary_tolerance", "x_canary_min_overlap", "x_parse_drop_threshold")
_ORDERED = (("x_query_delay_min_s", "x_query_delay_max_s"), ("x_page_gap_min_s", "x_page_gap_max_s"),
            ("reddit_request_delay_min_s", "reddit_request_delay_max_s"), ("x_sample_min", "x_sample_n"))
_MAY_BE_ZERO = {"x_backfill_days"}


class QueriesError(ValueError):
    """The query file is invalid; the message names the key, never a value."""


@dataclass(frozen=True)
class CollectorConfig:
    x_query_delay_min_s: int
    x_query_delay_max_s: int
    x_page_gap_min_s: int
    x_page_gap_max_s: int
    x_daily_post_budget: int
    x_sample_n: int
    x_sample_min: int
    x_page_cap: int
    x_backfill_days: int
    reddit_request_delay_min_s: int
    reddit_request_delay_max_s: int
    reddit_daily_request_budget: int
    reddit_sample_min: int
    x_lang: str = X_DEFAULTS["x_lang"]
    x_window_syntax: str = X_DEFAULTS["x_window_syntax"]
    x_min_account_age_days: int = X_DEFAULTS["x_min_account_age_days"]
    x_min_followers: int = X_DEFAULTS["x_min_followers"]
    x_max_cashtags: int = X_DEFAULTS["x_max_cashtags"]
    x_raw_retention_days: int = X_DEFAULTS["x_raw_retention_days"]
    x_canary_query: str = X_DEFAULTS["x_canary_query"]
    x_canary_min_results: int = X_DEFAULTS["x_canary_min_results"]
    x_unit_max_restarts: int = X_DEFAULTS["x_unit_max_restarts"]
    x_canary_tolerance: float = X_DEFAULTS["x_canary_tolerance"]
    x_canary_min_overlap: float = X_DEFAULTS["x_canary_min_overlap"]
    x_parse_drop_threshold: float = X_DEFAULTS["x_parse_drop_threshold"]
    x_allow_curl_backend: bool = X_DEFAULTS["x_allow_curl_backend"]

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Queries:
    config: CollectorConfig
    subreddits: tuple[str, ...]
    ambiguous: dict[str, frozenset[str]]
    coins: dict[str, dict]


def valid_lang(v) -> bool:
    """An X language code (`en`, `ja`) or empty, meaning any language."""
    return isinstance(v, str) and (v == "" or bool(LANG_RE.fullmatch(v)))


def _x_value(key: str, v) -> bool:
    if key == "x_lang":
        return valid_lang(v)
    if key == "x_window_syntax":
        return v in X_WINDOW_SYNTAXES
    if key == "x_canary_query":
        return isinstance(v, str) and bool(CANARY_QUERY_RE.fullmatch(v))
    if key == "x_allow_curl_backend":
        return isinstance(v, bool)
    if key in _X_FRACTIONS:
        return isinstance(v, (int, float)) and not isinstance(v, bool) and 0 < v <= 1
    return isinstance(v, int) and not isinstance(v, bool) and v >= _X_COUNTS[key]


def validate_config(block) -> CollectorConfig:
    if not isinstance(block, dict):
        raise QueriesError("collector: must be an object")
    unknown = sorted(set(block) - set(DEFAULTS))
    if unknown:
        raise QueriesError(f"collector: unknown key(s) {', '.join(k[:40] for k in unknown)}")
    for key in X_DEFAULTS:
        if key not in block or not _x_value(key, block[key]):
            raise QueriesError(f"collector: {key} is missing or not a valid value")
    for key in _INT_KEYS:
        v = block.get(key)
        floor = 0 if key in _MAY_BE_ZERO else 1
        if not isinstance(v, int) or isinstance(v, bool) or v < floor:
            raise QueriesError(f"collector: {key} must be an integer >= {floor}")
    for lo, hi in _ORDERED:
        if block[lo] > block[hi]:
            raise QueriesError(f"collector: {lo} must be <= {hi}")
    return CollectorConfig(**{k: block[k] for k in DEFAULTS})


def _symbol(value, what: str) -> str:
    if not isinstance(value, str) or not SYMBOL_RE.fullmatch(value):
        raise QueriesError(f"{what}: symbol must match {SYMBOL_RE.pattern}")
    return value


def validate(doc, placed_symbols=None) -> Queries:
    if not isinstance(doc, dict):
        raise QueriesError("queries: file must be a JSON object")
    if set(doc) - TOP_KEYS or doc.get("version") != 1:
        raise QueriesError(f"queries: keys must be within {', '.join(sorted(TOP_KEYS))} and version must be 1")
    if not isinstance(doc.get("note", ""), str):
        raise QueriesError("queries: note must be text")
    config = validate_config(doc.get("collector"))
    subs = doc.get("subreddits")
    if not isinstance(subs, list) or not subs or not all(isinstance(s, str) and SUBREDDIT_RE.fullmatch(s)
                                                          for s in subs):
        raise QueriesError("subreddits: must be a non-empty list of subreddit names")
    if len({s.lower() for s in subs}) != len(subs):
        raise QueriesError("subreddits: duplicate name")
    amb = doc.get("ambiguous")
    if not isinstance(amb, dict) or set(amb) != set(SOURCES):
        raise QueriesError(f"ambiguous: must have exactly the sources {', '.join(SOURCES)}")
    ambiguous = {}
    for source, items in amb.items():
        if not isinstance(items, list):
            raise QueriesError(f"ambiguous: {source} must be a list")
        ambiguous[source] = frozenset(_symbol(s, f"ambiguous {source}") for s in items)
    coins = doc.get("coins")
    if not isinstance(coins, dict):
        raise QueriesError("coins: must be an object")
    out: dict[str, dict] = {}
    for sym, entry in coins.items():
        _symbol(sym, "coins")
        if not isinstance(entry, dict) or set(entry) - COIN_KEYS:
            raise QueriesError(f"coins: {sym} keys must be within {', '.join(sorted(COIN_KEYS))}")
        name = entry.get("name")
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            raise QueriesError(f"coins: {sym} name must be 1-40 safe characters (letters, digits, space . ' & -)")
        if not isinstance(entry.get("cashtag_only", False), bool):
            raise QueriesError(f"coins: {sym} cashtag_only must be true or false")
        if "x_lang" in entry and not valid_lang(entry["x_lang"]):
            raise QueriesError(f"coins: {sym} x_lang must be a 2-3 letter language code or empty")
        out[sym] = dict(entry)
    if placed_symbols is not None:
        missing = sorted(set(placed_symbols) - set(out))
        if missing:
            raise QueriesError(f"coins: {len(missing)} placed coin(s) have no entry: {', '.join(missing[:5])}")
    return Queries(config, tuple(subs), ambiguous, out)


def _no_duplicate_keys(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise QueriesError(f"queries: duplicate key {str(key)[:30]!r}")
        seen[key] = value
    return seen


def load(path: Path | None = None, placed_symbols=None) -> Queries:
    text = (path or QUERIES_PATH).read_bytes().decode("utf-8")
    return validate(json.loads(text, object_pairs_hook=_no_duplicate_keys), placed_symbols)


def placed_symbols(path: Path | None = None) -> list[str]:
    """Every symbol placed in a narrative (read here so api.data never imports api.analytics)."""
    doc = json.loads((path or NARRATIVES_PATH).read_text(encoding="utf-8"))
    syms = {_symbol(c.get("symbol"), "narratives") for n in doc.get("narratives", []) for c in n.get("coins", [])}
    return sorted(syms)


def coin_set(q: Queries, source: str, placed) -> list[str]:
    if source not in SOURCES:
        raise QueriesError(f"coin_set: source must be one of {', '.join(SOURCES)}")
    return sorted(set(placed) - q.ambiguous[source])


def x_query(q: Queries, symbol: str) -> str | None:
    """SPEC A.1 query text (cashtag first), or None when the coin is ambiguous for X or has no entry."""
    entry = q.coins.get(symbol)
    if entry is None or symbol in q.ambiguous["xsearch_web"]:
        return None
    name = entry["name"]
    if entry.get("cashtag_only") or name.upper() == symbol:
        return f'"${symbol}" {X_FILTERS}'
    return f'("${symbol}" OR "{name}") {X_FILTERS}'


def reddit_terms(q: Queries, symbol: str) -> list[str] | None:
    """Ticker and name for the Reddit search, or None when the coin is ambiguous for Reddit or has no entry."""
    entry = q.coins.get(symbol)
    if entry is None or symbol in q.ambiguous["reddit_web"]:
        return None
    name = entry["name"]
    return [symbol] if name.upper() == symbol else [symbol, name]
