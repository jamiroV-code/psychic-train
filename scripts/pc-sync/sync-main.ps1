# Keep the PC's local main in step with origin/main. Fast-forward only.
# Never merges, rebases, resets or forces. On a dirty tree, another branch, or a diverged main
# it does nothing and writes one log line.
#
# Exit codes: 0 ok or skipped (not on main, dirty tree, diverged); 1 real failure (not a git repo, fetch or pull failed).
#
# UNVERIFIED IN CI: written in a container with no PowerShell. Parse and dry-run it on the PC first:
#   .\sync-main.ps1 -WhatIf
param(
    [string]$RepoPath = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
    [string]$LogFile = (Join-Path $env:LOCALAPPDATA 'my_site\logs\sync-main.log'),
    [switch]$WhatIf
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-SyncLog {
    param([Parameter(Mandatory)][string]$Message)
    $dir = Split-Path -Parent $LogFile
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $line = '{0} [sync-main] {1}' -f (Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK'), $Message
    Add-Content -Path $LogFile -Value $line
    Write-Host $line
}

Push-Location $RepoPath
try {
    $branch = (git rev-parse --abbrev-ref HEAD)
    if ($LASTEXITCODE -ne 0 -or -not $branch) { Write-SyncLog "failed: git rev-parse could not read the current branch (exit $LASTEXITCODE); is '$RepoPath' a git repo?"; exit 1 }
    $branch = $branch.Trim()
    if ($branch -ne 'main') { Write-SyncLog "skipped: current branch is '$branch', not main"; return }

    $dirty = git status --porcelain
    if ($dirty) { Write-SyncLog 'skipped: working tree is not clean'; return }

    if ($WhatIf) { Write-SyncLog 'dry run: would run git fetch origin, then git pull --ff-only origin main'; return }

    git fetch origin
    if ($LASTEXITCODE -ne 0) { Write-SyncLog "failed: git fetch failed (exit $LASTEXITCODE)"; exit 1 }

    git merge-base --is-ancestor main origin/main
    if ($LASTEXITCODE -ne 0) { Write-SyncLog 'skipped: local main is not an ancestor of origin/main (diverged or ahead); nothing changed'; return }

    git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { Write-SyncLog "failed: fast-forward refused (exit $LASTEXITCODE); nothing changed"; exit 1 }
    Write-SyncLog 'ok: main is up to date with origin/main'
}
finally {
    Pop-Location
}
