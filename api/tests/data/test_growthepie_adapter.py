"""Chain growth RFC-2: growthepie adapter. Recorded-shape fixtures, no network
except the opt-in `integration` test
(`uv run --project api pytest api/ -m integration -k growthepie`)."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import httpx
import pytest

from api.data import growthepie_adapter as gp

FIX = Path(__file__).parent / "fixtures"
BASE_DAA = json.loads((FIX / "growthepie_chain_base_daa.json").read_text())
EXPORT_TX = json.loads((FIX / "growthepie_export_txcount.json").read_text())
MASTER = json.loads((FIX / "growthepie_master.json").read_text())


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_chain_metric_contract_shape_and_url():
    seen = []

    def h(req):
        seen.append(str(req.url))
        return httpx.Response(200, json=BASE_DAA)

    s = gp.fetch_chain_metric("base", "active_addresses", _client(h))
    assert seen == ["https://api.growthepie.xyz/v1/metrics/chains/base/daa.json"]
    assert s.status == "ok" and s.chain_key == "base" and s.metric == "active_addresses"
    # ms timestamps -> UTC dates; null value dropped, never zero-filled
    assert s.points == [("2024-09-23", 812345.0), ("2024-09-25", 834567.0)]
    assert s.last_updated_utc == "2026-09-25 06:12:03"
    assert s.reason is None


def test_unix_seconds_and_ms_give_same_utc_date():
    assert gp.unix_to_utc_date(1727049600) == gp.unix_to_utc_date(1727049600000) == "2024-09-23"
    assert gp.unix_to_utc_date(1727049600 + 86399) == "2024-09-23"  # still that UTC day
    assert gp.unix_to_utc_date(None) is None and gp.unix_to_utc_date("x") is None


def test_transactions_uses_txcount_key():
    seen = []
    gp.fetch_chain_metric("ethereum", "transactions", _client(lambda r: seen.append(r.url.path) or httpx.Response(200, json=BASE_DAA)))
    assert seen == ["/v1/metrics/chains/ethereum/txcount.json"]


def test_redistribution_flag_and_attribution():
    s = gp.fetch_chain_metric("base", "active_addresses", _client(lambda r: httpx.Response(200, json=BASE_DAA)))
    assert gp.REDISTRIBUTABLE is True and s.redistributable is True
    assert s.attribution == "Source: growthepie, https://www.growthepie.com."


@pytest.mark.parametrize(
    "resp,reason",
    [
        (httpx.Response(403, text="AccessDenied"), "http-403"),
        (httpx.Response(200, text="not json"), "invalid-json"),
        (httpx.Response(200, json={"details": {}}), "unexpected-shape"),
        (httpx.Response(200, json={"details": {"timeseries": {"daily": {"types": ["unix", "value"], "data": []}}}}), "empty-series"),
        (httpx.Response(200, json=[1, 2]), "unexpected-shape"),
    ],
)
def test_bad_responses_are_unavailable_never_zero(resp, reason):
    s = gp.fetch_chain_metric("base", "active_addresses", _client(lambda r: resp))
    assert s.status == "unavailable" and s.reason == reason and s.points == []


def test_network_error_never_raises():
    def h(req):
        raise httpx.ConnectTimeout("boom")

    s = gp.fetch_chain_metric("base", "active_addresses", _client(h))
    assert s.status == "unavailable" and s.reason == "fetch-failed: ConnectTimeout"


def test_unknown_metric():
    assert gp.fetch_chain_metric("base", "new_addresses", _client(lambda r: httpx.Response(200))).reason == "unknown-metric"


def test_per_chain_failure_isolation():
    """P7/E7: two chain calls in one run; the first forced to fail (raise),
    the second succeeds and is unaffected. Also a malformed-payload chain."""
    calls = []

    def h(req):
        calls.append(req.url.path)
        if "/arbitrum/" in req.url.path:
            raise httpx.ReadTimeout("forced")
        if "/optimism/" in req.url.path:
            return httpx.Response(200, json={"details": "garbage"})
        return httpx.Response(200, json=BASE_DAA)

    out = gp.fetch_chain_metrics(["arbitrum", "base", "optimism"], "active_addresses", _client(h))
    assert len(calls) == 3  # every chain attempted despite the first failing
    assert out["arbitrum"].status == "unavailable" and out["arbitrum"].reason.startswith("fetch-failed")
    assert out["optimism"].status == "unavailable" and out["optimism"].reason == "unexpected-shape"
    alone = gp.fetch_chain_metric("base", "active_addresses", _client(lambda r: httpx.Response(200, json=BASE_DAA)))
    assert asdict(out["base"]) == asdict(alone)


def test_bulk_export_split_per_chain():
    seen = []

    def h(req):
        seen.append(req.url.path)
        return httpx.Response(200, json=EXPORT_TX)

    out = gp.fetch_export("transactions", ["arbitrum", "base", "optimism", "robinhood"], _client(h))
    assert seen == ["/v1/export/txcount.json"]
    assert out["arbitrum"].points == [("2021-05-29", 1200.0), ("2021-05-30", 1500.0)]
    assert out["base"].points == [("2023-08-09", 136000.0)]  # null row dropped
    assert out["optimism"].status == "unavailable" and out["optimism"].reason == "chain-not-in-export"
    assert out["robinhood"].reason == "chain-not-in-export"


def test_bulk_export_failure_marks_each_requested_chain():
    out = gp.fetch_export("transactions", ["base", "arbitrum"], _client(lambda r: httpx.Response(500)))
    assert {k: v.reason for k, v in out.items()} == {"base": "http-500", "arbitrum": "http-500"}


def test_supported_chains_from_master():
    seen = []
    s = gp.fetch_supported_chains("active_addresses", _client(lambda r: seen.append(r.url.path) or httpx.Response(200, json=MASTER)))
    assert seen == ["/v1/master.json"]
    assert s.status == "ok" and {"robinhood", "polygon_pos", "optimism"} <= s.chains
    assert gp.fetch_supported_chains("transactions", _client(lambda r: httpx.Response(200, json={"metrics": {}}))).status == "unavailable"


def test_no_secret_in_results():
    s = gp.fetch_chain_metric("base", "active_addresses", _client(lambda r: httpx.Response(200, json=BASE_DAA)))
    text = json.dumps(asdict(s)).lower()
    assert "key" not in text.replace("chain_key", "") and "token" not in text and "secret" not in text


@pytest.mark.integration
def test_real_growthepie():
    s = gp.fetch_chain_metric("base", "active_addresses")
    assert s.status == "ok", s.reason
    assert len(s.points) > 300
    sup = gp.fetch_supported_chains("active_addresses")
    assert sup.status == "ok" and "base" in sup.chains
    exp = gp.fetch_export("transactions", ["arbitrum"])
    assert exp["arbitrum"].status == "ok" and exp["arbitrum"].points[0][0] <= "2021-06-01"
