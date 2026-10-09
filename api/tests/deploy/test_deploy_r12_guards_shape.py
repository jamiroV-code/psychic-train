"""R12 guards: TEXT-SHAPE ONLY on `deploy/` (port-scoped stop, build marker, stale check).

These tests read the PowerShell launchers as plain text. They never execute PowerShell
(the container has none). Green here means certain text is present, absent or ordered;
it does NOT prove any `.ps1` parses or runs. That proof is the user's PC record.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEPLOY = REPO_ROOT / "deploy"

CHANGED_PS1 = ("_common.ps1", "build-web.ps1", "start-web.ps1")


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


def _function_body(text: str, name: str) -> str:
    """Code of `function <name>` up to the next top-level `function` (or end of file)."""
    code = "\n".join(_code_lines(text))
    match = re.search(rf"^function {re.escape(name)}\b.*?(?=^function |\Z)", code, re.S | re.M)
    assert match, f"function {name} not found"
    return match.group(0)


def _first_index(lines: list[str], needle: str, start: int = 0) -> int:
    for i in range(start, len(lines)):
        if needle in lines[i]:
            return i
    return -1


def _call_lines(lines: list[str], name: str) -> list[int]:
    return [i for i, line in enumerate(lines) if name in line and "function " not in line]


def _dry_run_block(lines: list[str]) -> tuple[int, int]:
    begin = _first_index(lines, "if ($DryRun)")
    assert begin >= 0, "dry-run block not found"
    end = next((i for i in range(begin, len(lines)) if lines[i].strip() == "exit 0"), -1)
    assert end > begin, "dry-run block must end with exit 0"
    return begin, end


def test_common_selects_listener_by_port_never_by_name():
    common = _read("_common.ps1")
    for token in (
        "Get-NetTCPConnection",
        "-State Listen",
        "-LocalPort",
        "Stop-Process -Id",
        "-ErrorAction SilentlyContinue",
    ):
        assert token in common, f"_common.ps1 is missing {token!r}"
    for path in _ps1_files():
        for line in _code_lines(path.read_text(encoding="utf-8")):
            low = line.lower()
            assert "stop-process -name" not in low, f"{path.name}: stop by name: {line.strip()}"
            assert "taskkill" not in low, f"{path.name}: taskkill: {line.strip()}"
            assert "get-process -name" not in low, f"{path.name}: lookup by name: {line.strip()}"
            if "stop-process" in low:
                after = low.split("stop-process", 1)[1]
                assert "-force" not in after, f"{path.name}: Stop-Process -Force: {line.strip()}"
            for m in re.finditer(r"get-process\b", low):
                assert low[m.end():].lstrip().startswith("-id"), (
                    f"{path.name}: Get-Process must select by -Id: {line.strip()}"
                )


def test_stop_helper_protects_system_pids_and_is_bounded():
    common = _read("_common.ps1")
    body = _function_body(common, "Stop-WebPortListener")
    for token in ("$listenerId -le 4", "$PID", "exit 5", "$deadline", "Start-Sleep", "-ErrorAction Stop"):
        assert token in body, f"Stop-WebPortListener is missing {token!r}"
    assign = re.compile(r"\$(pid|host|args|input)\b\s*=(?!=)", re.I)
    loop = re.compile(r"foreach\s*\(\s*\$pid\b", re.I)
    for path in _ps1_files():
        code = "\n".join(_code_lines(path.read_text(encoding="utf-8")))
        assert not loop.search(code), f"{path.name}: foreach over $pid (read-only automatic)"
        assert not assign.search(code), f"{path.name}: assigns an automatic variable"


def test_build_web_stops_port_listener_before_build_and_dry_run_is_report_only():
    lines = _code_lines(_read("build-web.ps1"))
    calls = _call_lines(lines, "Stop-WebPortListener")
    assert len(calls) == 2, f"expected exactly two Stop-WebPortListener calls, found {len(calls)}"
    begin, end = _dry_run_block(lines)
    build = _first_index(lines, "& $config.PnpmPath @buildArgs")
    assert build > end, "the build must run after the dry-run block"
    assert "-ReportOnly" in lines[calls[0]] and begin < calls[0] < end
    assert "-ReportOnly" not in lines[calls[1]] and end < calls[1] < build
    assert not any("Remove-WebBuildMarker" in line for line in lines[begin:end + 1]), (
        "the dry run must not remove the build marker"
    )


def test_start_web_stops_port_listener_before_bind_and_dry_run_is_report_only():
    lines = _code_lines(_read("start-web.ps1"))
    calls = _call_lines(lines, "Stop-WebPortListener")
    assert len(calls) in (2, 3), f"expected two or three Stop-WebPortListener calls, found {len(calls)}"
    begin, end = _dry_run_block(lines)
    assert "-ReportOnly" in lines[calls[0]] and begin < calls[0] < end
    assert "-ReportOnly" not in lines[calls[1]] and calls[1] > end
    launch = next(
        (i for i in range(end, len(lines)) if "Start-Process" in lines[i] or "@webArgs" in lines[i]),
        -1,
    )
    assert launch > calls[1], "the port must be freed before the server starts"
    if len(calls) == 3:
        start_process = _first_index(lines, "Start-Process", end)
        assert 0 <= start_process < calls[2], "a third stop is only the smoke cleanup after Start-Process"


def test_changed_ps1_files_are_ascii_only():
    for name in CHANGED_PS1:
        assert _read(name).isascii(), f"{name} has non-ASCII text (PowerShell 5.1 reads it as ANSI)"


def test_changed_ps1_files_have_balanced_brackets_and_quotes():
    for name in CHANGED_PS1:
        code = "\n".join(_code_lines(_read(name)))
        for open_, close in (("{", "}"), ("(", ")"), ("[", "]")):
            assert code.count(open_) == code.count(close), f"{name}: unbalanced {open_}{close}"
        assert code.count('"') % 2 == 0, f"{name}: odd number of double quotes"
        assert code.count("'") % 2 == 0, f"{name}: odd number of single quotes"
