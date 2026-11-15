"""Stage 3: collector program. Network is replaced by httpx.MockTransport; the clock is pinned.

Paths are resolved inside each helper, never at import time: the autouse isolation
fixture in conftest.py sets the cache roots per test. Lock and retry waits run on a
fake clock so no test sleeps for real.
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

from api.data.perp import hl_snapshot as hs
from api.data.perp import textlog
from api.data.perp.paths import hl_snapshot_path, perp_root
from api.scripts import collect_perp

FIXTURE = Path(__file__).parent / "fixtures" / "hl_snapshot.json"
NOW = dt.datetime(2026, 11, 14, 23, 30, 0, tzinfo=dt.timezone.utc)
MONTH = "2026-11"


class FakeClock:
    """Stands in for the `time` module: monotonic and sleep advance together."""

    def __init__(self) -> None:
        self.now = 0.0
        self.wall = time.time()

    def monotonic(self) -> float:
        return self.now

    def time(self) -> float:
        return self.wall + self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def _month_file(coin: str) -> Path:
    return hl_snapshot_path(coin, MONTH)


def _sidecar_file() -> Path:
    return perp_root() / "_last_run_hl-snapshot.json"


def _body(name: str = "response") -> list:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))[name]


def _client(body=None, status=200, fail: bool = False) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            raise httpx.ConnectError("network off")
        return httpx.Response(status, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _counting_client(body) -> tuple[httpx.Client, list[int]]:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler)), calls


def _sequence_client(responses: list[tuple[int, object]]) -> httpx.Client:
    seq = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        status, body = seq.pop(0)
        return httpx.Response(status, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _run(args: list[str], client: httpx.Client | None = None) -> int:
    return collect_perp.run(args, client=client, now=NOW)


def _sidecar() -> dict:
    return json.loads(_sidecar_file().read_text(encoding="utf-8"))


def _run_lock_path() -> Path:
    return perp_root() / "_locks" / "hl-snapshot.lock"


def _run_guard_path() -> Path:
    return _run_lock_path().with_name(_run_lock_path().name + ".takeover")


def _plant_fresh_lock(coin: str) -> None:
    path = _month_file(coin)
    path.parent.mkdir(parents=True, exist_ok=True)
    textlog.lock_path(path).write_text(
        json.dumps({"pid": 1, "started_utc": textlog._now_iso(), "token": "other"}),
        encoding="utf-8",
    )


def _plant_stale_lock(coin: str) -> None:
    path = _month_file(coin)
    path.parent.mkdir(parents=True, exist_ok=True)
    old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).isoformat()
    textlog.lock_path(path).write_text(
        json.dumps({"pid": 1, "started_utc": old, "token": "stale"}), encoding="utf-8")


def _plant_stale_run_lock() -> None:
    lock = _run_lock_path()
    lock.parent.mkdir(parents=True, exist_ok=True)
    old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).isoformat()
    lock.write_text(json.dumps({"pid": 1, "started_utc": old, "token": "stale-run"}), encoding="utf-8")


# --- program shape ----------------------------------------------------------

def test_collector_help_runs_from_another_cwd(tmp_path):
    """Launcher-style invocation: absolute script path, cwd outside the repo. No network."""
    script = collect_perp._REPO_ROOT / "api" / "scripts" / "collect_perp.py"
    result = subprocess.run([sys.executable, str(script), "--help"], cwd=tmp_path,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert "--job" in result.stdout


# --- run lock (VA-2, VA-3) ----------------------------------------------------

def test_run_lock_uses_plan_path_and_blocks_second_run_before_fetch(isolated_cache):
    lock = _run_lock_path()
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps({"token": "held", "started_utc": textlog._now_iso()}), encoding="utf-8")
    client, calls = _counting_client(_body())
    assert _run(["--job", "hl-snapshot"], client) == 1
    assert calls == []


def test_stale_run_lock_is_taken_over_and_its_guard_removed(isolated_cache):
    _plant_stale_run_lock()
    client, _ = _counting_client(_body())
    assert _run(["--job", "hl-snapshot"], client) == 0
    assert _month_file("BTC").exists() and _month_file("ETH").exists()
    assert not _run_lock_path().exists()
    assert not _run_guard_path().exists()


def test_replaced_run_token_prevents_coin_writes(isolated_cache, monkeypatch):
    client, _ = _counting_client(_body())

    def replace_after_create(lock):
        if lock == _run_lock_path():
            lock.write_text(json.dumps({"token": "foreign", "started_utc": textlog._now_iso()}), encoding="utf-8")

    monkeypatch.setattr(textlog, "_after_create_hook", replace_after_create)
    assert _run(["--job", "hl-snapshot"], client) == 1
    assert not _month_file("BTC").exists() and not _month_file("ETH").exists()


def test_guard_refusal_records_actionable_path(isolated_cache):
    guard = _run_guard_path()
    guard.parent.mkdir(parents=True, exist_ok=True)
    guard.write_text("", encoding="utf-8")
    client, calls = _counting_client(_body())
    assert _run(["--job", "hl-snapshot"], client) == 1
    side = _sidecar()
    assert calls == []
    assert "guard-present" in side["problems"]
    assert "takeover-guard-left" in side["problems"]
    assert str(guard) in side["lock_guard"]


def test_run_guard_refusal_exit_and_coverage_include_guard_path(isolated_cache, capsys):
    guard = _run_guard_path()
    guard.parent.mkdir(parents=True, exist_ok=True)
    guard.write_text("", encoding="utf-8")
    client, calls = _counting_client(_body())
    assert _run(["--job", "hl-snapshot"], client) == 1
    assert calls == []  # no request was made
    assert not _month_file("BTC").exists() and not _month_file("ETH").exists()
    assert guard.exists()  # the run never removes a guard it did not create
    side = _sidecar()
    assert "guard-present" in side["problems"]
    assert "takeover-guard-left" in side["problems"]
    assert str(guard) in side["lock_guard"]
    collect_perp.coverage_report(1, NOW)
    assert str(guard) in capsys.readouterr().out


def test_lock_create_denied_retries_then_refuses(isolated_cache, monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(textlog, "time", clock)
    attempts: list[int] = []

    def deny(p, data):
        attempts.append(1)
        raise PermissionError("denied")

    monkeypatch.setattr(textlog, "_create_excl", deny)
    assert _run(["--job", "hl-snapshot"], _client(_body())) == 1
    assert "lock-create-denied" in _sidecar()["problems"]
    assert len(attempts) > 1  # the 2-second denial-only retry ran
    assert clock.now >= textlog.ACQUIRE_DENIAL_RETRY_SECONDS


def test_lock_create_denial_that_clears_within_deadline_still_writes(isolated_cache, monkeypatch):
    monkeypatch.setattr(textlog, "time", FakeClock())
    real_create = textlog._create_excl
    denied = {"n": 0}

    def flaky(p, data):
        if denied["n"] < 2:
            denied["n"] += 1
            raise PermissionError("denied")
        real_create(p, data)

    monkeypatch.setattr(textlog, "_create_excl", flaky)
    assert _run(["--job", "hl-snapshot"], _client(_body())) == 0
    assert _month_file("BTC").exists() and _month_file("ETH").exists()


# --- fetch retry, receipt stamp (VA-3) ---------------------------------------

def test_recovered_503_then_200_is_clean_exit_0(isolated_cache, monkeypatch):
    monkeypatch.setattr(hs, "time", FakeClock())
    client = _sequence_client([(503, None), (200, _body())])
    assert _run(["--job", "hl-snapshot"], client) == 0
    assert _sidecar()["problems"] == []


def test_persistent_503_is_exit_1_with_the_status_recorded(isolated_cache, monkeypatch):
    monkeypatch.setattr(hs, "time", FakeClock())
    client = _sequence_client([(503, None)] * hs.MAX_RETRIES)
    assert _run(["--job", "hl-snapshot"], client) == 1
    side = _sidecar()
    assert "http-503" in side["problems"]
    for coin in hs.COINS:
        assert str(textlog.guard_path(_month_file(coin))) in side["lock_guard"]


def test_collected_at_is_stamped_at_response_receipt_not_job_start(isolated_cache, monkeypatch):
    # The job starts at T0; the response is received at T1. The row must carry T1.
    # Clock reads happen in order: job start, then response receipt, then sidecar finish.
    stamps = [dt.datetime(2026, 11, 14, 23, 30, 0, tzinfo=dt.timezone.utc),
              dt.datetime(2026, 11, 14, 23, 30, 5, tzinfo=dt.timezone.utc)]
    def fake_now(tz):
        return stamps.pop(0) if len(stamps) > 1 else stamps[0]
    monkeypatch.setattr(collect_perp.dt, "datetime", type("DateTimeProxy", (), {
        "timezone": dt.timezone,
        "datetime": dt.datetime,
        "now": staticmethod(fake_now),
    }))
    assert collect_perp.run(["--job", "hl-snapshot"], client=_client(_body())) == 0
    assert _sidecar()["started_utc"] == "2026-11-14T23:30:00Z"
    row = json.loads(_month_file("BTC").read_text(encoding="utf-8").splitlines()[0])
    assert row["collected_at_utc"] == "2026-11-14T23:30:05Z"


def test_response_month_is_used_for_coin_guard_paths(isolated_cache, monkeypatch):
    stamps = [dt.datetime(2026, 11, 30, 23, 59, 0, tzinfo=dt.timezone.utc),
              dt.datetime(2026, 12, 1, 0, 0, 5, tzinfo=dt.timezone.utc)]

    def fake_now(tz):
        return stamps.pop(0) if len(stamps) > 1 else stamps[0]

    monkeypatch.setattr(collect_perp.dt, "datetime", type("DateTimeProxy", (), {
        "timezone": dt.timezone,
        "datetime": dt.datetime,
        "now": staticmethod(fake_now),
    }))
    assert collect_perp.run(["--job", "hl-snapshot"], client=_client(_body())) == 0

    side = _sidecar()
    for coin in hs.COINS:
        november = hl_snapshot_path(coin, "2026-11")
        december = hl_snapshot_path(coin, "2026-12")
        december_guard = str(textlog.guard_path(december))
        november_guard = str(textlog.guard_path(november))
        assert december.exists() and not november.exists()
        assert december_guard in side["lock_guard"]
        assert november_guard not in side["lock_guard"]
        assert side["lock_guard"][december_guard] == {"lock": False, "guard": False}



# --- exit codes ---------------------------------------------------------------

def test_exit_0_when_every_coin_is_written(isolated_cache):
    assert _run(["--job", "hl-snapshot"], _client(_body())) == 0
    assert _month_file("BTC").exists() and _month_file("ETH").exists()
    side = _sidecar()
    assert side["exit_code"] == 0 and side["problems"] == []


def test_exit_1_when_fetch_fails_and_nothing_is_written(isolated_cache):
    assert _run(["--job", "hl-snapshot"], _client(status=500)) == 1
    assert not _month_file("BTC").exists() and not _month_file("ETH").exists()
    assert _sidecar()["exit_code"] == 1


def test_network_off_is_exit_1_with_sidecar_saying_so(isolated_cache, monkeypatch):
    monkeypatch.setattr(hs, "time", FakeClock())
    assert _run(["--job", "hl-snapshot"], _client(fail=True)) == 1
    assert not _month_file("BTC").exists()
    side = _sidecar()
    assert side["exit_code"] == 1
    assert "transport-error" in side["problems"]


def test_exit_2_when_one_coin_is_missing(isolated_cache):
    body = _body()
    body[0]["universe"] = [u for u in body[0]["universe"] if u["name"] != "ETH"]
    body[1] = body[1][:2]
    assert _run(["--job", "hl-snapshot"], _client(body)) == 2
    assert _month_file("BTC").exists() and not _month_file("ETH").exists()
    assert "coin-missing:ETH" in _sidecar()["problems"]


def test_exit_2_when_an_expected_key_is_absent(isolated_cache):
    body = _body()
    del body[1][1]["funding"]  # contexts[1] is BTC (universe index 1)
    assert _run(["--job", "hl-snapshot"], _client(body)) == 2
    assert "key-absent:BTC:funding" in _sidecar()["problems"]


def test_exit_1_when_lock_is_held_and_nothing_is_written(isolated_cache):
    _plant_fresh_lock("BTC")
    _plant_fresh_lock("ETH")
    assert _run(["--job", "hl-snapshot"], _client(_body())) == 1
    assert not _month_file("BTC").exists() and not _month_file("ETH").exists()
    assert _sidecar()["exit_code"] == 1


# --- successful write, but flagged ------------------------------------------

def test_successful_write_then_release_denied_is_exit_2(isolated_cache, monkeypatch):
    real_unlink = textlog._unlink

    def deny_lock_delete(p):
        if p.name.endswith(".jsonl.lock"):
            raise PermissionError("lock delete denied")
        real_unlink(p)

    monkeypatch.setattr(textlog, "_unlink", deny_lock_delete)
    monkeypatch.setattr(textlog, "time", FakeClock())
    assert _run(["--job", "hl-snapshot"], _client(_body())) == 2
    assert _month_file("BTC").exists()  # the line was written before the release failed
    assert "lock-release-denied" in _sidecar()["problems"]


def test_left_behind_takeover_guard_is_flagged(isolated_cache, monkeypatch):
    _plant_stale_lock("BTC")
    real_delete_own = textlog._delete_own

    def keep_guard(path):
        if path.name.endswith(".takeover"):
            return False  # the guard stays on disk; the write itself succeeds
        return real_delete_own(path)

    monkeypatch.setattr(textlog, "_delete_own", keep_guard)
    assert _run(["--job", "hl-snapshot"], _client(_body())) == 2
    assert not _month_file("BTC").exists()  # guard seen at confirm: refused, not written
    assert "takeover-guard-left" in _sidecar()["problems"]
    assert "not-written:BTC" in _sidecar()["problems"]
    assert textlog.guard_path(_month_file("BTC")).exists()


def test_left_behind_guard_blocks_the_next_writer(isolated_cache):
    guard = textlog.guard_path(_month_file("BTC"))
    guard.parent.mkdir(parents=True, exist_ok=True)
    guard.write_text("", encoding="utf-8")
    assert _run(["--job", "hl-snapshot"], _client(_body())) == 2  # ETH written, BTC refused
    assert not _month_file("BTC").exists()
    assert _month_file("ETH").exists()


def test_guards_on_both_coin_files_exit_1_with_no_data_line(isolated_cache):
    for coin in ("BTC", "ETH"):
        guard = textlog.guard_path(_month_file(coin))
        guard.parent.mkdir(parents=True, exist_ok=True)
        guard.write_text("", encoding="utf-8")
    assert _run(["--job", "hl-snapshot"], _client(_body())) == 1
    assert not _month_file("BTC").exists() and not _month_file("ETH").exists()
    assert _sidecar()["exit_code"] == 1


def test_guard_on_one_coin_file_other_coin_still_writes(isolated_cache):
    guard = textlog.guard_path(_month_file("BTC"))
    guard.parent.mkdir(parents=True, exist_ok=True)
    guard.write_text("", encoding="utf-8")
    assert _run(["--job", "hl-snapshot"], _client(_body())) == 2
    assert _month_file("ETH").exists() and not _month_file("BTC").exists()
    side = _sidecar()
    assert "not-written:BTC" in side["problems"]
    assert "guard-present" in side["problems"]
    assert "takeover-guard-left" in side["problems"]


# --- dry run, coverage, sidecar -----------------------------------------------

def test_dry_run_writes_nothing(isolated_cache, capsys):
    assert _run(["--job", "hl-snapshot", "--dry-run"], _client(_body())) == 0
    assert not _month_file("BTC").exists() and not _sidecar_file().exists()
    assert "BTC" in capsys.readouterr().out


def test_coverage_prints_one_line_per_day(isolated_cache, capsys):
    _run(["--job", "hl-snapshot"], _client(_body()))  # snapshot at 23:30Z on 2026-11-14
    capsys.readouterr()
    assert _run(["--coverage", "--days", "2"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert "2026-11-14 BTC ok" in out
    assert "2026-11-13 BTC gap" in out
    assert "2026-11-14 ETH ok" in out


def test_coverage_shows_lock_and_guard_state(isolated_cache, capsys):
    _plant_fresh_lock("BTC")
    capsys.readouterr()
    _run(["--coverage", "--days", "1"])
    out = capsys.readouterr().out
    assert "BTC 2026-11 lock=present guard=absent" in out
    assert "ETH 2026-11 lock=absent guard=absent" in out


def test_sidecar_has_the_pinned_keys(isolated_cache):
    _run(["--job", "hl-snapshot"], _client(_body()))
    side = _sidecar()
    assert set(side) >= {"job", "started_utc", "finished_utc", "exit_code", "problems"}
    assert side["job"] == "hl-snapshot"


def test_coin_refusal_by_one_writer_is_flagged_not_raised(isolated_cache):
    _plant_fresh_lock("ETH")
    assert _run(["--job", "hl-snapshot"], _client(_body())) == 2
    assert _month_file("BTC").exists()
    assert "lock-present" in _sidecar()["problems"]


def test_mkdir_failure_on_one_coin_keeps_the_other_coin_and_exits_2(isolated_cache):
    # A regular file where ETH's directory must go makes ETH's mkdir raise OSError.
    blocker = perp_root() / "hl_snapshot" / "ETH"
    blocker.parent.mkdir(parents=True, exist_ok=True)
    blocker.write_text("x", encoding="utf-8")
    assert _run(["--job", "hl-snapshot"], _client(_body())) == 2
    assert _month_file("BTC").exists()
    assert "not-written:ETH" in _sidecar()["problems"]


def test_decoding_error_is_exit_1_with_sidecar_not_a_traceback(isolated_cache, monkeypatch):
    monkeypatch.setattr(hs, "time", FakeClock())

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.DecodingError("bad content-encoding")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert _run(["--job", "hl-snapshot"], client) == 1
    assert _sidecar()["exit_code"] == 1
    assert "http-client-error" in _sidecar()["problems"]


def test_snapshot_append_uses_zero_wait_per_va30(isolated_cache, monkeypatch):
    seen: list[float] = []
    real_append = textlog.append_line

    def spy(path, line, **kwargs):
        seen.append(kwargs.get("wait_seconds"))
        return real_append(path, line, **kwargs)

    monkeypatch.setattr(textlog, "append_line", spy)
    assert _run(["--job", "hl-snapshot"], _client(_body())) == 0
    assert seen == [0.0, 0.0]
