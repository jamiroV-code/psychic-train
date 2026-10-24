"""Resource-host guard (AC-28..AC-31), CI-safe: loads route_guard.py and approvals.py by path (stdlib only)."""
from __future__ import annotations

import importlib.util

import pytest

from ._common import TOOL_DIR

SRC = TOOL_DIR / "src" / "data_integration"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"_rh_{name}", SRC / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class P:
    def __init__(self, hosts=("page.example.test",), resource_hosts=()):
        self.hosts, self.resource_hosts = tuple(hosts), tuple(resource_hosts)

    def permits(self, url):
        return True


class Req:
    def __init__(self, url, rtype="script", nav=False):
        self.url, self.resource_type, self.nav = url, rtype, nav

    def is_navigation_request(self):
        return self.nav


class Route:
    def __init__(self, req):
        self.request, self.action = req, None

    def continue_(self):
        self.action = "continue"

    def abort(self):
        self.action = "abort"


def test_decide_allows_listed_subresources_only():
    rg = _load("route_guard")
    p = P(resource_hosts=("cdn.example.test",))
    for t in ("script", "stylesheet", "font", "image", "xhr", "fetch"):
        assert rg.decide("https://cdn.example.test/a", t, False, p)
    assert not rg.decide("https://cdn.example.test/a", "document", True, p)
    assert not rg.decide("https://cdn.example.test/a", "websocket", False, p)
    assert not rg.decide("https://cdn.example.test/a", "other", False, p)
    assert not rg.decide("http://cdn.example.test/a", "script", False, p)
    assert not rg.decide("https://cdn.example.test:8443/a", "script", False, p)
    assert not rg.decide("https://x.example.test/a", "script", False, p)


def test_handler_records_hosts_only():
    rg = _load("route_guard")
    blocked: list[str] = []
    h = rg.make_handler(P(), blocked)
    r = Route(Req("https://t.example.test/p?q=1", "xhr"))
    h(r)
    assert r.action == "abort" and blocked == ["t.example.test"]


def test_record_checks():
    ap = _load("approvals")
    ap.check_resource_hosts(("cdn.example.test",), 2)
    for bad in (("*.a.test",), ("192.0.2.1",), ("0x7f.0x1",), ("a.test:1",), ("a.test", "a.test")):
        with pytest.raises(ValueError):
            ap.check_resource_hosts(bad, 2)
    with pytest.raises(ValueError):
        ap.check_resource_hosts(("cdn.example.test",), 1)
    with pytest.raises(ValueError):
        ap.check_resource_hosts(tuple(f"h{i}.example.test" for i in range(9)), 2)
