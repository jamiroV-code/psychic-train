# Push the current task branch and open a DRAFT pull request. Never pushes main, never forces.
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
    $current = (git rev-parse --abbrev-ref HEAD).Trim()
    if ($current -eq 'main' -or $current -eq 'HEAD') { Write-Host "refused: current branch is '$current'; check out a task branch first"; exit 1 }
    if ($Branch -and $Branch -ne $current) { Write-Host "refused: -Branch '$Branch' is not the checked-out branch '$current'"; exit 1 }
    if ($current -notlike 'claude/*' -and -not $Branch) {
        Write-Host "refused: '$current' is not a claude/* branch; pass -Branch $current to confirm it is a named task branch"
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

    if (Get-Command gh -ErrorAction SilentlyContinue) {
        gh pr create --draft --base main --head $current --title $Title --body 'Draft PR opened by push-task-branch.ps1. The owner reviews and merges.'
    }
    else {
        $remote = (git remote get-url origin).Trim() -replace '\.git$', ''
        Write-Host "gh is not installed. Open the draft PR yourself: $remote/pull/new/$current"
    }
}
finally {
    Pop-Location
}
