"""B2 test-only seeded real server; no production fixture switches or fake responses.

The launcher explicitly injects private synthetic query and discovery paths into
this process before importing the real FastAPI application. Workers stay disabled.
"""
from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
import socket
import sys
from datetime import UTC, datetime, timedelta
from uuid import UUID

LABELS = ("legacy", "unknown", "healthy", "quarantined", "blocked")
SECRET = "B2_SYNTHETIC_SECRET_NEVER_PUBLIC"
# S-StatusUI: Reddit accounts (max 3 per config, so two finish scenarios cover all five states).
REDDIT_SCENARIOS = {
    "finish-a": (("r_active", "r_resting", "r_unknown"), ["browser", "gql_anon"], "sentinel"),
    "finish-b": (("r_paused", "r_locked"), ["gql_anon"], "auto"),
}


def root() -> Path:
    from api.scripts.seed_e2e_cache import _guard
    return _guard()


def put(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def seed() -> None:
    from api.data.attention import web_queries, x_pool
    from copy import deepcopy
    from api.analytics.attention.discovery import load_config
    directory = root()
    private = directory / "collector-private"
    private.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    config = dict(web_queries.DEFAULTS)
    config.update(x_accounts=list(LABELS), x_accounts_db_path=str(private / "accounts"),
                  x_account_daily_cap=100, x_pool_max=len(LABELS), x_proxy_required=False)
    direct = dict(version=1, collector=dict(config), subreddits=["synthetic"],
                  ambiguous={"xsearch_web": [], "reddit_web": []}, coins={})
    put(private / "queries-direct.json", direct)
    config.update(x_proxy_list_path=str(private / "routes.txt"),
                  x_proxy_assignments_path=str(private / "assignments.json"),
                  x_proxy_policy_path=str(private / "policy.json"))
    configured = dict(direct, collector=config)
    put(private / "queries-configured.json", configured)
    put(private / "queries.json", configured)
    # Refuse an internally inconsistent fixture before the real server starts.
    web_queries.validate(direct)
    web_queries.validate(configured)
    for scenario, (labels, methods, mode) in REDDIT_SCENARIOS.items():
        finish = dict(config, reddit_live_methods=methods, reddit_surface_path=str(private / "surface.json"),
                      browser_path=str(private / "browser.exe"), browser_profiles_dir=str(private / "profiles"),
                      reddit_browser_accounts=[{"label": label, "profile": f"p_{label}"} for label in labels],
                      x_queryid_mode=mode)
        body = dict(configured, collector=finish)
        web_queries.validate(body)
        put(private / f"queries-{scenario}.json", body)
    # These marker-bearing private inputs must never be opened by the status
    # reader. Deliberately malformed bodies make accidental admission fail.
    for name in ("routes.txt", "assignments.json", "policy.json"):
        (private / name).write_text(SECRET, encoding="utf-8")
    (private / "accounts").mkdir(exist_ok=True)
    put(private / "accounts" / "cookie_ages.json", {"healthy": now.isoformat()})
    discovery_config = deepcopy(load_config())
    discovery_config.setdefault("source_impl", {})["xsearch"] = "xsearch_web"
    if discovery_config["source_weights"]["xsearch"] <= 0:
        discovery_config["source_weights"]["xsearch"] = 10
    put(directory / "discovery.json", discovery_config)
    pool = x_pool.XPool(list(LABELS), clock=lambda: now)
    state = pool._s
    state["proxy_provider_budget"] = {"day": None, "used": 0}
    for index, label in enumerate(LABELS):
        account = state["accounts"][label]
        account.update(reads_day=now.date().isoformat(), reads_used=index + 1)
        if label == "legacy":
            for key in tuple(account):
                if key.startswith("proxy_") or key == "identity_revision":
                    account.pop(key)
            continue
        account.update(proxy_id=str(UUID(int=index + 1)),
                       identity_revision="12345678-1234-4234-8234-123456789abd",
                       proxy_health="unknown", proxy_checked_at=None,
                       proxy_quarantine_until=None, proxy_reason=None, proxy_changed_at=now.isoformat())
        if label == "healthy":
            account.update(proxy_health="healthy", proxy_checked_at=now.isoformat())
        elif label == "quarantined":
            account.update(proxy_health="quarantined", proxy_checked_at=now.isoformat(),
                           proxy_quarantine_until=(now + timedelta(hours=1)).isoformat(),
                           proxy_reason="proxy_quarantine")
        elif label == "blocked":
            account.update(proxy_reason="proxy_config")
    put(pool.path, state)
    put(directory / "attention" / "_pc_state" / "xsearch_web.json", {
        "budget_day": now.date().isoformat(), "used": 15, "spent_day": None,
        "effective": 400, "clean_days": 0,
        "activity": {"day": now.date().isoformat(), "units": 0, "warned": False},
        "pause_until": None, "pause_reason": None, "last_unit_at": now.isoformat(),
    })
    seed_finish(directory, now)


def seed_finish(directory: Path, now: datetime) -> None:
    """Producer files in the S-StatusAPI layouts (its report section 7). Secret-bearing and IP values are planted
    where a reader must drop or count them, never show them."""
    state = directory / "attention" / "_pc_state"
    reports = directory / "attention" / "_reports"
    today, yesterday = now.date(), now.date() - timedelta(days=1)
    put(state / "reddit_accounts.json", {"accounts": {
        "r_active": {"state": "active", "reads_day": today.isoformat(), "reads_used": 3, "session_state": "ok",
                     "session_checked_at": now.isoformat(), "proxy_state": "healthy"},
        "r_resting": {"state": "resting", "reason": "new_account_rest",
                      "rest_until": (now + timedelta(days=3)).isoformat()},
        "r_paused": {"state": "paused", "reason": "rate_limited", "reads_day": today.isoformat(), "reads_used": 9},
        "r_locked": {"state": "locked", "reason": SECRET, "proxy_state": "blocked"},
    }})
    put(state / "reddit_account_ready.json", {"ready": {"r_active": yesterday.isoformat(),
                                                         "r_resting": today.isoformat()}})
    put(state / "reddit_live" / "reddit_live_browser_health.json", {"state": "needs_probe", "reason": "probe_missing"})
    put(state / "reddit_live" / "reddit_live_gql_health.json", {
        "state": "degraded", "reason": "rate_limited", "lanes": {"posts": 1, "comments": 0.4},
        "comments_scope": "threads_opened", "requests_today": 30, "cap": 200})
    put(state / "x_queryids.json", {"check_state": "candidate", "last_check": now.isoformat(), "operations": {
        "SearchTimeline": {"active": {"id": SECRET, "source": "bundle",
                                      "adopted_at": (now - timedelta(days=2)).isoformat()}}}})
    put(state / "browser_health.json", {"profile_state": "policy_unsatisfied", "relay_refusals": {
        "edge.microsoft.com": 3, "192.0.2.1": 9, SECRET: 7}})
    put(reports / f"daily_report_{yesterday.isoformat()}.json", {"revision": 1, "per_source_method": {
        "reddit/reddit_live_gql": {"eligible": 10, "stored": 8, "exact": 7, "estimated": 1, "missing": 2,
                                   "reasons": {"blocked": 2}},
        "xsearch/xsearch_web": {"eligible": 5, "stored": 5, "exact": 5, "estimated": 0, "missing": 0, "reasons": {}}}})
    put(reports / "doctor.json", {"state": "WARN", "checked_at": now.isoformat(), "failures": [],
                                  "warnings": [SECRET, "check text"]})


def install_private_read_guard(directory: Path) -> None:
    """Fail the test server if any status path opens admission-only inputs."""
    forbidden = {str((directory / "collector-private" / name).resolve())
                 for name in ("routes.txt", "assignments.json", "policy.json")}

    class ForbiddenPrivateRead(BaseException):
        """Cannot be swallowed by a production fail-closed Exception handler."""

    def audit(event, args):
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            try:
                target = str(Path(os.fsdecode(args[0])).resolve())
            except (OSError, ValueError):
                return
            if target in forbidden:
                raise ForbiddenPrivateRead("status opened an admission-only private fixture")

    sys.addaudithook(audit)



def serve() -> None:
    from api.analytics.attention import discovery
    from api.data.attention import web_queries
    directory = root()
    discovery.CONFIG_PATH = directory / "discovery.json"
    web_queries.QUERIES_PATH = directory / "collector-private" / "queries.json"
    install_private_read_guard(directory)
    # Dependency-level containment in this test process, not a production
    # bypass flag. Any attempted provider/collection connection fails loudly.
    connect = socket.socket.connect

    def loopback_only(sock, address):
        if not isinstance(address, tuple) or not ipaddress.ip_address(address[0]).is_loopback:
            raise AssertionError("external connection forbidden in seeded B2 server")
        return connect(sock, address)

    socket.socket.connect = loopback_only
    resolve = socket.getaddrinfo
    connect_ex = socket.socket.connect_ex

    def resolve_loopback(host, *args, **kwargs):
        if host != "localhost":
            try:
                allowed = ipaddress.ip_address(host).is_loopback
            except ValueError:
                allowed = False
            if not allowed:
                raise AssertionError("external DNS forbidden in seeded B2 server")
        return resolve(host, *args, **kwargs)

    def connect_ex_loopback(sock, address):
        if not isinstance(address, tuple) or not ipaddress.ip_address(address[0]).is_loopback:
            raise AssertionError("external connection forbidden in seeded B2 server")
        return connect_ex(sock, address)

    socket.getaddrinfo = resolve_loopback
    socket.socket.connect_ex = connect_ex_loopback
    import uvicorn
    from api.main import app
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ["E2E_API_PORT"]))


if __name__ == "__main__":
    {"seed": seed, "serve": serve}[sys.argv[1]]()
