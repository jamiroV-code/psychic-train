# Start the built my_site web app (next start, never the dev server) on this PC's
# Tailscale IPv4 only.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File deploy\start-web.ps1 [-DryRun]
#
# Needs a prior build from deploy\build-web.ps1 (the API address is baked in at build time).
#
# UNVERIFIED IN CI: written without PowerShell available; see deploy\README.md steps B5/B6.
param([switch]$DryRun)

. "$PSScriptRoot\_common.ps1"

$config = Import-MySiteConfig -LogName 'web'
$ip = Wait-TailscaleIPv4 -Config $config

$webArgs = @('--filter', 'web', 'exec', 'next', 'start', '-H', $ip, '-p', [string]$config.WebPort)

if ($DryRun) {
    Write-Host "DRY RUN (nothing started)"
    Write-Host "host    = $ip"
    Write-Host "port    = $($config.WebPort)"
    Write-Host "command = $($config.PnpmPath) $($webArgs -join ' ')  (in $($config.RepoRoot))"
    Test-WebBuildFresh -Config $config -ReportOnly
    Stop-WebPortListener -Config $config -ReportOnly
    exit 0
}

# Refuse a missing or stale build before touching the running server (exit 4).
Test-WebBuildFresh -Config $config

# Free the web port (by PID, never by name) so the new server can bind it.
Stop-WebPortListener -Config $config

Write-MySiteLog "Starting web on ${ip}:$($config.WebPort)"
Set-Location $config.RepoRoot
& $config.PnpmPath @webArgs
$code = $LASTEXITCODE
Write-MySiteLog "Web process exited with code $code"
exit $code
