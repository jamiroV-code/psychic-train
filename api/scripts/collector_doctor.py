"""S-OpsDoctor (OD-1, AC11/AC16/AC17/AC20): one-command self-check of the collector's owner inputs and subsystems.

    uv run --project api --frozen --group xreader python -m api.scripts.collector_doctor \
        [--queries ABS_PATH] [--json] [--live] [--selftest]

Every check returns PASS, WARN, FAIL or UNKNOWN with a reason code and a fix hint. UNKNOWN is never PASS: absent or
unreadable evidence is UNKNOWN, a missing owner input is WARN, a broken or unsafe one is FAIL. Exit codes: 2 any
FAIL; 1 any WARN or UNKNOWN; 0 only when every check is PASS.

Offline and read-only: no network, no firewall or scheduled-task writes, no pool or account mutation. The two
read-only OS queries (`firewall_rule`, `scheduled_tasks`) and the `--selftest` run go through injected runners.
Output carries check names, states, codes and counts only: never a secret, path, IP, hostname or label value.

`--live` adds the LIVE-READY gate: the recorded owner-approved live probe evidence (PX1-PX6, PR1/PR2 verify, PR5).
Absent evidence is UNKNOWN (`needs_probe`); a failing live gate blocks LIVE-READY only, never collection.
`--selftest` runs `python -m api.tests.cycle.acceptance` through `selftest_runner(argv) -> exit code`; its pass
proves the synthetic cycle only and never turns a pending live check into PASS.

Writes `<cache>/attention/_reports/doctor.json` in the S-StatusAPI layout
`{state, checked_at, failures, warnings}` (plus `checks`: name/state/reason only).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from api.data import cache

PASS, WARN, FAIL, UNKNOWN = "PASS", "WARN", "FAIL", "UNKNOWN"
STATES = (PASS, WARN, FAIL, UNKNOWN)
FIREWALL_RULE_NAME = "mysite-collector-browser-block"  # OD-5 text generator's DisplayName
TASK_NAMES = ("mysite-collector", "mysite-collector-doctor")  # OD-3
FEED_END = date(2026, 11, 13)  # the public Reddit feeds end (plan Context); reddit_web/reddit_stream go stale
FEED_METHODS = ("reddit_web", "reddit_stream")
X_SIZING_ABOUT, X_SIZING_WORST = 4, 6  # X accounts needed (about 4, worst case 6)
DISK_FAIL_MB, DISK_WARN_MB = 1024, 5120
LIVE_PROBES = (("PX1", "observe"), ("PX2", "observe"), ("PX3", "observe"), ("PX4", "observe"),
               ("PX5", "observe"), ("PX6", "observe"), ("PR1", "verify"), ("PR2", "verify"), ("PR5", "observe"))
SELFTEST_ARGV = (sys.executable, "-m", "api.tests.cycle.acceptance")
DOCTOR_FILE = "doctor.json"


@dataclass(frozen=True)
class Check:
    name: str
    state: str
    reason: str
    fix: str = ""


def _query_argv(script: str) -> list[str]:
    return ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]


def firewall_query_argv() -> list[str]:
    """Read-only: counts the OD-5 rule by its display name (Get- only, never New-/Set-/Remove-)."""
    return _query_argv(f"@(Get-NetFirewallRule -DisplayName '{FIREWALL_RULE_NAME}' -ErrorAction SilentlyContinue).Count")


def task_query_argv(name: str) -> list[str]:
    """Read-only: counts the scheduled task by name (Get- only)."""
    return _query_argv(f"@(Get-ScheduledTask -TaskName '{name}' -ErrorAction SilentlyContinue).Count")


def default_query_runner(argv) -> tuple[int, str]:
    """Run one read-only OS query; (exit code, stdout). Windows only; elsewhere (-1, "")."""
    if os.name != "nt":
        return -1, ""
    try:
        done = subprocess.run(list(argv), capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return -1, ""
    return done.returncode, done.stdout


def default_selftest_runner(argv) -> int:
    return subprocess.run(list(argv), check=False).returncode


def _private_verifier(path: Path) -> None:
    from api.data.attention import twscrape_reader, x_proxy_private as xpp
    sid = xpp.actual_service_sid() if os.name == "nt" else ""
    xpp.verify_private(path, path.parent, repo_root=twscrape_reader.REPO_ROOT, service_sid=sid)


def _profile_verifier(root: Path, cache_root: Path) -> None:
    from api.data.attention import browser_profile
    store = browser_profile.ProfileStore(root, cache_root=cache_root)
    store._check(root, "", root=True)  # the store's own read-only A10 root check


def _machine_lock() -> int | None:
    """Non-blocking acquire then immediate release; the wait result (0 free, 128 abandoned)."""
    from api.data.attention import browser_host
    lock = browser_host.MachineLock()
    try:
        lock.acquire()
        return lock.wait_result
    finally:
        lock.close()


def _memory() -> float | None:
    from api.data.attention import browser_host
    return browser_host.free_memory_mb()


def _browser_version(binary: Path) -> str:
    from api.data.attention import browser_host
    return browser_host.executable_version(binary)


@dataclass
class Deps:
    cache_root: Path
    now: datetime
    queries_path: Path | None = None
    env: dict = field(default_factory=lambda: dict(os.environ))
    query_runner: Callable = default_query_runner
    selftest_runner: Callable = default_selftest_runner
    private_verifier: Callable = _private_verifier
    profile_verifier: Callable = _profile_verifier
    machine_lock: Callable = _machine_lock
    memory: Callable = _memory
    browser_version: Callable = _browser_version
    disk_free_mb: Callable = lambda p: shutil.disk_usage(p).free / 1048576
    dist_lookup: Callable | None = None


def _attention(d: Deps) -> Path:
    return Path(d.cache_root) / "attention"


def _json(path: Path):
    """Parsed JSON object, None when absent, or the string 'unreadable'."""
    if not path.exists():
        return None
    try:
        doc = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return "unreadable"
    return doc if isinstance(doc, dict) else "unreadable"


def _iso(v) -> datetime | None:
    try:
        t = datetime.fromisoformat(v)
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else None


# --- checks ----------------------------------------------------------------------------------------------------------

def check_config(d: Deps):
    """(Check, Queries or None): the strict schema of the private owner query file."""
    from api.data.attention import web_queries
    if d.queries_path is None:
        return Check("config", WARN, "owner_config_not_given", "pass --queries <absolute private query file>"), None
    if not Path(d.queries_path).is_absolute():
        return Check("config", FAIL, "owner_config_path_relative", "use an absolute path"), None
    try:
        q = web_queries.load(Path(d.queries_path))
    except OSError:
        return Check("config", FAIL, "owner_config_unreadable", "check the file exists and is readable"), None
    except ValueError:
        return Check("config", FAIL, "owner_config_invalid", "fix the collector block (deploy/README.md keys)"), None
    return Check("config", PASS, "owner_config_valid"), q


def _x_checks(d: Deps, c) -> list[Check]:
    from api.data.attention import twscrape_reader as tr
    lookup = d.dist_lookup or tr.find_dist
    out = []
    backend = "curl" if c.x_connection_style == "curl" else "httpx"
    bad = tr.env_guard(d.env, selected_backend=backend)
    out.append(Check("x_env", PASS, "env_ok") if not bad else
               Check("x_env", FAIL, "env_bad", "run through deploy/start-collector.ps1 or deploy/doctor.ps1"))
    dist = lookup("twscrape")
    if dist is None:
        out.append(Check("x_pin", FAIL, "twscrape_not_installed", "uv sync --project api --group xreader --frozen"))
    elif tr.identity_problem(dist, tr.PINNED_COMMIT) is None and c.x_pinned_commit == tr.PINNED_COMMIT:
        out.append(Check("x_pin", PASS, "pinned_commit_match"))
    else:
        out.append(Check("x_pin", FAIL, "pinned_commit_mismatch", "reinstall the pinned twscrape"))
    if not c.x_allow_curl_backend:
        out.append(Check("x_curl", PASS, "curl_fallback_off"))
    else:
        status = tr.curl_status(tr.read_install_record(), tr.platform_key(), lookup("curl_cffi"))
        out.append(Check("x_curl", PASS, "curl_ok") if status == "ok" else
                   Check("x_curl", FAIL, f"curl_{status}"[:40], "re-run the curl install verification"))
    labels = list(c.x_accounts)
    problems = tr.accounts_problems(c) if labels else []
    if not labels:
        out.append(Check("x_accounts", WARN, "no_x_accounts", "add owner-created X accounts (about 4)"))
    elif problems:
        out.append(Check("x_accounts", FAIL, "accounts_files_invalid", "fix x_accounts_db_path and account files"))
    elif len(labels) < X_SIZING_ABOUT:
        out.append(Check("x_accounts", WARN, f"x_accounts_{len(labels)}_below_{X_SIZING_ABOUT}",
                         f"add accounts: about {X_SIZING_ABOUT}, worst case {X_SIZING_WORST}"))
    else:
        out.append(Check("x_accounts", PASS, f"x_accounts_{len(labels)}"))
    out.append(Check("x_backfill", WARN, "x_backfill_days_over_7", "lower x_backfill_days to 7 or less")
               if c.x_backfill_days > 7 else Check("x_backfill", PASS, "x_backfill_days_ok"))
    pool = _json(_attention(d) / "_pc_state" / "x_pool.json")
    accounts = pool.get("accounts") if isinstance(pool, dict) else None
    out.append(_x_rest(d, labels, accounts, pool))
    out.append(_x_cookies(d, c, labels, accounts))
    out.extend(_proxy_checks(d, c, labels, accounts, pool))
    return out


def _x_rest(d: Deps, labels, accounts, pool) -> Check:
    if not labels:
        return Check("x_rest_ready", WARN, "no_x_accounts", "add X accounts, then rest them")
    if pool is None:
        return Check("x_rest_ready", UNKNOWN, "x_pool_absent", "start the collector once")
    if not isinstance(accounts, dict):
        return Check("x_rest_ready", UNKNOWN, "x_pool_unreadable", "inspect the collector log")
    resting = sum(1 for lb in labels if isinstance(accounts.get(lb), dict)
                  and (_iso(accounts[lb].get("rest_until")) or d.now) > d.now)
    inactive = sum(1 for lb in labels if not isinstance(accounts.get(lb), dict)
                   or accounts[lb].get("state") not in ("active",))
    ready = len(labels) - max(resting, inactive)
    if ready <= 0:
        return Check("x_rest_ready", WARN, f"x_ready_0_of_{len(labels)}", "wait for rest to end or reactivate")
    if resting or inactive:
        return Check("x_rest_ready", WARN, f"x_ready_{ready}_of_{len(labels)}", "see the status box per account")
    return Check("x_rest_ready", PASS, f"x_ready_{ready}_of_{len(labels)}")


def _x_cookies(d: Deps, c, labels, accounts) -> Check:
    from api.data.attention import twscrape_reader as tr
    if not labels:
        return Check("x_cookies", WARN, "no_x_accounts", "add X accounts")
    if isinstance(accounts, dict) and any(isinstance(accounts.get(lb), dict)
                                          and accounts[lb].get("harvest_state") in ("failed", "refused")
                                          for lb in labels):
        return Check("x_cookies", WARN, "harvest_failed", "run --harvest-cookies LABEL --interactive")
    try:
        ages = tr.cookie_ages(c, now=d.now)
    except Exception:  # noqa: BLE001 - any failure is the same code; no detail is printed
        return Check("x_cookies", UNKNOWN, "cookie_ages_unreadable", "check the private accounts folder")
    values = [ages.get(lb) for lb in labels]
    if any(v is None for v in values):
        return Check("x_cookies", UNKNOWN, "cookie_age_unknown", "refresh cookies once per account")
    limit = c.x_cookie_refresh_age_days
    if limit is not None and max(values) > limit:
        return Check("x_cookies", WARN, "cookie_age_over_limit", "refresh or harvest the oldest account")
    return Check("x_cookies", PASS, f"cookie_age_max_{max(values)}d")


def _proxy_checks(d: Deps, c, labels, accounts, pool) -> list[Check]:
    keys = ("x_proxy_list_path", "x_proxy_assignments_path", "x_proxy_policy_path")
    if not c.x_proxy_required:
        return [Check("proxy_files", WARN, "proxy_not_required",
                      "configure one private proxy per account, or record the direct decision")]
    missing = [k for k in keys if not getattr(c, k) or not Path(getattr(c, k)).is_file()]
    if missing:
        return [Check("proxy_files", FAIL, "missing_" + "_".join(k.split("_")[2] for k in missing),
                      "provide the missing private files: " + ", ".join(missing))]
    out = [Check("proxy_files", PASS, "proxy_files_present")]
    try:
        for k in keys:
            d.private_verifier(Path(getattr(c, k)))
        out.append(Check("private_acl", PASS, "private_acl_verified"))
    except Exception:  # noqa: BLE001
        out.append(Check("private_acl", FAIL, "private_acl_unverified", "recreate the private root owner-only"))
    if not isinstance(accounts, dict) or not labels:
        out.append(Check("proxy_admission", UNKNOWN, "no_admission_evidence", "start the collector once"))
        return out
    fresh, quarantined, ids = 0, 0, []
    max_age = timedelta(seconds=c.x_proxy_admission_max_age_seconds)
    for lb in labels:
        a = accounts.get(lb) if isinstance(accounts.get(lb), dict) else {}
        checked = _iso(a.get("proxy_checked_at"))
        if a.get("proxy_health") == "quarantined":
            quarantined += 1
        elif a.get("proxy_health") == "healthy" and checked and timedelta(0) <= d.now - checked < max_age:
            fresh += 1
        if a.get("proxy_id"):
            ids.append(a["proxy_id"])
    n = len(labels)
    out.append(Check("proxy_admission", PASS, f"admitted_{fresh}_of_{n}") if fresh == n else
               Check("proxy_admission", WARN, f"admitted_{fresh}_of_{n}", "wait for the next admission check"))
    out.append(Check("proxy_quarantine", PASS, "none_quarantined") if not quarantined else
               Check("proxy_quarantine", WARN, f"quarantined_{quarantined}", "check the quarantined routes"))
    out.append(Check("proxy_distinct", FAIL, "shared_route", "give every account its own route")
               if len(set(ids)) != len(ids) else Check("proxy_distinct", PASS, "routes_distinct"))
    return out


def check_stage3_trigger(d: Deps, c) -> Check:
    """AC16: the V2Ray gateway stays parked. Trigger (SPEC Stage 3): the built-in proxy list cannot manage the
    accounts' routes, measured from pool evidence: met when no configured account holds an admitted route while
    every one is locked by a route failure."""
    pool = _json(_attention(d) / "_pc_state" / "x_pool.json") if c is not None else None
    labels = list(c.x_accounts) if c is not None else []
    if c is None or not c.x_proxy_required or not labels or not isinstance(pool, dict) \
            or not isinstance(pool.get("accounts"), dict):
        return Check("stage3_trigger", UNKNOWN, "gateway_not_built_trigger_unmeasured",
                     "measured once routed accounts have run")
    accounts = pool["accounts"]
    failing = sum(1 for lb in labels if isinstance(accounts.get(lb), dict)
                  and accounts[lb].get("proxy_health") == "quarantined")
    if failing == len(labels):
        return Check("stage3_trigger", WARN, "gateway_not_built_trigger_met",
                     "every route is failing: review the proxy list before any Stage 3 decision")
    return Check("stage3_trigger", PASS, f"gateway_not_built_trigger_not_met_{failing}_of_{len(labels)}")


def _browser_checks(d: Deps, c) -> list[Check]:
    from api.data.attention import browser_host, web_queries
    out = []
    binary = Path(c.browser_path) if c.browser_path else None
    if binary is None:
        out.append(Check("browser_path", WARN, "browser_not_configured", "set browser_path to Edge or Chrome"))
    elif not binary.is_file():
        out.append(Check("browser_path", FAIL, "browser_missing", "fix browser_path"))
        binary = None
    else:
        out.append(Check("browser_path", PASS, "browser_present"))
    root = Path(c.browser_profiles_dir) if c.browser_profiles_dir else None
    if root is None:
        out.append(Check("profile_acl", WARN, "profiles_dir_not_configured", "set browser_profiles_dir"))
    elif not root.is_dir():
        out.append(Check("profile_acl", FAIL, "profiles_dir_missing", "browser_session --init-profile"))
    else:
        try:
            d.profile_verifier(root, d.cache_root)
            out.append(Check("profile_acl", PASS, "profile_root_verified"))
        except Exception:  # noqa: BLE001
            out.append(Check("profile_acl", FAIL, "profile_acl_unverified", "recreate the profile root (A10)"))
    names = list(c.x_account_profiles.values()) + [a["profile"] for a in c.reddit_browser_accounts]
    ids = [web_queries.profile_identity(n) for n in names]
    out.append(Check("profile_unique", FAIL, "profile_shared", "one profile per account")
               if len(set(ids)) != len(ids) else Check("profile_unique", PASS, f"profiles_{len(ids)}"))
    health = _json(_attention(d) / "_pc_state" / "browser_health.json")
    if health is None:
        out.append(Check("relay_refusals", UNKNOWN, "no_relay_health", "run one browser session"))
    elif health == "unreadable" or not isinstance(health.get("relay_refusals"), dict):
        out.append(Check("relay_refusals", UNKNOWN, "relay_health_unreadable", "inspect the collector log"))
    else:
        n = sum(v for v in health["relay_refusals"].values() if isinstance(v, int))
        out.append(Check("relay_refusals", PASS, "no_refusals") if not n else
                   Check("relay_refusals", WARN, f"refused_{n}", "review the refused hostnames in the status box"))
    if binary is None:
        out.append(Check("browser_live", UNKNOWN, "blocked(browser_not_configured)", "configure the browser"))
        out.append(Check("containment", UNKNOWN, "no_admission_record", "run the A19 self-test"))
    else:
        try:
            record = browser_host.read_admission(d.cache_root, binary, d.browser_version(binary))
            outcome = record["outcome"]
            out.append(Check("browser_live", PASS, f"admitted_{outcome}"))
            out.append(Check("containment", WARN, "accepted_residual", "O-2 residual accepted by the owner")
                       if outcome == "accepted_residual" else Check("containment", PASS, outcome))
        except Exception as exc:  # noqa: BLE001
            reason = getattr(exc, "reason", "browser_unadmitted")
            out.append(Check("browser_live", FAIL, f"blocked({reason})"[:40], "run the A19 self-test (BG-1..BG-3)"))
            out.append(Check("containment", UNKNOWN if reason == "browser_unadmitted" else FAIL, reason[:40],
                             "run the A19 self-test; decide O-1/O-2"))
    out.append(check_firewall(d))
    floor = c.browser_memory_floor_mb
    mem = d.memory()
    if mem is None:
        out.append(Check("memory", UNKNOWN, "memory_unreadable", ""))
    elif mem < floor:
        out.append(Check("memory", WARN, "below_floor", "close programs before a browser run"))
    else:
        out.append(Check("memory", PASS, "above_floor"))
    try:
        wait = d.machine_lock()
        out.append(Check("kernel_lock", WARN, "lock_abandoned", "a browser run crashed; check its log")
                   if wait == 128 else Check("kernel_lock", PASS, "lock_free"))
    except Exception:  # noqa: BLE001
        out.append(Check("kernel_lock", WARN, "browser_busy", "a browser run holds the lock; re-run later"))
    return out


def check_firewall(d: Deps) -> Check:
    """`firewall_rule: present|absent|unknown` by a read-only query through the injected runner."""
    try:
        code, text = d.query_runner(firewall_query_argv())
        count = int(str(text).strip()) if code == 0 else None
    except (ValueError, TypeError):
        count = None
    if count is None:
        return Check("firewall_rule", UNKNOWN, "unknown", "query Get-NetFirewallRule yourself")
    if count > 0:
        return Check("firewall_rule", PASS, "present")
    return Check("firewall_rule", WARN, "absent", "review browser_firewall_rule output and apply it yourself")


def _queryid_check(d: Deps, c) -> Check:
    from api.data.attention import x_queryids
    if c.x_queryid_mode == "off":
        return Check("query_ids", PASS, "mode_off")
    path = x_queryids.state_path(d.cache_root)
    if not path.exists():
        return Check("query_ids", UNKNOWN, "no_queryid_state", "wait for the first unit-boundary check")
    try:
        state = x_queryids.load(path)["check_state"]
    except Exception:  # noqa: BLE001
        return Check("query_ids", UNKNOWN, "queryid_state_unreadable", "inspect the collector log")
    if state == "ok":
        return Check("query_ids", PASS, "ok")
    if state in ("blocked", "refused_by_policy"):
        return Check("query_ids", FAIL, state, "see the query-id runbook section")
    return Check("query_ids", WARN if state in ("candidate", "stale") else UNKNOWN, state, "see the status box")


def _reddit_checks(d: Deps, c) -> list[Check]:
    from api.data.attention import reddit_accounts, reddit_core
    from api.scripts import probe_owner
    out = []
    labels = [a["label"] for a in c.reddit_browser_accounts]
    if not labels:
        out.append(Check("reddit_accounts", WARN, "no_reddit_accounts",
                         "create 2 throwaway accounts, init profiles, log in once, rest a week"))
    else:
        ready_marks = reddit_accounts.read_ready()
        ready = sum(1 for lb in labels if lb in ready_marks and date.fromisoformat(ready_marks[lb]) < d.now.date())
        state = _json(_attention(d) / "_pc_state" / "reddit_accounts.json")
        entries = state.get("accounts") if isinstance(state, dict) else None
        if not isinstance(entries, dict):
            out.append(Check("reddit_accounts", UNKNOWN if state is None or state == "unreadable" else WARN,
                             f"ready_{ready}_of_{len(labels)}_state_unknown", "start the collector once"))
        else:
            locked = sum(1 for lb in labels if isinstance(entries.get(lb), dict)
                         and entries[lb].get("state") in ("locked", "paused"))
            if ready == 0:
                out.append(Check("reddit_accounts", WARN, f"ready_0_of_{len(labels)}",
                                 "after the rest week: reddit_accounts --mark-ready LABEL"))
            elif locked:
                out.append(Check("reddit_accounts", WARN, f"locked_{locked}_of_{len(labels)}",
                                 "see the account reason in the status box"))
            else:
                out.append(Check("reddit_accounts", PASS, f"ready_{ready}_of_{len(labels)}"))
    methods = list(c.reddit_live_methods)
    if not methods:
        out.append(Check("reddit_live_gates", WARN, "live_methods_off",
                         "PR2 bootstrap, approve surface, PR2 verify, then enable reddit_live_methods"))
    else:
        gates = {m: probe_owner.verify_gate(d.cache_root, m, surface_path=Path(c.reddit_surface_path),
                                            max_age_days=c.reddit_live_probe_max_age_days, today=d.now.date())
                 for m in methods}
        bad = sorted(f"{m}:{g}" for m, g in gates.items() if g != "ok")
        out.append(Check("reddit_surface", PASS, "surface_and_probe_fresh") if not bad else
                   Check("reddit_surface", WARN, ",".join(bad)[:80], "re-run the verify probe or publish the surface"))
        for m in methods:
            store = reddit_core.STORES.get(m)
            doc = _json(_attention(d) / "_pc_state" / "reddit_live" / f"{store}_health.json") if store else None
            gate = doc.get("state") if isinstance(doc, dict) else None
            if gate is None or gate not in reddit_core.GATE_STATES:
                out.append(Check(f"gate_{m}", UNKNOWN, "no_gate_state", "start the collector once"))
            elif gate == "ready":
                out.append(Check(f"gate_{m}", PASS, "ready"))
            else:
                out.append(Check(f"gate_{m}", WARN, gate, "see the Reddit row in the status box"))
    feeds = [m for m in c.reddit_impl_order if m in FEED_METHODS]
    if d.now.date() >= FEED_END and feeds:
        out.append(Check("feed_methods", WARN, "feed_methods_stale", "the public feeds ended 13-11-26"))
    else:
        out.append(Check("feed_methods", PASS, "before_feed_end" if feeds else "no_feed_methods"))
    return out


def _ops_checks(d: Deps, c) -> list[Check]:
    from api.analytics.attention import daily_report
    from api.data.attention import collector_heartbeat
    out = []
    try:
        free = d.disk_free_mb(Path(d.cache_root) if Path(d.cache_root).exists() else Path(d.cache_root).anchor)
        out.append(Check("disk", FAIL, "disk_below_1gb", "free disk space") if free < DISK_FAIL_MB else
                   Check("disk", WARN, "disk_below_5gb", "free disk space") if free < DISK_WARN_MB else
                   Check("disk", PASS, "disk_ok"))
    except OSError:
        out.append(Check("disk", UNKNOWN, "disk_unreadable", ""))
    found = []
    for name in TASK_NAMES:
        try:
            code, text = d.query_runner(task_query_argv(name))
            found.append(int(str(text).strip()) > 0 if code == 0 else None)
        except (ValueError, TypeError):
            found.append(None)
    if any(f is None for f in found):
        out.append(Check("scheduled_tasks", UNKNOWN, "unknown", "run Get-ScheduledTask yourself"))
    elif all(found):
        out.append(Check("scheduled_tasks", PASS, "registered"))
    else:
        out.append(Check("scheduled_tasks", WARN, f"registered_{sum(found)}_of_{len(found)}",
                         "deploy/register-collector-tasks.ps1"))
    hb = collector_heartbeat.status(d.now)
    st = hb.get("state")
    out.append(Check("heartbeat", PASS, "running") if st == "running" else
               Check("heartbeat", UNKNOWN, "heartbeat_unreadable", "inspect the collector log") if st == "unknown" else
               Check("heartbeat", WARN, str(st)[:40], "deploy/start-collector.ps1"))
    day = d.now.date() - timedelta(days=1)
    report = daily_report.read_report(day)
    rows = report.get("per_source_method") if isinstance(report, dict) else None
    if report is None:
        out.append(Check("daily_report", WARN, "no_report_yesterday", "python -m api.scripts.attention_daily_report"))
    elif not isinstance(rows, dict) or not rows:
        out.append(Check("daily_report", UNKNOWN, "report_without_rows", "check facts and completeness files"))
    elif all(isinstance(r, dict) and r.get("eligible") and r.get("stored") == r.get("eligible") for r in rows.values()):
        out.append(Check("daily_report", PASS, "complete"))
    else:
        out.append(Check("daily_report", WARN, "incomplete", "read daily_report_<D>.txt for missing reasons"))
    out.append(_facts_retention(d, c))
    return out


def _facts_retention(d: Deps, c) -> Check:
    folder = _attention(d) / "_facts"
    if not folder.is_dir():
        return Check("facts_retention", UNKNOWN, "no_facts", "start the collector once")
    keep = c.facts_retention_days if c is not None else 180
    oldest = d.now.date() - timedelta(days=keep)
    stale = 0
    for p in folder.glob("events_*.jsonl"):
        try:
            stale += date.fromisoformat(p.stem[len("events_"):]) < oldest
        except ValueError:
            continue
    return Check("facts_retention", PASS, "within_retention") if not stale else \
        Check("facts_retention", WARN, f"over_retention_{stale}", "the collector prunes at its next pass")


def _live_checks(d: Deps) -> list[Check]:
    from api.scripts import probe_owner
    out = []
    for probe_id, mode in LIVE_PROBES:
        rec = probe_owner.latest_record(d.cache_root, probe_id, mode)
        if rec is None:
            out.append(Check(f"live_{probe_id}", UNKNOWN, "needs_probe", f"probe_owner {probe_id} --approve"))
        elif rec.get("outcome") == "pass":
            out.append(Check(f"live_{probe_id}", PASS, "probe_passed"))
        else:
            out.append(Check(f"live_{probe_id}", FAIL, "probe_failed", "read the probe record reason"))
    return out


def check_selftest(d: Deps) -> Check:
    try:
        code = d.selftest_runner(list(SELFTEST_ARGV))
    except Exception:  # noqa: BLE001
        return Check("selftest", FAIL, "selftest_not_run", "run python -m api.tests.cycle.acceptance")
    return Check("selftest", PASS, "acceptance_passed") if code == 0 else \
        Check("selftest", FAIL, "acceptance_failed", "run python -m api.tests.cycle.acceptance")


def run_checks(d: Deps, *, live: bool = False, selftest: bool = False) -> list[Check]:
    first, q = check_config(d)
    checks = [first]
    c = q.config if q is not None else None
    if c is not None:
        checks += _x_checks(d, c)
        checks.append(_queryid_check(d, c))
        checks += _browser_checks(d, c)
        checks += _reddit_checks(d, c)
    else:
        checks.append(check_firewall(d))
    checks.append(check_stage3_trigger(d, c))
    checks += _ops_checks(d, c)
    if live:
        checks += _live_checks(d)
    if selftest:
        checks.append(check_selftest(d))
    return checks


def overall(checks: list[Check]) -> str:
    states = {ch.state for ch in checks}
    for s in (FAIL, WARN, UNKNOWN):
        if s in states:
            return s
    return PASS


def exit_code(checks: list[Check]) -> int:
    states = {ch.state for ch in checks}
    return 2 if FAIL in states else 1 if states & {WARN, UNKNOWN} else 0


def document(checks: list[Check], now: datetime) -> dict:
    return {"state": overall(checks), "checked_at": now.astimezone(timezone.utc).isoformat(),
            "failures": [ch.name for ch in checks if ch.state == FAIL],
            "warnings": [ch.name for ch in checks if ch.state in (WARN, UNKNOWN)],
            "checks": [{"name": ch.name, "state": ch.state, "reason": ch.reason} for ch in checks]}


def doctor_path(cache_root: Path) -> Path:
    return Path(cache_root) / "attention" / "_reports" / DOCTOR_FILE


def main(argv=None, *, out=sys.stdout, deps: Deps | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m api.scripts.collector_doctor")
    parser.add_argument("--queries", type=Path, help="absolute private owner query file")
    parser.add_argument("--json", action="store_true", help="print the doctor document as JSON")
    parser.add_argument("--live", action="store_true", help="also gate on recorded live probe evidence (LIVE-READY)")
    parser.add_argument("--selftest", action="store_true", help="run the synthetic end-to-end acceptance")
    args = parser.parse_args(argv)
    d = deps or Deps(cache_root=cache.CACHE_ROOT, now=datetime.now(timezone.utc))
    if args.queries is not None:
        d.queries_path = args.queries
    checks = run_checks(d, live=args.live, selftest=args.selftest)
    doc = document(checks, d.now)
    from api.data.attention.x_proxy_private import atomic_json
    atomic_json(doctor_path(d.cache_root), doc)
    if args.json:
        print(json.dumps(doc, indent=1, sort_keys=True), file=out)
    else:
        for ch in checks:
            print(f"{ch.state:<7} {ch.name}: {ch.reason}" + (f"  -> {ch.fix}" if ch.fix and ch.state != PASS else ""),
                  file=out)
        print(f"doctor: {doc['state']} ({len(doc['failures'])} fail, {len(doc['warnings'])} warn/unknown)", file=out)
    return exit_code(checks)


if __name__ == "__main__":
    raise SystemExit(main())
