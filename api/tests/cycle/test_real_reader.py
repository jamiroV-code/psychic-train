"""Cycle fixture contract: real TwscrapeReader, upstream search and bootstrap over TLS."""
import asyncio

from api.data.attention import twscrape_reader as tr
from api.tests.cycle.services import AUTH, CSRF, Clock, Origin


def test_real_reader_bootstrap_parser_and_cookie_wire(tmp_path, monkeypatch):
    clock = Clock()
    origin = Origin(tmp_path, clock)
    reader = None
    try:
        origin.install(monkeypatch)
        lib = tr.load_library()
        path = tmp_path / "acc_a.db"
        api = lib.API(str(path))
        asyncio.run(api.pool.add_account_cookies("acc_a", f"auth_token={AUTH['acc_a']}; ct0={CSRF}"))
        reader = tr.TwscrapeReader("acc_a", path, lib, max_entries=40)
        end = int(clock().timestamp())
        query = f'"$SOL" since_time:{end - 86400} until_time:{end} lang:en -filter:replies -filter:retweets'
        page = reader.search_raw(query, {"product": "Latest"}, 0)
        assert page is not None
        assert len(reader.parse_tweets(page.body)) == 20
        assert len(page.entry_ids) == 20
        assert origin.errors == []
        assert {r["path"] for r in origin.requests} >= {"/tesla", "/responsive-web/client-web/sign.o-fixture.js"}
        assert all(r["ct0_count"] <= 1 for r in origin.requests)
        assert {"x.com", "abs.twimg.com"} <= set(origin.sni)
    finally:
        if reader:
            reader.close()
        origin.close()
