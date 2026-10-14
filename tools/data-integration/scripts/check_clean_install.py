"""AC-5 hybrid check: syncing the tooling in a throwaway environment leaves the API install untouched.

Run from anywhere: python tools/data-integration/scripts/check_clean_install.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _run(cmd: list[str], env: dict[str, str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=REPO_ROOT, env=env, check=True)


def main() -> int:
    env = {k: v for k, v in os.environ.items() if k != "UV_FROZEN"}
    with tempfile.TemporaryDirectory(prefix="dit-clean-") as tmp:
        env["UV_PROJECT_ENVIRONMENT"] = str(Path(tmp) / "env")
        _run(["uv", "sync", "--project", "tools/data-integration"], env)
    env.pop("UV_PROJECT_ENVIRONMENT", None)
    _run(["uv", "lock", "--check", "--project", "api"], env)
    _run(["git", "diff", "--exit-code", "api/uv.lock"], env)
    print("OK: API install unchanged by the tooling sync")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as exc:
        print(f"FAILED: {exc.cmd[:3]} exit {exc.returncode}", file=sys.stderr)
        sys.exit(1)
