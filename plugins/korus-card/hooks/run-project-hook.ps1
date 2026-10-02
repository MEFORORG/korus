<#
.SYNOPSIS
    SessionStart shim for the korus-card plugin. Runs the PROJECT's own copy of one hook script,
    or does nothing.

.DESCRIPTION
    POSTURE: FAILS OPEN, AND NEVER BLOCKS. Every path exits 0. A SessionStart hook that can break a
    session is a worse fault than a missing card.

    WHY A SHIM AND NOT A COPY. The plugin ships no copy of role-card-inject.ps1 or
    precompact-reprime.ps1. A copy drifts from the scripts it was taken from, and nothing reports
    the drift. So this shim finds the scripts in the repository the session runs in, and runs
    those.

    IT STAYS SILENT IN THREE CASES, IN THIS ORDER.

      1. The repository has not opted in to KORUS: no ccx.config.json at its root. A user-scope
         install fires in every repository on the machine. docs/HOOKS.md, "State the cost of an
         always-on hook", says to gate a user-global hook on that file, not on script presence.
      2. The repository has no scripts/hooks/<script>. There is nothing of its own to run.
      3. A settings file already runs the same script at SessionStart. The project's own wiring
         wins, and this shim stands down, so the card is not injected twice.

    CASE 3 READS AT LEAST THESE FILES: .claude/settings.json and .claude/settings.local.json under
    both $env:CLAUDE_PROJECT_DIR and the repository root, and the user settings.json in
    $env:CLAUDE_CONFIG_DIR, or in ~/.claude when that is unset. Managed settings are not read.

    WHAT COUNTS AS WIRING. A SessionStart command counts when it names the script's file name as a
    whole path segment, and one of these holds:

      - it names no directory, as a user-scope shim does when it resolves the script at run time;
      - its directory holds a variable ($, %, or a leading ~) this shim cannot expand, so it is
        taken on trust;
      - its path, resolved against the repository root when relative, is a file that exists.

    A row still holding the example's REPLACE_WITH_ABSOLUTE_PATH_TO_YOUR_CHECKOUT placeholder does
    not count, and nor does an absolute path to a checkout that is gone. Both run nothing, so
    standing down for them would leave the session with no card at all.

    IT ADDS NO GUARD OF ITS OWN. precompact-reprime.ps1 decides for itself whether this start is a
    compaction restart. A second guard here could disagree with that one, and whichever was wrong
    would be silent.

.PARAMETER Script
    The file name under scripts/hooks/ to run. Only the two names the plugin wires are accepted.
    Anything else is a no-op, not an error.
#>

[CmdletBinding()]
param(
    [string] $Script
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Allowed = @('role-card-inject.ps1', 'precompact-reprime.ps1')
$Placeholder = 'REPLACE_WITH_ABSOLUTE_PATH_TO_YOUR_CHECKOUT'

function Test-CommandRuns {
    # True when $Command runs the script $Name. See WHAT COUNTS AS WIRING above.
    param([string] $Command, [string] $Name, [string[]] $Roots)
    if ($Command.IndexOf($Placeholder, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) { return $false }
    # The directory token may hold quotes, as in "$CLAUDE_PROJECT_DIR"/scripts/hooks/<name>. They
    # are stripped before the checks below.
    $pattern = '(?<![\w.-])(?<dir>[^\s`;|&()<>]*?)' + [regex]::Escape($Name) + '(?![\w.-])'
    foreach ($m in [regex]::Matches($Command, $pattern, 'IgnoreCase')) {
        $dir = $m.Groups['dir'].Value -replace '["'']', ''
        if (-not $dir) { return $true }
        if (-not ($dir.EndsWith('/') -or $dir.EndsWith('\'))) { continue }
        # A leading ~ is a home directory. A ~ inside a path is an 8.3 short name, which can resolve.
        if ($dir -match '[$%]' -or $dir.StartsWith('~')) { return $true }
        $path = $dir + $Name
        if ([System.IO.Path]::IsPathRooted($path)) {
            if (Test-Path -LiteralPath $path -PathType Leaf) { return $true }
            continue
        }
        # Relative: the harness runs a row from the session's directory, and a user-scope shim
        # usually joins it to the repository root. Either one existing counts.
        foreach ($base in $Roots) {
            if (Test-Path -LiteralPath (Join-Path $base $path) -PathType Leaf) { return $true }
        }
    }
    return $false
}

function Test-Wired {
    # True when the settings file at $Path runs $Name at SessionStart.
    param([string] $Path, [string] $Name, [string[]] $Roots)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    $text = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
    if (-not $text) { return $false }
    try {
        $settings = $text | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        # A settings file that does not parse cannot be read by event, so read its raw text.
        # Standing down on a mention is the cheaper error: a doubled card puts the same rules in
        # context twice, and the harness may not load a file it cannot parse either.
        return (Test-CommandRuns -Command $text -Name $Name -Roots $Roots)
    }
    if ($null -eq $settings -or -not $settings.PSObject.Properties['hooks']) { return $false }
    $hooks = $settings.hooks
    if ($null -eq $hooks -or -not $hooks.PSObject.Properties['SessionStart']) { return $false }
    foreach ($group in @($hooks.SessionStart)) {
        if ($null -eq $group -or -not $group.PSObject.Properties['hooks']) { continue }
        foreach ($hook in @($group.hooks)) {
            if ($null -eq $hook -or -not $hook.PSObject.Properties['command']) { continue }
            if (Test-CommandRuns -Command ([string]$hook.command) -Name $Name -Roots $Roots) { return $true }
        }
    }
    return $false
}

try {
    # Stdin is read as BYTES. Console.In decodes with the console input code page, so a non-ASCII
    # cwd would reach the child altered. The bytes go to the child unchanged, and are decoded as
    # UTF-8 only for this shim's own read of the cwd.
    $utf8 = [System.Text.UTF8Encoding]::new($false)
    $bytes = [byte[]]@()
    try {
        $buffer = [System.IO.MemoryStream]::new()
        [Console]::OpenStandardInput().CopyTo($buffer)
        $bytes = $buffer.ToArray()
    }
    catch { }
    $raw = $utf8.GetString($bytes)

    if ($Allowed -notcontains $Script) { exit 0 }

    # ------------------------------------------------------------------ which repository is this
    $start = $env:CLAUDE_PROJECT_DIR
    if (-not $start -and $raw) {
        try {
            $payload = $raw | ConvertFrom-Json -ErrorAction Stop
            if ($payload -and $payload.PSObject.Properties['cwd'] -and $payload.cwd) {
                $start = [string]$payload.cwd
            }
        }
        catch { }
    }
    if (-not $start) { $start = $PWD.Path }
    if (-not (Test-Path -LiteralPath $start -PathType Container)) { exit 0 }

    # A machine with no git still gets a card at the top of a repository; it only loses the walk
    # up from a subdirectory.
    $root = $start
    try {
        $top = (& git -C $start rev-parse --path-format=absolute --show-toplevel 2>$null)
        if ($LASTEXITCODE -eq 0 -and $top) { $root = ([string]$top).Trim() }
    }
    catch { }

    # ------------------------------------------------------------------- the three silent cases
    if (-not (Test-Path -LiteralPath (Join-Path $root 'ccx.config.json') -PathType Leaf)) { exit 0 }

    $target = Join-Path (Join-Path $root 'scripts/hooks') $Script
    if (-not (Test-Path -LiteralPath $target -PathType Leaf)) { exit 0 }

    $settingsFiles = [System.Collections.Generic.List[string]]::new()
    foreach ($dir in @($start, $root)) {
        foreach ($leaf in @('.claude/settings.json', '.claude/settings.local.json')) {
            $file = Join-Path $dir $leaf
            if (-not $settingsFiles.Contains($file)) { $settingsFiles.Add($file) }
        }
    }
    $configDir = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR }
                 elseif ($HOME) { Join-Path $HOME '.claude' }
                 else { $null }
    if ($configDir) { $settingsFiles.Add((Join-Path $configDir 'settings.json')) }

    foreach ($file in $settingsFiles) {
        try {
            if (Test-Wired -Path $file -Name $Script -Roots @($start, $root)) { exit 0 }
        }
        catch {
            # An unreadable file is not evidence of wiring. Keep looking.
        }
    }

    # ------------------------------------------------------------------------ run the real one
    # The same pwsh that runs this shim, so a machine with two installs does not switch between
    # them. The payload is written byte for byte: a pipe would append a newline, and turn an empty
    # stdin into one.
    $psi = [System.Diagnostics.ProcessStartInfo]::new((Get-Process -Id $PID).Path)
    foreach ($arg in @('-NoProfile', '-File', $target)) { $psi.ArgumentList.Add($arg) }
    $psi.WorkingDirectory = $root
    $psi.UseShellExecute = $false
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = $utf8
    $psi.StandardErrorEncoding = $utf8

    $child = [System.Diagnostics.Process]::Start($psi)
    $stderr = $child.StandardError.ReadToEndAsync()
    $child.StandardInput.BaseStream.Write($bytes, 0, $bytes.Length)
    $child.StandardInput.Close()
    $stdout = $child.StandardOutput.ReadToEndAsync()
    # Bounded below the row's 30-second timeout, so a hung child ends here and not in the harness.
    if (-not $child.WaitForExit(25000)) {
        try { $child.Kill($true) } catch { }
        throw "scripts/hooks/$Script did not finish within 25 seconds"
    }
    $text = $stdout.Result
    $errText = $stderr.Result
    if ($errText) { [Console]::Error.Write($errText) }
    if (-not $text -and $child.ExitCode -ne 0) {
        $text = "[korus-card] scripts/hooks/$Script exited $($child.ExitCode) and printed nothing."
    }

    if ($text) {
        try { [Console]::OutputEncoding = $utf8 } catch { }
        [Console]::Out.Write($text)
    }
    exit 0
}
catch {
    # Fail open. Say so, because a silent fault here reads exactly like a repository with no card.
    [Console]::Out.Write("[korus-card] The plugin shim failed and ran nothing: $($_.Exception.Message)")
    exit 0
}
