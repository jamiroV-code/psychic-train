"""Test-only spawned entrypoint: real protocol/HMAC and real routed clients.

Installed-distribution/filesystem inspectors and upstream search dispatch are
injected. There is no production bypass or secret in argv/environment. The
entrypoint installs the Python-level network-denial guard first (see
fixture_seams.NATIVE_CONTAINMENT_GAP for its limits).
"""
import json
import re
import sys


QUERY_ID = re.compile(r"[A-Za-z0-9_-]{16,32}")


def expected_query_id(options):
    """Envelope-v2 `query_id` the parent is expected to deliver (None = explicit null)."""
    value = options.get("query_id")
    if value is None:
        return None
    if not isinstance(value, str) or not QUERY_ID.fullmatch(value):
        raise AssertionError("fixture query_id must match the envelope-v2 grammar")
    return value


def ct0_count(cookie_headers):
    """Number of `ct0` cookies across every Cookie header of one request."""
    return sum(1 for header in cookie_headers for part in header.split(";")
               if part.strip().split("=", 1)[0] == "ct0")


class FakeXCookies:
    """Fake-X helper over a WireFixture: every Cookie header of every request, duplicate `ct0`."""

    def __init__(self, wire):
        self.wire = wire

    def cookie_headers(self):
        return [list(request["cookies"]) for request in self.wire.requests]

    def duplicate_ct0(self):
        """Indexes of recorded requests that carried more than one `ct0`."""
        return [index for index, headers in enumerate(self.cookie_headers()) if ct0_count(headers) > 1]


def main():
    from api.tests.data.attention.fixture_seams import install_network_denial
    install_network_denial()
    from api.data.attention import twscrape_reader as tr, x_proxy_snapshot as snap
    from api.data.attention import x_proxy_private as private, x_proxy_runtime as runtime
    from api.data.attention import x_proxy_curl as curl
    from api.tests.data.attention.test_x_proxy_snapshot import fixture_open
    options = json.loads(sys.argv[1])
    query_id = expected_query_id(options)
    original_load = snap.load_snapshot
    snap.load_snapshot = lambda path, **kw: original_load(path, opener=fixture_open, **kw)
    private.verified_open = fixture_open
    runtime.private_read = lambda path, policy, repo, limit: private.read_bounded(path, limit)
    tr.identity_problem = lambda *args: None
    tr.curl_status = lambda *args: "ok"
    if not options.get("direct_wire"):
        tr.accounts_problems = lambda *args, **kw: []
    original_curl = curl.CurlRouteClient
    async def resolve(host, port):
        if host not in ("origin.test", "proxy.test"):
            raise AssertionError("fixture refused external host")
        return "127.0.0.1"
    def client(route, policy, **kwargs):
        return original_curl(route, policy, resolver=resolve, origin_root=options["origin_root"],
                             proxy_root=options["proxy_root"], **kwargs)
    curl.CurlRouteClient = client
    from twscrape import account, xclid
    from twscrape.api import API
    if options.get("direct_wire"):
        # Keep API.search_raw, QueueClient, cookie DB selection, cursor encoding,
        # account factory and bootstrap factory REAL. Only endpoint/DNS/trust and
        # the deterministic transaction-ID parser are fixture dependencies.
        from urllib.parse import urlsplit
        from curl_cffi import CurlOpt, requests
        from twscrape import api as api_module
        api_module.GQL_URL = options["origin_url"] + "/gql"
        original_session = requests.AsyncSession
        origin = urlsplit(options["origin_url"])
        def direct_session(**kwargs):
            kwargs["curl_options"][CurlOpt.RESOLVE] = [
                f"{origin.hostname}:{origin.port}:127.0.0.1"]
            return original_session(**kwargs)
        requests.AsyncSession = direct_session
        class Transaction:
            def calc(self, method, path):
                return "synthetic-local-transaction"
        async def bootstrap(proxy=None, cookies=None):
            session = xclid._make_client()
            try:
                response = await session.get(options["origin_url"] + "/bootstrap")
                assert response.status_code == 200
                return Transaction()
            finally:
                await session.aclose()
        xclid.XClIdGen.create = bootstrap
        return tr.main(["--curl-fallback"])
    async def search(self, query, limit=-1, kv=None):
        if query_id is not None:
            from twscrape import api as api_module
            assert api_module.OP_SearchTimeline.split("/", 1)[0] == query_id
        if options.get("predicate_only"):
            from types import SimpleNamespace
            yield SimpleNamespace(json=lambda: {"data": {"entries": []}}, headers={})
            return
        assert kv.get("cursor") == "fixture-continuation"
        acc = account.Account("alpha", "_", "_", "_", "fixture", True, cookies={"ct0": "synthetic"})
        bootstrap = xclid._make_client()
        try:
            await bootstrap.get(options["origin_url"] + "/child")
        finally:
            await bootstrap.aclose()
        session = acc.make_client()
        try:
            response = await session.get(options["origin_url"] + "/child")
            yield response
        finally:
            await session.aclose()
    API.search_raw = search
    return tr.main(["--curl-fallback"])


if __name__ == "__main__":
    raise SystemExit(main())
