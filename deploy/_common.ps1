# Shared helpers for the my_site launchers. Dot-source it: . "$PSScriptRoot\_common.ps1"
#
# UNVERIFIED IN CI: this file was written in a container with no PowerShell. Parse it on the
# PC first (deploy\README.md, step B5) before trusting it.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:MySiteHome = Join-Path $env:LOCALAPPDATA 'my_site'
$script:MySiteConfigPath = Join-Path $script:MySiteHome 'deploy.psd1'
$script:MySiteLogDir = Join-Path $script:MySiteHome 'logs'
$script:MySiteLogName = 'deploy'

function Write-MySiteLog {
    param([Parameter(Mandatory)][string]$Message)
    if (-not (Test-Path $script:MySiteLogDir)) {
        New-Item -ItemType Directory -Force -Path $script:MySiteLogDir | Out-Null
    }
    $line = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK'), $script:MySiteLogName, $Message
    Add-Content -Path (Join-Path $script:MySiteLogDir "$($script:MySiteLogName).log") -Value $line
    Write-Host $line
}

function Import-MySiteConfig {
    param([string]$LogName = 'deploy')
    $script:MySiteLogName = $LogName
    if (-not (Test-Path $script:MySiteConfigPath)) {
        Write-MySiteLog "Config file not found: $($script:MySiteConfigPath). Copy deploy\config.example.psd1 there and edit it (deploy\README.md, step B4)."
        exit 2
    }
    $config = Import-PowerShellDataFile -Path $script:MySiteConfigPath
    foreach ($key in 'RepoRoot', 'UvPath', 'PnpmPath', 'TailscaleExe', 'ApiPort', 'WebPort', 'MaxWaitSeconds') {
        if (-not $config.ContainsKey($key) -or [string]::IsNullOrWhiteSpace([string]$config[$key])) {
            Write-MySiteLog "Config key '$key' is missing or empty in $($script:MySiteConfigPath)."
            exit 2
        }
    }
    return $config
}

function Test-TailscaleIPv4 {
    # Accept only an IPv4 inside Tailscale's range, 100.64.0.0/10 (100.64.0.0 - 100.127.255.255).
    param([string]$Candidate)
    $ip = $null
    if (-not [System.Net.IPAddress]::TryParse($Candidate.Trim(), [ref]$ip)) { return $false }
    if ($ip.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { return $false }
    $bytes = $ip.GetAddressBytes()
    return ($bytes[0] -eq 100) -and ($bytes[1] -ge 64) -and ($bytes[1] -le 127)
}

function Wait-TailscaleIPv4 {
    # Bounded wait: poll `tailscale ip -4` every 5 seconds until a 100.64.0.0/10 IPv4 appears
    # or MaxWaitSeconds passes. On timeout, log and exit non-zero (Task Scheduler retries).
    param([Parameter(Mandatory)][hashtable]$Config)
    $deadline = (Get-Date).AddSeconds([int]$Config.MaxWaitSeconds)
    while ($true) {
        try {
            $lines = & $Config.TailscaleExe ip -4 2>$null
            foreach ($line in @($lines)) {
                if ($line -and (Test-TailscaleIPv4 -Candidate ([string]$line))) {
                    return ([string]$line).Trim()
                }
            }
        } catch {
            # Tailscale not running or logged out yet; keep waiting until the deadline.
        }
        if ((Get-Date) -ge $deadline) {
            Write-MySiteLog "Timed out waiting for Tailscale IP after $($Config.MaxWaitSeconds)s. Is Tailscale running and signed in?"
            exit 3
        }
        Start-Sleep -Seconds 5
    }
}

function Invoke-StageAPull {
    # Stage A auto-resume: a single fast-forward-only pull. Never fatal: any failure
    # (no network, local edits, divergence, no upstream) is logged and the app still starts
    # on the code it already has. Never touches any parquet cache.
    param([Parameter(Mandatory)][hashtable]$Config)
    try {
        $output = & git -C $Config.RepoRoot pull --ff-only 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-MySiteLog "Stage A: git pull --ff-only ok. $($output -join ' ')"
        } else {
            Write-MySiteLog "Stage A: git pull --ff-only refused (exit $LASTEXITCODE), starting on current code. $($output -join ' ')"
        }
    } catch {
        Write-MySiteLog "Stage A: git pull --ff-only failed, starting on current code. $($_.Exception.Message)"
    }
}
