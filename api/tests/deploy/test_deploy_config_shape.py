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


# --- Migration to a different PC (README section added 01-10-26) -------------

MIGRATION_MUST_COPY = (
    r"api\data\cache\ohlcv",
    r"api\data\cache\liquidity",
    r"api\data\cache\pairs",
    r"api\data\watchlist.json",
    r"api\data\cache\narrative\coingecko_trending.parquet",
)


def _migration_section() -> str:
    """The README text from the migration heading up to the next top-level heading."""
    text = _read("README.md")
    start = text.find("## Moving to a different PC")
    assert start != -1, "README must document moving to a different PC (cache migration)"
    nxt = text.find("\n## ", start + 1)
    return text[start:] if nxt == -1 else text[start:nxt]


def test_readme_has_migration_section():
    section = _migration_section()
    assert "migration" in section.lower()
    assert len(section.splitlines()) > 30, "the migration section must be a real runbook, not a stub"


def test_readme_migration_names_every_must_copy_path():
    section = _migration_section()
    for path in MIGRATION_MUST_COPY:
        assert path in section, f"migration section must name the gitignored path {path!r}"


def test_readme_migration_marks_next_build_as_must_not_copy():
    section = _migration_section()
    lower = section.lower()
    assert r"web\.next" in section, "migration section must name web\\.next"
    assert "next_public_api_base_url" in lower, "the baked-URL reason must be named"
    assert "baked" in lower
    assert "build-web.ps1" in section, "the new PC must re-run build-web.ps1"
    assert "deploy.psd1" in section, "the operator config must be recreated on the new PC"
    for rebuild_not_copy in (".venv", "node_modules", "__pycache__", "tsconfig.tsbuildinfo"):
        assert rebuild_not_copy in section, f"migration section must forbid copying {rebuild_not_copy}"


def test_readme_migration_says_legs_cache_is_not_needed():
    section = _migration_section()
    assert r"api\data\cache\legs" in section, "migration section must mention the legs cache"
    assert "write_confirmed_boundaries" not in section and "read_confirmed_boundaries" not in section, "the removed helpers must not be named"
    assert "has been removed" in section
    assert "dead weight" in section.lower()


def test_readme_migration_states_pairs_staleness_rule():
    section = _migration_section()
    assert "statsmodels" in section
    assert "0.15.0" in section, "uv.lock pins statsmodels 0.15.0 exactly"
    assert "compute_pairs" in section, "the stale fix is one compute_pairs run"
    assert "stale" in section.lower()
    assert "provenance.json" in section, "explain that provenance holds no absolute path"


def test_readme_migration_lists_paths_that_arrive_with_git_clone():
    section = _migration_section()
    for tracked in (r"api\data\cache\liqtide", r"api\data\cache\onchain"):
        assert tracked in section, f"migration section must say {tracked} needs no copy"
    assert "clone" in section.lower()


def test_readme_migration_orders_tailscale_before_config_before_build():
    """The step rows must run: get the new Tailscale address -> write the config -> rebuild."""
    rows = [line for line in _migration_section().splitlines() if re.match(r"\|\s*M\d+\s*\|", line)]
    assert len(rows) >= 8, f"expected a numbered migration step table, found {len(rows)} rows"
    ip_row = next(i for i, r in enumerate(rows) if "tailscale.exe" in r and "ip -4" in r)
    config_row = next(i for i, r in enumerate(rows) if "deploy.psd1" in r)
    build_row = next(i for i, r in enumerate(rows) if "build-web.ps1" in r)
    assert ip_row < config_row < build_row, (
        "order must be: new Tailscale address -> recreate deploy.psd1 -> rebuild the web app"
    )


def test_readme_migration_requires_services_stopped_and_old_pc_retired():
    section = _migration_section()
    lower = section.lower()
    assert "stop-scheduledtask" in lower, "copy with both services stopped on the old PC"
    assert "register-tasks.ps1 -Remove" in section, "the old PC must stop serving"
    assert "sign the old pc out of tailscale" in lower or "sign out of tailscale" in lower


def test_readme_migration_has_verification_and_rebuild_fallback():
    section = _migration_section()
    assert "computation_status" in section and "fresh" in section
    assert "grid_dates" in section
    assert "refresh_cache" in section and "backfill_primaries" in section
    assert "backfill_pairs_universe" in section
    assert "watchlist.example.json" in section, "this branch has no bootstrap script"
    assert "available once P1 merges" in section
    assert "2020-08-19" in section and "unverified" in section.lower(), (
        "the Hyperliquid history floor is unconfirmed and must be stated as such"
    )


def test_start_api_launches_uvicorn_via_python_module_not_the_console_script():
    """Regression guard for the Windows uv-trampoline failure (found 01-10-26).

    `uv run --project api uvicorn ...` fails on the user's Windows PC with
    "uv trampoline failed to canonicalize script path" — uv installs console scripts as
    trampoline .exe shims and launching one through `uv run` could not resolve its own path.
    `uv run --project api python -m uvicorn ...` works. This pins the module form so an
    innocent-looking tidy-up cannot reintroduce a launcher that only fails on the real machine,
    which is the one place CI cannot reach (no PowerShell, no Windows, no Tailscale here).
    """
    args = _read("start-api.ps1")
    assert "'python', '-m', 'uvicorn'" in args, (
        "start-api.ps1 must invoke uvicorn as `python -m uvicorn` — the bare `uvicorn` console "
        "script triggers the uv trampoline failure on Windows"
    )
    # The bare console-script form must not come back: `'api', 'uvicorn'` is how it looked before.
    assert "'api', 'uvicorn'" not in args, (
        "start-api.ps1 is back on the bare `uvicorn` console script; use `python -m uvicorn`"
    )
