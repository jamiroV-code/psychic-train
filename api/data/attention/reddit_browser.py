"""Finish plan S-RBrowser (BR-1..BR-6): the PRIMARY Reddit live method (`browser` -> store `reddit_live_browser`).

Honest scope: the owner's chosen route. A throwaway account's own browser profile (one manual login, the one-week
rest) is launched per poll through the admitted relay; Reddit's enforcement signal is login, so a logged-out or
challenged account is paused for the owner (`needs_owner`, relogin by `browser_session --site reddit --interactive`)
and the poll is retried once on another ready account. Comments are observed only for the threads a poll opens
(`threads_opened`). Default off: nothing runs unless `browser` is named in `reddit_live_methods`.

BR-1 gate (`gate_state`): `browser` switched on; the published `browser` section of `reddit_surface_path` loads; a
`verify` record of probe PR2 is fresh and matches its hash and revision (`probe_owner.verify_gate`); the browser
binary is configured and its relay admission record is current (`browser_host.read_admission`: else
`browser_unadmitted` / `containment_residual_unaccepted`); the last session refusal (`cdp_pipe_unavailable`,
`profile_policy_unsatisfied`) has aged out; at least one Reddit account is ready. The launch-time login check runs
inside each poll on the first navigation (final URL + cookie names only), so no extra navigation is spent.

BR-2 evidence: allowlisted pages only (A3: `/r/<sub>/new/`, `/r/<sub>/comments/<id>/`); captured responses are
matched to the section endpoints (`reddit_surface.match_request`) and read ONLY through the grammar
(`extract_page`); each page's request must carry the previous page's cursor (request -> response -> body
correlation along the cursor chain) down to the floor. A lane ends `exhausted|cap|error|empty_shell|login_required|
schema_mismatch|unsupported_format`; a navigation that yields no matching response is `empty_shell`, never zero.

BR-3 budgets: the daily navigation cap (`reddit_browser_daily_navigation_cap`, enforced by the worker and per poll),
the per-account cap (`reddit_browser_account_daily_cap`), the daily browser minutes (`reddit_browser_daily_minutes`,
persisted here), at most 12 scrolls per page, one machine-wide browser (the host's machine lock: a pending X
harvest makes the poll wait `BUSY_RETRY_S`). Nothing here stores text or usernames: items are reduced at once.

Account scheduling (BR-4): `reddit_accounts.run_poll` over the pool built with `RedditRoutes.route_admission` (the
S-RAcct-B provider); `RedditRoutes` is also the CK-6 `RouteProvider` for Reddit labels, built over the B2
`ProxyRuntime` reconciled with `reddit=RedditRouteView` (the X pool is never written from here). The relay
allowlist of a read is the PUBLISHED section's `hosts`.
"""
from __future__ import annotations

import dataclasses
import json
import time
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from api.data import cache
from api.data.attention import browser_cdp as cdp
from api.data.attention import browser_host as bh
from api.data.attention import browser_session as bs
from api.data.attention import reddit_accounts as ra
from api.data.attention import reddit_core, reddit_live
from api.data.attention import reddit_surface as rs
from api.scripts.surface_tool import Capture

SECTION = "browser"
STORE = reddit_core.STORES[SECTION]
HOST = "www.reddit.com"
MAX_PAGES_PER_LANE = 40
MAX_PAGES_PER_THREAD = 5
SCROLL_PX = 2400
SETTLE_ROUNDS = 6
SETTLE_SLEEP_S = 0.5
BUSY_RETRY_S = 60
REFUSAL_HOLD_S = 3600
DIRECT_ADMISSION_S = 900
# a lost session as the account pool records it (`reddit_accounts.LOSS_REASONS`)
LOSS = {"login_required": "reddit_login_required", "challenge": "challenge"}
STICKY_REFUSALS = ("browser_unadmitted", "containment_residual_unaccepted", "cdp_pipe_unavailable",
                   "profile_policy_unsatisfied")


def listing_url(sub: str) -> str:
    return f"https://{HOST}/r/{sub}/new/"


def thread_url(sub: str, thread: str) -> str:
    return f"https://{HOST}/r/{sub}/comments/{thread.removeprefix('t3_')}/"


class Lost(Exception):
    """The account's session is lost mid-poll; `reason` is a `reddit_accounts.LOSS_REASONS` code."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class Refused(Exception):
    """The browser could not run this poll (not an account problem); `reason` is a closed code."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# --- budgets ---

class PollBudget:
    """One attempt's bounds: navigations left (daily and account), scrolls per page and the minutes left."""

    def __init__(self, navigations: int, seconds: float, *, clock: Callable[[], float] = time.monotonic,
                 scrolls_per_page: int = 12):
        self.left, self.clock, self.deadline = max(navigations, 0), clock, clock() + max(seconds, 0)
        self.scrolls_per_page = scrolls_per_page
        self.navs = self.scrolls = self.responses = 0
        self._page_scrolls = 0

    def navigate(self) -> bool:
        if self.left <= 0 or self.clock() >= self.deadline:
            return False
        self.left -= 1
        self.navs += 1
        self._page_scrolls = 0
        return True

    def scroll(self) -> bool:
        if self._page_scrolls >= self.scrolls_per_page or self.clock() >= self.deadline:
            return False
        self._page_scrolls += 1
        self.scrolls += 1
        return True

    def response(self, nbytes: int) -> bool:
        self.responses += 1
        return True


# --- the evidence state machine (BR-2) over a driver ---

def cursor_of(ep: rs.Endpoint, capture) -> str | None:
    """The cursor a captured request carried, where the endpoint's `request_cursor` places it."""
    kind, arg = ep.request_cursor
    parts = urlsplit(capture.url)
    if kind == "query":
        return dict(parse_qsl(parts.query, keep_blank_values=True)).get(arg)
    if kind == "path":
        segs = parts.path.split("/")
        i = int(arg)
        return segs[i] if i < len(segs) else None
    if not capture.request_body:
        return None
    try:
        value = rs.resolve(json.loads(capture.request_body), rs.parse_pointer(arg))
    except (ValueError, rs.SurfaceInvalid):
        return None
    return value if isinstance(value, str) else None


@dataclasses.dataclass
class Chain:
    pages: list
    stop: str
    abort: bool = False


def read_chain(driver, section: rs.Section, lane: str, url: str, *, budget, max_pages: int,
               floor: datetime | None = None) -> Chain:
    """Navigate once, then follow the lane's cursor chain through captured responses (scrolling for each next
    page). Raises `Lost` when the page is a login or challenge page."""
    if not budget.navigate():
        return Chain([], "cap", abort=True)
    try:
        state = driver.navigate(url)
        if state in LOSS:
            raise Lost(LOSS[state])
        pool = list(driver.drain())
    except bh.BrowserFailure as exc:
        if exc.reason == "navigation_off_allowlist":
            raise Lost("reddit_login_required") from None
        return Chain([], "error", abort=True)
    pages, want, used = [], None, set()
    while True:
        found, failed = None, False
        for i, c in enumerate(pool):
            if i in used:
                continue
            ep = rs.match_request(section, c.method, c.url, c.request_body)
            if ep is None or ep.lane != lane:
                continue
            cur = cursor_of(ep, c)
            if cur == want or (want is None and not pages and ep.request_cursor[0] == "path"):
                used.add(i)
                if c.status != 200:
                    failed = True
                found = (ep, c)
                break
        if found is None:
            if not pages:
                return Chain(pages, "empty_shell")
            if not budget.scroll():
                return Chain(pages, "cap", abort=budget.clock() >= budget.deadline)
            try:
                driver.scroll()
                pool += driver.drain()
            except bh.BrowserFailure:
                return Chain(pages, "error", abort=True)
            if any(i not in used and (ep := rs.match_request(section, c.method, c.url, c.request_body))
                   and ep.lane == lane and cursor_of(ep, c) == want for i, c in enumerate(pool)):
                continue
            return Chain(pages, "error")
        ep, c = found
        if failed:
            return Chain(pages, "error")
        budget.response(len(c.body))
        try:
            page = rs.extract_page(section, ep, status=c.status, content_type=c.content_type, body=c.body)
        except rs.SurfaceError as exc:
            return Chain(pages, exc.reason)
        pages.append(page)
        reached = floor is not None and any(r.created <= floor for r in page.items)
        if reached or page.has_more is False or not page.next_cursor:
            return Chain(pages, "exhausted")
        if len(pages) >= max_pages:
            return Chain(pages, "cap")
        want = page.next_cursor


# --- the CDP driver (production) ---

class CdpDriver:
    """The PR2 driver seam over one `CdpClient` page: navigate (classify login/challenge pages), scroll, drain the
    finished captures (bodies only for `data` records), the relay's refused hosts."""

    def __init__(self, client, relay=None, *, sleep: Callable[[float], None] = time.sleep, wall=time.time,
                 check: Callable[[], None] = lambda: None):
        self.client, self.relay, self.sleep, self.wall, self.check = client, relay, sleep, wall, check
        self.sid = client.open_page()
        self._seen: set[str] = set()
        self._first = True

    def __repr__(self) -> str:
        return "CdpDriver()"

    def navigate(self, url: str) -> str:
        """`ok`, `login_required` or `challenge`. The first navigation of a session is the launch-time login
        check (final URL and cookie names, CK-1 `classify`); later ones check the final URL's first segment."""
        self.check()
        self.client.navigate(self.sid, url)
        href = self.client.location_href(self.sid)
        if self._first:
            self._first = False
            jar = self.client.cookies(self.sid, bs.SITES["reddit"].cookie_urls)
            state = bs.classify("reddit", href, jar, self.wall())[0]
            return "ok" if state == "logged_in" else state
        return _page_state(href)

    def scroll(self) -> None:
        self.check()
        self.client.scroll(self.sid, SCROLL_PX)

    def drain(self) -> list:
        """New finished captures after the page settles (no new record for one round, bounded)."""
        count = -1
        for _ in range(SETTLE_ROUNDS):
            self.client.location_href(self.sid)  # pumps the event queue
            done = [r for r in self.client.responses() if r.request_id not in self._seen]
            if done and len(done) == count:
                break
            count = len(done)
            self.sleep(SETTLE_SLEEP_S)
        out = []
        for r in self.client.responses():
            if r.request_id in self._seen or r.kind not in ("data", "http_error"):
                continue
            self._seen.add(r.request_id)
            body = b""
            if r.kind == "data":
                try:
                    body = self.client.body(self.sid, r.request_id)
                except bh.BrowserFailure as exc:
                    if exc.reason not in ("capture_evicted", "capture_too_large"):
                        raise
                    continue
            out.append(Capture(url=r.url, method=r.method, status=r.status or 0, content_type=r.mime or "",
                               body=body))
        return out

    def refused_hosts(self) -> dict:
        return dict(self.relay.health().get("relay_refusals", {})) if self.relay is not None else {}


def _page_state(href) -> str:
    parts = urlsplit(href) if isinstance(href, str) else None
    first = (parts.path or "/").strip("/").split("/")[0] if parts else ""
    if first in bs._REDDIT_LOGIN:
        return "login_required"
    return "challenge" if first in bs._REDDIT_CHALLENGE else "ok"


# --- routes (CK-6 Reddit provider over the B2 runtime) ---

class _XUntouched:
    """The X side handed to `ProxyRuntime.reconcile` from here: the Reddit reader never writes X pool state."""

    proxy_direct = proxy_required = connection_style = proxy_regions = None

    def _acct(self, label):
        return {"proxy_id": None}

    def reconcile_proxy(self, label, proxy_id, revision):
        return False

    def proxy_unknown(self, label, reason, *, wake_at=None):
        return None


class RedditRoutes:
    """Reddit account routes: `route_admission(site, label)` for `reddit_accounts` (S-RAcct-B), and the CK-6
    `admitted_route(site, label) -> AdmittedRoute | refusal` for the relay. A pure lookup over the runtime's
    snapshot; `refresh()` reconciles (`reddit=RedditRouteView`) and `admit(label)` runs the B2 admission."""

    def __init__(self, config, *, config_path=None, repo_root=None, runtime=None,
                 wall: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                 clock: Callable[[], float] = time.monotonic):
        repo_root = repo_root or Path(__file__).resolve().parents[3]
        self.config, self.wall, self.clock = config, wall, clock
        if runtime is None:
            from api.data.attention.x_proxy_runtime import ProxyRuntime
            runtime = ProxyRuntime(config, config_path=config_path, repo_root=repo_root)
        self.runtime = runtime
        self.accounts = ra.from_config(config, clock=wall, admission=self.route_admission)
        self.view = None

    def __repr__(self) -> str:
        return "RedditRoutes(<private>)"

    def refresh(self) -> ra.RedditAccounts:
        from api.data.attention import x_pool
        from api.data.attention import x_proxy as xp
        from api.data.attention.x_proxy_runtime import ProviderBudget, RedditRouteView
        if self.view is None:
            budget_pool = x_pool.from_config(self.config, clock=self.wall) if self.config.x_accounts else None
            self.view = RedditRouteView(self.accounts, ProviderBudget(budget_pool), clock=self.wall)
        try:
            self.runtime.reconcile(_XUntouched(), reddit=self.view)
        except xp.ProxyFailure:
            self.runtime.snapshot = None  # unreadable route configuration: every Reddit label is unadmitted
        return self.accounts

    def proxy_mode(self) -> bool:
        snapshot = self.runtime.snapshot
        return snapshot is not None and snapshot.policy is not None

    def admittable(self, label: str) -> bool:
        snapshot = self.runtime.snapshot
        return self.proxy_mode() and label in snapshot.reddit_assignments

    def admit(self, label: str) -> None:
        from api.data.attention import x_proxy as xp
        if self.view is None or not self.admittable(label) or self.runtime.admitted(label):
            return
        try:
            self.runtime.admit(label, self.view)
        except xp.ProxyFailure:
            return  # the view recorded the quarantine; the account stays locked

    def route_admission(self, site: str, label: str) -> str:
        if self.runtime.snapshot is None:
            return "unadmitted"
        return self.runtime.route_admission(site, label)

    def admitted_route(self, site: str, label: str):
        from api.data.attention import browser_relay as relay
        runtime, snapshot = self.runtime, self.runtime.snapshot
        if (site != "reddit" or snapshot is None
                or label not in {a["label"] for a in snapshot.config.reddit_browser_accounts}):
            return "proxy_not_admitted"
        if snapshot.policy is None:
            if snapshot.config.x_proxy_required:
                return "proxy_not_admitted"
            revision = "direct-" + label
            return bs.AdmittedRoute("direct", revision,
                                    lambda: relay.Admission(revision, self.clock() + DIRECT_ADMISSION_S))
        revision = snapshot.revisions.get(label)
        if revision is None or label not in snapshot.reddit_assignments or not runtime.admitted(label):
            return "proxy_not_admitted"

        def admission():
            item = runtime.admissions.get(label)
            if item is None or item.revision != revision or not runtime.admitted(label):
                return None
            return relay.Admission(revision, self.clock() + (item.expires_at - runtime.clock()).total_seconds())

        return bs.AdmittedRoute("proxy", revision, admission, route=snapshot.reddit_assignments[label].route)


class _Hosts:
    """A provider whose admitted routes carry the given relay allowlist (the published section's hosts)."""

    def __init__(self, routes, hosts):
        self.routes, self.hosts = routes, hosts

    def admitted_route(self, site, label):
        route = self.routes.admitted_route(site, label)
        if isinstance(route, bs.AdmittedRoute):
            return dataclasses.replace(route, hosts=self.hosts)
        return route


# --- sessions ---

class BrowserSessions:
    """Opens one account's browser per poll: admitted relay (hosts from the section; bootstrap: the relay's
    bootstrap set), launched profile, `CdpClient` of the role, `CdpDriver`. Refusals raise `Refused`, a lost
    route `Lost('proxy_not_admitted')`."""

    def __init__(self, config, *, host, routes, sleep=time.sleep, wall=time.time):
        self.config, self.host, self.routes, self.sleep, self.wall = config, host, routes, sleep, wall

    def __repr__(self) -> str:
        return "BrowserSessions()"

    def profile(self, label: str) -> str | None:
        return {a["label"]: a["profile"] for a in self.config.reddit_browser_accounts}.get(label)

    @contextmanager
    def open(self, label: str, *, role: str, section: rs.Section | None, subreddits=()):
        name = self.profile(label)
        if name is None:
            raise Refused("label_unconfigured")
        hosts = section.hosts if section is not None and role == "reddit_read" else None
        policy = cdp.UrlPolicy("reddit", subreddits=tuple(dict.fromkeys(subreddits)))
        try:
            with bs.open_browser("reddit", label, host=self.host, profile_name=name, routes=_Hosts(self.routes, hosts),
                                 role=role, policy=policy,
                                 max_body_bytes=section.max_body_bytes if role == "reddit_read" else None) as (
                    client, session, relay):
                yield CdpDriver(client, relay, sleep=self.sleep, wall=self.wall, check=session.check)
        except bs.SessionRefused as exc:
            if exc.reason == "proxy_not_admitted":
                raise Lost("proxy_not_admitted") from None
            raise Refused(exc.reason) from None


def build_host(config):
    if not config.browser_path or not config.browser_profiles_dir:
        return None
    return bh.BrowserHost(config.browser_path, config.browser_profiles_dir, cache_root=cache.CACHE_ROOT,
                          memory_floor=config.browser_memory_floor_mb, rss_ceiling=config.browser_rss_ceiling_mb,
                          timeout=600)


# --- persisted browser minutes ---

def browser_state_path() -> Path:
    return reddit_live.state_path(STORE).parent / "_browser_state.json"


def read_browser_state(now: datetime) -> dict:
    day = now.astimezone(timezone.utc).date().isoformat()
    path = browser_state_path()
    s = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return s if s.get("day") == day else {"day": day, "seconds": 0.0}


def charge_seconds(now: datetime, seconds: float) -> None:
    s = read_browser_state(now)
    s["seconds"] = round(s["seconds"] + max(seconds, 0.0), 3)
    path = browser_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    cache._atomic_write_json(s, path)


# --- the LiveMethod ---

class BrowserMethod:
    method_id = SECTION
    label = reddit_core.LABELS[SECTION]
    store = STORE

    def __init__(self, config, *, routes, sessions, admission: Callable[[], str | None], clock, monotonic,
                 hasher=None, queries=None):
        self.config, self.routes, self.sessions = config, routes, sessions
        self._admission, self.clock, self.monotonic = admission, clock, monotonic
        self._hasher, self._queries = hasher, queries
        self.last_account: str | None = None
        self._refusal: tuple[str, datetime] | None = None
        self._busy_until: datetime | None = None

    def __repr__(self) -> str:
        return "BrowserMethod()"

    def _section(self) -> rs.Section:
        return rs.load_surface(Path(self.config.reddit_surface_path), SECTION)

    def gate_state(self, now: datetime) -> str:
        from api.scripts import probe_owner
        if SECTION not in self.config.reddit_live_methods:
            return "disabled"
        if not self.config.reddit_surface_path:
            return "needs_probe"
        try:
            self._section()
        except rs.SurfaceInvalid as exc:
            return "unsupported_format" if exc.reason == "unsupported_format" else "needs_probe"
        verdict = probe_owner.verify_gate(cache.CACHE_ROOT, SECTION, surface_path=Path(self.config.reddit_surface_path),
                                          max_age_days=self.config.reddit_live_probe_max_age_days,
                                          today=now.astimezone(timezone.utc).date())
        if verdict != "ok":
            return "needs_probe"
        if self.sessions is None:
            return "method_unavailable"
        refused = self._admission()
        if refused is not None:
            return refused
        if self._refusal is not None and now < self._refusal[1]:
            return self._refusal[0]
        pool = self.routes.refresh()
        ready = [x for x in pool.labels if pool.account_state(x)[0] == "active"
                 or (pool.account_state(x) == ("locked", "proxy_not_admitted") and self.routes.admittable(x))]
        return "ready" if ready else "no_ready_account"

    def next_poll_due(self, now: datetime) -> datetime | None:
        due = []
        if self._busy_until is not None and now < self._busy_until:
            due.append(self._busy_until)
        if read_browser_state(now)["seconds"] >= self.config.reddit_browser_daily_minutes * 60:
            day = now.astimezone(timezone.utc).date() + timedelta(days=1)
            due.append(datetime(day.year, day.month, day.day, tzinfo=timezone.utc))
        return max(due) if due else None

    def close(self) -> None:
        return None

    def _matchers(self):
        from api.data.attention import reddit_items, reddit_metrics, web_queries
        hasher = self._hasher or reddit_items.AuthorHasher(reddit_items.load_salt(create=True))
        q = self._queries() if self._queries is not None else web_queries.load()
        terms = reddit_metrics.coin_terms(q)
        return hasher, (lambda text: reddit_metrics.matched_coins(text, terms))

    def _known_threads(self, now) -> dict[str, tuple[str, int]]:
        out: dict[str, tuple[str, int]] = {}
        for lane in reddit_live.read_lanes(STORE, now.date() - timedelta(days=2), now.date()):
            if lane.kind == "posts":
                for t, n in lane.threads:
                    out[t] = (lane.subreddit, n)
        return out

    def run_poll(self, ctx: reddit_live.PollContext) -> reddit_live.PollResult:
        now = ctx.now
        pid = now.isoformat()
        section = self._section()
        hasher, match = self._matchers()
        pool = self.routes.refresh()
        for x in pool.labels:
            self.routes.admit(x)
        known = self._known_threads(now)
        subs = tuple(dict.fromkeys([*ctx.subreddits, *(known[t][0] for t in ctx.threads if t in known)]))
        cap, minutes = self.config.reddit_browser_account_daily_cap, self.config.reddit_browser_daily_minutes
        navs = [0]

        def read(label):
            used = read_browser_state(now)["seconds"]
            budget = PollBudget(min(ctx.requests_left - navs[0], cap - pool.reads_today(label)),
                                minutes * 60 - used, clock=self.monotonic)
            started = self.monotonic()
            try:
                with self.sessions.open(label, role="reddit_read", section=section, subreddits=subs) as driver:
                    value = self._collect(driver, ctx, section, budget, pid, known, hasher, match)
            except Lost as lost:
                navs[0] += budget.navs
                self._fact_loss(label, lost.reason, now)
                raise ra.AccountLost(lost.reason, budget.navs) from None
            finally:
                charge_seconds(now, self.monotonic() - started)
            navs[0] += budget.navs
            return value, budget.navs

        self.last_account = None
        try:
            res = ra.run_poll(pool, read)
        except Refused as exc:
            if exc.reason in ("browser_busy", "low_memory"):
                self._busy_until = now + timedelta(seconds=BUSY_RETRY_S)
            elif exc.reason in STICKY_REFUSALS:
                self._refusal = (exc.reason, now + timedelta(seconds=REFUSAL_HOLD_S))
            return reddit_live.PollResult(pid, now, (), (), 0, navs[0])
        self.last_account = res.label
        if res.value is None:
            lanes = ()
            if res.reason in LOSS.values():  # every attempt hit login/challenge: say so, never zero
                lanes = tuple(reddit_live.LaneEvidence(s, "posts", pid, now, ctx.floors[s], None, None, 0, 0, (),
                                                       "login_required") for s in ctx.subreddits)
            return reddit_live.PollResult(pid, now, lanes, (), 0, navs[0])
        lanes, items, responses = res.value
        return reddit_live.PollResult(pid, now, lanes, items, responses, navs[0])

    def _fact_loss(self, label: str, reason: str, now: datetime) -> None:
        if reason not in ("reddit_login_required", "challenge"):
            return
        from api.data.attention import daily_facts, x_pool
        try:
            daily_facts.append({"kind": "challenge", "source": "reddit", "account": label,
                                "class": "challenge" if reason == "challenge" else "login_required"},
                               now=now, switches=x_pool.facts_switches(self.config))
        except Exception:  # noqa: BLE001 - facts never stop collection
            return

    def _collect(self, driver, ctx, section, budget, pid, known, hasher, match):
        now, lanes, items, aborted = ctx.now, [], [], False
        listed_counts: dict[str, tuple[str, int]] = {}
        for sub in ctx.subreddits:
            floor = ctx.floors[sub]
            chain = read_chain(driver, section, "posts", listing_url(sub), budget=budget,
                               max_pages=MAX_PAGES_PER_LANE, floor=floor)
            seen = [r for p in chain.pages for r in p.items if r.kind == "post"]
            cursors = tuple((p.next_cursor or p.items[-1].id, min(r.created for r in p.items))
                            for p in chain.pages if p.items)
            newer = [r for r in seen if r.created > floor]
            listed = newer + sorted((r for r in seen if r.created <= floor), key=lambda r: r.created,
                                    reverse=True)[:1]
            lanes.append(reddit_live.LaneEvidence(
                sub, "posts", pid, now, floor, max((r.created for r in listed), default=None),
                min((r.created for r in listed), default=None), len(newer), len(chain.pages), cursors, chain.stop,
                tuple((r.id, r.num_comments or 0) for r in listed)))
            items += [reddit_core.reduce_item(r, hasher, match) for r in listed]
            for r in listed:
                listed_counts[r.id] = (r.subreddit, r.num_comments or 0)
            if chain.abort:
                aborted = True
                break
        if not aborted and ctx.threads:
            lanes += self._comment_lanes(driver, ctx, section, budget, pid, {**known, **listed_counts}, items,
                                         hasher, match)
        return tuple(lanes), tuple(items), budget.responses

    def _comment_lanes(self, driver, ctx, section, budget, pid, known, items, hasher, match):
        now = ctx.now
        done: dict[str, list] = {}
        failed: dict[str, tuple[list, str]] = {}
        stats: dict[str, list] = {}
        for t in ctx.threads:
            if t not in known:
                continue  # never listed by this method: no subreddit to attribute it to
            sub, count = known[t]
            chain = read_chain(driver, section, "comments", thread_url(sub, t), budget=budget,
                               max_pages=MAX_PAGES_PER_THREAD)
            got = [r for p in chain.pages for r in p.items if r.kind == "comment"]
            items += [reddit_core.reduce_item(r, hasher, match) for r in got]
            st = stats.setdefault(sub, [0, 0, None, None])
            st[0] += len(chain.pages)
            st[1] += len(got)
            for r in got:
                st[2] = r.created if st[2] is None else max(st[2], r.created)
                st[3] = r.created if st[3] is None else min(st[3], r.created)
            if chain.stop == "exhausted":
                done.setdefault(sub, []).append((t, count))
            else:
                failed.setdefault(sub, ([], chain.stop))[0].append((t, count))
            if chain.abort:
                break
        lanes = []
        for sub in dict.fromkeys([*done, *failed]):
            pages, n, newest, oldest = stats.get(sub, [0, 0, None, None])
            if sub in done:
                lanes.append(reddit_live.LaneEvidence(sub, "comments", pid, now, None, newest, oldest, n, pages, (),
                                                      "exhausted", tuple(done[sub])))
            if sub in failed:
                threads, stop = failed[sub]
                lanes.append(reddit_live.LaneEvidence(sub, "comments", pid, now, None, None, None, 0, 0, (), stop,
                                                      tuple(threads)))
        return lanes


def admission_state(config) -> str | None:
    """BG-1: the relay admission record of the configured binary (`None` when current)."""
    try:
        binary = Path(config.browser_path)
        bh.read_admission(cache.CACHE_ROOT, binary, bh.executable_version(binary))
    except bh.BrowserFailure as exc:
        return exc.reason if exc.reason == "containment_residual_unaccepted" else "browser_unadmitted"
    except (OSError, ValueError, TypeError):
        return "browser_unadmitted"
    return None


def make_method(config, deps) -> BrowserMethod:
    """RC-9 factory: `deps` from the worker (`clock`, `sleep`, optionally `config_path`, `reddit_routes`,
    `browser_host`, `reddit_sessions`, `browser_admission`, `monotonic`, `hasher`, `queries`). Without a configured
    browser the gate is `method_unavailable`; nothing launches at construction."""
    clock = getattr(deps, "clock", None) or (lambda: datetime.now(timezone.utc))
    sleep = getattr(deps, "sleep", None) or time.sleep
    routes = getattr(deps, "reddit_routes", None) or RedditRoutes(
        config, config_path=getattr(deps, "config_path", None), wall=clock)
    sessions = getattr(deps, "reddit_sessions", None)
    if sessions is None:
        host = getattr(deps, "browser_host", None) or build_host(config)
        sessions = None if host is None else BrowserSessions(config, host=host, routes=routes, sleep=sleep)
    admission = getattr(deps, "browser_admission", None) or (lambda: admission_state(config))
    return BrowserMethod(config, routes=routes, sessions=sessions, admission=admission, clock=clock,
                         monotonic=getattr(deps, "monotonic", None) or time.monotonic,
                         hasher=getattr(deps, "hasher", None), queries=getattr(deps, "queries", None))
