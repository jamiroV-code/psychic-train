"""Lazy-loaded B2 app-owned transport. Imported only by the reader boundary.

A pool is connection-scoped: every new request resolves and validates its binding;
no expired hostname binding or unbound direct transport can be reused.
"""
from __future__ import annotations

import asyncio
import socket
import threading
import ipaddress
from urllib.parse import urlsplit

import httpcore
import httpx

from api.data.attention import x_proxy as p


_dns_slots = threading.BoundedSemaphore(8)
_dns_lock = threading.Lock()
_dns_inflight = {}


async def resolve_public(host: str, port: int) -> str:
    """Bounded, single-flight DNS without executor-shutdown deadline extension."""
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        return p.public_address(str(literal))
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    key = (host, port)
    with _dns_lock:
        waiters = _dns_inflight.get(key)
        start = waiters is None
        if start:
            p.require(_dns_slots.acquire(blocking=False), "proxy_address")
            _dns_inflight[key] = [(loop, future)]
        else:
            p.require(len(waiters) < 64, "proxy_address")
            waiters.append((loop, future))
    def deliver(future, rows):
        if not future.done():
            future.set_result(rows)
    def finish(rows):
        with _dns_lock:
            waiters = _dns_inflight.pop(key, ())
        _dns_slots.release()
        for target_loop, target in waiters:
            try:
                target_loop.call_soon_threadsafe(deliver, target, rows)
            except RuntimeError:
                pass
    def resolve():
        rows = None
        try:
            candidate = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            if 0 < len(candidate) <= 64:
                rows = candidate
        except Exception:
            pass
        finally:
            finish(rows)
    if start:
        try:
            threading.Thread(target=resolve, daemon=True).start()
        except RuntimeError:
            finish(None)
    try:
        try:
            async with asyncio.timeout(5):
                rows = await future
        except TimeoutError:
            rows = None
    finally:
        with _dns_lock:
            waiters = _dns_inflight.get(key)
            if waiters is not None:
                waiters[:] = [(owner, pending) for owner, pending in waiters if pending is not future]
    p.require(rows is not None, "proxy_address")
    values = sorted({p.public_address(row[4][0]) for row in rows})
    p.require(bool(values), "proxy_address")
    return values[0]


class BoundStream(httpcore.AsyncNetworkStream):
    def __init__(self, stream, frame):
        self.stream, self.frame = stream, frame

    async def read(self, max_bytes, timeout=None):
        p.require(self.frame.done, "proxy_transport")
        return await self.stream.read(max_bytes, timeout)

    async def write(self, buffer, timeout=None):
        data = self.frame.feed(buffer)
        if data is not None:
            await self.stream.write(data, timeout)

    async def aclose(self):
        await self.stream.aclose()

    async def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        # Before CONNECT this is proxy TLS; after CONNECT it is origin TLS.
        self.stream = await self.stream.start_tls(ssl_context, server_hostname, timeout)
        return self

    def get_extra_info(self, info):
        return self.stream.get_extra_info(info)


class BoundBackend(httpcore.AsyncNetworkBackend):
    def __init__(self, proxy_host, proxy_port, proxy_address, original, numeric, backend=None):
        self.proxy_host, self.proxy_port, self.proxy_address = proxy_host, proxy_port, proxy_address
        self.original, self.numeric = original, numeric
        self.backend = backend or httpcore.AnyIOBackend()

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        p.require(host == self.proxy_host and port == self.proxy_port and local_address is None, "proxy_transport")
        stream = await self.backend.connect_tcp(self.proxy_address, port, timeout=timeout,
                                                local_address=None, socket_options=socket_options)
        return BoundStream(stream, p.ConnectFrame({self.original: self.numeric}))

    async def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise p.ProxyFailure("proxy_transport")

    async def sleep(self, seconds):
        await asyncio.sleep(seconds)


class CoreBody(httpx.AsyncByteStream):
    def __init__(self, response, pool, deadline, limit, owner):
        self.response, self.pool = response, pool
        self.deadline, self.limit, self.owner = deadline, limit, owner
        self.closed = False

    async def __aiter__(self):
        total, reason = 0, None
        try:
            async with asyncio.timeout_at(self.deadline - 1):
                async for chunk in self.response.aiter_stream():
                    total += len(chunk)
                    p.require(total <= self.limit, "proxy_response")
                    yield chunk
        except Exception as error:
            reason = ("proxy_timeout" if isinstance(error, TimeoutError) else
                      error.reason if isinstance(error, p.ProxyFailure) else "proxy_transport")
        finally:
            await self.aclose()
        if reason is not None:
            raise p.ProxyFailure(reason)

    async def aclose(self):
        if self.closed:
            return
        self.closed = True
        reason = None
        try:
            async with asyncio.timeout_at(self.deadline):
                try:
                    await self.response.aclose()
                finally:
                    await self.pool.aclose()
            self.owner.discard(self.pool)
        except Exception as error:
            reason = "proxy_timeout" if isinstance(error, TimeoutError) else "proxy_transport"
        if reason is not None:
            raise p.ProxyFailure(reason)


class NumericProxyTransport(httpx.AsyncBaseTransport):
    def __init__(self, route: p.PrivateRoute, policy: p.Policy, *, resolver=resolve_public,
                 origin_context=None, proxy_context=None, backend_factory=BoundBackend,
                 limit=p.X_LIMIT, allow_content_encoding=False):
        self.route, self.policy = route, policy
        self.resolver, self.backend_factory, self.limit = resolver, backend_factory, limit
        self.allow_content_encoding = allow_content_encoding
        self.origin_context = origin_context or httpx.create_ssl_context(verify=True, trust_env=False)
        self.proxy_context = proxy_context or httpx.create_ssl_context(verify=True, trust_env=False)
        p.require(self.origin_context.check_hostname and self.origin_context.verify_mode == 2
                  and self.proxy_context.check_hostname and self.proxy_context.verify_mode == 2, "proxy_policy")
        self.pools = set()

    async def handle_async_request(self, request):
        pool = None
        try:
            deadline = asyncio.get_running_loop().time() + 10
            connect_deadline = asyncio.get_running_loop().time() + 5
            async with asyncio.timeout_at(deadline - 1):
                self.policy.validate_url(str(request.url))
                p.require(request.method in ("GET", "POST"), "proxy_policy")
                origin = request.url.host
                port = request.url.port or 443
                async with asyncio.timeout_at(connect_deadline):
                    address = await self.resolver(origin, port)
                proxy = urlsplit(self.route.url)
                proxy_port = proxy.port or (443 if proxy.scheme == "https" else 80)
                async with asyncio.timeout_at(connect_deadline):
                    proxy_address = await self.resolver(proxy.hostname, proxy_port)
                # Match the pinned core's original authority exactly; it omits
                # brackets for literal IPv6. The forwarded numeric authority is
                # always correctly bracketed by the validated frame below.
                original = f"{origin}:{port}".encode("ascii")
                numeric = (f"[{address}]:{port}" if ":" in address else f"{address}:{port}").encode("ascii")
                backend = self.backend_factory(proxy.hostname, proxy_port, proxy_address, original, numeric)
                auth = None if self.route.auth is None else tuple(v.encode("utf-8") for v in self.route.auth)
                pool = httpcore.AsyncHTTPProxy(proxy_url=self.route.url,
                    proxy_auth=auth, ssl_context=self.origin_context,
                    proxy_ssl_context=self.proxy_context if proxy.scheme == "https" else None,
                    network_backend=backend, retries=0, max_connections=1, max_keepalive_connections=0,
                    http1=True, http2=False)
                self.pools.add(pool)
                headers = [(k, v) for k, v in request.headers.raw if k.lower() not in (b"accept-encoding", b"proxy-authorization")]
                headers.append((b"accept-encoding", b"identity"))
                core_request = httpcore.Request(request.method, httpcore.URL(scheme=request.url.raw_scheme,
                    host=request.url.raw_host, port=port, target=request.url.raw_path),
                    headers=headers, content=request.stream,
                    extensions={"timeout": {"connect": max(0.001, connect_deadline - asyncio.get_running_loop().time()),
                                             "read": 10, "write": 10, "pool": 5}})
                async with asyncio.timeout_at(connect_deadline):
                    response = await pool.handle_async_request(core_request)
                p.require(not 300 <= response.status < 400, "proxy_redirect")
                encoding = [v for k, v in response.headers if k.lower() == b"content-encoding"]
                p.require(not encoding or encoding == [b"identity"] or
                    self.allow_content_encoding and len(encoding) == 1 and encoding[0] in (b"gzip", b"deflate"), "proxy_response")
                return httpx.Response(response.status, headers=response.headers,
                    stream=CoreBody(response, pool, deadline, self.limit, self.pools), extensions=response.extensions)
        except Exception as exc:
            reason = ("proxy_timeout" if isinstance(exc, TimeoutError) else
                      exc.reason if isinstance(exc, p.ProxyFailure) else "proxy_transport")
            if pool is not None:
                try:
                    async with asyncio.timeout_at(deadline):
                        await pool.aclose()
                    self.pools.discard(pool)
                except Exception:
                    pass  # retained for the client's bounded close; never retried
        raise p.ProxyFailure(reason)

    async def aclose(self):
        pools = tuple(self.pools)
        failed = False
        try:
            async with asyncio.timeout(1):
                results = await asyncio.gather(*(pool.aclose() for pool in pools), return_exceptions=True)
                failed = any(isinstance(result, BaseException) for result in results)
            self.pools.difference_update(pools)
        except Exception:
            failed = True
        if failed:
            raise p.ProxyFailure("proxy_transport")


def client(route, policy, *, headers=None, cookies=None, **dependencies):
    return httpx.AsyncClient(transport=NumericProxyTransport(route, policy, **dependencies),
                            trust_env=False, follow_redirects=False, headers=headers, cookies=cookies,
                            timeout=httpx.Timeout(10, connect=5))


class LimitedBody(httpx.AsyncByteStream):
    def __init__(self, stream, deadline, limit):
        self.stream, self.deadline, self.limit = stream, deadline, limit

    async def __aiter__(self):
        size = 0
        try:
            async with asyncio.timeout_at(self.deadline - 1):
                async for chunk in self.stream:
                    size += len(chunk)
                    p.require(size <= self.limit, "proxy_response")
                    yield chunk
        finally:
            await self.aclose()

    async def aclose(self):
        async with asyncio.timeout_at(self.deadline):
            await self.stream.aclose()


class DirectTransport(httpx.AsyncBaseTransport):
    """Explicit direct/off compatibility, with the same trust/retry/resource floor."""
    def __init__(self):
        origin = httpx.create_ssl_context(verify=True, trust_env=False)
        self.transport = httpx.AsyncHTTPTransport(verify=origin, trust_env=False, retries=0,
                                                limits=httpx.Limits(max_keepalive_connections=0))

    async def handle_async_request(self, request):
        deadline = asyncio.get_running_loop().time() + 10
        request.headers["accept-encoding"] = "identity"
        async with asyncio.timeout_at(deadline - 1):
            response = await self.transport.handle_async_request(request)
            if 300 <= response.status_code < 400 or response.headers.get("content-encoding", "identity") != "identity":
                await response.aclose()
                raise p.ProxyFailure("proxy_response")
            response.stream = LimitedBody(response.stream, deadline, p.X_LIMIT)
            return response

    async def aclose(self):
        async with asyncio.timeout(1):
            await self.transport.aclose()


def direct_client(*, headers=None, cookies=None):
    return httpx.AsyncClient(transport=DirectTransport(), trust_env=False, follow_redirects=False,
                            headers=headers, cookies=cookies, timeout=httpx.Timeout(10, connect=5))
