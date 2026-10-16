import httpx

from api.data.attention import wikipedia
from .conftest import TODAY, client_for, wiki_payload


def test_ok_90_days():
    c = client_for(lambda r: httpx.Response(200, json=wiki_payload(95)))
    s = wikipedia.fetch_series("BTC", "Bitcoin", client=c, today=TODAY)
    assert s.state == "ok" and len(s.points) == 95 and s.source == "wikipedia"
    assert s.points[-1][0] < TODAY


def test_empty_is_unavailable():
    c = client_for(lambda r: httpx.Response(200, json={"items": []}))
    s = wikipedia.fetch_series("BTC", "Bitcoin", client=c, today=TODAY)
    assert s.state == "unavailable" and s.points == []


def test_short_history():
    c = client_for(lambda r: httpx.Response(200, json=wiki_payload(30)))
    s = wikipedia.fetch_series("BTC", "Bitcoin", client=c, today=TODAY)
    assert s.state == "insufficient-history" and len(s.points) == 30


def test_http_error_unavailable():
    c = client_for(lambda r: httpx.Response(500))
    s = wikipedia.fetch_series("BTC", "Bitcoin", client=c, today=TODAY)
    assert s.state == "unavailable" and "500" in s.reason


def test_rate_limit_is_capped_without_sleeping():
    calls = []
    c = client_for(lambda r: calls.append(1) or httpx.Response(429))
    s = wikipedia.fetch_series("BTC", "Bitcoin", client=c, today=TODAY, sleep=lambda x: None)
    assert s.state == "capped" and len(calls) >= 1


def test_404_is_no_article():
    c = client_for(lambda r: httpx.Response(404))
    s = wikipedia.fetch_series("BTC", "Bitcoin", client=c, today=TODAY)
    assert s.state == "no-article"


def test_missing_article_makes_no_request():
    calls = []
    c = client_for(lambda r: calls.append(1) or httpx.Response(200, json={}))
    s = wikipedia.fetch_series("XYZ", None, client=c, today=TODAY)
    assert s.state == "no-article" and not calls


def test_network_error_unavailable_without_secret_text():
    def h(r):
        raise httpx.ConnectError("boom secret-token")
    s = wikipedia.fetch_series("BTC", "Bitcoin", client=client_for(h), today=TODAY)
    assert s.state == "unavailable" and "secret" not in s.reason and "ConnectError" in s.reason


def test_today_is_dropped_at_fetch():
    p = wiki_payload(95)
    p["items"].append({"timestamp": TODAY.strftime("%Y%m%d") + "00", "views": 5})
    c = client_for(lambda r: httpx.Response(200, json=p))
    s = wikipedia.fetch_series("BTC", "Bitcoin", client=c, today=TODAY)
    assert all(d < TODAY for d, _ in s.points)


def test_wiki_articles_json_valid():
    import json
    from pathlib import Path
    m = json.loads((Path(wikipedia.__file__).parents[1] / "wiki_articles.json").read_text())
    assert m["BTC"] == "Bitcoin" and all(v is None or isinstance(v, str) for v in m.values())
