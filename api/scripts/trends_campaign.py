"""Campaign state for `probe_trends --all-eligible` / `--report` (T201): every Discovery-eligible coin's candidate
term groups, tested a few dozen requests per run and resumed from a JSON state file outside the repo.

The state keeps terms, outcomes and metrics only (never a response body, header or secret). Writes are atomic (temp
file + rename); a corrupt state file is refused and never overwritten. Stage-2 hook: each coin keeps
`last_tested`, `best_group` and `verdict`, enough for the Discovery gate to require "keyword tested" later.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path

from api.data.attention import trends
from api.data.attention import trends_candidates as tc_
from api.data.attention import trends_groups as tg
from api.data.attention import trends_keywords as tk

STATE_VERSION = 1
TESTER_VERSION = "t201-1"
DEFAULT_STATE_NAME = "trends_campaign.json"
REPO_ROOT = Path(__file__).resolve().parents[2]
GROUP_KEYS = ("terms", "kind", "note", "loader_flags", "outcome", "metrics", "tested_at", "tester_version")
OK = "ok"
REQUEST_FAILED = "request-failed"
FRAME_REJECTED = "frame-rejected"
HEALTH_ORDER = ("missing", "empty", "weak")  # tested before the "ok" coins


class StateError(ValueError):
    pass


def default_state_path() -> Path:
    return Path.home() / DEFAULT_STATE_NAME


def check_state_path(path: Path) -> Path:
    """Refuse a path inside the repository (api/data/cache, the tracked dirs, the root) or a folder."""
    resolved = Path(path).expanduser().resolve()
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        raise StateError("state file: refused, the path is inside the repository; keep it outside "
                         f"(default {default_state_path()})")
    if resolved.is_dir():
        raise StateError("state file: refused, the path is a folder")
    return resolved


def new_state() -> dict:
    return {"version": STATE_VERSION, "tester_version": TESTER_VERSION, "coins": {}}


def _valid(doc) -> bool:
    if not (isinstance(doc, dict) and doc.get("version") == STATE_VERSION and isinstance(doc.get("coins"), dict)):
        return False
    for sym, coin in doc["coins"].items():
        if not (isinstance(sym, str) and tk.SYMBOL_RE.fullmatch(sym) and isinstance(coin, dict)
                and isinstance(coin.get("groups"), dict)):
            return False
        for rec in coin["groups"].values():
            if not (isinstance(rec, dict) and isinstance(rec.get("terms"), list) and rec["terms"]
                    and all(isinstance(t, str) for t in rec["terms"]) and isinstance(rec.get("outcome"), str)
                    and (rec.get("metrics") is None or isinstance(rec["metrics"], dict))):
                return False
            try:
                datetime.fromisoformat(rec["tested_at"])
            except (KeyError, TypeError, ValueError):
                return False
    return True


def load_state(path: Path, *, must_exist: bool) -> tuple[dict, bool]:
    """(state, is_new). A missing file is a new campaign unless must_exist; anything unreadable is refused."""
    if not path.exists():
        if must_exist:
            raise StateError("state file not found; run --all-eligible first")
        if not path.parent.is_dir():
            raise StateError("state file: the state file's folder does not exist")
        return new_state(), True
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        doc = None
    if not _valid(doc):
        raise StateError("state file is not a valid campaign state; it was left untouched (fix or move it, or pass "
                         "another --state)")
    return doc, False


def save_state(path: Path, state: dict) -> None:
    """Atomic: write a temp file in the same folder, fsync, then rename over the old file."""
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=1, sort_keys=True, allow_nan=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _responded(rec: dict) -> bool:
    return not rec["outcome"].startswith(REQUEST_FAILED)


def is_fresh(rec: dict | None, today: date, max_age_days: int) -> bool:
    """Tested (Google answered, usable frame or not) within max_age_days; a failed request is never fresh."""
    if not rec or not _responded(rec):
        return False
    return (today - datetime.fromisoformat(rec["tested_at"]).date()).days < max_age_days


def _ranked(coin: dict) -> list[tuple[str, dict]]:
    tested = [(k, r) for k, r in coin["groups"].items() if r["outcome"] == OK and r.get("metrics")]
    return sorted(tested, key=lambda kr: tg.rank_values(
        kr[1]["metrics"]["verdict"], kr[1]["metrics"]["clean"], kr[1]["metrics"]["zero_pct"],
        kr[1]["metrics"]["distinct"], kr[1]["metrics"]["identity_corr"]))


def record(state: dict, symbol: str, cand: tc_.Candidate, loader_flags: dict, outcome: str, metrics: dict | None,
           tested_at: datetime) -> None:
    coin = state["coins"].setdefault(symbol, {"groups": {}, "last_tested": None, "best_group": None,
                                             "verdict": None})
    coin["groups"][cand.key] = {"terms": list(cand.terms), "kind": cand.kind, "note": cand.note,
                                "loader_flags": dict(loader_flags), "outcome": outcome, "metrics": metrics,
                                "tested_at": tested_at.isoformat(), "tester_version": TESTER_VERSION}
    if not outcome.startswith(REQUEST_FAILED):
        coin["last_tested"] = tested_at.isoformat()
    ranked = _ranked(coin)
    coin["best_group"] = ranked[0][0] if ranked else None
    coin["verdict"] = ranked[0][1]["metrics"]["verdict"] if ranked else None


def latest_run_outcomes(runs_dir: Path) -> dict[str, str]:
    """Per-coin outcome of the newest daily-run summary (`trends_runs/*.json`, if another task adds it):
    {"coins": {SYM: {"outcome": str} | str}}. Missing or unreadable: {} (the caller falls back to stored series)."""
    try:
        files = sorted(Path(runs_dir).glob("*.json"))
        if not files:
            return {}
        coins = json.loads(files[-1].read_text(encoding="utf-8"))["coins"]
        out = {}
        for sym, v in coins.items():
            outcome = v.get("outcome") if isinstance(v, dict) else v
            if isinstance(sym, str) and isinstance(outcome, str):
                out[sym] = outcome
        return out
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}


def keyword_health(km: tk.KeywordMap | None, symbols, run_outcomes: dict[str, str], stored_values) -> dict[str, str]:
    """missing (no usable keyword), weak (latest run outcome not ok, else the stored series fails the daily rule),
    empty (nothing stored) or ok. stored_values(sym) -> the stored daily values."""
    out = {}
    for s in symbols:
        if tk.keyword_status(km, s) not in ("topic", "term"):
            out[s] = "missing"
        elif s in run_outcomes:
            out[s] = OK if run_outcomes[s] == OK else "weak"
        else:
            vals = stored_values(s)
            if not vals:
                out[s] = "empty"
            else:
                out[s] = OK if trends.interest_verdict(vals[-trends.TRENDS_RANGE_DAYS:]) == OK else "weak"
    return out


def priority_order(eligible: list[str], health: dict[str, str]) -> list[str]:
    """Weak, missing or empty keywords first, then the rest; universe (market cap) order inside each part."""
    first = [s for s in eligible if health.get(s) in HEALTH_ORDER]
    return first + [s for s in eligible if s not in first]


def plan(order: list[str], candidates: dict[str, list[tc_.Candidate]], state: dict, today: date,
         max_age_days: int) -> list[tuple[str, tc_.Candidate]]:
    pending = []
    for s in order:
        groups = state["coins"].get(s, {}).get("groups", {})
        pending += [(s, c) for c in candidates.get(s, []) if not is_fresh(groups.get(c.key), today, max_age_days)]
    return pending


def _terms(key_or_terms) -> str:
    terms = key_or_terms if isinstance(key_or_terms, list) else key_or_terms.split("|")
    return "[" + " | ".join(terms) + "]"


def _recommend(coin: dict, baseline_key: str | None) -> tuple[str, str]:
    """(recommendation, best group text). Switch only for a gain in usability or clean rising, and only to a group
    whose terms are all loader-valid."""
    ranked = _ranked(coin)
    if not ranked:
        return "needs owner (no group answered with a usable frame)", "-"
    m = ranked[0][1]["metrics"]
    best_txt = f"best: {_terms(ranked[0][1]['terms'])} {m['verdict']}, median {m['median']:g} (own scale only)"
    if m["verdict"] != OK:
        return "needs owner (no usable group)", best_txt
    base = coin["groups"].get(baseline_key) if baseline_key else None
    bm = base["metrics"] if base and base.get("metrics") else None
    base_ok = bool(bm) and bm["verdict"] == OK
    switch = next((r for _, r in ranked if r["metrics"]["verdict"] == OK
                   and all(f == "loader-valid" for f in r["loader_flags"].values())), None)
    if base_ok and (bm["clean"] or switch is None or not switch["metrics"]["clean"]):
        return "keep", best_txt
    if switch is None:
        return "needs owner (best usable group is not loader-valid)", best_txt
    return f"switch to {_terms(switch['terms'])}", best_txt


def report_lines(state: dict, eligible: list[str], km: tk.KeywordMap | None, health: dict[str, str]) -> list[str]:
    lines = ["campaign report: read from the state file, no request sent",
             ("every median is on its own request's 0-100 scale (own scale only): never compared across groups; "
             "groups rank by usable, clean rising, fewer zero days, more distinct values, volume correlation"),
             "coin | current keyword (verdict) | best tested group | clean rising | identity | recommend"]
    tested, untested = 0, []
    for s in eligible:
        coin = state["coins"].get(s)
        kw = km.keyword_for(s) if km else None
        if not coin or not any(r["outcome"] == OK or r["outcome"].startswith(FRAME_REJECTED)
                               for r in coin["groups"].values()):
            untested.append(s)
            continue
        tested += 1
        base = coin["groups"].get(kw) if kw else None
        if base and base.get("metrics"):
            cur = base["metrics"]["verdict"]
        elif base:
            cur = base["outcome"]
        else:
            cur = f"not tested; stored series {health.get(s, 'n/a')}"
        rec, best_txt = _recommend(coin, kw)
        best_key = coin.get("best_group")
        bm = coin["groups"][best_key]["metrics"] if best_key else None
        clean = ("yes" if bm["clean"] else "no") if bm else "-"
        ident = "-" if not bm else (f"{bm['identity_corr']:.2f} (a hint)" if bm["identity_corr"] is not None
                                    else bm["identity_reason"] or "n/a")
        lines.append(f"{s} | current: {kw or 'none'} ({cur}) | {best_txt} | clean rising {clean} | identity {ident} | "
                     f"recommend: {rec}")
    lines.append(f"\ntested {tested} of {len(eligible)} eligible coins")
    if untested:
        lines.append("untested (not tested yet, never counted as passed): " + ", ".join(untested))
    gone = [s for s in state["coins"] if s not in eligible]
    if gone:
        lines.append("no longer eligible (tested earlier, not part of the campaign now): " + ", ".join(gone))
    lines.append("stage 2 (not built): the Discovery gate could require 'keyword tested' status; each coin's state "
                 "keeps last_tested, best_group and verdict for that.")
    return lines
