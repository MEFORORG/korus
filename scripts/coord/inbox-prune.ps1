#Requires -Version 7.3
<#
.SYNOPSIS
    Delete the korus-inbox plugin's spent files: ended, or untouched for 24 hours. A dry run unless
    -Apply is passed.

.DESCRIPTION
    The korus-inbox plugin writes one JSON file per session to <USERPROFILE or HOME>/.korus-inbox.
    Its file API has no delete, so a session that ends overwrites its file with `ended: true` and
    the file stays. This script removes those, and any file nobody has written for 24 hours.

        pwsh -NoProfile -File scripts/coord/inbox-prune.ps1            # list what would go
        pwsh -NoProfile -File scripts/coord/inbox-prune.ps1 -Apply     # delete it

    A file is deleted when its name has the shape the plugin writes, `<session id>.json`, and one
    of these holds:

        - it was last written more than 24 hours ago. Every reader already ignores such a file;
        - it parses as `korus-inbox/1` with `ended: true`.

    WHAT IT NEVER TOUCHES. Anything outside the folder: it lists the folder's own files and does not
    recurse. A link, whose target may sit anywhere. A file of any other name. A folder whose last
    segment is not `.korus-inbox`, which it refuses outright, -Apply or not, so a mistyped -Folder
    cannot point it at another directory.

    A LIVE SESSION CAN WRITE BETWEEN THE READ AND THE DELETE. So the file's write time is read again
    just before the delete, and a file that changed is kept. A live session rewrites its file at
    least every ten minutes while it holds an entry, so the 24-hour rule cannot catch a live one.

    Exit 0 when the run finished, dry or applied. Exit 1 when a delete failed. Exit 2 when it
    refused the folder or found no home folder.
#>
[CmdletBinding()]
param(
    # The inbox folder. Defaults to <USERPROFILE or HOME>/.korus-inbox. Its last segment must be
    # `.korus-inbox`.
    [string]$Folder,
    # Delete. Without it the run only lists.
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$FolderName = '.korus-inbox'
$Format = 'korus-inbox/1'
$MaxAge = [TimeSpan]::FromHours(24)
# The plugin's own session-id rule, so a file it could not have written is left alone.
$InboxFile = '^[A-Za-z0-9_-]{1,100}\.json$'
# The plugin reads no file larger than this, so neither does the ended check.
$MaxBytes = 256KB

if (-not $Folder) {
    $homeDir = if ($env:USERPROFILE) { $env:USERPROFILE } elseif ($env:HOME) { $env:HOME } else { $null }
    if (-not $homeDir) {
        [Console]::Error.WriteLine('inbox-prune: no home folder in USERPROFILE or HOME; pass -Folder')
        exit 2
    }
    $Folder = Join-Path $homeDir $FolderName
}

$trimmed = $Folder.TrimEnd('\', '/')
if ((Split-Path -Leaf $trimmed) -cne $FolderName) {
    [Console]::Error.WriteLine("inbox-prune: refused: $Folder is not a folder named $FolderName")
    exit 2
}
if (-not (Test-Path -LiteralPath $trimmed -PathType Container)) {
    Write-Output "inbox-prune: nothing to do: $trimmed does not exist"
    exit 0
}
$dir = Get-Item -LiteralPath $trimmed -Force
if ($dir.Attributes -band [IO.FileAttributes]::ReparsePoint) {
    [Console]::Error.WriteLine("inbox-prune: refused: $trimmed is a link, so its files may sit anywhere")
    exit 2
}

function Get-SpentReason {
    param([IO.FileInfo]$File, [datetime]$NowUtc)
    if ($NowUtc - $File.LastWriteTimeUtc -gt $MaxAge) { return 'not written for 24 hours' }
    if ($File.Length -gt $MaxBytes) { return $null }
    try {
        # -NoEnumerate keeps a one-item array an array, so it is not read as the object inside it.
        $body = Get-Content -LiteralPath $File.FullName -Raw -ErrorAction Stop |
            ConvertFrom-Json -NoEnumerate -ErrorAction Stop
    } catch {
        # A file caught half-written does not parse. It is kept, and the age rule takes it later.
        return $null
    }
    if ($body -isnot [pscustomobject]) { return $null }
    # Matched case-sensitively, as the plugin's JSON.parse reads them: "ENDED" is not "ended".
    $props = @($body.PSObject.Properties)
    $formatProp = @($props | Where-Object { $_.Name -ceq 'format' })
    $endedProp = @($props | Where-Object { $_.Name -ceq 'ended' })
    if ($formatProp.Count -eq 1 -and $formatProp[0].Value -is [string] -and $formatProp[0].Value -ceq $Format -and
        $endedProp.Count -eq 1 -and $endedProp[0].Value -is [bool] -and $endedProp[0].Value) {
        return 'ended'
    }
    return $null
}

$nowUtc = [datetime]::UtcNow
$files = @(Get-ChildItem -LiteralPath $trimmed -File -Force | Sort-Object Name)
$spent = 0
$deleted = 0
$failed = 0
foreach ($file in $files) {
    if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        Write-Output "keep    $($file.Name): a link"
        continue
    }
    if ($file.Name -cnotmatch $InboxFile) {
        Write-Output "keep    $($file.Name): not a file the plugin writes"
        continue
    }
    try {
        $reason = Get-SpentReason -File $file -NowUtc $nowUtc
    } catch {
        # One odd file must not stop the run halfway, with some files deleted and the rest unread.
        Write-Output "keep    $($file.Name): could not be read ($($_.Exception.Message))"
        continue
    }
    if (-not $reason) { continue }
    $spent++
    if (-not $Apply) {
        Write-Output "would delete $($file.Name): $reason"
        continue
    }
    $written = $file.LastWriteTimeUtc
    $file.Refresh()
    if (-not $file.Exists -or $file.LastWriteTimeUtc -ne $written) {
        Write-Output "keep    $($file.Name): written again since it was read"
        continue
    }
    try {
        Remove-Item -LiteralPath $file.FullName -Force -ErrorAction Stop
        $deleted++
        Write-Output "deleted $($file.Name): $reason"
    } catch {
        $failed++
        [Console]::Error.WriteLine("inbox-prune: could not delete $($file.Name): $($_.Exception.Message)")
    }
}

if ($Apply) {
    Write-Output "inbox-prune: $trimmed -- $($files.Count) files read, $deleted deleted, $failed failed"
} else {
    Write-Output "inbox-prune: $trimmed -- $($files.Count) files read, $spent would be deleted. Dry run: pass -Apply to delete."
}
if ($failed -gt 0) { exit 1 }
exit 0
