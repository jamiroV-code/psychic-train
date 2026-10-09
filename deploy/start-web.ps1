# Start the built my_site web app (next start, never the dev server) on this PC's
# Tailscale IPv4 only.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File deploy\start-web.ps1 [-DryRun] [-SmokeTimeoutSeconds <5..600>]
#
# Needs a prior build from deploy\build-web.ps1 (the API address is baked in at build time).
# next start runs as a child process; a smoke check then polls this PC's own Tailscale
# address for HTTP 200 and the marker's build id (default 90 s, exit 6 on failure). After a
# passing check the script waits for the server to end, with no time limit: it is the service.
#
# UNVERIFIED IN CI: written without PowerShell available; see deploy\README.md steps B5/B6.
param(
    [switch]$DryRun,
    [int]$SmokeTimeoutSeconds = 0
)

. "$PSScriptRoot\_common.ps1"

$config = Import-MySiteConfig -LogName 'web'
if ($SmokeTimeoutSeconds -ne 0 -and ($SmokeTimeoutSeconds -lt 5 -or $SmokeTimeoutSeconds -gt 600)) {
    Write-MySiteLog "SmokeTimeoutSeconds must be 0 (default, 90 s) or 5 to 600; got $SmokeTimeoutSeconds."
    exit 2
}
$ip = Wait-TailscaleIPv4 -Config $config

$webArgs = @('--filter', 'web', 'exec', 'next', 'start', '-H', $ip, '-p', [string]$config.WebPort)
$smokeSeconds = 90
if ($SmokeTimeoutSeconds -ne 0) { $smokeSeconds = $SmokeTimeoutSeconds }

if ($DryRun) {
    Write-Host "DRY RUN (nothing started)"
    Write-Host "host    = $ip"
    Write-Host "port    = $($config.WebPort)"
    Write-Host "command = $($config.PnpmPath) $($webArgs -join ' ')  (in $($config.RepoRoot))"
    Write-Host "smoke   = http://${ip}:$($config.WebPort)/ within ${smokeSeconds}s"
    Test-WebBuildFresh -Config $config -ReportOnly
    Stop-WebPortListener -Config $config -ReportOnly
    exit 0
}

# Refuse a missing or stale build before touching the running server (exit 4).
Test-WebBuildFresh -Config $config

# Free the web port (by PID, never by name) so the new server can bind it.
Stop-WebPortListener -Config $config

Write-MySiteLog "Starting web on ${ip}:$($config.WebPort)"
$proc = Start-Process -FilePath $config.PnpmPath -ArgumentList $webArgs -WorkingDirectory $config.RepoRoot -NoNewWindow -PassThru
# Reading Handle once keeps the exit code readable after the process ends.
$null = $proc.Handle

if (-not (Invoke-WebSmokeCheck -Config $config -Ip $ip -Process $proc -TimeoutSeconds $smokeSeconds)) {
    Write-MySiteLog 'Smoke check failed; stopping the new web server.'
    # The port listener is the node grandchild; stop it first, then the pnpm parent.
    Stop-WebPortListener -Config $config
    Stop-Process -Id $proc.Id -ErrorAction SilentlyContinue
    exit 6
}

# Deliberately unbounded: the server runs until it stops (D6, as the old foreground call did).
$proc.WaitForExit()
$code = $proc.ExitCode
if ($null -eq $code) { $code = 1 }
Write-MySiteLog "Web process exited with code $code"
exit $code
