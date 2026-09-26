"""chain-growth RFC-3: nightly snapshot script (fake adapters, stubbed sleep, no network)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from api.data import cache, growthepie_adapter, l2beat_adapter
from api.data.growthepie_adapter import GrowthepieSeries
from api.data.l2beat_adapter import ActivityPoint, L2beatActivity
from api.scripts import snapshot_chain_growth as snap

NOW = datetime(2026, 9, 25, 22, 0, tzinfo=timezone.utc)
PTS = [("2026-09-23", 10.0), ("2026-09-24", 11.0)]


class Calls:
    def __init__(self):
        self.growthepie: list[tuple[str, str]] = []
        self.l2beat: list[str] = []
        self.sleeps: list[float] = []


@pytest.fixture
def fakes(monkeypatch):
    calls = Calls()
    behaviour: dict[str, str] = {}  # growthepie source_key -> "ok" | "raise" | "unavailable"

    def fake_gp(chain_key, metric, client=None):
        calls.growthepie.append((chain_key, metric))
        mode = behaviour.get(chain_key, "ok")
        if mode == "raise":
            raise RuntimeError("boom")
        if mode == "unavailable":
            return GrowthepieSeries(chain_key, metric, "unavailable", reason="http-429")
        return GrowthepieSeries(chain_key, metric, "ok", points=list(PTS))

    def fake_l2(project, range_="max", client=None):
        calls.l2beat.append(project)
        if behaviour.get("l2beat") == "unavailable":
            return L2beatActivity(project, "unavailable", range_, reason="http-500")
        return L2beatActivity(project, "ok", range_, points=[ActivityPoint(d, v, None) for d, v in PTS])

    monkeypatch.setattr(growthepie_adapter, "fetch_chain_metric", fake_gp)
    monkeypatch.setattr(l2beat_adapter, "fetch_activity", fake_l2)
    return calls, behaviour


def _run(calls, **kw):
    return snap.run_snapshot(now=NOW, sleep=calls.sleeps.append, **kw)


def _files(root):
    return sorted(p.relative_to(root / "onchain").as_posix() for p in (root / "onchain").rglob("*.parquet"))


def test_full_run_writes_live_chains_and_skips_none_sources(isolated_cache, fakes):
    calls, _ = fakes
    summaries, skipped = _run(calls)
    files = _files(isolated_cache)
    assert "growthepie/base/active_addresses.parquet" in files
    assert "l2beat/base/transactions.parquet" in files
    assert "growthepie/polygon/transactions.parquet" in files
    for none_chain in ("solana", "bnb", "tron"):
        assert not any(f.split("/")[1] == none_chain for f in files)
        assert not any(k == none_chain for k, _ in calls.growthepie)
        assert any(line.startswith(f"{none_chain}/") and "skipped" in line for line in skipped)
    assert all(s.ok for s in summaries) and snap.exit_code(summaries) == 0


def test_spacing_between_every_request(isolated_cache, fakes):
    calls, _ = fakes
    _run(calls)
    n_requests = len(calls.growthepie) + len(calls.l2beat)
    assert n_requests == 16
    assert calls.sleeps == [snap.REQUEST_SPACING_SECONDS] * (n_requests - 1)


def test_partial_failure_leaves_others_written(isolated_cache, fakes, tmp_path_factory, monkeypatch):
    calls, behaviour = fakes
    behaviour["arbitrum"] = "raise"
    behaviour["optimism"] = "unavailable"
    summaries, _ = _run(calls)
    by_key = {s.key: s for s in summaries}
    assert not by_key["growthepie/arbitrum/active_addresses"].ok
    assert "boom" in by_key["growthepie/arbitrum/active_addresses"].reason
    assert by_key["growthepie/optimism/transactions"].reason == "http-429"
    assert not (isolated_cache / "onchain" / "growthepie" / "arbitrum").exists()
    assert not (isolated_cache / "onchain" / "growthepie" / "optimism").exists()
    full = cache.read_onchain_series("growthepie", "base", "active_addresses")

    # Base's series equals a solo run.
    solo_root = tmp_path_factory.mktemp("solo")
    monkeypatch.setattr(cache, "CACHE_ROOT", solo_root)
    _run(Calls(), only={"base"})
    solo = cache.read_onchain_series("growthepie", "base", "active_addresses")
    assert full.equals(solo)
    assert snap.exit_code(summaries) == 0


def test_all_unavailable_exit_2(isolated_cache, fakes):
    calls, behaviour = fakes
    for key in ("ethereum", "base", "arbitrum", "optimism", "polygon_pos", "robinhood"):
        behaviour[key] = "unavailable"
    behaviour["l2beat"] = "unavailable"
    summaries, _ = _run(calls)
    assert summaries and not any(s.ok for s in summaries)
    assert snap.exit_code(summaries) == 2
    assert _files(isolated_cache) == []


def test_only_flag_limits_chains(isolated_cache, fakes):
    calls, _ = fakes
    _run(calls, only={"ethereum"})
    assert {k for k, _ in calls.growthepie} == {"ethereum"} and calls.l2beat == []


def test_dry_run_writes_nothing_and_restores_root(isolated_cache, fakes, capsys):
    calls, _ = fakes
    assert snap.main(["--dry-run"], sleep=calls.sleeps.append) == 0
    assert cache.CACHE_ROOT == isolated_cache
    assert not (isolated_cache / "onchain").exists()
    assert "[dry-run] growthepie/base/active_addresses: ok" in capsys.readouterr().out


def test_verify_only_makes_no_adapter_calls(isolated_cache, fakes, capsys):
    calls, _ = fakes
    assert snap.main(["--verify-only"]) == 0
    assert calls.growthepie == [] and calls.l2beat == []
    assert "no chain-growth archive rows" in capsys.readouterr().out
    _run(calls)
    calls.growthepie.clear()
    snap.main(["--verify-only"])
    out = capsys.readouterr().out
    assert "growthepie/base/active_addresses: rows=2 first=2026-09-23 last=2026-09-24" in out
    assert calls.growthepie == []


def test_summary_line_includes_history_depth(isolated_cache, fakes, capsys):
    calls, _ = fakes
    snap.main(["--only", "base"], sleep=calls.sleeps.append)
    out = capsys.readouterr().out
    assert "growthepie/base/active_addresses: ok inserted=2 revised=0 drift=0 rows=2 first=2026-09-23 last=2026-09-24" in out


def test_second_run_is_no_change(isolated_cache, fakes):
    calls, _ = fakes
    _run(calls, only={"base"})
    summaries, _ = _run(calls, only={"base"})
    assert all(s.inserted == 0 and s.revised == 0 for s in summaries)


def test_window_days_flag_validated(isolated_cache, fakes):
    with pytest.raises(SystemExit):
        snap.main(["--window-days", "-1"])
