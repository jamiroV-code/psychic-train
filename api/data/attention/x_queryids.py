"""Nonsecret query-ID registry. No bundle code is ever executed.

Same-user limit: validation catches malformed state, not an owner fabricating both
an adoption and its evidence. Only SearchTimeline may be adopted; ordinary IDs
remain pinned. The network sentinel and account evaluator are separate owners.
"""
from __future__ import annotations

import copy
import json
import re
from datetime import datetime
from pathlib import Path

from api.data.attention import x_proxy as p

QUERY_ID = re.compile(r"[A-Za-z0-9_-]{16,32}")
TRACKED = "SearchTimeline"
PINNED = {TRACKED: "BYppgupFFS2yqVmmRNjlsw", "UserTweets": "OdBLACRZ0-9NikpJotaT7g",
          "TweetDetail": "wjV7NuWEsHgTBFfW3zYKzQ", "UserByScreenName": "AMIBMjtxEEATh4z8V9GtRg"}
OPERATIONS = tuple(PINNED)
EMBED_URL = "https://x.com/i/embed"
STATIC_BASE = "https://abs.twimg.com/responsive-web/client-web/main."
BUNDLE_LIMIT = 4 * 1024 * 1024
STATE_LIMIT = 128 * 1024
EVIDENCE_LIMIT = 32
CHECK_STATES = {"unknown", "blocked", "refused_by_policy", "ok", "candidate", "stale"}


def valid_id(value):
    return isinstance(value, str) and QUERY_ID.fullmatch(value) is not None


def _pinned(op):
    return {"id": PINNED[op], "source": "pinned", "adopted_at": None, "evidence_id": None}


def initial_state():
    return {"version": 1, "check_state": "unknown", "last_check": None, "bundle_sha256": None,
            "budget": {"day": None, "used": 0}, "operations": {
                op: {"active": _pinned(op), "candidate": None, "observed": None} for op in OPERATIONS}, "evidence": []}


def _require(value):
    if not value:
        raise ValueError("invalid query-id state")


def _exact(value, keys):
    _require(isinstance(value, dict) and set(value) == set(keys))


def _stamp(value, optional=False):
    if optional and value is None:
        return
    _require(isinstance(value, str) and len(value) <= 40)
    dt = datetime.fromisoformat(value)
    _require(dt.tzinfo is not None and dt.utcoffset().total_seconds() == 0)


def validate(value):
    """Every disk read passes here. Invalid documents fail closed to pinned IDs."""
    try:
        _exact(value, initial_state())
        _require(type(value["version"]) is int and value["version"] == 1)
        _require(value["check_state"] in CHECK_STATES)
        _stamp(value["last_check"], True)
        _require(value["bundle_sha256"] is None or isinstance(value["bundle_sha256"], str)
                 and re.fullmatch(r"[0-9a-f]{64}", value["bundle_sha256"]))
        budget = value["budget"]
        _exact(budget, ("day", "used"))
        _require(type(budget["used"]) is int and 0 <= budget["used"] <= 12)
        if budget["day"] is not None:
            _require(isinstance(budget["day"], str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", budget["day"]))
            datetime.strptime(budget["day"], "%Y-%m-%d")
        _require(isinstance(value["evidence"], list) and len(value["evidence"]) <= EVIDENCE_LIMIT)
        identifiers = set()
        for e in value["evidence"]:
            _exact(e, ("evidence_id", "operation", "candidate_id", "account_label", "evaluated_at", "result", "entries", "parse_ok"))
            _require(isinstance(e["evidence_id"], str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", e["evidence_id"]))
            _require(e["evidence_id"] not in identifiers)
            identifiers.add(e["evidence_id"])
            _require(e["operation"] == TRACKED and valid_id(e["candidate_id"]))
            _require(isinstance(e["account_label"], str) and re.fullmatch(r"[a-z0-9_]{1,24}", e["account_label"]))
            _stamp(e["evaluated_at"])
            _require(e["result"] in ("passed", "failed", "inconclusive") and type(e["parse_ok"]) is bool)
            _require(type(e["entries"]) is int and 0 <= e["entries"] <= 100000)
        _exact(value["operations"], OPERATIONS)
        result = copy.deepcopy(value)
        for op, entry in result["operations"].items():
            _exact(entry, ("active", "candidate", "observed"))
            a = entry["active"]
            _exact(a, ("id", "source", "adopted_at", "evidence_id"))
            _require(valid_id(a["id"]) and a["source"] in ("pinned", "bundle"))
            _stamp(a["adopted_at"], True)
            if a["source"] == "pinned":
                _require(a["id"] == PINNED[op] and a["evidence_id"] is None)
            elif op != TRACKED or a["adopted_at"] is None or not any(
                    e["evidence_id"] == a["evidence_id"] and e["candidate_id"] == a["id"]
                    and e["operation"] == op and e["result"] == "passed" and e["parse_ok"] and e["entries"] > 0
                    for e in result["evidence"]):
                entry["active"] = _pinned(op)
            c = entry["candidate"]
            if c is not None:
                _require(op == TRACKED)
                _exact(c, ("id", "seen_at", "rejected_until", "reason"))
                _require(valid_id(c["id"]))
                _stamp(c["seen_at"])
                _stamp(c["rejected_until"], True)
                _require(c["reason"] in (None, "evaluation_failed", "inconclusive"))
            o = entry["observed"]
            if o is not None:
                _exact(o, ("id", "seen_at"))
                _require(valid_id(o["id"]))
                _stamp(o["seen_at"])
        return result
    except (ValueError, TypeError, KeyError, AttributeError):
        return initial_state()


def state_path(cache_root):
    return Path(cache_root) / "attention" / "_pc_state" / "x_queryids.json"


def load(path):
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(STATE_LIMIT + 1)
        return validate(p.strict_json(raw, limit=STATE_LIMIT))
    except (OSError, ValueError, p.ProxyFailure):
        return initial_state()


def save(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(validate(state), separators=(",", ":"), ensure_ascii=True)
    _require(len(raw) <= STATE_LIMIT)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(raw, encoding="utf-8")
    temporary.replace(path)


def active_id(state, operation=TRACKED):
    return state["operations"][operation]["active"]["id"]


def bundle_hash(html):
    hashes = set(re.findall(r'https://abs\.twimg\.com/responsive-web/client-web/main\.([a-f0-9]{7,32})\.js', html))
    return next(iter(hashes)) if len(hashes) == 1 else None


def bundle_url(value):
    _require(isinstance(value, str) and re.fullmatch(r"[a-f0-9]{7,32}", value))
    return STATIC_BASE + value + ".js"


def parse_bundle(text):
    """Parse only literal queryId/operationName pairs; reject duplicates globally."""
    if len(text) > BUNDLE_LIMIT:
        return None
    pairs = re.findall(r'queryId\s*:\s*"([^"\r\n]*)"\s*,\s*operationName\s*:\s*"([A-Za-z0-9_]+)"', text)
    mapping, ids = {}, set()
    for query_id, op in pairs:
        if not valid_id(query_id) or op in mapping or query_id in ids:
            return None
        mapping[op] = query_id
        ids.add(query_id)
    if TRACKED not in mapping:
        return None
    return {op: value for op, value in mapping.items() if op in PINNED}


def apply_check(state, now, *, outcome, mapping=None, sha256=None):
    result = validate(state)
    result["last_check"] = now.isoformat()
    if outcome != "ok":
        result["check_state"] = outcome if outcome in ("blocked", "refused_by_policy") else "unknown"
        return result
    _require(isinstance(mapping, dict) and TRACKED in mapping and all(op in PINNED and valid_id(i) for op, i in mapping.items()))
    _require(isinstance(sha256, str) and re.fullmatch(r"[a-f0-9]{64}", sha256))
    result["bundle_sha256"] = sha256
    for op, value in mapping.items():
        result["operations"][op]["observed"] = {"id": value, "seen_at": now.isoformat()}
    entry = result["operations"][TRACKED]
    if mapping[TRACKED] == entry["active"]["id"]:
        entry["candidate"] = None
        result["check_state"] = "ok"
    else:
        candidate = entry["candidate"]
        if candidate is None or candidate["id"] != mapping[TRACKED]:
            candidate = {"id": mapping[TRACKED], "seen_at": now.isoformat(), "rejected_until": None, "reason": None}
        entry["candidate"] = candidate
        result["check_state"] = "stale" if candidate["rejected_until"] and datetime.fromisoformat(candidate["rejected_until"]) > now else "candidate"
    return result
