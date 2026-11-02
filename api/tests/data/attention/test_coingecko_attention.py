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
    assert set(rows[0]) == {"id", "symbol", "market_cap", "volume_24h", "rank", "name"}
    assert rows[0]["symbol"] == "BTC"
    assert {"USDT"} <= {r["symbol"] for r in rows} or len(rows) == len(markets_json)


def test_top100_markets_failure_returns_none():
    assert cg.fetch_top100_markets(client=client_for(lambda r: httpx.Response(500))) is None
    assert cg.fetch_top100_markets(client=client_for(lambda r: httpx.Response(429)),
                                   sleep=lambda x: None) is None


def test_markets_fetch_asks_for_120_rows_and_keeps_rank_and_name():
    seen = []
    body = [{"id": f"coin-{i}", "symbol": f"c{i}", "name": f"Coin {i}", "market_cap": 1000 - i,
             "total_volume": i} for i in range(120)]

    def h(r: httpx.Request):
        seen.append(r.url.params.get("per_page"))
        return httpx.Response(200, json=body)
    rows = cg.fetch_top100_markets(client=client_for(h))
    assert seen == ["120"] == [str(cg.MARKETS_ROWS)]
    assert [r["rank"] for r in rows] == list(range(1, 121))
    assert rows[0]["name"] == "Coin 0" and rows[119]["symbol"] == "C119"


def test_markets_fetch_drops_hostile_symbol_and_id_and_keeps_the_rank_of_the_rest():
    body = [{"id": "bitcoin", "symbol": "btc", "name": "Bitcoin", "market_cap": 3},
            {"id": "bad/../id", "symbol": "x", "name": "X", "market_cap": 2},
            {"id": "ok-id", "symbol": "::warning::", "name": "Y", "market_cap": 1},
            {"id": "eth.er_1", "symbol": "eth", "name": "\u202eEther", "market_cap": 1}]
    rows = cg.fetch_top100_markets(client=client_for(lambda r: httpx.Response(200, json=body)))
    assert [(r["id"], r["rank"]) for r in rows] == [("bitcoin", 1), ("eth.er_1", 4)]
    assert rows[1]["name"] == "Ether"


def test_chart_url_quotes_the_id():
    seen = []

    def h(r: httpx.Request):
        seen.append(r.url.raw_path.decode())
        return httpx.Response(200, json=chart_payload(95))
    cg.fetch_series("BTC", "a b", client=client_for(h), today=TODAY)
    assert "/coins/a%20b/market_chart" in seen[0]


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


# --- T223 O3: coin detail and price statistics for the classifier (live shapes UNVERIFIED until P-O0) ---

def test_coin_detail_keeps_only_categories_name_platform_and_quotes_the_id():
    seen = []

    def h(r: httpx.Request):
        seen.append((r.url.raw_path.decode(), dict(r.url.params)))
        return httpx.Response(200, json={"categories": ["Stablecoins", None, 3], "name": "Pay", "symbol": "pay",
                                         "asset_platform_id": "ethereum", "description": {"en": "long"}})
    got, state = cg.fetch_coin_detail("a b", client=client_for(h), sleep=lambda x: None)
    assert state == "ok" and got == {"categories": ["Stablecoins"], "name": "Pay", "asset_platform_id": "ethereum"}
    assert "/coins/a%20b" in seen[0][0] and seen[0][1].get("market_data") == "false"


def test_coin_detail_failures_are_states_never_raise():
    assert cg.fetch_coin_detail("x", client=client_for(lambda r: httpx.Response(429)), sleep=lambda x: None) == (
        None, "capped")
    assert cg.fetch_coin_detail("x", client=client_for(lambda r: httpx.Response(503)), sleep=lambda x: None) == (
        None, "unavailable")
    assert cg.fetch_coin_detail("x", client=client_for(lambda r: httpx.Response(200, json=[1])),
                                sleep=lambda x: None) == (None, "unavailable")

    def boom(r):
        raise httpx.ConnectError("secret")
    assert cg.fetch_coin_detail("x", client=client_for(boom), sleep=lambda x: None) == (None, "unavailable")


def test_price_stats_fetch_returns_derived_numbers_only():
    body = {"prices": [[1_700_000_000_000 + i * 86_400_000, 1.0 + i * 0.0001] for i in range(30)],
            "total_volumes": [[1, 2]]}
    got, state = cg.fetch_price_stats("usd-x", client=client_for(lambda r: httpx.Response(200, json=body)),
                                      sleep=lambda x: None)
    assert state == "ok" and set(got) == {"price_min", "price_max", "n_days", "last_price"} and got["n_days"] == 30
    assert cg.fetch_price_stats("x", client=client_for(lambda r: httpx.Response(429)), sleep=lambda x: None) == (
        None, "capped")
    assert cg.fetch_price_stats("x", client=client_for(lambda r: httpx.Response(200, json={"prices": []})),
                                sleep=lambda x: None) == (None, "unavailable")
