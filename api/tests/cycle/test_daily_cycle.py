"""Synthetic daily cycle; only loopback services, never installed Edge or live accounts."""
from api.tests.cycle.world import CycleWorld


def test_daily_cycle(tmp_path, monkeypatch):
    with CycleWorld(tmp_path, monkeypatch) as world:
        world.run()
        assert set(world.results) == {f"C{i}" for i in range(1, 15)}
        assert all(row["state"] == "passed" for row in world.results.values())
