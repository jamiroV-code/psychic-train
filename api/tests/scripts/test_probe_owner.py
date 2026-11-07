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

@pytest.mark.parametrize("kind", ["relative", "repository"])
def test_private_query_selection_rejects_unsafe_paths(kind, tmp_path):
    from api.data.attention import web_queries
    path = "private.json" if kind == "relative" else str(web_queries.QUERIES_PATH)
    with pytest.raises(SystemExit) as exc:
        po.main(["PX1", "--queries", path], cache_root=tmp_path, out=io.StringIO())
    assert exc.value.code == 2


def test_private_query_selection_is_lazy_during_dry_run(tmp_path):
    out = io.StringIO()
    assert po.main(["PX1", "--queries", str(tmp_path / "private.json")],
                   cache_root=tmp_path, out=out) == 0
    assert json.loads(out.getvalue())["dry_run"]


def _approved_main(monkeypatch, tmp_path, argv, configured):
    from types import SimpleNamespace
    from api.data.attention import web_queries
    from api.scripts import probe_executors as pe
    config = SimpleNamespace(x_proxy_required=configured, x_proxy_list_path=None,
                             x_proxy_assignments_path=None, x_proxy_policy_path=None)
    loaded = []
    monkeypatch.setattr(web_queries, "load", lambda path=None: loaded.append(path) or SimpleNamespace(config=config))
    built = []
    monkeypatch.setattr(pe, "build_dependencies",
                        lambda probe, cfg, *, config_path=None: built.append((probe, config_path)) or {})
    digest = po.plan("PX1")["approval_digest"]
    out = io.StringIO()
    po.main(["PX1", "--approve", digest, *argv], cache_root=tmp_path, out=out,
            executors={"PX1": lambda run: po.Outcome("pass")})
    return json.loads(out.getvalue()), loaded, built


def test_routed_config_without_private_queries_refuses(monkeypatch, tmp_path):
    result, loaded, built = _approved_main(monkeypatch, tmp_path, [], configured=True)
    assert result["reason"] == "private_queries_required"
    assert loaded == [None] and built == []


def test_private_queries_path_reaches_the_builder(monkeypatch, tmp_path):
    private = tmp_path / "private.json"
    result, loaded, built = _approved_main(monkeypatch, tmp_path, ["--queries", str(private)], configured=True)
    assert loaded == [private] and built == [("PX1", private)]


def test_direct_config_keeps_committed_default(monkeypatch, tmp_path):
    result, loaded, built = _approved_main(monkeypatch, tmp_path, [], configured=False)
    assert loaded == [None] and built == [("PX1", None)]
