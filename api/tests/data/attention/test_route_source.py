"""D-33 route source feeder: loopback fake public lists and fake CONNECT proxies, synthetic TLS roots only.

Every dial goes through the injected `Net.dial`, which maps synthetic public tokens to loopback listeners and refuses
anything else; a socket-level guard additionally refuses any non-loopback connect. No list host, provider, X or
Reddit is contacted. The produced files are then read by the REAL B2 loaders (`load_snapshot`/`parse_assignments`)
and admitted by the REAL `ProxyRuntime.admit` with only its documented `request` seam synthetic.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import ipaddress
import json
import select
import socket
import socketserver
import ssl
import threading
import time
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path

import pytest

from api.data.attention import route_source as rs, web_queries as wq, x_proxy as p
from api.data.attention import x_proxy_runtime as runtime, x_proxy_snapshot as snapshot
from api.data.attention.x_proxy_private import atomic_bytes, atomic_json
from api.scripts import collector_doctor as doctor, route_feeder
from api.tests.data.attention.proxy_wire_fixture import certificates, verified_context
from api.tests.data.attention.test_x_proxy_policy import firehol, spamhaus
from api.tests.data.attention.test_x_proxy_snapshot import fixture_open, query_document

NOW = datetime(2026, 11, 9, 12, tzinfo=UTC)
SID = "S-1-5-21-1-2-3-1001"
BASELINE = b"route-source baseline page\n"
TOKEN = "93.184.216.34"  # synthetic public-class proxy host; never dialed, mapped to loopback
LIST_HOST = "raw.githubusercontent.com"
OWNER_ID = "00000000-0000-0000-0000-0000000000b2"
OWNER_LINE = "https://user:SYNTHETIC_CREDENTIAL_MARKER@owner.example:8443"
GEO = {"8.8.8.8": ("US", "America/New_York"), "8.8.4.4": ("US", "America/New_York"),
       "4.2.2.2": ("US", "America/New_York"), "4.2.2.3": ("US", "America/New_York"),
       "81.2.69.142": ("GB", "Europe/London"), "1.0.0.1": ("AU", "Australia/Sydney"),
       "1.0.0.2": ("AU", "Australia/Sydney")}
SITE_PAGE = b"<!doctype html><html><head><title>landing</title></head><body>public landing page</body></html>"
IDENTITIES = {
    "alpha": {"accept_language": "en-US", "region": "US", "timezone": "America/New_York",
              "user_agent": "Mozilla/5.0 Chrome/131.0.0.0 Safari/537.36", "impersonation_target": "chrome131"},
    "beta": {"accept_language": "en-AU", "region": "AU", "timezone": "Australia/Sydney",
             "user_agent": "Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36", "impersonation_target": "chrome120"},
}


# --- loopback fixture ------------------------------------------------------------------------------------------------

def _read_head(sock) -> bytes:
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError
        data += chunk
    return data


class _Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = False
    request_queue_size = 128

    def handle_error(self, request, client_address):
        pass


class World:
    """One TLS origin (echo, baseline, ipapi, list host) plus fake public proxies, all on 127.0.0.1."""

    def __init__(self, certs):
        self.certs = certs
        self.lists = {}
        self.redirects = {}
        self.blocked = {}  # exit ip -> (status, body) the target site landing page answers through that exit
        self.timeouts = []
        self.dials = []
        self.servers = []
        self.routes = {}  # (host, port) -> loopback port
        world = self
        origin_tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        origin_tls.load_cert_chain(str(certs["origin"]["cert"]), str(certs["origin"]["key"]))
        self.mitm_tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.mitm_tls.load_cert_chain(str(certs["proxy"]["cert"]), str(certs["proxy"]["key"]))

        class Origin(socketserver.BaseRequestHandler):
            def handle(self):
                sock = self.request
                sock.settimeout(5)
                preface = b""
                while not preface.endswith(b"\n"):
                    preface += sock.recv(1)
                exit_ip = preface[5:-1].decode()
                with origin_tls.wrap_socket(sock, server_side=True) as tls:
                    head = _read_head(tls).decode("latin-1").split("\r\n")
                    path = head[0].split(" ")[1]
                    host = next(line.split(":", 1)[1].strip() for line in head[1:] if line.lower().startswith("host:"))
                    status, body, extra = world.respond(host, path, exit_ip)
                    tls.sendall(f"HTTP/1.1 {status} X\r\ncontent-length: {len(body)}\r\nconnection: close\r\n{extra}"
                                f"\r\n".encode() + body)

        self.origin = _Server(("127.0.0.1", 0), Origin)
        self._start(self.origin)
        self.routes[(LIST_HOST, 443)] = ("direct", self.origin.server_address[1])

    def respond(self, host, path, exit_ip):
        if host == "origin.test" and path == "/ip":
            return 200, json.dumps({"ip": exit_ip}).encode(), ""
        if host == "origin.test" and path == "/plain":
            return 200, BASELINE, ""
        if host == "ipapi.co" and path == "/json/" and exit_ip in GEO:
            country, zone = GEO[exit_ip]
            return 200, json.dumps({"ip": exit_ip, "country_code": country, "region_code": "XX",
                                    "timezone": zone}).encode(), ""
        if host in ("x.com", "www.reddit.com") and path == "/":
            if exit_ip in self.blocked:
                status, body = self.blocked[exit_ip]
                return status, body, ""
            return 200, SITE_PAGE, ""
        if host == LIST_HOST and path in self.redirects:
            return 302, b"", f"location: {self.redirects[path]}\r\n"
        if host == LIST_HOST and path in self.lists:
            return 200, self.lists[path].encode(), ""
        return 404, b"", ""

    def _start(self, server):
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.servers.append(server)

    def proxy(self, port: int, kind: str = "good", exits=("8.8.8.8",)) -> str:
        """A fake public proxy reachable as TOKEN:port; returns its list line."""
        origin_port = self.origin.server_address[1]
        mitm = self.mitm_tls
        counter = {"n": 0}

        class Proxy(socketserver.BaseRequestHandler):
            def handle(self):
                sock = self.request
                sock.settimeout(5)
                _read_head(sock)
                if kind == "noconnect":
                    sock.sendall(b"HTTP/1.1 405 Method Not Allowed\r\ncontent-length: 0\r\n\r\n")
                    return
                sock.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
                if kind == "mitm":
                    with contextlib.suppress(OSError, ssl.SSLError):
                        mitm.wrap_socket(sock, server_side=True).recv(1)
                    return
                exit_ip = exits[counter["n"] % len(exits)]
                counter["n"] += 1
                with socket.create_connection(("127.0.0.1", origin_port), timeout=5) as up:
                    up.sendall(f"EXIT {exit_ip}\n".encode())
                    pipe(sock, up)

        if kind == "dead":
            with socket.socket() as hole:
                hole.bind(("127.0.0.1", 0))
                self.routes[(TOKEN, port)] = ("proxy", hole.getsockname()[1])
        elif kind == "hang":  # a blackholed SYN: the dial burns its whole connect timeout
            self.routes[(TOKEN, port)] = ("hang", 0)
        else:
            server = _Server(("127.0.0.1", 0), Proxy)
            self._start(server)
            self.routes[(TOKEN, port)] = ("proxy", server.server_address[1])
        return f"{TOKEN}:{port}"

    def kill(self, port: int):
        kind, loop = self.routes[(TOKEN, port)]
        for server in self.servers:
            if server.server_address[1] == loop:
                server.shutdown()
                server.server_close()
        with socket.socket() as hole:
            hole.bind(("127.0.0.1", 0))
            self.routes[(TOKEN, port)] = (kind, hole.getsockname()[1])

    def dial(self, host, port, timeout):
        self.dials.append((host, port))
        if (host, port) not in self.routes:
            raise AssertionError("fixture dial outside the loopback world")
        kind, loop = self.routes[(host, port)]
        if kind == "hang":
            self.timeouts.append(timeout)
            time.sleep(timeout)
            raise TimeoutError
        sock = socket.create_connection(("127.0.0.1", loop), timeout=timeout)
        if kind == "direct":
            sock.sendall(b"EXIT home\n")
        return sock

    def close(self):
        for server in self.servers:
            with contextlib.suppress(Exception):
                server.shutdown()
                server.server_close()


def pipe(a, b):
    while True:
        ready, _, _ = select.select([a, b], [], [], 5)
        if not ready:
            return
        for s in ready:
            try:
                data = s.recv(65536)
            except OSError:
                return
            if not data:
                return
            (b if s is a else a).sendall(data)


@pytest.fixture(scope="module")
def certs(tmp_path_factory):
    return certificates(tmp_path_factory.mktemp("route-source-certs"))


@pytest.fixture
def world(certs, monkeypatch):
    original = socket.create_connection

    def loopback_only(address, *args, **kwargs):
        if not ipaddress.ip_address(address[0]).is_loopback:
            raise AssertionError("non-loopback connection refused in route source tests")
        return original(address, *args, **kwargs)
    monkeypatch.setattr(socket, "create_connection", loopback_only)
    w = World(certs)
    yield w
    w.close()


# --- private layout --------------------------------------------------------------------------------------------------

def layout(tmp_path, *, enabled=True, experiment=("alpha",), spares=1, owner_beta=True, urls=None, collector=None):
    root = tmp_path / "private"
    root.mkdir(mode=0o700, exist_ok=True)
    doc = query_document(root)
    doc["collector"].update(
        x_identity_enabled=True, x_account_identities=IDENTITIES, route_source_enabled=enabled,
        route_source_list_urls=urls or [f"https://{LIST_HOST}/lists/http.txt"],
        route_source_allowed_hosts=[LIST_HOST], route_source_spares_per_country=spares,
        x_proxy_experiment_labels=list(experiment), **(collector or {}))
    (root / "queries.json").write_text(json.dumps(doc), encoding="utf-8")
    policy = {"version": 1, "allowed_origins": ["https://origin.test", "https://www.spamhaus.org",
                                                 "https://raw.githubusercontent.com", "https://ipapi.co"],
              "echo": {"url": "https://origin.test/ip", "response_format": "json-ip"},
              "baseline": {"url": "https://origin.test/plain", "sha256": hashlib.sha256(BASELINE).hexdigest()},
              "metadata_provider": None, "service_sid": SID, "cache_dir": str(root / "cache")}
    (root / "policy.json").write_text(json.dumps(policy), encoding="utf-8")
    if owner_beta:
        assignments = {"version": 1, "lines": {OWNER_ID: 1}, "accounts": {"beta": {
            "proxy_id": OWNER_ID, "expected_ip": "1.1.1.1", "region": "AU", "timezone": "Australia/Sydney",
            "accept_language": "en-AU"}}}
        (root / "assignments.json").write_text(json.dumps(assignments), encoding="utf-8")
        (root / "routes.txt").write_text(OWNER_LINE + "\n", encoding="utf-8")
    return root / "queries.json"


class Recorder:
    def __init__(self):
        self.publish_sids, self.order = [], []

    def publish(self, path, data, *, service_sid=None):
        self.publish_sids.append(service_sid)
        self.order.append(Path(path).name)
        atomic_bytes(path, data)

    def write_state(self, path, value, *, service_sid=None):
        self.publish_sids.append(service_sid)
        atomic_json(path, value)


def deps(world, certs, tmp_path, rec=None, ids=None, now=NOW, clock=None, connect_timeout=3.0):
    rec = rec or Recorder()
    counter = iter(ids or [f"00000000-0000-4000-8000-{n:012d}" for n in range(1, 100)])
    extra = {"clock": clock} if clock is not None else {}
    return rs.Deps(net=rs.Net(dial=world.dial, tls=verified_context(certs["origin"]["root"]), timeout=3,
                              connect_timeout=connect_timeout),
                   opener=fixture_open, publish=rec.publish, write_state=rec.write_state,
                   write_status=lambda path, value, **kw: atomic_json(path, value), now=lambda: now,
                   new_id=lambda: next(counter), cache_root=tmp_path / "cache", repo_root=tmp_path / "repo", **extra)


def standard_list(world):
    lines = [
        world.proxy(8001, exits=("8.8.8.8",)),
        world.proxy(8002, exits=("8.8.4.4",)),
        world.proxy(8003, "dead"),
        world.proxy(8004, "noconnect"),
        world.proxy(8005, "mitm"),
        world.proxy(8006, exits=("4.2.2.2", "4.2.2.3")),  # rotating exit
        world.proxy(8007, exits=("81.2.69.142",)),  # wrong country
        world.proxy(8008, exits=("8.8.8.8",)),  # same exit as 8001
        "socks5://93.184.216.34:1080", "10.0.0.1:8080", f"{TOKEN}:25", "proxy.example.com:8080",
        f"http://user:pw@{TOKEN}:8009", "garbage",
    ]
    world.lists["/lists/http.txt"] = "\n".join(lines) + "\n"


def read_private(root):
    return (json.loads((root / "assignments.json").read_bytes()), (root / "routes.txt").read_text().splitlines(),
            json.loads((root / "cache" / "route_source" / "state.json").read_bytes()))


def status(tmp_path):
    return json.loads(rs.status_path(tmp_path / "cache").read_bytes())


# --- unit boundaries -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("line,expected", [
    ("93.184.216.34:8080", "http://93.184.216.34:8080"), ("http://93.184.216.34:3128/", "http://93.184.216.34:3128"),
    ("[2606:4700:4700::1111]:8080", "http://[2606:4700:4700::1111]:8080"),
    ("socks5://93.184.216.34:1080", None), ("https://93.184.216.34:443", None), ("10.0.0.1:8080", None),
    ("127.0.0.1:8080", None), ("93.184.216.34:25", None), ("93.184.216.34:0", None), ("93.184.216.34:70000", None),
    ("proxy.example.com:8080", None), ("http://u:p@93.184.216.34:8080", None), ("93.184.216.34", None),
    ("# comment", None), ("", None),
])
def test_candidate_lines_are_numeric_public_credential_free_http(line, expected):
    cand = rs.candidate_from_line(line)
    assert (cand.line if cand else None) == expected


def test_parse_candidates_dedupes_and_caps():
    body = ("93.184.216.34:8080\n" * 3 + "93.184.216.34:8081\n").encode()
    assert [c.port for c in rs.parse_candidates(body)] == [8080, 8081]
    assert len(rs.parse_candidates(b"\n" * (rs.LIST_LINES + 5) + b"93.184.216.34:8080\n")) == 0


def test_net_refuses_a_non_verifying_tls_context():
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with pytest.raises(rs.SourceError, match="tls_not_verifying"):
        rs.Net(tls=context)


def test_list_fetch_follows_only_same_host_https_redirects(world, certs):
    net = rs.Net(dial=world.dial, tls=verified_context(certs["origin"]["root"]), timeout=3)
    world.lists["/b.txt"] = "93.184.216.34:8080\n"
    world.redirects["/a.txt"] = f"https://{LIST_HOST}/b.txt"
    assert rs.fetch_list(f"https://{LIST_HOST}/a.txt", (LIST_HOST,), net) == b"93.184.216.34:8080\n"
    world.redirects["/off.txt"] = "https://evil.example/b.txt"
    with pytest.raises(rs.SourceError, match="list_redirect"):
        rs.fetch_list(f"https://{LIST_HOST}/off.txt", (LIST_HOST,), net)
    world.redirects["/plain.txt"] = f"http://{LIST_HOST}/b.txt"
    with pytest.raises(rs.SourceError, match="list_redirect"):
        rs.fetch_list(f"https://{LIST_HOST}/plain.txt", (LIST_HOST,), net)
    with pytest.raises(rs.SourceError, match="list_host"):
        rs.fetch_list("https://other.example/b.txt", (LIST_HOST,), net)
    assert all(host in (LIST_HOST,) for host, _ in world.dials)


def test_prescreen_rejects_dead_non_connect_mitm_and_rotating(world, certs, tmp_path):
    net = rs.Net(dial=world.dial, tls=verified_context(certs["origin"]["root"]), timeout=3)
    policy = p.parse_policy((Path(layout(tmp_path)).parent / "policy.json").read_bytes(), tmp_path / "private")
    expected = {8001: None, 8003: "dead", 8004: "no_connect", 8005: "tls", 8006: "rotating"}
    standard_list(world)
    for port, reason in expected.items():
        cand = rs.Candidate(TOKEN, port)
        if reason is None:
            verified = rs.prescreen(cand, policy, net)
            assert verified.exit_ip == "8.8.8.8"
        else:
            with pytest.raises(rs.SourceError, match=reason):
                rs.prescreen(cand, policy, net)


# --- config ----------------------------------------------------------------------------------------------------------

def _doc(tmp_path, **collector):
    doc = json.loads(layout(tmp_path).read_bytes())
    doc["collector"].update(collector)
    return doc


def test_route_source_is_off_by_default_and_inert():
    c = wq.load().config
    assert c.route_source_enabled is False and c.x_proxy_experiment_labels == () and c.route_source_list_urls == ()
    assert c.reddit_proxy_experiment_identities == {}
    assert c.route_source_scan_concurrency == 96 and c.route_source_scan_budget_seconds == 240
    assert c.route_source_site_checks == {"x": True, "reddit": True}


@pytest.mark.parametrize("change", [
    {"route_source_list_urls": []},
    {"route_source_list_urls": ["http://raw.githubusercontent.com/x.txt"]},
    {"route_source_list_urls": ["https://evil.example/x.txt"]},
    {"route_source_list_urls": ["https://raw.githubusercontent.com:8443/x.txt"]},
    {"route_source_allowed_hosts": ["RAW.githubusercontent.com"]},
    {"x_proxy_experiment_labels": ["gamma"]},
    {"x_proxy_experiment_labels": ["alpha", "alpha"]},
    {"x_identity_enabled": False, "x_account_identities": {}},
    {"route_source_spares_per_country": 11},
    {"route_source_scan_concurrency": 0}, {"route_source_scan_concurrency": 257},
    {"route_source_scan_budget_seconds": 5}, {"route_source_site_checks": {"x": True}},
    {"route_source_site_checks": {"x": 1, "reddit": True}},
    {"route_source_enabled": "yes"},
    {"reddit_proxy_experiment_identities": {"nobody": {"region": "US", "timezone": "America/New_York",
                                                       "accept_language": "en-US"}}},
    {"x_proxy_experiment_labels": [], "reddit_proxy_experiment_identities": {}},
])
def test_route_source_config_is_strict(tmp_path, change):
    with pytest.raises(wq.QueriesError):
        wq.validate(_doc(tmp_path, **change))


def test_route_source_needs_the_b2_paths(tmp_path):
    doc = _doc(tmp_path, x_proxy_required=False, x_proxy_list_path=None, x_proxy_assignments_path=None,
               x_proxy_policy_path=None)
    with pytest.raises(wq.QueriesError, match="three B2 proxy paths"):
        wq.validate(doc)


# --- end to end (fixture mode) ---------------------------------------------------------------------------------------

def test_default_off_writes_no_route_file_and_dials_nothing(world, certs, tmp_path):
    path = layout(tmp_path, enabled=False, owner_beta=False)
    result = rs.run_once(path, deps(world, certs, tmp_path))
    assert result.state == "off" and not world.dials
    assert not (path.parent / "routes.txt").exists() and not (path.parent / "cache").exists()
    assert status(tmp_path)["state"] == "off"


def test_once_produces_files_the_real_b2_loader_and_admission_accept(world, certs, tmp_path, monkeypatch):
    path = layout(tmp_path)
    standard_list(world)
    rec = Recorder()
    out = io.StringIO()
    code = route_feeder.main(["--queries", str(path), "--once"], out=out, deps=deps(world, certs, tmp_path, rec))
    assert code == 0, out.getvalue()
    assert out.getvalue().startswith("route_source[experiment] ok: assigned managed=1 assigned=1 spares=1")
    assert rec.order == ["routes.txt", "assignments.json"] and set(rec.publish_sids) == {SID}
    doc, lines, state = read_private(path.parent)
    # Owner label, ID and credentialed line untouched; the managed label is coherent with its B1 identity.
    assert doc["accounts"]["beta"]["proxy_id"] == OWNER_ID and doc["lines"][OWNER_ID] == 1 and lines[0] == OWNER_LINE
    alpha = doc["accounts"]["alpha"]
    assert alpha["region"] == "US" and alpha["timezone"] == "America/New_York" and alpha["accept_language"] == "en-US"
    assert alpha["expected_ip"] in ("8.8.8.8", "8.8.4.4")
    assert lines[doc["lines"][alpha["proxy_id"]] - 1] in (f"http://{TOKEN}:8001", f"http://{TOKEN}:8002")
    assert state["owned_ids"] == [alpha["proxy_id"]] and len(state["spares"]) == 1
    assert {state["bank"][state["spares"][0]]["exit_ip"], alpha["expected_ip"]} == {"8.8.8.8", "8.8.4.4"}
    rejections = status(tmp_path)["rejections"]
    for reason in ("dead", "no_connect", "tls", "rotating"):
        assert rejections.get(reason) == 1, (reason, rejections)
    assert "8.8.8.8" not in json.dumps(status(tmp_path)) and TOKEN not in json.dumps(status(tmp_path))
    # REAL B2 loader over the published bytes.
    private = snapshot.load_snapshot(path, repo_root=tmp_path / "repo", opener=fixture_open)
    assert private.assignments["alpha"].expected_ip == alpha["expected_ip"]
    assert private.assignments["alpha"].route.url.startswith(f"http://{TOKEN}:800")
    # REAL admission with only its request seam synthetic: the echo answers what the fixture proxy exits as.
    monkeypatch.setattr(runtime, "private_read", lambda path, policy, repo, limit: runtime.read_bounded(Path(path), limit))
    monkeypatch.setattr(runtime, "atomic_json", lambda path, value, **kw: atomic_json(path, value))
    monkeypatch.setattr(runtime, "atomic_bytes", lambda path, value, **kw: atomic_bytes(path, value))
    monkeypatch.setattr(runtime, "secure_directory", lambda path, **kw: path.mkdir(parents=True, exist_ok=True))
    exits = {f"http://{TOKEN}:8001": "8.8.8.8", f"http://{TOKEN}:8002": "8.8.4.4"}

    async def request(route, policy, url, limit):
        return {policy.echo: json.dumps({"ip": exits[route.url]}).encode(), p.SPAMHAUS: spamhaus(NOW),
                p.FIREHOL: firehol(NOW), policy.baseline: BASELINE}[url]
    resolver = runtime.ProxyRuntime(private.config, config_path=path, repo_root=tmp_path / "repo",
                                    clock=lambda: NOW, snapshot_loader=partial(snapshot.load_snapshot,
                                                                               opener=fixture_open), request=request)

    class Pool:
        path = tmp_path / "pool.json"
        results = []
        def _acct(self, label):
            return {"proxy_quarantine_until": None}
        def proxy_result(self, label, **kw):
            self.results.append(kw)
    resolver.snapshot = runtime.Snapshot(private.config, private.policy, private.assignments,
                                         {lb: "c92163a0-a06d-4ae1-bbe4-2f36c308a250" for lb in private.assignments},
                                         path, private)
    resolver._revisions = dict(resolver.snapshot.revisions)
    pool = Pool()
    resolver.admit("alpha", pool)
    assert resolver.admitted("alpha") and pool.results[-1] == {"reason": None}


def test_healthy_route_is_sticky(world, certs, tmp_path):
    path = layout(tmp_path)
    standard_list(world)
    rs.run_once(path, deps(world, certs, tmp_path))
    before = (path.parent / "assignments.json").read_bytes(), (path.parent / "routes.txt").read_bytes()
    rec = Recorder()
    result = rs.run_once(path, deps(world, certs, tmp_path, rec))
    assert result.state == "ok" and result.reason == "steady" and not result.published and rec.order == []
    assert ((path.parent / "assignments.json").read_bytes(), (path.parent / "routes.txt").read_bytes()) == before


def _pool_state(tmp_path, accounts):
    target = tmp_path / "cache" / "attention" / "_pc_state" / "x_pool.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"accounts": accounts}), encoding="utf-8")


def test_pool_quarantine_replaces_with_same_country_spare_and_change_record(world, certs, tmp_path):
    path = layout(tmp_path)
    standard_list(world)
    rs.run_once(path, deps(world, certs, tmp_path))
    old_doc, old_lines, _ = read_private(path.parent)
    old = old_doc["accounts"]["alpha"]
    _pool_state(tmp_path, {"alpha": {"proxy_health": "quarantined", "proxy_id": old["proxy_id"]},
                           "beta": {"proxy_health": "quarantined", "proxy_id": OWNER_ID}})
    rec = Recorder()
    result = rs.run_once(path, deps(world, certs, tmp_path, rec, ids=["00000000-0000-4000-8000-0000000000aa"]))
    assert result.replaced == 1 and result.published and rec.order == ["routes.txt", "assignments.json"]
    doc, lines, state = read_private(path.parent)
    new = doc["accounts"]["alpha"]
    assert new["proxy_id"] == "00000000-0000-4000-8000-0000000000aa" and new["proxy_id"] != old["proxy_id"]
    assert new["expected_ip"] != old["expected_ip"] and new["region"] == "US"
    # Experiment scoping: the quarantined OWNER label is untouched; old slots never move.
    assert doc["accounts"]["beta"] == old_doc["accounts"]["beta"] and lines[:len(old_lines)] == old_lines
    assert old["proxy_id"] not in doc["lines"] and state["owned_ids"] == [new["proxy_id"]]
    assert old["expected_ip"] in state["quarantine"]
    change = state["changes"][-1]
    assert change == {"at": NOW.isoformat(), "label": "alpha", "from": old["proxy_id"], "to": new["proxy_id"],
                      "reason": "pool_quarantined"}
    assert {"code": "route_replaced", "site": "x"} in status(tmp_path)["alerts"]
    snapshot.load_snapshot(path, repo_root=tmp_path / "repo", opener=fixture_open)


def test_dying_route_is_replaced_pre_emptively_and_freed_slot_is_reused(world, certs, tmp_path):
    path = layout(tmp_path)
    standard_list(world)
    rs.run_once(path, deps(world, certs, tmp_path))
    doc, lines, _ = read_private(path.parent)
    old = doc["accounts"]["alpha"]
    port = int(lines[doc["lines"][old["proxy_id"]] - 1].rsplit(":", 1)[1])
    world.kill(port)
    first = rs.run_once(path, deps(world, certs, tmp_path, ids=["00000000-0000-4000-8000-0000000000bb"]))
    assert first.replaced == 1 and first.rejections.get("assigned_dead") == 1  # fail_streak 1 + a spare: replace now
    doc2, lines2, state2 = read_private(path.parent)
    assert doc2["accounts"]["alpha"]["proxy_id"] == "00000000-0000-4000-8000-0000000000bb"
    assert doc2["accounts"]["alpha"]["expected_ip"] != old["expected_ip"]
    assert state2["changes"][-1]["reason"] == "probe_failed" and state2["changes"][-1]["from"] == old["proxy_id"]
    assert len(lines2) == len(lines) + 1  # the replaced slot was still referenced by the old file
    snapshot.load_snapshot(path, repo_root=tmp_path / "repo", opener=fixture_open)
    steady = rs.run_once(path, deps(world, certs, tmp_path))
    assert steady.replaced == 0 and not steady.published  # the new healthy route is sticky


def test_wrong_country_exit_is_banked_never_assigned_and_coverage_shows_it(world, certs, tmp_path):
    path = layout(tmp_path, spares=0)
    world.lists["/lists/http.txt"] = world.proxy(8007, exits=("81.2.69.142",)) + "\n"
    result = rs.run_once(path, deps(world, certs, tmp_path))
    assert result.state == "degraded" and result.reason == "no_spare:US" and not result.published
    assert {"code": "no_spare:US", "site": "x"} in status(tmp_path)["alerts"]
    assert status(tmp_path)["bank"]["no_spare"] == ["US"]
    assert "alpha" not in json.loads((path.parent / "assignments.json").read_bytes())["accounts"]
    out = io.StringIO()
    assert route_feeder.main(["--queries", str(path), "--coverage"], out=out,
                             deps=deps(world, certs, tmp_path)) == 0
    assert out.getvalue().splitlines()[1:] == ["GB 1"]
    assert "81.2.69.142" not in out.getvalue() and TOKEN not in out.getvalue()


def test_no_spare_keeps_the_old_route_and_alerts_never_direct(world, certs, tmp_path, isolated_cache):
    path = layout(tmp_path, spares=0)
    world.lists["/lists/http.txt"] = world.proxy(8001, exits=("8.8.8.8",)) + "\n"
    rs.run_once(path, deps(world, certs, tmp_path))
    before = (path.parent / "assignments.json").read_bytes()
    old = json.loads(before)["accounts"]["alpha"]
    _pool_state(tmp_path, {"alpha": {"proxy_health": "quarantined", "proxy_id": old["proxy_id"]}})
    result = rs.run_once(path, deps(world, certs, tmp_path))
    assert result.state == "degraded" and result.reason == "no_spare:US" and not result.published
    assert (path.parent / "assignments.json").read_bytes() == before
    assert {host for host, _ in world.dials} <= {TOKEN, LIST_HOST}  # never a direct (home-IP) target dial
    report = {c.name: c for c in doctor.run_checks(_doctor_deps(tmp_path, path))}["route_source"]
    assert report.state == doctor.WARN and report.reason == "route_source_no_spare:US"


def test_missing_owner_x_label_is_never_published(world, certs, tmp_path):
    path = layout(tmp_path, owner_beta=False)
    standard_list(world)
    result = rs.run_once(path, deps(world, certs, tmp_path))
    assert result.state == "degraded" and result.reason == "x_labels_unassigned" and not result.published
    assert not (path.parent / "routes.txt").exists()


def test_dry_run_publishes_nothing(world, certs, tmp_path):
    path = layout(tmp_path)
    standard_list(world)
    rec = Recorder()
    out = io.StringIO()
    assert route_feeder.main(["--queries", str(path), "--once", "--dry-run"], out=out,
                             deps=deps(world, certs, tmp_path, rec)) == 0
    assert rec.order == [] and "published=false" in out.getvalue()
    assert (path.parent / "routes.txt").read_text().splitlines() == [OWNER_LINE]


def test_cli_bounds_interval_and_requires_mode(tmp_path):
    with pytest.raises(SystemExit):
        route_feeder.main(["--queries", str(tmp_path / "q.json"), "--loop", "--interval", "10"])
    with pytest.raises(SystemExit):
        route_feeder.main(["--queries", str(tmp_path / "q.json")])


def test_loop_repeats_with_bounded_interval(world, certs, tmp_path):
    path = layout(tmp_path)
    standard_list(world)
    sleeps = []
    out = io.StringIO()
    assert route_feeder.main(["--queries", str(path), "--loop", "--interval", "600"], out=out,
                             deps=deps(world, certs, tmp_path), sleep=sleeps.append, max_runs=2) == 0
    assert sleeps == [600] and out.getvalue().count("route_source[experiment]") == 2


# --- doctor ----------------------------------------------------------------------------------------------------------

def _doctor_deps(tmp_path, queries):
    return doctor.Deps(cache_root=tmp_path / "cache", now=NOW + timedelta(minutes=5), env={},
                       query_runner=lambda argv: (0, "1"), selftest_runner=lambda argv: 0,
                       private_verifier=lambda path: None, profile_verifier=lambda root, cache_root: None,
                       machine_lock=lambda: 0, memory=lambda: 8000.0, browser_version=lambda b: "1.0",
                       disk_free_mb=lambda path: 100000.0, dist_lookup=lambda name: None, queries_path=queries)


def test_doctor_route_source_states(world, certs, tmp_path, isolated_cache):
    off = layout(tmp_path, enabled=False)
    check = {c.name: c for c in doctor.run_checks(_doctor_deps(tmp_path, off))}["route_source"]
    assert (check.state, check.reason) == (doctor.PASS, "route_source_off")
    on = layout(tmp_path)
    check = {c.name: c for c in doctor.run_checks(_doctor_deps(tmp_path, on))}["route_source"]
    assert (check.state, check.reason) == (doctor.UNKNOWN, "route_source_not_run")
    standard_list(world)
    rs.run_once(on, deps(world, certs, tmp_path))
    check = {c.name: c for c in doctor.run_checks(_doctor_deps(tmp_path, on))}["route_source"]
    assert (check.state, check.reason) == (doctor.PASS, "experiment_assigned_1_of_1_spares_1_bank_8_live_4")
    stale = _doctor_deps(tmp_path, on)
    stale.now = NOW + timedelta(days=2)
    assert {c.name: c for c in doctor.run_checks(stale)}["route_source"].state == doctor.WARN


# --- v2: bank, whole-list scanner, reachability, spares, pre-emptive replacement -------------------------------------

def _bank(path):
    return read_private(path.parent)[2]["bank"]


def test_bank_persists_and_dead_ttl_skips_known_dead(world, certs, tmp_path):
    path = layout(tmp_path)
    standard_list(world)
    rs.run_once(path, deps(world, certs, tmp_path))
    bank = _bank(path)
    good, dead = bank[f"{TOKEN}|8001"], bank[f"{TOKEN}|8003"]
    assert good["ok_streak"] == 1 and good["fail_streak"] == 0 and good["first_seen"] == NOW.isoformat()
    assert good["country"] == "US" and good["exit_ip"] == "8.8.8.8" and good["latency"] is not None
    assert dead["fail_streak"] == 1 and dead["last_ok"] is None and rs._when(dead["dead_until"]) > NOW
    assert "8.8.8.8" not in json.dumps(status(tmp_path)) and status(tmp_path)["bank"]["size"] == 8
    world.dials.clear()
    later = NOW + timedelta(minutes=30)
    rs.run_once(path, deps(world, certs, tmp_path, now=later))
    assert (TOKEN, 8003) not in world.dials and (TOKEN, 8004) not in world.dials  # skipped inside the dead TTL
    bank = _bank(path)
    assert bank[f"{TOKEN}|8001"]["ok_streak"] == 2 and bank[f"{TOKEN}|8001"]["first_seen"] == NOW.isoformat()
    world.dials.clear()
    rs.run_once(path, deps(world, certs, tmp_path, now=NOW + rs.DEAD_TTL + timedelta(minutes=1)))
    assert (TOKEN, 8003) in world.dials  # the TTL expired: re-probed once
    assert rs._when(_bank(path)[f"{TOKEN}|8003"]["dead_until"]) - (NOW + rs.DEAD_TTL) > rs.DEAD_TTL  # backoff grows


def test_whole_list_scan_fits_the_budget_with_short_connect_timeouts(world, certs, tmp_path):
    path = layout(tmp_path, spares=0, collector={"route_source_scan_concurrency": 64})
    lines = [world.proxy(9000 + n, "hang") for n in range(120)] + [world.proxy(8001, exits=("8.8.8.8",))]
    world.lists["/lists/http.txt"] = "\n".join(lines) + "\n"
    started = time.monotonic()
    result = rs.run_once(path, deps(world, certs, tmp_path, connect_timeout=0.25))
    elapsed = time.monotonic() - started
    assert len(world.timeouts) == 120 and set(world.timeouts) == {0.25}  # every hung host got only the short dial
    assert elapsed < 8, elapsed  # 120 x 0.25 s serial would be 30 s
    assert result.assigned == 1 and result.rejections.get("dead") == 120 and "scan_budget" not in result.rejections
    assert status(tmp_path)["bank"]["scanned"] == 121


def test_budget_stops_starting_probes_and_next_pass_resumes_with_unknown_first(world, certs, tmp_path):
    path = layout(tmp_path, spares=0, collector={"route_source_scan_concurrency": 1,
                                                 "route_source_scan_budget_seconds": 10})
    lines = [world.proxy(9000 + n, "dead") for n in range(6)]
    world.lists["/lists/http.txt"] = "\n".join(lines) + "\n"
    ticks = iter(range(0, 10_000, 4))  # every budget check costs 4 s of fake wall clock
    result = rs.run_once(path, deps(world, certs, tmp_path, clock=lambda: next(ticks)))
    probed = {p for h, p in world.dials if h == TOKEN}
    assert result.rejections.get("scan_budget") == 6 - len(probed) and 0 < len(probed) < 6
    world.dials.clear()
    ticks2 = iter(range(0, 10_000, 4))
    rs.run_once(path, deps(world, certs, tmp_path, clock=lambda: next(ticks2)))
    assert {p for h, p in world.dials if h == TOKEN}.isdisjoint(probed)  # never-probed first, known-dead skipped


def test_target_site_reachability_rejects_blocks_and_interstitials(world, certs, tmp_path):
    path = layout(tmp_path, spares=0)
    world.lists["/lists/http.txt"] = "\n".join([world.proxy(8001, exits=("8.8.8.8",)),
                                                world.proxy(8002, exits=("8.8.4.4",)),
                                                world.proxy(8003, exits=("4.2.2.2",))]) + "\n"
    world.blocked["8.8.8.8"] = (403, b"forbidden")
    world.blocked["8.8.4.4"] = (200, b"<html><title>Attention Required! | Cloudflare</title></html>")
    result = rs.run_once(path, deps(world, certs, tmp_path))
    assert result.rejections.get("reach_x") == 2
    doc = json.loads((path.parent / "assignments.json").read_bytes())
    assert doc["accounts"]["alpha"]["expected_ip"] == "4.2.2.2"
    bank = _bank(path)
    assert bank[f"{TOKEN}|8001"]["reach"] == {"x": False} and bank[f"{TOKEN}|8003"]["reach"] == {"x": True}


def test_site_check_can_be_switched_off_per_site(world, certs, tmp_path):
    path = layout(tmp_path, spares=0, collector={"route_source_site_checks": {"x": False, "reddit": True}})
    world.lists["/lists/http.txt"] = world.proxy(8001, exits=("8.8.8.8",)) + "\n"
    world.blocked["8.8.8.8"] = (403, b"forbidden")
    result = rs.run_once(path, deps(world, certs, tmp_path))
    assert result.assigned == 1 and "reach_x" not in result.rejections


def _four_us(world):
    world.lists["/lists/http.txt"] = "\n".join(
        world.proxy(8001 + n, exits=(ip,)) for n, ip in enumerate(("8.8.8.8", "8.8.4.4", "4.2.2.2", "4.2.2.3"))) + "\n"


def test_spares_are_kept_per_country_and_refilled_while_healthy_route_stays(world, certs, tmp_path):
    path = layout(tmp_path, spares=2)
    _four_us(world)
    first = rs.run_once(path, deps(world, certs, tmp_path))
    assert first.assigned == 1 and first.spares == 2
    assert status(tmp_path)["bank"]["spares_per_country"] == {"US": 2}
    before = (path.parent / "assignments.json").read_bytes()
    state = read_private(path.parent)[2]
    victim = state["bank"][state["spares"][0]]["line"]
    world.kill(int(victim.rsplit(":", 1)[1]))
    second = rs.run_once(path, deps(world, certs, tmp_path, now=NOW + timedelta(minutes=10)))
    assert second.spares == 2 and not second.published and second.replaced == 0
    assert (path.parent / "assignments.json").read_bytes() == before
    state = read_private(path.parent)[2]
    assert victim not in {state["bank"][k]["line"] for k in state["spares"]}


def test_pre_emptive_replacement_batches_one_change_and_keeps_healthy_routes(world, certs, tmp_path):
    path = layout(tmp_path, experiment=("alpha", "beta"), owner_beta=False, spares=1)
    world.lists["/lists/http.txt"] = "\n".join([
        world.proxy(8001, exits=("8.8.8.8",)), world.proxy(8002, exits=("8.8.4.4",)),
        world.proxy(8011, exits=("1.0.0.1",)), world.proxy(8012, exits=("1.0.0.2",))]) + "\n"
    rs.run_once(path, deps(world, certs, tmp_path))
    doc, lines, _ = read_private(path.parent)
    alpha, beta = doc["accounts"]["alpha"], doc["accounts"]["beta"]
    assert beta["region"] == "AU" and beta["expected_ip"] in ("1.0.0.1", "1.0.0.2")
    world.kill(int(lines[doc["lines"][alpha["proxy_id"]] - 1].rsplit(":", 1)[1]))
    rec = Recorder()
    result = rs.run_once(path, deps(world, certs, tmp_path, rec, ids=["00000000-0000-4000-8000-0000000000cc"]))
    assert result.replaced == 1 and rec.order == ["routes.txt", "assignments.json"]  # one batch, one publication
    doc2, _, state = read_private(path.parent)
    assert doc2["accounts"]["beta"] == beta  # healthy route untouched
    assert doc2["accounts"]["alpha"]["region"] == "US" and doc2["accounts"]["alpha"]["expected_ip"] != alpha["expected_ip"]
    assert state["changes"][-1] == {"at": NOW.isoformat(), "label": "alpha", "from": alpha["proxy_id"],
                                    "to": "00000000-0000-4000-8000-0000000000cc", "reason": "probe_failed"}
    assert {"code": "route_replaced", "site": "x"} in status(tmp_path)["alerts"]


def test_everything_dead_never_falls_back_to_a_direct_route(world, certs, tmp_path):
    path = layout(tmp_path, spares=1)
    _four_us(world)
    rs.run_once(path, deps(world, certs, tmp_path))
    before = (path.parent / "assignments.json").read_bytes(), (path.parent / "routes.txt").read_bytes()
    for port in (8001, 8002, 8003, 8004):
        world.kill(port)
    world.dials.clear()
    result = rs.run_once(path, deps(world, certs, tmp_path, now=NOW + timedelta(minutes=10)))
    assert result.state == "degraded" and result.reason == "no_spare:US" and not result.published
    assert ((path.parent / "assignments.json").read_bytes(), (path.parent / "routes.txt").read_bytes()) == before
    assert {host for host, _ in world.dials} <= {TOKEN, LIST_HOST}


def test_bank_summary_reports_counts_only(world, certs, tmp_path):
    path = layout(tmp_path, spares=1)
    standard_list(world)
    rs.run_once(path, deps(world, certs, tmp_path))
    rs.run_once(path, deps(world, certs, tmp_path, now=NOW + timedelta(hours=2)))
    bank = status(tmp_path)["bank"]
    assert bank["size"] == 8 and bank["verified_live"] == 4 and bank["spares_per_country"] == {"US": 1}
    assert bank["oldest_assigned_age_hours"] == 2.0 and bank["no_spare"] == [] and bank["last_scan_seconds"] >= 0
    assert set(bank) == {"size", "verified_live", "spares_per_country", "no_spare", "last_scan_seconds", "scanned",
                         "oldest_assigned_age_hours"}


def test_coverage_cli_is_read_only_and_empty_before_any_scan(world, certs, tmp_path):
    path = layout(tmp_path)
    out = io.StringIO()
    assert route_feeder.main(["--queries", str(path), "--coverage"], out=out, deps=deps(world, certs, tmp_path)) == 0
    assert out.getvalue().splitlines()[1:] == ["none"] and not world.dials
    assert not (path.parent / "cache" / "route_source").exists()
    with pytest.raises(SystemExit):
        route_feeder.main(["--queries", str(path), "--coverage", "--once"])
