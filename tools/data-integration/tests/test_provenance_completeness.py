"""T63: provenance completeness (F1), honest headers (F2), size caps (F3), cache key (F4)."""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import version

import pytest

from data_integration import fetch_tier1, status as st
from data_integration.approvals import ApprovalStore
from data_integration.fetch_tier1 import fetch
from data_integration.gate import FetchPass, request_access
from data_integration.normalise import normalise
from data_integration.parse import PARSER_VERSION, parse_table
from data_integration.pipeline import run
from data_integration.politeness import USER_AGENT, Politeness
from data_integration.provenance import build_record, provenance_path, read_records
from data_integration.response_cache import ResponseCache
from data_integration.robots import ROBOTS_MAX_BYTES
from _helpers import fixed_clock, make_record
from fixture_server import OK_BODY
from pathlib import Path

PRICES = (Path(__file__).parent / "fixtures" / "ok.html").read_bytes()

HOSTS = ("example.test",)
URL = "http://example.test/data/ok"
NOW = datetime(2026, 1, 10, 12, tzinfo=timezone.utc)


class _Big(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_GET(self):
        srv = self.server
        srv.seen.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}})
        if self.path.endswith("/robots.txt"):
            body = srv.robots
        else:
            body = srv.page
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def fixture_server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Big)
    httpd.daemon_threads = True
    httpd.seen, httpd.robots, httpd.page = [], b"User-agent: *\nAllow: /\n", OK_BODY
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    httpd.proxy_url = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture
def store(tmp_path):
    s = ApprovalStore(tmp_path / "ap")
    s.write(make_record(tier=1, hosts=HOSTS, pages=("/data/",), id="source-20261014", revision=3))
    return s


@pytest.fixture
def real_pass(store):
    p = request_access("example-src", 1, store, fixed_clock())
    assert isinstance(p, FetchPass)
    return p


def _go(server, pass_, url=URL, **kw):
    kw.setdefault("politeness", Politeness(min_delay=0, sleeper=lambda s: None))
    return fetch(url, pass_, proxy=server.proxy_url, **kw)


# ---- F1
def test_request_access_pass_carries_approval_facts(real_pass, store, fixture_server):
    rec = store.read("example-src")
    assert real_pass.approval_id == "source-20261014" == rec.id
    assert real_pass.approval_revision == rec.revision and isinstance(real_pass.approval_revision, int)
    assert real_pass.approved == rec.approved and real_pass.expires == rec.expiry


def test_fetch_outcome_carries_body_sha256(fixture_server, real_pass):
    out = _go(fixture_server, real_pass)
    assert out.status == st.OK and out.body_sha256 == hashlib.sha256(OK_BODY).hexdigest()


def test_record_has_new_typed_fields(real_pass, store, fixture_server):
    df = normalise(parse_table(PRICES, "table.prices"), "synthetic")
    sha = hashlib.sha256(OK_BODY).hexdigest()
    rec = build_record(real_pass, URL, df, NOW, sha)
    rec_ref = store.read("example-src")
    assert rec["response_sha256"] == sha and len(sha) == 64
    assert rec["scrapling_version"] == version("scrapling") and isinstance(rec["scrapling_version"], str)
    assert rec["parser_version"] == PARSER_VERSION == "dit-parse-1"
    assert rec["approval_id"] == rec_ref.id and rec["approval_revision"] == rec_ref.revision
    assert rec["approved"] == rec_ref.approved and rec["expires"] == rec_ref.expiry
    assert rec["source"] == "example-src" and rec["tier"] == 1
    json.dumps(rec)


def test_pipeline_writes_complete_provenance(fixture_server, real_pass, store):
    class F:
        def fetch(self, url, pass_):
            return _go(fixture_server, pass_, url)

    fixture_server.page = PRICES
    res = run(F(), real_pass, url=URL, selector="table.prices", symbol="T63-X", timeframe="1d", clock=fixed_clock(NOW),
              accept_baseline=True, adaptive_path=None)
    assert res.status == st.OK, res
    recs = read_records("T63-X", "1d")
    assert len(recs) == 1
    assert recs[0]["response_sha256"] == hashlib.sha256(fixture_server.page).hexdigest()
    assert recs[0]["approval_id"] == "source-20261014" and recs[0]["approval_revision"] == store.read("example-src").revision
    assert provenance_path("T63-X", "1d").is_file()


# ---- F2
def test_request_has_no_referer_and_only_honest_ua(fixture_server, real_pass):
    assert _go(fixture_server, real_pass).status == st.OK
    assert fixture_server.seen
    for req in fixture_server.seen:
        assert "referer" not in req["headers"]
        assert req["headers"]["user-agent"] == USER_AGENT


# ---- F3
def test_oversized_robots_fails_closed(fixture_server, real_pass):
    fixture_server.robots = b"User-agent: *\nAllow: /\n" + b"# " + b"x" * ROBOTS_MAX_BYTES + b"\n"
    out = _go(fixture_server, real_pass)
    assert out.status == st.ROBOTS_BLOCKED and "too large" in out.detail
    assert all(r["path"].endswith("robots.txt") for r in fixture_server.seen)


def test_oversized_page_gets_closed_status(fixture_server, real_pass):
    fixture_server.page = b"x" * 2048
    out = _go(fixture_server, real_pass, max_body_bytes=1024)
    assert out.status == st.HTTP_ERROR and "too large" in out.detail and out.body == b""
    assert st.is_status(out.status)


def test_page_cap_default_and_at_cap_ok(fixture_server, real_pass):
    assert fetch_tier1.DEFAULT_MAX_BODY_BYTES == 5 * 1024 * 1024 and ROBOTS_MAX_BYTES == 512 * 1024
    assert _go(fixture_server, real_pass, max_body_bytes=len(OK_BODY)).status == st.OK


# ---- F4
def test_cache_key_separates_tiers(tmp_path, fixture_server):
    t1, t2 = ResponseCache(tmp_path / "rc", tier=1), ResponseCache(tmp_path / "rc", tier=2)
    t1.put(URL, 200, b"tier-one")
    assert t2.get(URL) is None
    t2.put(URL, 200, b"tier-two")
    assert t1.get(URL).body == b"tier-one" and t2.get(URL).body == b"tier-two"
    assert t1._key(URL, 1) != t1._key(URL, 2)
    assert t1._key(URL, 1) != t1._key(URL + "x", 1)
