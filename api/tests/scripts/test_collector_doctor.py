"""S-OpsDoctor (OD-1): states, exit codes, UNKNOWN never PASS, read-only firewall query, injected selftest runner,
Stage-3 trigger measurement (AC16), doctor.json in the S-StatusAPI layout, offline and secret-free output."""
from __future__ import annotations

import io
import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from api.analytics.attention import sources
from api.data import cache
from api.data.attention import web_queries
from api.scripts import collector_doctor as doc

NOW = datetime(2026, 11, 8, 9, 0, tzinfo=timezone.utc)
REPO = Path(__file__).resolve().parents[3]
MARKER = "zz_secret_marker_9f3"


def _deps(**kw):
    calls = kw.pop("calls", [])

    def query(argv):
        calls.append(list(argv))
        return kw.get("query_result", (0, "1"))

    base = dict(cache_root=cache.CACHE_ROOT, now=NOW, env=dict(web_queries_env()), query_runner=query,
                selftest_runner=lambda argv: 0, private_verifier=lambda p: None,
                profile_verifier=lambda root, cache_root: None, machine_lock=lambda: 0, memory=lambda: 8000.0,
                browser_version=lambda b: "1.0", disk_free_mb=lambda p: 100000.0, dist_lookup=lambda name: None)
    base.update({k: v for k, v in kw.items() if k != "query_result"})
    return doc.Deps(**base)


def web_queries_env():
    from api.data.attention import twscrape_reader
    return twscrape_reader.REQUIRED_ENV


def _queries(tmp_path, **collector):
    raw = json.loads((REPO / "api" / "data" / "attention_queries.json").read_text(encoding="utf-8"))
    raw["collector"].update(collector)
    p = tmp_path / "private" / "queries.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(raw), encoding="utf-8")
    web_queries.load(p)  # the fixture itself must be a valid strict config
    return p


def _by_name(checks):
    return {c.name: c for c in checks}


def test_exit_codes_and_unknown_never_pass():
    ok = doc.Check("a", doc.PASS, "x")
    assert doc.exit_code([ok]) == 0 and doc.overall([ok]) == doc.PASS
    assert doc.exit_code([ok, doc.Check("b", doc.UNKNOWN, "y")]) == 1
    assert doc.overall([ok, doc.Check("b", doc.UNKNOWN, "y")]) == doc.UNKNOWN
    assert doc.exit_code([ok, doc.Check("b", doc.WARN, "y")]) == 1
    assert doc.exit_code([doc.Check("b", doc.WARN, "y"), doc.Check("c", doc.FAIL, "z")]) == 2


def test_no_config_warns_and_writes_status_layout(isolated_cache):
    out = io.StringIO()
    code = doc.main([], out=out, deps=_deps())
    assert code in (1, 2)
    written = json.loads(doc.doctor_path(cache.CACHE_ROOT).read_text(encoding="utf-8"))
    assert {"state", "checked_at", "failures", "warnings"} <= set(written)
    assert written["state"] != doc.PASS and "config" in written["warnings"]
    status = sources._doctor()
    assert status.state == written["state"] or (status.state == "UNKNOWN" and written["state"] == doc.UNKNOWN)
    assert status.warnings == len(written["warnings"]) and status.failures == len(written["failures"])


def test_invalid_config_fails_without_echoing_content(isolated_cache, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"version": 1, "collector": {"x_accounts_db_path": MARKER}}), encoding="utf-8")
    out = io.StringIO()
    assert doc.main(["--queries", str(bad)], out=out, deps=_deps()) == 2
    assert MARKER not in out.getvalue() and str(tmp_path) not in out.getvalue()
    assert _by_name(doc.run_checks(_deps(queries_path=bad)))["config"].state == doc.FAIL


def test_valid_config_runs_every_subsystem_check(isolated_cache, tmp_path):
    q = _queries(tmp_path)
    names = set(_by_name(doc.run_checks(_deps(queries_path=q))))
    assert {"config", "x_env", "x_pin", "x_curl", "x_accounts", "x_backfill", "x_rest_ready", "x_cookies",
            "proxy_files", "query_ids", "browser_path", "profile_acl", "profile_unique", "relay_refusals",
            "browser_live", "containment", "firewall_rule", "memory", "kernel_lock", "reddit_accounts",
            "reddit_live_gates", "feed_methods", "stage3_trigger", "disk", "scheduled_tasks", "heartbeat",
            "daily_report", "facts_retention"} <= names


def test_pending_evidence_is_never_pass(isolated_cache, tmp_path):
    checks = _by_name(doc.run_checks(_deps(queries_path=_queries(tmp_path)), live=True, selftest=True))
    assert checks["selftest"].state == doc.PASS  # the synthetic cycle passed ...
    for pid in ("PX1", "PX5", "PR1", "PR2"):  # ... yet no recorded live evidence is PASS
        assert checks[f"live_{pid}"].state == doc.UNKNOWN and checks[f"live_{pid}"].reason == "needs_probe"
    assert checks["heartbeat"].state != doc.PASS and checks["daily_report"].state != doc.PASS
    assert checks["x_backfill"].state == doc.WARN  # committed default 14 > 7


def test_firewall_rule_present_absent_unknown_read_only():
    calls = []
    assert doc.check_firewall(_deps(calls=calls, query_result=(0, "1\n"))).reason == "present"
    assert doc.check_firewall(_deps(query_result=(0, "0"))).reason == "absent"
    assert doc.check_firewall(_deps(query_result=(1, ""))).state == doc.UNKNOWN
    assert doc.check_firewall(_deps(query_result=(0, "garbage"))).state == doc.UNKNOWN
    script = " ".join(calls[0])
    assert "Get-NetFirewallRule" in script and doc.FIREWALL_RULE_NAME in script
    for verb in ("New-", "Set-", "Remove-", "Enable-", "Disable-", "netsh"):
        assert verb not in script
    for name in doc.TASK_NAMES:
        task = " ".join(doc.task_query_argv(name))
        assert "Get-ScheduledTask" in task and "Register-" not in task and "Unregister-" not in task


def test_selftest_uses_injected_runner_with_acceptance_module():
    seen = []
    ok = doc.check_selftest(_deps(selftest_runner=lambda argv: seen.append(argv) or 0))
    assert ok.state == doc.PASS and seen[0][-2:] == ["-m", "api.tests.cycle.acceptance"]
    assert doc.check_selftest(_deps(selftest_runner=lambda argv: 3)).state == doc.FAIL

    def boom(argv):
        raise FileNotFoundError("x")
    assert doc.check_selftest(_deps(selftest_runner=boom)).state == doc.FAIL


def _pool(accounts):
    p = cache.CACHE_ROOT / "attention" / "_pc_state" / "x_pool.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"accounts": accounts}), encoding="utf-8")


def test_stage3_trigger_measurement(isolated_cache):
    cfg = SimpleNamespace(x_proxy_required=True, x_accounts=("a1", "a2"))
    assert doc.check_stage3_trigger(_deps(), None).state == doc.UNKNOWN
    unrouted = SimpleNamespace(x_proxy_required=False, x_accounts=("a1",))
    assert doc.check_stage3_trigger(_deps(), unrouted).reason == "gateway_not_built_trigger_unmeasured"
    _pool({"a1": {"proxy_health": "healthy"}, "a2": {"proxy_health": "quarantined"}})
    not_met = doc.check_stage3_trigger(_deps(), cfg)
    assert not_met.state == doc.PASS and not_met.reason.startswith("gateway_not_built_trigger_not_met")
    _pool({"a1": {"proxy_health": "quarantined"}, "a2": {"proxy_health": "quarantined"}})
    met = doc.check_stage3_trigger(_deps(), cfg)
    assert met.state == doc.WARN and met.reason == "gateway_not_built_trigger_met"


def test_feed_methods_stale_after_13_11_26(isolated_cache, tmp_path):
    q = _queries(tmp_path)
    before = _by_name(doc.run_checks(_deps(queries_path=q, now=datetime(2026, 11, 12, tzinfo=timezone.utc))))
    after = _by_name(doc.run_checks(_deps(queries_path=q, now=datetime(2026, 11, 14, tzinfo=timezone.utc))))
    assert before["feed_methods"].state == doc.PASS
    assert after["feed_methods"].state == doc.WARN and after["feed_methods"].reason == "feed_methods_stale"


def test_browser_paths_never_printed_and_missing_browser_fails(isolated_cache, tmp_path):
    q = _queries(tmp_path, browser_path=str(tmp_path / MARKER / "msedge.exe"),
                 browser_profiles_dir=str(tmp_path / MARKER / "profiles"))
    out = io.StringIO()
    assert doc.main(["--queries", str(q), "--json"], out=out, deps=_deps()) == 2
    text = out.getvalue() + doc.doctor_path(cache.CACHE_ROOT).read_text(encoding="utf-8")
    assert MARKER not in text and str(tmp_path) not in text
    checks = _by_name(doc.run_checks(_deps(queries_path=q)))
    assert checks["browser_path"].state == doc.FAIL and checks["browser_live"].state == doc.UNKNOWN


def test_proxy_required_lists_missing_files_by_key(isolated_cache, tmp_path):
    cfg = SimpleNamespace(x_proxy_required=True, x_proxy_list_path=None, x_proxy_assignments_path=None,
                          x_proxy_policy_path=None)
    [check] = doc._proxy_checks(_deps(), cfg, [], None, None)
    assert check.state == doc.FAIL and "x_proxy_list_path" in check.fix and "x_proxy_policy_path" in check.fix


def test_doctor_is_offline(isolated_cache, tmp_path, monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    assert doc.main(["--queries", str(_queries(tmp_path)), "--live"], out=io.StringIO(), deps=_deps()) in (1, 2)


def test_doctor_ps1_wrapper_shape():
    text = (REPO / "deploy" / "doctor.ps1").read_text(encoding="utf-8")
    assert "api.scripts.collector_doctor" in text and "--frozen" in text and "xreader" in text
    for flag in ("-Json", "-Live", "-SelfTest", "QueriesPath"):
        assert flag in text
    for forbidden in ("New-NetFirewallRule", "Set-NetFirewallRule", "Remove-NetFirewallRule", "netsh",
                      "Register-ScheduledTask", "Invoke-WebRequest", "Invoke-RestMethod"):
        assert forbidden not in text
    assert "exit $code" in text
