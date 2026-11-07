"""Owner probe protocol. No network is performed by discovery or dry-run.

Executors register with register(probe_id) and receive a Run. They must charge
BEFORE every transport action and return an Outcome, never a serialized record.
Only run() binds that outcome to its approved plan, published section and date.
Records gate behaviour, not security: another process of the same user can forge
local files. PR3 deliberately cannot receive Reddit cookie values (A17).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from api.data.attention.reddit_surface import load_surface, section_sha256
from api.data.attention.x_proxy_private import atomic_json, state_lock

COUNTS = ('requests', 'navigations', 'responses', 'scrolls', 'bytes')
REASONS = frozenset(('challenge', 'rate_limited', 'blocked', 'budget_exhausted', 'schema_mismatch',
    'unsupported_format', 'empty_shell', 'facts_missing_days', 'transport_failed', 'capability_missing',
    'queryid_changed', 'login_required', 'browser_refused', 'inconclusive', 'proposal_refused',
    'ct0_rotated', 'ct0_stable', 'style_disagreement', 'hosts_refused', 'exit_class_mismatch'))
LIMITS = frozenset((*COUNTS, 'seconds', 'resource_bytes', 'scrolls_per_page', 'launches'))
SECTIONS = {'PR1': 'gql_anon', 'PR2': 'browser', 'PX6': 'x_session'}
PENDING = {'PR1': 'S-RGQL', 'PR2': 'S-RBrowser'}
EXECUTORS = {}


class ProbeRefused(ValueError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


class RecordInvalid(ValueError):
    pass


@dataclass(frozen=True)
class Spec:
    purpose: str
    limits: dict
    modes: tuple = ('observe',)


PROBES = {
    'PX1': Spec('Compare pinned and public bundle query ids', {'requests': 6}),
    'PX2': Spec('Compare pinned and candidate SearchTimeline', {'requests': 4}),
    'PX3': Spec('SearchTimeline and UserByScreenName per account', {'requests': 2}),
    'PX4': Spec('Observe ct0 replacement and fresh-session validity', {'requests': 3}),
    'PX5': Spec('Two-account transport comparison', {'requests': 8}),
    'PX6': Spec('One owner-initiated X session harvest', {'launches': 1, 'seconds': 180}),
    'PR1': Spec('Anonymous GraphQL token, feeds and comments', {'requests': 120}, ('bootstrap', 'verify')),
    'PR2': Spec('Browser structural capture and published grammar verification',
                {'navigations': 15, 'responses': 150, 'bytes': 16 * 1024 * 1024,
                 'scrolls_per_page': 12, 'seconds': 600, 'resource_bytes': 2 * 1024 * 1024},
                ('bootstrap', 'verify')),
    'PR3': Spec('Cookie HTTP refused under A17', {'requests': 20}),
    'PR4': Spec('Reserved; archive route declined', {'requests': 0}),
    'PR5': Spec('Compare admitted route exit class', {'requests': 10}),
    'PR6': Spec('Seven completed UTC days of local facts', {'requests': 0}),
}


def register(probe_id):
    if probe_id not in PROBES or probe_id in ('PR3', 'PR4'):
        raise ValueError('probe_registration_refused')
    def install(fn):
        if probe_id in EXECUTORS:
            raise ValueError('probe_already_registered')
        EXECUTORS[probe_id] = fn
        return fn
    return install


def limits_for(probe_id, mode, *, max_body_bytes=262144, accounts=1):
    result = dict(PROBES[probe_id].limits)
    if probe_id == 'PX3':
        result['requests'] *= accounts
    if probe_id == 'PR2' and mode == 'verify':
        result.update(responses=500, bytes=4 * max_body_bytes, resource_bytes=max_body_bytes)
    return result


class Budget:
    def __init__(self, limits, *, clock=time.monotonic):
        self.limits, self.clock, self.start = dict(limits), clock, clock()
        self.counts = dict.fromkeys(COUNTS, 0)
        self.limits_hit = []
        self.page_scrolls = self.launches = 0

    def charge(self, kind, *, nbytes=0):
        if kind not in (*COUNTS, 'launches') or type(nbytes) is not int or nbytes < 0:
            raise ValueError('invalid_charge')
        hit = None
        if self.clock() - self.start >= self.limits.get('seconds', float('inf')):
            hit = 'seconds'
        elif nbytes > self.limits.get('resource_bytes', float('inf')):
            hit = 'resource_bytes'
        elif self.counts['bytes'] + nbytes > self.limits.get('bytes', float('inf')):
            hit = 'bytes'
        elif kind == 'scrolls' and self.page_scrolls >= self.limits.get('scrolls_per_page', float('inf')):
            hit = 'scrolls_per_page'
        elif (self.launches if kind == 'launches' else self.counts[kind]) >= self.limits.get(kind, float('inf')):
            hit = kind
        if hit:
            if hit not in self.limits_hit:
                self.limits_hit.append(hit)
            return False
        if kind == 'launches':
            self.launches += 1
        else:
            self.counts[kind] += 1
        self.counts['bytes'] += nbytes
        if kind == 'scrolls':
            self.page_scrolls += 1
        if kind == 'navigations':
            self.page_scrolls = 0
        return True


@dataclass(frozen=True)
class Outcome:
    outcome: str
    reason_codes: tuple = ()


@dataclass
class Run:
    probe_id: str
    mode: str
    today: date
    cache_root: Path
    budget: Budget
    section: object = None
    dependencies: dict = field(default_factory=dict, repr=False)

    def charge(self, kind='requests', **kwargs):
        if not self.budget.charge(kind, **kwargs):
            raise ProbeRefused('budget_exhausted')


def validate_record(r):
    keys = {'schema', 'probe_id', 'mode', 'date_utc', 'commit', 'egress_class', 'outcome', 'section',
            'section_sha256', 'surface_revision', 'counts', 'reason_codes', 'limits_hit'}
    try:
        assert type(r) is dict and set(r) == keys and type(r['schema']) is int and r['schema'] == 1
        assert r['probe_id'] in PROBES and r['mode'] in PROBES[r['probe_id']].modes
        assert date.fromisoformat(r['date_utc']).isoformat() == r['date_utc']
        assert re.fullmatch('[0-9a-f]{40,64}', r['commit'])
        assert r['egress_class'] in ('none', 'direct', 'proxy', 'unknown')
        assert r['outcome'] in ('pass', 'fail', 'inconclusive')
        assert r['section'] == SECTIONS.get(r['probe_id'])
        assert type(r['counts']) is dict and set(r['counts']) == set(COUNTS)
        assert all(type(v) is int and v >= 0 for v in r['counts'].values())
        assert type(r['reason_codes']) is list and set(r['reason_codes']) <= REASONS
        assert type(r['limits_hit']) is list and set(r['limits_hit']) <= LIMITS
        bound = r['section_sha256'] is not None
        assert bound == (r['surface_revision'] is not None)
        assert not bound or (r['section'] is not None and re.fullmatch('[0-9a-f]{64}', r['section_sha256'])
                             and type(r['surface_revision']) is int and r['surface_revision'] >= 1)
        assert r['mode'] != 'verify' or bound
    except (AssertionError, ValueError, TypeError, KeyError):
        raise RecordInvalid('record_invalid') from None
    return r


def make_record(**kwargs):
    return validate_record({'schema': 1, **kwargs})


def write_record(cache_root, record):
    validate_record(record)
    path = Path(cache_root) / 'attention' / '_probes' / (
        f"probe_{record['probe_id']}_{record['mode']}_{record['date_utc']}.json")
    atomic_json(path, record)
    return path


def latest_record(cache_root, probe_id, mode):
    if probe_id not in PROBES or mode not in PROBES[probe_id].modes:
        return None
    for p in sorted((Path(cache_root) / 'attention' / '_probes').glob(f'probe_{probe_id}_{mode}_*.json'), reverse=True):
        try:
            r = validate_record(json.loads(p.read_text(encoding='utf-8')))
            if r['probe_id'] == probe_id and r['mode'] == mode:
                return r
        except (OSError, ValueError):
            continue
    return None


def verify_gate(cache_root, section, *, surface_path, max_age_days, today):
    try:
        published = load_surface(surface_path, section)
    except (ValueError, TypeError):
        return 'surface_unpublished'
    probe_id = {'browser': 'PR2', 'gql_anon': 'PR1'}.get(section)
    rec = latest_record(cache_root, probe_id, 'verify')
    if rec is None:
        return 'needs_probe'
    if rec['outcome'] != 'pass':
        return 'probe_failed'
    age = (today - date.fromisoformat(rec['date_utc'])).days
    if age < 0 or age > max_age_days:
        return 'probe_stale'
    if rec['section_sha256'] != published.sha256 or rec['surface_revision'] != published.revision:
        return 'surface_changed'
    return 'ok'


def plan(probe_id, mode=None):
    spec = PROBES[probe_id]
    mode = mode or spec.modes[0]
    if mode not in spec.modes:
        raise ProbeRefused('mode_unsupported')
    p = {'probe_id': probe_id, 'mode': mode, 'purpose': spec.purpose, 'limits': limits_for(probe_id, mode)}
    p['approval_digest'] = hashlib.sha256(json.dumps(p, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return p


def run(probe_id, *, approval, cache_root, commit, today=None, mode=None, surface_path=None,
        egress_class='unknown', executors=None, dependencies=None):
    p = plan(probe_id, mode)
    if approval != p['approval_digest']:
        return {**p, 'dry_run': True, 'approve_with': '--approve ' + p['approval_digest']}
    if probe_id == 'PR3':
        raise ProbeRefused('executor_refused:a17_cookie_boundary')
    if probe_id == 'PR4':
        raise ProbeRefused('probe_reserved')
    if executors is None:
        import api.scripts.probe_executors  # noqa: F401 - registers the S-OpsProbe executors
        executors = EXECUTORS
    executor = executors.get(probe_id)
    if executor is None:
        raise ProbeRefused('executor_pending:' + PENDING.get(probe_id, 'S-OpsProbe'))
    section = None
    if p['mode'] == 'verify':
        try:
            section = load_surface(surface_path, SECTIONS[probe_id])
        except (ValueError, TypeError):
            raise ProbeRefused('surface_unpublished') from None
    # Production transport is built only now: after approval, never on a dry run.
    deps = dict((dependencies() if callable(dependencies) else dependencies) or {})
    root = Path(cache_root)
    accounts = len(deps.get('readers') or ()) or 1
    budget = Budget(limits_for(probe_id, p['mode'], max_body_bytes=section.max_body_bytes if section else 262144,
                               accounts=accounts))
    ctx = Run(probe_id, p['mode'], today or date.today(), root, budget, section, deps)
    with state_lock(root / 'attention' / '_probes' / 'owner_probe'):
        try:
            result = executor(ctx)
        except ProbeRefused as exc:
            if exc.reason != 'budget_exhausted':
                raise
            result = Outcome('fail', ('budget_exhausted',))
        if type(result) is not Outcome:
            raise ProbeRefused('executor_result_invalid')
        record = make_record(probe_id=probe_id, mode=ctx.mode, date_utc=ctx.today.isoformat(), commit=commit,
            egress_class=egress_class, outcome=result.outcome, section=SECTIONS.get(probe_id),
            section_sha256=section.sha256 if section else None, surface_revision=section.revision if section else None,
            counts=dict(budget.counts), reason_codes=list(result.reason_codes), limits_hit=list(budget.limits_hit))
        write_record(root, record)
        return record


def main(argv=None, *, cache_root=None, out=sys.stdout, executors=None, today=None, dependencies=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('probe_id', choices=PROBES)
    parser.add_argument('--mode', choices=('observe', 'bootstrap', 'verify'))
    parser.add_argument('--approve')
    parser.add_argument('--commit', default='0' * 40)
    parser.add_argument('--surface-path', type=Path)
    parser.add_argument('--queries', type=Path, help='absolute private owner query file outside the repository')
    args = parser.parse_args(argv)
    from api.data.attention import web_queries
    if args.queries is not None:
        if not args.queries.is_absolute() or not web_queries._outside_repo(str(args.queries.resolve())):
            parser.error('--queries must be absolute and outside the repository')
    if cache_root is None:
        from api.data.cache import CACHE_ROOT
        cache_root = CACHE_ROOT
    if dependencies is None:
        def dependencies():
            from api.scripts.probe_executors import build_dependencies
            try:
                config = web_queries.load(args.queries).config
            except (OSError, ValueError):
                raise ProbeRefused('config_invalid') from None
            configured = config.x_proxy_required or any(getattr(config, key) is not None for key in
                ('x_proxy_list_path', 'x_proxy_assignments_path', 'x_proxy_policy_path'))
            if configured and args.queries is None:
                raise ProbeRefused('private_queries_required')
            return build_dependencies(args.probe_id, config, config_path=args.queries)
    try:
        result = run(args.probe_id, approval=args.approve, cache_root=cache_root, commit=args.commit, today=today,
                     mode=args.mode, surface_path=args.surface_path, executors=executors, dependencies=dependencies)
    except ProbeRefused as exc:
        result = {'probe_id': args.probe_id, 'state': 'refused', 'reason': exc.reason}
    out.write(json.dumps(result, sort_keys=True) + '\n')
    return 2 if result.get('state') == 'refused' or result.get('outcome') in ('fail', 'inconclusive') else 0


if __name__ == '__main__':
    raise SystemExit(main())
