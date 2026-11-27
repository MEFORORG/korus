<#
.SYNOPSIS
  Copy the board.html a refresh built to the owner's lander.html, without ever losing the old one.

.DESCRIPTION
  PowerShell 7 or later. Run it on the owner's PC only, after refresh.ps1 exited zero
  (LANDER-BOARD.md section 9b). It does the copy and nothing else: it never refreshes, so the
  artifact and lander.html carry one build.

  The dashboard folder is named by the engine's scripts/dashboard/render_html.py, the one place
  that decides it. The script extracts that folder from origin/main of an engine checkout into a
  temp directory, the way section 9b step 1 extracts scripts/board, and runs it with python -I.
  No working tree's copy runs.

  The old lander.html survives every failure: the new file is copied to a unique temp name in the
  folder and replaced with a three-argument File.Move, which overwrites only on success. Old
  lander.*.tmp files, left by a killed run, are cleared first and a failure to clear one is a
  warning, not an error.

.PARAMETER BoardHtml
  The board.html a refresh built.

.PARAMETER EngineCheckout
  An engine checkout. Only its origin/main is read, and it is fetched first.

.PARAMETER ExpectedHost
  The machine that may copy. Any other machine throws and copies nothing.

.EXAMPLE
  pwsh -NoProfile -File scripts/board/copy-to-dashboard.ps1 -BoardHtml $out\board.html -EngineCheckout D:\Code\MessageFoundry
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $BoardHtml,
    [Parameter(Mandatory)] [string] $EngineCheckout,
    [string] $ExpectedHost = 'MEFORDEV01'
)

if ([Environment]::MachineName -ne $ExpectedHost) {
    & { $ErrorActionPreference = 'Stop'; throw "STOP     this must run on $ExpectedHost, but this is $([Environment]::MachineName); nothing ran" }
}

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'copy-to-dashboard.ps1: PowerShell 7 or later is required.' }
if (-not (Test-Path -LiteralPath $BoardHtml -PathType Leaf)) { throw "copy-to-dashboard.ps1: $BoardHtml does not exist." }

$scratch = $null
try {
    git -C $EngineCheckout fetch origin main
    if ($LASTEXITCODE -ne 0) { throw 'copy-to-dashboard.ps1: git fetch failed; nothing copied.' }
    $scratch = Join-Path ([IO.Path]::GetTempPath()) "board-copy-$([guid]::NewGuid().ToString('N'))"
    New-Item -ItemType Directory -Path $scratch | Out-Null
    $tar = Join-Path $scratch 'dash.tar'
    git -C $EngineCheckout archive --format=tar -o $tar origin/main scripts/dashboard
    if ($LASTEXITCODE -ne 0) { throw 'copy-to-dashboard.ps1: git archive failed; nothing copied.' }
    # A relative archive name, run from inside the folder: GNU tar reads "C:" in a path as a host.
    Push-Location -LiteralPath $scratch
    try { tar -x -f dash.tar } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw 'copy-to-dashboard.ps1: tar failed; nothing copied.' }
    # The helper prints the folder as UTF-8; read it as UTF-8, not through the console code page.
    $prevEncoding = [Console]::OutputEncoding
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    try { $DashboardDir = (python -I -X utf8 (Join-Path $scratch 'scripts/dashboard/render_html.py') --print-out-dir) }
    finally { [Console]::OutputEncoding = $prevEncoding }
    if ($LASTEXITCODE -ne 0 -or -not $DashboardDir) { throw 'copy-to-dashboard.ps1: no dashboard folder; nothing copied.' }
    if (-not (Test-Path -LiteralPath $DashboardDir -PathType Container)) {
        New-Item -ItemType Directory -Path $DashboardDir | Out-Null
    }

    foreach ($old in Get-ChildItem -LiteralPath $DashboardDir -Filter 'lander.*.tmp') {
        try { Remove-Item -LiteralPath $old.FullName } catch { Write-Warning "old temp file left: $($old.FullName)" }
    }

    $tmp = Join-Path $DashboardDir "lander.$([guid]::NewGuid().ToString('N')).tmp"
    try {
        Copy-Item -LiteralPath $BoardHtml -Destination $tmp
        [System.IO.File]::Move($tmp, (Join-Path $DashboardDir 'lander.html'), $true)
    } finally {
        if (Test-Path -LiteralPath $tmp) {
            try { Remove-Item -LiteralPath $tmp } catch { Write-Warning "temp file left: $tmp" }
        }
    }
    Write-Host "copied $BoardHtml -> $(Join-Path $DashboardDir 'lander.html')"
} finally {
    if ($scratch -and (Test-Path -LiteralPath $scratch)) {
        Remove-Item -LiteralPath $scratch -Recurse -Force -ErrorAction SilentlyContinue
    }
}
