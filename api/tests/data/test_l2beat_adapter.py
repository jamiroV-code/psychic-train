"""Chain growth RFC-2: L2BEAT cross-check adapter. No network except the
opt-in `integration` test (`uv run --project api pytest api/ -m integration -k l2beat`)."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from api.data import l2beat_adapter as l2

FIX = Path(__file__).parent / "fixtures"
BASE = json.loads((FIX / "l2beat_activity_base.json").read_text())
EMPTY = json.loads((FIX / "l2beat_activity_optimism_empty.json").read_text())


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_parse_by_column_name_and_range_param():
    seen = []

    def h(req):
        seen.append(str(req.url))
        return httpx.Response(200, json=BASE)

    a = l2.fetch_activity("base", "max", _client(h))
    assert seen == ["https://l2beat.com/api/scaling/activity/base?range=max"]
    assert a.status == "ok" and a.range == "max"
    assert [(p.date, p.count, p.uops_count) for p in a.points] == [
        ("2024-09-23", 4100000.0, 4300000.0),
        ("2024-09-24", 4200000.0, None),
    ]  # null count row dropped, not zero


def test_columns_reordered_still_parsed():
    payload = {"data": {"chart": {"types": ["count", "timestamp"], "data": [[7, 1727049600]]}}}
    a = l2.fetch_activity("x", "30d", _client(lambda r: httpx.Response(200, json=payload)))
    assert a.status == "ok" and a.points[0].count == 7.0 and a.points[0].uops_count is None


def test_empty_chart_is_unavailable_not_zero():
    a = l2.fetch_activity("optimism", "max", _client(lambda r: httpx.Response(200, json=EMPTY)))
    assert a.status == "unavailable" and a.reason == "empty-chart" and a.points == []


@pytest.mark.parametrize(
    "resp,reason",
    [
        (httpx.Response(404), "http-404"),
        (httpx.Response(200, text="<html>"), "invalid-json"),
        (httpx.Response(200, json={"data": {"chart": {"types": ["x"], "data": []}}}), "unexpected-shape"),
        (httpx.Response(200, json=[]), "unexpected-shape"),
    ],
)
def test_bad_responses(resp, reason):
    a = l2.fetch_activity("base", "30d", _client(lambda r: resp))
    assert a.status == "unavailable" and a.reason == reason


def test_invalid_range_no_request():
    calls = []
    a = l2.fetch_activity("base", "forever", _client(lambda r: calls.append(r) or httpx.Response(200, json=BASE)))
    assert a.reason == "invalid-range" and calls == []


def test_network_error_never_raises():
    def h(req):
        raise httpx.ConnectError("down")

    assert l2.fetch_activity("base", client=_client(h)).reason == "fetch-failed: ConnectError"


def test_not_redistributable():
    a = l2.fetch_activity("base", client=_client(lambda r: httpx.Response(200, json=BASE)))
    assert l2.REDISTRIBUTABLE is False and a.redistributable is False


@pytest.mark.integration
def test_real_l2beat():
    a = l2.fetch_activity("op-mainnet", "max")
    assert a.status == "ok", a.reason
    assert len(a.points) > 1000
    assert l2.fetch_activity("optimism", "30d").status == "unavailable"
