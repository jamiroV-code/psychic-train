"""Windows behavior coverage for the perp launcher root override (RFC-001 S1, VA-10)."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from api.tests.tooling_guards._common import REPO_ROOT

LAUNCHER = REPO_ROOT / "deploy" / "run-perp-collector.ps1"
STANDARD_COLLECTOR = REPO_ROOT / "deploy" / "start-collector.ps1"
MISSING = object()

pytestmark = pytest.mark.skipif(os.name != "nt", reason="requires Windows PowerShell")


# A `None` config value omits the key; empty/whitespace values are written verbatim.
# Root/cache labels resolve to distinct paths under tmp_path, except `default`, which is
# the actual checkout root and is never snapshotted or written by these DryRun cases.
ROOT_MATRIX = [
    pytest.param("configured", None, None, None, "configured", "repo-default", id="configured-repo-cache-absent"),
    pytest.param("configured", "", None, None, "configured", "repo-default", id="configured-repo-cache-empty"),
    pytest.param("configured", "configured-cache", None, None, "configured", "configured-cache", id="configured-roots"),
    pytest.param(None, "fallback-cache", None, None, "default", "fallback-cache", id="missing-config-repo-default-root"),
    pytest.param("", "fallback-cache", None, None, "default", "fallback-cache", id="empty-config-repo-default-root"),
    pytest.param("configured", None, "cli", None, "cli", "repo-default", id="repo-override-default-cache"),
    pytest.param("configured", "configured-cache", None, "cli-cache", "configured", "cli-cache", id="cache-override-only"),
    pytest.param(None, None, None, "cli-cache", "default", "cli-cache", id="cache-override-with-default-repo"),
    pytest.param("other", "other-cache", "cli", "cli-cache", "cli", "cli-cache", id="both-overrides-win-conflicts"),
    pytest.param("configured", "configured-cache", "   ", "   ", "configured", "configured-cache", id="whitespace-cli-overrides-fall-through"),
    pytest.param("configured", "configured-cache", "", "", "configured", "configured-cache", id="empty-cli-overrides-fall-through"),
    pytest.param("   ", "fallback-cache", None, None, "default", "fallback-cache", id="whitespace-config-repo-default-root"),
    pytest.param("", "fallback-cache", None, None, "default", "fallback-cache", id="empty-config-repo-default-root"),
    pytest.param("configured", "   ", None, None, "configured", "repo-default", id="whitespace-config-cache-defaults"),
    pytest.param("configured", "configured-cache", None, " ", "configured", "configured-cache", id="whitespace-cli-cache-falls-through"),
    pytest.param("configured", "configured-cache", None, "", "configured", "configured-cache", id="empty-cli-cache-falls-through"),
]


def _path(tmp_path: Path, label: str, config_repo: str | None = None) -> Path:
    if label == "default":
        return REPO_ROOT
    if label == "repo-default":
        repo = REPO_ROOT if config_repo is None else _path(tmp_path, config_repo)
        return repo / "api" / "data" / "cache"
    return tmp_path / label


def _root_setting(tmp_path: Path, value: str | None) -> str | None:
    if value is None or not value.strip():
        return value
    return str(_path(tmp_path, value))


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _write_config(
    local_app_data: Path,
    uv_path: Path,
    repo_root: str | None | object = MISSING,
    cache_root: str | None | object = MISSING,
    omit_key: str | None = None,
) -> Path:
    config_dir = local_app_data / "my_site"
    config_dir.mkdir(parents=True, exist_ok=True)
    settings: dict[str, str | int] = {
        "UvPath": str(uv_path),
        "PnpmPath": "pnpm",
        "TailscaleExe": "tailscale",
        "ApiPort": 8000,
        "WebPort": 3000,
        "MaxWaitSeconds": 60,
    }
    if repo_root is not MISSING:
        settings["RepoRoot"] = "" if repo_root is None else str(repo_root)
    if cache_root is not MISSING:
        settings["CacheRoot"] = "" if cache_root is None else str(cache_root)
    lines = ["@{"]
    for key, value in settings.items():
        if key == omit_key:
            continue
        encoded = str(value) if isinstance(value, int) else _ps_quote(value)
        lines.append(f"    {key} = {encoded}")
    lines.append("}")
    path = config_dir / "deploy.psd1"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_uv_marker(tmp_path: Path) -> tuple[Path, Path]:
    executable = tmp_path / "uv-marker.cmd"
    marker = tmp_path / "uv-invoked.marker"
    executable.write_text(
        "@echo off\r\n"
        f'> "{marker}" echo invoked\r\n'
        "exit /b 23\r\n",
        encoding="ascii",
    )
    return executable, marker


def _run_powershell(script: Path, local_app_data: Path, args: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(local_app_data)
    env.pop("SCREENER_CACHE_ROOT", None)
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            *(args or []),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )


def _snapshot_one(path: Path) -> tuple[object, ...]:
    if not path.exists():
        return ("missing",)
    if path.is_file():
        stat = path.stat()
        data = path.read_bytes()
        return ("file", len(data), hashlib.sha256(data).hexdigest(), stat.st_mtime_ns)

    entries: list[tuple[object, ...]] = []
    for child in sorted(path.rglob("*"), key=lambda item: item.relative_to(path).as_posix()):
        stat = child.stat()
        relative = child.relative_to(path).as_posix()
        if child.is_dir():
            entries.append(("dir", relative, stat.st_mtime_ns))
        else:
            data = child.read_bytes()
            entries.append(("file", relative, len(data), hashlib.sha256(data).hexdigest(), stat.st_mtime_ns))
    stat = path.stat()
    return ("dir", stat.st_mtime_ns, *entries)


def _snapshot(paths: list[Path]) -> dict[str, tuple[object, ...]]:
    snapshots: dict[str, tuple[object, ...]] = {}
    for path in paths:
        resolved = path.resolve(strict=False)
        key = os.path.normcase(str(resolved))
        snapshots.setdefault(key, _snapshot_one(resolved))
    return snapshots


def _temp_snapshot_paths(
    tmp_path: Path,
    local_app_data: Path,
    uv_path: Path,
    marker: Path,
    labels: set[str],
    config_repo: str | None,
) -> list[Path]:
    paths = [local_app_data / "my_site", uv_path, marker]
    for label in labels:
        if label in {"default", "repo-default"}:
            continue
        paths.append(_path(tmp_path, label))
    # Include the default-cache location only when it belongs to a temporary repo fixture.
    if config_repo is not None and config_repo not in {"", " ", "   "}:
        paths.append(_path(tmp_path, "repo-default", config_repo))
    return paths


def _output_lines(output: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in output.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            parsed[key.strip()] = value.strip()
    return parsed


@pytest.mark.parametrize(
    "config_repo,config_cache,cli_repo,cli_cache,expected_repo,expected_cache",
    ROOT_MATRIX,
)
def test_dry_run_uses_expected_root_precedence_without_writes(
    tmp_path: Path,
    config_repo: str | None,
    config_cache: str | None,
    cli_repo: str | None,
    cli_cache: str | None,
    expected_repo: str,
    expected_cache: str,
) -> None:
    local_app_data = tmp_path / "local-app-data"
    uv_path, marker = _write_uv_marker(tmp_path)
    configured_repo = _root_setting(tmp_path, config_repo)
    configured_cache = None if config_cache is None else (
        config_cache if not config_cache.strip() else str(_path(tmp_path, config_cache))
    )
    _write_config(
        local_app_data,
        uv_path,
        configured_repo if config_repo is not None else MISSING,
        configured_cache if config_cache is not None else MISSING,
    )

    args: list[str] = ["-DryRun"]
    if cli_repo is not None:
        args.extend(["-RepoRoot", cli_repo if not cli_repo.strip() else str(_path(tmp_path, cli_repo))])
    if cli_cache is not None:
        args.extend(["-CacheRoot", cli_cache if not cli_cache.strip() else str(_path(tmp_path, cli_cache))])

    expected_repo_path = _path(tmp_path, expected_repo, config_repo)
    if expected_cache == "repo-default":
        expected_cache_path = expected_repo_path / "api" / "data" / "cache"
    else:
        expected_cache_path = _path(tmp_path, expected_cache)

    # All files under these roots are test-owned. The real checkout/cache is intentionally excluded.
    root_labels = {label for label in (config_repo, cli_repo, expected_repo) if label not in (None, "default", "repo-default", "", " ", "   ")}
    cache_labels = {label for label in (config_cache, cli_cache, expected_cache) if label not in (None, "repo-default", "", " ", "   ")}
    snapshot_paths = _temp_snapshot_paths(
        tmp_path,
        local_app_data,
        uv_path,
        marker,
        root_labels | cache_labels,
        config_repo,
    )
    before = _snapshot(snapshot_paths)

    completed = _run_powershell(LAUNCHER, local_app_data, args)
    output = completed.stdout + completed.stderr

    assert completed.returncode == 0, output
    assert "DRY RUN (nothing started)" in output
    lines = _output_lines(output)
    assert lines.get("RepoRoot") == str(expected_repo_path), output
    assert lines.get("SCREENER_CACHE_ROOT") == str(expected_cache_path), output
    command = lines.get("command", "")
    assert re.search(
        rf"^{re.escape(str(uv_path))} run --project api python api/scripts/collect_perp\.py --job hl-snapshot\s+\(in {re.escape(str(expected_repo_path))}\)$",
        command,
    ), output
    assert not marker.exists(), "DryRun invoked the marker-only UvPath executable"
    assert _snapshot(snapshot_paths) == before, "DryRun changed a named temporary path"


@pytest.mark.parametrize("repo_value", [None, ""], ids=["repo-key-absent", "repo-key-empty"])
def test_non_perp_caller_still_requires_repo_root(
    tmp_path: Path, repo_value: str | None
) -> None:
    local_app_data = tmp_path / "local-app-data"
    uv_path, marker = _write_uv_marker(tmp_path)
    _write_config(
        local_app_data,
        uv_path,
        MISSING if repo_value is None else repo_value,
    )

    completed = _run_powershell(STANDARD_COLLECTOR, local_app_data, ["-DryRun"])
    output = completed.stdout + completed.stderr

    assert completed.returncode == 2, output
    assert "RepoRoot" in output and ("missing or empty" in output.lower() or "key" in output.lower()), output
    assert not marker.exists(), "Fail-closed config validation invoked UvPath"


@pytest.mark.parametrize("repo_value", [None, ""], ids=["repo-key-absent", "repo-key-empty"])
def test_perp_repo_opt_out_does_not_waive_other_required_keys(
    tmp_path: Path, repo_value: str | None
) -> None:
    local_app_data = tmp_path / "local-app-data"
    uv_path, marker = _write_uv_marker(tmp_path)
    _write_config(
        local_app_data,
        uv_path,
        MISSING if repo_value is None else repo_value,
        omit_key="PnpmPath",
    )

    completed = _run_powershell(LAUNCHER, local_app_data, ["-DryRun"])
    output = completed.stdout + completed.stderr

    assert completed.returncode == 2, output
    assert "PnpmPath" in output, output
    assert not marker.exists(), "Fail-closed config validation invoked UvPath"


def test_missing_config_file_fails_closed_before_uv_invocation(tmp_path: Path) -> None:
    local_app_data = tmp_path / "local-app-data"
    uv_path, marker = _write_uv_marker(tmp_path)

    completed = _run_powershell(LAUNCHER, local_app_data, ["-DryRun"])
    output = completed.stdout + completed.stderr

    assert completed.returncode == 2, output
    assert "Config file not found" in output, output
    assert not marker.exists(), "Missing config file path invoked UvPath"
