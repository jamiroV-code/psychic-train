"""S-RAcct-B contract F: union assignment namespace, site-scoped reconciliation, Reddit route admission.

Synthetic bytes and loopback-free fakes only: no request leaves the process.
"""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from functools import partial
from pathlib import Path
from uuid import UUID

import pytest

from api.data import cache
from api.data.attention import reddit_accounts as ra, x_pool as xpool, x_proxy as p
from api.data.attention import x_proxy_child as child, x_proxy_runtime as runtime, x_proxy_snapshot as snapshot
from api.tests.data.attention.test_x_proxy_policy import ID1, ID2, assignment_doc, firehol, policy_doc, spamhaus
from api.tests.data.attention.test_x_proxy_snapshot import NOW, fixture_open, query_document

ID3 = str(UUID(int=3))
ID4 = str(UUID(int=4))
MARKER = "SYNTHETIC_CREDENTIAL_MARKER"
REDDIT_IP = "4.4.4.4"


@pytest.fixture(autouse=True)
def _isolated(attention_cache):
    return attention_cache


def union_doc():
    doc = assignment_doc()
    doc["lines"][ID3] = 3
    doc["accounts"]["ra_one"] = {"proxy_id": ID3, "expected_ip": REDDIT_IP, "region": "US",
                                 "timezone": "America/New_York", "accept_language": "en-US"}
    return doc


ROUTES = (f"https://user:{MARKER}@first.example\nhttps://second.example\n"
          f"https://reddit:{MARKER}@third.example\nhttps://spare.example\n")


def write_union(root, *, provider=None, assignments=None):
    root.mkdir(mode=0o700, exist_ok=True)
    query = query_document(root)
    query["collector"]["reddit_browser_accounts"] = [{"label": "ra_one", "profile": "prof_ra_one"}]
    policy = policy_doc(root)
    policy["baseline"]["sha256"] = hashlib.sha256(b"trusted baseline").hexdigest()
    policy["metadata_provider"] = provider
    for name, value in (("queries.json", query), ("policy.json", policy),
                        ("assignments.json", assignments or union_doc())):
        (root / name).write_text(json.dumps(value), encoding="utf-8")
    (root / "routes.txt").write_text(ROUTES, encoding="utf-8")
    return root / "queries.json"


def edit_assignments(path, change):
    target = path.parent / "assignments.json"
    doc = json.loads(target.read_bytes())
    change(doc)
    target.write_text(json.dumps(doc), encoding="utf-8")


class XFake:
    """The existing B2 X-pool route protocol (reconcile only)."""
    def __init__(self):
        self.accounts = {}

    def reconcile_proxy(self, label, proxy_id, revision):
        previous = self.accounts.get(label)
        self.accounts[label] = (proxy_id, revision)
        return previous != self.accounts[label]


LOADER = partial(snapshot.load_snapshot, opener=fixture_open)


def resolver_for(path, tmp_path, request=None, clock=lambda: NOW):
    private = LOADER(path, repo_root=tmp_path / "repo")
    kwargs = {} if request is None else {"request": request}
    return runtime.ProxyRuntime(private.config, config_path=path, repo_root=tmp_path / "repo",
                                clock=clock, snapshot_loader=LOADER, **kwargs)


def reddit_pool(resolver, clock=lambda: NOW):
    return ra.RedditAccounts(["ra_one"], clock=clock, proxy_required=True, admission=resolver.route_admission)


def mark_ready():
    path = cache.CACHE_ROOT / "attention" / "_pc_state" / ra.READY_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"ready": {"ra_one": (NOW.date() - timedelta(days=1)).isoformat()}}))


# --- parse / snapshot over the union namespace ---

def test_union_parse_accepts_reddit_labels_and_rejects_unknown():
    body = json.dumps(union_doc()).encode()
    parsed = p.parse_assignments(body, ROUTES.encode(), ("alpha", "beta"), required=True, reddit_labels=("ra_one",))
    assert parsed["ra_one"].proxy_id == ID3 and parsed["ra_one"].expected_ip == REDDIT_IP
    with pytest.raises(p.ProxyFailure, match="proxy_assignment"):
        p.parse_assignments(body, ROUTES.encode(), ("alpha", "beta"), required=True)
    with pytest.raises(p.ProxyFailure, match="proxy_assignment"):
        p.parse_assignments(body, ROUTES.encode(), ("alpha", "beta"), required=True, reddit_labels=("rb_two",))


def test_union_label_collision_is_a_config_error():
    body = json.dumps(assignment_doc()).encode()
    with pytest.raises(p.ProxyFailure, match="proxy_config"):
        p.parse_assignments(body, ROUTES.encode(), ("alpha", "beta"), required=True, reddit_labels=("alpha",))


def test_reddit_assignment_is_optional_but_every_x_label_stays_required():
    body = json.dumps(assignment_doc()).encode()
    parsed = p.parse_assignments(body, ROUTES.encode(), ("alpha", "beta"), required=True, reddit_labels=("ra_one",))
    assert set(parsed) == {"alpha", "beta"}
    doc = union_doc()
    del doc["accounts"]["beta"]
    with pytest.raises(p.ProxyFailure, match="proxy_assignment"):
        p.parse_assignments(json.dumps(doc).encode(), ROUTES.encode(), ("alpha", "beta"), required=True,
                            reddit_labels=("ra_one",))


@pytest.mark.parametrize("field,value", [("expected_ip", "8.8.8.8"), ("proxy_id", ID1)])
def test_cross_site_duplicate_exit_or_proxy_id_refused(field, value):
    doc = union_doc()
    doc["accounts"]["ra_one"][field] = value
    with pytest.raises(p.ProxyFailure, match="proxy_assignment") as error:
        p.parse_assignments(json.dumps(doc).encode(), ROUTES.encode(), ("alpha", "beta"), required=True,
                            reddit_labels=("ra_one",))
    assert MARKER not in str(error.value)


def test_snapshot_loads_union_and_x_child_keeps_x_only_label_check(tmp_path):
    path = write_union(tmp_path / "private")
    private = LOADER(path, repo_root=tmp_path / "repo")
    assert set(private.assignments) == {"alpha", "beta", "ra_one"}
    assert MARKER not in repr(private)
    with pytest.raises(p.ProxyFailure, match="proxy_assignment"):
        child.admission_role(private, "ra_one", str(UUID(int=5, version=4)), now=NOW, repo_root=tmp_path / "repo")


# --- site-scoped reconciliation ---

def test_reddit_assignment_change_leaves_x_untouched(tmp_path):
    path = write_union(tmp_path / "private")
    resolver = resolver_for(path, tmp_path)
    xp_fake, view = XFake(), runtime.RedditRouteView(reddit_pool(resolver), runtime.ProviderBudget(None), clock=lambda: NOW)
    assert resolver.reconcile(xp_fake, reddit=view) == {"alpha", "beta"}
    assert set(resolver.snapshot.assignments) == {"alpha", "beta"}
    assert set(resolver.snapshot.reddit_assignments) == {"ra_one"}
    before, x_before = dict(resolver.snapshot.revisions), dict(xp_fake.accounts)
    assert view._acct("ra_one")["proxy_id"] == ID3
    edit_assignments(path, lambda d: (d["lines"].update({ID4: 4}),
                                      d["accounts"]["ra_one"].update(proxy_id=ID4)))
    assert resolver.reconcile(xp_fake, reddit=view) == set()
    assert xp_fake.accounts == x_before
    assert {k: resolver.snapshot.revisions[k] for k in ("alpha", "beta")} == {k: before[k] for k in ("alpha", "beta")}
    assert resolver.snapshot.revisions["ra_one"] != before["ra_one"]
    assert view._acct("ra_one")["proxy_id"] == ID4


def test_x_assignment_change_leaves_reddit_untouched(tmp_path):
    path = write_union(tmp_path / "private")
    resolver = resolver_for(path, tmp_path)
    xp_fake = XFake()
    view = runtime.RedditRouteView(reddit_pool(resolver), runtime.ProviderBudget(None), clock=lambda: NOW)
    resolver.reconcile(xp_fake, reddit=view)
    before = dict(resolver.snapshot.revisions)
    stored = view._acct("ra_one")
    edit_assignments(path, lambda d: d["accounts"]["beta"].update(expected_ip="9.9.9.9"))
    assert resolver.reconcile(xp_fake, reddit=view) == {"beta"}
    assert resolver.snapshot.revisions["ra_one"] == before["ra_one"]
    assert view._acct("ra_one") == stored


def test_reddit_label_unassigned_is_never_admitted(tmp_path):
    path = write_union(tmp_path / "private", assignments=assignment_doc())
    resolver = resolver_for(path, tmp_path)
    view = runtime.RedditRouteView(reddit_pool(resolver), runtime.ProviderBudget(None), clock=lambda: NOW)
    resolver.reconcile(XFake(), reddit=view)
    assert resolver.route_admission("reddit", "ra_one") == "unadmitted"
    with pytest.raises(p.ProxyFailure, match="proxy_assignment"):
        resolver.admit("ra_one", view)


# --- Reddit admission reuses ProxyRuntime ---

class Clock:
    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now


EXITS = {"first.example": "8.8.8.8", "second.example": "1.1.1.1", "third.example": REDDIT_IP,
         "spare.example": REDDIT_IP}


def fake_network(monkeypatch, calls, *, fail=None, clock=lambda: NOW):
    monkeypatch.setattr(runtime, "private_read", lambda path, policy, repo, limit: runtime.read_bounded(Path(path), limit))
    original_atomic, original_bytes = runtime.atomic_json, runtime.atomic_bytes
    monkeypatch.setattr(runtime, "atomic_json", lambda path, value, **kw: original_atomic(path, value))
    monkeypatch.setattr(runtime, "atomic_bytes", lambda path, value, **kw: original_bytes(path, value))
    monkeypatch.setattr(runtime, "secure_directory", lambda path, **kw: path.mkdir(parents=True, exist_ok=True))

    async def request(route, policy, url, limit):
        calls.append(url)
        if url == fail:
            raise p.ProxyFailure("proxy_exit")
        ip = next(value for host, value in EXITS.items() if host in route.url)
        return {policy.echo: json.dumps({"ip": ip}).encode(), p.SPAMHAUS: spamhaus(clock()),
                p.FIREHOL: firehol(clock()),
                p.IPAPI: json.dumps({"ip": ip, "country_code": "US", "region_code": "NY",
                                     "timezone": "America/New_York"}).encode(),
                policy.baseline: b"trusted baseline"}[url]
    return request


def test_proxy_required_reddit_account_without_admitted_route_is_never_selected(tmp_path, monkeypatch):
    calls = []
    path = write_union(tmp_path / "private")
    resolver = resolver_for(path, tmp_path, request=fake_network(monkeypatch, calls))
    mark_ready()
    accounts = reddit_pool(resolver)
    view = runtime.RedditRouteView(accounts, runtime.ProviderBudget(None), clock=lambda: NOW)
    resolver.reconcile(XFake(), reddit=view)
    assert resolver.route_admission("reddit", "ra_one") == "unadmitted"
    assert accounts.select() is None and accounts.account_state("ra_one") == ("locked", "proxy_not_admitted")
    resolver.admit("ra_one", view)
    assert calls and all(url != p.IPAPI for url in calls)
    assert resolver.route_admission("reddit", "ra_one") == "proxy"
    assert accounts.select() == "ra_one"
    assert resolver.route_admission("x", "alpha") == "unadmitted"


def test_reddit_admission_failure_quarantines_then_replacement_and_rollback(tmp_path, monkeypatch):
    calls, clock = [], Clock()
    path = write_union(tmp_path / "private")
    policy = json.loads((path.parent / "policy.json").read_bytes())
    resolver = resolver_for(path, tmp_path, request=fake_network(monkeypatch, calls, fail=policy["echo"]["url"],
                                                                  clock=clock), clock=clock)
    mark_ready()
    accounts = reddit_pool(resolver, clock=clock)
    view = runtime.RedditRouteView(accounts, runtime.ProviderBudget(None), clock=clock)
    resolver.reconcile(XFake(), reddit=view)
    with pytest.raises(p.ProxyFailure, match="proxy_exit"):
        resolver.admit("ra_one", view)
    assert accounts.account_state("ra_one") == ("locked", "proxy_quarantined")
    assert view._acct("ra_one")["proxy_quarantine_until"] is not None
    first_revision = resolver.snapshot.revisions["ra_one"]
    # Replacement: a new proxy for the account resets quarantine and requires a fresh admission.
    edit_assignments(path, lambda d: (d["lines"].update({ID4: 4}), d["accounts"]["ra_one"].update(proxy_id=ID4)))
    resolver.reconcile(XFake(), reddit=view)
    replaced = view._acct("ra_one")
    assert (replaced["proxy_id"], replaced["proxy_health"], replaced["proxy_quarantine_until"]) == (ID4, "unknown", None)
    assert resolver.route_admission("reddit", "ra_one") == "unadmitted"
    clock.now += timedelta(seconds=3600)  # the inherited B2 health interval still applies
    resolver.request = fake_network(monkeypatch, calls, clock=clock)
    resolver.admit("ra_one", view)
    assert resolver.route_admission("reddit", "ra_one") == "proxy" and accounts.select() == "ra_one"
    # Rollback to the previous assignment: a new opaque revision, admission invalidated again.
    edit_assignments(path, lambda d: d["accounts"]["ra_one"].update(proxy_id=ID3))
    resolver.reconcile(XFake(), reddit=view)
    assert resolver.snapshot.revisions["ra_one"] not in (first_revision,)
    assert view._acct("ra_one")["proxy_id"] == ID3
    assert resolver.route_admission("reddit", "ra_one") == "unadmitted" and accounts.select() is None


def test_single_provider_budget_under_two_site_contention(tmp_path, monkeypatch):
    calls = []
    path = write_union(tmp_path / "private", provider="ipapi")
    resolver = resolver_for(path, tmp_path, request=fake_network(monkeypatch, calls))
    x = xpool.XPool(["alpha", "beta"], clock=lambda: NOW)
    view = runtime.RedditRouteView(reddit_pool(resolver), runtime.ProviderBudget(x), clock=lambda: NOW)
    resolver.reconcile(x, reddit=view)
    state = json.loads(x.path.read_bytes())
    state["proxy_provider_budget"] = {"day": NOW.date().isoformat(), "used": 897}
    x.path.write_text(json.dumps(state), encoding="utf-8")
    resolver.admit("alpha", x)
    resolver.admit("ra_one", view)
    assert json.loads(x.path.read_bytes())["proxy_provider_budget"]["used"] == 899
    assert calls.count(p.IPAPI) == 2
    with pytest.raises(p.ProxyFailure, match="proxy_budget"):
        resolver.admit("beta", x)
    assert calls.count(p.IPAPI) == 2
    # The X pool state stays the only reservation record; Reddit state carries no budget of its own.
    assert "proxy_provider_budget" not in json.loads(view.accounts.path.read_bytes())
    assert sorted(f.name for f in x.path.parent.glob("*.json")) == ["reddit_accounts.json", "x_pool.json"]


def test_reddit_admission_without_provider_budget_refuses_ipapi(tmp_path, monkeypatch):
    calls = []
    path = write_union(tmp_path / "private", provider="ipapi")
    resolver = resolver_for(path, tmp_path, request=fake_network(monkeypatch, calls))
    view = runtime.RedditRouteView(reddit_pool(resolver), runtime.ProviderBudget(None), clock=lambda: NOW)
    resolver.reconcile(XFake(), reddit=view)
    with pytest.raises(p.ProxyFailure, match="proxy_budget"):
        resolver.admit("ra_one", view)
    assert p.IPAPI not in calls


def test_direct_config_admits_reddit_direct_only_when_proxy_inputs_absent(tmp_path):
    from api.data.attention import web_queries as wq
    doc = query_document(tmp_path, required=False)
    for key in ("x_proxy_list_path", "x_proxy_assignments_path", "x_proxy_policy_path"):
        doc["collector"][key] = None
    doc["collector"]["reddit_browser_accounts"] = [{"label": "ra_one", "profile": "prof_ra_one"}]
    config = wq.validate(doc).config
    resolver = runtime.ProxyRuntime(config, repo_root=tmp_path / "repo", clock=lambda: NOW)
    xfake = XFake()
    xfake._acct = lambda label: {"proxy_id": None}
    resolver.reconcile(xfake)
    assert resolver.route_admission("reddit", "ra_one") == "direct"
    assert resolver.route_admission("reddit", "rb_unknown") == "unadmitted"


def test_secret_marker_never_persisted_or_shown(tmp_path, monkeypatch):
    calls = []
    path = write_union(tmp_path / "private")
    resolver = resolver_for(path, tmp_path, request=fake_network(monkeypatch, calls))
    accounts = reddit_pool(resolver)
    view = runtime.RedditRouteView(accounts, runtime.ProviderBudget(None), clock=lambda: NOW)
    resolver.reconcile(XFake(), reddit=view)
    resolver.admit("ra_one", view)
    texts = [repr(resolver.snapshot), repr(view), repr(resolver.snapshot.reddit_assignments)]
    texts += [f.read_text(errors="ignore") for f in (cache.CACHE_ROOT / "attention").rglob("*") if f.is_file()]
    texts += [f.read_text(errors="ignore") for f in (tmp_path / "private" / "cache").rglob("*.json")]
    assert not any(MARKER in text or "reddit:" in text for text in texts)
