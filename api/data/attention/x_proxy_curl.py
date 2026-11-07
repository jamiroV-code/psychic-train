"""Lazy curl route adapter; native CONNECT_TO storage lives through session close."""
from __future__ import annotations

import asyncio
from urllib.parse import urlsplit

from api.data.attention import x_proxy as p
from api.data.attention.x_proxy_transport import resolve_public

X_COOKIE_DOMAIN = ".x.com"


def seed_cookies(cookies, values):
    """Load `values` into an httpx/curl_cffi cookie jar scoped to `.x.com`, so a refreshed cookie replaces it."""
    for name, value in dict(values or {}).items():
        cookies.set(name, value, domain=X_COOKIE_DOMAIN, path="/")
    return cookies


def scope_cookies(cookies, previous):
    """Collapse the jar to one `.x.com` cookie per name (REF-X rec 8, upstream PR #363 semantics).

    `previous` is the name -> value view taken before the request; any entry whose value differs from it (a
    domain or host-only `Set-Cookie`) replaces the old value. Returns the names whose value changed.
    """
    merged, changed = dict(previous), set()
    for cookie in list(cookies.jar):
        if cookie.value != previous.get(cookie.name):
            merged[cookie.name] = cookie.value
            if cookie.name in previous:
                changed.add(cookie.name)
    cookies.jar.clear()
    seed_cookies(cookies, merged)
    return changed


def cookie_values(cookies):
    """Name -> value view of a scoped jar."""
    return {cookie.name: cookie.value for cookie in cookies.jar}


class Slist:
    def __init__(self, values):
        from curl_cffi import ffi, lib
        self.ffi, self.lib, self.pointer = ffi, lib, ffi.NULL
        try:
            for value in values:
                updated = lib.curl_slist_append(self.pointer, value.encode("ascii"))
                p.require(updated != ffi.NULL, "proxy_transport")
                self.pointer = updated
        except Exception:
            self.close()
            raise p.ProxyFailure("proxy_transport") from None

    @property
    def option(self):
        return self.ffi.cast("char *", self.pointer)

    def close(self):
        if self.pointer != self.ffi.NULL:
            self.lib.curl_slist_free_all(self.pointer)
            self.pointer = self.ffi.NULL


async def retire_session(session):
    """Retire session-local ownership; retain every handle on partial failure."""
    from curl_cffi import lib
    session._b2_retired = False
    handles = getattr(session, "_b2_handles", set())
    session._b2_handles = handles
    failures = []
    def attempt(operation):
        try:
            return operation()
        except Exception:
            failures.append(True)
            return None
    multi = session._acurl
    checker = None
    if multi is not None:
        p.require(all(hasattr(multi, name) for name in
            ("_timeout_checker", "_curl2future", "_curl2curl", "_curlm", "_sockfds", "_timer", "loop")), "proxy_policy")
        checker = multi._timeout_checker
        checker.cancel()
        handles.update(multi._curl2curl.values())
        handles.update(multi._curl2future)
        if multi._curlm is not None:
            for curl, future in tuple(multi._curl2future.items()):
                attempt(lambda: lib.curl_multi_remove_handle(multi._curlm, curl._curl))
                if not future.done():
                    future.cancel()
        removed = set()
        for descriptor in tuple(multi._sockfds):
            before = len(failures)
            attempt(lambda: multi.loop.remove_reader(descriptor))
            attempt(lambda: multi.loop.remove_writer(descriptor))
            if before == len(failures):
                removed.add(descriptor)
        if multi._timer:
            before = len(failures)
            attempt(multi._timer.cancel)
            if before == len(failures):
                multi._timer = None
        if multi._curlm is not None:
            result = attempt(lambda: lib.curl_multi_cleanup(multi._curlm))
            p.require(result == 0, "proxy_transport")
            multi._curlm = None
        # Native cleanup may invoke the pinned callbacks; retain their socket
        # membership until then and cancel any final callback-installed timer.
        multi._sockfds.difference_update(removed)
        if multi._timer:
            before = len(failures)
            attempt(multi._timer.cancel)
            if before == len(failures):
                multi._timer = None
        multi._curl2future.clear()
        multi._curl2curl.clear()
    session._closed = True
    while not session.pool.empty():
        curl = session.pool.get_nowait()
        if curl is not None:
            handles.add(curl)
    for curl in tuple(handles):
        before = len(failures)
        attempt(curl.close)
        if before == len(failures):
            handles.remove(curl)
    if checker is not None:
        await asyncio.gather(checker, return_exceptions=True)
    session._b2_retired = not handles and not failures
    p.require(not failures and session._b2_retired, "proxy_transport")


class CurlRouteClient:
    backend = "curl"

    def __init__(self, route, policy, *, target, headers=None, cookies=None,
                 resolver=resolve_public, origin_root=None, proxy_root=None):
        from curl_cffi.requests import Cookies, Headers
        import certifi
        import re
        from curl_cffi import __curl_version__
        version = re.search(r"libcurl/(\d+)\.(\d+)\.(\d+)", __curl_version__)
        p.require(version is not None and tuple(map(int, version.groups())) >= (8, 4, 0), "proxy_policy")
        self.route, self.policy, self.target = route, policy, target
        self.resolver = resolver
        self.origin_root = origin_root or certifi.where()
        self.proxy_root = proxy_root or certifi.where()
        self.headers = Headers({k: v for k, v in (headers or {}).items() if k.lower() != "user-agent"})
        self.cookies = seed_cookies(Cookies(), cookies)
        self._active = set()
        self._retained = []
        self.closed = False

    async def request(self, method, url, **kwargs):
        from curl_cffi import CurlOpt, ffi
        from curl_cffi.requests import AsyncSession
        from twscrape.http import Response
        session, bindings = None, None
        reason = None
        deadline = asyncio.get_running_loop().time() + 10
        connect_deadline = asyncio.get_running_loop().time() + 5
        try:
            p.require(not self.closed and method in ("GET", "POST"), "proxy_policy")
            if self.policy is not None:
                self.policy.validate_url(str(url))
            p.require(set(kwargs) <= {"params", "headers", "cookies", "json", "data"}, "proxy_policy")
            async with asyncio.timeout_at(deadline):
                options = {}
                if self.route is not None:
                    origin, proxy = urlsplit(str(url)), urlsplit(self.route.url)
                    port = origin.port or 443
                    async with asyncio.timeout_at(connect_deadline):
                        address = await self.resolver(origin.hostname, port)
                        proxy_address = await self.resolver(proxy.hostname, proxy.port)
                    numeric = f"[{address}]" if ":" in address else address
                    proxy_numeric = f"[{proxy_address}]" if ":" in proxy_address else proxy_address
                    source = f"[{origin.hostname}]" if ":" in origin.hostname else origin.hostname
                    proxy_source = f"[{proxy.hostname}]" if ":" in proxy.hostname else proxy.hostname
                    bindings = Slist([f"{source}:{port}:{numeric}:{port}"])
                    options.update({CurlOpt.CONNECT_TO: bindings.option,
                        CurlOpt.RESOLVE: [f"{proxy_source}:{proxy.port}:{proxy_numeric}"],
                        CurlOpt.HTTPPROXYTUNNEL: 1, CurlOpt.NOPROXY: ""})
                    if self.route.auth:
                        options[CurlOpt.PROXYUSERNAME], options[CurlOpt.PROXYPASSWORD] = self.route.auth
                else:
                    options.update({CurlOpt.PROXY: "", CurlOpt.NOPROXY: "*"})
                self._active.add(asyncio.current_task())
                body = bytearray()
                def receive(chunk):
                    if len(body) + len(chunk) > p.X_LIMIT:
                        return 0
                    body.extend(chunk)
                    return len(chunk)
                options.update({CurlOpt.CAINFO: str(self.origin_root), CurlOpt.PROXY_CAINFO: str(self.proxy_root),
                           CurlOpt.SSL_VERIFYPEER: 1, CurlOpt.SSL_VERIFYHOST: 2,
                           CurlOpt.PROXY_SSL_VERIFYPEER: 1, CurlOpt.PROXY_SSL_VERIFYHOST: 2,
                           CurlOpt.CONNECTTIMEOUT_MS: max(1, int((connect_deadline - asyncio.get_running_loop().time()) * 1000)),
                           CurlOpt.TIMEOUT_MS: 9000,
                           CurlOpt.CAPATH: ffi.NULL, CurlOpt.PROXY_CAPATH: ffi.NULL,
                           CurlOpt.MAXFILESIZE_LARGE: p.X_LIMIT,
                           CurlOpt.FOLLOWLOCATION: 0, CurlOpt.MAXREDIRS: 0})
                previous = cookie_values(self.cookies)
                session = AsyncSession(proxy=self.route.url if self.route else "", impersonate=self.target,
                    headers=self.headers, cookies=self.cookies, trust_env=False, verify=True,
                    allow_redirects=False, retry=0, max_clients=1, curl_options=options)
                try:
                    p.require(all(hasattr(session.acurl, name) for name in
                        ("_timeout_checker", "_curl2future", "_curl2curl", "_curlm", "_sockfds", "_timer", "loop")), "proxy_policy")
                    async with asyncio.timeout_at(deadline - 1):
                        result = await session.request(method, str(url), timeout=(5, 9),
                            allow_redirects=False, accept_encoding="identity", content_callback=receive, **kwargs)
                    p.require(not 300 <= result.status_code < 400, "proxy_redirect")
                    p.require(len(body) <= p.X_LIMIT, "proxy_response")
                    result.content = bytes(body)
                    self.cookies.update(session.cookies)
                    scope_cookies(self.cookies, previous)
                    return Response(result)
                finally:
                    # No shielded orphan task may survive reader-loop disposal.
                    owned, bindings = bindings, None
                    self._retained.append((session, owned))
                    try:
                        await retire_session(session)
                    finally:
                        if getattr(session, "_b2_retired", False):
                            if owned is not None:
                                owned.close()
                            self._retained.remove((session, owned))
        except TimeoutError:
            reason = "proxy_timeout"
        except Exception as exc:
            reason = exc.reason if isinstance(exc, p.ProxyFailure) else "proxy_transport"
        finally:
            self._active.discard(asyncio.current_task())
            if bindings is not None:
                bindings.close()
        raise p.ProxyFailure(reason) from None

    async def get(self, url, **kwargs):
        return await self.request("GET", url, **kwargs)

    async def post(self, url, **kwargs):
        return await self.request("POST", url, **kwargs)

    async def aclose(self):
        self.closed = True
        tasks = [task for task in self._active if task is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for session, bindings in tuple(self._retained):
            await retire_session(session)
            if bindings is not None:
                bindings.close()
            self._retained.remove((session, bindings))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.aclose()
