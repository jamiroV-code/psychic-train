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


def _line(reasons, src="trends"):
    return f"{src}: 0/103 ok, 0 rows written [other 103] reasons: {reasons}"


def test_all_code_class_reasons_fail():
    assert x.classify("exchange_volume", _line("fetch-failed: TypeError x103", "exchange_volume")).status == "failed"
    assert x.classify("exchange_volume", _line("fetch-failed: TypeError x60; fetch-failed: KeyError x43", "exchange_volume")).status == "failed"


def test_http_or_provider_class_reasons_stay_unavailable():
    assert x.classify("exchange_volume", _line("fetch-failed: ExchangeNotAvailable HTTP 451 x103", "exchange_volume")).status == "unavailable"
    assert x.classify("exchange_volume", _line("fetch-failed: TypeError HTTP 451 x103", "exchange_volume")).status == "unavailable"
    assert x.classify("trends", _line("fetch-failed: ReadTimeout x100")).status == "unavailable"
    assert x.classify("trends", _line("unavailable x98; skipped after repeated provider failures x5")).status == "unavailable"
    assert x.classify("reddit", _line("token unavailable x103", "reddit")).status == "unavailable"


def test_mixed_reasons_unavailable_only_with_provider_majority():
    assert x.classify("trends", _line("fetch-failed: TypeError x20; fetch-failed: ReadTimeout x80")).status == "unavailable"
    assert x.classify("trends", _line("fetch-failed: TypeError x80; fetch-failed: ReadTimeout x20")).status == "failed"
    assert x.classify("trends", _line("fetch-failed: TypeError x50; fetch-failed: ReadTimeout x50")).status == "failed"


def test_line_without_reasons_unchanged():
    assert x.classify("trends", "trends: 0/10 ok, 0 rows written [other 10]").status == "unavailable"


# T181: a Google refusal of the runner is a provider block (yellow); our own bugs stay code errors (red).
@pytest.mark.parametrize("reason", [
    "fetch-failed: ConnectionError", "fetch-failed: ReadTimeout", "fetch-failed: Timeout", "fetch-failed: SSLError",
    "fetch-failed: ConnectionResetError", "fetch-failed: TimeoutError", "fetch-failed: ChunkedEncodingError",
    "fetch-failed: ConnectionError(HTTP 503)", "fetch-failed: ResponseError(HTTP 500)", "fetch-failed: HTTPError(HTTP 429)",
    "rate-limited: TooManyRequestsError(HTTP 429)", "capped", "time budget reached", "skipped after repeated HTTP 429",
    "session-failed: ConnectionError", "session-failed: ReadTimeout", "session-failed: no client",
])
def test_provider_refusals_classify_as_provider(reason):
    assert x.reason_kind(reason) == "provider", reason
    assert x.classify("trends", _line(f"{reason} x75")).status == "unavailable"


@pytest.mark.parametrize("reason", [
    "fetch-failed: TypeError", "fetch-failed: KeyError", "fetch-failed: AttributeError", "fetch-failed: ValueError",
    "fetch-failed: RuntimeError", "fetch-failed: SomethingUnknownError",
    "parse-failed: ValueError", "parse-failed: KeyError", "parse-failed: ConnectionError",
    "store-failed: OSError", "store-failed: ValueError", "store-failed: ConnectionError", "store-failed: TimeoutError",
])
def test_our_own_errors_classify_as_code(reason):
    assert x.reason_kind(reason) == "code", reason
    assert x.classify("trends", _line(f"{reason} x75")).status == "failed"


def test_network_class_set_is_class_names_only():
    assert {"ConnectionError", "Timeout", "SSLError", "ReadTimeout"} <= set(x.PROVIDER_CLASSES)
    assert not {"TypeError", "KeyError", "AttributeError", "ValueError", "Exception", "RuntimeError", "OSError"} & set(x.PROVIDER_CLASSES)
    assert all(c.isidentifier() for c in x.PROVIDER_CLASSES)


def test_error_line_with_connection_error_is_unavailable():
    assert x.classify("trends", "trends: error ConnectionError: refused").status == "unavailable"
    assert x.classify("trends", "trends: error ValueError: bad").status == "failed"


def test_failure_class_labels_cover_every_status():
    assert set(x.FAILURE_CLASS) == {"ok", "unavailable", "failed", "not-probed"}
    assert x.failure_class("unavailable").startswith("provider block")
    assert x.failure_class("failed") == "code error"
