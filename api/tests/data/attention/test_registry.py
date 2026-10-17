import json
from datetime import timedelta

from api.data.attention import registry, store
from api.data.attention.types import SourceSeries
from .conftest import TODAY


def _store(n, source="wikipedia"):
    pts = [(TODAY - timedelta(days=n - i), float(i)) for i in range(n)]
    store.write_series(SourceSeries(source, "BTC", pts, "ok", ""), today=TODAY)


def test_registry_maps_sources():
    assert set(registry.FETCHERS) == {"wikipedia", "coingecko", "exchange_volume", "hyperliquid_volume", "trends", "reddit", "xsearch"}


def test_not_probed_without_record(attention_cache, tmp_path):
    _store(100)
    p = tmp_path / "probe.json"
    p.write_text("{}")
    s = registry.read_series("wikipedia", "BTC", today=TODAY, probe_path=p)
    assert s.state == "not-probed" and s.points == []


def test_missing_probe_file_is_not_probed(attention_cache, tmp_path):
    s = registry.read_series("wikipedia", "BTC", today=TODAY, probe_path=tmp_path / "none.json")
    assert s.state == "not-probed"


def test_probed_reads_ok(attention_cache, tmp_path):
    _store(100)
    p = tmp_path / "probe.json"
    p.write_text(json.dumps({"wikipedia": {"ok": True}}))
    s = registry.read_series("wikipedia", "BTC", today=TODAY, probe_path=p)
    assert s.state == "ok" and len(s.points) == 100


def test_probed_short_history(attention_cache, tmp_path):
    _store(10)
    p = tmp_path / "probe.json"
    p.write_text(json.dumps({"wikipedia": {"ok": True}}))
    assert registry.read_series("wikipedia", "BTC", today=TODAY, probe_path=p).state == "insufficient-history"


def test_probed_no_data_unavailable(attention_cache, tmp_path):
    p = tmp_path / "probe.json"
    p.write_text(json.dumps({"wikipedia": {"ok": True}}))
    assert registry.read_series("wikipedia", "ZZZ", today=TODAY, probe_path=p).state == "unavailable"


def test_shipped_probe_records_empty():
    assert registry.load_probe_records() == {}


def test_reader_makes_no_network(attention_cache, tmp_path, monkeypatch):
    import httpx
    monkeypatch.setattr(httpx.Client, "send", lambda *a, **k: (_ for _ in ()).throw(AssertionError("net")))
    p = tmp_path / "probe.json"
    p.write_text("{}")
    registry.read_series("wikipedia", "BTC", today=TODAY, probe_path=p)
