"""S-Fixtures: the permitted test seams are documented, asserted and loopback-only."""
from __future__ import annotations

import asyncio
import subprocess
import sys
import urllib.request

import pytest

from api.data.attention import x_proxy as p
from api.tests.data.attention import fixture_seams as seams
from api.tests.data.attention import proxy_child_fixture as child
from api.tests.data.attention.proxy_wire_fixture import HOSTS, fixture, verified_context


def test_permitted_and_forbidden_seams_are_closed_and_disjoint():
    assert set(seams.PERMITTED_SEAMS) == {
        "temporary_paths", "clock_and_wait", "memory_rss_inspector", "acl_inspector",
        "spawn_launcher", "resolver_answer_source", "relay_dialer", "synthetic_trust_roots",
        "transaction_id_parser"}
    assert {"run_unit", "search_raw_dispatch", "pool_selection", "reader_bootstrap_request",
            "relay_policy", "browser_host", "cdp_client", "browser_selftest"} == set(seams.FORBIDDEN_REPLACEMENTS)
    assert not set(seams.PERMITTED_SEAMS) & set(seams.FORBIDDEN_REPLACEMENTS)
    seams.require_permitted("relay_dialer")
    with pytest.raises(AssertionError):
        seams.require_permitted("run_unit")
    with pytest.raises(AssertionError):
        seams.require_permitted("unlisted")
    assert "NOT the real transaction-ID parser" in seams.PARSER_QUALIFICATION
    assert "not a universal sandbox" in seams.NATIVE_CONTAINMENT_GAP


def test_wire_hosts_include_synthetic_x_and_reddit_origins():
    assert {"x.com", seams.X_STATIC_ORIGIN, "www.reddit.com", "gql-fed.reddit.com",
            seams.REDDIT_FEED_ORIGIN} <= HOSTS
    assert set(seams.SYNTHETIC_HOSTS) <= HOSTS


def test_synthetic_resolver_runs_real_public_policy():
    resolve = seams.synthetic_resolver({"www.reddit.com": seams.SYNTHETIC_PUBLIC_TOKEN})
    assert asyncio.run(resolve("www.reddit.com", 443)) == seams.SYNTHETIC_PUBLIC_TOKEN
    with pytest.raises(AssertionError):
        asyncio.run(resolve("unlisted.test", 443))
    for literal in ("127.0.0.1", "10.0.0.1", "169.254.1.1", "224.0.0.1", "::1"):
        bad = seams.synthetic_resolver({"www.reddit.com": literal})
        with pytest.raises(p.ProxyFailure):
            asyncio.run(bad("www.reddit.com", 443))


def test_fixture_dialer_maps_only_the_exact_token_to_loopback():
    with fixture() as wire:
        dialer = seams.FixtureDialer({seams.SYNTHETIC_PUBLIC_TOKEN: ("127.0.0.1", wire.origin_port)})
        sock = dialer.dial(seams.SYNTHETIC_PUBLIC_TOKEN, 443, timeout=5)
        try:
            context = verified_context(wire.certs["origin"]["root"])
            with context.wrap_socket(sock, server_hostname="www.reddit.com") as tls:
                tls.sendall(b"GET /r/x/new HTTP/1.1\r\nHost: www.reddit.com\r\nConnection: close\r\n\r\n")
                assert tls.recv(64).startswith(b"HTTP/1.1 200")
        finally:
            sock.close()
        assert dialer.dialed == [(seams.SYNTHETIC_PUBLIC_TOKEN, 443)]
        assert wire.origin_sni == ["www.reddit.com"]
        for other in ("93.184.216.35", "127.0.0.1", "www.reddit.com"):
            with pytest.raises(AssertionError):
                dialer.dial(other, 443, timeout=5)


def test_fake_clock_advances_only_by_injected_waits():
    clock = seams.FakeClock(1000.0)
    asyncio.run(clock.wait(2.5))
    clock.sleep(0.5)
    assert clock.now() == 1003.0 and clock.waits == [2.5, 0.5]
    with pytest.raises(AssertionError):
        clock.sleep(-1)


def test_scripted_inspector_and_launcher():
    inspector = seams.ScriptedInspector([10, 20])
    assert inspector() == 10 and inspector("x") == 20
    with pytest.raises(AssertionError):
        inspector()
    assert seams.spawn_launcher("api.tests.data.attention.proxy_child_fixture", "{}") == [
        sys.executable, "-m", "api.tests.data.attention.proxy_child_fixture", "{}"]


def test_openssl_preflight_fails_never_skips(monkeypatch):
    assert seams.openssl_binary()
    monkeypatch.setattr(seams.shutil, "which", lambda name: None)
    monkeypatch.setattr(seams, "GIT_OPENSSL", seams.Path("Z:/missing/openssl.exe"))
    with pytest.raises(AssertionError, match="OpenSSL"):
        seams.openssl_binary()


def test_spawned_network_denial_guard():
    code = (
        "import socket\n"
        "from api.tests.data.attention import fixture_seams as s\n"
        "s.install_network_denial()\n"
        "out = []\n"
        "for target in (lambda: socket.getaddrinfo('denied.test', 443),\n"
        "               lambda: socket.create_connection(('93.184.216.34', 443), timeout=1)):\n"
        "    try:\n"
        "        target(); out.append('allowed')\n"
        "    except s.NetworkDenied:\n"
        "        out.append('denied')\n"
        "server = socket.socket(); server.bind(('127.0.0.1', 0)); server.listen(1)\n"
        "socket.create_connection(server.getsockname(), timeout=1).close()\n"
        "out.append('loopback')\n"
        "print(','.join(out))\n")
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "denied,denied,loopback"


def test_fake_x_cookie_recorder_reports_duplicate_ct0():
    with fixture() as wire:
        recorder = child.FakeXCookies(wire)
        context = verified_context(wire.certs["origin"]["root"])
        def get(cookies):
            request = urllib.request.Request(wire.origin_url + "/i/api/graphql/x/SearchTimeline")
            for value in cookies:
                request.add_header("Cookie", value)
            opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context))
            with seams.loopback_resolution():
                with opener.open(request, timeout=5) as response:
                    response.read()
        get(["ct0=a; auth_token=t"])
        get(["ct0=a; ct0=b"])
        assert recorder.cookie_headers() == [["ct0=a; auth_token=t"], ["ct0=a; ct0=b"]]
        assert recorder.duplicate_ct0() == [1]
    assert child.ct0_count(["ct0=a", "x=1; ct0=b"]) == 2
    assert child.ct0_count([]) == 0


def test_child_envelope_v2_query_id_option_is_validated():
    assert child.expected_query_id({}) is None
    assert child.expected_query_id({"query_id": "AbCdEfGhIjKlMnOp_1"}) == "AbCdEfGhIjKlMnOp_1"
    for bad in ("short", "x" * 33, "bad id with space!", 7):
        with pytest.raises(AssertionError):
            child.expected_query_id({"query_id": bad})
