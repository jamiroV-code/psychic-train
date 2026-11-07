"""S-Report (finish plan 06-11-26, AC14, RP-1..RP-3): the daily collection report for a completed UTC day D.

Inputs are day D's immutable evidence only (RP-1): the `_facts/events_<D>.jsonl` file of contract D (with the
`universe_snapshot` events), each PC store's `_meta/_completeness/<D>.json` document and the browser admission
records under `_probes/`. Today's pool state is never read as D's truth, and an absent universe snapshot yields
"no data for D", never a recomputed universe.

Per source and method: eligible (= stored + missing), stored, exact (stored - capped), estimated (capped) and missing
with a reason histogram and the per-coin list (RP-2: missing is never zero, `100% stored` only when every eligible
coin is stored and eligible > 0, unknown prints `unknown`). Methods are listed separately and never summed; each
coin's `selected_method` is the store `discovery.pick_source_impl` reads for the window ending D.

`_reports/daily_report_<D>.json` (schema, revision, built_at, inputs_digest) and `.txt` are written atomically and
idempotently (RP-3): an unchanged input digest writes nothing; a changed one (a late settle) writes the next revision
saying when and which inputs changed. Read-only over evidence: no network, no pool-state mutation.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import threading
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from api.analytics.attention import discovery, discovery_history
from api.data import cache
from api.data.attention import daily_facts, registry

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
REPORTS_DIR = "_reports"
SOURCES = ("xsearch", "reddit")
DEFAULT_WINDOW = 30      # the Discovery default window (`/api/discovery?window=30`)
REBUILD_DAYS = 7         # covers the Reddit feed backfill (5 + yesterday) and the live methods' open days (2)
_CODE_RE = re.compile(r"[a-z_]{1,40}")
_lock = threading.Lock()

Selector = Callable[[date, dict[str, list[str]]], Mapping[str, Mapping[str, str | None]]]


# --- paths ---

def report_paths(day: date) -> tuple[Path, Path]:
    base = cache.CACHE_ROOT / "attention" / REPORTS_DIR / f"daily_report_{day.isoformat()}"
    return base.with_suffix(".json"), base.with_suffix(".txt")


def _completeness_path(store: str, day: date) -> Path:
    return cache.CACHE_ROOT / "attention" / store / "_meta" / "_completeness" / f"{day.isoformat()}.json"


def _stores(source: str) -> list[str]:
    return [s for s in registry.SOURCE_IMPLS[source] if s in registry.PC_STORES]


# --- inputs (RP-1) ---

def _digest(data: bytes | None) -> str | None:
    return None if data is None else hashlib.sha256(data).hexdigest()


def _read_document(path: Path) -> tuple[bytes | None, dict | str | None]:
    """(raw bytes, document | "unreadable" | None when absent)."""
    if not path.exists():
        return None, None
    raw = path.read_bytes()
    try:
        doc = json.loads(raw)
    except ValueError:
        return raw, "unreadable"
    coins = doc.get("coins") if isinstance(doc, dict) else None
    if not isinstance(coins, dict) or not all(isinstance(c, dict) for c in coins.values()):
        return raw, "unreadable"
    return raw, doc


def _containment() -> tuple[bytes, list[str] | str]:
    directory = cache.CACHE_ROOT / "attention" / "_probes"
    outcomes, raw = set(), b""
    for path in sorted(directory.glob("browser_admission_*.json")):
        data = path.read_bytes()
        raw += path.name.encode() + b"\0" + data
        try:
            outcome = json.loads(data).get("outcome")
        except (ValueError, AttributeError):
            outcome = None
        outcomes.add(outcome if isinstance(outcome, str) and _CODE_RE.fullmatch(outcome) else "unknown")
    return raw, sorted(outcomes) if outcomes else "unknown"


def collect_inputs(day: date) -> dict:
    """Day D's evidence and a digest per input (`facts`, `completeness/<store>`, `containment`)."""
    facts_path = daily_facts.events_path(day)
    facts_raw = facts_path.read_bytes() if facts_path.exists() else None
    documents, digests = {}, {"facts": _digest(facts_raw)}
    for source in SOURCES:
        for store in _stores(source):
            raw, documents[store] = _read_document(_completeness_path(store, day))
            digests[f"completeness/{store}"] = _digest(raw)
    contain_raw, containment = _containment()
    digests["containment"] = _digest(contain_raw) if contain_raw else None
    return {"day": day, "events": daily_facts.read_events(day) if facts_raw is not None else [],
            "snapshots": {s: daily_facts.read_universe_snapshot(day, s) for s in SOURCES},
            "documents": documents, "containment": containment,
            "digests": {k: v for k, v in digests.items() if v is not None}}


def _has_inputs(inputs: dict) -> bool:
    return bool(inputs["events"]) or any(d is not None for d in inputs["documents"].values())


# --- per-coin method selection ---

def selected_methods(day: date, universe: Mapping[str, list[str]], *, window: int = DEFAULT_WINDOW,
                     config_path: Path | None = None, probe_path: Path | None = None) -> dict[str, dict]:
    """Per source and coin, the store `pick_source_impl` reads for the window ending `day` (None: no method usable),
    over the same known-at-time series as Discovery history (never a source-wide flag, never two stores mixed)."""
    cfg = discovery.load_config(config_path)
    recent, lag = int(cfg["recent_days"]), int(cfg["max_source_lag_days"])
    out: dict[str, dict] = {}
    for source, symbols in universe.items():
        stored = discovery_history._load(cfg, list(symbols), probe_path)
        picks = {}
        for sym in symbols:
            data = {k: s.at(day) for k, s in stored.items() if k[1] == sym}
            picked = discovery.pick_source_impl(source, cfg, data, sym, day, recent, window, lag)
            picks[sym] = None if picked is None else picked[0]
        out[source] = picks
    return out


# --- the report (pure) ---

def coverage(stored: int, eligible: int) -> str:
    """`100% stored` only when every eligible coin is stored; otherwise rounded DOWN, never shown as 100%."""
    if eligible == 0:
        return "no eligible coins"
    if stored == eligible:
        return "100% stored"
    pct = min(math.floor(stored * 1000 / eligible) / 10, 99.9)
    return f"{pct:g}% stored"


def _reason(coin: object) -> str:
    if not isinstance(coin, dict):
        return "not_recorded"
    reason = coin.get("reason")
    return reason if isinstance(reason, str) and _CODE_RE.fullmatch(reason) else "invalid_evidence"


def _method_section(doc: dict | str | None, eligible: list[str]) -> dict:
    if doc is None:
        return {"state": "no_data"}
    if doc == "unreadable":
        return {"state": "unknown", "reason": "unreadable"}
    coins = doc["coins"]
    stored = [s for s in eligible if _reason(coins.get(s)) == "fetched"]
    estimated = sum(coins[s].get("capped") is True for s in stored)
    missing = {s: _reason(coins.get(s)) for s in eligible if s not in stored}
    section = {"state": "ok", "eligible": len(eligible), "stored": len(stored), "exact": len(stored) - estimated,
               "estimated": estimated, "missing": len(missing),
               "reasons": dict(sorted(Counter(missing.values()).items())),
               "coverage": coverage(len(stored), len(eligible)), "missing_coins": dict(sorted(missing.items())),
               "coin_reasons": {s: _reason(coins.get(s)) for s in eligible}}
    if isinstance(doc.get("settled"), bool):
        section["settled"] = doc["settled"]
    return section


def _facts_sections(events: list[dict]) -> dict:
    summary = daily_facts.summarize(events)
    reddit_stores = set(_stores("reddit"))
    methods: dict[str, dict] = {}

    def method(source: str) -> dict:
        return methods.setdefault(source, {"polls": 0, "navigations": 0, "lanes": 0, "requests": 0,
                                           "stop_reasons": {}, "accounts": []})

    queryids: dict[str, str] = {}
    signals: dict[str, Counter] = {k: Counter() for k in (
        "challenge", "account_state", "handoff", "cooldown", "session_check", "mixed_call")}
    for ev in events:
        kind = ev.get("kind")
        if kind == "poll_result":
            m = method(str(ev.get("source")))
            m["polls"] += 1
            m["navigations"] += int(ev.get("navigations") or 0)
            m["lanes"] += int(ev.get("lanes") or 0)
            stop = str(ev.get("stop_reason"))
            m["stop_reasons"][stop] = m["stop_reasons"].get(stop, 0) + 1
            if ev.get("account") and ev["account"] not in m["accounts"]:
                m["accounts"].append(ev["account"])
        elif kind == "request_counter" and ev.get("source") in reddit_stores:
            method(str(ev["source"]))["requests"] += int(ev.get("requests") or 0)
        elif kind == "queryid_state":
            queryids[str(ev.get("operation"))] = str(ev.get("to_state"))
        elif kind == "challenge":
            signals["challenge"][str(ev.get("class"))] += 1
        elif kind == "account_state":
            signals["account_state"][f"{ev.get('state')}:{ev.get('reason')}"] += 1
        elif kind == "handoff":
            signals["handoff"][str(ev.get("reason"))] += 1
        elif kind == "cooldown":
            signals["cooldown"][str(ev.get("action"))] += 1
        elif kind == "session_check":
            signals["session_check"][str(ev.get("result_class"))] += 1
        elif kind == "mixed_call":
            signals["mixed_call"][str(ev.get("target"))] += 1
    for m in methods.values():
        m["stop_reasons"] = dict(sorted(m["stop_reasons"].items()))
        m["accounts"].sort()
    return {"x_accounts": {s: a for s, a in summary["accounts"].items() if s not in reddit_stores},
            "reddit_methods": dict(sorted(methods.items())),
            "queryids": dict(sorted(queryids.items())) if queryids else "unknown",
            "signals": {k: dict(sorted(v.items())) for k, v in signals.items()},
            "switches": summary["switches"]}


def build(inputs: dict, selected: Mapping[str, Mapping[str, str | None]] | str) -> dict:
    """The report body from `collect_inputs` and the per-coin selection (or "unknown" when it failed)."""
    day = inputs["day"]
    sources, per_source_method, coins = {}, {}, {}
    for source in SOURCES:
        snap = inputs["snapshots"][source]
        if snap is None:
            sources[source] = {"state": "no_data", "methods": {m: {"state": "no_data"} for m in _stores(source)}}
            continue
        eligible = sorted(snap["eligible_symbols"])
        order = [m for m in snap["method_order"] if m in registry.PC_STORES] or _stores(source)
        methods = {m: _method_section(inputs["documents"].get(m), eligible) for m in order}
        sel = selected if isinstance(selected, str) else selected.get(source, {})
        coins[source] = {s: {"selected_method": sel if isinstance(sel, str) else sel.get(s),
                             "methods": {m: sec["coin_reasons"][s] for m, sec in methods.items()
                                         if sec["state"] == "ok"}} for s in eligible}
        for m, sec in methods.items():
            if sec["state"] == "ok":
                per_source_method[f"{source}/{m}"] = {k: sec[k] for k in (
                    "eligible", "stored", "exact", "estimated", "missing", "reasons")}
            sec.pop("coin_reasons", None)
        sources[source] = {"state": "ok", "eligible": len(eligible),
                           "ambiguous": sorted(snap["ambiguous_symbols"]), "method_order": order, "methods": methods}
    return {"day": day.isoformat(), "sources": sources, "per_source_method": per_source_method, "coins": coins,
            **_facts_sections(inputs["events"]), "containment": inputs["containment"]}


def _counts(sec: dict) -> str:
    text = (f"eligible {sec['eligible']}, stored {sec['stored']}, exact {sec['exact']}, "
            f"estimated {sec['estimated']}, missing {sec['missing']}")
    if sec["reasons"]:
        text += " (" + ", ".join(f"{k} {v}" for k, v in sec["reasons"].items()) + ")"
    return f"{text}: {sec['coverage']}"


def render(report: dict) -> str:
    day = report["day"]
    lines = [f"Daily collection report {day} (revision {report.get('revision', 'unknown')})"]
    revisions = report.get("revisions") or []
    for rev in revisions:
        if rev["revision"] == 1:
            lines.append(f"first built at {rev['built_at']}")
        else:
            lines.append(f"revised at {rev['built_at']} (revision {rev['revision']}): inputs changed: "
                         + ", ".join(rev["changed"]))
    for source, src in report["sources"].items():
        if src["state"] != "ok":
            lines.append(f"[{source}] no data for {day} (no universe snapshot)")
            continue
        lines.append(f"[{source}] universe: {src['eligible']} eligible, {len(src['ambiguous'])} ambiguous")
        for m, sec in src["methods"].items():
            if sec["state"] == "no_data":
                lines.append(f"  {m}: no data for {day}")
            elif sec["state"] == "unknown":
                lines.append(f"  {m}: unknown ({sec['reason']})")
            else:
                settled = "" if "settled" not in sec else f" [{'settled' if sec['settled'] else 'not settled'}]"
                lines.append(f"  {m}: {_counts(sec)}{settled}")
                lines += [f"    {s} missing ({r})" for s, r in sec["missing_coins"].items()]
        picks = report["coins"].get(source, {})
        if picks:
            lines.append("  selected method per coin: " + ", ".join(
                f"{s} {c['selected_method'] or 'none'}" for s, c in picks.items()))
    for source, accounts in report["x_accounts"].items():
        for acct, a in sorted(accounts.items()):
            lines.append(f"X account {acct} ({source}): units {a['units']}, reads {a['reads']}, pages {a['pages']}")
    for store, m in report["reddit_methods"].items():
        stops = ", ".join(f"{k} {v}" for k, v in m["stop_reasons"].items()) or "none"
        lines.append(f"Reddit {store}: polls {m['polls']}, navigations {m['navigations']}, lanes {m['lanes']}, "
                     f"requests {m['requests']}, stops ({stops})")
    q = report["queryids"]
    lines.append("Query ids: " + (q if isinstance(q, str) else ", ".join(f"{k} {v}" for k, v in q.items())))
    for name, hist in report["signals"].items():
        if hist:
            lines.append(f"Signal {name}: " + ", ".join(f"{k} {v}" for k, v in hist.items()))
    c = report["containment"]
    lines.append("Browser containment: " + (c if isinstance(c, str) else ", ".join(c)))
    return "\n".join(lines) + "\n"


# --- revisions and writing (RP-3) ---

def read_report(day: date) -> dict | None:
    path = report_paths(day)[0]
    try:
        doc = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def rebuild(day: date, *, now: datetime, selector: Selector | None = None,
            only_if_inputs: bool = False) -> dict | None:
    """Build D's report when its inputs changed (idempotent); None when `only_if_inputs` and D has no evidence."""
    now = now.astimezone(timezone.utc) if now.tzinfo else now.replace(tzinfo=timezone.utc)
    if day >= now.date():
        raise ValueError("the report covers completed UTC days only")
    with _lock:
        inputs = collect_inputs(day)
        if only_if_inputs and not _has_inputs(inputs):
            return None
        digests = inputs["digests"]
        overall = hashlib.sha256(json.dumps(digests, sort_keys=True).encode()).hexdigest()
        prev = read_report(day)
        if prev and prev.get("schema") == SCHEMA_VERSION and prev.get("inputs_digest") == overall:
            return prev
        universe = {s: sorted(snap["eligible_symbols"]) for s, snap in inputs["snapshots"].items() if snap}
        try:
            selected = (selector or selected_methods)(day, universe) if universe else {}
        except Exception as exc:  # noqa: BLE001 - selection never stops the report; it prints unknown
            log.warning("daily report %s method selection unknown: %s", day.isoformat(), type(exc).__name__)
            selected = "unknown"
        report = build(inputs, selected)
        prev_rev = prev.get("revision") if prev else None
        revision = prev_rev + 1 if isinstance(prev_rev, int) and prev_rev > 0 else 1
        before = prev.get("inputs") if prev and isinstance(prev.get("inputs"), dict) else {}
        changed = sorted(k for k in set(digests) | set(before) if digests.get(k) != before.get(k))
        built_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        history = [r for r in (prev.get("revisions") or []) if isinstance(r, dict)] if prev else []
        history.append({"revision": revision, "built_at": built_at,
                        "reason": "initial" if revision == 1 else "inputs_changed", "changed": changed})
        report = {"schema": SCHEMA_VERSION, "revision": revision, "built_at": built_at, "inputs_digest": overall,
                  "inputs": digests, "revisions": history, **report}
        js, txt = report_paths(day)
        js.parent.mkdir(parents=True, exist_ok=True)
        # text first: the json (with the digest) is the commit marker, so a failure leaves the old revision current
        cache._atomic_write_bytes(render(report).encode("utf-8"), txt)
        cache._atomic_write_bytes(json.dumps(report, sort_keys=True, indent=1).encode("utf-8"), js)
        return report


def rebuild_recent(now: datetime, *, days: int = REBUILD_DAYS, selector: Selector | None = None) -> list[date]:
    """At a pass end: rebuild every recent completed day whose evidence changed (late settles revise D)."""
    today = now.astimezone(timezone.utc).date() if now.tzinfo else now.date()
    built = []
    for offset in range(1, days + 1):
        day = today - timedelta(days=offset)
        if rebuild(day, now=now, selector=selector, only_if_inputs=True) is not None:
            built.append(day)
    return built
