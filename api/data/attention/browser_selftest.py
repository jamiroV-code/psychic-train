"""A19 browser admission self-test with the OS TCP-table sentinel and residual acceptance.

Run once per (browser path, exact executable version, flag digest) by the owner:
``python -m api.data.attention.browser_selftest --binary <msedge.exe> --cache-root <cache>``.
It launches a DISPOSABLE profile through a real relay that forwards nothing,
runs the pipe ``Browser.getVersion`` round trip, keeps loopback TCP/UDP
sentinels open and polls the OS TCP table for every PID in the session's Job
Object for the whole window. Closed outcomes: ``tested_clean``,
``containment_residual_unaccepted``, ``accepted_residual``, ``contained``;
a failed pipe is ``cdp_pipe_unavailable`` and a sentinel hit leaves the browser
``browser_unadmitted`` (no record is written in either case).

Residual acceptance: ``--accept-residual <digest> --approve <digest>`` writes
``residual_acceptance_<digest>.json`` only when the digest equals the one
recomputed from the latest admission record's OWN observed classes and those
classes are exactly ``vendor_cloud_443``. ``lan_device``, ``unclassified``,
UDP and non-443 endpoints are never acceptable. The tool never creates, edits
or applies firewall state; the firewall attestation is a read-only query.
This proves no claim about connections between polls, UDP to non-loopback
addresses or other processes (PROBES-2 BP1c).
"""
from __future__ import annotations

import argparse
import ctypes
import ipaddress
import json
import math
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

from api.data.attention import browser_cdp as cdp
from api.data.attention import browser_host as bh
from api.data.attention import browser_profile as profiles
from api.data.attention import browser_relay as relay_mod
from api.data.attention.x_proxy_private import atomic_json

OUTCOMES = ("tested_clean", "containment_residual_unaccepted", "accepted_residual", "contained")
ACCEPTABLE = frozenset({"vendor_cloud_443"})
# Code-owned Microsoft cloud ranges covering the BP1c observations (52.97.x, 40.99.x) plus
# well-known Microsoft edge ranges. [INFERENCE] range ownership from public registry data.
VENDOR_CLOUD = tuple(ipaddress.ip_network(n) for n in (
    "40.96.0.0/12", "52.96.0.0/12", "13.107.0.0/16", "204.79.197.0/24", "150.171.0.0/16", "2603:1000::/24"))
RULE_NAME = "mysite-collector-browser-block"
ESTABLISHED = 5
LABEL = "selftest"
PROFILE = "selftest"


def classify(address: str, port: int) -> str:
    ip = ipaddress.ip_address(address)
    if port == 443 and any(ip.version == n.version and ip in n for n in VENDOR_CLOUD):
        return "vendor_cloud_443"
    if ip.is_private or ip.is_link_local:
        return "lan_device"
    return "unclassified"


def tcp_table():
    """`GetExtendedTcpTable` (TCP_TABLE_OWNER_PID_ALL) rows: (pid, remote_ip, remote_port, state)."""
    iphlp = ctypes.WinDLL("iphlpapi")
    rows = []
    for family, size, parse in ((socket.AF_INET, 24, _row4), (socket.AF_INET6, 56, _row6)):
        length = ctypes.c_ulong(0)
        iphlp.GetExtendedTcpTable(None, ctypes.byref(length), False, family, 5, 0)
        for _ in range(3):
            buf = ctypes.create_string_buffer(length.value + 4096)
            length = ctypes.c_ulong(len(buf))
            if iphlp.GetExtendedTcpTable(buf, ctypes.byref(length), False, family, 5, 0) == 0:
                break
        else:
            raise bh.BrowserFailure("tcp_table_unreadable")
        count = struct.unpack_from("<I", buf.raw, 0)[0]
        if count * size + 4 > len(buf.raw):
            raise bh.BrowserFailure("tcp_table_unreadable")
        rows.extend(parse(buf.raw, 4 + i * size) for i in range(count))
    return rows


def _port(value):
    return socket.ntohs(value & 0xFFFF)


def _row4(raw, offset):
    state, _la, _lp, ra, rp, pid = struct.unpack_from("<6I", raw, offset)
    return pid, socket.inet_ntoa(struct.pack("<I", ra)), _port(rp), state


def _row6(raw, offset):
    ra = raw[offset + 24:offset + 40]
    rp, state, pid = struct.unpack_from("<3I", raw, offset + 44)
    return pid, str(ipaddress.IPv6Address(ra)), _port(rp), state


def _powershell(argv):
    completed = subprocess.run(argv, capture_output=True, timeout=30, check=False, text=True,
                               stdin=subprocess.DEVNULL)
    return completed.stdout if completed.returncode == 0 else ""


def firewall_attested(binary, runner=_powershell) -> bool:
    """Read-only query for an enabled outbound block rule on exactly this executable."""
    script = (f"Get-NetFirewallRule -DisplayName '{RULE_NAME}' -ErrorAction SilentlyContinue | "
              "Where-Object { $_.Enabled -eq 'True' -and $_.Direction -eq 'Outbound' -and $_.Action -eq 'Block' } | "
              "Get-NetFirewallApplicationFilter | Select-Object -ExpandProperty Program")
    try:
        output = runner(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script])
    except Exception:
        return False
    target = os.path.normcase(os.path.realpath(binary))
    return any(os.path.normcase(line.strip()) == target for line in str(output).splitlines() if line.strip())


class LoopbackSentinels:
    """Direct-hit sentinels on loopback: any TCP accept or UDP datagram is a hit."""

    def __init__(self):
        self.tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp.bind(("127.0.0.1", 0))
        self.tcp.listen(8)
        self.tcp.settimeout(.2)
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.bind(("127.0.0.1", 0))
        self.udp.settimeout(.2)
        self.hits = 0
        self._stop = threading.Event()
        self._threads = [threading.Thread(target=self._loop, args=(f,), daemon=True)
                         for f in (self._accept, self._datagram)]
        for thread in self._threads:
            thread.start()

    def _accept(self):
        conn, _ = self.tcp.accept()
        conn.close()

    def _datagram(self):
        self.udp.recvfrom(2048)

    def _loop(self, step):
        while not self._stop.is_set():
            try:
                step()
                self.hits += 1
            except (TimeoutError, socket.timeout):
                continue
            except OSError:
                return

    def close(self):
        self._stop.set()
        for thread in self._threads:
            thread.join(2)
        self.tcp.close()
        self.udp.close()


class TableObserver:
    """Polls the TCP table for the Job Object's PIDs for the whole window."""

    def __init__(self, session, enumerator, interval):
        self.session, self.enumerator, self.interval = session, enumerator, interval
        self.endpoints = {}
        self.failure = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="collector-selftest-tcp", daemon=True)

    def start(self):
        self._thread.start()

    def poll(self):
        pids = set(self.session.job.pids())
        for pid, address, port, state in self.enumerator():
            if pid not in pids:
                continue
            ip = ipaddress.ip_address(address)
            if ip.is_loopback or ip.is_unspecified:
                continue
            owner = "browser" if pid == self.session.pid else "child"
            key = (str(ip), int(port))
            entry = self.endpoints.setdefault(key, {"established": False, "owner": owner})
            entry["established"] = entry["established"] or state == ESTABLISHED

    def _run(self):
        while True:
            try:
                self.poll()
            except Exception:
                self.failure = "tcp_table_unreadable"
                return
            if self._stop.wait(self.interval):
                return

    def stop(self):
        self._stop.set()
        self._thread.join(10)


def run(host, *, cache_root, enumerator=tcp_table, firewall=firewall_attested, window=20.0, interval=.5,
        headless=True):
    """Admission run on `host` (a real BrowserHost). Returns a nonsecret result dict."""
    if not (isinstance(window, (int, float)) and math.isfinite(window) and 0 <= window <= 600):
        raise bh.BrowserFailure("browser_unadmitted")
    version = bh.executable_version(host.binary)
    # A relay with an EMPTY allowlist: everything reaching it is refused and counted; nothing is forwarded.
    relay = relay_mod.Relay("reddit", LABEL, "direct", revision=LABEL, hosts=(),
                            admission=lambda: relay_mod.Admission(LABEL, math.inf))
    sentinels = LoopbackSentinels()
    observer = None
    product = None
    try:
        relay.start()
        with host._launch(LABEL, PROFILE, relay.port, headless=headless, admission_run=True) as session:
            observer = TableObserver(session, enumerator, interval)
            observer.start()
            try:
                client = cdp.CdpClient(session.pipe, "session_check", cdp.UrlPolicy("reddit"))
                product = client.version().get("product")
            except Exception:
                return {"outcome": "cdp_pipe_unavailable", "version": version}
            observer._stop.wait(window)
            observer.stop()
            observer.poll()  # last look before shutdown
    finally:
        if observer is not None:
            observer.stop()
        sentinels.close()
        health = relay.health()
        relay.close()
    if observer.failure:
        return {"outcome": "browser_unadmitted", "reason": "tcp_table_unreadable", "version": version}
    if sentinels.hits or health["forwarded"]:
        return {"outcome": "browser_unadmitted", "reason": "sentinel_failed", "version": version}
    endpoints = observer.endpoints
    established = {k: v for k, v in endpoints.items() if v["established"]}
    blocked = len(endpoints) - len(established)
    classes = sorted({classify(ip, port) for ip, port in established})
    residual = None
    if not established and firewall(host.binary):
        outcome, classes = "contained", []
    elif not endpoints:
        outcome, classes = "tested_clean", []
    else:
        classes = classes or sorted({classify(ip, port) for ip, port in endpoints})
        residual = bh.residual_digest(host.binary, version, classes)
        acceptance = Path(cache_root) / "attention" / "_probes" / f"residual_acceptance_{residual}.json"
        accepted = set(classes) <= ACCEPTABLE and acceptance.is_file()
        outcome = "accepted_residual" if accepted else "containment_residual_unaccepted"
    digest = bh.write_admission(cache_root, host.binary, version, outcome=outcome, destination_classes=classes)
    if outcome == "accepted_residual":
        try:
            bh.read_admission(cache_root, host.binary, version)
        except bh.BrowserFailure:
            outcome = "containment_residual_unaccepted"
            bh.write_admission(cache_root, host.binary, version, outcome=outcome, destination_classes=classes)
    return {"outcome": outcome, "version": version, "admission_digest": digest, "residual_digest": residual,
            "destination_classes": classes, "blocked_attempts": blocked,
            "owners": sorted({v["owner"] for v in established.values()}), "product": product,
            "relay_refusals": health["relay_refusals"], "background_refused": health["background_refused"]}


def accept_residual(cache_root, binary, digest, approve):
    """Owner acceptance (O-2); only an exact, recomputed vendor_cloud_443 digest is honoured."""
    bh.require(isinstance(digest, str) and digest == approve and len(digest) == 64, "containment_residual_unaccepted")
    version = bh.executable_version(binary)
    root = Path(cache_root) / "attention" / "_probes"
    path = root / f"browser_admission_{bh.admission_digest(binary, version)}.json"
    try:
        record = json.loads(path.read_bytes())
    except (OSError, ValueError):
        raise bh.BrowserFailure("browser_unadmitted") from None
    classes = record.get("destination_classes")
    bh.require(record.get("outcome") in ("containment_residual_unaccepted", "accepted_residual")
               and record.get("version") == version and record.get("flag_digest") == bh.FLAG_DIGEST
               and classes == ["vendor_cloud_443"]
               and bh.residual_digest(binary, version, classes) == digest, "containment_residual_unaccepted")
    target = root / f"residual_acceptance_{digest}.json"
    atomic_json(target, {"schema": 1, "browser_version": version, "flag_digest": bh.FLAG_DIGEST,
                         "residual_kind": "browser_process_direct_tcp", "destination_classes": classes,
                         "accepted_utc": datetime.now(timezone.utc).isoformat()})
    return target


def main(argv=None, *, out=sys.stdout):
    parser = argparse.ArgumentParser(prog="python -m api.data.attention.browser_selftest")
    parser.add_argument("--binary", required=True)
    parser.add_argument("--cache-root", required=True)
    parser.add_argument("--window", type=float, default=20.0)
    parser.add_argument("--accept-residual")
    parser.add_argument("--approve")
    args = parser.parse_args(argv)
    binary = Path(args.binary)
    try:
        if args.accept_residual is not None:
            accept_residual(args.cache_root, binary, args.accept_residual, args.approve)
            result = {"accepted": args.accept_residual}
        else:
            disposable = Path(tempfile.mkdtemp(prefix="mysite-browser-selftest-"))
            try:
                host = bh.BrowserHost(binary, disposable / "profiles", cache_root=args.cache_root,
                                      policy=profiles.OWNER_DECISIONS)
                result = run(host, cache_root=args.cache_root, window=args.window)
            finally:
                shutil.rmtree(disposable, ignore_errors=True)
    except bh.BrowserFailure as exc:
        out.write(json.dumps({"outcome": exc.reason}, sort_keys=True) + "\n")
        return 2
    out.write(json.dumps(result, sort_keys=True) + "\n")
    return 0 if result.get("outcome") in OUTCOMES or "accepted" in result else 2


if __name__ == "__main__":
    raise SystemExit(main())
