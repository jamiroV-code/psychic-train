# Start the attention collector (X and Reddit) as its own process, separate from the API.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File deploy\start-collector.ps1 [-DryRun] [-Doctor] [-QueriesPath <abs>]
#
# Order: load the config -> set the environment the collector checks -> run
# `python -m api.data.attention_collector` in the foreground until CTRL+C or the window closes.
# -DryRun prints what would run and exits 0 without starting anything.
# -Doctor first runs the offline collector doctor (`python -m api.scripts.collector_doctor`, no -Live, no
# -SelfTest). Any FAIL (doctor exit 2 or more) refuses the start with exit 5; WARN/UNKNOWN (exit 1) is logged
# and the collector starts, because pending live evidence must never stop collection.
#
# Restarting the API never touches this process. It does not pull code (start-api.ps1 does);
# after a pull that changes the collector, restart this script. It refuses to start (exit 3)
# while another collector, standalone or inside the API, still writes a fresh heartbeat.
#
# UNRUN: written without running PowerShell; see deploy\README.md "Collector (separate from the API)".
param([switch]$DryRun, [string]$QueriesPath = '', [switch]$Doctor)

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

# Keep global proxy variables out. Bind only a recognized configured backend; Python verifies curl before loading it.
foreach ($name in @('TWS_PROXY', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE')) {
    Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
}
$privateQueries = if ($QueriesPath) { $QueriesPath } elseif ($config.CollectorQueriesPath) { [string]$config.CollectorQueriesPath } else { '' }
if ($privateQueries -and -not [System.IO.Path]::IsPathRooted($privateQueries)) { throw 'Collector query path must be absolute.' }
$queriesPath = if ($privateQueries) { $privateQueries } else { Join-Path $config.RepoRoot 'api\data\attention_queries.json' }
$inputStream = [System.IO.File]::OpenRead($queriesPath)
try {
    $bytes = New-Object byte[] (1048576 + 1)
    $count = 0
    while ($count -lt $bytes.Length) {
        $read = $inputStream.Read($bytes, $count, $bytes.Length - $count)
        if ($read -eq 0) { break }
        $count += $read
    }
    if ($count -gt 1048576) { throw 'Collector query file exceeds 1 MiB.' }
    $queries = [System.Text.Encoding]::UTF8.GetString($bytes, 0, $count) | ConvertFrom-Json
} finally {
    $inputStream.Dispose()
}
$hasRouting = $queries.collector.x_proxy_required -eq $true
foreach ($name in @('x_proxy_list_path', 'x_proxy_assignments_path', 'x_proxy_policy_path')) {
    if ($null -ne $queries.collector.$name) { $hasRouting = $true }
}
if ($hasRouting -and -not $privateQueries) {
    throw 'Configured proxy collection requires an explicit private owner-query path.'
}
$styleProperty = $queries.collector.PSObject.Properties['x_connection_style']
$style = if ($null -eq $styleProperty) { 'plain' } else { $styleProperty.Value }
if ($style -cnotin @('plain', 'curl')) { throw 'Invalid x_connection_style; expected plain or curl.' }
$env:TWS_HTTP_BACKEND = if ($style -eq 'curl') { 'curl' } else { 'httpx' }

# SCREENER_ATTENTION_REDDIT_STREAM is inherited as the owner sets it (exactly 1 turns the Reddit stream on).
$stream = if ($env:SCREENER_ATTENTION_REDDIT_STREAM) { $env:SCREENER_ATTENTION_REDDIT_STREAM } else { '(not set: stream off)' }

$collectorArgs = @('run', '--project', 'api', '--frozen', '--group', 'xreader', 'python', '-m', 'api.data.attention_collector',
                   '--queries', $queriesPath)

if ($DryRun) {
    Write-Host "DRY RUN (nothing started)"
    Write-Host "SCREENER_CACHE_ROOT              = $(if ($config.CacheRoot) { $config.CacheRoot } else { '(default: api\data\cache)' })"
    Write-Host "SCREENER_ATTENTION_PC_WORKER     = $env:SCREENER_ATTENTION_PC_WORKER"
    Write-Host "SCREENER_ATTENTION_REDDIT_STREAM = $stream"
    Write-Host "TWS_TELEMETRY / DO_NOT_TRACK     = $env:TWS_TELEMETRY / $env:DO_NOT_TRACK"
    Write-Host "TWS_LOG_LEVEL                    = $env:TWS_LOG_LEVEL"
    Write-Host "TWS_RAISE_WHEN_NO_ACCOUNT        = $env:TWS_RAISE_WHEN_NO_ACCOUNT"
    Write-Host "proxy variables                  = cleared"
    Write-Host "command                          = uv run --project api --frozen --group xreader python -m api.data.attention_collector --queries <selected>"
    Write-Host "doctor pre-flight                = $(if ($Doctor) { 'on (offline; FAIL refuses the start)' } else { 'off' })"
    exit 0
}

if ($Doctor) {
    $doctorArgs = @('run', '--project', 'api', '--frozen', '--group', 'xreader', 'python', '-m', 'api.scripts.collector_doctor')
    if ($privateQueries) { $doctorArgs += @('--queries', $privateQueries) }
    Set-Location $config.RepoRoot
    & $config.UvPath @doctorArgs
    $doctorCode = $LASTEXITCODE
    if ($doctorCode -ge 2) {
        Write-MySiteLog "Collector doctor reported FAIL (exit $doctorCode); collector NOT started. Run deploy\doctor.ps1 for details."
        exit 5
    }
    Write-MySiteLog "Collector doctor pre-flight exit $doctorCode (0 all pass, 1 warn or unknown); starting the collector"
}

Write-MySiteLog "Starting attention collector; Reddit stream: $stream"
Set-Location $config.RepoRoot
& $config.UvPath @collectorArgs
$code = $LASTEXITCODE
Write-MySiteLog "Attention collector exited with code $code (0 stopped, 2 flag off, 3 another collector running, 4 start failed)"
exit $code
