import json
import re
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


def test_empty_records_mean_not_probed_for_every_source(attention_cache, tmp_path):
    _store(100)
    p = tmp_path / "probe.json"
    p.write_text("{}")
    for source in registry.FETCHERS:
        assert registry.read_series(source, "BTC", today=TODAY, probe_path=p).state == "not-probed"


def test_ok_record_makes_only_that_source_usable(attention_cache, tmp_path):
    _store(100)
    p = tmp_path / "probe.json"
    p.write_text(json.dumps({"wikipedia": {"state": "ok"}}))
    assert registry.read_series("wikipedia", "BTC", today=TODAY, probe_path=p).state == "ok"
    for source in set(registry.FETCHERS) - {"wikipedia"}:
        assert registry.read_series(source, "BTC", today=TODAY, probe_path=p).state == "not-probed"


def test_unreadable_or_non_dict_records_are_not_probed(attention_cache, tmp_path):
    _store(100)
    p = tmp_path / "probe.json"
    for text in ("not json", "[]", '"x"'):
        p.write_text(text)
        assert registry.load_probe_records(p) == {}
        assert registry.read_series("wikipedia", "BTC", today=TODAY, probe_path=p).state == "not-probed"


def test_shipped_probe_records_contract():
    """Stable contract on the committed file; the daily job rewrites its contents, so never assert them."""
    states = {"ok", "unavailable", "insufficient-history", "no-article", "capped"}
    data = json.loads(registry.PROBE_RECORDS_PATH.read_text())
    assert isinstance(data, dict)
    for name, rec in data.items():
        assert name in registry.FETCHERS, name
        assert isinstance(rec, dict), name
        assert rec["state"] in states, (name, rec)
    text = registry.PROBE_RECORDS_PATH.read_text()
    assert not re.search(r"(?i)secret|token|api[_-]?key|bearer|password", text)
    assert not re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", text)


def test_reader_makes_no_network(attention_cache, tmp_path, monkeypatch):
    import httpx
    monkeypatch.setattr(httpx.Client, "send", lambda *a, **k: (_ for _ in ()).throw(AssertionError("net")))
    p = tmp_path / "probe.json"
    p.write_text("{}")
    registry.read_series("wikipedia", "BTC", today=TODAY, probe_path=p)
