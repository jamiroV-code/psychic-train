"""Permanent B2 test harness: loopback sockets and ephemeral synthetic trust roots.

A fixture proxy deliberately maps numeric port 443 to its ephemeral origin port.
This observes requested CONNECT and original TLS names, not remote-route proof.
No fixture option exists in production configuration or environment.
"""
from __future__ import annotations

import contextlib
import ipaddress
import json
import select
import shutil
import socket
import socketserver
import ssl
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


HOSTS = {"origin.test", "wrong-origin.test", "proxy.test", "wrong-proxy.test", "www.spamhaus.org", "raw.githubusercontent.com", "ipapi.co"}


def certificates(directory):
    binary = shutil.which("openssl")
    if binary is None:
        candidate = Path("C:/Program Files/Git/usr/bin/openssl.exe")
        binary = str(candidate) if candidate.is_file() else None
    if binary is None:
        raise AssertionError("B2 mandatory TLS acceptance requires an OpenSSL executable")
    result = {}
    for name, hosts in (("origin", ["origin.test", "www.spamhaus.org", "raw.githubusercontent.com", "ipapi.co"]), ("proxy", ["proxy.test"])):
        root, root_key = directory / (name + "-root.pem"), directory / (name + "-root.key")
        leaf, key, csr = directory / (name + ".pem"), directory / (name + ".key"), directory / (name + ".csr")
        ext = directory / (name + ".ext")
        ext.write_text("basicConstraints=critical,CA:FALSE\nextendedKeyUsage=serverAuth\nsubjectAltName=" + ",".join("DNS:" + host for host in hosts) + "\n", encoding="ascii")
        commands = [
            ["req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(root_key), "-out", str(root), "-days", "2", "-subj", "/CN=B2 synthetic " + name + " CA", "-addext", "basicConstraints=critical,CA:TRUE"],
            ["req", "-new", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key), "-out", str(csr), "-subj", "/CN=" + hosts[0]],
            ["x509", "-req", "-in", str(csr), "-CA", str(root), "-CAkey", str(root_key), "-CAcreateserial", "-out", str(leaf), "-days", "2", "-extfile", str(ext)],
        ]
        for command in commands:
            completed = subprocess.run([binary, *command], capture_output=True, timeout=30, check=False)
            if completed.returncode:
                raise AssertionError("synthetic TLS certificate generation failed")
        result[name] = {"root": root, "cert": leaf, "key": key}
    return result


def verified_context(root):
    context = ssl.create_default_context(cafile=str(root))
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    return context


class TLSMixin:
    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(5)
        try:
            return self.tls.wrap_socket(connection, server_side=True), address
        except BaseException:
            connection.close()
            raise


class TLSHTTPServer(TLSMixin, ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        self.fixture.errors.append("origin_handler")


class ProxyServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = False

    def handle_error(self, request, client_address):
        self.fixture.errors.append("proxy_handler")


class TLSProxyServer(TLSMixin, ProxyServer):
    pass


class WireFixture:
    def __init__(self, certs, *, https_proxy=False):
        self.certs = certs
        self.requests, self.connects, self.origin_sni, self.proxy_sni, self.errors = [], [], [], [], []
        self.responses = {}
        self.https_proxy = https_proxy
        owner = self

        class Origin(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            def log_message(self, *args):
                pass
            def do_POST(self):
                length = int(self.headers.get("content-length", "0"))
                if length > 65536:
                    self.close_connection = True
                    return
                self.rfile.read(length)
                self.do_GET()
            def do_GET(self):
                host = self.headers.get("host", "")
                owner.requests.append({"host": host, "path": self.path, "headers": dict(self.headers), "method": self.command})
                response = owner.responses.get((host.split(":", 1)[0], self.path),
                    owner.responses.get(self.path, owner.responses.get("*")))
                if callable(response):
                    response = response()
                if response == "disconnect":
                    self.close_connection = True
                    self.connection.shutdown(socket.SHUT_RDWR)
                    return
                if response is None:
                    response = (200, {"content-type": "application/json"}, json.dumps(dict(self.headers)).encode())
                status, headers, body = response
                self.send_response(status)
                self.send_header("content-length", str(len(body)))
                self.send_header("connection", "close")
                for key, value in headers.items(): self.send_header(key, value)
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (OSError, ssl.SSLError):
                    pass
                self.close_connection = True

        self.origin = TLSHTTPServer(("127.0.0.1", 0), Origin)
        self.origin.fixture = self
        self.origin.tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.origin.tls.load_cert_chain(str(certs["origin"]["cert"]), str(certs["origin"]["key"]))
        self.origin.tls.set_alpn_protocols(["http/1.1"])
        self.origin.tls.set_servername_callback(lambda _s, name, _c: owner.origin_sni.append(name))
        self.origin_port = self.origin.server_address[1]

        class Proxy(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.settimeout(5)
                header = bytearray()
                while b"\r\n\r\n" not in header:
                    chunk = self.request.recv(4096)
                    if not chunk: return
                    header.extend(chunk)
                    if len(header) > 16384: return
                raw, remainder = bytes(header).split(b"\r\n\r\n", 1)
                rows = raw.split(b"\r\n")
                parts = rows[0].split(b" ")
                if len(parts) != 3 or parts[0] != b"CONNECT": return
                authority = parts[1].decode("ascii")
                host, port = authority.rsplit(":", 1)
                host = host.strip("[]")
                try:
                    address = ipaddress.ip_address(host)
                    if not address.is_loopback or int(port) not in (443, owner.origin_port):
                        return  # the harness itself can never dial a non-fixture destination
                except ValueError:
                    return
                headers = {}
                for row in rows[1:]:
                    key, value = row.split(b":", 1)
                    headers[key.decode().lower()] = value.strip().decode()
                owner.connects.append({"authority": authority, "headers": headers})
                upstream = socket.create_connection(("127.0.0.1", owner.origin_port), timeout=5)
                try:
                    self.request.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
                    if remainder: upstream.sendall(remainder)
                    sockets = [self.request, upstream]
                    while True:
                        readable, _, _ = select.select(sockets, [], [], 5)
                        if not readable: return
                        for source in readable:
                            try:
                                data = source.recv(65536)
                                if not data: return
                                destination = upstream if source is self.request else self.request
                                destination.sendall(data)
                            except (OSError, ssl.SSLError):
                                return
                finally:
                    upstream.close()

        self.proxy = (TLSProxyServer if https_proxy else ProxyServer)(("127.0.0.1", 0), Proxy)
        self.proxy.fixture = self
        if https_proxy:
            self.proxy.tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            self.proxy.tls.load_cert_chain(str(certs["proxy"]["cert"]), str(certs["proxy"]["key"]))
            self.proxy.tls.set_alpn_protocols(["http/1.1"])
            self.proxy.tls.set_servername_callback(lambda _s, name, _c: owner.proxy_sni.append(name))
        self.proxy_port = self.proxy.server_address[1]
        self.threads = [threading.Thread(target=server.serve_forever, daemon=True) for server in (self.origin, self.proxy)]
        for thread in self.threads: thread.start()

    @property
    def origin_url(self): return f"https://origin.test:{self.origin_port}"
    @property
    def proxy_url(self): return f"{'https' if self.https_proxy else 'http'}://proxy.test:{self.proxy_port}"

    async def resolve(self, host, port):
        if host not in HOSTS:
            raise AssertionError("fixture resolver rejected non-fixture host")
        return "127.0.0.1"

    def close(self):
        for server in (self.proxy, self.origin): server.shutdown()
        for server in (self.proxy, self.origin): server.server_close()
        for thread in self.threads: thread.join(6)
        assert all(not thread.is_alive() for thread in self.threads)


@contextlib.contextmanager
def fixture(*, https_proxy=False):
    with tempfile.TemporaryDirectory(prefix="b2-test-tls-") as directory:
        wire = WireFixture(certificates(Path(directory)), https_proxy=https_proxy)
        try:
            yield wire
        finally:
            wire.close()
