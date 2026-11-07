"""Spawned NUL-framed browser fixture, never imported by production.

The native host supplies only the two pipe handles. Scripted HTTPS page loads
use CONNECT through the session relay, never a direct origin socket.
"""
from __future__ import annotations

import base64
import json
import os
import socket
import ssl
import subprocess
import sys
import uuid
from pathlib import Path

from api.tests.data.attention.fixture_seams import install_network_denial


def main():
    install_network_denial()
    flags = dict(arg[2:].split("=", 1) for arg in sys.argv[1:] if arg.startswith("--") and "=" in arg)
    inputs = tuple(int(v) for v in flags["remote-debugging-io-pipes"].split(","))
    if os.name == "nt":
        import msvcrt
        read_fd = msvcrt.open_osfhandle(inputs[0], os.O_RDONLY | os.O_BINARY)
        write_fd = msvcrt.open_osfhandle(inputs[1], os.O_WRONLY | os.O_BINARY)
    else:
        read_fd, write_fd = inputs
    profile = Path(flags["user-data-dir"])
    identity_path = profile / "fake_identity.json"
    if not identity_path.exists():
        identity_path.write_text(json.dumps({"identity": uuid.uuid4().hex}))
    identity = json.loads(identity_path.read_text())["identity"]
    script = json.loads(Path(flags["fake-script"]).read_text()) if "fake-script" in flags else {}
    cookies = script.get("cookies", [])
    jar = profile / "fake_cookies.json"
    if jar.exists():
        cookies = json.loads(jar.read_text())
    else:
        jar.write_text(json.dumps(cookies))
    grandchild = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"], close_fds=True,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    session_url, bodies, limits = {}, {}, {"maxResourceBufferSize": 65536, "maxTotalBufferSize": 262144}
    next_target = 0

    def send(value):
        data = json.dumps(value, separators=(",", ":")).encode() + b"\0"
        while data:
            data = data[os.write(write_fd, data):]

    def page_bytes(url, page):
        if not page.get("wire"):
            return page.get("body", "{}").encode()
        from urllib.parse import urlsplit
        parsed = urlsplit(url)
        proxy = flags["proxy-server"].removeprefix("http://").split(":")
        with socket.create_connection((proxy[0], int(proxy[1])), timeout=5) as tunnel:
            tunnel.sendall(f"CONNECT {parsed.hostname}:443 HTTP/1.1\r\nHost: {parsed.hostname}:443\r\n\r\n".encode())
            response = bytearray()
            while not response.endswith(b"\r\n\r\n") and len(response) < 16384:
                chunk = tunnel.recv(1)
                if not chunk:
                    raise OSError("fixture_connect_closed")
                response.extend(chunk)
            if not bytes(response).startswith(b"HTTP/1.1 200"):
                raise OSError("fixture_connect_refused")
            context = ssl.create_default_context(cafile=script["ca_file"])
            with context.wrap_socket(tunnel, server_hostname=parsed.hostname) as secure:
                target = parsed.path or "/"
                if parsed.query:
                    target += "?" + parsed.query
                secure.sendall(f"GET {target} HTTP/1.1\r\nHost: {parsed.hostname}\r\nConnection: close\r\n\r\n".encode())
                data = bytearray()
                while len(data) <= 4 * 1024 * 1024:
                    part = secure.recv(65536)
                    if not part:
                        break
                    data.extend(part)
                return bytes(data).split(b"\r\n\r\n", 1)[1]

    buffer = bytearray()
    try:
        while True:
            chunk = os.read(read_fd, 65536)
            if not chunk:
                return
            buffer.extend(chunk)
            if len(buffer) > 1048576 and 0 not in buffer:
                return
            while 0 in buffer:
                raw, _, remainder = buffer.partition(b"\0")
                buffer[:] = remainder
                request = json.loads(raw)
                method, params, sid = request["method"], request.get("params", {}), request.get("sessionId")
                result, error = {}, None
                envelope = {"id": request["id"]}
                if sid is not None:
                    envelope["sessionId"] = sid
                if method == "Browser.getVersion":
                    result = {"protocolVersion": "1.3", "product": "FakeBrowser/1.0", "fakeIdentity": identity,
                              "grandchild": grandchild.pid}
                elif method == "Target.createTarget":
                    next_target += 1
                    result = {"targetId": str(next_target)}
                elif method == "Target.attachToTarget":
                    result = {"sessionId": "s" + params["targetId"]}
                elif method == "Target.closeTarget":
                    result = {"success": True}
                elif method == "Network.enable":
                    limits.update(params)
                elif method == "Network.disable":
                    bodies.clear()
                elif method == "Network.getCookies":
                    result = {"cookies": cookies}
                elif method == "Runtime.evaluate":
                    result = {"result": {"type": "string", "value": session_url.get(sid, "about:blank")}}
                elif method == "Page.navigate":
                    url = params["url"]
                    page = script.get("pages", {}).get(url, {})
                    session_url[sid] = page.get("final_url", url)
                    request_id = str(next_target) + ":" + str(len(bodies))
                    def event(name, value):
                        send({"method": name, "params": value, "sessionId": sid})
                    event("Network.requestWillBeSent", {"requestId": request_id, "type": "Document",
                                                        "request": {"url": url, "method": "GET"}})
                    event("Page.frameNavigated", {"frame": {"id": "f1", "url": session_url[sid]}})
                    try:
                        body = page_bytes(url, page)
                        bodies[request_id] = body if len(body) <= limits["maxResourceBufferSize"] else None
                        while sum(len(b) for b in bodies.values() if b is not None) > limits["maxTotalBufferSize"]:
                            first = next(k for k, b in bodies.items() if b is not None)
                            bodies[first] = None
                        event("Network.responseReceived", {"requestId": request_id, "type": "Fetch", "response": {
                            "url": url, "status": page.get("status", 200), "mimeType": "application/json",
                            "fromDiskCache": page.get("fromDiskCache", False)}})
                        event("Network.loadingFinished", {"requestId": request_id, "encodedDataLength": len(body)})
                        result = {"frameId": "f1"}
                    except (OSError, KeyError, IndexError):
                        event("Network.loadingFailed", {"requestId": request_id, "errorText": "fixture_route_failed"})
                        result = {"errorText": "fixture_route_failed"}
                elif method == "Network.getResponseBody":
                    body = bodies.get(params["requestId"])
                    if body is None:
                        error = {"code": -32000, "message": "Request content was evicted from inspector cache"}
                    else:
                        result = {"body": base64.b64encode(body).decode(), "base64Encoded": True}
                elif method not in {"Page.enable", "Browser.close"}:
                    error = {"code": -32601, "message": "Unsupported fixture method"}
                envelope["error" if error else "result"] = error if error else result
                send(envelope)
                if method == "Browser.close":
                    return
    finally:
        grandchild.terminate()
        grandchild.wait(timeout=5)
        os.close(read_fd)
        os.close(write_fd)


if __name__ == "__main__":
    main()
