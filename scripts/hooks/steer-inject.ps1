# PreToolUse hook: deliver a queued steering note mid-task.
#
# POSTURE: FAILS OPEN. Any error here exits 0 and must never block a tool call.
#
# Workaround for the absence of any supported way to reach a session between tool calls: a message
# typed at the prompt is queued for AFTER the current turn ends, which can be a long time and a lot
# of wasted work away. If a note is waiting at <project>\.claude\steer.txt -- dropped there by
# bin/ccx-steer.ps1 from a second terminal -- it is read, deleted, and re-emitted as
# `additionalContext`, so the session sees it at the next tool-call boundary rather than at the end
# of the turn.
#
# OPT-IN, and deliberately not registered in the shared .claude/settings.json: a PreToolUse hook on
# `*` costs a pwsh process spawn before EVERY tool call (measured ~366ms on the machine this was
# developed on, of which ~267ms is bare pwsh startup and unavoidable). That is a standing tax on
# every session in every worktree, which is a bad trade for an occasional-use feature. Enable it per
# worktree, in that worktree's .claude/settings.local.json, when you actually want it. See
# docs/STEERING.md.
#
# ASCII-only on purpose (the note is written by another process and must not depend on console
# encoding); run under pwsh 7 by the hook.
#
# WHICH WORKTREE: THE ONE THE HOOK INPUT NAMES. bin/ccx-steer.ps1, run from a terminal in the
# session's worktree, writes <worktree>\.claude\steer.txt. Measured 2026-10-12: the desktop app starts
# a worktree session's CLI with `--project-config-root <primary checkout>`, and CLAUDE_PROJECT_DIR then
# names the PRIMARY, so this hook read a file nobody wrote. It now walks up from the `cwd` in the JSON
# on stdin, and falls back to CLAUDE_PROJECT_DIR only when the input names no cwd at all.
#
# BUT ONLY A CWD IN THE PROJECT'S OWN CLONE. This hook DELETES the note it delivers, and delivers it as
# text the user typed. The korus#223 review measured it reading and deleting steer.txt in another
# repository, beside a bare `.git` file, and in a sibling's worktree after a `cd`. _hookinput.ps1 holds
# the rules that now refuse each of those, with or without a pin.
#
# A REFUSAL READS NOTHING. A cwd the helper refuses, input still open when the read gave up, or a
# helper that is missing or throws, leaves the hook unable to tell whose note is under
# CLAUDE_PROJECT_DIR: the primary's, under the desktop app.
# Delivering and deleting it would hand one session another's note, so the hook reads none and says
# why on stderr. That is not the chat, because this hook runs before every tool call.

$ErrorActionPreference = 'SilentlyContinue'

try {
    $root = ''
    try {
        $helper = Join-Path $PSScriptRoot '_hookinput.ps1'
        if (-not (Test-Path -LiteralPath $helper -PathType Leaf)) { throw "scripts/hooks/_hookinput.ps1 is missing" }
        . $helper
        $startDir = if ($env:CLAUDE_PROJECT_DIR) { $env:CLAUDE_PROJECT_DIR } else { $PWD.Path }
        # Read-only: this runs before every tool call; the SessionStart hooks write the pin.
        $wt = Resolve-CcxHookSession -Text (Read-CcxHookInput) -StartDir $startDir -ReadOnly
        if ($wt.Root) { $root = $wt.Root }
        elseif ($wt.Reason) { throw $wt.Reason }
    } catch {
        [Console]::Error.WriteLine("[steer-inject] $($_.Exception.Message), so no steering note was read.")
        exit 0
    }
    # The input named no cwd and no pin answered: an older harness, or a hand run. The old
    # behaviour stands.
    if (-not $root) { $root = $env:CLAUDE_PROJECT_DIR }
    if (-not $root) { exit 0 }

    $noteFile = Join-Path $root ".claude\steer.txt"
    if (-not (Test-Path -LiteralPath $noteFile)) { exit 0 }

    $note = Get-Content -LiteralPath $noteFile -Raw
    Remove-Item -LiteralPath $noteFile -Force

    if ([string]::IsNullOrWhiteSpace($note)) { exit 0 }
    $note = $note.Trim()

    $context = "[STEERING NOTE -- the user just typed this via a side channel while you were mid-task, not through the normal prompt queue. Read it now and act on it right away -- adjust your current work accordingly before or alongside your next step. Do not wait for the current turn to end.]: $note"

    $payload = [pscustomobject]@{
        hookSpecificOutput = [pscustomobject]@{
            hookEventName     = 'PreToolUse'
            additionalContext = $context
        }
    }
    [Console]::Out.Write(($payload | ConvertTo-Json -Compress -Depth 6))
} catch {
    exit 0
}
exit 0
