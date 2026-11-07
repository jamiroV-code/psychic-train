"""Real owner-probe executors for PX1-PX6, PR5 and PR6 (S-OpsProbe).

Every executor receives a `probe_owner.Run`, charges its budget BEFORE each transport action, and returns an
`Outcome` of allowlisted reason codes only: no values, no response text, no cookies leave an executor.
Transport is injected through `run.dependencies` (built by `build_dependencies` only after owner approval):
  static_get(url) -> bytes                      PX1: unauthenticated static GET (x_queryids_fetch.static_get)
  readers {label: XReader}                      PX2-PX4: `twscrape_reader.start` readers (identity-bound)
  query str                                     PX2-PX5: canary search query (x_pool.canary_query)
  adapter                                       PX4: IdentityAdapter (observe-only `ct0_rotations_seen`)
  fresh_reader(label) -> XReader                PX4: a new process-equivalent client on the stored cookies
  runs [(label, style, reader)]                 PX5: both styles on each of two accounts (V7 protocol)
  window (start, end)                           PX5: canary window
  check_session() -> SessionResult              PX6: one owner-initiated browser_session check (site x)
  refused_hosts() -> dict                       PX6: relay refusals, background_refused excluded
  routes {section: AdmittedRoute | str}         PR5: admitted routes of gql_anon and browser
  read_events(day) -> list                      PR6: daily_facts.read_events
PR1 is registered by S-RGQL (`api/scripts/probe_gql.py`, imported below so the default registry holds it) and
PR2 by S-RBrowser; PR3 is refused (A17) and PR4 reserved in `probe_owner.run`.
"""
from __future__ import annotations

from datetime import timedelta

from api.data.attention import x_queryids as q
from api.scripts import probe_owner as po

EXECUTORS_OWNED = ('PX1', 'PX2', 'PX3', 'PX4', 'PX5', 'PX6', 'PR5', 'PR6')

READ_REASON = {'not_found': 'capability_missing', 'gql_outdated': 'queryid_changed', 'no_account': 'login_required',
               'parse': 'schema_mismatch', 'xclid_parse': 'schema_mismatch', 'proxy': 'transport_failed'}


def _need(run, *names):
    deps = run.dependencies
    missing = [n for n in names if deps.get(n) is None]
    if missing:
        raise po.ProbeRefused('dependency_missing:' + ','.join(missing))
    return [deps[n] for n in names]


def _failure_reason(exc):
    kind = getattr(exc, 'kind', None)
    if kind == 'abort':
        return 'challenge'
    if kind == 'api':
        if getattr(exc, 'status', None) == 429 or 88 in getattr(exc, 'codes', ()):
            return 'rate_limited'
        return 'login_required' if 32 in getattr(exc, 'codes', ()) else 'blocked'
    return READ_REASON.get(kind, 'transport_failed')


def _stops(reason):
    return reason in ('challenge', 'rate_limited', 'blocked')


def _search(run, reader, query):
    """One charged SearchTimeline page; returns (page | None, reason | None)."""
    run.charge('requests')
    try:
        return reader.search_raw(query, {}, 0), None
    except Exception as exc:  # noqa: BLE001 - only the classified kind survives
        return None, _failure_reason(exc)


def _user(run, reader, screen_name):
    run.charge('requests')
    try:
        reader.ordinary('user_by_login', screen_name, on_page=lambda n: None)
        return None
    except Exception as exc:  # noqa: BLE001
        return _failure_reason(exc)


def _finish(reasons):
    reasons = tuple(dict.fromkeys(reasons))
    if not reasons:
        return po.Outcome('pass')
    return po.Outcome('inconclusive' if reasons == ('inconclusive',) else 'fail', reasons)


@po.register('PX1')
def px1_queryid_sentinel(run):
    """Pinned vs public-bundle query ids; no account; 2 of 6 static GETs."""
    get, = _need(run, 'static_get')
    run.charge('requests')
    try:
        html = get(q.EMBED_URL)
    except Exception:  # noqa: BLE001
        return po.Outcome('fail', ('transport_failed',))
    try:
        name = q.bundle_hash(html.decode('utf-8')) if isinstance(html, bytes) and len(html) <= q.BUNDLE_LIMIT else None
    except UnicodeError:
        name = None
    if name is None:
        return po.Outcome('inconclusive', ('schema_mismatch',))
    run.charge('requests')
    try:
        body = get(q.bundle_url(name))
    except Exception:  # noqa: BLE001
        return po.Outcome('fail', ('transport_failed',))
    try:
        mapping = q.parse_bundle(body.decode('utf-8')) if isinstance(body, bytes) and len(body) <= q.BUNDLE_LIMIT else None
    except UnicodeError:
        mapping = None
    if mapping is None:
        return po.Outcome('inconclusive', ('schema_mismatch',))
    changed = any(mapping.get(op) not in (None, pinned) for op, pinned in q.PINNED.items())
    return po.Outcome('fail', ('queryid_changed',)) if changed else po.Outcome('pass')


@po.register('PX2')
def px2_queryid_live(run):
    """Pinned SearchTimeline and UserByScreenName answered on one account (2 of 4 reads)."""
    readers, query = _need(run, 'readers', 'query')
    label = sorted(readers)[0]
    reader = readers[label]
    _, reason = _search(run, reader, query)
    reasons = [reason] if reason else []
    if not reason or not _stops(reason):
        names = getattr(reader, 'account_names', ())
        if names:
            user_reason = _user(run, reader, names[0])
            reasons += [user_reason] if user_reason else []
    return _finish(reasons)


@po.register('PX3')
def px3_account_capability(run):
    """Per account: known-good SearchTimeline + UserByScreenName (<= 2 per account). A search 404 next to a
    working UserByScreenName is the per-account `capability_missing` signal. Rate-limit header values stay out
    of the record (B5: no values); only counts and reason classes are kept."""
    readers, query = _need(run, 'readers', 'query')
    reasons = []
    for label in sorted(readers):
        reader = readers[label]
        _, reason = _search(run, reader, query)
        if reason:
            reasons.append(reason)
            if _stops(reason):
                break
        names = getattr(reader, 'account_names', ())
        if names:
            user_reason = _user(run, reader, names[0])
            if user_reason:
                reasons.append(user_reason)
                if _stops(user_reason):
                    break
    return _finish(reasons)


@po.register('PX4')
def px4_ct0(run):
    """Does a GraphQL response rotate `ct0`; does the stored `ct0` work in a fresh client (<= 3 reads)."""
    readers, query, adapter, fresh = _need(run, 'readers', 'query', 'adapter', 'fresh_reader')
    label = sorted(readers)[0]
    _, reason = _search(run, readers[label], query)
    if reason:
        return _finish([reason])
    rotated = adapter.ct0_rotations_seen
    reasons = ['ct0_rotated' if rotated else 'ct0_stable' if rotated is not None else 'inconclusive']
    _, fresh_reason = _search(run, fresh(label), query)
    if fresh_reason:
        return po.Outcome('fail', (fresh_reason, *[r for r in reasons if r != 'inconclusive']))
    return po.Outcome('inconclusive' if 'inconclusive' in reasons else 'pass', tuple(reasons))


@po.register('PX5')
def px5_x_compare(run):
    """V7 real-account comparison: both styles on each of two accounts, same query and window, fixed order, one
    canary page per (account, style); stop on challenge/429; agreement by `x_pool.compare_canary`. A tiny sample
    proves little: disagreement without a clear minority is `inconclusive`."""
    from api.data.attention import x_pool, x_reader as xr
    runs, window, tol, overlap = _need(run, 'runs', 'window', 'tolerance', 'min_overlap')
    query, = _need(run, 'query')
    accounts = {label for label, _, _ in runs}
    if len(accounts) != 2 or {style for _, style, _ in runs} != {'plain', 'curl'} or len(runs) != 4:
        raise po.ProbeRefused('protocol_invalid')
    results, order = {}, []
    for label, style, reader in runs:
        page, reason = _search(run, reader, query)
        if reason:
            return po.Outcome('fail', (reason,))
        key = f'{label}:{style}'
        order.append(key)
        results[key] = xr.canary_ids(reader.parse_tweets(page.body), *window) if page else set()
    suspects, inconclusive = x_pool.compare_canary(results, order, tol, overlap)
    if inconclusive:
        return po.Outcome('inconclusive', ('inconclusive',))
    return po.Outcome('fail', ('style_disagreement',)) if suspects else po.Outcome('pass')


@po.register('PX6')
def px6_harvest_real(run):
    """One owner-initiated X browser session (1 launch, <= 180 s): state class, cookie NAMES only via the
    public view, refused relay hosts as candidates for `surface-propose` of section x_session."""
    check, = _need(run, 'check_session')
    run.charge('launches')
    result = check()
    state = getattr(result, 'state', None)
    reasons = {'logged_in': [], 'login_required': ['login_required'], 'challenge': ['challenge'],
               'refused': ['browser_refused']}.get(state, ['transport_failed'])
    refused = run.dependencies.get('refused_hosts')
    if refused is not None and any(k != 'background_refused' for k in refused() or {}):
        reasons.append('hosts_refused')
    return _finish(reasons)


@po.register('PR5')
def pr5_proxy_exit(run):
    """Exit class of the admitted routes the GraphQL and browser methods would use. The class is the admitted
    route's mode (`proxy`/`direct`); an unadmitted route is `transport_failed`. No request is sent."""
    routes, = _need(run, 'routes')
    classes, reasons = {}, []
    for section in ('gql_anon', 'browser'):
        route = routes.get(section)
        mode = getattr(route, 'mode', None)
        if mode not in ('proxy', 'direct'):
            reasons.append('transport_failed')
        else:
            classes[section] = mode
    if not reasons and len(set(classes.values())) != 1:
        reasons.append('exit_class_mismatch')
    return _finish(reasons)


@po.register('PR6')
def pr6_durability(run):
    """Seven completed UTC days before `run.today` of local Reddit facts (0 requests)."""
    read_events, = _need(run, 'read_events')
    from api.data.attention import daily_facts
    missing = 0
    for back in range(1, 8):
        summary = daily_facts.summarize(read_events(run.today - timedelta(days=back)) or [])
        if 'reddit' not in summary['accounts'] and 'reddit' not in summary['requests']:
            missing += 1
    return po.Outcome('fail', ('facts_missing_days',)) if missing else po.Outcome('pass')


def build_dependencies(probe_id, config):
    """Production transport for an APPROVED run (never called on dry-run). Unwired routes stay default-deny."""
    from datetime import datetime, timezone
    if probe_id == 'PR1':
        from api.scripts.probe_gql import build_dependencies as gql_dependencies
        return gql_dependencies(config)
    if probe_id == 'PR6':
        from api.data.attention import daily_facts
        return {'read_events': daily_facts.read_events}
    if probe_id == 'PX1':
        configured = config.x_proxy_required or any(getattr(config, k) is not None for k in
            ('x_proxy_list_path', 'x_proxy_assignments_path', 'x_proxy_policy_path'))
        if configured:
            raise po.ProbeRefused('route_not_admitted')
        import asyncio
        from api.data.attention.x_queryids_fetch import static_get
        return {'static_get': lambda url: asyncio.run(static_get(None, None, url))}
    if probe_id == 'PR5':
        from api.data.attention.browser_session import DENY_ROUTES
        return {'routes': {'gql_anon': DENY_ROUTES.admitted_route('reddit', None),
                           'browser': DENY_ROUTES.admitted_route('reddit', None)}}
    if probe_id == 'PX6':
        from api.data import cache
        from api.data.attention import browser_host as bh, browser_session as bs
        label = sorted(dict(config.x_account_profiles))[0] if config.x_account_profiles else None
        if label is None or not config.browser_path or not config.browser_profiles_dir:
            raise po.ProbeRefused('browser_not_configured')
        host = bh.BrowserHost(config.browser_path, config.browser_profiles_dir, cache_root=cache.CACHE_ROOT,
                              memory_floor=config.browser_memory_floor_mb, rss_ceiling=config.browser_rss_ceiling_mb,
                              timeout=min(300, config.x_harvest_timeout_s + 60))
        return {'check_session': lambda: bs.check_session(
            'x', label, host=host, profile_name=bs._profile_name(config, 'x', label), day_guard=None,
            routes=bs.DENY_ROUTES, mode='probe', timeout=min(180, config.x_harvest_timeout_s))}
    if probe_id in ('PX2', 'PX3', 'PX4', 'PX5'):
        import dataclasses
        from api.data.attention import twscrape_reader as tr, x_pool
        now = datetime.now(timezone.utc)
        start, end = x_pool.canary_window(now)
        deps = {'query': x_pool.canary_query(config, start, end), 'window': (start, end),
                'tolerance': config.x_canary_tolerance, 'min_overlap': config.x_canary_min_overlap}
        try:
            boot = tr.start(config)
        except tr.XStartRefused as exc:
            raise po.ProbeRefused('x_start_refused:' + ','.join(exc.reasons)) from None
        deps.update(readers=boot.readers, adapter=boot.adapter)
        if probe_id == 'PX4':
            deps['fresh_reader'] = lambda label: tr.start(config).readers[label]
        if probe_id == 'PX5':
            labels = sorted(boot.readers)[:2]
            other = 'curl' if config.x_connection_style == 'plain' else 'plain'
            alt = tr.start(dataclasses.replace(config, x_connection_style=other))
            by_style = {config.x_connection_style: boot.readers, other: alt.readers}
            deps['runs'] = [(label, style, by_style[style][label]) for label in labels for style in ('plain', 'curl')]
        return deps
    raise po.ProbeRefused('executor_pending:' + po.PENDING.get(probe_id, 'S-OpsProbe'))


from api.scripts import probe_gql  # noqa: E402,F401 - registers PR1 (S-RGQL) in the default registry
