"""Spot volume (Binance, Coinbase, Kraken): parsing, store writes, daily schedule. No network, nothing sleeps."""
from __future__ import annotations

import threading
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest

from api.data import spot_volume_refresh
from api.data.attention import defillama, registry, spot_volume, store

TODAY = date(2026, 10, 31)
DAYS = 100  # completed days returned by the fake venues: above the 90-day Discovery gate


def _epoch(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


def _days(n: int = DAYS, through: date = TODAY) -> list[date]:
    """n completed days ending yesterday, plus today's partial bar."""
    return [through - timedelta(days=k) for k in range(n, -1, -1)]


def _handler(request: httpx.Request) -> httpx.Response:
    url = request.url
    if url.host == "api.binance.com":
        if url.params["symbol"] != "BTCUSDT":
            return httpx.Response(400, json={"code": -1121, "msg": "Invalid symbol."})
        bars = [[_epoch(d) * 1000, "1", "1", "1", "1", "5", 0, str(1000.0 + i), 7] for i, d in enumerate(_days())]
        return httpx.Response(200, json=bars)
    if url.host == "api.exchange.coinbase.com":
        if "/BTC-USD/" not in url.path:
            return httpx.Response(404, json={"message": "NotFound"})
        bars = [[_epoch(d), 1, 1, 1, 10.0, 2.0] for d in reversed(_days())]  # newest first, like the API
        return httpx.Response(200, json=bars)
    if url.host == "api.kraken.com":
        if url.params["pair"] != "BTCUSD":
            return httpx.Response(200, json={"error": ["EQuery:Unknown asset pair"]})
        bars = [[_epoch(d), "1", "1", "1", "1", "4.0", "3.0", 9] for d in _days()]
        return httpx.Response(200, json={"error": [], "result": {"XXBTZUSD": bars, "last": _epoch(TODAY)}})
    if url.host == "api.llama.fi":
        return _llama(url)
    return httpx.Response(500)


def _fees_chart(per_day: float, n: int = DAYS) -> dict:
    return {"totalDataChart": [[_epoch(d), per_day] for d in _days(n)]}


def _llama(url: httpx.URL) -> httpx.Response:
    if url.path == "/protocols":
        return httpx.Response(200, json=[
            {"slug": "btc-old", "gecko_id": "bitcoin", "tvl": 9},     # fewer fees than btc-main: not chosen
            {"slug": "btc-main", "gecko_id": "bitcoin", "tvl": 5},
            {"slug": "dead-proto", "gecko_id": "dead-coin", "tvl": 1},  # paid no fees in 30 days
            {"slug": "other", "gecko_id": None, "tvl": 1},
        ])
    if url.path == "/v2/chains":
        return httpx.Response(200, json=[{"name": "Ethereum", "gecko_id": "ethereum"}])
    if url.path == "/summary/fees/btc-old":
        return httpx.Response(200, json=_fees_chart(1.0))
    if url.path == "/summary/fees/btc-main":
        return httpx.Response(200, json=_fees_chart(7.0))
    if url.path == "/summary/fees/dead-proto":
        return httpx.Response(200, json=_fees_chart(0.0))
    if url.path == "/overview/fees/Ethereum":
        return httpx.Response(200, json=_fees_chart(50.0))
    return httpx.Response(404, json={"error": "unknown"})


@pytest.fixture(autouse=True)
def _llama_state(monkeypatch):
    monkeypatch.setattr(defillama, "_directory_cache", None)
    monkeypatch.setattr(defillama, "_ids_cache", {"BTC": "bitcoin", "ETH": "ethereum", "DEAD": "dead-coin"})


@pytest.fixture
def client():
    with httpx.Client(transport=httpx.MockTransport(_handler)) as c:
        yield c


@pytest.mark.parametrize("venue, per_day", [("binance", None), ("coinbase", 20.0), ("kraken", 12.0)])
def test_each_venue_returns_completed_days_only_with_its_quote_volume(client, venue, per_day):
    s = spot_volume.FETCHERS[venue]("BTC", client, TODAY)
    assert (s.state, s.source) == ("ok", spot_volume.STORES[venue])
    assert len(s.points) == DAYS and s.points[-1][0] == TODAY - timedelta(days=1)  # today's partial bar is dropped
    assert all(d < TODAY for d, _ in s.points)
    if per_day is not None:  # coinbase: close * base volume; kraken: vwap * base volume
        assert {v for _, v in s.points} == {per_day}
    else:  # binance: the venue's own quote volume column
        assert s.points[0][1] == 1000.0


@pytest.mark.parametrize("venue", ["binance", "coinbase", "kraken"])
def test_unlisted_coin_is_not_listed_not_an_outage(client, venue):
    s = spot_volume.FETCHERS[venue]("NOPE", client, TODAY)
    assert (s.state, s.reason, s.points) == ("unavailable", "not listed", [])


@pytest.mark.parametrize("venue", ["binance", "coinbase", "kraken"])
def test_provider_failure_is_unavailable_with_class_and_status_never_the_message(venue):
    def boom(request):
        return httpx.Response(451, text="secret-token-in-body")

    with httpx.Client(transport=httpx.MockTransport(boom)) as c:
        s = spot_volume.FETCHERS[venue]("BTC", c, TODAY)
    assert s.state == "unavailable" and s.reason.startswith("fetch-failed: HTTPStatusError HTTP 451")
    assert "secret" not in s.reason


def test_short_history_is_insufficient_not_ok(client):
    s = spot_volume._finish("exchange_volume", "BTC", [(TODAY - timedelta(days=k), 1.0) for k in range(1, 11)], TODAY)
    assert (s.state, s.reason) == ("insufficient-history", "10 days")


# ------------------------------------------------------------- refresh pass

def test_pass_writes_every_venue_then_skips_coins_already_current(isolated_cache, client):
    sleeps: list[float] = []
    first = spot_volume_refresh.refresh_once(["BTC", "NOPE"], today=TODAY, client=client, sleep=sleeps.append)
    for venue in ("binance", "coinbase", "kraken", "defillama"):
        assert first[venue] == {"written": DAYS, "ok": 1, "skipped": 0, "fact": 1, "failed": 0}
    assert len(sleeps) == 8  # one paced request per source and coin

    # The stores now read as ok series without any probe record.
    for store_name in ("exchange_volume", "coinbase_volume", "kraken_volume", "defillama"):
        got = registry.read_series(store_name, "BTC", TODAY, probe_path=isolated_cache / "no-probe.json")
        assert got.state == "ok" and len(got.points) == DAYS

    sleeps.clear()
    again = spot_volume_refresh.refresh_once(["BTC", "NOPE"], today=TODAY, client=client, sleep=sleeps.append)
    for venue in ("binance", "coinbase", "kraken", "defillama"):
        assert again[venue]["skipped"] == 1 and again[venue]["written"] == 0
    assert len(sleeps) == 4  # only the unlisted coin is asked again


def test_a_stale_store_is_refetched_and_extended(isolated_cache, client):
    old = [(TODAY - timedelta(days=k), 1.0) for k in range(60, 10, -1)]
    store.write_series(spot_volume.SourceSeries("exchange_volume", "BTC", old), today=TODAY)
    out = spot_volume_refresh.refresh_once(["BTC"], today=TODAY, client=client, sleep=lambda s: None)
    assert out["binance"]["skipped"] == 0 and out["binance"]["ok"] == 1
    points = store.read_points("exchange_volume", "BTC")
    assert points[-1][0] == TODAY - timedelta(days=1) and len(points) == DAYS
    assert dict(points)[TODAY - timedelta(days=60)] == 1.0  # first observation wins: the older value is kept


def test_provider_failures_are_counted_failed_and_stop_event_ends_the_pass(isolated_cache):
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))) as c:
        out = spot_volume_refresh.refresh_once(["BTC", "ETH"], today=TODAY, client=c, sleep=lambda s: None)
        assert all(v["failed"] == 2 and v["ok"] == 0 for v in out.values())
        stop = threading.Event()
        stop.set()
        stopped = spot_volume_refresh.refresh_once(["BTC"], today=TODAY, client=c, sleep=lambda s: None, stopping=stop)
        assert all(sum(v.values()) == 0 for v in stopped.values())


# ------------------------------------------------------------- schedule

def test_next_run_is_the_next_daily_slot_or_an_hour_after_a_failure():
    at = lambda h, m: datetime(2026, 10, 31, h, m, tzinfo=timezone.utc)  # noqa: E731
    assert spot_volume_refresh.next_run_after(at(0, 10), retry=False) == at(0, 40)
    assert spot_volume_refresh.next_run_after(at(0, 41), retry=False) == at(0, 40) + timedelta(days=1)
    assert spot_volume_refresh.next_run_after(at(9, 0), retry=True) == at(10, 0)


def test_worker_pass_reports_retry_only_when_a_venue_failed(isolated_cache):
    now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
    ok = spot_volume_refresh.SpotVolumeWorker(
        clock=lambda: now, sleep=lambda s: None, symbols=lambda: ["BTC"],
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(_handler)))
    assert ok.run_pass() is False and ok.passes == 1

    bad = spot_volume_refresh.SpotVolumeWorker(  # ETH is not stored yet, so it is fetched (and the venue is down)
        clock=lambda: now, sleep=lambda s: None, symbols=lambda: ["ETH"],
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))))
    assert bad.run_pass() is True


def test_env_switches_turn_the_worker_off():
    assert spot_volume_refresh.enabled_from_env({}) is True
    assert spot_volume_refresh.enabled_from_env({"SPOT_VOLUME_REFRESH": "0"}) is False
    assert spot_volume_refresh.enabled_from_env({"SCREENER_REFRESH_WORKER": "0"}) is False


# ------------------------------------------------------------- DefiLlama fees

def test_defillama_picks_the_candidate_with_most_recent_fees_and_remembers_it(isolated_cache, client):
    s = defillama.fetch_series("BTC", client, TODAY)
    assert s.state == "ok" and {v for _, v in s.points} == {7.0} and len(s.points) == DAYS
    assert defillama._read_map()["BTC"] == {"kind": "protocol", "name": "btc-main"}

    # The saved choice is used from now on, even if another candidate would win today.
    defillama._save_choice("BTC", {"kind": "protocol", "name": "btc-old"})
    assert {v for _, v in defillama.fetch_series("BTC", client, TODAY).points} == {1.0}


def test_defillama_matches_a_chain_on_its_gecko_id(isolated_cache, client):
    s = defillama.fetch_series("ETH", client, TODAY)
    assert s.state == "ok" and {v for _, v in s.points} == {50.0}
    assert defillama._read_map()["ETH"] == {"kind": "chain", "name": "Ethereum"}


@pytest.mark.parametrize("sym", ["DEAD", "UNMAPPED"])
def test_defillama_coin_without_fees_is_no_protocol_not_an_outage(isolated_cache, client, sym):
    s = defillama.fetch_series(sym, client, TODAY)
    assert (s.state, s.reason, s.points) == ("unavailable", "no protocol", [])
    assert sym in defillama._read_map()  # remembered: not looked up again until the map is deleted


def test_defillama_outage_is_reported_and_not_remembered(isolated_cache):
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))) as c:
        s = defillama.fetch_series("BTC", c, TODAY)
    assert s.state == "unavailable" and s.reason.startswith("fetch-failed: HTTPStatusError HTTP 503")
    assert "BTC" not in defillama._read_map()
