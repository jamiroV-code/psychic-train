# Register (or with -Remove, delete) the two Task Scheduler tasks that start my_site
# when YOU log on: mysite-api and mysite-web. Runs as the current user only, no elevation.
# Idempotent: re-running replaces the tasks with the same definition.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File deploy\register-tasks.ps1 [-Remove]
#
# UNVERIFIED IN CI: the ScheduledTasks cmdlet parameter names were written without
# PowerShell available. If one is rejected, check `Get-Help New-ScheduledTaskSettingsSet
# -Parameter *` and report it (deploy\README.md, step B11).
param([switch]$Remove)

. "$PSScriptRoot\_common.ps1"
$script:MySiteLogName = 'register-tasks'

$taskNames = @('mysite-api', 'mysite-web')

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

$user = "$env:USERDOMAIN\$env:USERNAME"
$powershellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

$scripts = @{
    'mysite-api' = Join-Path $PSScriptRoot 'start-api.ps1'
    'mysite-web' = Join-Path $PSScriptRoot 'start-web.ps1'
}

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

foreach ($name in $taskNames) {
    $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$($scripts[$name])`""
    $action = New-ScheduledTaskAction -Execute $powershellExe -Argument $arguments -WorkingDirectory (Split-Path $PSScriptRoot -Parent)
    Register-ScheduledTask -TaskName $name -Trigger $trigger -Principal $principal -Settings $settings -Action $action -Force | Out-Null
    Write-MySiteLog "Registered scheduled task $name (at logon of $user, no elevation)"
}
exit 0
