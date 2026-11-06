"""B2 E1/E2 parser boundaries. Synthetic bytes only; never resolve or send."""
from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from uuid import UUID

import pytest

from api.data.attention import web_queries as wq, x_proxy as p

NOW = datetime(2026, 11, 4, 12, tzinfo=UTC)
ID1, ID2 = str(UUID(int=1)), str(UUID(int=2))


def policy_doc(root):
    return {"version": 1, "allowed_origins": ["https://echo.example", "https://baseline.example",
        "https://www.spamhaus.org", "https://raw.githubusercontent.com", "https://ipapi.co"],
        "echo": {"url": "https://echo.example/ip", "response_format": "json-ip"},
        "baseline": {"url": "https://baseline.example/plain", "sha256": "a" * 64},
        "metadata_provider": None, "service_sid": "S-1-5-21-1-2-3-1001", "cache_dir": str(root / "cache")}


def assignment_doc():
    return {"version": 1, "lines": {ID1: 1, ID2: 2}, "accounts": {
        "alpha": {"proxy_id": ID1, "expected_ip": "8.8.8.8", "region": "US", "timezone": "America/New_York", "accept_language": "en-US"},
        "beta": {"proxy_id": ID2, "expected_ip": "1.1.1.1", "region": "AU", "timezone": "Australia/Sydney", "accept_language": "en-AU"}}}


def test_policy_roundtrip_fixed_sources_and_no_provider_default(tmp_path):
    doc = policy_doc(tmp_path)
    policy = p.parse_policy(json.dumps(doc).encode(), tmp_path)
    assert policy.metadata_provider is None
    assert policy.echo == doc["echo"]["url"] and policy.private_root == tmp_path
    for url in (p.SPAMHAUS, p.FIREHOL):
        policy.validate_url(url)
    with pytest.raises(p.ProxyFailure):
        policy.validate_url("https://echo.example.evil.test/ip")


@pytest.mark.parametrize("key,value", [("version", True), ("version", 2), ("metadata_provider", "reputation"),
    ("service_sid", "S-1-5-4294967296"), ("service_sid", "S-1-281474976710656-1"),
    ("service_sid", "S-1-05-1"), ("cache_dir", "relative"), ("allowed_origins", []),
    ("allowed_origins", ["https://echo.example", "https://ECHO.example:443/"])])
def test_policy_rejects_wrong_types_values_and_normalized_duplicates(tmp_path, key, value):
    doc = policy_doc(tmp_path)
    doc[key] = value
    with pytest.raises(p.ProxyFailure):
        p.parse_policy(json.dumps(doc).encode(), tmp_path)


@pytest.mark.parametrize("slot,key,value", [("echo", "response_format", "text"), ("echo", "url", "http://echo.example/ip"),
    ("echo", "url", "https://user:SECRET@echo.example/ip"), ("baseline", "sha256", "A" * 64),
    ("baseline", "url", "https://baseline.example/plain#fragment"), ("baseline", "extra", True)])
def test_nested_policy_exact_keys_and_no_credentials(tmp_path, slot, key, value):
    doc = policy_doc(tmp_path)
    doc[slot][key] = value
    with pytest.raises(p.ProxyFailure) as error:
        p.parse_policy(json.dumps(doc).encode(), tmp_path)
    assert "SECRET" not in str(error.value)


@pytest.mark.parametrize("slot", [None, "echo", "baseline"])
def test_unknown_and_missing_policy_keys_fail(tmp_path, slot):
    for action in ("add", "remove"):
        doc = policy_doc(tmp_path)
        target = doc if slot is None else doc[slot]
        if action == "add":
            target["unknown"] = "SECRET"
        else:
            target.pop(next(iter(target)))
        with pytest.raises(p.ProxyFailure):
            p.parse_policy(json.dumps(doc).encode(), tmp_path)


def test_cache_escape_and_fixed_source_origin_required(tmp_path):
    doc = policy_doc(tmp_path)
    doc["cache_dir"] = str(tmp_path / ".." / "escaped")
    with pytest.raises(p.ProxyFailure):
        p.parse_policy(json.dumps(doc).encode(), tmp_path)
    doc = policy_doc(tmp_path)
    doc["allowed_origins"].remove("https://www.spamhaus.org")
    with pytest.raises(p.ProxyFailure):
        p.parse_policy(json.dumps(doc).encode(), tmp_path)


def test_sticky_assignment_reorder_and_unassigned_spare():
    doc = assignment_doc()
    routes = b"https://first.example:443\nhttps://second.example:443\nhttp://spare.example:8080\n"
    before = p.parse_assignments(json.dumps(doc).encode(), routes, ("alpha", "beta"), required=True)
    doc["lines"] = {ID1: 2, ID2: 1, str(UUID(int=3)): 3}
    after = p.parse_assignments(json.dumps(doc).encode(), b"https://second.example:443\nhttps://first.example:443\nhttp://spare.example:8080\n", ("alpha", "beta"), required=True)
    assert before == after
    doc["accounts"]["alpha"]["proxy_id"] = str(UUID(int=3))
    replaced = p.parse_assignments(json.dumps(doc).encode(), routes, ("alpha", "beta"), required=True)
    assert replaced["alpha"].proxy_id == str(UUID(int=3))
    assert replaced["beta"].proxy_id == ID2


@pytest.mark.parametrize("mutation", ["duplicate_line", "duplicate_id", "duplicate_ip", "mapped_duplicate_ip", "missing", "unknown", "removed", "bool_line", "empty_url", "unknown_entry", "bad_timezone", "bad_language", "duplicate_key"])
def test_assignment_refusals(mutation):
    doc = assignment_doc()
    routes = b"https://first.example\nhttps://second.example\n"
    if mutation == "duplicate_line": doc["lines"][ID2] = 1
    if mutation == "duplicate_id": doc["accounts"]["beta"]["proxy_id"] = ID1
    if mutation == "duplicate_ip": doc["accounts"]["beta"]["expected_ip"] = "8.8.8.8"
    if mutation == "mapped_duplicate_ip": doc["accounts"]["beta"]["expected_ip"] = "::ffff:8.8.8.8"
    if mutation == "missing": del doc["accounts"]["alpha"]
    if mutation == "unknown": doc["accounts"]["unknown"] = doc["accounts"].pop("alpha")
    if mutation == "removed": del doc["lines"][ID1]
    if mutation == "bool_line": doc["lines"][ID1] = True
    if mutation == "empty_url": routes = b"https://first.example\n\n"
    if mutation == "unknown_entry": doc["accounts"]["alpha"]["url"] = "https://SECRET"
    if mutation == "bad_timezone": doc["accounts"]["alpha"]["timezone"] = "missing/timezone"
    if mutation == "bad_language": doc["accounts"]["alpha"]["accept_language"] = "en\r\nSECRET: x"
    body = json.dumps(doc).encode()
    if mutation == "duplicate_key": body = body.replace(b'"version": 1', b'"version":1,"version":1')
    with pytest.raises(p.ProxyFailure) as error:
        p.parse_assignments(body, routes, ("alpha", "beta"), required=True)
    assert "SECRET" not in str(error.value)


def test_identity_coherence_is_checked_even_for_sticky_id():
    doc = assignment_doc()
    with pytest.raises(p.ProxyFailure, match="proxy_region"):
        p.parse_assignments(json.dumps(doc).encode(), b"https://first.example\nhttps://second.example\n",
            ("alpha", "beta"), required=True, identities={"alpha": {"region": "GB", "timezone": "Europe/London", "accept_language": "en-GB"}})


def spamhaus(now=NOW, *, age=1, expiry=1):
    return (f"; Last-Modified: {format_datetime(now - timedelta(hours=age))}\n"
            f"; Expires: {format_datetime(now + timedelta(hours=expiry))}\n"
            "9.0.0.0/24 ; SBL12345\n").encode()


def firehol(now=NOW, *, age=1, count=2):
    return (f"# This File Date: {format_datetime(now - timedelta(hours=age))}\n"
            f"# Source File Date: {format_datetime(now - timedelta(hours=48))}\n"
            f"# Entries: {count}\n9.0.0.0/24\n2001:4860::1\n").encode()


@pytest.mark.parametrize("slot,body", [("spamhaus", spamhaus()), ("firehol", firehol())])
def test_feed_body_clocks_membership_and_source_tuple(slot, body):
    feed = p.parse_feed(slot, body, NOW)
    assert feed.contains("9.0.0.1") and not feed.contains("8.8.8.8")
    assert NOW < feed.expires_at <= NOW + timedelta(hours=23)
    assert feed.source_version


@pytest.mark.parametrize("slot,body", [("spamhaus", spamhaus(age=25)), ("spamhaus", spamhaus(age=-1)),
    ("spamhaus", spamhaus(expiry=-1)), ("spamhaus", b"9.0.0.0/24 ; SBL123\n"),
    ("spamhaus", spamhaus().replace(b"SBL12345", b"INVALID")),
    ("firehol", firehol(age=25)), ("firehol", firehol(age=-1)), ("firehol", firehol(count=1)),
    ("firehol", firehol().replace(b"Source File Date:", b"Ignored Date:")),
    ("firehol", firehol().replace(b"9.0.0.0/24", b"9.0.0.1/24")),
    ("firehol", firehol() + b"#" + b"x" * 4096),
    ("firehol", firehol() + b"\xff")])
def test_feed_malformed_stale_future_and_line_bounds(slot, body):
    with pytest.raises(p.ProxyFailure):
        p.parse_feed(slot, body, NOW)


def test_feed_entry_ceiling_before_membership_allocation_grows():
    body = firehol(count=50001).split(b"9.0.0.0/24")[0] + b"9.0.0.1\n" * 50001
    with pytest.raises(p.ProxyFailure):
        p.parse_feed("firehol", body, NOW)


@pytest.mark.parametrize("over", [{"x_proxy_required": 1}, {"x_proxy_list_path": ""},
    {"x_proxy_list_path": "relative"}, {"x_proxy_list_path": "/absolute"},
    {"x_proxy_required": True}, {"x_proxy_admission_max_age_seconds": True},
    {"x_proxy_admission_max_age_seconds": 86401}, {"x_proxy_health_interval_seconds": 3599},
    {"x_proxy_health_interval_seconds": 86401}, {"x_proxy_quarantine_seconds": 0}])
def test_public_optional_config_strictness(over):
    with pytest.raises(wq.QueriesError):
        wq.validate_config({**wq.DEFAULTS, **over})


def test_public_config_off_defaults_and_roundtrip(tmp_path):
    off = wq.validate_config(dict(wq.DEFAULTS))
    assert off.x_proxy_required is False and off.x_proxy_policy_path is None
    configured = wq.validate_config({**wq.DEFAULTS, "x_proxy_required": True,
        "x_proxy_list_path": str(tmp_path / "list"), "x_proxy_assignments_path": str(tmp_path / "assignments"),
        "x_proxy_policy_path": str(tmp_path / "policy"), "x_proxy_admission_max_age_seconds": 1,
        "x_proxy_health_interval_seconds": 86400, "x_proxy_quarantine_seconds": 1})
    assert wq.validate_config(configured.as_dict()) == configured


def test_query_file_bound_is_enforced_before_json_parsing(tmp_path):
    path = tmp_path / "oversized-queries.json"
    path.write_bytes(b" " * (1024 * 1024 + 1))
    with pytest.raises(wq.QueriesError, match="exceeds 1 MiB"):
        wq.load(path)
