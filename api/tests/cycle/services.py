"""Synthetic HTTP payloads over real TLS. No production collector implementation is replaced."""
from __future__ import annotations

import json
import re
import socket
import ssl
import threading
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from api.tests.data.attention.fixture_seams import SYNTHETIC_HOSTS
from api.tests.data.attention.proxy_wire_fixture import certificates, verified_context
from api.tests.data.attention.proxy_child_fixture import ct0_count
from api.tests.data.attention.reddit_gql_fake import FakeGql, TOKEN_PATH
from api.data.attention import x_queryids

AUTH = {label: "CycleAuthMarker" + label.replace("_", "") + "A" * 24 for label in
        ("acc_a", "acc_b", "acc_c", "acc_d", "acc_e")}
CSRF = "CycleCsrfMarker" + "B" * 32
NEW_AUTH = "CycleRenewedAuthMarker" + "C" * 32
BODY_MARKER = "CyclePrivateBodyMarker"


class Clock:
    def __init__(self):
        self.t = datetime(2026, 11, 12, tzinfo=UTC)
        self.waits = []

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        assert seconds >= 0
        self.waits.append(seconds)
        self.t += timedelta(seconds=seconds)

    def wait(self, seconds, stopping):
        self.sleep(seconds)
        return stopping.is_set()


def tweet_entry(when, symbol, ordinal):
    identifier = str(((int(when.timestamp() * 1000) - 1288834974657) << 22) + ordinal)
    uid = str(100000 + ordinal)
    user = {"__typename": "User", "rest_id": uid, "legacy": {
        "id_str": uid, "screen_name": "synthetic" + uid, "name": "Synthetic author",
        "description": "", "created_at": "Mon Jan 01 00:00:00 +0000 2024",
        "followers_count": 100, "friends_count": 100, "statuses_count": 100,
        "favourites_count": 10, "listed_count": 1, "media_count": 1, "location": "",
        "profile_image_url_https": "https://example.invalid/avatar.jpg", "verified": False}}
    legacy = {"id_str": identifier, "user_id_str": uid, "created_at": format_datetime(when),
              "full_text": (symbol or "bitcoin") + " synthetic market discussion " + str(ordinal),
              "lang": "en", "reply_count": 0, "retweet_count": 0, "favorite_count": 0,
              "quote_count": 0, "conversation_id_str": identifier,
              "entities": {"hashtags": [], "symbols": [{"text": symbol}] if symbol else [],
                           "user_mentions": [], "urls": []}}
    return {"entryId": "tweet-" + identifier, "content": {"itemContent": {"tweet_results": {"result": {
        "__typename": "Tweet", "rest_id": identifier, "legacy": legacy,
        "core": {"user_results": {"result": user}}}}}}}


class Origin:
    """One SAN-covered loopback TLS origin serving fake X, Reddit feed and gql endpoints."""
    def __init__(self, root, clock):
        self.clock = clock
        self.certs = certificates(root)
        self.requests, self.sni, self.errors = [], [], []
        self.query_id = x_queryids.PINNED["SearchTimeline"]
        self.bundle_id = None  # the ID the bundle advertises when it runs ahead of the server switch
        self.restricted = set()
        self.suspended = set()
        self.expired = set()
        self.inconclusive = set()
        self.near_limit = set()
        self.gql = FakeGql(clock())
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_POST(self):
                self.do_GET()

            def do_GET(self):
                length = int(self.headers.get("content-length", "0"))
                if length > 2 * 1024 * 1024:
                    self.close_connection = True
                    return
                body = self.rfile.read(length)
                host = self.headers.get("host", "").split(":")[0]
                cookies = self.headers.get_all("cookie") or []
                try:
                    assert ct0_count(cookies) <= 1
                    status, headers, payload = owner.respond(self.command, host, self.path,
                                                              dict(self.headers), body)
                except Exception as exc:
                    owner.errors.append(type(exc).__name__)
                    status, headers, payload = 500, {}, b"fixture_error"
                self.send_response(status)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Connection", "close")
                for name, value in headers.items():
                    self.send_header(name, value)
                self.end_headers()
                try:
                    self.wfile.write(payload)
                except (OSError, ssl.SSLError):
                    pass
                self.close_connection = True

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(self.certs["origin"]["cert"]), str(self.certs["origin"]["key"]))
        context.set_alpn_protocols(["http/1.1"])
        context.set_servername_callback(lambda sock, name, ctx: self.sni.append(name))
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def respond(self, method, host, target, headers, body):
        cookie = next((v for k, v in headers.items() if k.lower() == "cookie"), "")
        auth = next((v.split("=", 1)[1] for v in cookie.split("; ") if v.startswith("auth_token=")), "")
        label = next((k for k, v in AUTH.items() if v == auth), "acc_a" if auth == NEW_AUTH else None)
        parsed = urlsplit(target)
        self.requests.append({"host": host, "path": parsed.path, "label": label,
                              "renewed": auth == NEW_AUTH, "ct0_count": ct0_count([cookie]),
                              "at": self.clock().isoformat()})
        if host == "gql-fed.reddit.com" or parsed.path == TOKEN_PATH:
            response = self.gql(method, "https://" + host + target, headers, body)
            return response.status, {"content-type": response.content_type}, response.body
        if parsed.path.endswith(".rss"):
            if self.clock().date() >= datetime(2026, 11, 13).date():
                return 403, {"content-type": "text/html"}, b"<html>feed blocked</html>"
            from api.tests.data.test_attention_pc_refresh import atom
            return 200, {"content-type": "application/atom+xml"}, atom(
                [self.clock() - timedelta(minutes=10 * i) for i in range(100)])
        if host == "abs.twimg.com":
            text = ('queryId:"' + (self.bundle_id or self.query_id) + '",operationName:"SearchTimeline";'
                    'import("./sign.o-fixture.js")')
            return 200, {"content-type": "application/javascript"}, text.encode()
        if parsed.path in ("/tesla", "/i/embed"):
            return 200, {"content-type": "text/html"}, (
                '<script src="https://abs.twimg.com/responsive-web/client-web/main.abcdef0123456789.js"></script>'
            ).encode()
        if not parsed.path.endswith("/SearchTimeline"):
            return 200, {"content-type": "application/json"}, b'{"data":{}}'
        query_id = parsed.path.split("/")[-2]
        variables = json.loads(parse_qs(parsed.query)["variables"][0])
        query = variables["rawQuery"]
        match = re.search(r'"\$([A-Z0-9_]+)"', query)
        symbol = match.group(1) if match else None
        self.requests[-1].update(query_id=query_id, symbol=symbol, cursor=variables.get("cursor"),
                                 count=variables.get("count"))
        # Canary is healthy unless the active operation itself is obsolete.
        if query_id != self.query_id or (symbol and label in self.restricted):
            return 404, {"content-type": "application/json"}, b'{"errors":[{"code":34,"message":"not found"}]}'
        code = 64 if label in self.suspended else 32 if label in self.expired and auth != NEW_AUTH else None
        if code is not None and symbol:
            return 200, {"content-type": "application/json"}, json.dumps(
                {"errors": [{"code": code, "message": "synthetic account refusal"}]}).encode()
        end = datetime.fromtimestamp(int(re.search(r"until_time:(\d+)", query).group(1)), UTC)
        page = int(variables.get("cursor", "0"))
        count = 3 if label in self.inconclusive else int(variables.get("count") or 20)
        entries = [tweet_entry(end - timedelta(minutes=1 + (i + page * count) * (10 if symbol else 2)),
                               symbol, i + page * count) for i in range(count)]
        if symbol and page == 0:
            entries.append({"entryId": "cursor-bottom", "content": {"cursorType": "Bottom", "value": "1"}})
        remaining = "1" if label in self.near_limit else "40"
        return 200, {"content-type": "application/json", "x-rate-limit-remaining": remaining,
                     "x-rate-limit-limit": "50"}, json.dumps({"data": {"entries": entries}}).encode()

    def install(self, patch):
        """Only DNS/port mapping, trust and deterministic transaction-key parsing are substituted."""
        import httpx
        from twscrape import xclid
        real_resolve = socket.getaddrinfo

        def resolve(host, port, *args, **kwargs):
            name = host.decode() if isinstance(host, bytes) else host
            if name in SYNTHETIC_HOSTS:
                return real_resolve("127.0.0.1", self.port, *args, **kwargs)
            if name not in ("127.0.0.1", "::1", "localhost", None):
                raise AssertionError("non-loopback resolution refused")
            return real_resolve(host, port, *args, **kwargs)

        patch.setattr(socket, "getaddrinfo", resolve)
        import anyio
        real_connect_tcp = anyio.connect_tcp

        async def connect_tcp(remote_host, remote_port, **kwargs):
            name = remote_host.decode() if isinstance(remote_host, bytes) else remote_host
            if name in SYNTHETIC_HOSTS:
                remote_host, remote_port = "127.0.0.1", self.port
            elif name not in ("127.0.0.1", "::1", "localhost"):
                raise AssertionError("non-loopback connection refused")
            return await real_connect_tcp(remote_host, remote_port, **kwargs)

        patch.setattr(anyio, "connect_tcp", connect_tcp)
        original = httpx.AsyncClient.__init__
        context = verified_context(self.certs["origin"]["root"])

        def init(client, *args, **kwargs):
            kwargs["verify"] = context
            kwargs["trust_env"] = False
            original(client, *args, **kwargs)

        patch.setattr(httpx.AsyncClient, "__init__", init)
        transport_init = httpx.AsyncHTTPTransport.__init__

        def trusted_transport(transport, *args, **kwargs):
            kwargs["verify"] = context
            kwargs["trust_env"] = False
            transport_init(transport, *args, **kwargs)

        patch.setattr(httpx.AsyncHTTPTransport, "__init__", trusted_transport)
        sync_init = httpx.Client.__init__

        def sync_client(client, *args, **kwargs):  # the feed collector's synchronous client (same trust seam)
            kwargs["verify"] = context
            kwargs["trust_env"] = False
            sync_init(client, *args, **kwargs)

        patch.setattr(httpx.Client, "__init__", sync_client)

        async def deterministic_keys(soup, client):
            # Keep the real create/get_tw_page_text/bootstrap requests. Only parsing keys is substituted.
            response = await client.get("https://abs.twimg.com/responsive-web/client-web/sign.o-fixture.js")
            response.raise_for_status()
            return list(range(32)), "synthetic-animation-key"

        patch.setattr(xclid, "load_keys", deterministic_keys)
        from twscrape import queue_client
        # The library caches one transaction-key generator per account for the process: each origin starts empty
        # so its own bootstrap requests are observed (restored on exit).
        patch.setattr(queue_client.XClIdGenStore, "items", {})

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)
        assert not self.thread.is_alive()
