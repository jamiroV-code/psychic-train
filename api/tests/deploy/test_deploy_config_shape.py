"""Gate G4 — TEXT-SHAPE GUARDS ONLY on `deploy/`.

These tests read the PowerShell launchers, the example config and the runbook
as plain text. They never execute PowerShell (the container has none). Green
here means certain text is present or absent — it does NOT prove any `.ps1`
parses, runs, binds the right address or registers a task. That proof is the
user-run steps B5, B6, B8, B10 and B11 in the deployability plan.

Pattern mirrors `api/tests/scripts/test_snapshot_workflow_schedules.py`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DEPLOY = REPO_ROOT / "deploy"

EXPECTED_FILES = (
    "README.md",
    "config.example.psd1",
    "_common.ps1",
    "start-api.ps1",
    "start-web.ps1",
    "build-web.ps1",
    "register-tasks.ps1",
)


def _read(name: str) -> str:
    return (DEPLOY / name).read_text(encoding="utf-8")


def _code_lines(text: str) -> list[str]:
    """PowerShell lines with `#` comments removed (comment-only lines dropped)."""
    out = []
    for line in text.splitlines():
        stripped = line.split("#", 1)[0] if not line.lstrip().startswith("<#") else ""
        if stripped.strip():
            out.append(stripped)
    return out


def _ps1_files() -> list[Path]:
    return sorted(DEPLOY.glob("*.ps1"))


def _script_files() -> list[Path]:
    return sorted(list(DEPLOY.glob("*.ps1")) + list(DEPLOY.glob("*.psd1")))


def test_expected_deploy_files_exist():
    missing = [f for f in EXPECTED_FILES if not (DEPLOY / f).is_file()]
    assert not missing, f"missing deploy files: {missing}"


def test_no_deploy_script_binds_all_interfaces():
    assert _script_files(), "no deploy scripts found"
    for path in _script_files():
        text = path.read_text(encoding="utf-8")
        assert "0.0.0.0" not in text, f"{path.name} mentions 0.0.0.0 (D1: bind the Tailscale IPv4 only)"
        assert not re.search(r"--host\s+['\"]?(\*|::)['\"]?(\s|$)", text), f"{path.name} binds a wildcard host"


def test_readme_zero_zero_zero_zero_only_in_scoped_firewall_fallback():
    lines = _read("README.md").splitlines()
    hits = [line for line in lines if "0.0.0.0" in line]
    assert hits, "the README should document the D1 fallback (and forbid 0.0.0.0 by default)"
    for line in hits:
        lower = line.lower()
        assert (
            "fallback" in lower or "never" in lower or "not" in lower or "100.64.0.0/10" in line
        ), f"README mentions 0.0.0.0 outside the scoped-fallback / prohibition context: {line!r}"


def test_start_api_sets_cors_env_before_uvicorn_and_never_reloads():
    text = _read("start-api.ps1")
    cors = text.find("SCREENER_CORS_ORIGINS")
    uvicorn = text.find("uvicorn")
    assert cors != -1, "start-api.ps1 must set SCREENER_CORS_ORIGINS"
    assert uvicorn != -1, "start-api.ps1 must launch uvicorn"
    assert cors < uvicorn, "SCREENER_CORS_ORIGINS must be set before uvicorn starts (F4: read at import)"
    assert "$env:SCREENER_CORS_ORIGINS" in text
    assert "--reload" not in text
    assert "api.main:app" in text
    assert "-DryRun" in text


def test_start_api_host_is_a_variable_not_a_literal():
    text = _read("start-api.ps1")
    m = re.search(r"--host['\"]?\s*,?\s*(\S+)", text)
    assert m, "start-api.ps1 must pass --host"
    assert m.group(1).lstrip("'\"").startswith("$"), f"--host must be a variable, got {m.group(1)!r}"
    assert "127.0.0.1" not in "\n".join(_code_lines(text))


def test_start_web_uses_next_start_not_dev_and_binds_variable():
    text = _read("start-web.ps1")
    code = "\n".join(_code_lines(text))
    assert re.search(r"next['\"]?\s*,?\s*['\"]?start", code), "start-web.ps1 must run `next start`"
    assert not re.search(r"next['\"]?\s*,?\s*['\"]?dev\b", code), "start-web.ps1 must never run `next dev`"
    m = re.search(r"['\"]?-H['\"]?\s*,?\s*(\S+)", code)
    assert m and m.group(1).lstrip("'\"").startswith("$"), "next start -H must take a variable host"
    assert "-DryRun" in text


def test_build_web_sets_next_public_api_base_url_before_build():
    text = _read("build-web.ps1")
    env_set = text.find("$env:NEXT_PUBLIC_API_BASE_URL")
    build = re.search(r"['\"]?build['\"]?", text[env_set:] if env_set != -1 else "")
    assert env_set != -1, "build-web.ps1 must set $env:NEXT_PUBLIC_API_BASE_URL"
    assert build, "the web build must run after NEXT_PUBLIC_API_BASE_URL is set (F2: inlined at build time)"
    assert "rebuild" in text.lower()
    assert "-DryRun" in text


NEVER_SCHEDULED = (
    "refresh_cache",
    "compute_pairs",
    "backfill_primaries",
    "backfill_pairs_universe",
    "snapshot_narrative",
    "snapshot_liqtide",
    "snapshot_chain_growth",
)


def test_scheduled_scripts_never_run_stage_b_or_no_history_jobs():
    for path in _ps1_files():
        text = path.read_text(encoding="utf-8")
        for job in NEVER_SCHEDULED:
            assert job not in text, f"{path.name} references {job} (stage B / no-history job must stay off the PC's automatic path)"


def test_stage_a_is_ff_only_and_non_fatal():
    common = _read("_common.ps1")
    assert "--ff-only" in common
    assert re.search(r"\btry\b", common, re.I) and re.search(r"\bcatch\b", common, re.I), "stage A pull must catch errors"
    for path in _ps1_files():
        text = path.read_text(encoding="utf-8")
        for forbidden in ("--force", "reset --hard", "stash", "rebase", "merge"):
            assert forbidden not in text.lower(), f"{path.name} contains forbidden git operation {forbidden!r}"
    assert "AutoPull" in _read("start-api.ps1")


def test_register_tasks_at_logon_current_user_no_elevation():
    text = _read("register-tasks.ps1")
    assert "-AtLogOn" in text
    assert "SYSTEM" not in text
    assert not re.search(r"RunLevel\s+Highest", text, re.I)
    assert "-RestartCount" in text and "-RestartInterval" in text
    assert "-Remove" in text
    assert "Unregister-ScheduledTask" in text
    assert "mysite-api" in text and "mysite-web" in text


def test_ip_wait_is_bounded_and_cgnat_only():
    text = _read("_common.ps1")
    assert "MaxWaitSeconds" in text
    assert "100.64.0.0/10" in text
    assert "ip" in text and "-4" in text
    assert re.search(r"exit\s+[1-9]", text), "timeout must exit non-zero"


PUBLIC_EXPOSURE_WORDS = ("funnel", "ngrok", "cloudflared", "port forward", "exit node", "advertise-routes")
PROHIBITION_WORDS = ("never", "not", "forbidden", "no ", "do not", "don't")


def test_no_funnel_or_public_exposure_anywhere():
    for path in _script_files():
        lower = path.read_text(encoding="utf-8").lower()
        for word in PUBLIC_EXPOSURE_WORDS:
            assert word not in lower, f"{path.name} mentions {word!r} (D11 hard stop)"
        assert not re.search(r"-remoteaddress\s+['\"]?(any|0\.0\.0\.0)", lower), f"{path.name} opens a firewall rule to Any"
    for line in _read("README.md").splitlines():
        lower = line.lower()
        if "funnel" in lower:
            assert any(w in lower for w in PROHIBITION_WORDS), f"README mentions funnel without prohibiting it: {line!r}"
        assert not re.search(r"-remoteaddress\s+['\"]?(any|0\.0\.0\.0)", lower), f"README firewall rule opens Any: {line!r}"


REQUIRED_KEYS = (
    "RepoRoot", "UvPath", "PnpmPath", "TailscaleExe", "ApiPort", "WebPort",
    "MaxWaitSeconds", "AutoPull", "ExtraCorsOrigins", "CacheRoot", "WatchlistPath",
)


def test_config_example_has_required_keys_and_no_secrets():
    text = _read("config.example.psd1")
    for key in REQUIRED_KEYS:
        assert re.search(rf"\b{key}\b", text), f"config.example.psd1 missing key {key}"
    lower = text.lower()
    for secret_word in ("password", "secret", "token", "apikey", "api_key", "authkey", "tskey"):
        assert secret_word not in lower, f"config.example.psd1 must hold no secret ({secret_word!r})"
    assert "0.0.0.0" not in text


def test_readme_pins_required_operator_facts():
    text = _read("README.md")
    lower = text.lower()
    assert "NEXT_PUBLIC_API_BASE_URL" in text and "rebuild" in lower
    assert "Task Scheduler" in text
    assert "Tailscale" in text
    assert "_atomic_to_parquet" in text, "stage B gate (G-STAGEB) must be named"
    assert "pull, then optionally recompute" in lower
    assert "api/scripts/BOOTSTRAP.md" in text and "available once P1 merges" in text
