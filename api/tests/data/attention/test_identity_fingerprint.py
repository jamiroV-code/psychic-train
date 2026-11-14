"""B1.2 test-only bounded loopback capture. Never imported by collector runtime.

Wire layouts: RFC 8446 section 4.1.2 (ClientHello), RFC 9113 sections 3.4/6.5
(HTTP/2 preface/SETTINGS), RFC 8701 (GREASE). No browser baseline is assumed.
Run this file directly to print observed evidence; no accounts, proxy or public DNS.
"""
from __future__ import annotations

import json
import socket
import ssl
import struct
import tempfile
import threading
from pathlib import Path

import pytest

PREFACE = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"
LIMIT = 65536
TARGETS = ("chrome131", "safari170", "firefox133", "edge101")


class Cursor:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, n):
        if n < 0 or self.pos + n > len(self.data):
            raise ValueError("truncated vector")
        value = self.data[self.pos:self.pos + n]
        self.pos += n
        return value

    def number(self, n):
        return int.from_bytes(self.take(n), "big")

    def vector(self, n):
        return self.take(self.number(n))

    def done(self):
        if self.pos != len(self.data):
            raise ValueError("trailing bytes")


def words(data):
    if len(data) % 2:
        raise ValueError("odd uint16 vector")
    return [int.from_bytes(data[i:i + 2], "big") for i in range(0, len(data), 2)]


def parse_client_hello(body):
    c = Cursor(body)
    version = c.number(2)
    c.take(32)  # random bytes intentionally excluded from the summary
    c.vector(1)  # session id
    ciphers = words(c.vector(2))
    c.vector(1)  # compression methods
    extensions = Cursor(c.vector(2))
    c.done()
    ids, groups, formats, alpn = [], [], [], []
    while extensions.pos < len(extensions.data):
        kind = extensions.number(2)
        payload = extensions.vector(2)
        if kind in ids:
            raise ValueError("duplicate extension")
        ids.append(kind)
        part = Cursor(payload)
        if kind == 10:
            groups = words(part.vector(2))
            part.done()
        elif kind == 11:
            formats = list(part.vector(1))
            part.done()
        elif kind == 16:
            protocols = Cursor(part.vector(2))
            part.done()
            while protocols.pos < len(protocols.data):
                alpn.append(protocols.vector(1).decode("ascii"))
    def no_grease(values):
        return [v for v in values if not (v & 0x0F0F == 0x0A0A and v >> 8 == v & 255)]
    # JA3-style input only; not JA4 and not a browser-match assertion.
    ja3 = ",".join((str(version), "-".join(map(str, no_grease(ciphers))),
                    "-".join(map(str, no_grease(ids))), "-".join(map(str, no_grease(groups))),
                    "-".join(map(str, formats))))
    return {"legacy_version": version, "cipher_suites": ciphers, "extension_ids": ids,
            "supported_groups": groups, "point_formats": formats, "alpn": alpn, "ja3_input": ja3}


def parse_h2_initial(data):
    c = Cursor(data)
    if c.take(len(PREFACE)) != PREFACE:
        raise ValueError("invalid HTTP/2 preface")
    length, kind, flags, stream = c.number(3), c.number(1), c.number(1), c.number(4)
    if kind != 4 or flags != 0 or stream != 0 or length % 6:
        raise ValueError("invalid initial SETTINGS")
    payload = Cursor(c.take(length))
    settings = []
    while payload.pos < len(payload.data):
        settings.append([payload.number(2), payload.number(4)])
    c.done()
    return settings


def exact(conn, size):
    if size > LIMIT:
        raise ValueError("capture bound exceeded")
    data = bytearray()
    while len(data) < size:
        part = conn.recv(size - len(data))
        if not part:
            raise ValueError("unexpected EOF")
        data.extend(part)
    return bytes(data)


def receive_hello(conn):
    handshake = bytearray()
    records = bytearray()
    for _ in range(8):
        header = exact(conn, 5)
        if header[0] != 22:
            raise ValueError("not handshake record")
        body = exact(conn, int.from_bytes(header[3:5], "big"))
        records.extend(header + body)
        handshake.extend(body)
        if len(handshake) > LIMIT:
            raise ValueError("capture bound exceeded")
        if len(handshake) >= 4:
            length = int.from_bytes(handshake[1:4], "big")
            if handshake[0] != 1 or length > LIMIT:
                raise ValueError("not bounded ClientHello")
            if len(handshake) >= length + 4:
                return bytes(records), bytes(handshake[4:4 + length])
    raise ValueError("too many handshake records")


def certificate(directory):
    from datetime import UTC, datetime, timedelta
    from ipaddress import ip_address
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "B1 loopback test")])
    now = datetime.now(UTC)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ip_address("127.0.0.1"))]), False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), True).sign(key, hashes.SHA256()))
    cert_path, key_path = directory / "cert.pem", directory / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    return cert_path, key_path


def capture(target, context=None, cert_path=None):
    from curl_cffi import requests

    result, failures = {}, []
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(5)
        port = listener.getsockname()[1]

        def server():
            try:
                with listener.accept()[0] as raw:
                    raw.settimeout(5)
                    if context is None:
                        records, body = receive_hello(raw)
                        result.update(raw_records_hex=records.hex(), client_hello=parse_client_hello(body))
                    else:
                        with context.wrap_socket(raw, server_side=True) as tls:
                            result["negotiated_alpn"] = tls.selected_alpn_protocol()
                            preface = exact(tls, len(PREFACE))
                            header = exact(tls, 9)
                            payload = exact(tls, int.from_bytes(header[:3], "big"))
                            initial = preface + header + payload
                            result.update(h2_initial_hex=initial.hex(), settings=parse_h2_initial(initial))
            except Exception as exc:
                failures.append(exc)

        thread = threading.Thread(target=server, daemon=True)
        thread.start()
        try:
            # Explicitly bypass environment proxies; address is always a loopback IP.
            with requests.Session(impersonate=target, trust_env=False, proxy="", verify=str(cert_path) if cert_path else True) as session:
                try:
                    session.get(f"https://127.0.0.1:{port}/", timeout=5, allow_redirects=False)
                except requests.RequestsError as exc:
                    result["expected_client_error_code"] = int(exc.code)
                else:
                    raise AssertionError("capture endpoint intentionally supplies no HTTP response")
        finally:
            thread.join(7)
        if thread.is_alive():
            raise AssertionError("capture thread did not finish")
        if failures:
            raise failures[0]
    return result


def probe():
    import importlib.metadata as metadata

    with tempfile.TemporaryDirectory(prefix="b1-loopback-") as tmp:
        cert_path, key_path = certificate(Path(tmp))
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)
        context.set_alpn_protocols(["h2"])
        observed = {target: {"tls": capture(target), "http2": capture(target, context, cert_path)} for target in TARGETS}
    return {"scope": "loopback only; direct curl_cffi; no browser baseline; separate TLS and H2 connections",
            "versions": {name: metadata.version(name) for name in ("curl_cffi", "twscrape", "cryptography")},
            "ssl": ssl.OPENSSL_VERSION, "targets": observed}


def test_parsers_reject_truncated_or_invalid_input():
    for value in (b"", b"\x03\x03" + bytes(32), bytes(100)):
        with pytest.raises(ValueError):
            parse_client_hello(value)
    for value in (b"", PREFACE, PREFACE + b"\x00\x00\x01\x04\x00" + bytes(4) + b"x"):
        with pytest.raises(ValueError):
            parse_h2_initial(value)


def test_settings_preserve_order_and_duplicates():
    payload = struct.pack("!HIHI", 4, 65535, 4, 131072)
    assert parse_h2_initial(PREFACE + len(payload).to_bytes(3, "big") + b"\x04\x00" + bytes(4) + payload) == [[4, 65535], [4, 131072]]


def test_clienthello_parser_vectors_grease_and_extension_order():
    def vector(data, size=2):
        return len(data).to_bytes(size, "big") + data

    def extension(kind, payload):
        return kind.to_bytes(2, "big") + vector(payload)

    extensions = (extension(0x0A0A, b"") + extension(10, vector(bytes.fromhex("1a1a001d0017")))
                  + extension(11, vector(b"\x00", 1)) + extension(16, vector(vector(b"h2", 1))))
    prefix = bytes.fromhex("0303") + bytes(32) + vector(b"", 1) + vector(bytes.fromhex("2a2a1301")) + vector(b"\x00", 1)
    body = prefix + vector(extensions)
    parsed = parse_client_hello(body)
    assert parsed["ja3_input"] == "771,4865,10-11-16,29-23,0"
    assert parsed["extension_ids"] == [2570, 10, 11, 16]
    assert parsed["alpn"] == ["h2"]
    for end in range(len(body)):
        with pytest.raises(ValueError):
            parse_client_hello(body[:end])
    with pytest.raises(ValueError, match="duplicate"):
        parse_client_hello(prefix + vector(extensions + extension(10, vector(b""))))
    with pytest.raises(ValueError, match="odd"):
        words(b"x")


def test_receive_hello_reassembles_fragmented_records():
    body = b"synthetic"
    handshake = b"\x01" + len(body).to_bytes(3, "big") + body
    def record(part):
        return b"\x16\x03\x01" + len(part).to_bytes(2, "big") + part
    wire = record(handshake[:2]) + record(handshake[2:])

    class Fragmented:
        def __init__(self):
            self.pos = 0

        def recv(self, size):
            value = wire[self.pos:self.pos + min(size, 2)]
            self.pos += len(value)
            return value

    assert receive_hello(Fragmented()) == (wire, body)


def test_loopback_targets_emit_clienthello_and_h2_settings():
    pytest.importorskip("curl_cffi")
    pytest.importorskip("cryptography")
    evidence = probe()
    for observed in evidence["targets"].values():
        assert "h2" in observed["tls"]["client_hello"]["alpn"]
        assert observed["http2"]["negotiated_alpn"] == "h2"
        assert observed["http2"]["settings"]
        # Every truncated prefix of the captured H2 frame must fail closed.
        wire = bytes.fromhex(observed["http2"]["h2_initial_hex"])
        for end in range(len(wire)):
            with pytest.raises(ValueError):
                parse_h2_initial(wire[:end])


if __name__ == "__main__":
    print(json.dumps(probe(), indent=2))
