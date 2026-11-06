"""Default-dependency DNS/address decisions with injected resolver results only."""
import asyncio
import socket
import threading

import pytest

from api.data.attention import x_proxy as p

def test_dns_rejects_any_private_answer_without_a_connection(monkeypatch):
    from api.data.attention.x_proxy_transport import resolve_public
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(p.ProxyFailure, match="proxy_address"):
        asyncio.run(resolve_public("fixture.invalid", 443))
