"""T223 O4: onboarding fetchers are fail-closed; verdict functions moved here unchanged. Fakes only."""
from __future__ import annotations

from datetime import date, timedelta

import httpx

from api.data.attention import onboarding_sources as osrc
from api.scripts import check_trends_keywords as ctk
from .conftest import TODAY, client_for, wiki_payload


class FakeTrendReq:
    def __init__(self, sugg=None, exc=None):
        self.sugg, self.exc = sugg, exc

    def suggestions(self, q):
        if self.exc:
            raise self.exc
        return self.sugg


class TooMany(Exception):
    def __init__(self):
        super().__init__("The request failed: Google returned a response with code 429 secret")
        self.response = type("R", (), {"status_code": 429})()


def test_the_checker_uses_the_library_functions():
    for name in ("is_crypto_type", "_exact_match", "_bracket_match", "_ticker_match", "_usable", "CRYPTO_TYPE_WORDS"):
        assert getattr(ctk, name) is getattr(osrc, name)


def test_suggestions_ok_failed_and_rate_limited():
    raw = [{"mid": "/g/foo", "title": "Foo", "type": "Cryptocurrency"}, {"mid": "bad", "title": "x", "type": "y"}]
    assert osrc.fetch_suggestions(FakeTrendReq(raw), "Foo") == ([raw[0]], "ok")
    assert osrc.fetch_suggestions(FakeTrendReq(exc=RuntimeError("boom")), "Foo") == (None, "unavailable")
    assert osrc.fetch_suggestions(FakeTrendReq(exc=TooMany()), "Foo")[1] in ("capped", "unavailable")


def summary(title="Foo Network", type_="standard"):
    return {"type": type_, "title": title.replace(" ", "_"), "titles": {"normalized": title},
            "description": "cryptocurrency", "extract": "Foo Network is a blockchain."}


def test_wiki_page_reads_the_returned_title_and_quotes_the_request():
    seen = []

    def h(r):
        seen.append(r.url.raw_path.decode())
        return httpx.Response(200, json=summary("Foo (company)"))
    got, st = osrc.fetch_wiki_page("Foo/../x y", client=client_for(h))
    assert st == "ok" and got["canonical"] == "Foo (company)" and got["type"] == "standard"
    assert "Foo%2F..%2Fx_y" in seen[0]


def test_wiki_page_failure_states():
    assert osrc.fetch_wiki_page("X", client=client_for(lambda r: httpx.Response(404))) == (None, "none")
    assert osrc.fetch_wiki_page("X", client=client_for(lambda r: httpx.Response(429))) == (None, "capped")
    assert osrc.fetch_wiki_page("X", client=client_for(lambda r: httpx.Response(500))) == (None, "unavailable")
    assert osrc.fetch_wiki_page("X", client=client_for(lambda r: httpx.Response(200, text="<html>"))) == (
        None, "unavailable")

    def boom(r):
        raise httpx.ConnectError("secret")
    assert osrc.fetch_wiki_page("X", client=client_for(boom)) == (None, "unavailable")


def test_pageview_days():
    c = client_for(lambda r: httpx.Response(200, json=wiki_payload(40)))
    assert osrc.fetch_pageview_days("FOO", "Foo", client=c, today=TODAY, sleep=lambda s: None) == (40, "ok")
    c = client_for(lambda r: httpx.Response(429))
    assert osrc.fetch_pageview_days("FOO", "Foo", client=c, today=TODAY, sleep=lambda s: None) == (0, "capped")


def test_identity_needs_overlapping_volume():
    days = [date(2026, 6, 1) + timedelta(days=i) for i in range(90)]
    pts = [(d, float(10 + i + (i % 3))) for i, d in enumerate(days)]
    vol = [(d, 1000.0 * (10 + i)) for i, d in enumerate(days)]
    corr, n = osrc.identity(pts, vol)
    assert n >= 60 and corr is not None and corr > 0.5
    assert osrc.identity(pts, vol[:30])[1] < 60 and osrc.identity(pts, vol[:30])[0] is None
    assert osrc.identity([], vol) == (None, 0)
