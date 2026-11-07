"""PR1 `gql-anon` owner-probe executor (S-RGQL), registered with `probe_owner.register('PR1')`.

Bounds: <= 120 requests (`probe_owner.PROBES['PR1']`), each charged BEFORE it is sent. Steps: mint one app-only token
(the `Authorization: Basic` mint header is built by `reddit_gql` from the section's public `client_id`), page the
`new` feed of each probe subreddit down to the start of the newest completed UTC day, then read `PostComments` of the
busiest listed thread (<= 3 pages). `bootstrap` runs against the owner's draft `gql_anon` section (not gated);
`verify` against the PUBLISHED section `probe_owner.run` loaded, so the record binds its hash and revision.
Only allowlisted reason codes leave the executor: no token, client id, URL, text or username.

Dependencies (`build_dependencies`, only after approval): `transport` (`reddit_gql.Transport`), `section`
(bootstrap only), optional `now()` and `subreddits`.
"""
from __future__ import annotations

from datetime import datetime, timezone

from api.data.attention import density, reddit_core
from api.data.attention import reddit_gql as rg
from api.scripts import probe_owner as po

MAX_COMMENT_PAGES = 3
MAX_FEED_PAGES = 120  # never above the request budget, which is the real bound
REASON = {"budget_exhausted": "budget_exhausted", "transport_failed": "transport_failed",
          "rate_limited": "rate_limited", "blocked": "blocked", "schema_mismatch": "schema_mismatch",
          "unsupported_format": "unsupported_format", "empty_shell": "empty_shell",
          "queryid_changed": "queryid_changed"}


def _need(run, *names):
    missing = [n for n in names if run.dependencies.get(n) is None]
    if missing:
        raise po.ProbeRefused('dependency_missing:' + ','.join(missing))
    return [run.dependencies[n] for n in names]


@po.register('PR1')
def pr1_gql_anon(run):
    transport, = _need(run, 'transport')
    section = run.section if run.mode == 'verify' else _need(run, 'section')[0]
    now = (run.dependencies.get('now') or (lambda: datetime.now(timezone.utc)))()
    subs = tuple(run.dependencies.get('subreddits') or (reddit_core.CANARY_SUBREDDIT,))
    try:
        requests = rg.load_requests(section)
    except rg.RequestsInvalid:
        return po.Outcome('fail', ('schema_mismatch',))
    mints = [0]

    def may_mint():
        mints[0] += 1
        return mints[0] <= rg.MAX_MINTS_PER_DAY

    client = rg.GqlClient(section, requests, transport, charge=lambda: run.budget.charge('requests'),
                          may_mint=may_mint, clock=lambda: now)
    floor = density.window(density.completed_day(now))[0]
    try:
        listed = []
        for sub in subs:
            cursor = None
            for _ in range(MAX_FEED_PAGES):
                page = client.page('posts', subreddit=sub, cursor=cursor)
                listed += page.items
                if any(r.created <= floor for r in page.items) or page.has_more is False or not page.next_cursor:
                    break
                cursor = page.next_cursor
            else:
                return po.Outcome('inconclusive', ('inconclusive',))
        busiest = max((r for r in listed if r.kind == 'post'), key=lambda r: r.num_comments or 0, default=None)
        if busiest is not None and (busiest.num_comments or 0) > 0:
            cursor = None
            for _ in range(MAX_COMMENT_PAGES):
                page = client.page('comments', post_id=busiest.id, cursor=cursor)
                if page.has_more is False or not page.next_cursor:
                    break
                cursor = page.next_cursor
    except rg.GqlStop as exc:
        return po.Outcome('fail', (REASON.get(exc.kind, 'transport_failed'),))
    return po.Outcome('pass')


def build_dependencies(config, *, config_path=None):
    """Production transport for an APPROVED PR1 run: the section from `reddit_surface_path` (draft for bootstrap,
    published for verify) and the admitted transport (`reddit_gql.route_transport`, default deny)."""
    from pathlib import Path

    from api.data.attention import reddit_surface as rs
    if not config.reddit_surface_path:
        raise po.ProbeRefused('surface_unpublished')
    try:
        section = rs.load_surface(Path(config.reddit_surface_path), rg.SECTION)
    except rs.SurfaceInvalid:
        raise po.ProbeRefused('surface_unpublished') from None
    from api.data.attention import reddit_browser
    from api.data.attention.browser_session import AdmittedRoute
    configured = config.x_proxy_required or any(getattr(config, key) is not None for key in
        ('x_proxy_list_path', 'x_proxy_assignments_path', 'x_proxy_policy_path'))
    if configured:
        if config_path is None:  # routed mode never falls back to the committed query file
            raise po.ProbeRefused('route_not_admitted')
        routes = reddit_browser.RedditRoutes(config, config_path=config_path)
        pool = routes.refresh()
        for label in pool.labels:
            routes.admit(label)
        label = pool.select()
        if label is None:
            raise po.ProbeRefused('no_ready_account')
        class SelectedRoute:
            def admitted_route(self, site, method):
                if site != 'reddit' or method != rg.SECTION:
                    return 'proxy_not_admitted'
                route = routes.admitted_route(site, label)
                if not isinstance(route, AdmittedRoute) or not route.admission():
                    return 'proxy_not_admitted'
                return route
        transport = rg.route_transport(config, routes=SelectedRoute(),
                                       policy=routes.runtime.snapshot.policy, hosts=section.hosts)
    else:
        transport = rg.route_transport(config, hosts=section.hosts)
    if transport is None:
        raise po.ProbeRefused('route_not_admitted')
    return {'transport': transport, 'section': section}
