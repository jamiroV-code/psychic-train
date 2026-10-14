"""Run `npx -y rea-agents@<pin> <command> --json` for allow-listed commands only.

Evidence is written OUTSIDE the repo (paths.evidence_dir()). No shell is ever involved.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path
from typing import Callable, Sequence

from data_integration import paths, status
from data_integration.rea import allowlist

REDACTED = "[redacted]"
EXPECTED_TOP_LEVEL_KEYS = 15
TEMPLATE_PATH = Path(__file__).with_name("evidence_template.md")
EVIDENCE_FOOTER = (
    "REA cannot see server-side methodology and does not search public datasets. "
    "Nothing above says how the numbers are produced on the provider's server."
)
FINDING_TAGS = ("VERIFIED", "ASSUMED")
_DRIVE_PATH = re.compile(r"^[A-Za-z]:\\")


@dataclass(frozen=True)
class Refusal:
    reason: str
    detail: str
    status: str = status.REFUSED


@dataclass(frozen=True)
class ReaResult:
    status: str
    command: str
    argv: tuple[str, ...]
    output: dict | None = None
    evidence_path: Path | None = None
    detail: str = ""


Runner = Callable[[Sequence[str], dict], "subprocess.CompletedProcess[str]"]


def normalize_path_arg(value: str) -> str:
    """Windows drive-letter paths use forward slashes; any other backslash stays and fails the regex."""
    return value.replace("\\", "/") if _DRIVE_PATH.match(value) else value


def _valid_arg(value: str) -> bool:
    return bool(allowlist.ARG_RE.fullmatch(value)) and not (set(value) & allowlist.FORBIDDEN_CHARS)


def npx_executable(os_name: str | None = None) -> str:
    if (os_name or os.name) == "nt":
        return shutil.which("npx.cmd") or "npx.cmd"
    return "npx"


def redact(output: dict) -> dict:
    """Blank subject.local_path and normalized_result.input_path; nothing else changes."""
    out = json.loads(json.dumps(output))
    for outer, inner in (("subject", "local_path"), ("normalized_result", "input_path")):
        node = out.get(outer)
        if isinstance(node, dict) and inner in node:
            node[inner] = REDACTED
    return out


def _default_runner(cmd: Sequence[str], env: dict) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(list(cmd), shell=False, capture_output=True, text=True, env=env, timeout=600)


def _confirmed(confirm_source: str | None, findings: str | None) -> bool:
    if not confirm_source or not findings or not _valid_arg(confirm_source):
        return False
    fpath = normalize_path_arg(findings)
    if not _valid_arg(fpath):
        return False
    try:
        data = json.loads(Path(fpath).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    names = data.get("sources") if isinstance(data, dict) else data
    return isinstance(names, list) and confirm_source in names


def _within(root: Path, candidate: Path) -> bool:
    return candidate.resolve().is_relative_to(root.resolve())


def run_rea(
    command: str,
    args: Sequence[str] = (),
    *,
    confirm_source: str | None = None,
    findings: str | None = None,
    runner: Runner | None = None,
    today: str | None = None,
) -> ReaResult | Refusal:
    if command not in allowlist.ALLOWED_COMMANDS:
        return Refusal("not_allow_listed", "command is not on the allow-list")
    flags = allowlist.ALLOWED_FLAGS[command]
    day = today or _date.today().isoformat()
    evidence_root = paths.evidence_dir()
    if _within(paths._repo_root(), evidence_root):
        return Refusal("evidence_in_repo", "evidence folder must be outside the repository")
    day_dir = evidence_root / day

    forwarded: list[str] = []
    source_value: str | None = None
    items = list(args)
    i = 0
    while i < len(items):
        tok = items[i]
        if tok.startswith("-"):
            if tok not in flags:
                return Refusal("bad_flag", "flag is not allowed for this command")
            if tok == "--json":
                i += 1
                continue
            if i + 1 >= len(items):
                return Refusal("bad_argument", f"{tok} needs a value")
            val = normalize_path_arg(items[i + 1])
            if not _valid_arg(val) or val.startswith("-"):
                return Refusal("bad_argument", f"invalid value for {tok}")
            if tok == "--output":
                target = Path(val) if os.path.isabs(val) else day_dir / val
                if not _within(evidence_root, target):
                    return Refusal("bad_output_path", "output must stay inside the evidence folder")
                val = target.resolve().as_posix()
            else:
                source_value = val
            forwarded += [tok, val]
            i += 2
            continue
        val = normalize_path_arg(tok)
        if not _valid_arg(val):
            return Refusal("bad_argument", "argument fails the strict pattern")
        forwarded.append(val)
        i += 1

    if command in allowlist.LIVE_COMMANDS:
        if not _confirmed(confirm_source, findings):
            return Refusal("live_unconfirmed", "live command needs --confirm-source listed in --findings")
        if source_value is not None and source_value != confirm_source:
            return Refusal("bad_argument", "--source must equal --confirm-source")

    argv = [npx_executable(), "-y", allowlist.REA_PACKAGE, command, *forwarded, "--json"]
    env = {**os.environ, "npm_config_ignore_scripts": "true"}
    print(f"rea: running {command}", file=sys.stderr)
    try:
        proc = (runner or _default_runner)(argv, env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ReaResult(status.INVALID, command, tuple(argv), detail=type(exc).__name__)
    if proc.returncode != 0:
        return ReaResult(status.INVALID, command, tuple(argv), detail=f"exit {proc.returncode}")
    try:
        parsed = json.loads(proc.stdout)
    except ValueError:
        return ReaResult(status.INVALID, command, tuple(argv), detail="stdout is not JSON")
    if not isinstance(parsed, dict) or len(parsed) != EXPECTED_TOP_LEVEL_KEYS:
        return ReaResult(status.INVALID, command, tuple(argv), detail="unexpected output shape")

    clean = redact(parsed)
    day_dir.mkdir(parents=True, exist_ok=True)
    name = f"{command}-{source_value}.json" if source_value else f"{command}.json"
    target = day_dir / name
    target.write_text(json.dumps(clean, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return ReaResult(status.OK, command, tuple(argv), output=clean, evidence_path=target)


def render_evidence_note(
    source: str, command: str, date: str, raw_output: str, findings: Sequence[tuple[str, str]]
) -> str:
    lines = []
    for tag, text in findings:
        if tag not in FINDING_TAGS:
            raise ValueError("finding tag must be VERIFIED or ASSUMED")
        if "\n" in text or "\r" in text:
            raise ValueError("a finding is a single line")
        lines.append(f"- {tag}: {text}")
    body = "\n".join(lines) if lines else "- (none recorded)"
    note = TEMPLATE_PATH.read_text(encoding="utf-8")
    for key, val in {
        "{source}": source, "{rea_version}": allowlist.REA_VERSION, "{date}": date,
        "{command}": command, "{raw_output}": raw_output, "{findings}": body,
    }.items():
        note = note.replace(key, val)
    return note
