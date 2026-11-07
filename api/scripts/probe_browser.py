"""PR2 browser owner-probe executor (S-RBrowser), registered with `probe_owner.register('PR2')`.

Bounds (`probe_owner.limits_for('PR2', mode)`): navigations, responses, bytes, scrolls per page and seconds, each
charged BEFORE the action. The driver seam (`reddit_browser.CdpDriver` in production, a loopback fake in tests):
`navigate(url) -> 'ok'|'login_required'|'challenge'`, `scroll()`, `drain() -> [surface_tool.Capture]`,
`refused_hosts() -> {host: count}`.

`bootstrap` (bootstrap CDP role, relay bootstrap hosts): each probe subreddit's `new` listing with scrolls, then one
thread found in the captures; `surface_tool.propose('browser', ...)` reads the captures in memory and the validated
candidate is written for the owner's `surface_tool --approve-surface browser` (bodies are never written).
`verify` (reddit_read role, the PUBLISHED section's hosts): the live reader (`reddit_browser.read_chain`) pages the
first probe subreddit down to the newest completed UTC day's start and reads one listed thread through the grammar;
it passes only when both lanes end `exhausted`. Only allowlisted reason codes leave the executor.

Dependencies (`build_dependencies`, only after approval): `driver(mode, section)` -> context manager yielding a
driver; optional `now()` and `subreddits`.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from api.data.attention import density, reddit_core
from api.data.attention import reddit_browser as rb
from api.data.attention import reddit_surface as rs
from api.scripts import probe_owner as po
from api.scripts import surface_tool

STOP_REASON = {"cap": "budget_exhausted", "error": "transport_failed", "empty_shell": "empty_shell",
               "schema_mismatch": "schema_mismatch", "unsupported_format": "unsupported_format"}
LOST_REASON = {"reddit_login_required": "login_required", "challenge": "challenge",
               "proxy_not_admitted": "browser_refused"}


def _need(run, *names):
    missing = [n for n in names if run.dependencies.get(n) is None]
    if missing:
        raise po.ProbeRefused('dependency_missing:' + ','.join(missing))
    return [run.dependencies[n] for n in names]


class RunBudget:
    """`reddit_browser.read_chain`'s budget over the probe run's charges (navigations, scrolls, responses+bytes)."""

    def __init__(self, run):
        self.run, self.navs, self.responses = run, 0, 0
        self.clock, self.deadline = (lambda: 0.0), 1.0

    def navigate(self):
        ok = self.run.budget.charge('navigations')
        self.navs += ok
        return ok

    def scroll(self):
        return self.run.budget.charge('scrolls')

    def response(self, nbytes):
        self.responses += 1
        return self.run.budget.charge('responses', nbytes=nbytes)


def _thread_ids(captures):
    """Post ids seen in the captured JSON (bootstrap has no grammar yet): `t3_` strings, first seen first."""
    out = {}

    def walk(node, depth=0):
        if depth > rs.MAX_DEPTH + 4:
            return
        if isinstance(node, dict):
            for v in node.values():
                walk(v, depth + 1)
        elif isinstance(node, list):
            for v in node:
                walk(v, depth + 1)
        elif isinstance(node, str) and node.startswith('t3_') and rs.ID_RE.fullmatch(node):
            out.setdefault(node, None)
    for c in captures:
        try:
            walk(json.loads(c.body))
        except ValueError:
            continue
    return list(out)


def _bootstrap(run, driver, subs):
    captures = []

    def take():
        for c in driver.drain():
            if not run.budget.charge('responses', nbytes=len(c.body)):
                raise po.ProbeRefused('budget_exhausted')
            captures.append(c)

    for sub in subs:
        run.charge('navigations')
        state = driver.navigate(rb.listing_url(sub))
        if state != 'ok':
            return po.Outcome('fail', ('challenge',) if state == 'challenge' else ('login_required',))
        take()
        while run.budget.charge('scrolls'):
            driver.scroll()
            take()
    threads = _thread_ids(captures)
    if threads:
        run.charge('navigations')
        if driver.navigate(rb.thread_url(subs[0], threads[0])) != 'ok':
            return po.Outcome('fail', ('login_required',))
        take()
    proposal = surface_tool.propose('browser', captures, subreddits=subs, refused_hosts=driver.refused_hosts())
    captures.clear()
    if not proposal.ok:
        codes = tuple(r for r in proposal.reasons if r in po.REASONS)
        return po.Outcome('fail', ('proposal_refused', *codes))
    surface_tool.write_candidate(run.cache_root, proposal)
    return po.Outcome('pass')


def _verify(run, driver, section, subs, now):
    budget = RunBudget(run)
    floor = density.window(density.completed_day(now))[0]
    posts = rb.read_chain(driver, section, 'posts', rb.listing_url(subs[0]), budget=budget,
                          max_pages=rb.MAX_PAGES_PER_LANE, floor=floor)
    if posts.stop != 'exhausted':
        return po.Outcome('fail', (STOP_REASON.get(posts.stop, 'transport_failed'),))
    listed = [r for p in posts.pages for r in p.items if r.kind == 'post']
    busiest = max(listed, key=lambda r: r.num_comments or 0, default=None)
    if busiest is None or not busiest.num_comments:
        return po.Outcome('inconclusive', ('inconclusive',))
    comments = rb.read_chain(driver, section, 'comments', rb.thread_url(busiest.subreddit, busiest.id),
                             budget=budget, max_pages=rb.MAX_PAGES_PER_THREAD)
    if comments.stop != 'exhausted':
        return po.Outcome('fail', (STOP_REASON.get(comments.stop, 'transport_failed'),))
    return po.Outcome('pass')


@po.register('PR2')
def pr2_browser(run):
    driver_factory, = _need(run, 'driver')
    now = (run.dependencies.get('now') or (lambda: datetime.now(timezone.utc)))()
    subs = tuple(run.dependencies.get('subreddits') or (reddit_core.CANARY_SUBREDDIT,))
    section = run.section if run.mode == 'verify' else None
    try:
        with driver_factory(run.mode, section) as driver:
            if run.mode == 'bootstrap':
                return _bootstrap(run, driver, subs)
            return _verify(run, driver, section, subs, now)
    except rb.Lost as lost:
        return po.Outcome('fail', (LOST_REASON.get(lost.reason, 'login_required'),))
    except rb.Refused:
        return po.Outcome('fail', ('browser_refused',))


def build_dependencies(config):
    """Production driver for an APPROVED PR2 run: the least recently used ready Reddit account's profile, its
    admitted route (`reddit_browser.RedditRoutes`, default deny), the `bootstrap` (bootstrap hosts) or `reddit_read`
    (published section hosts) CDP role."""
    from api.data.attention import web_queries
    host = rb.build_host(config)
    if host is None:
        raise po.ProbeRefused('browser_not_configured')
    refused = rb.admission_state(config)
    if refused is not None:
        raise po.ProbeRefused(refused)
    routes = rb.RedditRoutes(config, config_path=web_queries.QUERIES_PATH)
    pool = routes.refresh()
    for label in pool.labels:
        routes.admit(label)
    label = pool.select()
    if label is None:
        raise po.ProbeRefused('no_ready_account')
    sessions = rb.BrowserSessions(config, host=host, routes=routes)

    def driver(mode, section):
        role = 'bootstrap' if mode == 'bootstrap' else 'reddit_read'
        return sessions.open(label, role=role, section=section, subreddits=(reddit_core.CANARY_SUBREDDIT,))
    return {'driver': driver}
