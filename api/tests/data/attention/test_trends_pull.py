"""T100b per-pull archive (point-in-time Trends values) and an end-to-end fake pull. No network."""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from pathlib import Path

import httpx
import pytest

from api.data.attention import store, trends_keywords
from api.data.attention.types import SourceSeries
from api.scripts import refresh_attention
from api.tests import trends_fixtures as fx

D = fx.TODAY
SIGNALS = Path(__file__).resolve().parents[3] / "data" / "cache" / "attention" / "signals"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    fx.block_network(monkeypatch)


def _pts(n, value=1.0, end=D - timedelta(days=1)):
    return [(end - timedelta(days=n - 1 - i), float(value) + i % 3) for i in range(n)]


def _s(symbol, pts, state="ok", reason=""):
    return SourceSeries("trends", symbol, pts, state, reason)


def test_archive_written_per_pull_date(isolated_cache):
    assert store.write_pull_archive("trends", D, [_s("AAVE", _pts(100))]) == 100
    store.write_pull_archive("trends", D + timedelta(days=1), [_s("AAVE", _pts(100, 5.0, end=D))])
    path = store.pull_archive_path("trends", D)
    assert path == isolated_cache / "attention" / "trends_pulls" / f"{D.isoformat()}.parquet"
    assert sorted(p.name for p in path.parent.iterdir()) == [f"{D.isoformat()}.parquet",
                                                             f"{(D + timedelta(days=1)).isoformat()}.parquet"]


def test_archive_second_run_adds_missing_symbols_only(isolated_cache):
    store.write_pull_archive("trends", D, [_s("AAVE", _pts(100, 1.0))])
    added = store.write_pull_archive("trends", D, [_s("AAVE", _pts(100, 9.0)), _s("INJ", _pts(95, 4.0))])
    got = store.read_pull_archive("trends", D)
    assert added == 95 and got["AAVE"] == _pts(100, 1.0) and got["INJ"] == _pts(95, 4.0)
    assert store.write_pull_archive("trends", D, [_s("AAVE", _pts(100, 7.0))]) == 0


def test_archive_excludes_missing_coins(isolated_cache):
    series = [_s("AAVE", _pts(100)), _s("INJ", [], "unavailable", "too-little-interest"),
              _s("ARB", _pts(50), "insufficient-history", "50 days"), _s("SOL", [], "capped", "rate-limited")]
    store.write_pull_archive("trends", D, series)
    assert list(store.read_pull_archive("trends", D)) == ["AAVE"]
    assert store.write_pull_archive("trends", D + timedelta(days=1), series[1:]) == 0
    assert not store.pull_archive_path("trends", D + timedelta(days=1)).exists()


def test_archive_roundtrip_values(isolated_cache):
    pts = [(D - timedelta(days=3), 0.0), (D - timedelta(days=2), 37.5), (D - timedelta(days=1), 100.0)]
    store.write_pull_archive("trends", D, [_s("ZEC", list(reversed(pts)) + [(D, 4.0)])])
    assert store.read_pull_archive("trends", D) == {"ZEC": pts}  # sorted; the pull day itself is never kept
    assert store.read_pull_archive("trends", D - timedelta(days=9)) == {}


def _main(monkeypatch, today, frame):
    kw = store.cache.CACHE_ROOT / "kw.json"
    kw.write_text(json.dumps({"_anchor": {"term": "Bitcoin", "label": "Bitcoin"},
                              "AAVE": {"term": "Aave", "label": "Aave"}}))
    monkeypatch.setattr(trends_keywords, "KEYWORDS_PATH", kw)
    client = fx.FakeTrendReq(frames=[frame])
    monkeypatch.setattr(refresh_attention, "TRENDREQ_FACTORY", lambda: client)
    monkeypatch.setattr(refresh_attention, "_jitter", lambda: 0.0)
    c = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    return refresh_attention.main(["--sources", "trends", "--symbols", "AAVE"], client=c, today=today,
                                  sleep=lambda s: None)


def test_replace_then_archive_end_to_end_two_days(isolated_cache, monkeypatch):
    d2 = D + timedelta(days=1)
    v1 = [10 + i % 40 for i in range(100)]
    v2 = [2 * v for v in v1[1:]] + [77]  # day 2 pull: one day later, on another scale
    assert _main(monkeypatch, D, fx.daily_frame(["Aave"], 100, end=D - timedelta(days=1), values={"Aave": v1})) == 0
    assert _main(monkeypatch, d2, fx.daily_frame(["Aave"], 100, end=d2 - timedelta(days=1), values={"Aave": v2})) == 0
    stored = store.read_points("trends", "AAVE")
    assert [v for _, v in stored] == [float(v) for v in v2] and stored[-1][0] == D
    a1, a2 = store.read_pull_archive("trends", D)["AAVE"], store.read_pull_archive("trends", d2)["AAVE"]
    assert [v for _, v in a1] == [float(v) for v in v1] and a1[-1][0] == D - timedelta(days=1)
    assert a2 == stored


def _hashes():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(SIGNALS.glob("*"))}


def test_frozen_signals_files_untouched(isolated_cache, monkeypatch):
    before = _hashes()
    assert before  # the frozen snapshots exist in the repo
    _main(monkeypatch, D, fx.daily_frame(["Aave"], 100))
    assert _hashes() == before


def _chart(day):
    """What the history chart (discovery_history) sees for Trends on a past `day`: the pull of day+1, gated."""
    from api.analytics.attention import discovery, discovery_history
    s = discovery_history._TrendsPulls(True, 90).at("AAVE", day)
    return discovery._source_change(s.points, day, 7, 7, 3) if s.state == "ok" else None


def _live(day):
    """The old chart path (before T175): the live store, gated per day."""
    from api.analytics.attention import discovery, discovery_history
    s = discovery_history._Stored("trends", "AAVE", True, 90).at(day)
    return discovery._source_change(s.points, day, 7, 7, 3) if s.state == "ok" else None
