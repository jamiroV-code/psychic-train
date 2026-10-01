# Start the my_site API bound to this PC's Tailscale IPv4 only.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File deploy\start-api.ps1 [-DryRun]
#
# Order: wait for the Tailscale address -> stage A pull (if AutoPull) -> set the
# environment the API reads at import -> run the API in the foreground (no reload).
# -DryRun prints what would run and exits 0 without starting anything.
#
# UNVERIFIED IN CI: written without PowerShell available; see deploy\README.md steps B5/B6.
param([switch]$DryRun)

. "$PSScriptRoot\_common.ps1"

$config = Import-MySiteConfig -LogName 'api'
$ip = Wait-TailscaleIPv4 -Config $config

if ($config.AutoPull -and -not $DryRun) {
    Invoke-StageAPull -Config $config
}

# The API reads these at import, so they must be in the process environment first.
$origins = @("http://${ip}:$($config.WebPort)") + @($config.ExtraCorsOrigins | Where-Object { $_ })
$env:SCREENER_CORS_ORIGINS = ($origins -join ',')
if ($config.CacheRoot) { $env:SCREENER_CACHE_ROOT = [string]$config.CacheRoot }
if ($config.WatchlistPath) { $env:SCREENER_WATCHLIST_PATH = [string]$config.WatchlistPath }

# `python -m uvicorn`, NOT `uvicorn` — verified on the user's Windows PC 01-10-26.
# `uv run --project api uvicorn ...` fails there with "uv trampoline failed to canonicalize
# script path": uv installs console scripts as Windows trampoline .exe shims, and launching that
# shim through `uv run` could not resolve its own path. Going through the module entry point skips
# the shim entirely and works. Same process, same binding — this is a launcher-only change.
# Pinned by api/tests/deploy/test_deploy_config_shape.py so it cannot regress.
$apiArgs = @('run', '--project', 'api', 'python', '-m', 'uvicorn', 'api.main:app', '--host', $ip, '--port', [string]$config.ApiPort)

if ($DryRun) {
    Write-Host "DRY RUN (nothing started)"
    Write-Host "host                    = $ip"
    Write-Host "port                    = $($config.ApiPort)"
    Write-Host "SCREENER_CORS_ORIGINS   = $env:SCREENER_CORS_ORIGINS"
    Write-Host "SCREENER_CACHE_ROOT     = $(if ($config.CacheRoot) { $config.CacheRoot } else { '(default: api\data\cache)' })"
    Write-Host "SCREENER_WATCHLIST_PATH = $(if ($config.WatchlistPath) { $config.WatchlistPath } else { '(default: api\data\watchlist.json)' })"
    Write-Host "AutoPull                = $($config.AutoPull) (skipped in dry run)"
    Write-Host "command                 = $($config.UvPath) $($apiArgs -join ' ')  (in $($config.RepoRoot))"
    exit 0
}

Write-MySiteLog "Starting API on ${ip}:$($config.ApiPort); CORS origins: $env:SCREENER_CORS_ORIGINS"
Set-Location $config.RepoRoot
& $config.UvPath @apiArgs
$code = $LASTEXITCODE
Write-MySiteLog "API process exited with code $code"
exit $code
