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



def _blocks_after(code: str, opener: str) -> list[str]:
    """Each `{ ... }` block that starts at `opener` (brace-counted)."""
    blocks = []
    for m in re.finditer(re.escape(opener), code):
        start = code.index("{", m.start())
        depth = 0
        for i in range(start, len(code)):
            depth += {"{": 1, "}": -1}.get(code[i], 0)
            if depth == 0:
                blocks.append(code[start:i + 1])
                break
    return blocks


def test_build_web_clears_marker_before_build_and_writes_it_only_after_success():
    lines = _code_lines(_read("build-web.ps1"))
    build = _first_index(lines, "& $config.PnpmPath @buildArgs")
    remove = _first_index(lines, "Remove-WebBuildMarker")
    write = _first_index(lines, "Write-WebBuildMarker")
    assert 0 <= remove < build, "the marker must be removed before the build"
    assert write > build, "the marker must be written after the build"
    guard = next((i for i in range(write - 1, build, -1) if lines[i].strip().startswith("if ")), -1)
    assert guard > build and "$code -eq 0" in lines[guard], "write the marker only when the build exited 0"
    assert any(line.strip() == "exit $code" for line in lines[write:]), "keep exit $code"


def test_marker_records_commit_web_tree_build_id_and_time_without_bom():
    common = _read("_common.ps1")
    for token in (
        "build-marker.json",
        "static",
        "BUILD_ID",
        "rev-parse",
        "HEAD:web",
        "commit",
        "web_tree",
        "build_id",
        "built_at_epoch",
        "UTF8Encoding($false)",
        "exit 7",
        "Test-Path -LiteralPath",
    ):
        assert token in common, f"_common.ps1 is missing {token!r}"


def test_start_web_refuses_stale_or_missing_build_with_exit_4():
    lines = _code_lines(_read("start-web.ps1"))
    fresh = [i for i in _call_lines(lines, "Test-WebBuildFresh") if "-ReportOnly" not in lines[i]]
    stop = [i for i in _call_lines(lines, "Stop-WebPortListener") if "-ReportOnly" not in lines[i]]
    assert fresh and stop, "start-web.ps1 needs a real stale check and a real stop"
    assert fresh[0] < stop[0], "check the build before stopping the running server"
    common = _read("_common.ps1")
    assert "exit 4" in _function_body(common, "Test-WebBuildFresh")
    stale = [line for line in common.splitlines() if "Stale build:" in line]
    assert stale and all("build-web.ps1" in line for line in stale), "tell the user to run build-web.ps1"


def test_stale_check_covers_web_tree_and_newest_tracked_source_mtime():
    body = _function_body(_read("_common.ps1"), "Test-WebBuildFresh")
    common = _read("_common.ps1")
    for token in ("ls-files", "GetLastWriteTimeUtc", "built_at_epoch", "HEAD:web", "no build marker", "-gt"):
        assert token in body, f"Test-WebBuildFresh is missing {token!r}"
    for token in ("git -C", "RepoRoot", "Floor"):
        assert token in common, f"_common.ps1 is missing {token!r}"


def test_stale_check_is_report_only_in_dry_run():
    lines = _code_lines(_read("start-web.ps1"))
    begin, end = _dry_run_block(lines)
    report = [i for i in range(begin, end) if "Test-WebBuildFresh" in lines[i] and "-ReportOnly" in lines[i]]
    assert report, "the dry run must run the stale check with -ReportOnly before exit 0"
    body = _function_body(_read("_common.ps1"), "Test-WebBuildFresh")
    blocks = _blocks_after(body, "if ($ReportOnly)")
    assert blocks, "Test-WebBuildFresh needs a -ReportOnly branch"
    for block in blocks:
        assert "exit 4" not in block, "the -ReportOnly branch must never exit 4"


# --- C3: child process, smoke check, README guard section ---------------------


def _readme_guard_section() -> str:
    text = (DEPLOY / "README.md").read_text(encoding="utf-8")
    start = text.find(GUARD_HEADING)
    assert start != -1, f"README needs the section {GUARD_HEADING!r}"
    end = text.find("\n## ", start + 1)
    return text[start:] if end == -1 else text[start:end]


GUARD_HEADING = "## Restarting safely after a web change (R12 guards)"
CREDENTIAL_WORDS = ("authorization", "bearer", "credential", "securestring", "password")


def test_start_web_runs_next_as_child_with_exit_code_passthrough():
    lines = _code_lines(_read("start-web.ps1"))
    code = "\n".join(lines)
    for token in ("Start-Process", "-PassThru", "-NoNewWindow", "$proc.WaitForExit()", "$proc.ExitCode", "exit 6"):
        assert token in code, f"start-web.ps1 is missing {token!r}"
    assert "& $config.PnpmPath @webArgs" not in code, "the old foreground call must be gone"
    start = _first_index(lines, "Start-Process")
    assert "$webArgs" in lines[start] and "-WorkingDirectory" in lines[start]
    wait = _first_index(lines, "$proc.WaitForExit()")
    assert any(line.strip() == "exit $code" for line in lines[wait:]), "pass the server exit code through"


def test_smoke_check_is_bounded_and_polls_own_tailscale_address_only():
    common = _read("_common.ps1")
    for token in (
        "Invoke-WebRequest",
        "-UseBasicParsing",
        "-TimeoutSec",
        "$deadline",
        "Start-Sleep -Seconds 2",
        ".HasExited",
        "StatusCode -eq 200",
    ):
        assert token in common, f"_common.ps1 is missing {token!r}"
    body = _function_body(common, "Invoke-WebSmokeCheck")
    urls = [line for line in body.splitlines() if "http://" in line]
    assert urls and all(re.search(r"http://\$\{?Ip\}?:", line) and "WebPort" in line for line in urls), (
        "the smoke URL must be built from $Ip and WebPort only"
    )
    for literal in ("localhost", "127.0.0.1"):
        assert literal not in body, f"the smoke check must not poll {literal}"


def test_smoke_compares_served_build_id_with_marker_and_exits_6_on_failure():
    common = _read("_common.ps1")
    for token in ("_next/static/build-marker.json", "build_id", "evidence", "Smoke check FAILED:", "Smoke check ok:"):
        assert token in common, f"_common.ps1 is missing {token!r}"
    text = _read("start-web.ps1")
    lines = _code_lines(text)
    smoke = _first_index(lines, "Invoke-WebSmokeCheck")
    wait = _first_index(lines, "$proc.WaitForExit()")
    assert 0 <= smoke < wait, "run the smoke check before waiting for the server"
    exit6 = _first_index(lines, "exit 6", smoke)
    assert smoke < exit6 < wait, "a failed smoke check exits 6 before the wait"
    param = re.search(r"param\((.*?)\n\)", "\n".join(lines), re.S)
    assert param and "$SmokeTimeoutSeconds" in param.group(1), "-SmokeTimeoutSeconds must be a parameter"


def test_start_web_dry_run_prints_and_exits_before_any_start_or_stop():
    lines = _code_lines(_read("start-web.ps1"))
    begin, end = _dry_run_block(lines)
    banner = _first_index(lines, "DRY RUN (nothing started)")
    start = _first_index(lines, "Start-Process")
    assert begin < banner < end < start, "the dry run prints and exits 0 before Start-Process"
    real_stops = [i for i in _call_lines(lines, "Stop-WebPortListener") if "-ReportOnly" not in lines[i]]
    assert real_stops and min(real_stops) > end, "no real stop before the dry-run exit 0"


def test_readme_documents_r12_guards_exit_codes_and_restart_procedure():
    text = (DEPLOY / "README.md").read_text(encoding="utf-8")
    rebuild = text.find("## Building the web app: the rebuild rule")
    guard = text.find(GUARD_HEADING)
    scheduler = text.find("## Starting it automatically")
    assert 0 <= rebuild < guard < scheduler, "the guard section sits between the rebuild rule and Task Scheduler"
    section = _readme_guard_section()
    for token in (
        "Stop-ScheduledTask mysite-web",
        "build-web.ps1",
        "Start-ScheduledTask mysite-web",
        "build-marker.json",
        "-SmokeTimeoutSeconds",
    ):
        assert token in section, f"README guard section is missing {token!r}"
    assert section.index("Stop-ScheduledTask") < section.index("build-web.ps1") < section.index("Start-ScheduledTask")
    for code in ("4", "5", "6", "7"):
        assert re.search(rf"^\| {code} \|", section, re.M), f"exit code {code} missing from the table"
    assert "by hand only while the `mysite-web` task is stopped" in section


def test_no_credentials_or_literal_remote_hosts_in_deploy_scripts():
    for path in _ps1_files():
        code = "\n".join(_code_lines(path.read_text(encoding="utf-8")))
        lower = code.lower()
        for word in CREDENTIAL_WORDS:
            assert word not in lower, f"{path.name} mentions {word!r}"
        for m in re.finditer(r"https?://", code):
            assert code[m.end():m.end() + 1] == "$", f"{path.name}: URL must take a variable host: {code[m.start():m.end() + 20]!r}"
