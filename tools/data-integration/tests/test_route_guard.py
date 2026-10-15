"""Route guard decisions and blocked-host diagnostics (stdlib only, AC-28..AC-30)."""
from __future__ import annotations

import pytest

from data_integration import route_guard as rg

PAGE = "page.example.test"
RES = "cdn.example.test"


class FakePass:
    def __init__(self, hosts=(PAGE,), resource_hosts=(), pages=("/data/",)):
        self.hosts, self.resource_hosts, self.pages = tuple(hosts), tuple(resource_hosts), tuple(pages)

    def permits(self, url):
        return rg.urlsplit(url).hostname in self.hosts and rg.urlsplit(url).path.startswith(self.pages)


class FakeRequest:
    def __init__(self, url, resource_type="script", nav=False):
        self.url, self.resource_type, self._nav = url, resource_type, nav

    def is_navigation_request(self):
        return self._nav


class FakeRoute:
    def __init__(self, request):
        self.request, self.action = request, None

    def continue_(self):
        self.action = "continue"

    def abort(self):
        self.action = "abort"


def _decide(url, rtype="script", nav=False, **kw):
    return rg.decide(url, rtype, nav, FakePass(**kw))


@pytest.mark.parametrize("rtype", ["script", "stylesheet", "font", "image", "xhr", "fetch"])
def test_listed_https_host_passes_for_six_types(rtype):
    assert _decide(f"https://{RES}/a.js", rtype, resource_hosts=(RES,))
    assert _decide(f"https://{RES}:443/a.js", rtype, resource_hosts=(RES,))


@pytest.mark.parametrize("rtype", ["document", "websocket", "other", "media", "eventsource", "manifest"])
def test_other_types_abort(rtype):
    assert not _decide(f"https://{RES}/a", rtype, resource_hosts=(RES,))


def test_navigation_to_listed_host_aborts():
    assert not _decide(f"https://{RES}/page", "document", True, resource_hosts=(RES,))
    assert not _decide(f"https://{RES}/page", "script", True, resource_hosts=(RES,))


def test_not_listed_http_port_and_odd_urls_abort():
    kw = dict(resource_hosts=(RES,))
    assert not _decide("https://other.example.test/a.js", **kw)
    assert not _decide(f"http://{RES}/a.js", **kw)
    assert not _decide(f"https://{RES}:8443/a.js", **kw)
    assert not _decide(f"https://{RES}\\@x/a.js", **kw)
    assert not _decide(f"https://u@{RES}/a.js", **kw)
    assert not _decide(f"https://{RES}:99999999/a.js", **kw)
    assert not _decide(None, **kw)


def test_empty_resource_hosts_equals_todays_guard():
    pass_ = FakePass()
    cases = [
        (f"https://{PAGE}/data/x", "document", True), (f"https://{PAGE}/other", "document", True),
        (f"https://{PAGE}/s.js", "script", False), (f"https://{RES}/s.js", "script", False),
        ("https://evil.example.test/", "document", True), (f"https://{PAGE}/data/x", "xhr", False),
    ]
    for url, rtype, nav in cases:
        today = rg.urlsplit(url).hostname in set(pass_.hosts) and (not nav or pass_.permits(url))
        assert rg.decide(url, rtype, nav, pass_) is today


def test_pass_without_resource_hosts_attribute_is_todays_guard():
    class Old:
        hosts = (PAGE,)

        def permits(self, url):
            return True

    assert rg.decide(f"https://{RES}/a.js", "script", False, Old()) is False


def test_host_label():
    assert rg.host_label("https://CDN.Example.test/a/b?q=1#f") == "cdn.example.test"
    assert rg.host_label("https://192.0.2.1/a") == "(ip)"
    assert rg.host_label("https://[2001:db8::1]/a") == "(ip)"
    assert rg.host_label("https://exa mple.test/") == "(invalid)"
    assert rg.host_label("https://" + "a" * 300 + ".test/") == "(invalid)"
    assert rg.host_label("not a url") == "(invalid)"
    assert rg.host_label(None) == "(invalid)"
    assert "/" not in rg.host_label("https://x.example.test/secret?token=1")


def test_summarise_distinct_sorted_bounded():
    labels = [f"h{i:02d}.example.test" for i in range(30)] + ["h00.example.test"]
    out = rg.summarise(reversed(labels))
    assert len(out) == 20 and list(out) == sorted(set(out)) and out[0] == "h00.example.test"
    text = rg.describe(out)
    assert text.startswith("browser request outside the pass was aborted; blocked hosts: h00.example.test")
    assert len(text.encode()) <= 600
    assert rg.describe(("b.example", "a.example")).endswith("blocked hosts: b.example, a.example")
    assert rg.describe(()) == "browser request outside the pass was aborted"


def test_describe_truncates_to_600_bytes():
    hosts = tuple("x" * 60 + f"{i}.example.test" for i in range(20))
    assert len(rg.describe(hosts).encode()) <= 600


def test_handler_continues_or_aborts_and_records_hosts_only():
    blocked: list[str] = []
    handler = rg.make_handler(FakePass(resource_hosts=(RES,)), blocked)
    ok = FakeRoute(FakeRequest(f"https://{RES}/a.js"))
    bad = FakeRoute(FakeRequest("https://tracker.example.test/p?id=9", "xhr"))
    nav = FakeRoute(FakeRequest(f"https://{RES}/p", "document", True))
    for r in (ok, bad, nav):
        handler(r)
    assert (ok.action, bad.action, nav.action) == ("continue", "abort", "abort")
    assert blocked == ["tracker.example.test", RES]


def test_redirect_hop_reenters_the_guard():
    blocked: list[str] = []
    handler = rg.make_handler(FakePass(resource_hosts=(RES,)), blocked)
    hop = FakeRoute(FakeRequest("https://elsewhere.example.test/next", "script"))
    handler(hop)
    assert hop.action == "abort" and blocked == ["elsewhere.example.test"]
