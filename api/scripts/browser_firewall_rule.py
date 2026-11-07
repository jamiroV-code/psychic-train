"""Print the browser firewall rule text for the owner to review and run (OD-5). GENERATE ONLY.

    python -m api.scripts.browser_firewall_rule --program <absolute path to msedge.exe> [--user <DOMAIN\\name>]

Prints: (1) the PowerShell `New-NetFirewallRule` command (scoped with `-LocalUser` when --user is given),
(2) the equivalent `netsh` command, (3) the removal commands, (4) the read-only verification commands,
(5) what the doctor's `firewall_rule` check reports, and (6) the A19 `contained` conditions, with a fixed warning
that the rule applies to EVERY use of that executable path and that loopback to the relay must keep working.

This module never reads or writes firewall state and starts no process: it only formats text. Refusals print a code
on stderr (never the input) and exit 2: `program_not_absolute`, `program_unsafe_characters`, `program_not_found`,
`user_invalid`.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path, PureWindowsPath

RULE_NAME = "mysite-collector-browser-block"  # collector_doctor.FIREWALL_RULE_NAME, browser_selftest.RULE_NAME
# Characters that could end a quoted argument or expand inside PowerShell/cmd text, plus separators.
_UNSAFE = re.compile(r"[\"'`$%;|<>&\x00-\x1f\x7f]")
_USER_PART = r"[A-Za-z0-9._ -]{1,64}"
_USER = re.compile(rf"{_USER_PART}\\{_USER_PART}")


class Refused(Exception):
    pass


def _absolute(value: str) -> bool:
    return Path(value).is_absolute() or PureWindowsPath(value).is_absolute()


def check_program(value: str) -> str:
    if _UNSAFE.search(value):
        raise Refused("program_unsafe_characters")
    if not _absolute(value):
        raise Refused("program_not_absolute")
    if not Path(value).is_file():
        raise Refused("program_not_found")
    return value


def check_user(value: str | None) -> str | None:
    if value is None:
        return None
    if _UNSAFE.search(value) or not _USER.fullmatch(value) or value != value.strip():
        raise Refused("user_invalid")
    return value


def render(program: str, user: str | None = None) -> str:
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
            f'New-NetFirewallRule -DisplayName "{RULE_NAME}" -Direction Outbound -Action Block -Program "{program}" '
            '-Profile Any -LocalUser "D:(A;;CC;;;$sid)"',
        ]
    else:
        lines.append(f'New-NetFirewallRule -DisplayName "{RULE_NAME}" -Direction Outbound -Action Block '
                     f'-Program "{program}" -Profile Any')
    lines += [
        "",
        "# 2. Or apply with netsh (equivalent rule" + (
            "; netsh cannot limit a rule to one user, so with --user use step 1 only)" if user else ")"),
        f'netsh advfirewall firewall add rule name="{RULE_NAME}" dir=out action=block program="{program}" enable=yes',
        "",
        "# 3. Remove (either line)",
        f'Remove-NetFirewallRule -DisplayName "{RULE_NAME}"',
        f'netsh advfirewall firewall delete rule name="{RULE_NAME}" program="{program}"',
        "",
        "# 4. Verify (read-only)",
        f'Get-NetFirewallRule -DisplayName "{RULE_NAME}" | Get-NetFirewallApplicationFilter',
        f"@(Get-NetFirewallRule -DisplayName '{RULE_NAME}' -ErrorAction SilentlyContinue).Count",
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


def main(argv=None, *, out=sys.stdout, err=sys.stderr) -> int:
    parser = argparse.ArgumentParser(prog="python -m api.scripts.browser_firewall_rule",
                                     description="Print (never apply) the collector browser firewall rule.")
    parser.add_argument("--program", required=True, help="absolute path of the browser executable")
    parser.add_argument("--user", help="optional DOMAIN\\name to limit the rule to one Windows user")
    args = parser.parse_args(argv)
    try:
        text = render(check_program(args.program), check_user(args.user))
    except Refused as exc:
        err.write(f"refused: {exc}\n")
        return 2
    out.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
