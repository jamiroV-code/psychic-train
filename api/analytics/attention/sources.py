"""Sources status (T106): what each Discovery input has stored, read from files and config only (no network).

Per series it reads only the `date` column of each eligible coin's file, cached per file by (mtime, size),
so a repeated call costs a stat per file. A coin counts as having data like live scoring does: the
registry's history gate (MIN_HISTORY_DAYS) and the source's newest day within `max_source_lag_days`.

W8f: a weighted source reports the store `source_impl` selects (the first with usable coins, else the first with
data, else the first); X in rotation mode is gated by `x_rotation_points` stored points and
`x_rotation_max_lag_days`. Each row carries a closed `reason` code beside its note; a failed or stale series is
`unavailable`, a short one `insufficient-history`.

W8e2: optional worker health is read from atomic state/completeness snapshots only. Collection-day counts
are distinct coin-days, excluding canaries, pages and account retries. The text separately labels the target
UTC day. Older files without attempt or scheduling evidence report unknown, never inferred zero.

Standalone collector: `collector` reads the collector's heartbeat file (`collector_heartbeat.status`) and repeats
each PC stream's health fields (X search, Reddit), also for a parked source; no worker state stays unknown.

Finish plan 06-11-26 (S-StatusAPI): optional, allowlisted fields read from the producers' nonsecret files only (no
network, writes or admission). `PC_STORES` keeps its stream-exclusion contract; each Reddit method gets its own row
from the SEPARATE method-health reader (`reddit_methods`), Reddit accounts their own model (`reddit_accounts`). All
of them stay omitted while their feature is off and no file exists, so the all-off wire shape is unchanged; a
configured feature without evidence reports `unknown`, never a guessed state.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd
from pydantic import ValidationError

from api.analytics.attention.discovery import (EXCHANGE_SERIES, FALLBACK_SERIES, SLOT, X_SOURCE, eligibility,
                                               load_config, source_impls, weights_for_day, x_setting)
from api.analytics.attention import narratives
from api.analytics.attention.universe import load_universe_rows
from api.data import cache
from api.data.attention import (collector_heartbeat, pc_pace, registry, store, trends_keywords, trends_runs,
                                universe_store, web_queries, x_pool)
from api.data.attention import pc_adapter as pa
from api.data.attention.types import MIN_HISTORY_DAYS
from api.models.discovery import (SAFE_CODE, DiscoveryAccountHealth, DiscoveryBrowserHealth, DiscoveryCollectorSource,
                                  DiscoveryCollectorStatus, DiscoveryDailyReportStatus, DiscoveryDoctorStatus,
                                  DiscoveryKeywordGap, DiscoveryQueryIdHealth, DiscoveryRedditAccountHealth,
                                  DiscoveryRedditMethodHealth, DiscoveryRelayRefusal, DiscoverySourceHealth,
                                  DiscoverySourceRow, DiscoverySourcesResponse, DiscoveryTrendsKeyword,
                                  DiscoveryTrendsWatch)

LABELS = {
    "wikipedia": "Wikipedia pageviews", "trends": "Google Trends", "reddit": "Reddit", "xsearch": "X search",
    "github_dev": "GitHub dev activity", "defillama": "DefiLlama", SLOT: "Exchange activity",
    "binance": "Binance volume", "coinbase": "Coinbase volume", "kraken": "Kraken volume",
    "hyperliquid": "Hyperliquid volume", FALLBACK_SERIES: "CoinGecko (volume fallback)",
    "universe": "Top-100 universe", "narratives": "Narratives file",
}
COVERAGE_ONLY_LABEL = "CoinGecko volume (coverage only)"   # T204: the fallback no longer votes

_file_cache: dict[str, tuple[int, int, int, date | None]] = {}   # path -> (mtime_ns, size, days, newest)


def clear_cache() -> None:
    _file_cache.clear()


PC_STORES = frozenset({"xsearch_web", "reddit_web"})
COLLECTOR_SOURCES = (("xsearch", "xsearch_web"), ("reddit", "reddit_web"))   # (Discovery id, PC stream store)
_PROXY_ACCOUNT_FIELDS = frozenset({
    "proxy_id", "proxy_state", "proxy_reason", "proxy_checked_at", "proxy_quarantine_until",
    "region", "connection_style", "identity_revision",
})
_FINISH_ACCOUNT_FIELDS = frozenset({"endpoint_state", "behaviour", "harvest", "ct0_rotations_seen"})
# Reddit live method store -> its `reddit_live_methods` switch; the feeds have no switch.
REDDIT_LIVE_STORES = {"reddit_live_browser": "browser", "reddit_live_gql": "gql_anon"}
REDDIT_METHOD_LABELS = {"reddit_live_browser": "Reddit live (browser)", "reddit_live_gql": "Reddit live (GraphQL)",
                        "reddit_web": "Reddit web feed", "reddit_stream": "Reddit stream"}


def _json_file(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def _timestamp(value) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.astimezone(UTC) if parsed.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def _collector():
    try:
        return web_queries.load().config
    except (OSError, ValueError):
        return None


def _accounts(now: datetime, health: DiscoverySourceHealth) -> None:
    """Reuse the pool's read-only loader and lock semantics, never its mutating methods or account DBs."""
    cfg = _collector()
    path = cache.CACHE_ROOT / "attention" / "_pc_state" / "x_pool.json"
    if cfg is None or not cfg.x_accounts:
        return
    ages = _json_file(Path(cfg.x_accounts_db_path) / "cookie_ages.json") if cfg.x_accounts_db_path else None
    if not path.exists():
        return
    try:
        pool = x_pool.from_config(cfg, clock=lambda: now)
        snapshot = pool.health()
    except x_pool.XPoolStateError:
        health.paused, health.pause_reason, health.pause_until = True, "state_error", None
        return
    accounts = []
    try:
        for account in snapshot["accounts"]:
            refreshed = _timestamp((ages or {}).get(account["label"]))
            # Only public fields cross this boundary, never private resolver data.
            public = {key: value for key, value in account.items()
                      if key in DiscoveryAccountHealth.model_fields and key != "cookie_age_days"}
            public["cookie_age_days"] = max(0, (now - refreshed).days) if refreshed else None
            accounts.append(_project_account(public))
    except ValidationError:
        # Invalid legacy data makes the complete snapshot unreadable. Never
        # stringify validation errors: they contain the rejected input.
        health.paused, health.pause_reason, health.pause_until = True, "state_error", None
        return
    health.accounts_active, health.accounts_total = snapshot["active"], snapshot["total"]
    health.accounts = accounts
    if snapshot["pause_reason"]:
        # One loaded snapshot: do not re-read a file that the producer may replace concurrently.
        health.paused, health.pause_reason = True, snapshot["pause_reason"]
        health.pause_until = None if pool._s["stopped"] else pool._s["pause_until"]


def _project_account(public: dict) -> DiscoveryAccountHealth:
    """Refuse a malformed group whole (proxy tuple, finish fields) and keep the rest: retaining a healthy state
    with malformed evidence would turn an unknown into a false success. A malformed legacy field still raises."""
    def without(fields: frozenset, extra: dict) -> dict:
        return {**{k: v for k, v in public.items() if k not in fields}, **extra}

    proxy = {"proxy_state": "unknown", "proxy_reason": "proxy_response"}
    finish = {"endpoint_state": "unknown"} if _FINISH_ACCOUNT_FIELDS & public.keys() else {}
    candidates = (public, without(_FINISH_ACCOUNT_FIELDS, finish), without(_PROXY_ACCOUNT_FIELDS, proxy),
                  without(_PROXY_ACCOUNT_FIELDS | _FINISH_ACCOUNT_FIELDS, {**proxy, **finish}))
    for candidate in candidates[:-1]:
        try:
            return DiscoveryAccountHealth(**candidate)
        except ValidationError:
            pass
    return DiscoveryAccountHealth(**candidates[-1])


def _days_since(value, now: datetime) -> int | None:
    stamp = _timestamp(value)
    return max(0, (now - stamp).days) if stamp else None


def _utc_text(value) -> str | None:
    """A producer timestamp passed on only when it is a UTC ISO timestamp, else unknown."""
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return value if parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0) else None


def _code(value) -> str | None:
    return value if isinstance(value, str) and SAFE_CODE.fullmatch(value) else None


def _count(value) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _queryids(cfg, now: datetime) -> DiscoveryQueryIdHealth | None:
    """X query-id registry state (`_pc_state/x_queryids.json`, S-XProto): omitted while off and never checked."""
    mode = cfg.x_queryid_mode if cfg is not None else "off"
    path = cache.CACHE_ROOT / "attention" / "_pc_state" / "x_queryids.json"
    if mode == "off" and not path.exists():
        return None
    doc = _json_file(path)
    operations = doc.get("operations") if doc else None
    if not isinstance(operations, dict) or not all(isinstance(o, dict) for o in operations.values()):
        return DiscoveryQueryIdHealth(mode=mode)
    active = [o.get("active") for o in operations.values()]
    active = [a for a in active if isinstance(a, dict)]
    sources = {a.get("source") for a in active}
    source = None if not sources or not sources <= {"pinned", "bundle"} else (
        sources.pop() if len(sources) == 1 else "mixed")
    ages = [_days_since(a.get("adopted_at"), now) for a in active]
    state = doc.get("check_state")
    return DiscoveryQueryIdHealth(
        mode=mode, state=state if state in ("ok", "candidate", "stale", "blocked", "refused_by_policy") else "unknown",
        active_source=source, active_age_days=max(ages) if ages and None not in ages else None,
        last_check=_utc_text(doc.get("last_check")))


def _settled_day(store_id: str) -> str | None:
    """Newest UTC day with a valid completeness document for this store (the method's own, never another's)."""
    directory = cache.CACHE_ROOT / "attention" / store_id / "_meta" / "_completeness"
    days = []
    for path in directory.glob("*.json"):
        try:
            day = date.fromisoformat(path.stem)
        except ValueError:
            continue
        doc = _json_file(path)
        if doc and isinstance(doc.get("coins"), dict):
            days.append(day)
    return max(days).isoformat() if days else None


def _live_method(store_id: str, cfg) -> DiscoveryRedditMethodHealth:
    """A live method's row from its worker-written `_pc_state/reddit_live/<store>_health.json` (S-RCore-B)."""
    label = REDDIT_METHOD_LABELS[store_id]
    if REDDIT_LIVE_STORES[store_id] not in cfg.reddit_live_methods:
        return DiscoveryRedditMethodHealth(method=store_id, label=label, state="disabled", reason="method_disabled",
                                           last_settled_day=_settled_day(store_id))
    doc = _json_file(cache.CACHE_ROOT / "attention" / "_pc_state" / "reddit_live" / f"{store_id}_health.json") or {}
    state = doc.get("state")
    lanes = doc.get("lanes")
    if not (isinstance(lanes, dict) and set(lanes) <= {"posts", "comments"} and all(
            type(v) in (int, float) and not isinstance(v, bool) and 0 <= v <= 1 for v in lanes.values())):
        lanes = None
    return DiscoveryRedditMethodHealth(
        method=store_id, label=label,
        state=state if state in ("ok", "degraded", "needs_probe", "disabled", "blocked", "stale") else "unknown",
        reason=_code(doc.get("reason")), last_settled_day=_settled_day(store_id), lanes=lanes,
        comments_scope="threads_opened" if doc.get("comments_scope") == "threads_opened" else None,
        requests_today=_count(doc.get("requests_today")), cap=_count(doc.get("cap")))


def _feed_method(store_id: str, day: date, now: datetime, known: dict) -> DiscoveryRedditMethodHealth:
    """A feed's row from the same worker health the Sources row uses (no second interpretation)."""
    # The stream keeps no pace state (`pc_pace.SOURCE_DELAYS`): its row stays unknown rather than guessed.
    h = known[store_id] if store_id in known else (
        _health(store_id, day, now) if store_id in pc_pace.SOURCE_DELAYS else None)
    fields = {"method": store_id, "label": REDDIT_METHOD_LABELS[store_id], "last_settled_day": _settled_day(store_id)}
    if h is None:
        return DiscoveryRedditMethodHealth(**fields)
    state, reason = ("degraded", _code(h.pause_reason)) if h.paused else ("stale", None) if h.stale else (
        "ok" if h.stale is False else "unknown", None)
    return DiscoveryRedditMethodHealth(**fields, state=state, reason=reason, requests_today=h.budget_used,
                                       cap=h.effective_budget)


def reddit_methods(cfg, day: date, now: datetime, known: dict | None = None) -> list[DiscoveryRedditMethodHealth] | None:
    """The separate method-health reader: one row per Reddit method, never merged. Omitted (None) while no live
    method and no Reddit account is configured, so the all-off rows keep their pre-finish shape."""
    if cfg is None or not (cfg.reddit_live_methods or cfg.reddit_browser_accounts):
        return None
    return [_live_method(m, cfg) if m in REDDIT_LIVE_STORES else _feed_method(m, day, now, known or {})
            for m in web_queries.REDDIT_METHODS]


def reddit_accounts(cfg, now: datetime) -> list[DiscoveryRedditAccountHealth] | None:
    """Configured Reddit accounts from `_pc_state/reddit_accounts.json` (`{"accounts": {label: entry}}`, S-RAcct-A)
    and `reddit_account_ready.json` (`{"ready": {label: marked ISO day}}`; ready from the next UTC day). Only
    configured labels are shown; an absent or malformed entry is `unknown`. None while no account is configured."""
    if cfg is None or not cfg.reddit_browser_accounts:
        return None
    root = cache.CACHE_ROOT / "attention" / "_pc_state"
    doc = _json_file(root / "reddit_accounts.json")
    entries = doc.get("accounts") if doc and isinstance(doc.get("accounts"), dict) else {}
    ready_doc = _json_file(root / "reddit_account_ready.json")
    marks = ready_doc.get("ready") if ready_doc and isinstance(ready_doc.get("ready"), dict) else None
    today = now.date()
    out = []
    for account in cfg.reddit_browser_accounts:
        label = account["label"]
        entry = entries.get(label)
        ready = None
        if marks is not None:
            try:
                ready = label in marks and date.fromisoformat(marks[label]) < today
            except (TypeError, ValueError):
                ready = None
        if not isinstance(entry, dict):
            out.append(DiscoveryRedditAccountHealth(label=label, ready=ready,
                                                    cap=cfg.reddit_browser_account_daily_cap))
            continue
        state = entry.get("state")
        used = _count(entry.get("reads_used"))
        proxy = entry.get("proxy_state")
        out.append(DiscoveryRedditAccountHealth(
            label=label, state=state if state in ("active", "resting", "paused", "locked") else "unknown",
            reason=_code(entry.get("reason")),
            reads_today=(used if entry.get("reads_day") == today.isoformat() else 0) if used is not None else None,
            cap=cfg.reddit_browser_account_daily_cap, rest_until=_utc_text(entry.get("rest_until")), ready=ready,
            session_state=_code(entry.get("session_state")),
            session_checked_at=_utc_text(entry.get("session_checked_at")),
            proxy_state=proxy if proxy in ("direct", "unknown", "healthy", "quarantined", "blocked") else None))
    return out


def _daily_report() -> DiscoveryDailyReportStatus | None:
    """Newest `_reports/daily_report_<D>.json` (S-Report); a malformed one keeps its day with counts unknown."""
    directory = cache.CACHE_ROOT / "attention" / "_reports"
    days = []
    for path in directory.glob("daily_report_*.json"):
        try:
            days.append((date.fromisoformat(path.stem.removeprefix("daily_report_")), path))
        except ValueError:
            continue
    if not days:
        return None
    day, path = max(days)
    doc = _json_file(path) or {}
    try:
        counts = doc.get("per_source_method")
        report = DiscoveryDailyReportStatus(day=day.isoformat(), revision=_count(doc.get("revision")),
                                            per_source_method=counts if isinstance(counts, dict) and counts else None)
    except ValidationError:
        return DiscoveryDailyReportStatus(day=day.isoformat(), revision=_count(doc.get("revision")))
    if report.per_source_method:
        report.complete = all(c.eligible > 0 and c.stored == c.eligible for c in report.per_source_method.values())
    return report


def _doctor() -> DiscoveryDoctorStatus | None:
    """`_reports/doctor.json` (S-OpsDoctor): verdict and counts only; unreadable → UNKNOWN."""
    path = cache.CACHE_ROOT / "attention" / "_reports" / "doctor.json"
    if not path.exists():
        return None
    doc = _json_file(path) or {}
    state = doc.get("state")
    size = lambda v: len(v) if isinstance(v, list) else _count(v)
    return DiscoveryDoctorStatus(state=state if state in ("PASS", "WARN", "FAIL") else "UNKNOWN",
                                 checked_at=_utc_text(doc.get("checked_at")), failures=size(doc.get("failures")),
                                 warnings=size(doc.get("warnings")))


def _browser() -> DiscoveryBrowserHealth | None:
    """`_pc_state/browser_health.json` (S-Relay): top refused hostnames (≤ 5) and the profile state."""
    path = cache.CACHE_ROOT / "attention" / "_pc_state" / "browser_health.json"
    if not path.exists():
        return None
    doc = _json_file(path) or {}
    refusals = doc.get("relay_refusals")
    rows = []
    if isinstance(refusals, dict):
        for host, count in sorted(refusals.items(), key=lambda kv: (-(_count(kv[1]) or 0), str(kv[0]))):
            try:
                rows.append(DiscoveryRelayRefusal(host=host, count=count))
            except (ValidationError, TypeError):
                continue
            if len(rows) == 5:
                break
    state = doc.get("profile_state")
    return DiscoveryBrowserHealth(relay_refusals=rows, profile_state=state if state in (
        "ok", "missing", "policy_unsatisfied") else "unknown")


def _completeness(store_id: str, day: date, now: datetime, health: DiscoverySourceHealth) -> None:
    directory = cache.CACHE_ROOT / "attention" / store_id / "_meta" / "_completeness"
    today_attempted = today_fetched = 0
    known_today = directory.exists()
    target = None
    for path in sorted(directory.glob("*.json")):
        doc = _json_file(path)
        coins = doc.get("coins") if doc else None
        if not isinstance(coins, dict) or not all(isinstance(c, dict) for c in coins.values()):
            known_today = False
            continue
        if path.stem == day.isoformat():
            target = coins
        for coin in coins.values():
            collected = _timestamp(coin.get("collected_at"))
            if collected and collected.date() == now.date():
                if coin.get("attempted") is None:
                    known_today = False
                else:
                    today_attempted += coin.get("attempted") is True
                    today_fetched += coin.get("reason") == "fetched"
    if known_today:
        health.attempted, health.fetched = today_attempted, today_fetched
    if target is None:
        return
    reasons = Counter()
    times = []
    fetched = capped = attempted = 0
    attempts_known = True
    for coin in target.values():
        reason = coin.get("reason")
        if not isinstance(reason, str) or not re.fullmatch(r"[a-z_]{1,40}", reason):
            reason = "invalid_evidence"
        if reason == "fetched":
            fetched += 1
            capped += coin.get("capped") is True
        else:
            reasons[reason] += 1
        attempts_known &= isinstance(coin.get("attempted"), bool)
        attempted += coin.get("attempted") is True
        collected = _timestamp(coin.get("collected_at"))
        if collected:
            times.append(collected)
    health.completeness_attempted = attempted if attempts_known else None
    health.completeness_fetched, health.capped = fetched, capped
    health.missing, health.missing_reasons = sum(reasons.values()), dict(sorted(reasons.items()))
    health.newest_age_hours = round(max(0, (now - max(times)).total_seconds()) / 3600, 1) if times else None


def _idle_until(state: dict) -> datetime | None:
    """When a by-design wait in the persisted worker state ends: a spent day's budget waits for the next UTC day's
    first due time (00:00 plus the behind delay, as the worker schedules it); a timed warning pause waits for its
    `pause_until`. None when the worker is not waiting on purpose (an owner-action pause has no end)."""
    ends = []
    spent = state["spent_day"] or (state["budget_day"] if state["used"] >= state["effective"] else None)
    if spent:
        ends.append(datetime.combine(date.fromisoformat(spent) + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
                    + timedelta(seconds=pc_pace.BEHIND_DELAY_S))
    until = _timestamp(state["pause_until"])
    if until and state["pause_reason"] not in pa.OWNER_ACTION_REASONS:
        ends.append(until)
    return max(ends, default=None)


def _health(store_id: str, day: date, now: datetime) -> DiscoverySourceHealth | None:
    path = pc_pace.state_path(store_id)
    if not path.exists():
        return None
    h = DiscoverySourceHealth(collection_day=now.date().isoformat(), completeness_day=day.isoformat(),
                              completeness="")
    state = _json_file(path)
    if not pc_pace._valid_state(state):
        h.paused, h.pause_reason, h.completeness = True, "state_error", "worker state unreadable"
        return h
    h.last_unit_at = state["last_unit_at"]
    until = _timestamp(state["pause_until"])
    if state["pause_reason"] in pa.OWNER_ACTION_REASONS or (state["pause_reason"] and until and now < until):
        h.paused, h.pause_reason, h.pause_until = True, state["pause_reason"], state["pause_until"]
    h.budget_used = state["used"] if state["budget_day"] == h.collection_day else 0
    h.effective_budget = state["effective"]
    h.budget_spent = state["spent_day"] == h.collection_day or h.budget_used >= h.effective_budget
    idle_until = _idle_until(state)
    schedule = _json_file(path.with_name(f"{store_id}_health.json")) or {}
    gap = schedule.get("expected_gap_s")
    if (schedule.get("mode") in ("baseline", "degraded") and isinstance(gap, (int, float))
            and not isinstance(gap, bool) and math.isfinite(gap) and gap > 0):
        h.mode, h.expected_gap_s = schedule["mode"], gap
        # Waiting on purpose is not stale: the gap counts from the later of the last unit and the wait's end (AC39).
        last = max(filter(None, (_timestamp(h.last_unit_at), idle_until)), default=None)
        h.stale = last is None or (now - last).total_seconds() > 2 * gap
    if store_id == "xsearch_web":
        _accounts(now, h)
        h.queryids = _queryids(_collector(), now)
    _completeness(store_id, day, now, h)
    count = lambda value: "unknown" if value is None else str(value)
    h.completeness = (f"{day.isoformat()}: attempted {count(h.completeness_attempted)}, "
                      f"fetched {count(h.completeness_fetched)}, missing {count(h.missing)}")
    if h.missing_reasons:
        h.completeness += " (" + ", ".join(f"{k} {v}" for k, v in h.missing_reasons.items()) + ")"
    h.completeness += f", capped {count(h.capped)}, newest "
    h.completeness += f"{h.newest_age_hours:g}h old" if h.newest_age_hours is not None else "unknown"
    if h.stale:
        h.completeness += "; stale"
    elif idle_until and now < idle_until:
        h.completeness += "; waiting for next UTC day"
    try:
        h.free_disk_bytes = shutil.disk_usage(cache.CACHE_ROOT).free
    except OSError:
        pass
    return h


def _collector_status(rows: list[DiscoverySourceRow], day: date, now: datetime) -> DiscoveryCollectorStatus:
    """The collector box: the heartbeat's state and each PC stream's health (reused from its row when computed)."""
    beat = collector_heartbeat.status(now)
    known = {r.impl: r.health for r in rows if r.impl in PC_STORES}
    reddit_row = next((r.health for r in rows if r.id == "reddit" and r.health is not None), None)
    sources = []
    for sid, store_id in COLLECTOR_SOURCES:
        h = known[store_id] if store_id in known else _health(store_id, day, now)
        fields = {} if h is None else {
            "last_unit_at": h.last_unit_at, "paused": h.paused, "pause_reason": h.pause_reason,
            "pause_until": h.pause_until, "stale": h.stale, "budget_used": h.budget_used,
            "effective_budget": h.effective_budget}
        if sid == "xsearch":
            schedule = _json_file(pc_pace.state_path(store_id).with_name(f"{store_id}_health.json")) or {}
            keys = ("capacity_reads", "need_reads", "shortfall_reads", "backlog_reads")
            # Only today's scheduling evidence describes today's capacity; stale/malformed is unknown.
            observed = _timestamp(schedule.get("observed_at"))
            target = (now.date() - timedelta(days=1)).isoformat()
            if (observed and observed.date() == now.date() and schedule.get("sizing_day") == target
                    and all(type(schedule.get(k)) is int and schedule[k] >= 0 for k in keys)):
                fields.update({k: schedule[k] for k in keys})
                fields["sizing_day"] = target
        if sid == "reddit":
            fields["methods"] = (reddit_row.methods if reddit_row is not None
                                 else reddit_methods(_collector(), day, now, {store_id: h} if h else None))
        sources.append(DiscoveryCollectorSource(id=sid, label=LABELS[sid], has_state=h is not None, **fields))
    return DiscoveryCollectorStatus(state=beat["state"], reason=beat["reason"], started_at=beat["started_at"],
                                    last_beat=beat["last_beat"], age_s=beat["age_s"], mode=beat["mode"],
                                    version=beat["version"], running_sources=beat["sources"], sources=sources,
                                    daily_report=_daily_report(), doctor=_doctor(), browser=_browser())


def _reddit_health(h: DiscoverySourceHealth | None, impl: str | None, day: date,
                   now: datetime) -> DiscoverySourceHealth | None:
    """Attach the Reddit method rows and the Reddit accounts to the Reddit row (whichever method it reports).
    Without worker state for that method a bare health line carries them; all off leaves the row unchanged."""
    cfg = _collector()
    methods = reddit_methods(cfg, day, now, {impl: h} if h is not None else None)
    accounts = reddit_accounts(cfg, now)
    if methods is None and accounts is None:
        return h
    if h is None:
        h = DiscoverySourceHealth(collection_day=now.date().isoformat(), completeness_day=day.isoformat(),
                                  completeness="no worker state for this method")
    h.methods = methods
    if accounts is not None:
        h.accounts = accounts
        h.accounts_active = sum(a.state == "active" for a in accounts)
        h.accounts_total = len(accounts)
    return h


def _scan(source: str, symbol: str) -> tuple[int, date | None]:
    """(stored days, newest date) of one file; (0, None) when missing or unreadable."""
    path = store.store_path(source, symbol)
    try:
        st = path.stat()
    except OSError:
        return 0, None
    hit = _file_cache.get(str(path))
    if hit and hit[:2] == (st.st_mtime_ns, st.st_size):
        return hit[2], hit[3]
    try:
        dates = pd.read_parquet(path, columns=["date"])["date"]
        days, newest = len(dates), (pd.Timestamp(dates.max()).date() if len(dates) else None)
    except Exception:   # unreadable file: report it as no data, never a 500
        days, newest = 0, None
    _file_cache[str(path)] = (st.st_mtime_ns, st.st_size, days, newest)
    return days, newest


class _Series:
    def __init__(self, source: str, coins: list[str], end: date, max_lag: int, gate: int = MIN_HISTORY_DAYS):
        scans = {c: _scan(source, c) for c in coins}
        self.gate = gate
        self.history_days = max((n for n, _ in scans.values()), default=0)
        stored = [d for _, d in scans.values() if d is not None]
        self.newest = max(stored, default=None)
        self.usable = {c for c, (n, d) in scans.items()
                       if n >= gate and d is not None and (end - d).days <= max_lag}
        self.stale = bool(stored) and self.history_days >= gate and not self.usable


def _state(store_id: str, s: _Series, probed: bool, x_live: bool) -> tuple[str, str, str]:
    """(state, note, reason) of one store; `store_id` is the official X store only when X_LIVE applies."""
    if store_id == "xsearch" and not x_live:
        return "off", "X search is off (X_LIVE not set): dry run only", "x_live_off"
    if not probed:
        return "not-probed", "not probed yet", "not_probed"
    if s.usable:
        return "ok", "", ""
    if s.stale:
        return "unavailable", f"stale: newest {s.newest}", "stale"
    if s.history_days:
        return "insufficient-history", f"insufficient history {s.history_days}/{s.gate}", "insufficient_history"
    return "unavailable", "no stored data", "no_stored_data"


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _helper(sid: str, snap: dict | None, key: str, what: str) -> DiscoverySourceRow:
    rows = (snap or {}).get(key, [])
    ok = bool(snap) and bool(rows)
    return DiscoverySourceRow(id=sid, label=LABELS[sid], kind="helper", weight=None,
                              state="ok" if ok else "unavailable", newest=str(snap["date"]) if snap and snap.get("date") else None,
                              history_days=0, coins_with_data=len(rows), eligible_size=0,
                              note="" if ok else f"{what} not downloaded yet", reason="" if ok else "no_stored_data")


def _narratives_row() -> DiscoverySourceRow:
    """Helper row (U2): the narratives file that Discovery membership comes from; `ok` when it loads."""
    try:
        doc = narratives.load_narratives()
    except (OSError, ValueError) as exc:
        return DiscoverySourceRow(id="narratives", label=LABELS["narratives"], kind="helper", weight=None,
                                  state="unavailable", newest=None, history_days=0, coins_with_data=0,
                                  eligible_size=0, note=f"narratives file invalid: {exc}", reason="invalid_file")
    coins = {c["symbol"] for n in doc["narratives"] for c in n["coins"]}
    return DiscoverySourceRow(id="narratives", label=LABELS["narratives"], kind="helper", weight=None, state="ok",
                              newest=doc["as_of"], history_days=0, coins_with_data=len(coins), eligible_size=0,
                              note="status proposed" if doc["status"] == "proposed" else "")


def _trends_keyword(eligible: list[str]) -> DiscoveryTrendsKeyword:
    """Read from the keyword file with the runner's own rule (`keyword_status`), so the two cannot disagree."""
    km, _ = trends_keywords.safe_load_merged()
    cov = trends_keywords.coverage(km, eligible)
    return DiscoveryTrendsKeyword(eligible_size=cov.eligible, with_keyword=cov.with_keyword,
                                  missing=[DiscoveryKeywordGap(symbol=s, detail=st) for s, st in cov.missing])


def build_sources(today: date, *, probe_path: Path | None = None, universe_path: Path | None = None,
                  config_path: Path | None = None, now: datetime | None = None) -> DiscoverySourcesResponse:
    cfg = load_config(config_path)
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(UTC)
    end = today - timedelta(days=1)
    max_lag = int(cfg["max_source_lag_days"])
    rows, _ = load_universe_rows(universe_path)
    eligible = eligibility(cfg, rows).eligible if rows else []
    probed = registry.load_probe_records(probe_path)
    x_live = os.environ.get("X_LIVE") == "1"
    n = len(eligible)
    coverage_only = weights_for_day(cfg, end)["fallback_coverage_only"]

    def series(sid: str, name: str, lag: int = max_lag, gate: int = MIN_HISTORY_DAYS) -> tuple:
        s = _Series(name, eligible, end, lag, gate)
        return (s, *_state(name, s, name in probed or name in registry.PROBE_EXEMPT, x_live))

    def weighted_series(sid: str) -> tuple[tuple, str]:
        """(series tuple, store) of the `source_impl` store this row reports."""
        lag, gate = max_lag, MIN_HISTORY_DAYS
        if sid == X_SOURCE and x_setting(cfg, "x_discovery_mode") == "rotation":
            lag, gate = int(x_setting(cfg, "x_rotation_max_lag_days")), int(x_setting(cfg, "x_rotation_points"))
        found = [(series(sid, m, lag, gate), m) for m in impls[sid]]
        return next((f for f in found if f[0][0].usable), None) or next(
            (f for f in found if f[0][0].history_days), found[0])

    def row(sid, kind, weight, s, state, note, reason, impl=None) -> DiscoverySourceRow:
        health = _health(impl, end, now) if impl in PC_STORES else None
        if sid == "reddit":
            health = _reddit_health(health, impl, end, now)
        return DiscoverySourceRow(id=sid, label=LABELS[sid], kind=kind, weight=weight, state=state,
                                  newest=_iso(s.newest), history_days=s.history_days,
                                  coins_with_data=len(s.usable), eligible_size=n, note=note, reason=reason,
                                  impl=impl, health=health)

    impls = source_impls(cfg)

    out: list[DiscoverySourceRow] = []
    members: dict[str, tuple] = {m: series(m, ser) for m, ser in EXCHANGE_SERIES.items()}
    fallback = series(FALLBACK_SERIES, FALLBACK_SERIES)
    for sid, w in cfg["source_weights"].items():
        if w <= 0:   # parked (T130): not fetched, not failing, not counted
            out.append(DiscoverySourceRow(id=sid, label=LABELS[sid], kind="weighted", weight=w, state="off",
                                          newest=None, history_days=0, coins_with_data=0, eligible_size=n,
                                          note="parked: weight 0, not fetched", reason="parked"))
            continue
        if sid != SLOT:
            found, impl = weighted_series(sid)
            out.append(row(sid, "weighted", w, *found, impl=impl))
            continue
        every = [members[m][0] for m in EXCHANGE_SERIES]
        agg = _Series.__new__(_Series)   # per coin: any exchange, else the CoinGecko fallback (as live scoring does)
        agg.usable = set().union(*(e.usable for e in every), fallback[0].usable)
        agg.history_days = max(e.history_days for e in every + [fallback[0]])
        agg.newest = max((e.newest for e in every + [fallback[0]] if e.newest), default=None)
        agg.stale = False
        via_fallback = fallback[0].usable - set().union(*(e.usable for e in every))
        note = (f"{len(via_fallback)} of {len(agg.usable)} coins use the CoinGecko volume fallback"
                + (" (coverage only, never a rising vote)" if coverage_only else "")
                if via_fallback else "" if agg.usable else "no exchange or CoinGecko volume data")
        out.append(row(SLOT, "weighted", w, agg, "ok" if agg.usable else "unavailable", note,
                       "" if agg.usable else "no_stored_data"))
    for m in EXCHANGE_SERIES:
        out.append(row(m, "exchange-member", cfg["exchange_sub_weights"].get(m), *members[m]))
    fb = row(FALLBACK_SERIES, "fallback", None, *fallback)
    out.append(fb.model_copy(update={"label": COVERAGE_ONLY_LABEL}) if coverage_only else fb)
    snap = universe_store.read_latest()
    if snap and isinstance(snap.get("coins"), list):   # T223: the 120-row snapshot still reports the top 100
        snap = {**snap, "coins": [r for r in snap["coins"]
                                  if not (isinstance(r, dict) and isinstance(r.get("rank"), int) and r["rank"] > 100)]}
    out.append(_helper("universe", snap, "coins", "top-100 snapshot"))
    out.append(_narratives_row())

    weighted = [r for r in out if r.kind == "weighted" and (r.weight or 0) > 0]
    live = [r for r in weighted if r.state == "ok"]
    return DiscoverySourcesResponse(
        as_of=end.isoformat(), universe_size=len(rows), eligible_size=n, live_sources=len(live),
        total_sources=len(weighted), live_weight=sum(r.weight or 0 for r in live),
        newest=max((r.newest for r in live if r.newest), default=None), sources=out,
        trends_keyword=_trends_keyword(eligible),
        trends_watch=[DiscoveryTrendsWatch(**w) for w in trends_runs.watch_list(today)],
        collector=_collector_status(out, end, now))
