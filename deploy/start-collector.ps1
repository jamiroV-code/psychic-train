# Start the attention collector (X and Reddit) as its own process, separate from the API.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File deploy\start-collector.ps1 [-DryRun]
#
# Order: load the config -> set the environment the collector checks -> run
# `python -m api.data.attention_collector` in the foreground until CTRL+C or the window closes.
# -DryRun prints what would run and exits 0 without starting anything.
#
# Restarting the API never touches this process. It does not pull code (start-api.ps1 does);
# after a pull that changes the collector, restart this script. It refuses to start (exit 3)
# while another collector, standalone or inside the API, still writes a fresh heartbeat.
#
# UNRUN: written without running PowerShell; see deploy\README.md "Collector (separate from the API)".
param([switch]$DryRun)

. "$PSScriptRoot\_common.ps1"

$config = Import-MySiteConfig -LogName 'collector'

# The same cache as the API, so the status box on /narrative reads this collector's heartbeat.
if ($config.CacheRoot) { $env:SCREENER_CACHE_ROOT = [string]$config.CacheRoot }

# The collector's own switch, for this process only (the API no longer needs it).
$env:SCREENER_ATTENTION_PC_WORKER = '1'

# The X library's required settings (twscrape_reader.REQUIRED_ENV); X refuses to start without them.
$env:TWS_TELEMETRY = '0'
$env:DO_NOT_TRACK = '1'
$env:TWS_LOG_LEVEL = 'WARNING'
$env:TWS_RAISE_WHEN_NO_ACCOUNT = '1'

# No proxy and no forced HTTP backend reach the collector (X refuses to start with one set).
foreach ($name in @('TWS_PROXY', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'TWS_HTTP_BACKEND')) {
    Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
}

# SCREENER_ATTENTION_REDDIT_STREAM is inherited as the owner sets it (exactly 1 turns the Reddit stream on).
$stream = if ($env:SCREENER_ATTENTION_REDDIT_STREAM) { $env:SCREENER_ATTENTION_REDDIT_STREAM } else { '(not set: stream off)' }

$collectorArgs = @('run', '--project', 'api', 'python', '-m', 'api.data.attention_collector')

if ($DryRun) {
    Write-Host "DRY RUN (nothing started)"
    Write-Host "SCREENER_CACHE_ROOT              = $(if ($config.CacheRoot) { $config.CacheRoot } else { '(default: api\data\cache)' })"
    Write-Host "SCREENER_ATTENTION_PC_WORKER     = $env:SCREENER_ATTENTION_PC_WORKER"
    Write-Host "SCREENER_ATTENTION_REDDIT_STREAM = $stream"
    Write-Host "TWS_TELEMETRY / DO_NOT_TRACK     = $env:TWS_TELEMETRY / $env:DO_NOT_TRACK"
    Write-Host "TWS_LOG_LEVEL                    = $env:TWS_LOG_LEVEL"
    Write-Host "TWS_RAISE_WHEN_NO_ACCOUNT        = $env:TWS_RAISE_WHEN_NO_ACCOUNT"
    Write-Host "proxy variables                  = cleared"
    Write-Host "command                          = $($config.UvPath) $($collectorArgs -join ' ')  (in $($config.RepoRoot))"
    exit 0
}

Write-MySiteLog "Starting attention collector; Reddit stream: $stream"
Set-Location $config.RepoRoot
& $config.UvPath @collectorArgs
$code = $LASTEXITCODE
Write-MySiteLog "Attention collector exited with code $code (0 stopped, 2 flag off, 3 another collector running, 4 start failed)"
exit $code
