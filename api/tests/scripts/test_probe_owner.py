"""Protocol tests: synthetic injected executors only; no provider requests."""
import io
import json
from datetime import date

import pytest

from api.scripts import probe_owner as po


@pytest.mark.parametrize('probe', po.PROBES)
def test_dry_run_never_executes(probe, tmp_path):
    def forbidden(ctx):
        pytest.fail('dry run executed')
    result = po.run(probe, approval=None, cache_root=tmp_path, commit='a'*40,
                    executors={probe: forbidden})
    assert result['dry_run'] is True
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('probe,reason', [('PR1','executor_pending:S-RGQL'),
    ('PR2','executor_pending:S-RBrowser'), ('PR3','executor_refused:a17_cookie_boundary'), ('PR4','probe_reserved')])
def test_unavailable_probes_cannot_create_records(probe, reason, tmp_path):
    class NoCookies:
        def __getattribute__(self, key):
            pytest.fail('cookie access')
    with pytest.raises(po.ProbeRefused, match=reason):
        po.run(probe, approval=po.plan(probe)['approval_digest'], cache_root=tmp_path,
               commit='a'*40, executors={}, dependencies={'cookies': NoCookies()})
    assert not list(tmp_path.iterdir())


def test_only_executor_outcome_can_be_recorded(tmp_path):
    kwargs = dict(approval=po.plan('PX1')['approval_digest'], cache_root=tmp_path, commit='a'*40,
                  today=date(2026,11,7))
    with pytest.raises(po.ProbeRefused, match='executor_result_invalid'):
        po.run('PX1', executors={'PX1': lambda ctx: {'outcome':'pass'}}, **kwargs)
    assert not list(tmp_path.rglob('probe_*.json'))
    def executor(ctx):
        ctx.charge()
        return po.Outcome('pass')
    result = po.run('PX1', executors={'PX1':executor}, **kwargs)
    assert result['counts']['requests'] == 1
    assert po.latest_record(tmp_path,'PX1','observe') == result


def test_budget_prevents_seventh_request(tmp_path):
    sends=[]
    def executor(ctx):
        for _ in range(7):
            ctx.charge()
            sends.append(1)
        return po.Outcome('pass')
    result=po.run('PX1', approval=po.plan('PX1')['approval_digest'], cache_root=tmp_path,
                  commit='a'*40, executors={'PX1':executor})
    assert len(sends)==6 and result['outcome']=='fail' and result['limits_hit']==['requests']


def test_budget_resource_and_scroll_bounds():
    b=po.Budget(po.limits_for('PR2','bootstrap'))
    assert all(b.charge('scrolls') for _ in range(12))
    assert not b.charge('scrolls')
    assert b.charge('navigations') and b.charge('scrolls')
    assert not b.charge('responses', nbytes=3*1024*1024)
    assert b.counts['bytes']==0


def test_registry_rejects_reserved_and_duplicate(monkeypatch):
    monkeypatch.setattr(po,'EXECUTORS',{})
    fn=lambda ctx: po.Outcome('pass')
    assert po.register('PR2')(fn) is fn
    with pytest.raises(ValueError):
        po.register('PR2')(fn)
    with pytest.raises(ValueError):
        po.register('PR3')


def test_invalid_mode_and_wrong_digest_never_execute(tmp_path):
    with pytest.raises(po.ProbeRefused,match='mode_unsupported'):
        po.plan('PX1','verify')
    result=po.run('PX1',approval='PX1',cache_root=tmp_path,commit='a'*40,executors={})
    assert result['dry_run']


def test_cli_prints_dry_run(tmp_path):
    out=io.StringIO()
    assert po.main(['PR2'],cache_root=tmp_path,out=out,executors={})==0
    assert json.loads(out.getvalue())['dry_run']
