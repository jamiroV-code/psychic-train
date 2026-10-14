"""One structured line per request; no headers, cookies, query strings or IPs."""
from __future__ import annotations

import logging

from data_integration.logging_setup import LOGGER_NAME, log_request


def test_one_line_with_expected_fields(caplog):
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        log_request("a.example.test", "/data/ok", 200, 0.1234, 1)
    assert len(caplog.records) == 1
    line = caplog.records[0].getMessage()
    for part in ("host=a.example.test", "path=/data/ok", "status=200", "duration_ms=123", "tier=1"):
        assert part in line
    assert "\n" not in line


def test_query_string_and_fragment_are_dropped(caplog):
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        log_request("a.example.test", "/data/ok?token=sekret123&k=v#frag", 200, 0.01, 1)
    line = caplog.records[0].getMessage()
    assert "sekret123" not in line and "token" not in line and "?" not in line and "#" not in line


def test_ip_literal_hosts_are_redacted(caplog):
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        log_request("10.1.2.3", "/data/ok", 200, 0.01, 1)
        log_request("[::1]", "/data/ok", 200, 0.01, 1)
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "10.1.2.3" not in text and "::1" not in text


def test_control_characters_cannot_forge_extra_lines(caplog):
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        log_request("a.example.test", "/x\nINFO forged status=200", 200, 0.01, 1)
    assert "\n" not in caplog.records[0].getMessage()
