"""S-RBrowser PR2 executor over the loopback driver seam (`reddit_probe_fixtures.FakeDriver`): no browser, no
network, no body written."""
from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import date, datetime, timezone

import pytest

from api.data.attention import reddit_browser as rb
from api.data.attention import reddit_surface as rs
from api.scripts import probe_browser as pb
from api.scripts import probe_owner as po
from api.scripts import surface_tool as st
from api.tests.scripts import reddit_probe_fixtures as fx

TODAY = date(2026, 10, 26)
NOW = datetime.fromtimestamp(fx.BASE + 600, timezone.utc)
SUBS = ("bitcoin", "ethereum")


def factory(driver, seen=None):
    @contextmanager
    def open_driver(mode, section):
        if seen is not None:
            seen.append((mode, section.sha256 if section else None))
        yield driver
    return open_driver


def go(mode, deps, tmp_path, surface=None):
    return po.run('PR2', approval=po.plan('PR2', mode)['approval_digest'], cache_root=tmp_path, commit='a' * 40,
                  today=TODAY, mode=mode, surface_path=surface, dependencies=deps)


def publish(tmp_path):
    p = st.propose('browser', fx.bootstrap_captures(SUBS), subreddits=SUBS)
    path = tmp_path / 'surface.json'
    path.write_text(json.dumps({'sections': {'browser': p.section}}), encoding='utf-8')
    return path, rs.load_section('browser', p.section)


def test_pr2_is_registered_by_this_slice():
    assert po.EXECUTORS['PR2'] is pb.pr2_browser


def test_bootstrap_captures_propose_and_write_the_candidate_without_bodies(tmp_path):
    d = fx.FakeDriver()
    seen = []
    rec = go('bootstrap', {'driver': factory(d, seen), 'subreddits': SUBS}, tmp_path)
    assert rec['outcome'] == 'pass' and rec['section_sha256'] is None and seen == [('bootstrap', None)]
    assert rec['counts']['navigations'] == 3 and rec['counts']['scrolls'] == 24
    cand = json.loads(st.candidate_path(tmp_path, 'browser').read_text(encoding='utf-8'))
    assert {e['lane'] for e in cand['section']['endpoints']} == {'posts', 'comments'}
    for p in tmp_path.rglob('*'):
        if p.is_file():
            assert fx.SECRET_MARK not in p.read_text(encoding='utf-8', errors='replace')


def test_bootstrap_refuses_a_proposal_that_does_not_fit(tmp_path):
    rec = go('bootstrap', {'driver': factory(fx.FakeDriver(pages=1)), 'subreddits': SUBS}, tmp_path)
    assert rec['outcome'] == 'fail' and rec['reason_codes'][0] == 'proposal_refused'
    assert not st.candidate_path(tmp_path, 'browser').exists()


def test_verify_reads_the_published_grammar_and_binds_its_hash(tmp_path):
    path, section = publish(tmp_path)
    seen = []
    rec = go('verify', {'driver': factory(fx.FakeDriver(), seen), 'subreddits': ('bitcoin',), 'now': lambda: NOW},
             tmp_path, path)
    assert rec['outcome'] == 'pass' and rec['section_sha256'] == section.sha256
    assert seen == [('verify', section.sha256)] and rec['counts']['navigations'] == 2
    assert po.verify_gate(tmp_path, 'browser', surface_path=path, max_age_days=7, today=TODAY) == 'ok'


@pytest.mark.parametrize('driver,reason', [
    (fx.FakeDriver(challenge=True), 'challenge'),
    (fx.FakeDriver(status=500), 'transport_failed'),
    (fx.FakeDriver(body_bytes=300), 'empty_shell'),
])
def test_verify_failures_are_allowlisted_codes(tmp_path, driver, reason):
    path, _ = publish(tmp_path)
    rec = go('verify', {'driver': factory(driver), 'subreddits': ('bitcoin',), 'now': lambda: NOW}, tmp_path, path)
    assert (rec['outcome'], rec['reason_codes']) == ('fail', [reason])


def test_refused_browser_and_missing_driver(tmp_path):
    @contextmanager
    def refused(mode, section):
        raise rb.Refused('browser_busy')
        yield
    rec = go('bootstrap', {'driver': refused}, tmp_path)
    assert (rec['outcome'], rec['reason_codes']) == ('fail', ['browser_refused'])
    with pytest.raises(po.ProbeRefused, match='dependency_missing:driver'):
        go('bootstrap', {}, tmp_path)


def test_production_dependencies_refuse_without_a_browser(monkeypatch):
    from api.data.attention import web_queries as wq
    import dataclasses
    cfg = dataclasses.replace(wq.load().config, browser_path=None, browser_profiles_dir=None)
    with pytest.raises(po.ProbeRefused, match='browser_not_configured'):
        pb.build_dependencies(cfg)
