"""S-OpsProbe executors over loopback fakes: no provider request, no browser, no cookie values."""
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone

import pytest

from api.data.attention import x_queryids as q, x_reader as xr
from api.scripts import probe_executors as pe, probe_owner as po

TODAY = date(2026, 11, 7)


def go(probe, deps, tmp_path, **kw):
    return po.run(probe, approval=po.plan(probe)['approval_digest'], cache_root=tmp_path, commit='a' * 40,
                  today=TODAY, dependencies=deps, **kw)


def test_default_registry_covers_owned_probes_only():
    po.run('PX1', approval=None, cache_root='.', commit='a' * 40)  # dry run; import side effect only via run
    assert pe.EXECUTORS_OWNED == ('PX1', 'PX2', 'PX3', 'PX4', 'PX5', 'PX6', 'PR5', 'PR6')
    assert not {'PR3', 'PR4'} & set(po.EXECUTORS)
    assert 'PR1' in po.EXECUTORS  # S-RGQL registers it (api/scripts/probe_gql.py)
    assert 'PR2' in po.EXECUTORS  # S-RBrowser registers it (api/scripts/probe_browser.py)


@pytest.mark.parametrize('probe,reason', [('PR3', 'executor_refused:a17_cookie_boundary')])
def test_default_registry_refuses_without_touching_dependencies(probe, reason, tmp_path):
    def forbidden():
        pytest.fail('dependencies (cookies) built')
    with pytest.raises(po.ProbeRefused, match=reason):
        go(probe, forbidden, tmp_path)
    assert not list(tmp_path.rglob('*.json'))


def test_dry_run_never_builds_dependencies(tmp_path):
    def forbidden():
        pytest.fail('dependencies built on dry run')
    assert po.run('PX3', approval=None, cache_root=tmp_path, commit='a' * 40, dependencies=forbidden)['dry_run']


def test_missing_dependency_is_refusal_not_record(tmp_path):
    with pytest.raises(po.ProbeRefused, match='dependency_missing:static_get'):
        go('PX1', {}, tmp_path)
    assert not list(tmp_path.rglob('probe_*.json'))


def _static(mapping, name='abcdef1234'):
    js = ''.join(f'queryId:"{v}",operationName:"{k}"' + ';' for k, v in mapping.items()).encode()
    html = f'<script src="https://abs.twimg.com/responsive-web/client-web/main.{name}.js">'.encode()
    calls = []
    def get(url):
        calls.append(url)
        return html if url == q.EMBED_URL else js
    return get, calls


def test_px1_pinned_pass_and_changed_fail(tmp_path):
    get, calls = _static(q.PINNED)
    r = go('PX1', {'static_get': get}, tmp_path)
    assert r['outcome'] == 'pass' and r['counts']['requests'] == 2 and calls[0] == q.EMBED_URL
    get, _ = _static({**q.PINNED, 'SearchTimeline': 'Zz' * 11})
    r = go('PX1', {'static_get': get}, tmp_path / 'b')
    assert r['outcome'] == 'fail' and r['reason_codes'] == ['queryid_changed']


@dataclass
class Page:
    body: dict


class Reader:
    def __init__(self, fail=None, user_fail=None, ids=(1, 2, 3), names=('acct',)):
        self.fail, self.user_fail, self.ids, self.account_names = fail, user_fail, ids, names
        self.calls = []

    def search_raw(self, query, kv, page):
        self.calls.append('search')
        if self.fail:
            raise self.fail
        return Page({'ids': list(self.ids)})

    def ordinary(self, op, target, *, on_page):
        self.calls.append(op)
        if self.user_fail:
            raise self.user_fail

    def parse_tweets(self, body):
        when = datetime(2026, 11, 6, 23, 30, tzinfo=timezone.utc)
        return [type('T', (), {'id': i, 'date': when}) for i in body['ids']]


def test_px3_per_account_capability_and_budget_scales(tmp_path):
    readers = {'a': Reader(), 'b': Reader(fail=xr.ReaderFailure('not_found'))}
    r = go('PX3', {'readers': readers, 'query': 'bitcoin'}, tmp_path)
    assert r['outcome'] == 'fail' and r['reason_codes'] == ['capability_missing']
    assert r['counts']['requests'] == 4 and r['limits_hit'] == []
    assert readers['b'].calls == ['search', 'user_by_login']


def test_px2_stops_on_challenge(tmp_path):
    reader = Reader(fail=xr.ReaderFailure('abort', text=xr.CLOUDFLARE_PREFIX))
    r = go('PX2', {'readers': {'a': reader}, 'query': 'bitcoin'}, tmp_path)
    assert r['reason_codes'] == ['challenge'] and reader.calls == ['search']


def test_px4_ct0_observation(tmp_path):
    adapter = type('A', (), {'ct0_rotations_seen': 1})()
    deps = {'readers': {'a': Reader()}, 'query': 'q', 'adapter': adapter, 'fresh_reader': lambda label: Reader()}
    r = go('PX4', deps, tmp_path)
    assert r['outcome'] == 'pass' and r['reason_codes'] == ['ct0_rotated'] and r['counts']['requests'] == 2
    deps['fresh_reader'] = lambda label: Reader(fail=xr.ReaderFailure('api', status=401, codes=(32,)))
    r = go('PX4', deps, tmp_path / 'b')
    assert r['outcome'] == 'fail' and r['reason_codes'] == ['login_required', 'ct0_rotated']


def _px5(readers):
    window = (datetime(2026, 11, 6, 23, tzinfo=timezone.utc), datetime(2026, 11, 7, tzinfo=timezone.utc))
    runs = [(label, style, readers[(label, style)]) for label in ('a', 'b') for style in ('plain', 'curl')]
    return {'runs': runs, 'window': window, 'query': 'q', 'tolerance': 0.25, 'min_overlap': 0.6}


def test_px5_v7_protocol(tmp_path):
    same = {(l, s): Reader() for l in 'ab' for s in ('plain', 'curl')}
    assert go('PX5', _px5(same), tmp_path)['outcome'] == 'pass'
    odd = dict(same)
    odd[('b', 'curl')] = Reader(ids=(1,))
    r = go('PX5', _px5(odd), tmp_path / 'b')
    assert r['outcome'] == 'fail' and r['reason_codes'] == ['style_disagreement'] and r['counts']['requests'] == 4
    with pytest.raises(po.ProbeRefused, match='protocol_invalid'):
        go('PX5', {**_px5(same), 'runs': _px5(same)['runs'][:2]}, tmp_path / 'c')


def test_px6_public_state_and_refused_hosts(tmp_path):
    result = type('S', (), {'state': 'logged_in'})()
    r = go('PX6', {'check_session': lambda: result,
                   'refused_hosts': lambda: {'video.twimg.com': 2, 'background_refused': 9}}, tmp_path)
    assert r['outcome'] == 'fail' and r['reason_codes'] == ['hosts_refused'] and r['counts']['requests'] == 0
    r = go('PX6', {'check_session': lambda: result, 'refused_hosts': lambda: {'background_refused': 1}},
           tmp_path / 'b')
    assert r['outcome'] == 'pass'


def test_pr5_exit_class(tmp_path):
    proxy = type('R', (), {'mode': 'proxy'})()
    assert go('PR5', {'routes': {'gql_anon': proxy, 'browser': proxy}}, tmp_path)['outcome'] == 'pass'
    r = go('PR5', {'routes': {'gql_anon': proxy, 'browser': 'proxy_not_admitted'}}, tmp_path / 'b')
    assert r['reason_codes'] == ['transport_failed']


def test_pr6_seven_completed_days(tmp_path):
    seen = []
    def events(day):
        seen.append(day)
        return [{'kind': 'request_counter', 'source': 'reddit', 'method': 'browser', 'requests': 3}]
    r = go('PR6', {'read_events': events}, tmp_path)
    assert r['outcome'] == 'pass' and r['counts'] == dict.fromkeys(po.COUNTS, 0)
    assert min(seen) == date(2026, 10, 31) and max(seen) == date(2026, 11, 6)
    r = go('PR6', {'read_events': lambda day: [] if day.day == 3 else events(day)}, tmp_path / 'b')
    assert r['reason_codes'] == ['facts_missing_days']


def test_records_carry_no_values(tmp_path):
    get, _ = _static(q.PINNED)
    go('PX1', {'static_get': get}, tmp_path)
    text = ''.join(p.read_text() for p in tmp_path.rglob('probe_*.json'))
    assert q.PINNED['SearchTimeline'] not in text and 'abcdef1234' not in text
    assert set(json.loads(text)) == {'schema', 'probe_id', 'mode', 'date_utc', 'commit', 'egress_class', 'outcome',
                                     'section', 'section_sha256', 'surface_revision', 'counts', 'reason_codes',
                                     'limits_hit'}
