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
    assert "param([switch]$DryRun)" in text and 'Import-MySiteConfig -LogName \'collector\'' in text
    assert "'python', '-m', 'api.data.attention_collector'" in text
    assert f"$env:{apr.FLAG_ENV} = '1'" in text
    assert apr.STREAM_ENV in text  # printed, inherited as the owner sets it, never forced on here
    assert text.index("if ($DryRun) {") < text.index("& $config.UvPath @collectorArgs")
    assert "uvicorn" not in text and "--host" not in text


def test_start_collector_sets_the_x_library_environment_and_clears_proxies():
    text = _read("start-collector.ps1")
    for name, value in twscrape_reader.REQUIRED_ENV.items():
        assert f"$env:{name} = '{value}'" in text, name
    for name in {v.upper() for v in x_reader.PROXY_VARS} | {"TWS_HTTP_BACKEND"}:
        assert f"'{name}'" in text, name
    assert "Remove-Item -Path \"Env:$name\"" in text


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
