"""B2 V3 real loopback HTTP/HTTPS proxy + original-origin TLS, both backends.

Mandatory under locked xreader acceptance. No external requests or real accounts.
"""
from __future__ import annotations

import asyncio
import base64
import gzip
import json
import socket
import traceback
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("twscrape", reason="optional xreader group; B2 acceptance requires frozen import preflight")
pytest.importorskip("curl_cffi", reason="optional xreader group; mandatory B2 cases cannot be skipped in acceptance")

from api.data.attention import x_proxy as p
from api.tests.data.attention.proxy_wire_fixture import fixture, verified_context


@pytest.fixture(params=[False, True], ids=["http-proxy", "https-proxy"])
def wire(request):
    with fixture(https_proxy=request.param) as value:
        yield value


def policy(wire, tmp_path):
    return p.Policy(frozenset({wire.origin_url, "https://www.spamhaus.org", "https://raw.githubusercontent.com", "https://ipapi.co",
                              f"https://wrong-origin.test:{wire.origin_port}"}),
        wire.origin_url + "/echo", wire.origin_url + "/baseline", "a" * 64, None,
        "S-1-5-21-1-2-3-1001", tmp_path / "cache", tmp_path)


def client(style, wire, configuration, *, origin=True, proxy=True, route=None, limit=None):
    if style == "plain":
        from api.data.attention.x_proxy_transport import client as make
        arguments = {"resolver": wire.resolve}
        if origin: arguments["origin_context"] = verified_context(wire.certs["origin"]["root"])
        if proxy: arguments["proxy_context"] = verified_context(wire.certs["proxy"]["root"])
        if limit is not None: arguments["limit"] = limit
        return make(route or p.parse_proxy(wire.proxy_url), configuration, **arguments)
    from api.data.attention.x_proxy_curl import CurlRouteClient
    return CurlRouteClient(route or p.parse_proxy(wire.proxy_url), configuration, target="chrome131", resolver=wire.resolve,
        origin_root=wire.certs["origin"]["root"] if origin else None,
        proxy_root=wire.certs["proxy"]["root"] if proxy else None)


@pytest.mark.parametrize("style", ["plain", "curl"])
def test_numeric_connect_original_host_sni_verified_separate_roots(wire, tmp_path, style):
    async def run():
        session = client(style, wire, policy(wire, tmp_path))
        try:
            response = await session.get(wire.origin_url + "/echo")
            assert response.status_code == 200
        finally:
            await session.aclose()
    asyncio.run(run())
    assert len(wire.connects) == len(wire.requests) == 1
    assert wire.connects[0]["authority"] == f"127.0.0.1:{wire.origin_port}"
    assert wire.connects[0]["headers"]["host"] == f"127.0.0.1:{wire.origin_port}"
    assert wire.requests[0]["host"] == f"origin.test:{wire.origin_port}"
    assert wire.origin_sni == ["origin.test"]
    assert wire.proxy_sni == (["proxy.test"] if wire.https_proxy else [])


@pytest.mark.parametrize("style", ["plain", "curl"])
@pytest.mark.parametrize("failure", ["origin-root", "origin-name"])
def test_untrusted_origin_or_wrong_origin_name_never_reaches_application(wire, tmp_path, style, failure):
    async def run():
        session = client(style, wire, policy(wire, tmp_path), origin=failure != "origin-root")
        try:
            name = "wrong-origin.test" if failure == "origin-name" else "origin.test"
            with pytest.raises(p.ProxyFailure) as error:
                await session.get(f"https://{name}:{wire.origin_port}/echo")
            assert error.value.reason in p.REASONS
        finally:
            await session.aclose()
    asyncio.run(run())
    assert len(wire.connects) == 1 and wire.requests == []


@pytest.mark.parametrize("style", ["plain", "curl"])
@pytest.mark.parametrize("failure", ["proxy-root", "proxy-name"])
def test_https_proxy_own_root_and_hostname_required_even_with_hostile_ambient_ca(tmp_path, monkeypatch, style, failure):
    with fixture(https_proxy=True) as wire:
        for name in ("SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
            monkeypatch.setenv(name, str(wire.certs["proxy"]["root"]))
        route = p.parse_proxy(wire.proxy_url.replace("proxy.test", "wrong-proxy.test")) if failure == "proxy-name" else None
        async def run():
            session = client(style, wire, policy(wire, tmp_path), proxy=failure != "proxy-root", route=route)
            try:
                with pytest.raises(p.ProxyFailure):
                    await session.get(wire.origin_url + "/echo")
            finally:
                await session.aclose()
        asyncio.run(run())
        assert wire.connects == [] and wire.requests == []


@pytest.mark.parametrize("style", ["plain", "curl"])
def test_redirect_refused_with_exactly_one_wire_attempt_no_direct_fallback(wire, tmp_path, style, monkeypatch):
    wire.responses["/redirect"] = (302, {"location": "https://not-allowlisted.invalid/secret"}, b"")
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "TWS_PROXY"):
        monkeypatch.setenv(name, "http://ambient.invalid:1")
    async def run():
        session = client(style, wire, policy(wire, tmp_path))
        try:
            with pytest.raises(p.ProxyFailure, match="proxy_redirect"):
                await session.get(wire.origin_url + "/redirect")
        finally:
            await session.aclose()
    asyncio.run(run())
    assert len(wire.connects) == len(wire.requests) == 1


@pytest.mark.parametrize("style", ["plain", "curl"])
def test_unallowlisted_page_derived_url_refused_before_a_socket(wire, tmp_path, style):
    async def run():
        session = client(style, wire, policy(wire, tmp_path))
        try:
            with pytest.raises(p.ProxyFailure, match="proxy_policy"):
                await session.get("https://not-allowlisted.invalid/asset.js")
        finally:
            await session.aclose()
    asyncio.run(run())
    assert wire.connects == [] and wire.requests == []


@pytest.mark.parametrize("style", ["plain", "curl"])
def test_stream_bound_before_buffering_oversized_x_response(wire, tmp_path, monkeypatch, style):
    wire.responses["/large"] = (200, {"content-type": "application/json"}, b"x" * 65)
    monkeypatch.setattr(p, "X_LIMIT", 64)
    async def run():
        session = client(style, wire, policy(wire, tmp_path), limit=64)
        try:
            with pytest.raises(p.ProxyFailure):
                await session.get(wire.origin_url + "/large")
        finally:
            await session.aclose()
    asyncio.run(run())
    assert len(wire.connects) == len(wire.requests) == 1


def test_dedicated_feed_wire_and_decompressed_limits_are_separate(wire, tmp_path, monkeypatch):
    from api.data.attention import x_proxy_runtime as runtime, x_proxy_transport as transport
    compressed = gzip.compress(b"#" + b"x" * 1024)
    wire.responses[("www.spamhaus.org", "/drop/drop.txt")] = (200, {"content-encoding": "gzip"}, compressed)
    original = transport.client
    def make(route, configuration, **kwargs):
        return original(route, configuration, resolver=wire.resolve,
            origin_context=verified_context(wire.certs["origin"]["root"]),
            proxy_context=verified_context(wire.certs["proxy"]["root"]), **kwargs)
    monkeypatch.setattr(transport, "client", make)
    monkeypatch.setattr(p, "FEED_DECODED_LIMIT", 64)
    with pytest.raises(p.ProxyFailure, match="proxy_response"):
        asyncio.run(runtime.one_shot(p.parse_proxy(wire.proxy_url), policy(wire, tmp_path), p.SPAMHAUS, 1024))
    assert len(wire.requests) == 1


@pytest.mark.parametrize("style", ["plain", "curl"])
def test_both_factories_account_revision_isolation_and_no_credential_output(tmp_path, monkeypatch, capsys, style):
    from twscrape import account, xclid
    from api.data.attention import twscrape_reader as tr, x_proxy_transport as transport, x_proxy_curl as curl
    with fixture(https_proxy=True) as wire:
        secret = "SYNTHETIC_PROXY_CREDENTIAL_MARKER"
        route = p.parse_proxy(wire.proxy_url.replace("https://", "https://user:" + secret + "@"))
        configuration = policy(wire, tmp_path)
        identities = {
            "alpha": {"accept_language": "en-US", "region": "US", "timezone": "America/New_York", "user_agent": "alpha-literal", "impersonation_target": "chrome131"},
            "beta": {"accept_language": "fr-FR", "region": "FR", "timezone": "Europe/Paris", "user_agent": "beta-literal", "impersonation_target": "firefox133"},
        }
        routes = {label: p.Assignment(str(uuid4()), "8.8.8.8" if label == "alpha" else "1.1.1.1",
            value["region"], value["timezone"], value["accept_language"], route) for label, value in identities.items()}
        state = SimpleNamespace(snapshot=SimpleNamespace(policy=configuration, assignments=routes,
            revisions={label: str(uuid4()) for label in identities}), admitted=lambda label: True, admissions={})
        original_plain, original_curl = transport.client, curl.CurlRouteClient
        def plain(route, configuration, **kwargs):
            return original_plain(route, configuration, resolver=wire.resolve,
                origin_context=verified_context(wire.certs["origin"]["root"]),
                proxy_context=verified_context(wire.certs["proxy"]["root"]), **kwargs)
        def curl_client(route, configuration, **kwargs):
            return original_curl(route, configuration, resolver=wire.resolve,
                origin_root=wire.certs["origin"]["root"], proxy_root=wire.certs["proxy"]["root"], **kwargs)
        monkeypatch.setattr(transport, "client", plain)
        monkeypatch.setattr(curl, "CurlRouteClient", curl_client)
        adapter = tr.IdentityAdapter(style, identities, runtime=state)
        adapter.install()
        async def capture(label, bootstrap):
            with adapter.bind(label):
                acc = account.Account(label, "_", "_", "_", "old", True, cookies={"ct0": "fake"})
                session = xclid._make_client() if bootstrap else acc.make_client()
                try:
                    response = await session.get(wire.origin_url + "/echo")
                    return {key.lower(): value for key, value in response.json().items()}
                finally:
                    await session.aclose()
        async def run():
            return await asyncio.gather(*(capture(label, bootstrap) for label in identities for bootstrap in (False, True)))
        try:
            observed = asyncio.run(run())
        finally:
            adapter.close()
        assert len(wire.connects) == len(wire.requests) == 4
        assert all(item["authority"] == f"127.0.0.1:{wire.origin_port}" for item in wire.connects)
        for item, label in zip(observed, ("alpha", "alpha", "beta", "beta")):
            assert item["accept-language"] == identities[label]["accept_language"]
        assert observed[0]["user-agent"] == observed[1]["user-agent"]
        assert observed[2]["user-agent"] == observed[3]["user-agent"]
        assert observed[0]["user-agent"] != observed[2]["user-agent"]
        captured = capsys.readouterr()
        assert secret not in captured.out + captured.err + repr(route) + repr(state.snapshot.revisions)
        encoded = base64.b64encode(("user:" + secret).encode()).decode()
        assert encoded not in captured.out + captured.err




@pytest.mark.parametrize("style", ["plain", "curl"])
def test_cancelled_wire_request_drains_native_ownership_without_slowclose_extension(wire, tmp_path, monkeypatch, style):
    import threading
    import time
    from curl_cffi import ffi
    from curl_cffi import requests
    from api.data.attention import x_proxy_curl as curl
    release = threading.Event()
    wire.responses["/slow"] = lambda: (release.wait(5) and (200, {}, b"ok")) or (200, {}, b"ok")
    sessions, lists = [], []
    original_session, original_slist = requests.AsyncSession, curl.Slist
    class Session(original_session):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            sessions.append(self)
        async def close(self):
            await asyncio.sleep(60)  # native retirement must not delegate to this slow coroutine
    class Bindings(original_slist):
        def __init__(self, values):
            super().__init__(values)
            lists.append(self)
    monkeypatch.setattr(requests, "AsyncSession", Session)
    monkeypatch.setattr(curl, "Slist", Bindings)
    async def run():
        session = client(style, wire, policy(wire, tmp_path))
        task = asyncio.create_task(session.get(wire.origin_url + "/slow"))
        try:
            async with asyncio.timeout(4):
                while not wire.requests:
                    await asyncio.sleep(0.01)
            started = time.monotonic()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            await session.aclose()
            assert time.monotonic() - started < 2
            if style == "curl":
                assert len(sessions) == len(lists) == 1
                assert sessions[0]._acurl._curlm is None
                assert sessions[0]._acurl._timeout_checker.done()
                assert sessions[0].pool.empty()
                assert lists[0].pointer == ffi.NULL
            assert not [pending for pending in asyncio.all_tasks()
                        if pending is not asyncio.current_task() and not pending.done()]
        finally:
            release.set()
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            await session.aclose()
    asyncio.run(run())
    assert len(wire.connects) == len(wire.requests) == 1


@pytest.mark.parametrize("fault", ["easy-close", "watcher-remove", "timer-cancel"])
def test_partial_native_retirement_retains_slist_until_retry_finishes(wire, tmp_path, monkeypatch, fault):
    from curl_cffi import Curl, ffi
    from api.data.attention import x_proxy_curl as curl
    original_retire, original_close = curl.retire_session, Curl.close
    injected = False
    def close(easy):
        nonlocal injected
        if fault == "easy-close" and not injected:
            injected = True
            raise RuntimeError("synthetic easy cleanup failure")
        return original_close(easy)
    async def retire(session):
        nonlocal injected
        if fault == "timer-cancel" and not injected:
            injected = True
            multi = session._acurl
            original_timer = multi._timer
            failed = False
            class Timer:
                def cancel(self):
                    nonlocal failed
                    if not failed:
                        failed = True
                        raise RuntimeError("synthetic timer cleanup failure")
                    if original_timer is not None:
                        original_timer.cancel()
            multi._timer = Timer()
        if fault == "watcher-remove" and not injected:
            injected = True
            multi = session._acurl
            multi._sockfds.add(-77)
            original_loop = multi.loop
            failed = False
            def remove_reader(descriptor):
                nonlocal failed
                if descriptor == -77:
                    if not failed:
                        failed = True
                        raise RuntimeError("synthetic watcher cleanup failure")
                    return False
                return original_loop.remove_reader(descriptor)
            def remove_writer(descriptor):
                return False if descriptor == -77 else original_loop.remove_writer(descriptor)
            class LoopProxy:
                def __getattr__(self, name):
                    return getattr(original_loop, name)
                def remove_reader(self, descriptor):
                    return remove_reader(descriptor)
                def remove_writer(self, descriptor):
                    return remove_writer(descriptor)
            multi.loop = LoopProxy()
        return await original_retire(session)
    monkeypatch.setattr(Curl, "close", close)
    monkeypatch.setattr(curl, "retire_session", retire)
    async def run():
        session = client("curl", wire, policy(wire, tmp_path))
        try:
            with pytest.raises(p.ProxyFailure, match="proxy_transport"):
                await session.get(wire.origin_url + "/echo")
            assert injected and len(session._retained) == 1
            native, binding = session._retained[0]
            assert not native._b2_retired and binding.pointer != ffi.NULL
            if fault == "watcher-remove":
                assert -77 in native._acurl._sockfds
            await session.aclose()
            assert native._b2_retired and binding.pointer == ffi.NULL and not session._retained
        finally:
            await session.aclose()
    asyncio.run(run())


@pytest.mark.parametrize("style", ["plain", "curl"])
@pytest.mark.parametrize("boundary", ["queue", "swallowed-bootstrap-asset"])
def test_typed_failure_escapes_real_queue_retries_and_bootstrap_swallow(wire, tmp_path, monkeypatch, style, boundary):
    from twscrape import account, queue_client, xclid
    from api.data.attention import twscrape_reader as tr, x_proxy_transport as transport, x_proxy_curl as curl
    wire.responses["/disconnect"] = "disconnect"
    route = p.parse_proxy(wire.proxy_url)
    configuration = policy(wire, tmp_path)
    assignment = p.Assignment(str(uuid4()), "8.8.8.8", "US", "America/New_York", "en-US", route)
    state = SimpleNamespace(snapshot=SimpleNamespace(policy=configuration, assignments={"alpha": assignment},
        revisions={"alpha": str(uuid4())}), admitted=lambda label: True, admissions={})
    original_plain, original_curl = transport.client, curl.CurlRouteClient
    def plain(route, configuration, **kwargs):
        return original_plain(route, configuration, resolver=wire.resolve,
            origin_context=verified_context(wire.certs["origin"]["root"]),
            proxy_context=verified_context(wire.certs["proxy"]["root"]), **kwargs)
    def native(route, configuration, **kwargs):
        return original_curl(route, configuration, resolver=wire.resolve,
            origin_root=wire.certs["origin"]["root"], proxy_root=wire.certs["proxy"]["root"], **kwargs)
    monkeypatch.setattr(transport, "client", plain)
    monkeypatch.setattr(curl, "CurlRouteClient", native)
    monkeypatch.setattr(queue_client.telemetry, "capture", lambda *args, **kwargs: None)
    adapter = tr.IdentityAdapter(style, {}, runtime=state)
    adapter.install()
    async def swallowed_asset(*args, **kwargs):
        session = xclid._make_client()
        try:
            try:
                await session.get(wire.origin_url + "/disconnect")
            except Exception:
                pass  # emulate the pinned asset-task broad Exception handler
            return object()
        finally:
            await session.aclose()
    if boundary == "swallowed-bootstrap-asset":
        monkeypatch.setattr(xclid.XClIdGen, "create", swallowed_asset)
    async def run():
        with adapter.bind("alpha"):
            acc = account.Account("alpha", "_", "_", "_", "fixture", True,
                                  cookies={"ct0": "synthetic", "auth_token": "synthetic"})
            session = acc.make_client()
            async def request(method, url, params=None):
                return await session.request(method, url, params=params)
            queue = queue_client.QueueClient(SimpleNamespace(), "B2SyntheticFailure")
            queue.ctx = SimpleNamespace(acc=acc, clt=session, req=request, req_count=0, fails={})
            try:
                with pytest.raises(queue_client.AbortReqError) as failure:
                    if boundary == "queue":
                        await queue.req("GET", wire.origin_url + "/disconnect")
                    else:
                        await adapter._store.get("alpha", cookies=acc.cookies)
                assert failure.value.proxy_reason == "proxy_transport"
                assert adapter._route_failures["alpha"] == "proxy_transport"
                assert queue.ctx.req_count == 0
                # The sticky failure refuses another send without another wire attempt.
                with pytest.raises(queue_client.AbortReqError):
                    await session.get(wire.origin_url + "/echo")
            finally:
                await session.aclose()
    try:
        asyncio.run(run())
    finally:
        adapter.close()
    assert len(wire.connects) == len(wire.requests) == 1


@pytest.mark.parametrize("style", ["plain", "curl"])
def test_new_request_revalidates_binding_and_never_reuses_rebound_origin(wire, tmp_path, style):
    async def run():
        session = client(style, wire, policy(wire, tmp_path))
        try:
            assert (await session.get(wire.origin_url + "/echo")).status_code == 200
            async def rebound(host, port):
                if host == "origin.test":
                    raise p.ProxyFailure("proxy_address")
                return await wire.resolve(host, port)
            if style == "plain":
                session._transport.resolver = rebound
            else:
                session.resolver = rebound
            with pytest.raises(p.ProxyFailure, match="proxy_address"):
                await session.get(wire.origin_url + "/echo")
        finally:
            await session.aclose()
    asyncio.run(run())
    assert len(wire.connects) == len(wire.requests) == 1
