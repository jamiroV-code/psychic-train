"""B1 transport identity wire gates; loopback only, optional locked X reader group."""
from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

twscrape = pytest.importorskip("twscrape")
from twscrape import account, xclid
from api.data.attention import twscrape_reader as tr


@pytest.fixture
def echo():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            payload = json.dumps(list(self.headers.items())).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


@pytest.mark.parametrize("style", ["plain", "curl"])
def test_both_factory_paths_send_account_identity(echo, style):
    identities = {
        "alpha": {"accept_language": "en-US,en;q=0.9", "region": "US", "timezone": "America/New_York",
                  "user_agent": "Mozilla/5.0 Chrome/131.0.0.0 Safari/537.36", "impersonation_target": "chrome131"},
        "beta": {"accept_language": "en-GB,en;q=0.8", "region": "GB", "timezone": "Europe/London",
                 "user_agent": "Mozilla/5.0 Firefox/133.0", "impersonation_target": "firefox133"},
    }
    adapter = tr.IdentityAdapter(style, identities)
    adapter.install()

    async def capture(label, bootstrap):
        with adapter.bind(label):
            if bootstrap:
                client = xclid._make_client(cookies={"ct0": "fake"})
            else:
                acc = account.Account(label, "_", "_", "_", "old", True, cookies={"ct0": "fake"})
                client = acc.make_client()
            try:
                reply = await client.get(echo)
                return {key.lower(): value for key, value in reply.json()}
            finally:
                await client.aclose()

    try:
        async def all_requests():
            return await asyncio.gather(*(capture(label, bootstrap) for label in identities for bootstrap in (False, True)))
        a_graph, a_boot, b_graph, b_boot = asyncio.run(all_requests())
        for observed, label in ((a_graph, "alpha"), (a_boot, "alpha"), (b_graph, "beta"), (b_boot, "beta")):
            assert observed["accept-language"] == identities[label]["accept_language"]
            assert observed["user-agent"]
        assert a_graph["user-agent"] == a_boot["user-agent"]
        assert b_graph["user-agent"] == b_boot["user-agent"]
        assert a_graph["user-agent"] != b_graph["user-agent"]
        if style == "plain":
            assert a_graph["user-agent"] == identities["alpha"]["user_agent"]
            assert b_graph["user-agent"] == identities["beta"]["user_agent"]
    finally:
        adapter.close()
