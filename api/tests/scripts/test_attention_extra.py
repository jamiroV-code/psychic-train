"""Classifier and verifier for the refresh-extra job (pure; no network)."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from api.scripts import attention_extra as x

TODAY = date(2026, 10, 17)


def test_ok_line_is_ok():
    assert x.classify("trends", "trends: 3/10 ok, 3 rows written [ok 3, other 7]").status == "ok"


def test_stored_insufficient_history_counts_as_refreshed():
    assert x.classify("hyperliquid_volume", "hyperliquid_volume: 0/5 ok, 5 rows written [insufficient-history 5]").status == "ok"


def test_binance_451_is_unavailable_with_status():
    r = x.classify("exchange_volume", "exchange_volume: 0/103 ok, 0 rows written [other 103] reasons: fetch-failed: ExchangeNotAvailable HTTP 451 x103")
    assert r.status == "unavailable" and "451" in r.detail


@pytest.mark.parametrize("err", ["HTTPStatusError HTTP 403: Forbidden", "ReadTimeout: timed out", "RateLimitExceeded: slow down"])
def test_provider_exceptions_are_unavailable(err):
    assert x.classify("reddit", f"reddit: error {err}").status == "unavailable"


@pytest.mark.parametrize("err", ["KeyError: 'foo'", "ImportError: no module", "RuntimeError: boom"])
def test_code_errors_fail(err):
    assert x.classify("trends", f"trends: error {err}").status == "failed"


def test_missing_or_garbled_line_fails():
    assert x.classify("trends", None).status == "failed"
    assert x.classify("trends", "trends: ???").status == "failed"
    assert x.classify("trends", "trends: 0/0 ok, 0 rows written []").status == "failed"


def test_no_credentials_is_not_probed():
    assert x.classify("reddit", "reddit: not-probed no credentials") == x.Result("not-probed", "no credentials")


def test_detail_cannot_inject_workflow_commands():
    r = x.classify("reddit", "reddit: error HTTPStatusError HTTP 403: ::error::pwn\n%0A")
    assert "::" not in r.detail and "\n" not in r.detail


def _store(tmp_path, src, day):
    d = tmp_path / src
    d.mkdir()
    pd.DataFrame({"date": [pd.Timestamp(day)], "value": [1.0]}).to_parquet(d / "BTC.parquet")


def test_verify_warns_for_blocks_probes_only_ok_and_does_not_fail(tmp_path):
    _store(tmp_path, "hyperliquid_volume", "2026-10-16")
    logs = {"exchange_volume": "exchange_volume: 0/3 ok, 0 rows written [other 3] reasons: fetch-failed: ExchangeNotAvailable HTTP 451 x3",
            "hyperliquid_volume": "hyperliquid_volume: 1/1 ok, 1 rows written [ok 1]",
            "trends": "trends: error HTTPStatusError HTTP 429: Too Many Requests",
            "reddit": "reddit: not-probed no credentials"}
    out, probe, failed = x.verify(logs, tmp_path, TODAY)
    assert probe == ["hyperliquid_volume"] and failed == []
    warns = [ln for ln in out if ln.startswith("::warning::")]
    assert len(warns) == 2 and "exchange_volume" in warns[0] and "HTTP 451" in warns[0] and "HTTP 429" in warns[1]


def test_verify_fails_on_code_error_and_stale_ok(tmp_path):
    _store(tmp_path, "hyperliquid_volume", "2026-10-01")
    logs = {"exchange_volume": "exchange_volume: error KeyError: 'x'",
            "hyperliquid_volume": "hyperliquid_volume: 1/1 ok, 0 rows written [ok 1]"}
    out, probe, failed = x.verify(logs, tmp_path, TODAY)
    assert probe == [] and "exchange_volume" in failed and "hyperliquid_volume" in failed and "trends" in failed
