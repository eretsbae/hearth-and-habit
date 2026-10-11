# claude-publish.ps1 - scheduled post writer on the owner's Claude plan (PowerShell 5.1, ASCII only).
#
# Why (2026-10-11): the Anthropic API credit balance ran out, so generate_post.py
# in GitHub Actions can no longer write posts. The owner asked for the scheduled
# post to run on Claude Code session tokens instead. This script starts a
# headless `claude -p` that follows generator/CLAUDE_RUN.md: research, write,
# verify, then `claude_post.py finalize` commits the post and pushes to main.
# generate-and-publish.yml (13:17 UTC = 22:17 KST, Mon/Wed/Fri) publishes it.
#
# The session runs in its own detached worktree (.claude/worktrees/publish, git-
# ignored), reset to origin/main each run, so it never touches files another
# session is editing in the main checkout.
#
# Task: hearth_publish_mwf (Mon/Wed/Fri 20:43 local), registered by
# scripts/register-claude-publish.ps1. Logs: logs/claude-publish/ (git-ignored).
#
# Usage (manual run, any PowerShell):
#   powershell -NoProfile -ExecutionPolicy Bypass -File C:\workspace\hearth-and-habit\scripts\claude-publish.ps1
#   ... -DryRun     prepare the worktree and print the command, do not start claude
#
# ASCII ONLY - PowerShell 5.1 reads BOM-less .ps1 as CP949.

param(
    [switch]$DryRun,
    [string]$Model = 'opus',
    [int]$MaxTurns = 200
)

$repo    = Split-Path -Parent $PSScriptRoot
$wt      = Join-Path $repo '.claude\worktrees\publish'
$logDir  = Join-Path $repo 'logs\claude-publish'
$stamp   = Get-Date -Format 'yyyy-MM-dd_HHmm'
$log     = Join-Path $logDir "$stamp.log"
$utf8    = New-Object System.Text.UTF8Encoding($false)

if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
function Log([string]$m) { [IO.File]::AppendAllText($log, ((Get-Date -Format 's') + ' ' + $m + "`r`n"), $utf8); Write-Output $m }

# Scheduled tasks start with a thin PATH; make python and claude resolvable.
$extra = @("$env:USERPROFILE\.local\bin", "$env:LOCALAPPDATA\Programs\Python\Python312", "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts")
$env:PATH = (($extra | Where-Object { Test-Path $_ }) -join ';') + ';' + $env:PATH
$env:PYTHONIOENCODING = 'utf-8'

$lock = Join-Path $logDir 'run.lock'
if (Test-Path $lock) {
    $old = (Get-Content -LiteralPath $lock -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($old -and (Get-Process -Id $old -ErrorAction SilentlyContinue)) { Log "[LOCKED] pid $old still running"; exit 0 }
}
Set-Content -LiteralPath $lock -Value "$PID" -Encoding ASCII

$rc = 1
try {
    # Fresh detached worktree at origin/main.
    & git -C $repo fetch --quiet origin main 2>&1 | Out-Null
    if (-not (Test-Path (Join-Path $wt '.git'))) {
        & git -C $repo worktree prune 2>&1 | Out-Null
        $out = & git -C $repo worktree add --detach $wt origin/main 2>&1
        Log "[worktree] add: $out"
    }
    & git -C $wt checkout --quiet --force --detach origin/main 2>&1 | Out-Null
    & git -C $wt clean -fdq 2>&1 | Out-Null
    $head = (& git -C $wt rev-parse --short HEAD)
    Log "[start] worktree=$wt head=$head model=$Model"

    $claude = Get-Command claude -ErrorAction SilentlyContinue
    if (-not $claude) { Log '[exit] claude not on PATH'; exit 1 }

    $prompt = 'Follow generator/CLAUDE_RUN.md in this directory exactly. Today is ' + (Get-Date -Format 'yyyy-MM-dd') + '. This run is unattended: never ask questions, make the reasonable choice and note it in the report.'
    $promptFile = Join-Path $logDir "$stamp.prompt.txt"
    $stdoutFile = Join-Path $logDir "$stamp.stdout.jsonl"
    $stderrFile = Join-Path $logDir "$stamp.stderr.txt"
    Set-Content -LiteralPath $promptFile -Value $prompt -Encoding ASCII
    $tools = 'Read,Edit,Write,Glob,Grep,WebFetch,WebSearch,Agent,Bash(python:*),Bash(git pull:*),Bash(git status:*),Bash(git log:*),Bash(git diff:*)'
    $argList = @('-p', '--model', $Model, '--allowedTools', ('"' + $tools + '"'),
                 '--permission-mode', 'acceptEdits', '--max-turns', "$MaxTurns",
                 '--output-format', 'stream-json', '--verbose')
    if ($DryRun) { Log ("[dry-run] " + $claude.Source + ' ' + ($argList -join ' ')); $rc = 0; exit 0 }

    $proc = Start-Process -FilePath $claude.Source -ArgumentList $argList -WorkingDirectory $wt `
              -RedirectStandardInput $promptFile -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile `
              -NoNewWindow -PassThru
    $null = $proc.Handle   # PS 5.1: keep the handle so ExitCode is not $null later
    Log "[pid] $($proc.Id)"
    $proc.WaitForExit()
    $rc = $proc.ExitCode

    # The final RESULT line comes from the session's report (CLAUDE_RUN.md).
    $result = Select-String -LiteralPath $stdoutFile -Pattern 'RESULT: (COMMITTED|NONE)[^"\\]*' -AllMatches -ErrorAction SilentlyContinue |
              ForEach-Object { $_.Matches } | Select-Object -Last 1
    $cost = Select-String -LiteralPath $stdoutFile -Pattern '"total_cost_usd":\s*([0-9.]+)' -ErrorAction SilentlyContinue | Select-Object -Last 1
    Log ("[exit] rc=$rc " + $(if ($result) { $result.Value } else { 'RESULT: (none found)' }) + $(if ($cost) { ' cost_usd_equiv=' + $cost.Matches[0].Groups[1].Value } else { '' }))
} catch {
    Log "[exception] $($_.Exception.Message)"
    $rc = 999
} finally {
    Remove-Item -LiteralPath $lock -ErrorAction SilentlyContinue
}
exit $rc
