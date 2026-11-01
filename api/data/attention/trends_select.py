"""Stage 2 selection rule (D-30): one Google Trends keyword per coin, proposed from the campaign evidence.

Pure and read-only: it reads one campaign coin record and the coin's keyword entry and returns a Selection. It never
touches the keyword file, the network or the store; the owner applies a proposal by hand (D2). The tester proposes,
the owner decides; `approved` is never produced here.

Rule: a candidate is a single-term group whose outcome starts with `ok`, whose verdict is `ok` (the daily rule) and
that has no one-term spike. The current keyword is kept when it is a candidate; otherwise topic first, then fewest
zero days, then most distinct values, then higher volume correlation (missing last). Rising never decides (AC3).
For an ambiguous coin only a topic or a qualified term can be a candidate, and a term needs the owner's approval.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from api.data.attention import trends
from api.data.attention import trends_groups as tg
from api.data.attention import trends_keywords as tk

VERDICTS = ("use-term", "use-topic", "needs-approval", "needs-owner", "waking-up", "untested")
OK = "ok"


@dataclass(frozen=True)
class Selection:
    verdict: str
    term: str | None
    reasons: tuple[str, ...]
    flags: tuple[str, ...]
    others: tuple[tuple[str, str], ...]   # (group text, why it was not chosen)


def _text(terms) -> str:
    return "[" + " | ".join(terms) + "]"


def _num(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def _metrics(rec: dict) -> dict | None:
    """The numbers a candidate needs, or None when the metrics are missing or malformed."""
    met = rec.get("metrics")
    if not isinstance(met, dict) or not isinstance(met.get("verdict"), str):
        return None
    zero, distinct = _num(met.get("zero_pct")), _num(met.get("distinct"))
    corr = met.get("identity_corr")
    if zero is None or distinct is None or (corr is not None and _num(corr) is None):
        return None
    return {"verdict": met["verdict"], "zero": zero, "distinct": distinct, "corr": _num(corr),
            "spike": met.get("spike") is True,
            "moves_alone": [t for t in met.get("moves_alone") or [] if isinstance(t, str)]}


def _groups(coin) -> list[dict] | None:
    if not isinstance(coin, dict) or not isinstance(coin.get("groups"), dict):
        return None
    out = []
    for rec in coin["groups"].values():
        if (isinstance(rec, dict) and isinstance(rec.get("terms"), list) and rec["terms"]
                and all(isinstance(t, str) for t in rec["terms"]) and isinstance(rec.get("outcome"), str)):
            out.append(rec)
    return out


def _why_not(rec: dict, met: dict | None, ambiguous: bool) -> str | None:
    """None when the group is a candidate, else why it is not."""
    outcome = rec["outcome"]
    if outcome.startswith("frame-rejected"):
        return "frame rejected"
    if not outcome.startswith(OK):
        return "request failed" if outcome.startswith("request-failed") else f"outcome {outcome}"
    if met is None:
        return "malformed or missing metrics"
    if met["verdict"] != OK:
        return f"not usable: {tg.verdict_label(met['verdict'])}"
    if met["spike"]:
        return "one-term spike"
    if len(rec["terms"]) != 1 or rec.get("kind") == "bundle":
        return "bundle: checks variants only, never the signal"
    term = rec["terms"][0]
    if not (tk.is_valid_topic(term) or tk.is_valid_term(term)):
        return "not loader-safe"
    if ambiguous and not tk.is_valid_topic(term):
        if str(rec.get("kind", "")).startswith("bare") or not trends.is_qualified_term(term):
            return "bare name on an ambiguous coin"
    return None


def _rank(c: dict) -> tuple:
    return (not tk.is_valid_topic(c["term"]), c["zero"], -c["distinct"],
            c["corr"] is None, -(c["corr"] or 0.0))


def _flags(term: str, cand: dict, groups: list[dict]) -> tuple[str, ...]:
    corr = cand["corr"]
    if corr is None:
        vol = "unchecked (no volume)"
    elif corr < tg.IDENTITY_MIN_CORR:
        vol = "unconfirmed (volume)"
    else:
        vol = "agrees (volume)"
    folded = term.casefold()
    bundles = []
    for rec in groups:
        met = _metrics(rec)
        if (rec.get("kind") == "bundle" and rec["outcome"].startswith(OK) and met and met["verdict"] == OK
                and folded in {t.casefold() for t in rec["terms"]}):
            bundles.append(met)
    if not bundles:
        var = "unchecked (no variants)"
    elif any(folded in {t.casefold() for t in b["moves_alone"]} for b in bundles):
        var = "unconfirmed (variants)"
    else:
        var = "agrees (variants)"
    return vol, var


def select(symbol: str, coin, entry: dict | None, ambiguous) -> Selection:
    """The stage-2 verdict for one coin. `coin` is the campaign record (None when the coin was not tested), `entry`
    its keyword-file entry (the caller reports a coin without an entry apart, never as a verdict)."""
    groups = _groups(coin)
    if groups is None or not any(not r["outcome"].startswith("request-failed") for r in groups):
        return Selection("untested", None, ("not tested in the campaign",), (), ())
    entry = entry if isinstance(entry, dict) else {}
    listed = symbol in ambiguous
    current = entry.get("topic") or entry.get("term")
    cands, others = [], []
    for rec in groups:
        met = _metrics(rec)
        why = _why_not(rec, met, listed)
        if why is None:
            cands.append({"term": rec["terms"][0], **met})
        else:
            others.append((_text(rec["terms"]), why))
    if not cands:
        if any(r["outcome"].startswith(OK) and (x := _metrics(r)) and x["verdict"] == trends.QUIET_THEN_SURGE
               for r in groups):
            approved = isinstance(current, str) and entry.get("approved") == current
            note = "waking up (quiet then surge); approved, pulled" if approved else "waking up (quiet then surge)"
            return Selection("waking-up", None, (note,), (), tuple(others))
        responded = [r for r in groups if not r["outcome"].startswith("request-failed")]
        if all(r["outcome"].startswith("frame-rejected") for r in responded):
            reason = "frame-rejected"
        elif any(r["outcome"].startswith(OK) and (x := _metrics(r)) and x["verdict"] == trends.TOO_LITTLE_INTEREST
                 for r in responded):
            reason = "too-little-interest"
        else:
            reason = "no usable group"
        return Selection("needs-owner", None, (reason,), (), tuple(others))
    by_term = {c["term"].casefold(): c for c in cands}
    cur = by_term.get(current.casefold()) if isinstance(current, str) else None
    approved_term = entry.get("approved") if entry.get("approved") == entry.get("term") else None
    if cur is not None and (not listed or tk.is_valid_topic(cur["term"]) or cur["term"] == approved_term):
        chosen, why = cur, "current keyword is a usable candidate"
    elif listed and any(tk.is_valid_topic(c["term"]) for c in cands):
        chosen = min((c for c in cands if tk.is_valid_topic(c["term"])), key=_rank)
        why = "topic (ambiguous coin)"
    elif cur is not None:
        chosen, why = cur, "current keyword is a usable candidate"
    else:
        chosen = min(cands, key=_rank)
        why = "best candidate: topic first, then fewest zero days, most distinct values, volume correlation"
    term = chosen["term"]
    for c in sorted(cands, key=_rank):
        if c is not chosen:
            others.append((_text([c["term"]]), f"ranked lower (zero {c['zero']:g}%, distinct {c['distinct']:g})"))
    flags = _flags(term, chosen, groups)
    if tk.is_valid_topic(term):
        verdict = "use-topic"
    elif listed and term != approved_term:
        verdict, why = "needs-approval", f"{why}; ambiguous coin: suggestion only, the owner approves the term"
    else:
        verdict = "use-term"
    return Selection(verdict, term, (why,), flags, tuple(others))


def proposal(selections: dict[str, tuple[Selection, dict | None]]) -> dict[str, dict]:
    """Paste-ready keyword entries for coins whose verdict changes their keyword (use-term / use-topic only). The
    label is kept; `approved` is never produced; every value passes the loader's own checks."""
    out: dict[str, dict] = {}
    for sym, (s, entry) in selections.items():
        if s.verdict not in ("use-term", "use-topic") or not s.term or not isinstance(entry, dict):
            continue
        if s.term == (entry.get("topic") or entry.get("term")):
            continue
        kind = "topic" if s.verdict == "use-topic" else "term"
        ok = tk.is_valid_topic(s.term) if kind == "topic" else tk.is_valid_term(s.term)
        label = entry.get("label")
        if ok and tk.SYMBOL_RE.fullmatch(sym) and tk.is_valid_label(label):
            out[sym] = {kind: s.term, "label": label}
    return out
