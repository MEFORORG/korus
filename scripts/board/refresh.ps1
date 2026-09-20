<#
.SYNOPSIS
  Rebuild the Lander Board: collect, derive, render. One command, PowerShell 7.

.DESCRIPTION
  The three steps stay separate on purpose (LANDER-BOARD.md section 9): a failed collect leaves
  the last good data.json in place, and the render still produces a board rather than an error.
  This script runs them in order and STOPS at the first failure, so a half-rebuilt board is
  never published.

  It does NOT publish. Publishing an artifact needs a Claude session, so the script prints the
  file to publish and the URL to publish it to, and the session does that step.

  Nothing here schedules anything. A session cron does not fire while the session is busy
  (section 9a), so the cadence is the Watchdog session's own loop.

.PARAMETER OutDir
  Where data.json, series.json and board.html are written. Defaults to a `.board` folder beside
  this script, which is git-ignored. Pass a scratchpad path to keep the repository clean.

.PARAMETER SkipCollect
  Re-derive and re-render from the data.json already in OutDir, without calling GitHub. Use it
  when you changed series.py, build.py or template.html and the data is still fresh.

.EXAMPLE
  pwsh -NoProfile -File scripts/board/refresh.ps1
.EXAMPLE
  pwsh -NoProfile -File scripts/board/refresh.ps1 -OutDir $env:TEMP\board -SkipCollect
#>
[CmdletBinding()]
param(
    [string] $OutDir,
    [switch] $SkipCollect
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $OutDir) { $OutDir = Join-Path $here '.board' }
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Force $OutDir | Out-Null }
$OutDir = (Resolve-Path $OutDir).Path

$python = (Get-Command python -ErrorAction SilentlyContinue)?.Source
if (-not $python) { throw 'refresh.ps1: python is not on PATH.' }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'refresh.ps1: gh is not on PATH.' }

# The scripts read and write beside themselves unless told otherwise.
$env:LANDER_BOARD_OUT = $OutDir

$steps = @()
if (-not $SkipCollect) { $steps += 'collect.py' }
$steps += 'series.py'
$steps += 'build.py'

foreach ($step in $steps) {
    Write-Host "== $step" -ForegroundColor Cyan
    & $python (Join-Path $here $step)
    if ($LASTEXITCODE -ne 0) {
        # collect.py refuses rather than writing a reading it cannot trust. Stopping here is the
        # designed outcome, not a crash: the last good board stays up and stays honest.
        throw "refresh.ps1: $step exited $LASTEXITCODE. The board was NOT rebuilt; the previous $OutDir\board.html still stands."
    }
}

$board = Join-Path $OutDir 'board.html'
if (-not (Test-Path $board)) { throw "refresh.ps1: $board was not produced." }

Write-Host ''
Write-Host "Board rebuilt: $board" -ForegroundColor Green
Write-Host 'Publish it from the Claude session with the Artifact tool:' -ForegroundColor Green
Write-Host "  file_path = $board"
Write-Host '  url       = the URL in LANDER-BOARD.md section 9b, so the link stays stable'
