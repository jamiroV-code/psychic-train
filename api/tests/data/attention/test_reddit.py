from datetime import timedelta

import httpx

from api.data.attention import reddit, store
from api.tests.data.attention.conftest import TODAY, client_for


def _listing(n):
    return {"data": {"children": [{"data": {"id": str(i)}} for i in range(n)]}}


def _handler(n=7):
    def h(r: httpx.Request):
        if "access_token" in str(r.url):
            return httpx.Response(200, json={"access_token": "tok"})
        return httpx.Response(200, json=_listing(n))
    return h


def test_no_keys_is_unavailable_without_network(monkeypatch):
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
    monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)

    def fail(r):
        raise AssertionError("no keys: no network call")

    s = reddit.fetch_series("BTC", client=client_for(fail), today=TODAY)
    assert s.state == "unavailable" and s.points == [] and s.source == "reddit"


def test_keys_give_one_completed_day_point(monkeypatch):
    monkeypatch.setenv("REDDIT_CLIENT_ID", "id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "secret")
    s = reddit.fetch_series("BTC", client=client_for(_handler(7)), today=TODAY)
    assert s.state == "ok"
    assert s.points == [(TODAY - timedelta(days=1), 7.0)]


def test_failed_search_is_unavailable(monkeypatch):
    monkeypatch.setenv("REDDIT_CLIENT_ID", "id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "secret")

    def h(r):
        if "access_token" in str(r.url):
            return httpx.Response(200, json={"access_token": "tok"})
        return httpx.Response(500)

    s = reddit.fetch_series("BTC", client=client_for(h), today=TODAY)
    assert s.state == "unavailable"


def test_point_lands_in_store_and_stays_insufficient(monkeypatch, isolated_cache):
    monkeypatch.setenv("REDDIT_CLIENT_ID", "id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "secret")
    s = reddit.fetch_series("ETH", client=client_for(_handler(3)), today=TODAY)
    assert store.write_series(s, today=TODAY) == 1
