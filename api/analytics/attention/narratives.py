"""Discovery narratives (U1): hand-maintained coin -> narrative memberships. File only; no network.

`attention_narratives.json` is {"status": "proposed"|"reviewed", "as_of": "YYYY-MM-DD",
"narratives": [{"id", "name", "coins": [{"symbol", "primary", "note"?}]}]}. A coin may sit in any number of
narratives and counts in each; exactly one of its entries is `primary`. Ids and symbols are checked against strict
patterns before anything else uses them: a symbol reaches `store.store_path`, which builds a file path from it.

Not errors: a narrative with fewer than `min_coins` in-universe members is hidden (listed, not scored), and an
in-universe coin with no entry is `unassigned`.

`attention_narrative_id_map.json` maps the old CoinGecko category ids (stored in frozen signal snapshots and in
bookmarked history links) to narrative ids; `null` means retired. It is read only to resolve old ids.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
NARRATIVES_PATH = DATA_DIR / "attention_narratives.json"
ID_MAP_PATH = DATA_DIR / "attention_narrative_id_map.json"
DEFINITION = "attention-narratives-v1"
STATUSES = ("proposed", "reviewed")
ID_RE = re.compile(r"[a-z0-9-]{1,40}")
SYMBOL_RE = re.compile(r"[A-Z0-9_]{1,24}")


class NarrativesError(ValueError):
    """The narratives or id-map file is invalid; the message names the narrative and symbol."""


def _check_id(value, what: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise NarrativesError(f"narratives: {what} {value!r} must match {ID_RE.pattern}")
    return value


def validate(doc) -> dict:
    if not isinstance(doc, dict):
        raise NarrativesError("narratives: file must be a JSON object")
    if doc.get("status") not in STATUSES:
        raise NarrativesError(f"narratives: status must be one of {', '.join(STATUSES)}")
    as_of = doc.get("as_of")
    try:
        ok = isinstance(as_of, str) and len(as_of) == 10 and date.fromisoformat(as_of).isoformat() == as_of
    except ValueError:
        ok = False
    if not ok:
        raise NarrativesError(f"narratives: as_of {as_of!r} must be an ISO date YYYY-MM-DD")
    items = doc.get("narratives")
    if not isinstance(items, list) or not items:
        raise NarrativesError("narratives: narratives must be a non-empty list")
    ids: set[str] = set()
    primaries: dict[str, list[str]] = {}
    for n in items:
        if not isinstance(n, dict):
            raise NarrativesError("narratives: each narrative must be an object")
        nid = _check_id(n.get("id"), "narrative id")
        if nid in ids:
            raise NarrativesError(f"narratives: duplicate narrative id {nid!r}")
        ids.add(nid)
        if not isinstance(n.get("name"), str) or not n["name"].strip():
            raise NarrativesError(f"narratives: narrative {nid!r} needs a name")
        coins = n.get("coins")
        if not isinstance(coins, list):
            raise NarrativesError(f"narratives: narrative {nid!r} coins must be a list")
        seen: set[str] = set()
        for c in coins:
            sym = c.get("symbol") if isinstance(c, dict) else None
            if not isinstance(sym, str) or not SYMBOL_RE.fullmatch(sym):
                raise NarrativesError(f"narratives: narrative {nid!r} symbol {sym!r} must match {SYMBOL_RE.pattern}")
            if sym in seen:
                raise NarrativesError(f"narratives: narrative {nid!r} lists symbol {sym!r} twice")
            seen.add(sym)
            if not isinstance(c.get("primary"), bool):
                raise NarrativesError(f"narratives: narrative {nid!r} symbol {sym!r} primary must be true or false")
            primaries.setdefault(sym, [])
            if c["primary"]:
                primaries[sym].append(nid)
    for sym, where in primaries.items():
        if len(where) != 1:
            raise NarrativesError(f"narratives: symbol {sym!r} must have exactly one primary narrative, "
                                  f"has {len(where)}" + (f" ({', '.join(where)})" if where else ""))
    return doc


def load_narratives(path: Path | None = None) -> dict:
    return validate(json.loads((path or NARRATIVES_PATH).read_text(encoding="utf-8")))


def file_sha(path: Path | None = None) -> str:
    """sha256 prefix of the narratives file bytes (folded into the signal snapshot hash)."""
    return hashlib.sha256((path or NARRATIVES_PATH).read_bytes()).hexdigest()[:16]


@dataclass
class Memberships:
    status: str
    as_of: str
    names: dict[str, str]                      # every narrative id -> name, file order
    visible: dict[str, set[str]]               # narrative id -> in-universe members, file order
    primary: dict[str, str]                    # symbol -> its primary narrative id
    hidden: list[dict] = field(default_factory=list)       # {id, name, coins}: fewer than min_coins in universe
    unassigned: list[str] = field(default_factory=list)    # in-universe symbols with no entry, universe order


def memberships(universe_symbols, min_coins: int, doc: dict | None = None) -> Memberships:
    """Every membership counts toward `min_coins`: a coin in three narratives counts in each."""
    doc = doc if doc is not None else load_narratives()
    universe = list(universe_symbols)
    inside = set(universe)
    names, visible, primary, hidden, listed = {}, {}, {}, [], set()
    for n in doc["narratives"]:
        names[n["id"]] = n["name"]
        members = [c["symbol"] for c in n["coins"]]
        listed.update(members)
        for c in n["coins"]:
            if c["primary"]:
                primary[c["symbol"]] = n["id"]
        present = [s for s in members if s in inside]
        if len(present) >= min_coins:
            visible[n["id"]] = set(present)
        else:
            hidden.append({"id": n["id"], "name": n["name"], "coins": present})
    return Memberships(status=doc["status"], as_of=doc["as_of"], names=names, visible=visible, primary=primary,
                       hidden=hidden, unassigned=[s for s in universe if s not in listed])


def load_id_map(path: Path | None = None) -> dict[str, dict]:
    """old category id -> {"narrative": id or None, "name": str}."""
    doc = json.loads((path or ID_MAP_PATH).read_text(encoding="utf-8"))
    entries = doc.get("map") if isinstance(doc, dict) else None
    if not isinstance(entries, dict):
        raise NarrativesError("narrative id map: map must be an object")
    for old, e in entries.items():
        _check_id(old, "old category id")
        if not isinstance(e, dict) or not isinstance(e.get("name"), str):
            raise NarrativesError(f"narrative id map: entry {old!r} needs a name")
        if e.get("narrative") is not None:
            _check_id(e["narrative"], f"narrative for {old!r}")
    return entries


def resolve_id(subject: str, doc: dict, id_map: dict[str, dict]) -> str | None:
    """A narrative id, or an old category id mapped to one; None when unknown or retired."""
    ids = {n["id"] for n in doc["narratives"]}
    if subject in ids:
        return subject
    target = id_map.get(subject, {}).get("narrative")
    return target if target in ids else None
