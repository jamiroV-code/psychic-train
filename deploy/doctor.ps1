# Collector doctor: one-command, read-only self-check of the collector's owner inputs and subsystems.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File deploy\doctor.ps1 [-QueriesPath <abs>] [-Json] [-Live] [-SelfTest]
#
# Runs `python -m api.scripts.collector_doctor` with the collector's cache and X environment. Offline: no network,
# no firewall or scheduled-task writes, no account or pool changes. Prints PASS/WARN/FAIL/UNKNOWN per check with a
# fix hint (never a secret, path or IP) and writes <cache>\attention\_reports\doctor.json for the status box.
# Exit codes: 0 all PASS; 1 any WARN or UNKNOWN; 2 any FAIL.
# -Live also gates on recorded live probe evidence (LIVE-READY only). -SelfTest runs the synthetic end-to-end cycle.
#
# UNRUN: written without running PowerShell; the owner's first run records the result.
param([string]$QueriesPath = '', [switch]$Json, [switch]$Live, [switch]$SelfTest)

. "$PSScriptRoot\_common.ps1"

$config = Import-MySiteConfig -LogName 'doctor'
if ($config.CacheRoot) { $env:SCREENER_CACHE_ROOT = [string]$config.CacheRoot }

# The X library's required settings, as start-collector.ps1 sets them, so the env check sees the collector's view.
$env:TWS_TELEMETRY = '0'
$env:DO_NOT_TRACK = '1'
$env:TWS_LOG_LEVEL = 'WARNING'
$env:TWS_RAISE_WHEN_NO_ACCOUNT = '1'
foreach ($name in @('TWS_PROXY', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE')) {
    Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
}

$privateQueries = if ($QueriesPath) { $QueriesPath } elseif ($config.CollectorQueriesPath) { [string]$config.CollectorQueriesPath } else { '' }
if ($privateQueries -and -not [System.IO.Path]::IsPathRooted($privateQueries)) { throw 'Collector query path must be absolute.' }

$doctorArgs = @('run', '--project', 'api', '--frozen', '--group', 'xreader', 'python', '-m', 'api.scripts.collector_doctor')
if ($privateQueries) { $doctorArgs += @('--queries', $privateQueries) }
if ($Json) { $doctorArgs += '--json' }
if ($Live) { $doctorArgs += '--live' }
if ($SelfTest) { $doctorArgs += '--selftest' }

Set-Location $config.RepoRoot
& $config.UvPath @doctorArgs
$code = $LASTEXITCODE
Write-MySiteLog "Collector doctor exited with code $code (0 all pass, 1 warn or unknown, 2 fail)"
exit $code
