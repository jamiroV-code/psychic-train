"""Test-only spawned entrypoint: real protocol/HMAC and real routed clients.

Installed-distribution/filesystem inspectors and upstream search dispatch are
injected. There is no production bypass or secret in argv/environment.
"""
import json
import sys


def main():
    from api.data.attention import twscrape_reader as tr, x_proxy_snapshot as snap
    from api.data.attention import x_proxy_private as private, x_proxy_runtime as runtime
    from api.data.attention import x_proxy_curl as curl
    from api.tests.data.attention.test_x_proxy_snapshot import fixture_open
    options = json.loads(sys.argv[1])
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
