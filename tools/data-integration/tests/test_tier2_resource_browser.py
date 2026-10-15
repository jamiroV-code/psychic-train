"""Real-browser resource-host checks (Hybrid, outside CI): needs Chromium and scrapling."""
from __future__ import annotations

import socket
import threading

import pytest

pytestmark = pytest.mark.browser

from data_integration import status as st  # noqa: E402
from data_integration.approvals import ApprovalStore  # noqa: E402
from data_integration.fetch_tier2 import default_navigator, fetch  # noqa: E402
from data_integration.gate import request_access  # noqa: E402
from data_integration.politeness import Politeness  # noqa: E402
from plugin_fixture_server import fixture_server  # noqa: E402,F401
from _helpers import fixed_clock, make_record  # noqa: E402


class ConnectRecorder:
    """Tiny loopback listener that records CONNECT targets and refuses them."""

    def __init__(self):
        self.targets: list[str] = []
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.url = f"http://127.0.0.1:{self.sock.getsockname()[1]}"
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            data = conn.recv(4096).decode("latin-1", "replace")
            if data.startswith("CONNECT "):
                self.targets.append(data.split()[1])
            conn.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            conn.close()


def _pass(tmp_path, resource_hosts):
    store = ApprovalStore(tmp_path / "ap")
    store.write(make_record(tier=2, hosts=("example.test",), pages=("/",), resource_hosts=resource_hosts))
    return request_access("example-src", 2, store, fixed_clock())


def test_blocked_hosts_are_named_without_path(fixture_server, tmp_path):
    out = fetch("http://example.test/js/table", _pass(tmp_path, ()), navigator=default_navigator,
                proxy=fixture_server.proxy_url, timeout=30.0, politeness=Politeness(min_delay=0, sleeper=lambda s: None))
    assert out.status in (st.OK, st.REFUSED)
    assert "?" not in (out.detail or "") and "/js/" not in (out.detail or "")


def test_listed_host_is_contacted_unlisted_is_not(tmp_path):
    rec = ConnectRecorder()
    pass_ = _pass(tmp_path, ("cdn.example.test",))
    out = fetch("https://example.test/", pass_, navigator=default_navigator, proxy=rec.url, timeout=15.0,
                politeness=Politeness(min_delay=0, sleeper=lambda s: None))
    assert out is not None
    assert all(not t.startswith("evil.") for t in rec.targets)
