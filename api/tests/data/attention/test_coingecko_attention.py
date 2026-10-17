import httpx

from api.data.attention import coingecko_attention as cg
from .conftest import TODAY, chart_payload, client_for


def test_top100_excludes_stable_and_wrapped(markets_json):
    c = client_for(lambda r: httpx.Response(200, json=markets_json))
    rows = cg.fetch_top100(client=c)
    assert [r["symbol"] for r in rows] == ["BTC", "ETH", "SOL"]
    assert rows[0]["id"] == "bitcoin" and rows[0]["market_cap"] == 1000


def test_top100_error_returns_none():
    c = client_for(lambda r: httpx.Response(500))
    assert cg.fetch_top100(client=c) is None


def test_top100_rate_limit_returns_none():
    c = client_for(lambda r: httpx.Response(429))
    assert cg.fetch_top100(client=c, sleep=lambda x: None) is None


def test_series_ok_drops_today():
    c = client_for(lambda r: httpx.Response(200, json=chart_payload(95)))
    s = cg.fetch_series("BTC", "bitcoin", client=c, today=TODAY)
    assert s.state == "ok" and s.source == "coingecko" and len(s.points) == 94
    assert all(d < TODAY for d, _ in s.points)


def test_series_short():
    c = client_for(lambda r: httpx.Response(200, json=chart_payload(20)))
    assert cg.fetch_series("BTC", "bitcoin", client=c, today=TODAY).state == "insufficient-history"


def test_series_empty():
    c = client_for(lambda r: httpx.Response(200, json={"total_volumes": []}))
    assert cg.fetch_series("BTC", "bitcoin", client=c, today=TODAY).state == "unavailable"


def test_series_http_error():
    c = client_for(lambda r: httpx.Response(503))
    assert cg.fetch_series("BTC", "bitcoin", client=c, today=TODAY).state == "unavailable"


def test_series_rate_limit_capped():
    c = client_for(lambda r: httpx.Response(429))
    s = cg.fetch_series("BTC", "bitcoin", client=c, today=TODAY, sleep=lambda x: None)
    assert s.state == "capped"


def test_top100_markets_unfiltered_with_volume(markets_json):
    c = client_for(lambda r: httpx.Response(200, json=markets_json))
    rows = cg.fetch_top100_markets(client=c)
    assert len(rows) == len(markets_json)
    assert set(rows[0]) == {"id", "symbol", "market_cap", "volume_24h"}
    assert rows[0]["symbol"] == "BTC"
    assert {"USDT"} <= {r["symbol"] for r in rows} or len(rows) == len(markets_json)


def test_top100_markets_failure_returns_none():
    assert cg.fetch_top100_markets(client=client_for(lambda r: httpx.Response(500))) is None
    assert cg.fetch_top100_markets(client=client_for(lambda r: httpx.Response(429)),
                                   sleep=lambda x: None) is None


def _cat_handler(by_cat, status=200):
    def h(r: httpx.Request):
        cid = r.url.params.get("category")
        assert "coins/markets" in str(r.url) and cid
        return httpx.Response(status, json=by_cat.get(cid, []))
    return h


def test_categories_ok_uppercases_and_maps_symbols():
    c = client_for(_cat_handler({"ai": [{"symbol": "fet"}, {"symbol": "tao"}], "defi": [{"symbol": "uni"}]}))
    out = cg.fetch_categories(["ai", "defi"], client=c, sleep=lambda x: None)
    assert out == {"ai": ["FET", "TAO"], "defi": ["UNI"]}


def test_categories_empty_category_is_kept_empty():
    c = client_for(_cat_handler({}))
    assert cg.fetch_categories(["ai"], client=c, sleep=lambda x: None) == {"ai": []}


def test_categories_http_error_returns_none():
    c = client_for(_cat_handler({}, status=500))
    assert cg.fetch_categories(["ai"], client=c, sleep=lambda x: None) is None


def test_categories_rate_limit_returns_none_after_backoff():
    sleeps = []
    c = client_for(_cat_handler({}, status=429))
    assert cg.fetch_categories(["ai"], client=c, sleep=sleeps.append) is None
    assert sleeps


def test_categories_one_failure_fails_all():
    def h(r):
        return httpx.Response(500 if r.url.params["category"] == "defi" else 200, json=[])
    assert cg.fetch_categories(["ai", "defi"], client=client_for(h), sleep=lambda x: None) is None


def test_categories_malformed_json_returns_none():
    c = client_for(lambda r: httpx.Response(200, json={"error": "x"}))
    assert cg.fetch_categories(["ai"], client=c, sleep=lambda x: None) is None
