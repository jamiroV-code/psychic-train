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

def test_px1_configured_uses_admitted_route(monkeypatch):
    from types import SimpleNamespace
    from api.data.attention import x_queryids_fetch
    config = SimpleNamespace(x_proxy_required=True, x_proxy_list_path="private",
                             x_proxy_assignments_path="private", x_proxy_policy_path="private")
    route, policy = object(), object()
    monkeypatch.setattr(pe, "_x_routes", lambda config, path: (
        SimpleNamespace(admitted_route=lambda site, label: SimpleNamespace(
            mode="proxy", route=route, admission=lambda: True)),
        "account", SimpleNamespace(snapshot=SimpleNamespace(policy=policy))))
    seen = []
    async def get(r, p, url):
        seen.append((r, p, url))
        return b"fixture"
    monkeypatch.setattr(x_queryids_fetch, "static_get", get)
    deps = pe.build_dependencies("PX1", config, config_path="private")
    assert deps["static_get"]("fixture") == b"fixture"
    assert seen == [(route, policy, "fixture")]


def test_px1_direct_does_not_build_routes(monkeypatch):
    from types import SimpleNamespace
    from api.data.attention import x_queryids_fetch
    config = SimpleNamespace(x_proxy_required=False, x_proxy_list_path=None,
                             x_proxy_assignments_path=None, x_proxy_policy_path=None)
    monkeypatch.setattr(pe, "_x_routes", lambda *args: pytest.fail("direct route provider"))
    seen = []
    async def get(r, p, url):
        seen.append((r, p))
        return b"fixture"
    monkeypatch.setattr(x_queryids_fetch, "static_get", get)
    assert pe.build_dependencies("PX1", config)["static_get"]("fixture") == b"fixture"
    assert seen == [(None, None)]


def test_px1_expired_admission_refuses(monkeypatch):
    from types import SimpleNamespace
    config = SimpleNamespace(x_proxy_required=True)
    monkeypatch.setattr(pe, "_x_routes", lambda *args: (
        SimpleNamespace(admitted_route=lambda *args: "proxy_not_admitted"), "a", None))
    with pytest.raises(po.ProbeRefused, match="route_not_admitted"):
        pe.build_dependencies("PX1", config, config_path="private")["static_get"]("fixture")


def _reddit_routes(monkeypatch, seen, *, ready=True, admitted=True):
    from types import SimpleNamespace
    from api.data.attention import reddit_browser
    class Routes:
        def __init__(self, config, *, config_path=None):
            seen.append(("routes", config_path))
            self.runtime = SimpleNamespace(snapshot=SimpleNamespace(policy="policy"))

        def refresh(self):
            return SimpleNamespace(labels=("r_acct1",), select=lambda: "r_acct1" if ready else None)

        def admit(self, label):
            seen.append(("admit", label))

        def admitted_route(self, site, label):
            return _Admitted(admitted) if admitted is not None else "proxy_not_admitted"

    monkeypatch.setattr(reddit_browser, "RedditRoutes", Routes)
    monkeypatch.setattr("api.data.attention.browser_session.AdmittedRoute", _Admitted)


class _Admitted:
    def __init__(self, ok):
        self.ok = ok

    def admission(self):
        return self.ok


def _routed():
    from types import SimpleNamespace
    return SimpleNamespace(x_proxy_required=True, x_proxy_list_path="C:/p/l.json",
                           x_proxy_assignments_path="C:/p/a.json", x_proxy_policy_path="C:/p/p.json",
                           reddit_surface_path="C:/p/surface.json")


def test_pr5_configured_uses_admitted_reddit_route(monkeypatch):
    seen = []
    _reddit_routes(monkeypatch, seen)
    deps = pe.build_dependencies("PR5", _routed(), config_path="C:/p/q.json")
    assert seen == [("routes", "C:/p/q.json"), ("admit", "r_acct1")]
    assert deps["routes"]["gql_anon"] is deps["routes"]["browser"] and deps["routes"]["browser"].ok


@pytest.mark.parametrize("ready,admitted,reason", [(False, True, "no_ready_account"),
                                                   (True, False, "route_not_admitted"),
                                                   (True, None, "route_not_admitted")])
def test_pr5_refuses_without_admission(monkeypatch, ready, admitted, reason):
    _reddit_routes(monkeypatch, [], ready=ready, admitted=admitted)
    with pytest.raises(po.ProbeRefused, match=reason):
        pe.build_dependencies("PR5", _routed(), config_path="C:/p/q.json")


def test_pr1_configured_uses_admitted_reddit_route(monkeypatch):
    from types import SimpleNamespace
    from api.data.attention import reddit_surface
    from api.scripts import probe_gql
    seen = []
    _reddit_routes(monkeypatch, seen)
    section = SimpleNamespace(hosts=("gql.example",))
    monkeypatch.setattr(reddit_surface, "load_surface", lambda path, name: section)
    calls = []

    def transport(config, *, routes=None, policy=None, hosts=()):
        calls.append((routes.admitted_route("reddit", probe_gql.rg.SECTION).ok,
                      routes.admitted_route("x", probe_gql.rg.SECTION), policy, hosts))
        return "transport"
    monkeypatch.setattr(probe_gql.rg, "route_transport", transport)
    deps = pe.build_dependencies("PR1", _routed(), config_path="C:/p/q.json")
    assert deps == {"transport": "transport", "section": section}
    assert seen[0] == ("routes", "C:/p/q.json")
    assert calls == [(True, "proxy_not_admitted", "policy", ("gql.example",))]


def test_pr1_configured_without_ready_account_refuses(monkeypatch):
    from types import SimpleNamespace
    from api.data.attention import reddit_surface
    _reddit_routes(monkeypatch, [], ready=False)
    monkeypatch.setattr(reddit_surface, "load_surface", lambda path, name: SimpleNamespace(hosts=()))
    with pytest.raises(po.ProbeRefused, match="no_ready_account"):
        pe.build_dependencies("PR1", _routed(), config_path="C:/p/q.json")


def test_pr2_passes_the_private_path_to_reddit_routes(monkeypatch):
    from api.scripts import probe_browser
    seen = []
    _reddit_routes(monkeypatch, seen)
    monkeypatch.setattr(probe_browser.rb, "build_host", lambda config: "host")
    monkeypatch.setattr(probe_browser.rb, "admission_state", lambda config: None)
    monkeypatch.setattr(probe_browser.rb, "BrowserSessions", lambda config, *, host, routes: object())
    deps = pe.build_dependencies("PR2", _routed(), config_path="C:/p/q.json")
    assert callable(deps["driver"]) and seen[0] == ("routes", "C:/p/q.json")


def test_pr2_refusal_is_kept_before_routes(monkeypatch):
    from api.scripts import probe_browser
    seen = []
    _reddit_routes(monkeypatch, seen)
    monkeypatch.setattr(probe_browser.rb, "build_host", lambda config: "host")
    monkeypatch.setattr(probe_browser.rb, "admission_state", lambda config: "browser_gate_missing")
    with pytest.raises(po.ProbeRefused, match="browser_gate_missing"):
        pe.build_dependencies("PR2", _routed(), config_path="C:/p/q.json")
    assert seen == []


def test_px6_uses_the_admitted_x_route_provider(monkeypatch):
    from types import SimpleNamespace
    from api.data.attention import browser_host, browser_session
    config = SimpleNamespace(x_account_profiles={"x_acct1": "x_acct1"}, browser_path="C:/b/msedge.exe",
                             browser_profiles_dir="C:/b/profiles", browser_memory_floor_mb=1,
                             browser_rss_ceiling_mb=1, x_harvest_timeout_s=60)
    monkeypatch.setattr(browser_host, "BrowserHost", lambda *a, **k: "host")
    provider = object()
    paths = []
    monkeypatch.setattr(pe, "_x_routes", lambda cfg, path: paths.append(path) or (provider, "x_acct1", None))
    monkeypatch.setattr(browser_session, "_profile_name", lambda cfg, site, label: label)
    checks = []
    monkeypatch.setattr(browser_session, "check_session", lambda *a, **k: checks.append(k["routes"]) or "ok")
    deps = pe.build_dependencies("PX6", config, config_path="C:/p/q.json")
    assert paths == ["C:/p/q.json"] and deps["check_session"]() == "ok" and checks == [provider]


def test_px6_refuses_when_admitted_label_differs(monkeypatch):
    from types import SimpleNamespace
    from api.data.attention import browser_host
    config = SimpleNamespace(x_account_profiles={"x_acct1": "x_acct1"}, browser_path="C:/b/msedge.exe",
                             browser_profiles_dir="C:/b/profiles", browser_memory_floor_mb=1,
                             browser_rss_ceiling_mb=1, x_harvest_timeout_s=60)
    monkeypatch.setattr(browser_host, "BrowserHost", lambda *a, **k: "host")
    monkeypatch.setattr(pe, "_x_routes", lambda cfg, path: (object(), "x_acct2", None))
    with pytest.raises(po.ProbeRefused, match="route_not_admitted"):
        pe.build_dependencies("PX6", config, config_path="C:/p/q.json")


@pytest.mark.parametrize("probe", ["PR1", "PR5"])
def test_routed_reddit_without_private_path_refuses(monkeypatch, probe):
    from types import SimpleNamespace
    from api.data.attention import reddit_surface
    seen = []
    _reddit_routes(monkeypatch, seen)
    monkeypatch.setattr(reddit_surface, "load_surface", lambda path, name: SimpleNamespace(hosts=()))
    with pytest.raises(po.ProbeRefused, match="route_not_admitted"):
        pe.build_dependencies(probe, _routed())
    assert seen == []
