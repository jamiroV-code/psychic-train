# Build the my_site web app with the API's Tailscale address baked in.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File deploy\build-web.ps1 [-DryRun]
#
# NEXT_PUBLIC_API_BASE_URL is inlined into the JavaScript at build time, so it must be
# set BEFORE the build. If the Tailscale address ever changes, rebuild with this script;
# restarting is not enough.
#
# UNVERIFIED IN CI: written without PowerShell available; see deploy\README.md steps B5/B7.
param([switch]$DryRun)

. "$PSScriptRoot\_common.ps1"

$config = Import-MySiteConfig -LogName 'build-web'
$ip = Wait-TailscaleIPv4 -Config $config

$env:NEXT_PUBLIC_API_BASE_URL = "http://${ip}:$($config.ApiPort)"
$buildArgs = @('--filter', 'web', 'build')

Write-Host "Baked API URL: $env:NEXT_PUBLIC_API_BASE_URL"
Write-Host "Reminder: changing the API address needs a rebuild (run this script again)."

if ($DryRun) {
    Write-Host "DRY RUN (nothing built)"
    Write-Host "command = $($config.PnpmPath) $($buildArgs -join ' ')  (in $($config.RepoRoot))"
    Stop-WebPortListener -Config $config -ReportOnly
    exit 0
}

# A running web server holds the build output open; free the web port (by PID) first.
Stop-WebPortListener -Config $config
# No marker while building: start-web.ps1 refuses until a build finishes cleanly.
Remove-WebBuildMarker -Config $config

Write-MySiteLog "Building web with NEXT_PUBLIC_API_BASE_URL=$env:NEXT_PUBLIC_API_BASE_URL"
Set-Location $config.RepoRoot
& $config.PnpmPath @buildArgs
$code = $LASTEXITCODE
Write-MySiteLog "Web build exited with code $code"
if ($code -eq 0) {
    Write-WebBuildMarker -Config $config
}
exit $code
