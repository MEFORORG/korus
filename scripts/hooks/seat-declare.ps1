#Requires -Version 7.0
<#
.SYNOPSIS
    UserPromptSubmit hook. Treats a prompt that is EXACTLY a roster label as a seat declaration,
    writes the marker, and loads that seat's card in the same turn.

.DESCRIPTION
    WHAT THIS EXISTS FOR. `role-card-inject.ps1` loads a card at SessionStart when a marker already
    exists. `scripts/coord/seat.ps1 -Declare` writes that marker. Nothing connected them, so a
    harness-created worktree was born seatless: the seat arrived as an ordinary chat turn, and the
    card never loaded for the session that had actually been told its seat. Measured on this
    repository 2026-09-19 -- a session was told `special`, held the seat for its whole run, and no
    card was ever injected.

    THE RULE, AND IT IS NARROW. A prompt whose WHOLE text is a roster label is a DECLARATION. A
    prompt that merely mentions one is not. `special` declares. `claude/special-d4c4b4`,
    `special seat`, and `I think the special seat should handle this` all do nothing at all.

    WHY THAT IS NOT THE GUESS THE SUBSYSTEM REFUSES. `role-card-inject.ps1` will not read a branch
    or directory name, because those are creation-time labels that nothing keeps current -- this
    repository has a worktree whose name describes a question its session answered in two minutes.
    A prompt is different in the one way that matters: the user typed it THIS TURN, on purpose, as
    the entire content of their message. Owner ruling 2026-09-19 drew the line there.

    This hook therefore reads no ref, and `TheHookReadsNoRef` in tests/test_seat_declaration.py
    fails on source containing `rev-parse`, `symbolic-ref`, `git branch` or `--show-current`.

    THE EXPLICIT FORM IS LOUDER THAN THE BARE ONE. `/seat lander` was unmistakably aimed at this
    hook, so an unmatched label there gets a refusal and the roster. A bare unmatched word was
    probably just a word, so it gets silence. Being chatty on ordinary turns is how a hook's real
    output stops being read.

    IT WRITES THE MARKER, NEVER THE GOAL. `docs/ROLE-CARDS.md` states the split: the marker carries
    the role, which a machine can write, and not the goal, which no machine can. A session that
    needs to be visible to its peers still runs `scripts/coord/seat.ps1 -Declare -Seat <seat>
    -Goal "<one line>"`, and the `/seat` skill does exactly that.

    IT ALWAYS EXITS 0. A UserPromptSubmit hook that fails can block the user's prompt outright.

.PARAMETER WorktreeRoot
    The worktree whose marker this sets. Defaults to the current directory. Tests pass a temporary
    root; a real session never passes this.
#>

[CmdletBinding()]
param(
    [string] $WorktreeRoot = $PWD.Path
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$MarkerRelPath = '.claude/seat.local.txt'

function Write-Note {
    param([string] $Text)
    # Plain stdout, the shape this repository has exercised at UserPromptSubmit. See
    # docs/ROLE-CARDS.md, "The one thing still unproven", for why no additionalContext is emitted.
    Write-Output $Text
}

try {
    # ------------------------------------------------------------------------ read the user's turn
    $stdin = ''
    try { $stdin = [Console]::In.ReadToEnd() } catch { $stdin = '' }
    if ([string]::IsNullOrWhiteSpace($stdin)) { exit 0 }

    $prompt = $null
    try {
        $payload = $stdin | ConvertFrom-Json
        if ($payload.PSObject.Properties.Name -contains 'prompt') { $prompt = [string]$payload.prompt }
    }
    catch {
        # Malformed stdin is not this hook's problem to report. Silence, and the turn proceeds.
        exit 0
    }
    if ([string]::IsNullOrWhiteSpace($prompt)) { exit 0 }

    # --------------------------------------------------------------- is this shaped like a label?
    $text = $prompt.Trim()

    # The explicit form. `/seat lander` and `seat: lander` both aim at this hook deliberately, so an
    # unmatched label below gets a refusal rather than the silence a bare word gets.
    $explicit = $false
    if ($text -match '^(?i)/seat\s+(.+)$') { $explicit = $true; $text = $Matches[1].Trim() }
    elseif ($text -match '^(?i)seat:\s*(.+)$') { $explicit = $true; $text = $Matches[1].Trim() }

    # EXACTNESS IS THE WHOLE RULE. Anything with inner whitespace is prose, not a declaration, and
    # this single test is what separates the widening from the guess it must not become.
    if ($text -match '\s') { exit 0 }
    if ([string]::IsNullOrWhiteSpace($text)) { exit 0 }

    $label = $text.ToLowerInvariant()

    # --------------------------------------------------------------------------- resolve the label
    $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $seatsPath = Join-Path $repoRoot 'docs/roles/seats.json'
    if (-not (Test-Path -LiteralPath $seatsPath)) {
        if ($explicit) { Write-Note "[seat] No roster at docs/roles/seats.json, so nothing was declared." }
        exit 0
    }
    $seats = Get-Content -LiteralPath $seatsPath -Raw | ConvertFrom-Json

    $canonical = $null
    if ($seats.live -contains $label) {
        $canonical = $label
    }
    elseif ($seats.aliases.PSObject.Properties.Name -contains $label) {
        $canonical = $seats.aliases.$label
    }

    # A retired label ALWAYS speaks, explicit or not. Silence would send the reader looking for a
    # card that was deliberately removed, and it must never reach the marker.
    if (-not $canonical -and ($seats.retired.PSObject.Properties.Name -contains $label)) {
        Write-Note @"
[seat] '$label' IS A RETIRED SEAT. Nothing was declared and no card was injected.

$($seats.retired.$label)

Its playbook stays in roles/retired/ as the record of what the seat did.
Live seats: $($seats.live -join ', ').
"@
        exit 0
    }

    if (-not $canonical) {
        if ($explicit) {
            Write-Note @"
[seat] '$label' MATCHES NO SEAT, so nothing was declared and nothing was guessed.

Live seats: $($seats.live -join ', ').
If '$label' is a spelling of one of those, add it to the aliases map in docs/roles/seats.json.
"@
        }
        # A bare unmatched word was probably just a word. Silence.
        exit 0
    }

    # ------------------------------------------------------------- already set? then say nothing
    $markerPath = Join-Path $WorktreeRoot $MarkerRelPath
    $previous = $null
    if (Test-Path -LiteralPath $markerPath) {
        $previous = (Get-Content -LiteralPath $markerPath -Raw -ErrorAction SilentlyContinue)
        if ($previous) { $previous = $previous.Trim().ToLowerInvariant() }
    }
    if ($previous -eq $canonical) { exit 0 }

    # ------------------------------------------------------------------------- write the marker
    $markerDir = Split-Path -Parent $markerPath
    if (-not (Test-Path -LiteralPath $markerDir)) {
        $null = New-Item -ItemType Directory -Path $markerDir -Force
    }
    Set-Content -LiteralPath $markerPath -Value $canonical -Encoding utf8NoBOM -NoNewline

    if ($previous) {
        Write-Note "[seat] SEAT CHANGED: '$previous' -> '$canonical'. The marker at $MarkerRelPath was rewritten, and the new card follows."
    }
    else {
        Write-Note "[seat] SEAT DECLARED: '$canonical', from a prompt that was exactly that label. The marker at $MarkerRelPath now holds it, so it survives a compaction and every later session in this worktree."
    }

    # ------------------------------------------------- load the card NOW, not at the next start
    # This is the gap the hook exists to close. Reusing the injector rather than reimplementing it
    # keeps one resolver, one cap check and one copy-writer.
    $injector = Join-Path $PSScriptRoot 'role-card-inject.ps1'
    if (Test-Path -LiteralPath $injector) {
        # No stdin redirect here. `<` is a reserved operator in PowerShell and is a parse error,
        # and none is needed: this hook has already read stdin to EOF, so the injector's own
        # ReadToEnd returns immediately.
        & $injector -WorktreeRoot $WorktreeRoot
    }
    else {
        Write-Note "[seat] role-card-inject.ps1 is missing from this checkout, so the marker is set and NO card was injected."
    }

    Write-Note @"
[seat] The marker carries the ROLE. It does not carry the GOAL, which no machine can write.
If this seat will write to a tracked path, push, or hold a shared resource, declare it to the fleet:

    pwsh -NoProfile -File scripts/coord/seat.ps1 -Declare -Seat $canonical -Goal "<one line>"
"@
    exit 0
}
catch {
    # Never fail a turn. A missed declaration is a far smaller fault than a blocked prompt.
    Write-Output "[seat] The seat-declaration hook failed and was skipped: $($_.Exception.Message)"
    exit 0
}
