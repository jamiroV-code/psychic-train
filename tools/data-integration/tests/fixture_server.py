"""Loopback fixture server: a plain-HTTP forward proxy serving canned synthetic pages.

Tests fetch http://<host>.test/<path> (port 80, so the gate sees a normal URL) and point the
real client at this proxy. Only loopback is ever bound; nothing here reaches another machine.
Routes are chosen by path (and robots behaviour by host):
  /data/ok /data/slow /data/500 /data/429 /data/challenge
  /data/redirect-same /data/redirect-other /data/redirect-loop
  /robots.txt  (host robots-disallow.test -> Disallow /data/, robots-500.test -> 500,
                robots-garbage.test -> unparsable, robots-hang.test -> slow, others allow all)
"""
from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest

OK_BODY = b"<html><body><table><tr><th>d</th><th>v</th></tr><tr><td>2026-01-01</td><td>1</td></tr></table></body></html>"
CHALLENGE_BODY = b"<html><head><title>Just a moment...</title></head><body>Checking your browser before accessing. cf-chl-bypass</body></html>"
SLOW_SECONDS = 2.0


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # keep test output quiet
        pass

    def _send(self, code, body=b"", headers=None):
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Type", "text/html" if not self.path.endswith("robots.txt") else "text/plain")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parts = urlsplit(self.path)
        host = (parts.hostname or "").lower()
        path = parts.path
        srv = self.server
        with srv.lock:
            srv.requests.append({"host": host, "path": path, "ua": self.headers.get("User-Agent", ""),
                                 "absolute": bool(parts.scheme)})
        if path == "/robots.txt":
            return self._robots(host)
        if path == "/data/ok":
            return self._send(200, OK_BODY)
        if path == "/data/slow":
            time.sleep(SLOW_SECONDS)
            return self._send(200, OK_BODY)
        if path == "/data/500":
            return self._send(500, b"boom")
        if path == "/data/429":
            return self._send(429, b"slow down")
        if path == "/data/challenge":
            return self._send(200, CHALLENGE_BODY)
        if path == "/data/redirect-same":
            return self._send(302, b"", {"Location": f"http://{host}/data/ok"})
        if path == "/data/redirect-other":
            return self._send(302, b"", {"Location": "http://other.test/data/ok"})
        if path == "/data/redirect-unlisted":
            return self._send(302, b"", {"Location": "http://unlisted.test/data/ok"})
        if path == "/data/redirect-loop":
            return self._send(302, b"", {"Location": f"http://{host}/data/redirect-loop"})
        return self._send(404, b"nope")

    def _robots(self, host):
        if host == "robots-disallow.test":
            return self._send(200, b"User-agent: *\nDisallow: /data/\n")
        if host == "robots-500.test":
            return self._send(500, b"boom")
        if host == "robots-garbage.test":
            return self._send(200, b"\x00\xff<html>not robots</html>")
        if host == "robots-hang.test":
            time.sleep(SLOW_SECONDS)
            return self._send(200, b"User-agent: *\nAllow: /\n")
        return self._send(200, b"User-agent: *\nAllow: /\n")


class FixtureServer:
    def __init__(self):
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._httpd.daemon_threads = True
        self._httpd.lock = threading.Lock()
        self._httpd.requests = []
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._httpd.shutdown()
        self._httpd.server_close()

    @property
    def proxy_url(self) -> str:
        return f"http://127.0.0.1:{self._httpd.server_address[1]}"

    @property
    def requests(self) -> list[dict]:
        with self._httpd.lock:
            return list(self._httpd.requests)

    def paths(self, host=None) -> list[str]:
        return [r["path"] for r in self.requests if host is None or r["host"] == host]

    @property
    def count(self) -> int:
        return len(self.requests)


@pytest.fixture
def fixture_server():
    server = FixtureServer().start()
    try:
        yield server
    finally:
        server.stop()
