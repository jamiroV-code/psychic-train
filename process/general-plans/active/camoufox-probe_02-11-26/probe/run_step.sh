#!/usr/bin/env bash
# Runs one probe step with every cache/temp path redirected into the throwaway
# probe root (outside the repo and outside the %LOCALAPPDATA% defaults).
#   WIN_PD_OVERRIDE_LOCAL_APPDATA: platformdirs' supported override; moves
#     camoufox's INSTALL_DIR (browser + config) under the probe root.
#   TEMP/TMP: Playwright's per-launch artifacts dir.
#   PLAYWRIGHT_BROWSERS_PATH: stays empty (Camoufox brings its own browser).
set -euo pipefail
ROOT='C:\Users\jamir\camoufox-probe'
export WIN_PD_OVERRIDE_LOCAL_APPDATA="$ROOT\\localappdata"
export TEMP="$ROOT\\tmp" TMP="$ROOT\\tmp"
export PLAYWRIGHT_BROWSERS_PATH="$ROOT\\pw-browsers"
export PYTHONDONTWRITEBYTECODE=1
unset GITHUB_TOKEN
cd "$(dirname "$0")"
exec 'C:/Users/jamir/camoufox-probe/venv/Scripts/python.exe' camoufox_probe.py "$@"
