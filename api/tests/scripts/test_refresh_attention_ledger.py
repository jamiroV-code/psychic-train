"""T223 O1: the `ledger` step of refresh_attention (seeding, advance, symbol cap, exit code, fixed-token stdout).
No network: every client is a MockTransport that fails on any request the ledger step must not make."""
from __future__ import annotations

import json
import socket
from datetime import timedelta

import httpx
import pytest

from api.data.attention import onboarding_store as ob
from api.data.attention import universe_store
from api.scripts import refresh_attention as ra
from api.tests.data.attention.conftest import TODAY


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the ledger step must not reach the network")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", boom)
    monkeypatch.setattr(socket.socket, "connect", boom)


def rows(placed: dict[str, int] | None = None, n: int = 120) -> list[dict]:
    order = [f"fill-{i}" for i in range(1, n + 1)]
    for cid, rank in (placed or {}).items():
        order.insert(rank - 1, cid)
    order = order[:n]
    return [{"id": c, "symbol": c.upper().replace("-", "_"), "name": c, "market_cap": 10_000 - i,
             "volume_24h": 1, "rank": i + 1} for i, c in enumerate(order)]


def fail_net(r):
    raise AssertionError("no network")


def run(argv, day=TODAY):
    c = httpx.Client(transport=httpx.MockTransport(fail_net))
    return ra.main(argv, client=c, today=day, sleep=lambda x: None)


def write(day, placed=None, n=120):
    universe_store.write_snapshot(day.isoformat(), rows(placed, n))


def test_first_run_seeds_rank_1_to_100_only(isolated_cache, capsys):
    write(TODAY, {"edge": 110})
    assert run(["--sources", "ledger"]) == 0
    led, st = ob.read_ledger()
    assert st == "ok" and len(led["coins"]) == 100 and "edge" not in led["coins"]
    assert {(e["state"], e["class"], e["class_source"]) for e in led["coins"].values()} == {
        ("member", "normal", "owner")}
    out = capsys.readouterr().out
    assert "ledger: ok seeded 100" in out
    assert ob.read_log(TODAY.isoformat())["entries"][0]["action"] == "seeded"


def test_present_ledger_is_advanced_not_reseeded(isolated_cache, capsys):
    write(TODAY - timedelta(days=1))
    run(["--sources", "ledger"], TODAY - timedelta(days=1))
    capsys.readouterr()
    write(TODAY, {"newc": 30})
    assert run(["--sources", "ledger"]) == 0
    led, _ = ob.read_ledger()
    assert led["coins"]["newc"]["state"] == "watching" and led["last_advanced_date"] == TODAY.isoformat()
    out = capsys.readouterr()
    assert "ledger: ok advanced, entered 1" in out.out
    assert "newc" not in out.out.lower() + out.err.lower()


def test_same_day_rerun_counts_once(isolated_cache):
    write(TODAY - timedelta(days=1))
    run(["--sources", "ledger"], TODAY - timedelta(days=1))
    write(TODAY, {"newc": 30})
    run(["--sources", "ledger"])
    before = ob.ledger_path().read_bytes()
    run(["--sources", "ledger"])
    assert ob.ledger_path().read_bytes() == before


def test_corrupt_ledger_is_refused_and_kept(isolated_cache, capsys):
    write(TODAY)
    ob.ledger_path().parent.mkdir(parents=True, exist_ok=True)
    ob.ledger_path().write_text("{broken")
    assert run(["--sources", "ledger"]) == 0
    assert ob.ledger_path().read_text() == "{broken"
    assert "ledger: unavailable corrupt ledger" in capsys.readouterr().out


def test_lost_ledger_reseeds_once_with_a_loud_line(isolated_cache, capsys):
    write(TODAY - timedelta(days=1))
    run(["--sources", "ledger"], TODAY - timedelta(days=1))
    ob.ledger_path().unlink()
    write(TODAY)
    run(["--sources", "ledger"])
    cap = capsys.readouterr()
    assert "ledger: warning re-seeded, probation progress lost" in cap.err
    assert ob.read_ledger()[1] == "ok"


def test_stale_snapshot_is_skipped(isolated_cache, capsys):
    write(TODAY - timedelta(days=1))
    assert run(["--sources", "ledger"]) == 0
    assert ob.read_ledger() == (None, "absent")
    assert "ledger: skipped, stale snapshot" in capsys.readouterr().out


def test_short_snapshot_is_unavailable(isolated_cache, capsys):
    write(TODAY, n=100)
    run(["--sources", "ledger"])
    assert ob.read_ledger() == (None, "absent")
    assert "ledger: unavailable short snapshot" in capsys.readouterr().out


def test_no_snapshot_is_unavailable(isolated_cache, capsys):
    run(["--sources", "ledger"])
    assert "ledger: unavailable no snapshot" in capsys.readouterr().out


def test_bad_settings_skip_the_step(isolated_cache, capsys, tmp_path, monkeypatch):
    from api.data.attention import onboarding_settings
    bad = tmp_path / "s.json"
    bad.write_text("{}")
    monkeypatch.setattr(onboarding_settings, "SETTINGS_PATH", bad)
    write(TODAY)
    run(["--sources", "ledger"])
    assert ob.read_ledger() == (None, "absent")
    assert "ledger: unavailable settings" in capsys.readouterr().out


def test_ledger_never_decides_the_exit_code(isolated_cache, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("ledger broke")
    monkeypatch.setitem(ra.RUNNERS, "ledger", boom)
    assert run(["--sources", "ledger"]) == 0
    write(TODAY)
    assert run(["--sources", "ledger,universe"]) == 1   # universe errors (no network): the ledger adds nothing


def test_failed_universe_step_skips_the_ledger(isolated_cache, capsys):
    write(TODAY - timedelta(days=1))
    assert run(["--sources", "universe,ledger"]) == 1
    assert ob.read_ledger() == (None, "absent")
    assert "ledger: skipped, universe step failed" in capsys.readouterr().out


def test_ledger_runs_after_universe_and_before_signals():
    d = ra.DEFAULT_SOURCES
    assert d.index("universe") < d.index("ledger") < d.index("signals")


def test_dry_run_writes_no_ledger(isolated_cache, capsys):
    write(TODAY)
    assert run(["--dry-run", "--sources", "ledger"]) == 0
    assert ob.read_ledger() == (None, "absent")
    assert "ledger: dry run" in capsys.readouterr().out


def test_runner_symbols_are_capped_at_top_100_plus_band_members(isolated_cache):
    write(TODAY - timedelta(days=1), {"bandm": 50})
    run(["--sources", "ledger"], TODAY - timedelta(days=1))      # seeds bandm as a member
    write(TODAY, {"bandm": 115})
    run(["--sources", "ledger"])
    syms = ra._symbols(None)
    assert len(syms) == 101 and "BANDM" in syms
    assert len([r for r in ra._universe_rows()]) == 101


def test_runner_symbols_without_a_ledger_are_the_top_100(isolated_cache):
    write(TODAY)
    assert len(ra._symbols(None)) == 100


def test_old_rankless_snapshot_keeps_every_row(isolated_cache):
    universe_store.write_snapshot(TODAY.isoformat(), [{"id": "a", "symbol": "A", "market_cap": 1}])
    assert ra._symbols(None) == ["A"]
