"""Pure B2 per-unit reconciliation and bounded admission/cache regressions."""
from datetime import timedelta
from functools import partial
from types import SimpleNamespace

from api.data.attention import x_proxy_runtime as runtime, x_proxy_snapshot as snapshot
from api.tests.data.attention.test_x_proxy_snapshot import NOW, fixture_open, write_snapshot


class Pool:
    def __init__(self):
        self.accounts = {}
        self.changes = []

    def reconcile_proxy(self, label, proxy_id, revision):
        previous = self.accounts.get(label)
        self.accounts[label] = (proxy_id, revision)
        self.changes.append(label)
        return previous != self.accounts[label]


def test_same_label_raw_snapshot_change_invalidates_admission_even_identity_off(tmp_path):
    path = write_snapshot(tmp_path / "private")
    loader = partial(snapshot.load_snapshot, opener=fixture_open)
    private = loader(path, repo_root=tmp_path / "repo")
    pool = Pool()
    resolver = runtime.ProxyRuntime(private.config, config_path=path, repo_root=tmp_path / "repo",
                                    clock=lambda: NOW, snapshot_loader=loader)
    assert resolver.reconcile(pool) == {"alpha", "beta"}
    previous = dict(resolver.snapshot.revisions)
    resolver.admissions["alpha"] = runtime.Admission(private.assignments["alpha"].proxy_id,
        previous["alpha"], NOW, NOW + timedelta(hours=1))
    # A trusted raw-byte revision is significant even when parsed values match.
    path.write_bytes(path.read_bytes() + b"\n")
    assert resolver.reconcile(pool) == {"alpha", "beta"}
    assert resolver.snapshot.config.x_identity_enabled is False
    assert resolver.snapshot.revisions["alpha"] != previous["alpha"]
    assert not resolver.admitted("alpha")


def test_unchanged_snapshot_preserves_revision_without_network(tmp_path):
    path = write_snapshot(tmp_path / "private")
    loader = partial(snapshot.load_snapshot, opener=fixture_open)
    private = loader(path, repo_root=tmp_path / "repo")
    pool = Pool()
    resolver = runtime.ProxyRuntime(private.config, config_path=path, repo_root=tmp_path / "repo",
                                    clock=lambda: NOW, snapshot_loader=loader)
    resolver.reconcile(pool)
    previous = dict(resolver.snapshot.revisions)
    assert resolver.reconcile(pool) == set()
    assert resolver.snapshot.revisions == previous


def test_one_account_assignment_edit_preserves_other_reader_revision(tmp_path):
    import json
    path = write_snapshot(tmp_path / "private")
    loader = partial(snapshot.load_snapshot, opener=fixture_open)
    private = loader(path, repo_root=tmp_path / "repo")
    resolver = runtime.ProxyRuntime(private.config, config_path=path, repo_root=tmp_path / "repo",
                                    clock=lambda: NOW, snapshot_loader=loader)
    pool = Pool()
    resolver.reconcile(pool)
    previous = dict(resolver.snapshot.revisions)
    assignment_path = path.parent / "assignments.json"
    document = json.loads(assignment_path.read_bytes())
    document["accounts"]["beta"]["expected_ip"] = "9.9.9.9"
    assignment_path.write_text(json.dumps(document), encoding="utf-8")
    assert resolver.reconcile(pool) == {"beta"}
    assert resolver.snapshot.revisions["alpha"] == previous["alpha"]
    assert resolver.snapshot.revisions["beta"] != previous["beta"]


def test_reader_reconcile_in_same_pass_evicts_only_changed_account_with_identity_off(tmp_path, monkeypatch):
    import json
    from api.data.attention import twscrape_reader as tr
    path = write_snapshot(tmp_path / "private")
    loader = partial(snapshot.load_snapshot, opener=fixture_open)
    private = loader(path, repo_root=tmp_path / "repo")
    resolver = runtime.ProxyRuntime(private.config, config_path=path, repo_root=tmp_path / "repo",
                                    clock=lambda: NOW, snapshot_loader=loader)
    pool = Pool()
    resolver.reconcile(pool)
    closed = []
    class Reader:
        def __init__(self, label, *args, account_names=(), **kwargs):
            self.label, self.account_names = label, account_names
        def close(self):
            closed.append(self.label)
    initial = {label: Reader(label) for label in private.config.x_accounts}
    adapter = SimpleNamespace(style="plain", identities={}, _route_failures={},
                              _items={("alpha", "old"): "alpha-generator", ("beta", "old"): "beta-generator"})
    start = tr.XStart(dict(initial), None, "off", adapter=adapter, runtime=resolver, library=object())
    monkeypatch.setattr(tr, "TwscrapeReader", Reader)
    # Admission has its own real/fake-client tests; this isolates reader eviction.
    monkeypatch.setattr(resolver, "admit", lambda label, pool: None)
    start.reconcile(private.config, pool)
    assert closed == []
    assignment_path = path.parent / "assignments.json"
    document = json.loads(assignment_path.read_bytes())
    document["accounts"]["beta"]["expected_ip"] = "9.9.9.9"
    assignment_path.write_text(json.dumps(document), encoding="utf-8")
    start.reconcile(private.config, pool)
    assert closed == ["beta"]
    assert start.readers["alpha"] is initial["alpha"] and start.readers["beta"] is not initial["beta"]
    assert adapter.identities == {} and adapter._items == {("alpha", "old"): "alpha-generator"}
    assert not resolver.admitted("beta")
