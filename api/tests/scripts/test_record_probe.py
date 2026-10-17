import hashlib
import json
from datetime import timedelta
from pathlib import Path

import pytest

from api.data import cache
from api.data.attention import registry, store
from api.data.attention.types import SourceSeries
from api.scripts import record_probe
from api.tests.data.attention.conftest import TODAY


def _fill(source, symbol, days, end=TODAY - timedelta(days=1)):
    pts = [(end - timedelta(days=i), float(i + 1)) for i in range(days)]
    store.write_series(SourceSeries(source, symbol, pts, "ok"), today=TODAY)


@pytest.fixture
def rec(tmp_path):
    return tmp_path / "probe_records.json"


def _run(rec, *args):
    return record_probe.main([*args], records_path=rec, today=TODAY)


def test_ok_when_a_coin_has_90_completed_days(isolated_cache, rec):
    _fill("wikipedia", "BTC", 95)
    _fill("wikipedia", "ETH", 10)
    assert _run(rec, "--sources", "wikipedia", "--symbols", "BTC,ETH") == 0
    r = json.loads(rec.read_text())["wikipedia"]
    assert r["state"] == "ok" and r["coins_ok"] == 1 and r["coins_checked"] == 2 and r["max_days"] == 95
    assert r["as_of"] == TODAY.isoformat()
    assert registry.read_series("wikipedia", "BTC", probe_path=rec).state == "ok"


def test_insufficient_history_and_unavailable(isolated_cache, rec):
    _fill("coingecko", "BTC", 20)
    assert _run(rec, "--sources", "coingecko,trends", "--symbols", "BTC") == 0
    d = json.loads(rec.read_text())
    assert d["coingecko"]["state"] == "insufficient-history"
    assert d["trends"]["state"] == "unavailable" and d["trends"]["max_days"] == 0


def test_today_is_not_a_completed_day(isolated_cache, rec):
    path = store.store_path("wikipedia", "BTC")
    path.parent.mkdir(parents=True, exist_ok=True)
    import pandas as pd
    days = [TODAY - timedelta(days=i) for i in range(95)]  # includes today
    cache._atomic_to_parquet(pd.DataFrame({"date": pd.to_datetime(days), "value": 1.0}), path)
    _run(rec, "--sources", "wikipedia", "--symbols", "BTC")
    assert json.loads(rec.read_text())["wikipedia"]["max_days"] == 94


def test_state_override_and_validation(isolated_cache, rec, capsys):
    assert _run(rec, "--sources", "wikipedia", "--symbols", "BTC", "--state", "xsearch=capped") == 0
    assert json.loads(rec.read_text())["xsearch"]["state"] == "capped"
    assert _run(rec, "--state", "xsearch=bogus") == 1
    assert _run(rec, "--sources", "nope") == 1
    assert json.loads(rec.read_text())["xsearch"]["state"] == "capped"


def test_not_probed_override_removes_record(isolated_cache, rec):
    rec.write_text(json.dumps({"reddit": {"state": "unavailable"}}))
    assert _run(rec, "--sources", "wikipedia", "--symbols", "BTC", "--state", "reddit=not-probed") == 0
    assert "reddit" not in json.loads(rec.read_text())


def test_existing_records_are_kept(isolated_cache, rec):
    rec.write_text(json.dumps({"reddit": {"state": "unavailable"}}))
    _fill("wikipedia", "BTC", 95)
    _run(rec, "--sources", "wikipedia", "--symbols", "BTC")
    d = json.loads(rec.read_text())
    assert d["reddit"] == {"state": "unavailable"} and d["wikipedia"]["state"] == "ok"


def test_dry_run_writes_nothing(isolated_cache, rec, capsys):
    _fill("wikipedia", "BTC", 95)
    assert _run(rec, "--sources", "wikipedia", "--symbols", "BTC", "--dry-run") == 0
    assert not rec.exists()
    assert "dry run" in capsys.readouterr().out


def test_no_network_secrets_or_leftovers(isolated_cache, rec, monkeypatch, capsys):
    import httpx
    monkeypatch.setenv("X_BEARER_TOKEN", "SECRET-TOKEN-123")

    def boom(*a, **k):
        raise AssertionError("network")
    monkeypatch.setattr(httpx.Client, "send", boom)
    _fill("wikipedia", "BTC", 95)
    _run(rec, "--sources", "wikipedia", "--symbols", "BTC")
    out = capsys.readouterr()
    assert "SECRET" not in rec.read_text() + out.out + out.err
    assert [p.name for p in rec.parent.iterdir()] == [rec.name]


def test_summary_lines(isolated_cache, rec, capsys):
    _fill("wikipedia", "BTC", 95)
    _run(rec, "--sources", "wikipedia", "--symbols", "BTC")
    assert "wikipedia: ok (1/1 coins with 90+ days, max 95 days)" in capsys.readouterr().out


def test_real_cache_and_real_records_untouched(isolated_cache, rec):
    def snap():
        h = hashlib.sha256()
        for root in (Path(cache.DEFAULT_CACHE_ROOT), registry.PROBE_RECORDS_PATH):
            for p in sorted(root.rglob("*")) if root.is_dir() else [root]:
                if p.is_file():
                    h.update(str(p).encode() + p.read_bytes())
        return h.hexdigest()
    before = snap()
    _fill("wikipedia", "BTC", 95)
    _run(rec, "--sources", "wikipedia", "--symbols", "BTC")
    assert snap() == before
