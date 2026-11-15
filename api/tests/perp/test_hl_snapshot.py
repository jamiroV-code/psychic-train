"""Stage 2: Hyperliquid snapshot adapter. No network: httpx.MockTransport only."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import httpx
import pytest

from api.data.perp import hl_snapshot as hs
from api.data.perp import textlog
from api.data.perp.paths import hl_snapshot_path, perp_root

FIXTURE = Path(__file__).parent / "fixtures" / "hl_snapshot.json"


def _utc(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def _response_body(name: str = "response") -> list:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))[name]


def _client(body=None, status=200, raw: bytes | None = None, headers=None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if raw is not None:
            return httpx.Response(status, content=raw, headers=headers or {})
        return httpx.Response(status, json=body, headers=headers or {})

    return httpx.Client(transport=httpx.MockTransport(handler))


NOW = dt.datetime(2026, 11, 14, 10, 0, 0, tzinfo=dt.timezone.utc)


# --- ok path and verbatim context -------------------------------------------

def test_ok_path_keeps_context_verbatim_and_matches_by_name():
    body = _response_body()
    result = hs.fetch_snapshot(client=_client(body), now=NOW)
    assert result.status == "ok"
    assert result.problems == []
    # BTC is at universe index 1 and ETH at 2; contexts are matched by position.
    assert result.coins["BTC"] == body[1][1]
    assert result.coins["ETH"] == body[1][2]
    # strings stay strings
    assert result.coins["BTC"]["markPx"] == "200.0"


def test_coins_constant_is_btc_eth():
    assert hs.COINS == ("BTC", "ETH")


def test_null_eth_context_is_preserved_not_invented():
    body = _response_body("response_eth_null")
    result = hs.fetch_snapshot(client=_client(body), now=NOW)
    assert result.status == "ok"
    eth = result.coins["ETH"]
    assert eth["premium"] is None
    assert eth["midPx"] is None
    assert eth["impactPxs"] is None
    assert "null-value:ETH:premium" in result.problems
    assert "null-value:ETH:midPx" in result.problems


# --- failures: nothing invented, no exception -------------------------------

def test_http_failure_is_unavailable_not_raised():
    result = hs.fetch_snapshot(client=_client(status=500, body={}), now=NOW)
    assert result.status == "unavailable"
    assert result.coins == {}
    assert result.problems


def test_bad_json_is_unavailable():
    result = hs.fetch_snapshot(client=_client(raw=b"not json"), now=NOW)
    assert result.status == "unavailable"
    assert result.coins == {}


def test_missing_coin_is_a_problem_and_the_other_coin_is_still_kept():
    body = _response_body()
    body[0]["universe"] = [u for u in body[0]["universe"] if u["name"] != "ETH"]
    body[1] = body[1][:2]
    result = hs.fetch_snapshot(client=_client(body), now=NOW)
    assert "ETH" not in result.coins
    assert "BTC" in result.coins
    assert "coin-missing:ETH" in result.problems


def test_shape_drift_is_refused():
    # top-level object instead of list-of-2
    result = hs.fetch_snapshot(client=_client({"universe": []}), now=NOW)
    assert result.status == "unavailable"
    assert "shape-drift" in result.problems


def test_unequal_universe_and_contexts_is_refused():
    body = _response_body()
    body[1] = body[1][:2]
    result = hs.fetch_snapshot(client=_client(body), now=NOW)
    assert result.status == "unavailable"
    assert "shape-drift" in result.problems


def test_expected_key_absent_is_flagged():
    body = _response_body()
    del body[1][1]["funding"]
    result = hs.fetch_snapshot(client=_client(body), now=NOW)
    assert "BTC" in result.coins
    assert "key-absent:BTC:funding" in result.problems


def test_naive_now_does_not_raise():
    naive = dt.datetime(2026, 11, 14, 10, 0, 0)
    result = hs.fetch_snapshot(client=_client(_response_body()), now=naive)
    assert result.status == "ok"
    assert result.collected_at_utc == "2026-11-14T10:00:00Z"


def test_optional_server_date_is_recorded_when_present():
    headers = {"Date": "Sat, 14 Nov 2026 10:00:01 GMT"}
    result = hs.fetch_snapshot(client=_client(_response_body(), headers=headers), now=NOW)
    assert result.server_date == "Sat, 14 Nov 2026 10:00:01 GMT"


def test_collected_time_is_response_receipt_time(monkeypatch):
    received = dt.datetime(2026, 11, 15, 0, 0, 1, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(hs.dt, "datetime", type("DateTimeProxy", (), {
        "timezone": dt.timezone,
        "datetime": dt.datetime,
        "now": staticmethod(lambda tz: received),
    }))
    result = hs.fetch_snapshot(client=_client(_response_body()), now=None)
    assert result.collected_at_utc == "2026-11-15T00:00:01Z"


def test_http_5xx_retries_then_succeeds(monkeypatch):
    calls = []
    def handler(request):
        calls.append(1)
        return httpx.Response(503 if len(calls) == 1 else 200, json=_response_body())
    monkeypatch.setattr(hs.time, "sleep", lambda _: None)
    ticks = iter([0, 0, 0, 0])
    monkeypatch.setattr(hs.time, "monotonic", lambda: next(ticks))
    result = hs.fetch_snapshot(client=httpx.Client(transport=httpx.MockTransport(handler)), now=NOW)
    assert result.status == "ok"
    assert calls == [1, 1]


def test_server_date_is_persisted_in_each_line(isolated_cache):
    result = _snap("2026-11-14T10:00:00Z", "x")
    result.server_date = "Sat, 14 Nov 2026 10:00:01 GMT"
    _write(result)
    for coin in hs.COINS:
        row = json.loads(hl_snapshot_path(coin, "2026-11").read_text().splitlines()[0])
        assert row["server_date"] == result.server_date


def test_reader_removes_exact_duplicate_lines_preserving_order(isolated_cache):
    path = hl_snapshot_path("BTC", "2026-11")
    path.parent.mkdir(parents=True, exist_ok=True)
    first = json.dumps({"collected_at_utc": "2026-11-14T10:00:00Z", "coin": "BTC", "context": {"markPx": "a"}})
    second = json.dumps({"collected_at_utc": "2026-11-14T11:00:00Z", "coin": "BTC", "context": {"markPx": "b"}})
    path.write_text(first + "\n" + second + "\n" + first + "\n", encoding="utf-8")
    rows = hs.read_snapshots("BTC", dt.date(2026, 11, 14), dt.date(2026, 11, 15))
    assert [r["context"]["markPx"] for r in rows] == ["a", "b"]

def test_server_date_absent_is_none():
    result = hs.fetch_snapshot(client=_client(_response_body()), now=NOW)
    assert result.server_date is None


def _snap(stamp: str, marker: str) -> hs.SnapshotResult:
    ctx = {"markPx": marker, "prevDayPx": "1", "dayNtlVlm": "2", "dayBaseVlm": "3",
           "midPx": None, "premium": None, "impactPxs": None, "funding": "0",
           "openInterest": "0", "oraclePx": "0"}
    return hs.SnapshotResult(status="ok", collected_at_utc=stamp,
                             coins={"BTC": dict(ctx), "ETH": dict(ctx)},
                             problems=[], server_date=None)


def _write(result: hs.SnapshotResult):
    """Write through the production writer under the run lock, as the collector does."""
    (perp_root() / "_locks").mkdir(parents=True, exist_ok=True)
    with textlog.locked(perp_root() / "_locks" / "hl-snapshot", takeover=True) as handle:
        return hs.write_snapshot(result, handle, [])


def test_write_and_read_back_in_time_order(isolated_cache):
    _write(_snap("2026-11-14T23:55:04Z", "b"))
    _write(_snap("2026-11-14T23:10:00Z", "a"))
    rows = hs.read_snapshots("BTC", dt.date(2026, 11, 14), dt.date(2026, 11, 15))
    assert [r["collected_at_utc"] for r in rows] == [
        "2026-11-14T23:10:00Z", "2026-11-14T23:55:04Z"]


def test_write_returns_per_coin_append_results(isolated_cache):
    written, out = _write(_snap("2026-11-14T10:00:00Z", "x"))
    assert set(out) == {"BTC", "ETH"}
    assert all(r.written for r in out.values())
    assert hl_snapshot_path("BTC", "2026-11").exists()


UTC_BOUNDARY_CASES = [
    # (snapshot time, marker) rows for day D = 2026-11-14
    ("2026-11-14T23:10:00Z", "early"),
    ("2026-11-14T23:55:04Z", "close"),
    ("2026-11-15T00:05:00Z", "next-day"),
]


def test_close_value_picks_latest_snapshot_in_utc_window(isolated_cache):
    for stamp, marker in UTC_BOUNDARY_CASES:
        _write(_snap(stamp, marker))
    day = dt.date(2026, 11, 14)
    assert hs.close_value("BTC", day, "markPx") == "close"


def test_only_a_snapshot_at_22_40_leaves_day_a_gap(isolated_cache):
    _write(_snap("2026-11-14T22:40:00Z", "too-early"))
    day = dt.date(2026, 11, 14)
    assert hs.close_value("BTC", day, "markPx") is None
    assert hs.coverage("BTC", day, day) == [(day, False)]


def test_exactly_next_midnight_belongs_to_day_d(isolated_cache):
    _write(_snap("2026-11-15T00:00:00Z", "midnight"))
    day = dt.date(2026, 11, 14)
    assert hs.close_value("BTC", day, "markPx") == "midnight"


def test_exactly_23_00_is_outside_the_window(isolated_cache):
    _write(_snap("2026-11-14T23:00:00Z", "edge"))
    day = dt.date(2026, 11, 14)
    assert hs.close_value("BTC", day, "markPx") is None


def test_null_context_field_gives_no_value(isolated_cache):
    snap = _snap("2026-11-14T23:30:00Z", "x")
    snap.coins["ETH"]["premium"] = None
    _write(snap)
    day = dt.date(2026, 11, 14)
    assert hs.close_value("ETH", day, "premium") is None


def test_month_roll_lands_in_correct_files(isolated_cache):
    _write(_snap("2026-11-30T23:55:00Z", "nov"))
    _write(_snap("2026-12-01T00:55:00Z", "dec"))
    assert hl_snapshot_path("BTC", "2026-11").exists()
    assert hl_snapshot_path("BTC", "2026-12").exists()
    rows = hs.read_snapshots("BTC", dt.date(2026, 11, 30), dt.date(2026, 12, 2))
    assert [r["collected_at_utc"] for r in rows] == [
        "2026-11-30T23:55:00Z", "2026-12-01T00:55:00Z"]


@pytest.mark.parametrize("tz", ["Europe/Brussels", "America/New_York"])
def test_result_does_not_depend_on_machine_timezone(isolated_cache, monkeypatch, tz):
    monkeypatch.setenv("TZ", tz)
    _write(_snap("2026-11-14T23:55:04Z", "close"))
    day = dt.date(2026, 11, 14)
    assert hs.close_value("BTC", day, "markPx") == "close"


def test_rolling_fields_are_not_relabelled_as_daily(isolated_cache):
    # VA-55: prevDayPx / dayNtlVlm / dayBaseVlm are stored verbatim as rolling values.
    _write(_snap("2026-11-14T23:55:04Z", "close"))
    rows = hs.read_snapshots("BTC", dt.date(2026, 11, 14), dt.date(2026, 11, 15))
    assert "prevDayPx" in rows[0]["context"]
    assert "closed_day" not in json.dumps(rows[0])


def test_decoding_error_is_recorded_not_raised(monkeypatch):
    # httpx.DecodingError is a RequestError, not a TransportError: it must not escape.
    monkeypatch.setattr(hs.time, "sleep", lambda _: None)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.DecodingError("bad content-encoding")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = hs.fetch_snapshot(client=client, now=NOW)
    assert result.status == "unavailable"
    assert result.coins == {}
    assert "http-client-error" in result.problems
