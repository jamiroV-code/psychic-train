"""Finish plan RC-1, RC-7, RC-8, RC-9: shared vocabulary of the Reddit live methods, item reduction, the per-method
item store and the `LiveMethod` factory table. Pure; no network.

Two live methods, each its own store and Discovery series (never mixed with the feeds or each other):
`browser` -> `reddit_live_browser`, `gql_anon` -> `reddit_live_gql` (`registry.SOURCE_IMPLS["reddit"]`).

Privacy (RC-7): an extracted item is reduced AT ONCE to `{id, kind, subreddit, created_utc, author_hash, coins}`;
the text is used only to match coins in memory and is never stored or logged; `[deleted]`/`[removed]`/empty authors
hash to None like the feed ledger (`reddit_items._NO_AUTHOR`).

Factory table (RC-9): dotted `module:function` strings resolved by lazy import ONLY for the methods named in
`reddit_live_methods`; an entry whose module has not landed or fails to import or build yields a method whose gate
state is `method_unavailable`, never an exception. S-RBrowser and S-RGQL supply `make_method(config, deps)`.
"""
from __future__ import annotations

import importlib
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from api.data import cache
from api.data.attention import reddit_items
from api.data.attention.reddit_surface import ID_RE, RawItem
from api.data.attention.web_queries import REDDIT_LIVE_METHODS, SUBREDDIT_RE, SYMBOL_RE

STORES = {"browser": "reddit_live_browser", "gql_anon": "reddit_live_gql"}
METHOD_IDS = {"reddit_live_browser": "reddit_live_browser_v1", "reddit_live_gql": "reddit_live_gql_v1"}
LABELS = {"browser": "Reddit live (browser)", "gql_anon": "Reddit live (anonymous GraphQL)"}
assert set(STORES) == set(REDDIT_LIVE_METHODS)

LANE_KINDS = ("posts", "comments")
STOP_REASONS = ("exhausted", "cap", "error", "breaker", "empty_shell", "login_required", "schema_mismatch",
                "unsupported_format", "unknown")
GATE_STATES = ("ready", "needs_probe", "no_ready_account", "browser_unadmitted", "containment_residual_unaccepted",
               "cdp_pipe_unavailable", "profile_policy_unsatisfied", "unsupported_format", "disabled",
               "method_unavailable")
# RC-8: reason codes the live methods add to the allowlist (completeness documents, health, facts).
REASONS = ("lane_incomplete", "needs_probe", "method_disabled", "no_ready_account", "request_cap",
           "schema_mismatch", "unsupported_format", "zero_unverified", "method_unavailable")
COMMENTS_SCOPE = "threads_opened"
CANARY_SUBREDDIT = "CryptoCurrency"

FACTORY_TABLE = {"browser": "api.data.attention.reddit_browser:make_method",
                 "gql_anon": "api.data.attention.reddit_gql:make_method"}


# --- items (RC-7) ---

@dataclass(frozen=True)
class LiveItem:
    id: str
    kind: str  # "post" | "comment"
    subreddit: str
    created_utc: datetime
    author_hash: str | None
    coins: tuple[str, ...]

    def __post_init__(self):
        if not isinstance(self.id, str) or not ID_RE.fullmatch(self.id):
            raise ValueError("bad Reddit id")
        if self.kind not in ("post", "comment") or self.id[:3] != ("t3_" if self.kind == "post" else "t1_"):
            raise ValueError("bad kind")
        if not isinstance(self.subreddit, str) or not SUBREDDIT_RE.fullmatch(self.subreddit):
            raise ValueError("bad subreddit")
        if not isinstance(self.created_utc, datetime) or self.created_utc.tzinfo is None:
            raise ValueError("created must be timezone-aware")
        if self.author_hash is not None and not (isinstance(self.author_hash, str)
                                                 and len(self.author_hash) == reddit_items.HASH_HEX):
            raise ValueError("author must be a hash")
        if not all(isinstance(c, str) and SYMBOL_RE.fullmatch(c) for c in self.coins):
            raise ValueError("bad coin symbol")
        object.__setattr__(self, "created_utc", self.created_utc.astimezone(timezone.utc))
        object.__setattr__(self, "coins", tuple(sorted(set(self.coins))))

    def to_json(self) -> dict:
        return {"id": self.id, "kind": self.kind, "subreddit": self.subreddit,
                "created_utc": self.created_utc.isoformat(), "author_hash": self.author_hash,
                "coins": list(self.coins)}

    @classmethod
    def from_json(cls, d: dict) -> LiveItem:
        if set(d) != {"id", "kind", "subreddit", "created_utc", "author_hash", "coins"}:
            raise ValueError("bad item row")
        return cls(d["id"], d["kind"], d["subreddit"], datetime.fromisoformat(d["created_utc"]), d["author_hash"],
                   tuple(d["coins"]))


def reduce_item(raw: RawItem, hasher: Callable[[str | None], str | None],
                match: Callable[[str], tuple[str, ...]]) -> LiveItem:
    """Reduce one extracted item at once; the text and the username go no further than this call."""
    return LiveItem(raw.id, raw.kind, raw.subreddit, raw.created, hasher(raw.author), tuple(match(raw.text)))


def items_path(store: str, day: date) -> Path:
    if store not in METHOD_IDS:
        raise ValueError("unknown live store")
    return cache.CACHE_ROOT / "attention" / store / "_items" / f"{day.isoformat()}.json"


def read_items(store: str, day: date) -> dict[str, LiveItem]:
    path = items_path(store, day)
    if not path.exists():
        return {}
    rows = (LiveItem.from_json(r) for r in json.loads(path.read_text(encoding="utf-8"))["rows"])
    return {r.id: r for r in rows}


def add_items(store: str, items: Iterable[LiveItem]) -> int:
    """Store new ids per created day (first row wins; a known id only gains coins). Returns the new-id count."""
    by_day: dict[date, list[LiveItem]] = {}
    for it in items:
        by_day.setdefault(it.created_utc.date(), []).append(it)
    new = 0
    for day, batch in by_day.items():
        known, changed = read_items(store, day), False
        for it in batch:
            old = known.get(it.id)
            if old is None:
                known[it.id], changed, new = it, True, new + 1
            elif not set(it.coins) <= set(old.coins):
                known[it.id] = LiveItem(old.id, old.kind, old.subreddit, old.created_utc, old.author_hash,
                                        old.coins + it.coins)
                changed = True
        if changed:
            path = items_path(store, day)
            path.parent.mkdir(parents=True, exist_ok=True)
            cache._atomic_write_json({"rows": [known[k].to_json() for k in sorted(known)]}, path)
    return new


# --- the factory table (RC-9) ---

class UnavailableMethod:
    """Stand-in for a method whose factory entry cannot be resolved: always `method_unavailable`, never polls."""

    def __init__(self, name: str):
        self.method_id = name
        self.label = LABELS.get(name, name)
        self.store = STORES.get(name)

    def gate_state(self, now: datetime) -> str:
        return "method_unavailable"

    def next_poll_due(self, now: datetime) -> datetime | None:
        return None

    def run_poll(self, ctx):
        raise RuntimeError("method_unavailable")

    def close(self) -> None:
        return None


def resolve_method(name: str, config, deps, *, table: dict[str, str] | None = None):
    """Build one method from the factory table by lazy import; any failure yields `UnavailableMethod`."""
    entry = (FACTORY_TABLE if table is None else table).get(name)
    if not isinstance(entry, str) or entry.count(":") != 1:
        return UnavailableMethod(name)
    module, func = entry.split(":")
    try:
        method = getattr(importlib.import_module(module), func)(config, deps)
    except Exception:  # an absent module, an import error or a failing factory: the method is unavailable
        return UnavailableMethod(name)
    if any(not hasattr(method, a) for a in ("method_id", "label", "store", "gate_state", "next_poll_due", "run_poll",
                                             "close")):
        return UnavailableMethod(name)
    return method


def resolve_methods(config, deps, *, table: dict[str, str] | None = None) -> dict:
    """The configured live methods in `reddit_live_methods` order; nothing is imported for an unnamed method."""
    return {name: resolve_method(name, config, deps, table=table) for name in config.reddit_live_methods}
