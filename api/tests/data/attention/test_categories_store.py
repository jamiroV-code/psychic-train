import json

from api.data.attention import categories_store as cs


def _rows(n):
    return [{"id": f"c{n}", "name": f"C{n}", "symbols": [f"S{n}"]}]


def test_round_trip_and_path(isolated_cache):
    cs.write_snapshot("2026-10-01", _rows(1))
    assert cs.read_latest() == {"date": "2026-10-01", "categories": _rows(1)}
    on_disk = json.loads((isolated_cache / "attention" / "categories.json").read_text())
    assert list(on_disk) == ["snapshots"]


def test_read_latest_missing_and_corrupt(isolated_cache):
    assert cs.read_latest() is None
    (isolated_cache / "attention").mkdir()
    (isolated_cache / "attention" / "categories.json").write_text("{nope")
    assert cs.read_latest() is None


def test_same_date_replaced(isolated_cache):
    cs.write_snapshot("2026-10-01", _rows(1))
    cs.write_snapshot("2026-10-01", _rows(2))
    assert cs.read_latest()["categories"] == _rows(2)


def test_fifteenth_drops_oldest(isolated_cache):
    for d in range(1, 16):
        cs.write_snapshot(f"2026-10-{d:02d}", _rows(d))
    snaps = json.loads((isolated_cache / "attention" / "categories.json").read_text())["snapshots"]
    assert [s["date"] for s in snaps] == [f"2026-10-{d:02d}" for d in range(2, 16)]


def test_path_follows_cache_root_at_call_time(isolated_cache):
    assert cs._path() == isolated_cache / "attention" / "categories.json"
