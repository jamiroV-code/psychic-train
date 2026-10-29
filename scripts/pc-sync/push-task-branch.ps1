# Push the current task branch and open a DRAFT pull request. Never pushes main, never forces.
#
# Exit codes: 0 ok or dry run; 1 refused or push failed; 2 pushed but no PR was opened (see message for the URL).
#
# UNVERIFIED IN CI: written in a container with no PowerShell. Dry-run it on the PC first:
#   .\push-task-branch.ps1 -WhatIf
param(
    [string]$RepoPath = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
    [string]$Branch,          # optional: must equal the current branch; default is the current branch
    [string]$Title,
    [switch]$WhatIf
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Push-Location $RepoPath
try {
    $current = (git rev-parse --abbrev-ref HEAD)
    if ($LASTEXITCODE -ne 0 -or -not $current) { Write-Host "refused: could not read the current branch (git rev-parse failed)"; exit 1 }
    $current = $current.Trim()
    if ($current -eq 'main' -or $current -eq 'HEAD') { Write-Host "refused: current branch is '$current' (main or detached HEAD); check out a task branch first"; exit 1 }
    if ($Branch -and $Branch -ne $current) { Write-Host "refused: -Branch '$Branch' is not the checked-out branch '$current'"; exit 1 }
    # The claude/* rule holds even when -Branch is given: -Branch only confirms the name, it never widens the rule.
    if ($current -notlike 'claude/*') {
        Write-Host "refused: '$current' is not a claude/* task branch; only claude/* branches are pushed by this script"
        exit 1
    }
    if (-not $Title) { $Title = $current }

    if ($WhatIf) {
        Write-Host "dry run: would run git push -u origin $current"
        Write-Host "dry run: would open a draft PR titled '$Title' with gh (or print the URL if gh is missing)"
        return
    }

    git push -u origin $current
    if ($LASTEXITCODE -ne 0) { Write-Host "push failed (exit $LASTEXITCODE); nothing forced"; exit 1 }

    $remote = ((git remote get-url origin) | Out-String).Trim() -replace '\.git$', ''
    $manualUrl = "$remote/pull/new/$current"

    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        Write-Host "pushed, but no PR was opened: gh is not installed. Open the draft PR yourself: $manualUrl"
        exit 2
    }

    # Double quotes in a native-command argument are mangled by PowerShell 5.1; swap them for single quotes.
    $safeTitle = $Title -replace '"', "'"
    gh pr create --draft --base main --head $current --title $safeTitle --body 'Draft PR opened by push-task-branch.ps1. The owner reviews and merges.'
    if ($LASTEXITCODE -ne 0) {
        Write-Host "pushed, but gh pr create failed (exit $LASTEXITCODE): gh may be unauthenticated (run gh auth login) or a PR for '$current' may already exist. Check or open it here: $manualUrl"
        exit 2
    }
}
finally {
    Pop-Location
}
