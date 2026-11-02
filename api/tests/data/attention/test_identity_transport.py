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


@pytest.fixture(autouse=True)
def isolated_cache(attention_cache):
    return attention_cache


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
        assert a_graph["x-twitter-client-language"] == "en"
        assert b_graph["x-twitter-client-language"] == "en"
        assert a_graph["user-agent"] == a_boot["user-agent"]
        assert b_graph["user-agent"] == b_boot["user-agent"]
        assert a_graph["user-agent"] != b_graph["user-agent"]
        if style == "plain":
            assert a_graph["user-agent"] == identities["alpha"]["user_agent"]
            assert b_graph["user-agent"] == identities["beta"]["user_agent"]
    finally:
        adapter.close()


def test_bootstrap_cache_isolated_by_label_and_fresh(monkeypatch):
    from twscrape.queue_client import XClIdGenStore

    identities = {
        "alpha": {"accept_language": "en-US", "region": "US", "timezone": "America/New_York",
                  "user_agent": "Mozilla/5.0 Chrome/131.0.0.0 Safari/537.36", "impersonation_target": "chrome131"},
        "beta": {"accept_language": "en-GB", "region": "GB", "timezone": "Europe/London",
                 "user_agent": "Mozilla/5.0 Firefox/133.0", "impersonation_target": "firefox133"},
    }
    calls = []

    async def create(proxy=None, cookies=None):
        result = object()
        calls.append(result)
        return result

    monkeypatch.setattr(xclid.XClIdGen, "create", staticmethod(create))
    adapter = tr.IdentityAdapter("plain", identities)
    adapter.install()
    try:
        async def check():
            with adapter.bind("alpha"):
                alpha = await XClIdGenStore.get("same-username")
                assert await XClIdGenStore.get("same-username") is alpha
            with adapter.bind("beta"):
                beta = await XClIdGenStore.get("same-username")
                assert beta is not alpha
                fresh = await XClIdGenStore.get("same-username", fresh=True)
                assert fresh is not beta
            with adapter.bind("alpha"):
                assert await XClIdGenStore.get("same-username") is alpha
        asyncio.run(check())
        assert len(calls) == 3
    finally:
        adapter.close()


def test_refresh_preserves_account_state_and_reconciles_identity(tmp_path):
    from datetime import UTC, datetime, timedelta
    from api.data.attention import web_queries as wq

    directory = tmp_path / "accounts"
    directory.mkdir(mode=0o700)
    db = directory / "alpha.db"
    api = twscrape.API(str(db), raise_when_no_account=True, wait_timeout=0)
    identity = {"accept_language": "en-US", "region": "US", "timezone": "America/New_York",
                "user_agent": "Mozilla/5.0 Chrome/131.0.0.0 Safari/537.36", "impersonation_target": "chrome131"}
    locked_until = datetime.now(UTC) + timedelta(hours=1)

    async def seed():
        await api.pool.add_account_cookies("alpha", "auth_token=old; ct0=old")
        acc = await api.pool.get("alpha")
        acc.active = False
        acc.locks = {"SearchTimeline": locked_until}
        acc.stats = {"SearchTimeline": 7}
        await api.pool.save(acc)

    asyncio.run(seed())
    config = wq.CollectorConfig(**{**wq.load().config.as_dict(), "x_accounts": ("alpha",),
                                 "x_accounts_db_path": str(directory), "x_identity_enabled": True,
                                 "x_account_identities": {"alpha": identity}})
    env = {"TWS_TELEMETRY": "0", "DO_NOT_TRACK": "1", "TWS_LOG_LEVEL": "WARNING",
           "TWS_RAISE_WHEN_NO_ACCOUNT": "1"}
    tr.refresh_cookies("alpha", "auth_token=new; ct0=new", config=config, env=env,
                       now=datetime.now(UTC), repo_root=tmp_path / "repo")
    refreshed = asyncio.run(api.pool.get("alpha"))
    assert refreshed.cookies["auth_token"] == "new"
    assert refreshed.active is False
    assert refreshed.locks == {"SearchTimeline": locked_until}
    assert refreshed.stats == {"SearchTimeline": 7}
    assert refreshed.user_agent == identity["user_agent"]
    assert refreshed.headers["accept-language"] == identity["accept_language"]


def test_incompatible_upstream_factory_is_refused(monkeypatch):
    monkeypatch.setattr(account, "_make_http_client", lambda unexpected: None)
    adapter = tr.IdentityAdapter("plain", {})
    with pytest.raises(tr.XStartRefused):
        adapter.install()


def test_restart_and_identity_change_invalidate_bootstrap_cache(monkeypatch):
    from twscrape.queue_client import XClIdGenStore
    created = []

    async def create(proxy=None, cookies=None):
        result = object()
        created.append(result)
        return result

    monkeypatch.setattr(xclid.XClIdGen, "create", staticmethod(create))
    identity = {"accept_language": "en-US", "region": "US", "timezone": "America/New_York",
                "user_agent": "Mozilla/5.0 Chrome/131.0.0.0 Safari/537.36", "impersonation_target": "chrome131"}

    def acquire(value):
        adapter = tr.IdentityAdapter("plain", {"alpha": value})
        adapter.install()
        try:
            with adapter.bind("alpha"):
                return asyncio.run(XClIdGenStore.get("same-username"))
        finally:
            adapter.close()

    first = acquire(identity)
    second = acquire({**identity, "user_agent": "Mozilla/5.0 Chrome/136.0.0.0 Safari/537.36",
                      "impersonation_target": "chrome136"})
    assert first is not second
