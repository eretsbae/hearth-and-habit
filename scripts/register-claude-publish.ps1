# register-claude-publish.ps1 - registers the hearth_publish_mwf task (PowerShell 5.1, ASCII only).
#
# Mon/Wed/Fri 20:43 local (KST) -> scripts/claude-publish.ps1. GitHub Actions
# publishes at 22:17 KST, so the session has about 90 minutes.
# Logon type: S4U (runs whether or not the owner is logged on, no stored
# password), like assistant_dispatch_0715 and nightloop_0115, which also run
# `claude -p`. If S4U registration is refused without elevation, falls back to
# Interactive and wraps the action in conhost --headless (C:\workspace\CLAUDE.md).
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\register-claude-publish.ps1 [-StartDate yyyy-MM-dd]
#   ... -Unregister      remove the task
#
# ASCII ONLY.

param(
    [string]$TaskName = 'hearth_publish_mwf',
    [string]$StartDate = '',
    [switch]$Unregister
)

$ErrorActionPreference = 'Stop'
if ($Unregister) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false; Write-Output "removed $TaskName"; exit 0 }

$script = Join-Path $PSScriptRoot 'claude-publish.ps1'
$psExe  = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$psArgs = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $script + '"'
if (-not $StartDate) { $StartDate = (Get-Date).AddDays(1).ToString('yyyy-MM-dd') }
$at = [datetime]::ParseExact($StartDate + ' 20:43', 'yyyy-MM-dd HH:mm', $null)

$trigger  = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday, Wednesday, Friday -At $at
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
              -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable:$false
$user = $env:USERDOMAIN + '\' + $env:USERNAME
$desc = 'hearth-and-habit: write the scheduled post with Claude Code (generator/CLAUDE_RUN.md); Actions publishes 22:17 KST'

try {
    $action    = New-ScheduledTaskAction -Execute $psExe -Argument $psArgs
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType S4U -RunLevel Limited
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
        -Principal $principal -Description $desc -Force | Out-Null
    Write-Output "registered $TaskName (S4U) first run on or after $($at.ToString('yyyy-MM-dd HH:mm'))"
} catch {
    Write-Output "S4U refused ($($_.Exception.Message.Trim())); falling back to Interactive + conhost --headless"
    $action    = New-ScheduledTaskAction -Execute 'C:\Windows\System32\conhost.exe' -Argument ('--headless ' + $psExe + ' ' + $psArgs)
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
        -Principal $principal -Description $desc -Force | Out-Null
    Write-Output "registered $TaskName (Interactive, runs only while logged on) first run on or after $($at.ToString('yyyy-MM-dd HH:mm'))"
}
