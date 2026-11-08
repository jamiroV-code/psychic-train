"""Synthetic daily cycle; only loopback services and the spawned fake browser, never installed Edge or live accounts.

The doctor's real self-test runner is driven by `python -m api.tests.cycle.acceptance` (C13), not from pytest.
"""
from api.tests.cycle.acceptance import SCENARIOS, run_cycle


def test_daily_cycle(tmp_path, monkeypatch):
    results = run_cycle(tmp_path, monkeypatch, nested=True)
    assert set(results) == set(SCENARIOS)
    failed = {k: v for k, v in results.items() if v["state"] != "passed"}
    assert failed == {}
