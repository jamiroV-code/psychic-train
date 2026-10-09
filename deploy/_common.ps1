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

function Get-WebBuildMarkerPath {
    # Inside the build output: every next build clears it, and git already ignores it.
    # Absolute, because the stale check runs before any Set-Location.
    param([Parameter(Mandatory)][hashtable]$Config)
    return (Join-Path $Config.RepoRoot 'web\.next\static\build-marker.json')
}

function Get-WebBuildIdPath {
    param([Parameter(Mandatory)][hashtable]$Config)
    return (Join-Path $Config.RepoRoot 'web\.next\BUILD_ID')
}

function Get-ShortSha {
    param([string]$Sha)
    if ($null -eq $Sha) { return '' }
    $text = $Sha.Trim()
    if ($text.Length -gt 7) { return $text.Substring(0, 7) }
    return $text
}

function ConvertTo-MySiteEpoch {
    # Whole UTC seconds since 1970, floored (file times have 100 ns resolution).
    param([Parameter(Mandatory)][DateTime]$Utc)
    $origin = New-Object DateTime 1970, 1, 1, 0, 0, 0, ([DateTimeKind]::Utc)
    return [int64][Math]::Floor(($Utc - $origin).TotalSeconds)
}

function Invoke-MySiteGit {
    # One read-only git call in the repo: git -C RepoRoot <GitArgs>. Returns the output lines
    # and throws when git is missing or exits non-zero. Stderr is left alone on purpose: under
    # the global Stop preference, PowerShell 5.1 turns redirected stderr text into an error.
    param(
        [Parameter(Mandatory)][hashtable]$Config,
        [Parameter(Mandatory)][string[]]$GitArgs
    )
    $out = @(& git -C $Config.RepoRoot @GitArgs)
    if ($LASTEXITCODE -ne 0) {
        throw ('git ' + ($GitArgs -join ' ') + ' exited with code ' + $LASTEXITCODE)
    }
    return $out
}

function Remove-WebBuildMarker {
    # Called before a build: a failed or running build must leave no marker behind.
    param([Parameter(Mandatory)][hashtable]$Config)
    $markerPath = Get-WebBuildMarkerPath -Config $Config
    if (Test-Path -LiteralPath $markerPath) {
        Remove-Item -LiteralPath $markerPath
        Write-MySiteLog 'Build marker removed before the build.'
    }
}

function Write-WebBuildMarker {
    # Called only after a successful build, as the last step. Records what was built so
    # start-web.ps1 can refuse a stale build. Nothing secret goes in it. Any failure: exit 7.
    param([Parameter(Mandatory)][hashtable]$Config)
    $now = [DateTime]::UtcNow
    $epoch = ConvertTo-MySiteEpoch -Utc $now
    $markerPath = Get-WebBuildMarkerPath -Config $Config
    $buildIdPath = Get-WebBuildIdPath -Config $Config
    try {
        if (-not (Test-Path -LiteralPath $buildIdPath)) { throw 'BUILD_ID not found after the build' }
        $buildId = ([System.IO.File]::ReadAllText($buildIdPath)).Trim()
        $commit = ([string](@(Invoke-MySiteGit -Config $Config -GitArgs @('rev-parse', 'HEAD'))[0])).Trim()
        $webTree = ([string](@(Invoke-MySiteGit -Config $Config -GitArgs @('rev-parse', 'HEAD:web'))[0])).Trim()
        $changes = @(Invoke-MySiteGit -Config $Config -GitArgs @('status', '--porcelain', '--', 'web') | Where-Object { $_ })
        if (-not $buildId -or -not $commit -or -not $webTree) { throw 'empty BUILD_ID or git output' }
        $marker = [ordered]@{
            schema         = 1
            commit         = $commit
            web_tree       = $webTree
            dirty          = ($changes.Count -gt 0)
            build_id       = $buildId
            built_at_epoch = $epoch
            built_at_utc   = $now.ToString('yyyy-MM-ddTHH:mm:ss', [System.Globalization.CultureInfo]::InvariantCulture) + 'Z'
        }
        $json = ConvertTo-Json -InputObject $marker -Compress
        $markerDir = Split-Path -Parent $markerPath
        if (-not (Test-Path -LiteralPath $markerDir)) {
            New-Item -ItemType Directory -Path $markerDir | Out-Null
        }
        [System.IO.File]::WriteAllText($markerPath, $json, (New-Object System.Text.UTF8Encoding($false)))
    } catch {
        Write-MySiteLog "Build marker not written: $($_.Exception.Message)"
        exit 7
    }
    Write-MySiteLog "Build marker written: commit $(Get-ShortSha $commit) web tree $(Get-ShortSha $webTree) build id $buildId"
}

function Test-WebBuildFresh {
    # Refuse to start a missing or stale build. First failing check wins: marker present,
    # marker readable, build output matches it, git readable, web/ tree unchanged, no tracked
    # web file newer than the build. HEAD alone moving is only a note. Refusal: exit 4.
    # With -ReportOnly it prints the result and returns; it never exits.
    param(
        [Parameter(Mandatory)][hashtable]$Config,
        [switch]$ReportOnly
    )
    $reason = $null
    $marker = $null
    $headCommit = ''
    $webTree = ''
    $notes = @()
    $markerPath = Get-WebBuildMarkerPath -Config $Config
    $buildIdPath = Get-WebBuildIdPath -Config $Config
    if (-not (Test-Path -LiteralPath $markerPath)) {
        $reason = 'no build marker'
    }
    if ($null -eq $reason) {
        try {
            $marker = [System.IO.File]::ReadAllText($markerPath) | ConvertFrom-Json
            $names = @($marker.PSObject.Properties | ForEach-Object { $_.Name })
            foreach ($field in 'schema', 'commit', 'web_tree', 'dirty', 'build_id', 'built_at_epoch') {
                if ($names -notcontains $field) { throw ('missing field ' + $field) }
            }
        } catch {
            $reason = 'build marker unreadable'
        }
    }
    if ($null -eq $reason) {
        $currentBuildId = ''
        if (Test-Path -LiteralPath $buildIdPath) {
            $currentBuildId = ([System.IO.File]::ReadAllText($buildIdPath)).Trim()
        }
        if (-not $currentBuildId -or $currentBuildId -ne [string]$marker.build_id) {
            $reason = 'build output missing or differs from the marker'
        }
    }
    if ($null -eq $reason) {
        try {
            $headCommit = ([string](@(Invoke-MySiteGit -Config $Config -GitArgs @('rev-parse', 'HEAD'))[0])).Trim()
            $webTree = ([string](@(Invoke-MySiteGit -Config $Config -GitArgs @('rev-parse', 'HEAD:web'))[0])).Trim()
            if (-not $headCommit -or -not $webTree) { throw 'empty git output' }
        } catch {
            $reason = 'cannot read git state'
        }
    }
    if ($null -eq $reason -and $webTree -ne [string]$marker.web_tree) {
        $builtTree = Get-ShortSha ([string]$marker.web_tree)
        $currentTree = Get-ShortSha $webTree
        $reason = "web/ sources changed since the build (built tree $builtTree, current $currentTree)"
    }
    if ($null -eq $reason) {
        $files = @()
        try {
            $files = @(Invoke-MySiteGit -Config $Config -GitArgs @('-c', 'core.quotepath=off', 'ls-files', '--', 'web'))
        } catch {
            $reason = 'cannot read git state'
        }
        $builtAt = [int64][Math]::Floor([double]$marker.built_at_epoch)
        $newest = [int64]0
        $newestPath = ''
        foreach ($relative in $files) {
            if (-not $relative) { continue }
            $full = Join-Path $Config.RepoRoot ([string]$relative)
            if (-not [System.IO.File]::Exists($full)) { continue }
            $written = ConvertTo-MySiteEpoch -Utc ([System.IO.File]::GetLastWriteTimeUtc($full))
            if ($written -gt $newest) {
                $newest = $written
                $newestPath = [string]$relative
            }
        }
        if ($null -eq $reason -and $newest -gt $builtAt) {
            $reason = "tracked web file newer than the build: $newestPath"
        }
    }
    if ($null -ne $reason) {
        $line = "Stale build: $reason. Run deploy\build-web.ps1, then start again."
        if ($ReportOnly) {
            Write-Host "DRY RUN: $line"
            return
        }
        Write-MySiteLog $line
        exit 4
    }
    if ($headCommit -ne [string]$marker.commit) {
        $notes += "Note: HEAD $(Get-ShortSha $headCommit) differs from the build commit $(Get-ShortSha ([string]$marker.commit)); web/ is unchanged."
    }
    if ($marker.dirty -eq $true) {
        $notes += 'Note: built from uncommitted web/ changes.'
    }
    $result = @("Build is current: commit $(Get-ShortSha ([string]$marker.commit)) web tree $(Get-ShortSha $webTree) build id $($marker.build_id)") + $notes
    foreach ($text in $result) {
        if ($ReportOnly) { Write-Host "DRY RUN: $text" } else { Write-MySiteLog $text }
    }
}
