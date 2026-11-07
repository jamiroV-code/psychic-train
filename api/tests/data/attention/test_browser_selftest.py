"""A19 E2E: the REAL browser_selftest against the spawned fake browser with an injected TCP enumerator.

Proves wiring only, not Chromium behaviour. No installed browser is launched.
"""
from __future__ import annotations

import io
import json

import pytest

from api.data.attention import browser_host as h
from api.data.attention import browser_profile as p
from api.data.attention import browser_selftest as st
from api.tests.data.attention.test_browser_host import BINARY, POLICY, fake_spawn

VENDOR = ("52.97.202.66", 443)
LAN = ("192.168.10.213", 8009)


def make_host(tmp_path):
    return h.BrowserHost(BINARY, tmp_path / "profiles", cache_root=tmp_path, policy=POLICY,
                         spawn=fake_spawn, memory=lambda: 9999)


class Enumerator:
    """Scripted TCP table owned by the session's root PID (read from the host's launch record)."""

    def __init__(self, tmp_path, endpoints=(), state=st.ESTABLISHED):
        self.record = tmp_path / "attention" / "_pc_state" / "browser_launches" / f"{st.LABEL}.json"
        self.endpoints, self.state = endpoints, state

    def __call__(self):
        pid = json.loads(self.record.read_text())["pid"]
        rows = [(pid, "127.0.0.1", 50000, st.ESTABLISHED), (pid + 100000, "8.8.8.8", 443, st.ESTABLISHED)]
        return rows + [(pid, ip, port, self.state) for ip, port in self.endpoints]


def selftest(tmp_path, endpoints=(), *, state=st.ESTABLISHED, firewall=False):
    return st.run(make_host(tmp_path), cache_root=tmp_path, enumerator=Enumerator(tmp_path, endpoints, state),
                  firewall=lambda binary: firewall, window=.3, interval=.05)


def test_empty_table_is_tested_clean_and_admits_with_pipe_round_trip(tmp_path):
    with pytest.raises(h.BrowserFailure, match="browser_unadmitted"):
        make_host(tmp_path).launch("a", "a", 12345)
    result = selftest(tmp_path)
    assert result["outcome"] == "tested_clean" and result["product"] == "FakeBrowser/1.0"
    assert h.read_admission(tmp_path, BINARY, h.executable_version(BINARY))["outcome"] == "tested_clean"
    assert result["relay_refusals"] == {} and result["destination_classes"] == []


def test_vendor_residual_unaccepted_then_owner_acceptance_then_accepted(tmp_path):
    result = selftest(tmp_path, [VENDOR])
    assert result["outcome"] == "containment_residual_unaccepted"
    assert result["destination_classes"] == ["vendor_cloud_443"] and result["owners"] == ["browser"]
    with pytest.raises(h.BrowserFailure, match="containment_residual_unaccepted"):
        h.read_admission(tmp_path, BINARY, h.executable_version(BINARY))
    digest = result["residual_digest"]
    out = io.StringIO()
    assert st.main(["--binary", str(BINARY), "--cache-root", str(tmp_path), "--accept-residual", digest,
                    "--approve", "0" * 64], out=out) == 2
    assert st.main(["--binary", str(BINARY), "--cache-root", str(tmp_path), "--accept-residual", digest,
                    "--approve", digest], out=io.StringIO()) == 0
    again = selftest(tmp_path, [VENDOR])
    assert again["outcome"] == "accepted_residual"
    assert h.read_admission(tmp_path, BINARY, h.executable_version(BINARY))["outcome"] == "accepted_residual"


def test_lan_endpoint_refused_even_with_a_vendor_record(tmp_path):
    vendor = selftest(tmp_path, [VENDOR])
    st.accept_residual(tmp_path, BINARY, vendor["residual_digest"], vendor["residual_digest"])
    result = selftest(tmp_path, [VENDOR, LAN])
    assert result["outcome"] == "containment_residual_unaccepted"
    assert result["destination_classes"] == ["lan_device", "vendor_cloud_443"]
    with pytest.raises(h.BrowserFailure, match="containment_residual_unaccepted"):
        h.read_admission(tmp_path, BINARY, h.executable_version(BINARY))
    with pytest.raises(h.BrowserFailure, match="containment_residual_unaccepted"):
        st.accept_residual(tmp_path, BINARY, result["residual_digest"], result["residual_digest"])


def test_firewall_attestation_with_zero_established_is_contained(tmp_path):
    result = selftest(tmp_path, [VENDOR], state=2, firewall=True)  # SYN_SENT only: a blocked attempt
    assert result["outcome"] == "contained" and result["blocked_attempts"] == 1
    assert h.read_admission(tmp_path, BINARY, h.executable_version(BINARY))["outcome"] == "contained"
    established = selftest(tmp_path, [VENDOR], firewall=True)
    assert established["outcome"] == "containment_residual_unaccepted"


def test_classes_firewall_query_and_tcp_table_are_read_only():
    assert st.classify("52.97.211.210", 443) == "vendor_cloud_443"
    assert st.classify("40.99.218.82", 443) == "vendor_cloud_443"
    assert st.classify("40.99.218.82", 80) == "unclassified"
    assert st.classify("192.168.10.213", 8009) == "lan_device"
    assert st.classify("8.8.8.8", 443) == "unclassified"
    seen = []

    def runner(argv):
        seen.append(argv)
        return str(BINARY).upper() + "\r\n"
    assert st.firewall_attested(BINARY, runner)
    assert not st.firewall_attested(BINARY, lambda argv: "C:\\Other\\msedge.exe\n")
    assert not st.firewall_attested(BINARY, lambda argv: (_ for _ in ()).throw(OSError()))
    command = seen[0][-1]
    assert command.startswith("Get-NetFirewallRule") and "New-" not in command and "Set-" not in command
    rows = st.tcp_table()
    assert all(isinstance(pid, int) and isinstance(port, int) for pid, _ip, port, _s in rows)


def test_default_owner_policy_refuses_selftest_launch(tmp_path):
    host = h.BrowserHost(BINARY, tmp_path / "profiles", cache_root=tmp_path, policy=p.OWNER_DECISIONS,
                         spawn=fake_spawn, memory=lambda: 9999)
    with pytest.raises(h.BrowserFailure, match="profile_policy_unsatisfied"):
        st.run(host, cache_root=tmp_path, enumerator=lambda: [], firewall=lambda b: False, window=0)
    assert not (tmp_path / "attention" / "_probes").exists()
