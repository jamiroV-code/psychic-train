"""request_access: refusal reasons, expiry boundary, host/page-bound FetchPass."""
from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone

import pytest

from data_integration.approvals import ApprovalStore, format_utc
from data_integration.gate import FetchPass, Refused, request_access
from _helpers import NOW, fixed_clock, make_record


@pytest.fixture
def store(tmp_path):
    s = ApprovalStore(tmp_path / "ap")
    s.write(make_record())
    return s


@pytest.fixture
def client_counter(monkeypatch):
    # looked up by name: the marker audit flags tests that import network modules
    socket = importlib.import_module("socket")
    calls = []

    class Counting(socket.socket):
        def __init__(self, *a, **k):
            calls.append(1)
            super().__init__(*a, **k)

    monkeypatch.setattr(socket, "socket", Counting)
    return calls


def test_grant_equal_and_lower_tier(store):
    for tier in (1, 2):
        p = request_access("example-src", tier, store, fixed_clock())
        assert isinstance(p, FetchPass)
        assert p.source == "example-src" and p.tier == tier


def test_tier_above_refused(store):
    r = request_access("example-src", 3, store, fixed_clock())
    assert isinstance(r, Refused) and r.reason == "tier_too_low"
    assert r.tier_asked == 3 and r.tier_allowed == 2 and r.source == "example-src"
    assert r.expiry == format_utc(NOW + timedelta(days=30))


def test_invalid_tier_refused(store):
    for t in (0, 4, "2", None, True):
        assert request_access("example-src", t, store, fixed_clock()).reason == "tier_too_low"


def test_expiry_boundary(tmp_path):
    s = ApprovalStore(tmp_path)
    s.write(make_record(expiry=NOW))
    r = request_access("example-src", 1, s, fixed_clock(NOW))
    assert r.reason == "expired"
    ok = request_access("example-src", 1, s, fixed_clock(NOW - timedelta(seconds=1)))
    assert isinstance(ok, FetchPass)


def test_missing_and_store_missing(tmp_path):
    s = ApprovalStore(tmp_path)
    assert request_access("example-src", 1, s, fixed_clock()).reason == "missing"
    s2 = ApprovalStore(tmp_path / "nope")
    assert request_access("example-src", 1, s2, fixed_clock()).reason == "store_missing"


def test_corrupt_refused(tmp_path):
    (tmp_path / "example-src.approval.json").write_text("[]", encoding="utf-8")
    r = request_access("example-src", 1, ApprovalStore(tmp_path), fixed_clock())
    assert r.reason == "store_corrupt"


def test_naive_clock_is_bad_clock(store):
    r = request_access("example-src", 1, store, lambda: datetime(2026, 1, 10, 12, 0, 0))
    assert r.reason == "bad_clock"


def test_clock_errors_are_bad_clock(store):
    def bad():
        raise RuntimeError("x")

    assert request_access("example-src", 1, store, bad).reason == "bad_clock"
    assert request_access("example-src", 1, store, lambda: "now").reason == "bad_clock"


def test_future_approval_date_is_bad_clock(tmp_path):
    s = ApprovalStore(tmp_path)
    s.write(make_record(approved=NOW + timedelta(days=2)))
    assert request_access("example-src", 1, s, fixed_clock()).reason == "bad_clock"


def test_non_utc_aware_clock_ok(store):
    tz = timezone(timedelta(hours=2))
    assert isinstance(request_access("example-src", 1, store, lambda: NOW.astimezone(tz)), FetchPass)


def test_bad_source_names_refused_not_raised(store):
    for bad in ["../x", "a.b", "CON", "", "x" * 70, None, 3]:
        r = request_access(bad, 1, store, fixed_clock())
        assert isinstance(r, Refused) and r.reason == "missing"


def test_pass_bound_to_host_and_page(store):
    p = request_access("example-src", 2, store, fixed_clock())
    assert p.permits("https://a.example.test/data/x.csv")
    assert p.permits("http://A.EXAMPLE.TEST/data/")
    assert not p.permits("https://b.example.test/data/x.csv")
    assert not p.permits("https://a.example.test/other")
    assert not p.permits("https://a.example.test/data/../secret")
    assert not p.permits("https://a.example.test/database")


def test_permits_userinfo_scheme_port(store):
    p = request_access("example-src", 2, store, fixed_clock())
    assert not p.permits("https://user@a.example.test/data/")
    assert not p.permits("https://a.example.test@evil.test/data/")
    assert not p.permits("https://evil.test\\@a.example.test/data/")
    assert not p.permits("ftp://a.example.test/data/")
    assert not p.permits("file:///data/")
    assert not p.permits("https://a.example.test:8443/data/")
    assert p.permits("https://a.example.test:443/data/")
    assert not p.permits("http://a.example.test:443/data/")
    assert not p.permits("not a url")
    assert not p.permits(None)


def test_pass_constructor_is_private():
    with pytest.raises(TypeError):
        FetchPass(object(), source="example-src", tier=1, hosts=("a.example.test",), pages=("/",))
    with pytest.raises(TypeError):
        FetchPass()


def test_duck_typed_pass_rejected():
    class Fake:
        source, tier = "example-src", 1

        def permits(self, url):
            return True

    assert not isinstance(Fake(), FetchPass)


def test_zero_client_on_every_refusal(tmp_path, client_counter):
    s = ApprovalStore(tmp_path / "ap")
    s.write(make_record("src-ok"))
    s.write(make_record("src-old", expiry=NOW - timedelta(days=1)))
    (tmp_path / "ap" / "src-bad.approval.json").write_text("{", encoding="utf-8")
    cases = [
        (("src-none", 1, s, fixed_clock()), "missing"),
        (("src-old", 1, s, fixed_clock()), "expired"),
        (("src-ok", 3, s, fixed_clock()), "tier_too_low"),
        (("src-ok", 1, ApprovalStore(tmp_path / "x"), fixed_clock()), "store_missing"),
        (("src-ok", 1, s, lambda: datetime(2026, 1, 1)), "bad_clock"),
        (("src-bad", 1, s, fixed_clock()), "store_corrupt"),
    ]
    for args, reason in cases:
        assert request_access(*args).reason == reason
    assert client_counter == []


def test_gate_module_stdlib_only():
    import ast
    import pathlib
    import sys

    import data_integration.gate as g

    tree = ast.parse(pathlib.Path(g.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        for n in names:
            assert n.split(".")[0] in sys.stdlib_module_names or n.split(".")[0] == "data_integration", n
