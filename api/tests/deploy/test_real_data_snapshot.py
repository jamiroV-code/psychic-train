from __future__ import annotations


from api.tests.deploy import conftest as deploy_conftest


def test_snapshot_tracks_real_data_except_exact_collector_heartbeat(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    heartbeat = cache_dir / "attention" / "_pc_state" / "collector_heartbeat.json"
    other_heartbeat = cache_dir / "other" / "collector_heartbeat.json"
    other_cache_file = cache_dir / "prices.parquet"
    watchlist = tmp_path / "watchlist.json"
    for path, value in (
        (heartbeat, b'{"beat":1}'),
        (other_heartbeat, b'{"beat":1}'),
        (other_cache_file, b"cache-one"),
        (watchlist, b'{"coins":["BTC"]}'),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)

    monkeypatch.setattr(deploy_conftest, "REAL_CACHE_DIR", cache_dir)
    monkeypatch.setattr(deploy_conftest, "REAL_WATCHLIST", watchlist)

    first = deploy_conftest.snapshot_real_data()
    assert str(heartbeat) not in first
    assert str(other_heartbeat) in first
    assert str(other_cache_file) in first
    assert str(watchlist) in first

    heartbeat.write_bytes(b'{"beat":2, "updated":true}')
    assert deploy_conftest.snapshot_real_data() == first

    other_cache_file.write_bytes(b"cache-two-is-different")
    second = deploy_conftest.snapshot_real_data()
    assert second != first
    assert second[str(other_cache_file)] != first[str(other_cache_file)]

    watchlist.write_bytes(b'{"coins":["BTC","ETH"]}')
    third = deploy_conftest.snapshot_real_data()
    assert third != second
    assert third[str(watchlist)] != second[str(watchlist)]
