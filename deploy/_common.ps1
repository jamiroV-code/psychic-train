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

function Get-WebPortListenerIds {
    # Unique PIDs listening on a local TCP port, selected by port only. Nothing returned means
    # the port is free. SilentlyContinue keeps a no-match quiet under the global Stop
    # preference; a real failure (cmdlet missing, CIM error) is thrown to the caller.
    param([Parameter(Mandatory)][int]$Port)
    $ids = @()
    try {
        $conns = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    } catch {
        throw ('Get-NetTCPConnection failed: ' + $_.Exception.Message)
    }
    foreach ($conn in $conns) {
        if ($null -ne $conn) { $ids += [int]$conn.OwningProcess }
    }
    return @($ids | Sort-Object -Unique)
}

function Stop-WebPortListener {
    # Stop whatever listens on the configured web port, by PID only, then wait (bounded) for
    # the port to clear. Refuses System/Idle (PID 4 or less) and this script itself. Any
    # failure is fail-closed: log and exit 5. With -ReportOnly nothing is stopped or logged
    # to the file; it only prints what would happen and never exits.
    param(
        [Parameter(Mandatory)][hashtable]$Config,
        [switch]$ReportOnly
    )
    $port = 0
    $valid = [int]::TryParse([string]$Config.WebPort, [ref]$port)
    if (-not $valid -or $port -lt 1 -or $port -gt 65535 -or [string]$port -eq [string]$Config.ApiPort) {
        $message = "WebPort $($Config.WebPort) is not a usable port: it must be 1-65535 and differ from ApiPort."
        if ($ReportOnly) { Write-Host "DRY RUN: $message" } else { Write-MySiteLog $message }
        exit 2
    }
    try {
        $ids = @(Get-WebPortListenerIds -Port $port)
    } catch {
        $reason = $_.Exception.Message
        if ($ReportOnly) {
            Write-Host "DRY RUN: cannot list listeners: $reason"
            return
        }
        Write-MySiteLog "Port ${port}: cannot list listeners, not continuing: $reason"
        exit 5
    }
    if ($ids.Count -eq 0) {
        if ($ReportOnly) {
            Write-Host "DRY RUN: port $port is free; nothing would be stopped."
        } else {
            Write-MySiteLog "Port ${port}: nothing listening; nothing to stop."
        }
        return
    }
    foreach ($listenerId in $ids) {
        $name = '(unknown)'
        $proc = Get-Process -Id $listenerId -ErrorAction SilentlyContinue
        if ($null -ne $proc) { $name = [string]$proc.ProcessName }
        if ($listenerId -le 4 -or $listenerId -eq $PID) {
            if ($ReportOnly) {
                Write-Host "DRY RUN: would refuse to stop PID $listenerId (protected)"
                continue
            }
            Write-MySiteLog "Port ${port}: PID $listenerId ($name) is protected; refusing to stop it."
            exit 5
        }
        if ($ReportOnly) {
            Write-Host "DRY RUN: would stop PID $listenerId ($name) listening on port $port (nothing stopped)."
            continue
        }
        Write-MySiteLog "Port ${port}: stopping PID $listenerId ($name) listening on it."
        try {
            Stop-Process -Id $listenerId -ErrorAction Stop
        } catch {
            $reason = $_.Exception.Message
            $still = Get-Process -Id $listenerId -ErrorAction SilentlyContinue
            if ($null -ne $still) {
                Write-MySiteLog "Port ${port}: could not stop PID ${listenerId}: $reason."
                exit 5
            }
        }
    }
    if ($ReportOnly) { return }
    $deadline = (Get-Date).AddSeconds(10)
    while ($true) {
        try {
            $left = @(Get-WebPortListenerIds -Port $port)
        } catch {
            Write-MySiteLog "Port ${port}: cannot list listeners, not continuing: $($_.Exception.Message)"
            exit 5
        }
        if ($left.Count -eq 0) { break }
        if ((Get-Date) -ge $deadline) {
            Write-MySiteLog "Port ${port}: still in use after 10s; not continuing."
            exit 5
        }
        Start-Sleep -Milliseconds 500
    }
    Write-MySiteLog "Port ${port}: free."
}
