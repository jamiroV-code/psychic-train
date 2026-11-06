"""Behavioral boundaries for Windows-compatible ASGI network denial."""
import socket
import threading

import pytest

from api.tests.network_guard import deny_network


def test_only_socketpair_thread_can_connect_numeric_loopback(monkeypatch):
    sent = []
    monkeypatch.setattr(socket.socket, "connect", lambda sock, address: sent.append(address))

    def original_pair():
        socket.socket.connect(object(), ("127.0.0.1", 12345))
        with pytest.raises(AssertionError):
            socket.socket.connect(object(), ("localhost", 12345))
        with pytest.raises(AssertionError):
            socket.socket.connect(object(), ("192.0.2.1", 12345))
        errors = []

        def another_thread():
            try:
                socket.socket.connect(object(), ("127.0.0.1", 12345))
            except AssertionError:
                errors.append(True)

        thread = threading.Thread(target=another_thread)
        thread.start()
        thread.join()
        assert errors == [True]
        return "pair"

    monkeypatch.setattr(socket, "socketpair", original_pair)
    deny_network(monkeypatch)
    assert socket.socketpair() == "pair"
    assert sent == [("127.0.0.1", 12345)]
    with pytest.raises(AssertionError):
        socket.socket.connect(object(), ("127.0.0.1", 12345))
    with pytest.raises(AssertionError):
        socket.getaddrinfo("localhost", 12345)
    with pytest.raises(AssertionError):
        socket.create_connection(("127.0.0.1", 12345))


def test_socketpair_error_clears_plumbing_allowance(monkeypatch):
    def broken_pair():
        raise RuntimeError("synthetic plumbing failure")

    monkeypatch.setattr(socket, "socketpair", broken_pair)
    deny_network(monkeypatch)
    with pytest.raises(RuntimeError, match="synthetic plumbing failure"):
        socket.socketpair()
    with pytest.raises(AssertionError):
        socket.socket.connect(object(), ("127.0.0.1", 12345))


def test_real_stdlib_pair_works_without_opening_endpoint_network(monkeypatch):
    deny_network(monkeypatch)
    left, right = socket.socketpair()
    try:
        left.sendall(b"plumbing")
        assert right.recv(8) == b"plumbing"
        with pytest.raises(AssertionError):
            socket.socket.connect(left, ("127.0.0.1", 12345))
    finally:
        left.close()
        right.close()


def test_http_network_transports_are_denied_but_custom_transport_is_untouched(monkeypatch):
    import asyncio
    import httpx

    deny_network(monkeypatch)
    request = httpx.Request("GET", "http://127.0.0.1:12345")
    with pytest.raises(AssertionError):
        httpx.HTTPTransport().handle_request(request)
    with pytest.raises(AssertionError):
        asyncio.run(httpx.AsyncHTTPTransport().handle_async_request(request))
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))) as client:
        assert client.get("http://testserver/").status_code == 200
