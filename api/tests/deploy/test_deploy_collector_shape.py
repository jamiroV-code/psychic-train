"""Standalone collector (E): TEXT-SHAPE GUARDS ONLY on `deploy/start-collector.ps1` and its README section.

No PowerShell runs here (CI has none): green means certain text is present or absent. It does NOT prove the script
parses or starts anything; that proof is the owner's UNRUN steps in deploy/README.md ("Collector (separate from
the API)")."""
from __future__ import annotations

import re
from pathlib import Path

from api.data import attention_pc_refresh as apr
from api.data.attention import twscrape_reader, x_reader

DEPLOY = Path(__file__).resolve().parents[3] / "deploy"


def _read(name: str) -> str:
    return (DEPLOY / name).read_text(encoding="utf-8")


def _section() -> str:
    text = _read("README.md")
    start = text.find("## Collector (separate from the API)")
    assert start != -1, "README must document the standalone collector"
    nxt = text.find("\n## ", start + 1)
    return text[start:] if nxt == -1 else text[start:nxt]


def test_start_collector_runs_the_module_with_its_flag_and_dry_run():
    text = _read("start-collector.ps1")
    # S-OpsDeploy (table H): the whole param(...) now also carries the -Doctor pre-flight switch.
    assert "param([switch]$DryRun, [string]$QueriesPath = '', [switch]$Doctor)" in text
    assert 'Import-MySiteConfig -LogName \'collector\'' in text
    assert "'python', '-m', 'api.data.attention_collector'" in text
    assert f"$env:{apr.FLAG_ENV} = '1'" in text
    assert apr.STREAM_ENV in text  # printed, inherited as the owner sets it, never forced on here
    assert text.index("if ($DryRun) {") < text.index("& $config.UvPath @collectorArgs")
    assert "uvicorn" not in text and "--host" not in text


def test_start_collector_sets_the_x_library_environment_and_clears_proxies():
    text = _read("start-collector.ps1")
    for name, value in twscrape_reader.REQUIRED_ENV.items():
        assert f"$env:{name} = '{value}'" in text, name
    for name in {v.upper() for v in x_reader.PROXY_VARS}:
        assert f"'{name}'" in text, name
    assert "Remove-Item -Path \"Env:$name\"" in text
    # B1 (deliberate): the backend is no longer cleared; the launcher binds the validated configured style.
    assert "'TWS_HTTP_BACKEND'" not in text and "x_connection_style" in text
    assert "$env:TWS_HTTP_BACKEND = if ($style -eq 'curl') { 'curl' } else { 'httpx' }" in text
    assert "cnotin @('plain', 'curl')" in text


def test_start_collector_never_pulls_reads_keys_or_holds_secrets():
    text = _read("start-collector.ps1")
    for forbidden in ("Invoke-StageAPull", "Import-LseApiKey", "LSE_API_KEY", "Wait-TailscaleIPv4"):
        assert forbidden not in text, forbidden
    lower = text.lower()
    for word in ("password", "secret", "token", "cookie", "apikey", "api_key"):
        assert word not in lower, word
    assert text.isascii()


def test_register_tasks_does_not_register_the_collector():
    assert "mysite-collector" not in _read("register-tasks.ps1")


def test_readme_collector_section_has_task_switchover_and_unrun_marks():
    section = _section()
    assert "mysite-collector" in section and "Register-ScheduledTask" in section
    assert "start-collector.ps1 -DryRun" in section
    assert apr.FLAG_ENV in section and "no longer needs" in section
    assert "collector_heartbeat.json" in section and "Collector: Running (standalone process)" in section
    commands = [line for line in section.splitlines() if re.match(r"\s*(powershell|Register-|Start-|Stop-|\$|\[Environment\])", line)]
    assert commands, "the section must give the exact commands"
    assert section.count("UNRUN") >= 3
    assert section.isascii()


def test_b2_launcher_freezes_locked_group_and_passes_explicit_bounded_query_path():
    text = _read("start-collector.ps1")
    assert "'--frozen', '--group', 'xreader'" in text
    assert "'--queries', $queriesPath" in text
    assert "[System.IO.File]::OpenRead($queriesPath)" in text
    assert "$count -gt 1048576" in text
    assert "x_proxy_required" in text
    for name in ("x_proxy_list_path", "x_proxy_assignments_path", "x_proxy_policy_path"):
        assert name in text
    assert "if ($hasRouting -and -not $privateQueries)" in text
    assert "Get-Content -Raw" not in text


# --- S-OpsDeploy (finish plan 06-11-26, OD-2..OD-5): text-shape guards only; no PowerShell runs here. ---

import json  # noqa: E402

from api.data.attention import web_queries  # noqa: E402

EXAMPLES = DEPLOY / "examples"
RUNBOOK = "## Collector identity pool runbook (owner steps)"


def _runbook() -> str:
    text = _read("README.md")
    start = text.find(RUNBOOK)
    assert start != -1, "README must carry the owner runbook"
    nxt = text.find("\n## ", start + 1)
    return text[start:] if nxt == -1 else text[start:nxt]


def test_start_collector_doctor_preflight_runs_before_the_collector_and_refuses_on_fail():
    text = _read("start-collector.ps1")
    assert "param([switch]$DryRun, [string]$QueriesPath = '', [switch]$Doctor)" in text
    assert "'python', '-m', 'api.scripts.collector_doctor'" in text
    assert text.index("if ($DryRun) {") < text.index("if ($Doctor) {") < text.index("& $config.UvPath @collectorArgs")
    assert "& $config.UvPath @doctorArgs" in text
    assert "if ($doctorCode -ge 2)" in text and "exit 5" in text
    assert "--live" not in text and "--selftest" not in text  # pre-flight stays offline and fast


def test_register_collector_tasks_shape():
    text = _read("register-collector-tasks.ps1")
    assert text.startswith("#") and "UNRUN" in text and text.isascii()
    assert "param([switch]$Remove, [string]$QueriesPath = '', [string]$DoctorTime = '07:00')" in text
    assert "'mysite-collector'" in text and "'mysite-collector-doctor'" in text
    assert "-LogonType Interactive -RunLevel Limited" in text
    assert "-AtLogOn -User $user" in text and "-Daily -At $DoctorTime" in text
    assert "-RestartCount 3" in text and "-RestartInterval (New-TimeSpan -Minutes 1)" in text
    assert "-MultipleInstances IgnoreNew" in text
    assert "start-collector.ps1" in text and "-Doctor" in text and "doctor.ps1" in text
    assert "Register-ScheduledTask" in text and "Unregister-ScheduledTask" in text and "-Force" in text
    # identity: actual token SID, compared with the private policy SID; refusal, never ACL relaxation
    assert "[System.Security.Principal.WindowsIdentity]::GetCurrent()" in text and ".User.Value" in text
    assert "service_sid" in text and "exit 4" in text
    assert "IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)" in text
    for forbidden in ("SYSTEM", "S4U", "Highest", "ServiceAccount", "-Password", "icacls", "Set-Acl", "LocalService",
                      "NetworkService"):
        assert forbidden not in text, forbidden
    lower = text.lower()
    for word in ("password", "cookie", "token =", "apikey"):
        assert word not in lower, word


def test_register_tasks_and_collector_tasks_stay_separate():
    assert "mysite-collector" not in _read("register-tasks.ps1")
    assert "mysite-api" not in _read("register-collector-tasks.ps1")


def test_examples_are_synthetic_and_the_collector_block_validates(tmp_path):
    names = sorted(p.name for p in EXAMPLES.iterdir())
    assert names == ["collector-queries.example.json", "deploy.example.psd1", "private-layout.example.txt"]
    for path in EXAMPLES.iterdir():
        text = path.read_text(encoding="utf-8")
        assert text.isascii()
        lower = text.lower()
        for word in ("auth_token=", "ct0=", '"password":', "reddit_session=", "token_v2=", "http://", "https://", "socks"):
            assert word not in lower, (path.name, word)
    doc = json.loads((EXAMPLES / "collector-queries.example.json").read_text(encoding="utf-8"))
    block = doc["collector"]

    def relocate(value):  # synthetic absolute paths become real temp paths on any OS
        if isinstance(value, str) and value.startswith("C:\\MySitePrivate\\"):
            return str(tmp_path.joinpath(*value[len("C:\\MySitePrivate\\"):].split("\\")))
        if isinstance(value, dict):
            return {k: relocate(v) for k, v in value.items()}
        if isinstance(value, list):
            return [relocate(v) for v in value]
        return value

    committed = json.loads((DEPLOY.parent / "api" / "data" / "attention_queries.json").read_text(encoding="utf-8"))
    merged = {**committed["collector"], **relocate(block)}
    config = web_queries.validate_config(merged)
    # the example shows every switch at its safe default: all optional measures OFF
    assert config.x_queryid_mode == "off" and config.reddit_live_methods == ()
    assert not any((config.x_cookie_harvest_enabled, config.x_quiet_hours_enabled, config.x_mixed_traffic_enabled,
                    config.x_variation_enabled, config.x_adaptive_cooldown_enabled, config.x_warmup_enabled,
                    config.reddit_session_check_enabled))
    assert len(config.reddit_browser_accounts) == 2 and config.x_proxy_required is True


def test_runbook_has_every_owner_step_with_exact_commands():
    section = _runbook()
    assert section.isascii()
    for needle in (
        # private layout, X cookies and ready marks
        "private-layout.example.txt", "collector-queries.example.json", "CollectorQueriesPath",
        "X_REFRESH_COOKIES", "--refresh-cookies", "twscrape_reader --mark-ready", "--harvest-cookies",
        # Reddit profiles, login and ready marks
        "browser_session --site reddit --label", "--init-profile", "--interactive", "reddit_accounts --mark-ready",
        # probes in order, with --approve
        "probe_owner", "--approve", "--mode bootstrap", "--mode verify", "surface_tool surface-propose",
        "--approve-surface browser",
        # firewall
        "browser_firewall_rule --program", "Get-NetFirewallApplicationFilter", "Remove-NetFirewallRule",
        "browser_selftest",
        # switches, doctor, report, analyzer, tasks
        "x_queryid_mode", "sentinel", "auto", "x_cookie_harvest_enabled", "reddit_live_methods",
        "x_quiet_hours_enabled", "x_behaviour_report --from", "attention_daily_report --print",
        "doctor.ps1", "start-collector.ps1 -Doctor", "register-collector-tasks.ps1", "-Remove",
        # calendar, failure path, compliance, limits
        "13-11-26", "12-01-27", "March 2027", "missing-not-zero", "BP12", "deletion",
    ):
        assert needle in section, needle
    probe_order = [section.index(f"probe_owner {p}") for p in ("PX1", "PX2", "PX3", "PX4", "PX5", "PX6", "PR2", "PR1",
                                                               "PR5", "PR6")]
    assert probe_order == sorted(probe_order), "probes must appear in the enabling order"
    for status in ("PASS", "WARN", "FAIL", "UNKNOWN", "needs_probe", "containment_residual_unaccepted",
                   "accepted_residual", "contained", "browser_unadmitted", "x_login_required", "resting",
                   "probe_stale", "surface_changed"):
        assert status in section, status
    assert section.count("UNRUN") >= 3
    assert "Rollback" in section


def test_stage3_gateway_stays_absent_and_relay_is_loopback_only():
    """OD-4 / A9 / AC16: no gateway key, module or deploy setting; the relay binds only loopback."""
    from api.data.attention import browser_relay
    assert browser_relay.LISTEN_HOST == "127.0.0.1"
    assert not [k for k in web_queries.DEFAULTS if "gateway" in k or "v2ray" in k]
    for path in DEPLOY.rglob("*"):
        if path.is_file() and path.suffix in {".ps1", ".psd1", ".json", ".txt"}:
            lower = path.read_text(encoding="utf-8").lower()
            assert "gateway" not in lower and "v2ray" not in lower, path.name
    assert "is NOT a gateway" in _runbook()
