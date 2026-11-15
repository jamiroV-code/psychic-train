# Run one perp collector pass (RFC-001 S1) and exit. Scheduling is the owner's choice (see deploy\README.md "Perp collector").
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File deploy\run-perp-collector.ps1 [-RepoRoot <path>] [-CacheRoot <path>] [-Job hl-snapshot] [-DryRun]
#
# Order: load the config -> set SCREENER_CACHE_ROOT the way the API does -> run
# `collect_perp.py --job <job>` once -> exit with its exit code (0 ok, 1 nothing written, 2 written but flagged).
# -DryRun prints what would run and exits 0 without starting anything.
#
# -DryRun behavior is covered by the Windows deploy test; actual collection and Scheduler behavior remain unverified.
param(
    [string]$RepoRoot,
    [string]$CacheRoot,
    [ValidateSet('hl-snapshot')][string]$Job = 'hl-snapshot',
    [switch]$DryRun
)

. "$PSScriptRoot\_common.ps1"

$config = Import-MySiteConfig -LogName 'perp-collector' -AllowMissingRepoRoot

# Resolve both roots once so the printed DryRun contract matches the launcher's actual inputs.
$configuredRepoRoot = if ($config.ContainsKey('RepoRoot')) { [string]$config['RepoRoot'] } else { $null }
if (-not [string]::IsNullOrWhiteSpace($RepoRoot)) {
    $effectiveRepoRoot = $RepoRoot
} elseif (-not [string]::IsNullOrWhiteSpace($configuredRepoRoot)) {
    $effectiveRepoRoot = $configuredRepoRoot
} else {
    $effectiveRepoRoot = Split-Path -Parent $PSScriptRoot
}

$configuredCacheRoot = if ($config.ContainsKey('CacheRoot')) { [string]$config['CacheRoot'] } else { $null }
if (-not [string]::IsNullOrWhiteSpace($CacheRoot)) {
    $effectiveCacheRoot = $CacheRoot
} elseif (-not [string]::IsNullOrWhiteSpace($configuredCacheRoot)) {
    $effectiveCacheRoot = $configuredCacheRoot
} else {
    $effectiveCacheRoot = Join-Path $effectiveRepoRoot 'api\data\cache'
}
$env:SCREENER_CACHE_ROOT = $effectiveCacheRoot

$collectorArgs = @('run', '--project', 'api', 'python', 'api/scripts/collect_perp.py', '--job', $Job)

if ($DryRun) {
    Write-Host "DRY RUN (nothing started)"
    Write-Host "RepoRoot            = $effectiveRepoRoot"
    Write-Host "SCREENER_CACHE_ROOT = $effectiveCacheRoot"
    Write-Host "command             = $($config.UvPath) $($collectorArgs -join ' ')  (in $effectiveRepoRoot)"
    exit 0
}

Push-Location $effectiveRepoRoot
try {
    & $config.UvPath @collectorArgs
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $code
