# Register (or with -Remove, delete) the collector's two Task Scheduler tasks (finish plan OD-3):
#   mysite-collector         at YOUR logon: deploy\start-collector.ps1 -Doctor (restart 3 times, 1 minute apart;
#                            a second start while one runs is ignored)
#   mysite-collector-doctor  daily at -DoctorTime (local time): deploy\doctor.ps1 (offline; writes doctor.json)
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File deploy\register-collector-tasks.ps1 [-QueriesPath <abs>] [-DoctorTime 07:00] [-Remove]
#
# Identity: both tasks run as the CURRENT user, Interactive logon, Limited run level, no elevation. The registering
# identity is the actual process token SID; when the private query file names a proxy policy, that SID must equal
# the policy's service_sid, otherwise the script refuses (exit 4) and changes nothing. It never uses the local system
# account, a service account, a stored credential or the highest run level, and it never changes an ACL to make access work.
# Run it from a NORMAL (not administrator) PowerShell; an elevated shell is refused (exit 4).
#
# Limit: these are logged-on-user tasks (the collector browser needs your interactive session). Nothing collects
# while you are logged out; whether a locked or disconnected session still renders is probe BP12 (owner-run).
# Idempotent: re-running replaces both tasks with the same definition (-Force). Registering does not start them.
#
# UNRUN: written without running PowerShell; the owner's first run records the result (deploy\README.md,
# "Collector identity pool runbook", step 9).
param([switch]$Remove, [string]$QueriesPath = '', [string]$DoctorTime = '07:00')

. "$PSScriptRoot\_common.ps1"
$script:MySiteLogName = 'register-collector-tasks'

$taskNames = @('mysite-collector', 'mysite-collector-doctor')

if ($Remove) {
    foreach ($name in $taskNames) {
        if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskName $name -Confirm:$false
            Write-MySiteLog "Removed scheduled task $name"
        } else {
            Write-MySiteLog "Scheduled task $name not present; nothing to remove"
        }
    }
    exit 0
}

$config = Import-MySiteConfig -LogName 'register-collector-tasks'

$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$tokenSid = $identity.User.Value
$windowsPrincipal = New-Object System.Security.Principal.WindowsPrincipal($identity)
if ($windowsPrincipal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-MySiteLog 'Refused: run this from a normal (not administrator) PowerShell; the tasks never run elevated.'
    exit 4
}

$privateQueries = if ($QueriesPath) { $QueriesPath } elseif ($config.CollectorQueriesPath) { [string]$config.CollectorQueriesPath } else { '' }
if ($privateQueries) {
    if (-not [System.IO.Path]::IsPathRooted($privateQueries)) { throw 'Collector query path must be absolute.' }
    if ($privateQueries -match '["`$%;|<>&]') { throw 'Collector query path contains a character the task argument cannot carry.' }
}
if ($DoctorTime -notmatch '^([01][0-9]|2[0-3]):[0-5][0-9]$') { throw 'DoctorTime must be HH:mm (24-hour).' }

# Validate the same private snapshot as the collector, including actual_service_sid(), before any task write.
$identityCheck = @'
import sys
from pathlib import Path
from api.data.attention import web_queries
from api.data.attention.x_proxy_private import actual_service_sid
from api.data.attention.x_proxy_snapshot import load_snapshot
try:
    sid = actual_service_sid()
    path = Path(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] else None
    if path is not None and (not path.is_absolute() or not web_queries._outside_repo(str(path.resolve()))):
        raise ValueError()
    config = web_queries.load(path).config
    routed = config.x_proxy_required or any(getattr(config, k) is not None for k in
        ('x_proxy_list_path', 'x_proxy_assignments_path', 'x_proxy_policy_path'))
    if routed:
        if path is None or load_snapshot(path, repo_root=web_queries.REPO_ROOT).policy.service_sid != sid:
            raise ValueError()
    print(sid)
except Exception:
    sys.exit(4)
'@
Push-Location $config.RepoRoot
try {
    $checkedSid = & $config.UvPath run --project api --frozen --group xreader python -c $identityCheck $privateQueries
    if ($LASTEXITCODE -ne 0 -or [string]$checkedSid -cne $tokenSid) {
        Write-MySiteLog 'Refused: private configuration or actual identity check failed; no tasks changed.'
        exit 4
    }
} finally { Pop-Location }
$user = $tokenSid
$powershellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$repoRoot = Split-Path $PSScriptRoot -Parent
$queryArgument = if ($privateQueries) { " -QueriesPath `"$privateQueries`"" } else { '' }

$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

# mysite-collector: at logon, doctor pre-flight, restarts 3 times one minute apart, no time limit, one instance.
$collectorAction = New-ScheduledTaskAction -Execute $powershellExe `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $PSScriptRoot 'start-collector.ps1')`" -Doctor$queryArgument" `
    -WorkingDirectory $repoRoot
$collectorTrigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$collectorSettings = New-ScheduledTaskSettingsSet `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName 'mysite-collector' -Trigger $collectorTrigger -Principal $principal `
    -Settings $collectorSettings -Action $collectorAction -Force | Out-Null
Write-MySiteLog "Registered scheduled task mysite-collector (at logon of $user, Limited, doctor pre-flight)"

# mysite-collector-doctor: daily, offline, same principal; a run while one is still going is ignored.
$doctorAction = New-ScheduledTaskAction -Execute $powershellExe `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $PSScriptRoot 'doctor.ps1')`"$queryArgument" `
    -WorkingDirectory $repoRoot
$doctorTrigger = New-ScheduledTaskTrigger -Daily -At $DoctorTime
$doctorSettings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName 'mysite-collector-doctor' -Trigger $doctorTrigger -Principal $principal `
    -Settings $doctorSettings -Action $doctorAction -Force | Out-Null
Write-MySiteLog "Registered scheduled task mysite-collector-doctor (daily at $DoctorTime, as $user, Limited)"
exit 0
