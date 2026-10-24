import json

from api.data.attention import universe_store as us


def _rows(n):
    return [{"id": f"c{n}", "symbol": f"C{n}", "market_cap": n, "volume_24h": n}]


def test_round_trip_and_path(isolated_cache):
    us.write_snapshot("2026-10-01", _rows(1))
    snap = us.read_latest()
    assert snap == {"date": "2026-10-01", "coins": _rows(1)}
    on_disk = json.loads((isolated_cache / "attention" / "universe.json").read_text())
    assert list(on_disk) == ["snapshots"]


def test_read_latest_missing_and_corrupt(isolated_cache):
    assert us.read_latest() is None
    (isolated_cache / "attention").mkdir()
    (isolated_cache / "attention" / "universe.json").write_text("{nope")
    assert us.read_latest() is None


def test_same_date_replaced(isolated_cache):
    us.write_snapshot("2026-10-01", _rows(1))
    us.write_snapshot("2026-10-01", _rows(2))
    on_disk = json.loads((isolated_cache / "attention" / "universe.json").read_text())
    assert len(on_disk["snapshots"]) == 1
    assert us.read_latest()["coins"] == _rows(2)


def test_fifteenth_drops_oldest(isolated_cache):
    for d in range(1, 16):
        us.write_snapshot(f"2026-10-{d:02d}", _rows(d))
    snaps = json.loads((isolated_cache / "attention" / "universe.json").read_text())["snapshots"]
    assert [s["date"] for s in snaps] == [f"2026-10-{d:02d}" for d in range(2, 16)]
    assert us.read_latest()["date"] == "2026-10-15"
