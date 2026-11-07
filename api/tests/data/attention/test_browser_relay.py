"""S-Relay A5-A9 acceptance on loopback fixtures (A6b seams only: dialer + resolver answers)."""
from __future__ import annotations

import base64
import json
import socket
import socketserver
import ssl
import threading
import time
from types import SimpleNamespace

import pytest

from api.data.attention import browser_relay as r
from api.data.attention import x_proxy as p
from api.tests.data.attention.fixture_seams import SYNTHETIC_PUBLIC_TOKEN, FixtureDialer, synthetic_resolver
from api.tests.data.attention.proxy_wire_fixture import fixture, verified_context

PROXY_TOKEN = "93.184.216.35"
REDDIT = "www.reddit.com"


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class Gate:
    """Mutable route admission snapshot."""
    def __init__(self, clock):
        self.value = r.Admission("rev-1", expires_at=100.0)

    def __call__(self):
        return self.value


class NumericProxy:
    """Fake upstream CONNECT proxy: records the numeric authority and reaches the origin listener."""

    def __init__(self, origin_port, *, tls=None):
        self.connects, owner = [], self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                conn = self.request
                conn.settimeout(5)
                head = b""
                while b"\r\n\r\n" not in head:
                    chunk = conn.recv(1)
                    if not chunk:
                        return
                    head += chunk
                rows = head[:-4].split(b"\r\n")
                headers = dict(row.decode().split(": ", 1) for row in rows[1:])
                owner.connects.append({"line": rows[0].decode(), "headers": headers})
                upstream = socket.create_connection(("127.0.0.1", origin_port), timeout=5)
                conn.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
                pump = threading.Thread(target=_pump, args=(upstream, conn), daemon=True)
                pump.start()
                _pump(conn, upstream)
                pump.join(5)

        class Server(socketserver.ThreadingTCPServer):
            daemon_threads = True

            def get_request(self):
                sock, address = super().get_request()
                return (tls.wrap_socket(sock, server_side=True) if tls else sock), address

        self.server = Server(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def _pump(src, dst):
    try:
        while data := src.recv(65536):
            dst.sendall(data)
    except OSError:
        pass
    finally:
        try:
            dst.shutdown(socket.SHUT_WR)
        except OSError:
            pass


@pytest.fixture
def wire():
    with fixture() as w:
        yield w


def relay_for(wire, mode="direct", *, answers=None, route=None, dialer=None, clock=None, gate=None, **kw):
    clock = clock or Clock()
    gate = gate or Gate(clock)
    dialer = dialer or FixtureDialer({SYNTHETIC_PUBLIC_TOKEN: ("127.0.0.1", wire.origin_port)})
    resolver = synthetic_resolver(answers or {REDDIT: SYNTHETIC_PUBLIC_TOKEN, "x.com": SYNTHETIC_PUBLIC_TOKEN})
    relay = r.Relay("reddit", "acct1", mode, revision="rev-1", admission=gate, route=route,
                    resolver=resolver, dialer=dialer, clock=clock, **kw)
    relay.start()
    return relay, dialer, gate, clock


def connect(port, authority: bytes, line=None):
    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    sock.sendall(line or b"CONNECT " + authority + b" HTTP/1.1\r\nHost: " + authority + b"\r\n\r\n")
    head = b""
    while b"\r\n\r\n" not in head:
        chunk = sock.recv(1)
        if not chunk:
            break
        head += chunk
    return sock, head.split(b"\r\n", 1)[0]


def fetch(port, wire, host=REDDIT, root=None):
    sock, status = connect(port, host.encode() + b":443")
    assert status.startswith(b"HTTP/1.1 200"), status
    context = verified_context(root or wire.certs["origin"]["root"])
    with context.wrap_socket(sock, server_hostname=host) as tls:
        tls.sendall(f"GET / HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode())
        data = b""
        while chunk := tls.recv(65536):
            data += chunk
    return data


def test_direct_allowlisted_tls_end_to_end_with_pinned_numeric_dial(wire):
    relay, dialer, *_ = relay_for(wire)
    try:
        assert r.LISTEN_HOST == "127.0.0.1"
        assert fetch(relay.port, wire).startswith(b"HTTP/1.1 200")
        assert dialer.dialed == [(SYNTHETIC_PUBLIC_TOKEN, 443)]
        assert wire.origin_sni == [REDDIT]
        assert relay.health()["forwarded"] == 1
    finally:
        relay.close()


@pytest.mark.parametrize("authority", [b"evil.example:443", b"93.184.216.34:443", b"[::1]:443", b"127.0.0.1:443",
                                       b"localhost:443", b"www.reddit.com:8443", b"user:pw@www.reddit.com:443",
                                       b"www.reddit.com", b"www.reddit.com:443:1", b"WWW.reddit.com.:443"])
def test_off_allowlist_literal_port_userinfo_and_malformed_refused_without_dial(wire, authority):
    relay, dialer, *_ = relay_for(wire)
    try:
        sock, status = connect(relay.port, authority)
        sock.close()
        assert status.startswith(b"HTTP/1.1 403")
        assert dialer.dialed == []
    finally:
        relay.close()


def test_plain_http_absolute_form_gets_405(wire):
    relay, dialer, *_ = relay_for(wire)
    try:
        for line in (b"GET http://www.reddit.com/ HTTP/1.1\r\nHost: www.reddit.com\r\n\r\n",
                     b"GET http://127.0.0.1/ HTTP/1.1\r\n\r\n"):
            sock, status = connect(relay.port, b"", line=line)
            sock.close()
            assert status.startswith(b"HTTP/1.1 405")
        assert dialer.dialed == []
    finally:
        relay.close()


@pytest.mark.parametrize("answer", ["127.0.0.1", "10.0.0.7", "192.168.1.5", "169.254.1.1", "224.0.0.1", "::1", "0.0.0.0"])
def test_private_loopback_linklocal_multicast_resolution_refused_by_real_policy(wire, answer):
    relay, dialer, *_ = relay_for(wire, answers={REDDIT: answer})
    try:
        sock, status = connect(relay.port, b"www.reddit.com:443")
        sock.close()
        assert status.startswith(b"HTTP/1.1 502")
        assert dialer.dialed == []
    finally:
        relay.close()


@pytest.mark.parametrize("https_upstream", [False, True])
def test_proxy_mode_numeric_connect_original_sni_and_relay_side_credentials(wire, https_upstream):
    tls = None
    if https_upstream:
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(str(wire.certs["proxy"]["cert"]), str(wire.certs["proxy"]["key"]))
    upstream = NumericProxy(wire.origin_port, tls=tls)
    scheme = "https://u1:s3cretpw@" if https_upstream else "http://"
    route = p.parse_proxy(f"{scheme}proxy.test:{upstream.port}")
    dialer = FixtureDialer({PROXY_TOKEN: ("127.0.0.1", upstream.port)})
    relay, *_ = relay_for(wire, "proxy", route=route, dialer=dialer,
                          answers={REDDIT: SYNTHETIC_PUBLIC_TOKEN, "proxy.test": PROXY_TOKEN},
                          proxy_context=verified_context(wire.certs["proxy"]["root"]) if https_upstream else None)
    try:
        assert fetch(relay.port, wire).startswith(b"HTTP/1.1 200")
        assert dialer.dialed == [(PROXY_TOKEN, upstream.port)]
        [seen] = upstream.connects
        assert seen["line"] == f"CONNECT {SYNTHETIC_PUBLIC_TOKEN}:443 HTTP/1.1"
        assert seen["headers"]["Host"] == f"{SYNTHETIC_PUBLIC_TOKEN}:443"
        if https_upstream:
            assert seen["headers"]["Proxy-Authorization"] == "Basic " + base64.b64encode(b"u1:s3cretpw").decode()
        else:
            assert "Proxy-Authorization" not in seen["headers"]
        assert wire.origin_sni == [REDDIT]
        assert "s3cretpw" not in json.dumps(relay.health()) and "s3cretpw" not in repr(route)
    finally:
        relay.close()
        upstream.close()


def test_hostile_origin_certificate_fails_and_hostile_proxy_certificate_refuses(wire):
    relay, *_ = relay_for(wire)
    try:
        with pytest.raises(ssl.SSLError):
            fetch(relay.port, wire, root=wire.certs["proxy"]["root"])
    finally:
        relay.close()
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(str(wire.certs["proxy"]["cert"]), str(wire.certs["proxy"]["key"]))
    upstream = NumericProxy(wire.origin_port, tls=tls)
    route = p.parse_proxy(f"https://u1:s3cretpw@proxy.test:{upstream.port}")
    relay, *_ = relay_for(wire, "proxy", route=route, dialer=FixtureDialer({PROXY_TOKEN: ("127.0.0.1", upstream.port)}),
                          answers={REDDIT: SYNTHETIC_PUBLIC_TOKEN, "proxy.test": PROXY_TOKEN},
                          proxy_context=verified_context(wire.certs["origin"]["root"]))
    try:
        sock, status = connect(relay.port, b"www.reddit.com:443")
        sock.close()
        assert status.startswith(b"HTTP/1.1 502") and upstream.connects == []
    finally:
        relay.close()
        upstream.close()


def test_upstream_failure_never_goes_direct(wire):
    route = p.parse_proxy("http://proxy.test:3128")
    dialer = FixtureDialer({SYNTHETIC_PUBLIC_TOKEN: ("127.0.0.1", wire.origin_port)})  # proxy token unmapped
    relay, *_ = relay_for(wire, "proxy", route=route, dialer=dialer,
                          answers={REDDIT: SYNTHETIC_PUBLIC_TOKEN, "proxy.test": PROXY_TOKEN})
    try:
        sock, status = connect(relay.port, b"www.reddit.com:443")
        sock.close()
        assert status.startswith(b"HTTP/1.1 502")
        assert dialer.dialed == [] and wire.origin_sni == []
    finally:
        relay.close()


@pytest.mark.parametrize("change,reason", [("expire", "proxy_admission_expired"), ("revision", "proxy_admission_expired"),
                                           ("quarantine", "proxy_quarantined")])
def test_admission_expiry_revision_quarantine_close_open_tunnels(wire, change, reason):
    relay, dialer, gate, clock = relay_for(wire)
    try:
        sock, status = connect(relay.port, b"www.reddit.com:443")
        assert status.startswith(b"HTTP/1.1 200")
        if change == "expire":
            clock.now = 100.0
        elif change == "revision":
            gate.value = r.Admission("rev-2", expires_at=100.0)
        else:
            gate.value = r.Admission("rev-1", expires_at=100.0, quarantined=True)
        sock.settimeout(5)
        deadline = time.monotonic() + 5
        closed = False
        while time.monotonic() < deadline and not closed:
            try:
                closed = sock.recv(1) == b""
            except (ConnectionError, OSError):
                closed = True
        assert closed
        assert relay.health()["failure"] == reason
        again, status = connect(relay.port, b"www.reddit.com:443")
        again.close()
        assert status.startswith(b"HTTP/1.1 502")
        assert len(dialer.dialed) == 1
    finally:
        relay.close()


def test_background_hosts_classified_and_refusal_metadata_bounded(wire):
    relay, dialer, *_ = relay_for(wire)
    try:
        for host in (b"edge.microsoft.com", b"nav-edge.smartscreen.microsoft.com", b"www.bing.com", b"mss.office.com"):
            connect(relay.port, host + b":443")[0].close()
        for i in range(60):
            connect(relay.port, f"h{i}.example:443".encode())[0].close()
        connect(relay.port, b"www.reddit.com.evil.example:443")[0].close()
        health = relay.health()
        assert set(health["background_refused"]) == {"edge.microsoft.com", "nav-edge.smartscreen.microsoft.com",
                                                     "www.bing.com", "mss.office.com"}
        assert len(health["relay_refusals"]) == r.REFUSAL_LIMIT and health["refused_other"] == 11
        assert all("/" not in h for h in health["relay_refusals"])
        assert dialer.dialed == []
    finally:
        relay.close()


def test_mode_predicate_and_refuse_mode():
    direct = SimpleNamespace(x_proxy_required=False, x_proxy_list_path=None, x_proxy_assignments_path=None,
                             x_proxy_policy_path=None)
    route = p.parse_proxy("http://proxy.test:3128")
    full = SimpleNamespace(x_proxy_required=True, x_proxy_list_path="C:/a", x_proxy_assignments_path="C:/b",
                           x_proxy_policy_path="C:/c")
    partial = SimpleNamespace(x_proxy_required=False, x_proxy_list_path="C:/a", x_proxy_assignments_path=None,
                              x_proxy_policy_path=None)
    assert r.select_mode(direct) == "direct"
    assert r.select_mode(full, route=route, admitted=True) == "proxy"
    assert r.select_mode(full, route=route, admitted=False) == "refuse"
    assert r.select_mode(full, route=None, admitted=True) == "refuse"
    assert r.select_mode(partial, route=route, admitted=True) == "refuse"
    assert r.select_mode(SimpleNamespace()) == "refuse"
    with pytest.raises(r.RelayFailure, match="proxy_not_admitted"):
        r.Relay("reddit", "a", "refuse", revision="r", admission=lambda: None)
    with pytest.raises(r.RelayFailure, match="proxy_not_admitted"):
        r.Relay("reddit", "a", "proxy", revision="r", admission=lambda: None)


def test_health_file_shape(wire, tmp_path):
    relay, *_ = relay_for(wire)
    try:
        connect(relay.port, b"evil.example:443")[0].close()
        r.write_health(tmp_path, relay, profile_state="ok")
    finally:
        relay.close()
    data = json.loads((tmp_path / "attention" / "_pc_state" / "browser_health.json").read_text())
    assert data == {"relay_refusals": {"evil.example": 1}, "background_refused": {}, "profile_state": "ok"}


def test_spawned_fake_browser_loads_only_through_relay(wire, tmp_path):
    from api.tests.data.attention.test_browser_host import host
    relay, dialer, *_ = relay_for(wire)
    script = tmp_path / "script.json"
    pages = {f"https://{h}/": {"wire": True} for h in (REDDIT, "evil.example", "edge.microsoft.com")}
    script.write_text(json.dumps({"ca_file": str(wire.certs["origin"]["root"]), "pages": pages}))
    b = host(tmp_path)
    original = b.spawn
    b.spawn = lambda argv: original(argv + [f"--fake-script={script}"])
    try:
        with b.launch("a", "a", relay.port) as session:
            results = []
            for i, url in enumerate(pages, 1):
                session.pipe.send(json.dumps({"id": i, "method": "Page.navigate", "params": {"url": url}}).encode())
                while True:
                    message = json.loads(session.pipe.receive(timeout=10))
                    if message.get("id") == i:
                        results.append(message["result"])
                        break
        assert "frameId" in results[0]
        assert results[1] == results[2] == {"errorText": "fixture_route_failed"}
        health = relay.health()
        assert health["relay_refusals"] == {"evil.example": 1}
        assert health["background_refused"] == {"edge.microsoft.com": 1}
        assert dialer.dialed == [(SYNTHETIC_PUBLIC_TOKEN, 443)]
    finally:
        relay.close()
