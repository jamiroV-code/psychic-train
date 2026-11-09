# Register (or with -Remove, delete) the route source feeder's Task Scheduler task (D-33, EXPERIMENT tier):
#   mysite-route-feeder  at YOUR logon: uv run python -m api.scripts.route_feeder --queries <abs> --loop
#                        --interval <IntervalSeconds> (restart 3 times, 1 minute apart; a second start while one
#                        runs is ignored; no time limit)
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File deploy\register-route-feeder-task.ps1 -QueriesPath <abs> [-IntervalSeconds 600] [-Remove]
#
# The feeder stays inert while route_source_enabled is false (it writes its status file and the loop exits), so
# registering this task changes nothing until the owner turns the feeder on in the private query file.
# Identity: the CURRENT user, Interactive logon, Limited run level, no elevation; the actual process token SID must
# equal the private policy's service_sid (the feeder publishes the route files with the collector's ACL helpers),
# otherwise the script refuses (exit 4) and changes nothing. It never uses the local system account, a service
# account, a stored credential or the highest run level, and it never changes an ACL to make access work.
# Run it from a NORMAL (not administrator) PowerShell; an elevated shell is refused (exit 4).
# Idempotent: re-running replaces the task with the same definition (-Force). Registering does not start it.
#
# UNRUN: written without running PowerShell; the owner's first run records the result (deploy\README.md,
# "Route source feeder").
param([switch]$Remove, [string]$QueriesPath = '', [int]$IntervalSeconds = 600)

. "$PSScriptRoot\_common.ps1"
$script:MySiteLogName = 'register-route-feeder-task'

$taskName = 'mysite-route-feeder'

if ($Remove) {
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-MySiteLog "Removed scheduled task $taskName"
    } else {
        Write-MySiteLog "Scheduled task $taskName not present; nothing to remove"
    }
    exit 0
}

$config = Import-MySiteConfig -LogName 'register-route-feeder-task'

$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$tokenSid = $identity.User.Value
$windowsPrincipal = New-Object System.Security.Principal.WindowsPrincipal($identity)
if ($windowsPrincipal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-MySiteLog 'Refused: run this from a normal (not administrator) PowerShell; the task never runs elevated.'
    exit 4
}

if (-not $QueriesPath) { $QueriesPath = if ($config.CollectorQueriesPath) { [string]$config.CollectorQueriesPath } else { '' } }
if (-not $QueriesPath) { throw 'The private query path is required (-QueriesPath or CollectorQueriesPath).' }
if (-not [System.IO.Path]::IsPathRooted($QueriesPath)) { throw 'The private query path must be absolute.' }
if ($QueriesPath -match '["`$%;|<>&]') { throw 'The private query path contains a character the task argument cannot carry.' }
if ($IntervalSeconds -lt 300 -or $IntervalSeconds -gt 86400) { throw 'IntervalSeconds must be 300..86400.' }

# The feeder publishes with the policy's service_sid: it must be the identity the task runs as.
$identityCheck = @'
import sys
from pathlib import Path
from api.data.attention import web_queries
from api.data.attention import x_proxy
from api.data.attention.x_proxy_private import actual_service_sid, read_bounded
try:
    sid = actual_service_sid()
    path = Path(sys.argv[1])
    if not path.is_absolute() or not web_queries._outside_repo(str(path.resolve())):
        raise ValueError()
    config = web_queries.load(path).config
    if config.x_proxy_policy_path is None:
        raise ValueError()
    policy_path = Path(config.x_proxy_policy_path)
    policy = x_proxy.parse_policy(read_bounded(policy_path, x_proxy.SMALL_LIMIT), policy_path.parent)
    if policy.service_sid != sid:
        raise ValueError()
    print(sid)
except Exception:
    sys.exit(4)
'@
Push-Location $config.RepoRoot
try {
    $checkedSid = & $config.UvPath run --project api --frozen --group xreader python -c $identityCheck $QueriesPath
    if ($LASTEXITCODE -ne 0 -or [string]$checkedSid -cne $tokenSid) {
        Write-MySiteLog 'Refused: private configuration or actual identity check failed; no task changed.'
        exit 4
    }
} finally { Pop-Location }
$user = $tokenSid
$repoRoot = Split-Path $PSScriptRoot -Parent

$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$feederArgs = @('run', '--project', 'api', '--frozen', 'python', '-m', 'api.scripts.route_feeder',
    '--queries', "`"$QueriesPath`"", '--loop', '--interval', [string]$IntervalSeconds)
$action = New-ScheduledTaskAction -Execute $config.UvPath -Argument ($feederArgs -join ' ') -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Principal $principal `
    -Settings $settings -Action $action -Force | Out-Null
Write-MySiteLog "Registered scheduled task $taskName (at logon of $user, Limited, every $IntervalSeconds s)"
exit 0
