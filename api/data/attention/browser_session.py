"""Harvest-only session helper core (finish plan S-Cookie-C: CK-1..CK-7). Default off.

One account, one existing browser profile, one relay, one check: open the site's home, wait for the page, read the
final URL (`location.href`) and the cookie jar (`Network.getCookies`), classify, close. It never types anything
(the CDP method tables contain no input domain), never retries, never switches route. Values: Reddit cookie values
are discarded at parse by the CDP client; X values reach only `SessionResult.cookies`, in memory, for the caller,
and only when the session is logged in. Nothing here logs; the CLI prints one JSON line of codes and names.

Seams (CK-6), injected by the state owners: `DayGuard.try_claim(site, label, day) -> bool` (X: the pool key via
S-Cookie-X; Reddit: `reddit_accounts.RedditAccounts.try_claim`) and `RouteProvider.admitted_route(site, label)`
returning an `AdmittedRoute` or a refusal (X: the B2 runtime via S-Cookie-X; Reddit: S-RAcct-B via S-RBrowser).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol
from urllib.parse import urlsplit

from api.data.attention import browser_cdp as cdp
from api.data.attention import browser_host as bh
from api.data.attention import browser_profile as profiles
from api.data.attention import browser_relay as relay_mod

STATES = ("logged_in", "login_required", "challenge", "refused", "failed")
REFUSED_REASONS = ("browser_unadmitted", "containment_residual_unaccepted", "cdp_pipe_unavailable",
                   "profile_policy_unsatisfied", "proxy_not_admitted", "browser_busy", "low_memory")
ROLES = {"automatic": "session_check", "interactive": "session_check", "probe": "bootstrap"}
POLL_SECONDS = 2.0
DAY_SECONDS = 86400
# A Reddit session outcome as the account pool records it (`reddit_accounts.SESSION_STATES`).
SESSION_RECORD = {"logged_in": "logged_in", "login_required": "logged_out", "challenge": "challenge"}


@dataclass(frozen=True)
class Site:
    host: str
    home: str
    cookie_urls: tuple[str, ...]
    required: tuple[str, ...]


SITES = {
    "x": Site("x.com", "https://x.com/home", ("https://x.com/",), ("auth_token", "ct0")),
    "reddit": Site("www.reddit.com", "https://www.reddit.com/", ("https://www.reddit.com/",), ("reddit_session",)),
}
_X_LOGIN = ("/i/flow/login", "/i/flow/signup", "/login", "/logout")
_X_CHALLENGE = ("/account/", "/i/flow/")
_REDDIT_LOGIN = {"login", "register"}
_REDDIT_CHALLENGE = {"account", "verify", "captcha"}


class DayGuard(Protocol):
    def try_claim(self, site: str, label: str, day: str) -> bool: ...


@dataclass(frozen=True)
class AdmittedRoute:
    """The admitted route for one account: `direct`, or `proxy` with the account's `x_proxy.PrivateRoute`."""
    mode: str
    revision: str
    admission: Callable[[], relay_mod.Admission]
    route: Any = None
    hosts: tuple[str, ...] | None = None


class RouteProvider(Protocol):
    def admitted_route(self, site: str, label: str) -> AdmittedRoute | str: ...


class _DenyRoutes:
    """Default-deny provider until the real providers are wired (S-Cookie-X for X, S-RBrowser for Reddit)."""

    def admitted_route(self, site, label):
        return "proxy_not_admitted"


DENY_ROUTES = _DenyRoutes()


@dataclass(frozen=True)
class SessionResult:
    site: str
    label: str
    state: str
    reason: str | None
    mode: str
    owner_initiated: bool
    cookie_names_present: tuple[str, ...] = ()
    earliest_expiry: float | None = None
    expiry_class: str | None = None
    # (name, value, expires) for site `x` only, in memory for the caller; never in repr or `public()`.
    cookies: tuple = field(default=(), repr=False, compare=False)

    def public(self) -> dict:
        return {"site": self.site, "label": self.label, "state": self.state, "reason": self.reason,
                "mode": self.mode, "owner_initiated": self.owner_initiated,
                "cookie_names_present": list(self.cookie_names_present),
                "earliest_expiry": self.earliest_expiry, "expiry_class": self.expiry_class}


def expiry_class(cookies, required, now):
    """CK-5: earliest expiry among the site's required cookies and its class."""
    expiries = [c.get("expires") for c in cookies if c.get("name") in required]
    if not expiries:
        return None, "absent"
    if any(e is None or e <= 0 for e in expiries):
        return None, "session"
    earliest = min(expiries)
    left = earliest - now
    if left <= 0:
        klass = "expired"
    elif left < DAY_SECONDS:
        klass = "lt_1d"
    elif left < 7 * DAY_SECONDS:
        klass = "lt_7d"
    elif left < 30 * DAY_SECONDS:
        klass = "lt_30d"
    else:
        klass = "ge_30d"
    return earliest, klass


def classify(site, href, cookies, now):
    """CK-1 decision on the final URL and the projected jar. Returns (state, reason, names, earliest, class)."""
    spec = SITES[site]
    names = tuple(sorted({c["name"] for c in cookies}))
    earliest, klass = expiry_class(cookies, spec.required, now)

    def out(state, reason):
        return state, reason, names, earliest, klass

    parts = urlsplit(href) if isinstance(href, str) else None
    if parts is None or parts.scheme != "https" or parts.netloc not in (spec.host, spec.host + ":443"):
        return out("login_required", "host_mismatch")
    path = parts.path or "/"
    if site == "x":
        if path.startswith(_X_LOGIN):
            return out("login_required", "login_page")
        if path.startswith(_X_CHALLENGE):
            return out("challenge", "challenge_page")
        if path != "/home":
            return out("login_required", "not_home")
        if not set(spec.required) <= set(names):
            return out("login_required", "session_cookie_missing")
        return out("logged_in", None)
    first = path.strip("/").split("/")[0]
    if first in _REDDIT_LOGIN:
        return out("login_required", "login_page")
    if first in _REDDIT_CHALLENGE:
        return out("challenge", "challenge_page")
    if "reddit_session" not in names:
        return out("login_required", "session_cookie_missing")
    if klass in ("expired", "session"):
        return out("login_required", "session_cookie_expired")
    return out("logged_in", None)


def observe(client, site, *, interactive, timeout, clock=time.monotonic, sleep=time.sleep, wall=time.time,
            check=lambda: None):
    """Open the home page once, then poll without any input event.

    Automatic/probe: wait (<= timeout) only for the page to leave `about:blank`, then classify once.
    Interactive (owner logs in or recovers by hand in the visible window): poll until logged in or timeout.
    """
    spec = SITES[site]
    started = clock()
    sid = client.open_page()
    client.navigate(sid, spec.home)
    while True:
        check()
        href = client.location_href(sid)
        settled = href != "about:blank"
        if settled or interactive:
            values = []
            jar = client.cookies(sid, spec.cookie_urls, hook=values.extend if site == "x" else None)
            state, reason, names, earliest, klass = classify(site, href, jar, wall())
            if state == "logged_in" or not interactive:
                break
            values.clear()
        if clock() - started >= timeout:
            if not settled:
                state, reason, names, earliest, klass = classify(site, href, [], wall())
            break
        sleep(POLL_SECONDS)
    kept = tuple(values) if state == "logged_in" and site == "x" else ()
    if not kept:
        values.clear()
    return {"state": state, "reason": reason, "cookie_names_present": names, "earliest_expiry": earliest,
            "expiry_class": klass, "cookies": kept}


class SessionRefused(Exception):
    """The browser session could not be opened (or failed under the host/relay); `reason` is a closed code."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@contextmanager
def open_browser(site, label, *, host, profile_name, routes, role, policy, max_body_bytes=None,
                 clock=time.monotonic):
    """One admitted relay, one launched profile, one CDP client with `Browser.getVersion` proven; yields
    `(client, session, relay)`. Teardown is the host's job-object close and the relay close, never CDP.
    Shared by the session check (CK-1) and the Reddit browser reader (S-RBrowser)."""
    route = routes.admitted_route(site, label)
    if not isinstance(route, AdmittedRoute) or route.mode not in ("proxy", "direct"):
        raise SessionRefused("proxy_not_admitted")
    try:
        relay = relay_mod.Relay(site, label, route.mode, revision=route.revision, admission=route.admission,
                                hosts=route.hosts, route=route.route)
    except relay_mod.RelayFailure as exc:
        raise SessionRefused("proxy_not_admitted" if exc.reason == "proxy_not_admitted" else exc.reason) from None
    try:
        port = relay.start()
        with host.launch(label, profile_name, port) as session:
            try:
                client = cdp.CdpClient(session.pipe, role, policy, max_body_bytes=max_body_bytes, clock=clock)
                client.version()
            except bh.BrowserFailure:
                raise SessionRefused("cdp_pipe_unavailable") from None
            yield client, session, relay
    except (bh.BrowserFailure, relay_mod.RelayFailure, profiles.ProfileFailure) as exc:
        raise SessionRefused(exc.reason if hasattr(exc, "reason") else "profile_acl_unverified") from None
    finally:
        relay.close()


def check_session(site, label, *, host, profile_name, day_guard, routes, mode="automatic", timeout=120,
                  clock=time.monotonic, sleep=time.sleep, wall=time.time) -> SessionResult:
    """CK-1/CK-2/CK-7. Behind the machine-wide lock (taken by `host.launch`); never retries."""
    if site not in SITES or mode not in ROLES or not (isinstance(timeout, (int, float)) and 1 <= timeout <= 300):
        raise ValueError("site, mode and timeout required")
    owner = mode != "automatic"

    def result(state, reason, **fields):
        return SessionResult(site, label, state, reason, mode, owner, **fields)

    def stop(reason):
        return result("refused" if reason in REFUSED_REASONS else "failed", reason)

    if not owner:
        day = datetime.fromtimestamp(wall(), timezone.utc).date().isoformat()
        if not day_guard.try_claim(site, label, day):
            return result("failed", "daily_check_used")
    try:
        with open_browser(site, label, host=host, profile_name=profile_name, routes=routes, role=ROLES[mode],
                          policy=cdp.UrlPolicy(site), clock=clock) as (client, session, _relay):
            try:
                fields = observe(client, site, interactive=mode == "interactive", timeout=timeout, clock=clock,
                                 sleep=sleep, wall=wall, check=session.check)
            except bh.BrowserFailure as exc:
                if exc.reason == "navigation_off_allowlist":
                    return result("login_required", exc.reason)
                return stop(exc.reason)
            return result(fields.pop("state"), fields.pop("reason"), **fields)
    except SessionRefused as exc:
        return stop(exc.reason)


def _profile_name(config, site, label):
    if site == "x":
        return dict(config.x_account_profiles).get(label)
    return {a["label"]: a["profile"] for a in config.reddit_browser_accounts}.get(label)


def _emit(out, payload, code):
    out.write(json.dumps(payload, sort_keys=True) + "\n")
    return code


def main(argv=None, *, config=None, host=None, day_guard=None, routes=None, out=sys.stdout):
    parser = argparse.ArgumentParser(prog="python -m api.data.attention.browser_session")
    parser.add_argument("--site", choices=sorted(SITES), required=True)
    parser.add_argument("--label", required=True)
    from pathlib import Path
    parser.add_argument("--queries", type=Path, help="absolute private query file outside the repository")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--init-profile", action="store_true")
    group.add_argument("--interactive", action="store_true")
    group.add_argument("--probe", action="store_true")
    args = parser.parse_args(argv)
    from api.data.attention import web_queries
    if args.queries is not None:
        if not args.queries.is_absolute() or not web_queries._outside_repo(str(args.queries.resolve())):
            parser.exit(2, f"{parser.prog}: error: --queries must be absolute and outside the repository\n")
    mode = "interactive" if args.interactive else "probe" if args.probe else "automatic"
    head = {"site": args.site, "label": args.label}
    config_path = args.queries
    if config is None:
        try:
            config = web_queries.load(config_path).config
        except (OSError, ValueError):
            return _emit(out, {**head, "state": "failed", "reason": "config_invalid"}, 2)
        configured = config.x_proxy_required or any(getattr(config, key) is not None for key in
            ("x_proxy_list_path", "x_proxy_assignments_path", "x_proxy_policy_path"))
        if configured and config_path is None:
            return _emit(out, {**head, "state": "failed", "reason": "private_queries_required"}, 2)
    name = _profile_name(config, args.site, args.label)
    if name is None:
        return _emit(out, {**head, "state": "failed", "reason": "label_unconfigured"}, 2)
    if mode == "automatic" and day_guard is None and not args.init_profile:
        if args.site != "reddit":  # the X pool key is wired by S-Cookie-X
            return _emit(out, {**head, "state": "failed", "reason": "day_guard_unavailable"}, 2)
        from api.data.attention import reddit_accounts
        day_guard = reddit_accounts.from_config(config, clock=lambda: datetime.now(timezone.utc))
    if host is None:
        if not config.browser_path or not config.browser_profiles_dir:
            return _emit(out, {**head, "state": "failed", "reason": "browser_not_configured"}, 2)
        from api.data import cache
        host = bh.BrowserHost(config.browser_path, config.browser_profiles_dir, cache_root=cache.CACHE_ROOT,
                              memory_floor=config.browser_memory_floor_mb,
                              rss_ceiling=config.browser_rss_ceiling_mb,
                              timeout=min(300, config.x_harvest_timeout_s + 60))
    if args.init_profile:
        try:
            host.profiles.prepare(args.label, name)
        except profiles.ProfileFailure as exc:
            return _emit(out, {**head, "state": "failed", "reason": exc.reason}, 2)
        return _emit(out, {**head, "profile": "created"}, 0)
    if routes is None and args.site == "reddit":  # S-RBrowser: the Reddit label's B2 route (default deny)
        from api.data.attention import reddit_browser
        routes = reddit_browser.RedditRoutes(config, config_path=config_path)
        routes.refresh()
        routes.admit(args.label)
    result = check_session(args.site, args.label, host=host, profile_name=name, day_guard=day_guard,
                           routes=routes or DENY_ROUTES, mode=mode, timeout=config.x_harvest_timeout_s)
    if args.site == "reddit" and result.state in SESSION_RECORD:
        from api.data.attention import reddit_accounts
        reddit_accounts.from_config(config, clock=lambda: datetime.now(timezone.utc)).record_session(
            args.label, SESSION_RECORD[result.state])  # an owner relogin reopens a login/challenge pause (BR-4)
    return _emit(out, result.public(), 0 if result.state == "logged_in" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
