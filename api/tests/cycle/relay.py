"""C8: route quarantine and replacement (B2 runtime), the REAL relay in both modes, refusals and expiry.

Seams: the A6b resolver answer source and dialer (S-Fixtures), the fake CONNECT proxy, the spawned fake browser and
the B2 private-file readers of the existing S-RAcct-B fixture (`fake_network`). Relay policy, `ProxyRuntime`,
`RedditAccounts`, the host and the CDP pipe are real. The B2 part runs in its own temporary cache root because the
fixture's synthetic private documents name their own Reddit label.
"""
from __future__ import annotations

import json
import socket
import time
from datetime import timedelta
from types import SimpleNamespace

from api.data import cache
from api.data.attention import browser_relay as r
from api.data.attention import browser_session as bs
from api.data.attention import x_proxy as p
from api.data.attention import x_proxy_runtime as runtime
from api.tests.cycle import browser as cb
from api.tests.data.attention import test_browser_relay as trl
from api.tests.data.attention import test_x_proxy_reddit as txr
from api.tests.data.attention.fixture_seams import SYNTHETIC_PUBLIC_TOKEN, FixtureDialer, synthetic_resolver
from api.tests.data.attention.proxy_wire_fixture import verified_context

REDDIT = "www.reddit.com"
HOSTILE = (b"evil.example:443", b"93.184.216.34:443", b"[::1]:443", b"127.0.0.1:443", b"www.reddit.com:8443",
           b"user:pw@www.reddit.com:443")
PRIVATE = ("127.0.0.1", "10.0.0.7", "192.168.1.5", "169.254.1.1")


def connect(port, authority):
    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    sock.sendall(b"CONNECT " + authority + b" HTTP/1.1\r\nHost: " + authority + b"\r\n\r\n")
    head = b""
    while b"\r\n\r\n" not in head:
        chunk = sock.recv(1)
        if not chunk:
            break
        head += chunk
    return sock, head.split(b"\r\n", 1)[0]


def fetch(port, root):
    sock, status = connect(port, REDDIT.encode() + b":443")
    assert status.startswith(b"HTTP/1.1 200"), status
    with verified_context(root).wrap_socket(sock, server_hostname=REDDIT) as tls:
        tls.sendall(f"GET / HTTP/1.1\r\nHost: {REDDIT}\r\nConnection: close\r\n\r\n".encode())
        data = b""
        while chunk := tls.recv(65536):
            data += chunk
    return data


def relay(mode, origin_port, *, route=None, answers=None, dialer=None, gate=None, clock=None):
    clock = clock or trl.Clock()
    gate = gate or trl.Gate(clock)
    dialer = dialer or FixtureDialer({SYNTHETIC_PUBLIC_TOKEN: ("127.0.0.1", origin_port)})
    resolver = synthetic_resolver(answers or {REDDIT: SYNTHETIC_PUBLIC_TOKEN})
    rel = r.Relay("reddit", "rd_a", mode, revision="rev-1", admission=gate, route=route, resolver=resolver,
                  dialer=dialer, clock=clock)
    rel.start()
    return rel, dialer, gate, clock


def quarantine_and_replacement(root, patch):
    """B2: a failing admission quarantines the Reddit account's route; a replacement proxy is admitted afresh."""
    previous = cache.CACHE_ROOT
    try:
        cache.CACHE_ROOT = root / "b2_cache"
        cache.bootstrap_cache_dirs()
        calls, clock = [], txr.Clock()
        path = txr.write_union(root / "b2_private")
        policy = json.loads((path.parent / "policy.json").read_bytes())
        resolver = txr.resolver_for(path, root, request=txr.fake_network(patch, calls, fail=policy["echo"]["url"],
                                                                          clock=clock), clock=clock)
        txr.mark_ready()
        accounts = txr.reddit_pool(resolver, clock=clock)
        view = runtime.RedditRouteView(accounts, runtime.ProviderBudget(None), clock=clock)
        resolver.reconcile(txr.XFake(), reddit=view)
        try:
            resolver.admit("ra_one", view)
            raise AssertionError("admission should fail")
        except p.ProxyFailure as failure:
            assert failure.reason == "proxy_exit"
        quarantined = accounts.account_state("ra_one")
        assert quarantined == ("locked", "proxy_quarantined"), quarantined
        txr.edit_assignments(path, lambda d: (d["lines"].update({txr.ID4: 4}),
                                              d["accounts"]["ra_one"].update(proxy_id=txr.ID4)))
        resolver.reconcile(txr.XFake(), reddit=view)
        assert resolver.route_admission("reddit", "ra_one") == "unadmitted"
        clock.now += timedelta(seconds=3600)
        resolver.request = txr.fake_network(patch, calls, clock=clock)
        resolver.admit("ra_one", view)
        assert resolver.route_admission("reddit", "ra_one") == "proxy" and accounts.select() == "ra_one"
        return {"quarantined": list(quarantined), "replacement": "admitted", "fresh_admission_required": True}
    finally:
        cache.CACHE_ROOT = previous


def run(world):
    origin, root = world.origin, world.origin.certs["origin"]["root"]
    observed = {"b2": quarantine_and_replacement(world.root, world.patch)}

    rel, dialer, *_ = relay("direct", origin.port)
    try:
        before = len(origin.sni)
        assert fetch(rel.port, root).startswith(b"HTTP/1.1 200")
        assert dialer.dialed == [(SYNTHETIC_PUBLIC_TOKEN, 443)] and origin.sni[before:] == [REDDIT]
        for authority in HOSTILE:
            sock, status = connect(rel.port, authority)
            sock.close()
            assert status.startswith(b"HTTP/1.1 403"), (authority, status)
        assert dialer.dialed == [(SYNTHETIC_PUBLIC_TOKEN, 443)]
    finally:
        rel.close()
    for answer in PRIVATE:
        rel, dialer, *_ = relay("direct", origin.port, answers={REDDIT: answer})
        try:
            sock, status = connect(rel.port, b"www.reddit.com:443")
            sock.close()
            assert status.startswith(b"HTTP/1.1 502") and dialer.dialed == [], (answer, status)
        finally:
            rel.close()
    observed["direct"] = {"pinned_numeric_dial": True, "hostile_refused": len(HOSTILE),
                          "private_answers_refused": len(PRIVATE)}

    upstream = trl.NumericProxy(origin.port)
    proxy_token = "93.184.216.35"
    route = p.parse_proxy(f"http://proxy.test:{upstream.port}")
    dialer = FixtureDialer({proxy_token: ("127.0.0.1", upstream.port)})
    rel, dialer, *_ = relay("proxy", origin.port, route=route, dialer=dialer,
                            answers={REDDIT: SYNTHETIC_PUBLIC_TOKEN, "proxy.test": proxy_token})
    fake = cb.FakeBrowser(world.root / "relay_browser", extra={"ca_file": str(root)},
                          pages={f"https://{x}/": {"wire": True} for x in (REDDIT, "evil.example")})
    try:
        with fake.host.launch("c8_probe", "c8_probe", rel.port) as session:
            results = []
            for i, url in enumerate((f"https://{REDDIT}/", "https://evil.example/"), 1):
                session.pipe.send(json.dumps({"id": i, "method": "Page.navigate", "params": {"url": url}}).encode())
                while True:
                    message = json.loads(session.pipe.receive(timeout=10))
                    if message.get("id") == i:
                        results.append(message["result"])
                        break
        assert "frameId" in results[0] and results[1] == {"errorText": "fixture_route_failed"}, results
        assert dialer.dialed == [(proxy_token, upstream.port)]  # never the origin: no direct connection
        assert [c["line"] for c in upstream.connects] == [f"CONNECT {SYNTHETIC_PUBLIC_TOKEN}:443 HTTP/1.1"]
        assert rel.health()["relay_refusals"] == {"evil.example": 1}
    finally:
        rel.close()
        upstream.close()
    observed["proxy"] = {"spawned_browser_through_relay": True, "dials": "proxy only", "numeric_connect": True,
                         "hostile_page_refused": True}

    partial = SimpleNamespace(x_proxy_required=False, x_proxy_list_path="C:/a", x_proxy_assignments_path=None,
                              x_proxy_policy_path=None)
    assert r.select_mode(partial, route=route, admitted=True) == "refuse"
    launches = []
    refused = cb.FakeBrowser(world.root / "refused_browser")
    result = bs.check_session("reddit", "rd_a", host=refused.host, profile_name="rd_a", day_guard=trl_guard(),
                              routes=_Routes(), mode="automatic", timeout=30)
    launches += refused.launches
    assert (result.state, result.reason) == ("refused", "proxy_not_admitted") and launches == []
    observed["partial_config"] = {"mode": "refuse", "browser_launched": False}

    rel, dialer, gate, clock = relay("direct", origin.port)
    try:
        sock, status = connect(rel.port, b"www.reddit.com:443")
        assert status.startswith(b"HTTP/1.1 200")
        clock.now = 100.0
        deadline, closed = time.monotonic() + 5, False
        sock.settimeout(5)
        while time.monotonic() < deadline and not closed:
            try:
                closed = sock.recv(1) == b""
            except OSError:
                closed = True
        assert closed and rel.health()["failure"] == "proxy_admission_expired"
    finally:
        rel.close()
    observed["admission_expiry"] = "open tunnel closed, proxy_admission_expired"
    observed["not_exercised"] = [
        "the B2 quarantine/replacement half uses the S-RAcct-B fixture's own synthetic private documents in a "
        "separate temporary cache (label ra_one), not the cycle's rd_* accounts",
        "partial-config refusal: the relay mode is the real `select_mode`; the session's route answer for that "
        "case is a fixed proxy_not_admitted provider (the real RedditRoutes refusal is covered by test_reddit_browser)",
        "native (non-Python) sockets of a real browser are not observed (BP13 native-containment gap)"]
    return observed


class _Routes:
    def admitted_route(self, site, label):
        return "proxy_not_admitted"


def trl_guard():
    from api.tests.data.attention.test_browser_session import Guard
    return Guard()
