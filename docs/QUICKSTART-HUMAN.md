# Install KORUS and test a blocked edit

Install KORUS in a repository you already use, then test it with two Claude Code sessions.
The final test asks both sessions to edit one file and checks that KORUS blocks the second edit.

You need Claude Code for Desktop, PowerShell (`pwsh`) 7.3 or newer, Git, and `python` on `PATH`.
[Limits and requirements](LIMITS.md) lists platform support and what breaks when a tool is missing.

**Run the setup commands in a plain terminal outside Claude Code.** All four installers refuse
when `$env:CLAUDECODE` is `1`. Installation stays outside the session the controls govern.

## 1. Get the tooling

```powershell
git clone https://github.com/MEFORORG/korus.git
```

Choose a commit you have reviewed and check it out before installing. `main` changes as other
sessions work, so upgrade to a new commit deliberately.

If your network blocks GitHub, download the files listed in [Every script](SCRIPTS.md) into a local
directory. The site serves them individually, including
[scripts/coord/claim.ps1](https://claude-multisession.pages.dev/scripts/coord/claim.ps1).

## 2. Set the source and target paths

| Variable | Directory |
|---|---|
| `$tooling` | The Korus checkout you just downloaded; setup copies files from here |
| `$target` | The repository you want KORUS to govern |

Replace both placeholders with your paths:

```powershell
$tooling = "<path-to-this-checkout>"
$target  = "<path-to-the-repo-you-want-governed>"
Set-Location $target
```

The target receives the config and Git hooks. Its primary checkout also goes into the worktree
gate's allowlist. Naming it here does not install controls on the source checkout.

## 3. Copy the tooling into your repository

```powershell
Copy-Item "$tooling/ccx.config.json" "$target/ccx.config.json"
Copy-Item "$tooling/scripts" $target -Recurse -Force
Copy-Item "$tooling/bin" $target -Recurse -Force
```

These commands merge the directories and overwrite matching files. Review any existing local
changes first; committed versions remain recoverable through Git.

Keep `-Force`. Without it, existing directories produce errors even though files still copy. The
original re-run reported ten such errors. Repeat the copy step when you upgrade.

Edit `ccx.config.json` before committing:

| Key | What to do |
|---|---|
| `setupHook` | Delete it or create the named hook. The shipped value points to `.ccx/worktree-setup.ps1`, which is not included |
| `sequences` | Remove it if you do not number records. The supplied `adr` entry otherwise adds an `OFF (opt-in)` doctor row |

For a setup hook, use `examples/worktree-setup.ps1.example` and the contract in
[Worktrees](WORKTREES.md). A missing hook produces a warning on every spawn.

Commit `scripts/`, `bin/`, and the edited config in the target so new worktrees receive them.
Then use the target's copy for every remaining command:

```powershell
$tooling = $target
```

Installing from one copy and auditing against another can produce `STALE` results. Keeping the
tooling in the target is also the only layout in which the doctor can exit `0`.

Separate checkouts work for the worktree gate, both Git hooks, and the backstop. The three
coordination hooks instead look for their scripts inside the repository each session runs in.

Without those files in the target, the hooks can be configured but unable to run.

## 4. Check the state before installation

```powershell
pwsh -NoProfile -File "$tooling/bin/ccx-doctor.ps1" -Repo $target
```

On a fresh setup, expect `OFF` rows and exit `1`. Save this result so you can compare it with the
report after installation.

## 5. Install the controls

Each installer writes to a different scope. Run these in order from the plain terminal.

Install the coordination hooks. This writes one settings file; each hook resolves its repository
when a session runs.

```powershell
pwsh -NoProfile -File "$tooling/scripts/coord/install-coordination.ps1"
```

Install the commit-message claim gate and pre-push guard. They go into the target clone's shared
`.git/hooks` directory and apply to all its worktrees.

```powershell
pwsh -NoProfile -File "$tooling/scripts/coord/install-git-hooks.ps1" -RepoRoot $target
```

Install the worktree gate for the target's primary checkout. **This replaces the existing
allowlist.** If you govern several primaries, name them all in one run using `-Command`;
[Install](INSTALL.md) gives that command.

```powershell
pwsh -NoProfile -File "$tooling/scripts/worktree/install-gate.ps1" -Repo $target
```

Install the SessionStart backstop for one config root:

```powershell
pwsh -NoProfile -File "$tooling/scripts/worktree/install-selfheal.ps1" -ConfigDir ~/.claude
```

Repeat that command for every config root the doctor lists. An unwired root reports `OFF` and
causes exit `1`.

## 6. Check which repository the doctor examined

```powershell
pwsh -NoProfile -File "$tooling/bin/ccx-doctor.ps1" -Repo $target
```

Confirm the report names your target and its tooling copy:

```powershell
pwsh -NoProfile -File "$tooling/bin/ccx-doctor.ps1" -Repo $target |
    Select-String 'repo examined|tooling checkout'
```

Without an explicit target, the doctor uses the current directory. A report about the wrong clone
can look like a successful installation.

You can still see two `OFF (opt-in)` rows on a good install: the ASCII gate and, if configured, the
sequence gate. No installer wires either one, and these rows do not raise the exit code.

If you allocate record numbers, wire the sequence check yourself. Until then, no commit-time gate
protects those numbers. [Sequence allocation](SEQUENCE-ALLOC.md) gives the hook.

## 7. Create two worktrees

Stay in the target repository and run:

```powershell
pwsh -NoProfile -File "$tooling/scripts/worktree/spawn.ps1" -Name alerts
pwsh -NoProfile -File "$tooling/scripts/worktree/spawn.ps1" -Name parser
```

Each command creates a worktree and branch named after `-Name`. Neither `spawn.ps1` nor `new.ps1`
takes a target flag; both use the primary checkout you are standing in.

`spawn.ps1` looks for an editor in this order: `-Editor`, `$CCX_EDITOR`, `$EDITOR`, then `code`.
If none is available on `PATH`, it prints a warning and the worktree path for you to open.

`new.ps1` skips the editor. A missing `setupHook` warning refers to the config from step 3; it does
not prevent the collision test below.

Start a Claude Code session in each worktree. Then check the roster:

```powershell
pwsh -NoProfile -File "$tooling/scripts/coord/presence.ps1"
pwsh -NoProfile -File "$tooling/scripts/coord/overlap.ps1"
$LASTEXITCODE
```

| Exit code | Meaning |
|---|---|
| `0` | The roster is complete, even if it lists nobody |
| `2` | The roster could not be completed, even if some peers appear |

Seeing two peers does not prove that a third was found.

## 8. Ask both sessions to edit the same file

1. Ask `parser` to edit a file and leave the change uncommitted.
2. Ask `alerts` to edit that same file in its own worktree.

The collision gate should refuse the second tool call. Claude receives a message like this:

<!-- no-copy -->
```text
service.py has UNCOMMITTED changes in another LIVE session's worktree -- editing it now means one of you loses work at merge.

  4f2a1c9b (desktop) in myrepo-parser [parser]
      building: the CSV column parser

Before overriding: that session may already be doing what you are about to do.
  see everything in flight :  pwsh -NoProfile -File scripts/coord/overlap.ps1
  who is live              :  pwsh -NoProfile -File scripts/coord/presence.ps1
If you genuinely need this file, coordinate first -- or edit a different one.
```

The peer line gives an 8-character session ID, the client type, the worktree directory, and the
branch. The `building:` line appears only when that peer has a task list.

Check that the edit was actually refused. A completed installer does not prove the collision gate
can see the other session.

The refusal requires uncommitted changes in a live peer's worktree. If the peer has committed and
its worktree is clean, KORUS reports it but allows your edit. See [Coordination](COORDINATION.md).

## The controls cover different mistakes

| Control | Refuses |
|---|---|
| Worktree gate | Edit-tool writes into the shared primary checkout and selected Git verbs that swap its tree |
| Collision gate | An edit to a file with uncommitted changes in a live peer's worktree |
| `commit-msg` claim gate | A commit whose subject claims work this worktree does not hold |
| `pre-push` guard | A direct push to a protected ref |

## Give each session its role instructions

A role's playbook is a file of standing instructions under `roles/` in your checkout.
[The playbooks](PLAYBOOKS.md) maps roles to files and links to the role cards available on the site.

Name the files in the session's opening prompt:

```text
You are the Builder. Read roles/COMMON.md, then roles/BUILDER.md, before anything else.
```

The setup described in [Run a KORUS build](KORUS-BUILD.md) does not automatically route full
playbooks to sessions. Open those files in your checkout.

On 2026-09-08, the original guide retired its `roles/README.md` link because that address served no
page. That file also listed six roles retired on 2026-09-01 as live. Use the playbooks page instead.

### Playbook copies can disagree

No script reconciles the copies, and no check reports their drift. The original guide recorded the
following comparison on 2026-09-04:

| Measured set | Reading |
|---|---|
| Editions of `roles/` on that machine | At least 2: this repository and a separate private vault |
| Filenames shared by the editions | 13; all 13 differed in content |
| Filenames in only one edition | 2 here, 1 in the vault |
| Vault worktrees with a `roles/` copy | 62, excluding the primary |
| Copies compared with the vault's working tree | 607 differed; 35 matched |
| Registered vault worktrees safe to remove | 10 of 79 |

The 607 copies came from 62 worktrees carrying `roles/`. The removal check covered all 79
registered worktrees. Those rows use different populations.

These commands produced the comparisons:

```powershell
# Two editions, compared by filename and by content hash.
$k = Get-ChildItem <this-checkout>/roles -Recurse -Filter *.md -File
$v = Get-ChildItem <vault>/roles -Recurse -Filter *.md -File
($k | Where-Object { $n = $_.Name
    ($h = $v | Where-Object Name -eq $n) -and
    (Get-FileHash $_.FullName).Hash -ne (Get-FileHash $h[0].FullName).Hash }).Count
```

```powershell
# Worktree copies, hashed against the vault's own working tree.
Set-Location <vault>
$primary = (git worktree list --porcelain | Select-String '^worktree ' |
    Select-Object -First 1) -replace '^worktree ',''
$dirs = (git worktree list --porcelain | Select-String '^worktree ') -replace '^worktree ','' |
    Where-Object { $_ -ne $primary -and (Test-Path "$_/roles") }
$stale = 0
foreach ($d in $dirs) {
  foreach ($f in Get-ChildItem "$d/roles" -Filter *.md -File) {
    $p = Join-Path "$primary/roles" $f.Name
    if ((Test-Path $p) -and (Get-FileHash $f.FullName).Hash -ne (Get-FileHash $p).Hash) { $stale++ }
  }
}
"$($dirs.Count) worktrees, $stale stale copies"
```

Removal safety was checked separately. It required both a successful
`git merge-base --is-ancestor <tip> origin/main` and no output from
`git diff origin/main...<tip> --name-only`.

The comparisons used working trees, not either repository's `origin/main`. A worktree on a valid,
newer branch could therefore count as stale. Stripping `\r` did not change the 13 shared-file differences.

These are historical readings from the original guide, not a fresh audit of your installation.
They do not establish whether today's copies agree.

## Set a working agreement before adding more sessions

Copy [CLAUDE.md.template](https://claude-multisession.pages.dev/CLAUDE.md.template) into your target as
`CLAUDE.md`. Keep only instructions that apply to your project, including rules the gates cannot enforce.

Use [Run a KORUS build](KORUS-BUILD.md) to run a manager with builders and a lander.
[Install](INSTALL.md) gives the full installer reference and verification steps.
