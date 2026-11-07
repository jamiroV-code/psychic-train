"""OD-5: the browser firewall rule TEXT generator (generate only, never apply).

Asserts the exact printed text for fixture paths, every refusal, and that the module cannot touch firewall state
(no subprocess / os.system / network import). Nothing here runs PowerShell or netsh."""
from __future__ import annotations

import ast
import io
from pathlib import Path

import pytest

from api.scripts import browser_firewall_rule as fw

MODULE = Path(fw.__file__)


def _program(tmp_path: Path) -> Path:
    exe = tmp_path / "Edge App" / "msedge.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"MZ")
    return exe


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    code = fw.main(argv, out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def _expected(program: str, user: str | None) -> str:
    name = "mysite-collector-browser-block"
    lines = [
        "# Browser firewall rule for the collector (OD-5). GENERATED TEXT ONLY: this tool changed nothing.",
        "# Review every line, then run the commands yourself in an ADMINISTRATOR PowerShell.",
        f"# Program: {program}",
        "",
        "# WARNING: the rule blocks outbound traffic for EVERY use of this executable path, including your",
        "# everyday browser if it is the same program" + (
            ", unless it is limited to one Windows user (below)." if user else
            ". Use --user <DOMAIN\\name> with a dedicated Windows user to limit it."),
        "# Loopback to the collector relay must keep working: after applying, run the A19 self-test (step 6) and",
        "# check the doctor; if the relay stops answering, remove the rule (step 3).",
        "",
        "# 1. Apply (PowerShell)",
    ]
    if user:
        lines += [
            f"$sid = (New-Object System.Security.Principal.NTAccount('{user}')).Translate("
            "[System.Security.Principal.SecurityIdentifier]).Value",
            f'New-NetFirewallRule -DisplayName "{name}" -Direction Outbound -Action Block -Program "{program}" '
            '-Profile Any -LocalUser "D:(A;;CC;;;$sid)"',
        ]
    else:
        lines.append(f'New-NetFirewallRule -DisplayName "{name}" -Direction Outbound -Action Block '
                     f'-Program "{program}" -Profile Any')
    lines += [
        "",
        "# 2. Or apply with netsh (equivalent rule" + (
            "; netsh cannot limit a rule to one user, so with --user use step 1 only)" if user else ")"),
        f'netsh advfirewall firewall add rule name="{name}" dir=out action=block program="{program}" enable=yes',
        "",
        "# 3. Remove (either line)",
        f'Remove-NetFirewallRule -DisplayName "{name}"',
        f'netsh advfirewall firewall delete rule name="{name}" program="{program}"',
        "",
        "# 4. Verify (read-only)",
        f'Get-NetFirewallRule -DisplayName "{name}" | Get-NetFirewallApplicationFilter',
        f"@(Get-NetFirewallRule -DisplayName '{name}' -ErrorAction SilentlyContinue).Count",
        "",
        "# 5. What the doctor reports",
        "# firewall_rule PASS present = the rule exists (count >= 1); WARN absent = no rule; UNKNOWN = query failed.",
        "",
        "# 6. When the browser counts as 'contained' (A19)",
        "# All of these, for the same browser path and exact version:",
        "#  - the rule above exists (the doctor's read-only firewall_rule check is PASS);",
        "#  - the A19 self-test observed ZERO Established non-loopback TCP endpoints for the browser's processes;",
        "#  - the relay on loopback kept working during the self-test.",
        "# Blocked connection attempts are recorded as blocked_attempts, never as residual.",
        "# Any browser version change voids the result: run the self-test again.",
        "# Self-test: uv run --project api --frozen --group xreader python -m api.data.attention.browser_selftest "
        f'--binary "{program}" --cache-root <cache>',
        "",
    ]
    return "\n".join(lines)


def test_exact_text_without_user(tmp_path):
    exe = _program(tmp_path)
    code, out, err = _run(["--program", str(exe)])
    assert (code, err) == (0, "")
    assert out == _expected(str(exe), None)


def test_exact_text_with_user(tmp_path):
    exe = _program(tmp_path)
    code, out, err = _run(["--program", str(exe), "--user", "DESKTOP-1\\collector bot"])
    assert (code, err) == (0, "")
    assert out == _expected(str(exe), "DESKTOP-1\\collector bot")


def test_rule_name_matches_doctor_and_selftest():
    from api.data.attention import browser_selftest
    from api.scripts import collector_doctor
    assert fw.RULE_NAME == collector_doctor.FIREWALL_RULE_NAME == browser_selftest.RULE_NAME


@pytest.mark.parametrize("bad", ["msedge.exe", "Edge\\msedge.exe", "./msedge.exe"])
def test_refuses_relative_program(bad):
    code, out, err = _run(["--program", bad])
    assert (code, out) == (2, "") and err.strip() == "refused: program_not_absolute"


@pytest.mark.parametrize("char", ['"', "'", "`", "$", "%", "\n", "\r", "\t", "\x00", "\x1b", ";", "|"])
def test_refuses_unsafe_characters_in_program(tmp_path, char):
    code, out, err = _run(["--program", str(tmp_path / f"ms{char}edge.exe")])
    assert (code, out) == (2, "") and err.strip() == "refused: program_unsafe_characters"


def test_refuses_missing_program_and_directory(tmp_path):
    for path in (tmp_path / "absent.exe", tmp_path):
        code, out, err = _run(["--program", str(path)])
        assert (code, out) == (2, "") and err.strip() == "refused: program_not_found"


@pytest.mark.parametrize("user", ["collector", "A\\B\\C", "DOM\\na\"me", "DOM\\na'me", "DOM\\a`b", "DOM\\a$b",
                                  "DOM\\a\nb", "DOM\\a\x00b", "\\name", "DOM\\", "DOM\\a;b", "DOM\\" + "x" * 300])
def test_refuses_invalid_user(tmp_path, user):
    exe = _program(tmp_path)
    code, out, err = _run(["--program", str(exe), "--user", user])
    assert (code, out) == (2, "") and err.strip() == "refused: user_invalid"


def test_refusal_never_echoes_the_input(tmp_path):
    code, out, err = _run(["--program", "relative\\secret-name.exe"])
    assert code == 2 and "secret-name" not in err


def test_module_cannot_touch_firewall_state_or_network():
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
        elif isinstance(node, ast.Attribute):
            assert node.attr not in {"system", "popen", "startfile", "spawnv", "execv", "run"}, node.attr
        elif isinstance(node, ast.Name):
            assert node.id not in {"__import__", "exec", "eval"}, node.id
    forbidden = {"subprocess", "socket", "http", "urllib", "requests", "httpx", "ctypes", "winreg", "asyncio",
                 "multiprocessing", "pty", "shutil"}
    assert not imported & forbidden, imported & forbidden
    assert imported <= {"__future__", "argparse", "re", "sys", "pathlib", "typing"}, imported


def test_module_is_ascii():
    assert MODULE.read_text(encoding="utf-8").isascii()
