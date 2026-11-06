"""Network denial for real-ASGI tests, allowing only stdlib socketpair plumbing."""
from __future__ import annotations

import ipaddress
import socket
import threading

import httpx


def deny_network(monkeypatch) -> None:
    """Permit numeric loopback connects only during socketpair on that thread.

    Windows asyncio's Proactor loop constructs its self-pipe through Python's
    socketpair fallback. Endpoint code still cannot connect, even to loopback.
    TestClient's in-process ASGI transport is deliberately left untouched.
    """
    plumbing = threading.local()
    original_pair = socket.socketpair
    original_connect = socket.socket.connect

    def refuse(*args, **kwargs):
        raise AssertionError("status must not resolve/connect/admit")

    async def refuse_async(*args, **kwargs):
        refuse()

    def guarded_connect(sock, address):
        if getattr(plumbing, "active", False) and isinstance(address, tuple):
            try:
                loopback = ipaddress.ip_address(address[0]).is_loopback
            except (ValueError, TypeError):
                loopback = False
            if loopback:
                return original_connect(sock, address)
        return refuse()

    def socketpair(*args, **kwargs):
        previous = getattr(plumbing, "active", False)
        plumbing.active = True
        try:
            return original_pair(*args, **kwargs)
        finally:
            plumbing.active = previous

    monkeypatch.setattr(socket, "socketpair", socketpair)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket.socket, "sendto", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refuse)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", refuse_async)
