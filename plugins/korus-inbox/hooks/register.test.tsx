import { test, expect, mock } from 'claude-code/testing'
import type { On } from 'claude-code'

// Every fixture here is synthetic: invented sessions, folders and commands.
// The refusal texts follow the shape the real gates print (worktree_gate.ps1
// rules 3b, 3d and 1a, block-blanket-git-stage.ps1), with invented paths.

const PLUGIN = 'korus-inbox'
const SURFACES = ['terminal', 'desktop'] as const
const NOW = Date.UTC(2026, 0, 1, 12, 0, 0)
const HOME = 'C:\\Users\\tester'
const DIR = `${HOME}\\.korus-inbox`
const ME = 'sess-own-1'
const MY_FILE = `${DIR}\\${ME}.json`
const OTHER_FILE = `${DIR}\\sess-other-2.json`
const CWD = 'C:\\work\\repo'
const PWSH = 'C:\\Program Files\\PowerShell\\7\\pwsh.exe'
const ACTION = `mcp__${PLUGIN}__owner_action`
const DONE = `mcp__${PLUGIN}__owner_action_done`

const PANE_PROPS = {
  title: 'Owner inbox',
  isFocused: false,
  bodyColumns: 100,
  placement: 'dock',
  scroll: { offset: 0, bodyRows: 40 },
  view: {},
} as const

const BAND_PROPS = {
  hasSurvey: false,
  isWorking: false,
  maxRows: 10,
  bodyColumns: 100,
  scroll: { offset: 0, bodyRows: 9 },
  view: {},
} as const

type World = {
  files: Map<string, { text: string; mtimeMs: number }>
  runs: { argv: readonly string[]; cwd: string | undefined }[]
  copies: string[]
  opens: string[]
  tools: string[]
  statusCalls: (string | undefined)[]
  settle: () => Promise<void>
  advance: (ms: number) => Promise<void>
}

type WorldOptions = { env?: Record<string, string>; cwd?: string | (() => string); cwdFails?: boolean; stdout?: string; exitCode?: number; hang?: boolean }

// The engine beneath the plugin: an in-memory shared folder, a fixed session,
// a recorded process runner and clipboard. Nothing touches the real disk.
function world(on: On, opts: WorldOptions = {}): World {
  const files = new Map<string, { text: string; mtimeMs: number }>()
  const runs: World['runs'] = []
  const copies: string[] = []
  const opens: string[] = []
  const tools: string[] = []
  const statusCalls: (string | undefined)[] = []
  const clock = mock.clock(on, { now: NOW })
  mock.env(on, { USERPROFILE: HOME, ProgramFiles: 'C:\\Program Files', ...opts.env })
  files.set(PWSH, { text: '', mtimeMs: 0 })
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  on('session.end', ($, e) => ({ sessionId: e.sessionId }))
  on('session.id', () => ({ value: ME }))
  on('session.cwd', () => {
    if (opts.cwdFails === true) throw new Error('no cwd')
    return { value: typeof opts.cwd === 'function' ? opts.cwd() : (opts.cwd ?? CWD) }
  })
  on('session.root', () => ({ value: CWD }))
  on('command.register', ($, e) => ({ value: { command: e.name } }))
  on('tool.register', ($, e) => {
    tools.push(e.name)
    return { value: { tool: `mcp__${PLUGIN}__${e.name}` } }
  })
  on('ui.open', ($, e) => {
    opens.push(e.id)
    return { value: { isPlaced: true } }
  })
  on('ui.toast', () => ({ value: undefined }))
  on('ui.status', ($, e) => {
    statusCalls.push(e.text)
    return { value: undefined }
  })
  on('ui.copy', ($, e) => {
    copies.push(e.text)
    return { value: { isCopied: true } }
  })
  on('fs.write', ($, e) => {
    files.set(e.path, { text: e.text, mtimeMs: clock.now() })
    return { value: undefined }
  })
  on('fs.exists', ($, e) => ({ value: files.has(e.path) }))
  on('fs.read', ($, e) => {
    const file = files.get(e.path)
    if (file === undefined) throw new Error('ENOENT')
    return { value: file.text }
  })
  on('fs.list', ($, e) => ({
    value: [...files.entries()]
      .filter(([path]) => path.startsWith(`${e.path}\\`))
      .map(([path, file]) => ({
        name: path.slice(e.path.length + 1),
        kind: 'file' as const,
        size: file.text.length,
        mtimeMs: file.mtimeMs,
        isLink: false,
      })),
  }))
  on('process.run', async ($, e) => {
    if (opts.hang === true) await new Promise(() => undefined)
    runs.push({ argv: e.argv, cwd: e.init?.cwd })
    return {
      value: {
        exitCode: opts.exitCode ?? 0,
        stdout: opts.stdout ?? 'switched fine\n',
        stderr: '',
        isStdoutTruncated: false,
        isStderrTruncated: false,
      },
    }
  })
  return { files, runs, copies, opens, tools, statusCalls, settle: clock.settle, advance: clock.advance }
}

// ------------------------------------------------------------- refusal texts

const SWITCH_PART = 'git switch feature-x'
const SWITCH_LINE = `git add notes.txt && git commit -m wip && ${SWITCH_PART} && git push origin feature-x`

// worktree_gate.ps1 rule 3b, as it prints it. Kept: it hands the act over.
const SWITCH_REFUSAL = [
  `BLOCKED: '${SWITCH_PART}' would switch a LINKED WORKTREE (C:/work/repo/.claude/worktrees/other) onto the existing branch 'feature-x'.`,
  '',
  "That worktree belongs to another session, which is building on 'main' right now. Switching it swaps every",
  "file under that session mid-task -- silently -- and drags two sessions' work onto one branch.",
  '',
  'What to do instead:',
  "  * To READ 'feature-x' without touching any working tree, use the plumbing:",
  '        git -C C:/work/repo show feature-x:<path>',
  '  * If you genuinely OWN this worktree and must switch it, do it from a PLAIN terminal -- the gate governs',
  '    agents, not you. Do not route around this with a shell script; that only hides the collision.',
].join('\n')

// block-blanket-git-stage.ps1, as it prints it. Dropped: the agent routes
// around it by naming paths.
const STAGE_REFUSAL =
  "Blocked blanket git staging: git add/stage -A/--all/-u/--update (or a cluster containing A or u) stages everything, including files another session may be editing. Stage explicit paths instead: 'git add <path> ...' then 'git commit -m ...'. (MessageFoundry guard; disable via /hooks.)"

// worktree_gate.ps1 rule 3b's shared-primary sibling (4038). Dropped.
const PRIMARY_REFUSAL = [
  "BLOCKED: 'git checkout' would change the working tree of the SHARED PRIMARY checkout (C:/work/repo).",
  '',
  'Create a worktree and work there instead.',
].join('\n')

// worktree_gate.ps1 rule 3d, another session's tree. Kept.
const REMOVE_PART = 'git worktree remove C:/work/old'
const REMOVE_REFUSAL = [
  `BLOCKED: '${REMOVE_PART}' acts on a worktree of C:/work/repo that is NOT the tree`,
  'this session is running in. This gate cannot tell whether another session is using it.',
  '',
  'What to do instead:',
  '  * To find out whether a worktree is still in use, look rather than delete:',
  '        git -C "C:/work/repo" worktree list',
  "  * If you are certain it is abandoned and must go now, that is the user's call, not yours. Say so:",
  '    "I want to remove the worktree C:/work/old and I need you to confirm it is not in use."',
].join('\n')

// A refusal that hands the act over and quotes the whole command.
function handing(command: string): string {
  return `BLOCKED: '${command}' needs the person. Do it from a PLAIN terminal -- the gate governs agents, not you.`
}

function inputCommand(e: unknown): string | undefined {
  const value = (e as { command?: unknown }).command
  return typeof value === 'string' ? value : undefined
}

// A settings PreToolUse hook that refuses a shell call with `reason(command)`,
// or lets it through when that is undefined. The 2.1.286 kit routes
// $.tool.call through classic.PreToolUse; the tool hooks beneath answer as a
// session prints a hook refusal, which the fallback path reads.
function refuse(on: On, reason: (command: string) => string | undefined): void {
  on('classic.PreToolUse', ($, e) => {
    const command = inputCommand(e)
    const text = command === undefined ? undefined : reason(command)
    return text === undefined ? {} : { deny: text }
  })
  for (const tool of ['PowerShell', 'Bash'] as const) {
    on('tool.call', { tool }, ($, e) => {
      const text = reason(e.command)
      return text === undefined
        ? { result: 'ok', text: 'ok' }
        : { isError: true, result: 'blocked', text: `PreToolUse:${tool} hook error: ${text}` }
    })
  }
}

function refuseAll(on: On, text: string): void {
  refuse(on, () => text)
}

function refuseQuoting(on: On): void {
  refuse(on, command => handing(command))
}

function mine(w: World): { entries: Record<string, unknown>[]; dismissed: string[] } {
  const file = w.files.get(MY_FILE)
  if (file === undefined) return { entries: [], dismissed: [] }
  return JSON.parse(file.text) as { entries: Record<string, unknown>[]; dismissed: string[] }
}

const MOUNT = { plugin: PLUGIN, surface: 'terminal', component: 'Pane', requestId: PLUGIN, props: PANE_PROPS } as const
const GIT_BASH = 'C:\\Program Files\\Git\\bin\\bash.exe'

// The rows the confirm and result views draw: a label, or a continuation mark.
const ROW = /^(argv\[\d+\]: |folder: |  \+ |  line \d+: )/

type Found = { text?: string; key?: string; props?: Record<string, unknown> }
type Finder = { findAll: (query: { type?: string; text?: RegExp }) => Promise<Found[]> }

async function shownRows(ui: Finder): Promise<string[]> {
  return (await ui.findAll({ type: 'Text', text: ROW })).map(one => one.text ?? '')
}

async function textOf(ui: { find: (q: { type: 'Text'; text: RegExp }) => Promise<Found | undefined> }, re: RegExp) {
  return (await ui.find({ type: 'Text', text: re }))?.text
}

// The waiting cards drawn: each carries one Dismiss, and the Done section's
// own are not drawn while it is collapsed.
async function drawnCards(ui: Finder): Promise<number> {
  const buttons = await ui.findAll({ type: 'Button' })
  return buttons.filter(one => /^r?dismiss:/.test(one.key ?? '')).length
}

function otherFile(fields: Record<string, unknown>): string {
  return JSON.stringify({
    format: 'korus-inbox/1',
    sessionId: 'sess-other-2',
    label: 'other-worktree',
    updatedAt: NOW - 1000,
    ended: false,
    entries: [],
    dismissed: [],
    ...fields,
  })
}

const REMOTE_KEEP = {
  id: 'e1',
  kind: 'refused',
  createdAt: NOW - 60_000,
  shell: 'PowerShell',
  command: `cd C:\\elsewhere; ${REMOVE_PART}`,
  cwd: 'C:\\elsewhere',
  refusal: `BLOCKED: '${REMOVE_PART}' acts on a worktree`,
  detail: REMOVE_REFUSAL,
  ask: "If you are certain it is abandoned and must go now, that is the user's call, not yours.",
}
const REMOTE_DROP = {
  id: 'e2',
  kind: 'refused',
  createdAt: NOW - 50_000,
  shell: 'Bash',
  command: 'git add -A',
  cwd: 'C:\\elsewhere',
  refusal: STAGE_REFUSAL,
}
const REMOTE_SIGNAL = {
  id: 'e3',
  kind: 'signal',
  createdAt: NOW - 40_000,
  title: 'Approve the release tag',
  why: 'Tagging publishes to the index.',
  recommendedAction: 'Approve the tag v1.2.0.',
  needs: 'authority',
  reviewOutcome: 'not applicable: only the owner signs releases',
  confidence: 'high',
  command: 'git tag v1.2.0',
}

// ------------------------------------------------------------- the one count

for (const surface of SURFACES) {
  test(`the band, the pane header and the waiting list agree on one count, on ${surface}`, async ($, on) => {
    const w = world(on)
    w.files.set(OTHER_FILE, { mtimeMs: NOW - 1000, text: otherFile({ entries: [REMOTE_KEEP, REMOTE_DROP, REMOTE_SIGNAL] }) })
    refuse(on, command =>
      command === 'git add -A'
        ? STAGE_REFUSAL
        : command.includes('&&')
          ? command.includes('worktree')
            ? REMOVE_REFUSAL
            : SWITCH_REFUSAL
          : undefined,
    )
    on('ui.render', { component: 'AbovePrompt' }, () => ({ type: 'engine', ref: 0 }))
    let answer: (() => void) | undefined
    const gate = new Promise<void>(resolve => {
      answer = resolve
    })
    on('tool.call', { tool: 'AskUserQuestion' }, async () => {
      await gate
      return { result: { questions: [], answers: {} }, text: 'answered' }
    })
    await $.session.start({ cwd: CWD, surface, isInteractive: true })
    // Waiting: the switch refusal. Done: the remove refusal, which later ran fine.
    await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
    await $.tool.call({ tool: 'PowerShell', command: `git status && ${REMOVE_PART}` })
    await $.tool.call({ tool: 'PowerShell', command: REMOVE_PART.replace('git worktree', 'git  worktree') })
    // Not recorded at all: a refusal the agent routes around.
    await $.tool.call({ tool: 'Bash', command: 'git add -A' })
    await w.settle()
    const call = $.tool.call({
      tool: 'AskUserQuestion',
      questions: [{ header: 'Approach', question: 'Which path?', multiSelect: false, options: [{ label: 'A', description: '' }, { label: 'B', description: '' }] }],
    })
    await w.settle()

    // own: switch (waiting), remove (waiting: the doubled space is a different command), question
    // remote: keep + signal; the stage refusal is dropped.
    const band = await $.ui.mount({ plugin: PLUGIN, surface, component: 'AbovePrompt', props: BAND_PROPS })
    const pane = await $.ui.mount({ plugin: PLUGIN, surface, component: 'Pane', requestId: PLUGIN, props: PANE_PROPS })
    const bandCount = Number(/^inbox (\d+)$/.exec((await band.find({ type: 'Button', key: 'korus-inbox:open' }))?.text ?? '')?.[1])
    const headCount = Number(/^(\d+) waiting on the owner$/.exec((await textOf(pane, /waiting on the owner$/)) ?? '')?.[1])
    const cards = await drawnCards(pane)
    expect(bandCount).toBe(5)
    expect(headCount).toBe(bandCount)
    expect(cards).toBe(bandCount)

    // A later success moves the remove refusal to Done: all three drop together.
    await $.tool.call({ tool: 'PowerShell', command: REMOVE_PART })
    await w.settle()
    const bandAfter = (await band.find({ type: 'Button', key: 'korus-inbox:open' }))?.text
    expect(bandAfter).toBe('inbox 4')
    expect(await textOf(pane, /waiting on the owner$/)).toBe('4 waiting on the owner')
    expect(await drawnCards(pane)).toBe(4)
    expect((await pane.find({ type: 'Button', key: 'done:toggle' }))?.text).toBe('Done (1)')
    answer?.()
    await call
    await w.settle()
    expect((await band.find({ type: 'Button', key: 'korus-inbox:open' }))?.text).toBe('inbox 3')
    expect(await drawnCards(pane)).toBe(3)
    await band.unmount()
    await pane.unmount()
  })
}

test('the inbox never sets the status line, and clears it once at session start', async ($, on) => {
  const w = world(on)
  refuseAll(on, SWITCH_REFUSAL)
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  expect(w.statusCalls).toEqual([])
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.advance(5000)
  expect(w.statusCalls).toEqual([undefined])
  const ui = await $.ui.mount(MOUNT)
  const id = String(mine(w).entries[0]?.id)
  await ui.press({ key: `dismiss:${id}` })
  expect(w.statusCalls).toEqual([undefined])
  await ui.unmount()
})

// --------------------------------------------------------- what is recorded

test('a refusal that does not hand the act to the person is not recorded at all', async ($, on) => {
  const w = world(on)
  refuse(on, command => (command === 'git add -A' ? STAGE_REFUSAL : PRIMARY_REFUSAL))
  await $.tool.call({ tool: 'Bash', command: 'git add -A' })
  await $.tool.call({ tool: 'PowerShell', command: 'git checkout main' })
  await w.settle()
  expect(w.files.has(MY_FILE)).toBe(false)
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /waiting on the owner$/)).toBe('0 waiting on the owner')
  expect(await drawnCards(ui)).toBe(0)
  await ui.unmount()
})

test('an allowed call is not recorded, and neither is a command that merely failed', async ($, on) => {
  const w = world(on)
  on('classic.PreToolUse', () => ({}))
  on('tool.call', { tool: 'PowerShell' }, () => ({ result: 'ok', text: 'ok' }))
  on('tool.call', { tool: 'Bash' }, () => ({ isError: true, result: 'Exit code 1', text: 'Exit code 1' }))
  await $.tool.call({ tool: 'PowerShell', command: 'git status' })
  await $.tool.call({ tool: 'Bash', command: 'false' })
  await w.settle()
  expect(w.files.has(MY_FILE)).toBe(false)
})

test('a refusal that reaches the result as the session prints it is recorded too', async ($, on) => {
  const w = world(on)
  on('tool.call', { tool: 'PowerShell' }, () => ({
    isError: true,
    result: 'blocked',
    text: `PreToolUse:PowerShell hook error: ${SWITCH_REFUSAL}`,
  }))
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  expect(mine(w).entries[0]).toMatchObject({ kind: 'refused', command: SWITCH_LINE })
  expect(String(mine(w).entries[0]?.ask)).toContain('PLAIN terminal')
})

test('a secret-looking command is stored as a placeholder and offers no Run', async ($, on) => {
  const w = world(on)
  refuseQuoting(on)
  await $.tool.call({ tool: 'Bash', command: 'export GH_TOKEN=abc' })
  await $.tool.call({ tool: 'Bash', command: 'psql postgres://bob:hunter2@db.local/app' })
  await w.settle()
  const text = w.files.get(MY_FILE)?.text ?? ''
  expect(text).not.toContain('GH_TOKEN')
  expect(text).not.toContain('hunter2')
  for (const entry of mine(w).entries) {
    expect(entry.command).toBeUndefined()
    expect(entry.withheld).toContain('secret')
  }
  const ui = await $.ui.mount(MOUNT)
  expect(await ui.findAll({ type: 'Button', text: 'Run' })).toHaveLength(0)
  await ui.unmount()
})

// -------------------------------------------------------------- the card

for (const surface of SURFACES) {
  test(`a gate-handed refusal reads as one plain card, on ${surface}`, async ($, on) => {
    const w = world(on)
    refuseAll(on, SWITCH_REFUSAL)
    await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
    await w.settle()
    const id = String(mine(w).entries[0]?.id)
    const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'Pane', requestId: PLUGIN, props: PANE_PROPS })
    expect(await textOf(ui, /^Blocked: /)).toBe(`Blocked: ${SWITCH_PART}`)
    expect(await textOf(ui, /^Do this: /)).toBe(`Do this: Run this in a plain terminal: ${SWITCH_PART}`)
    expect(await textOf(ui, /^Needs you for: /)).toBe('Needs you for: authority | confidence: high')
    expect(await textOf(ui, /^Why: /)).toBe(
      `Why: '${SWITCH_PART}' would switch a LINKED WORKTREE (C:/work/repo/.claude/worktrees/other) onto the existing branch 'feature-x'.`,
    )
    expect(await textOf(ui, /^For you: /)).toBe(
      'For you: If you genuinely OWN this worktree and must switch it, do it from a PLAIN terminal -- the gate governs agents, not you.',
    )
    expect(await textOf(ui, /^From: /)).toBe('From: this session, 0s ago')
    expect(await textOf(ui, /^Folder: /)).toBe(`Folder: ${CWD}`)
    expect(await textOf(ui, /only the blocked part/)).toBe('Copy and Run use only the blocked part above, not the whole line.')
    // The whole line is under Details, not on the card.
    expect(await ui.find({ type: 'Text', text: SWITCH_LINE })).toBeUndefined()
    await ui.press({ key: `copy:${id}` })
    expect(w.copies).toEqual([SWITCH_PART])
    await ui.unmount()
  })

  test(`Details opens the full command and refusal, and closes again, on ${surface}`, async ($, on) => {
    const w = world(on)
    refuseAll(on, SWITCH_REFUSAL)
    await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
    await w.settle()
    const id = String(mine(w).entries[0]?.id)
    const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'Pane', requestId: PLUGIN, props: PANE_PROPS })
    expect(await ui.find({ type: 'Text', text: 'Full command:' })).toBeUndefined()
    expect((await ui.find({ key: `details:${id}` }))?.text).toBe('Details')
    await ui.press({ key: `details:${id}` })
    expect(await ui.find({ type: 'Text', text: 'Full command:' })).toBeDefined()
    expect((await ui.find({ type: 'Text', text: SWITCH_LINE }))?.text).toBe(SWITCH_LINE)
    expect((await ui.find({ type: 'Text', text: /^BLOCKED: 'git switch/ }))?.text).toBe(SWITCH_REFUSAL)
    expect((await ui.find({ key: `details:${id}` }))?.text).toBe('Hide details')
    await ui.press({ key: `details:${id}` })
    expect(await ui.find({ type: 'Text', text: 'Full command:' })).toBeUndefined()
    await ui.unmount()
  })
}

test('with no verbatim match the headline is the first line, Copy takes the whole line, and Run is not offered', async ($, on) => {
  const w = world(on)
  refuseAll(on, SWITCH_REFUSAL)
  const command = `git -C C:/work/repo switch feature-x\ngit log -1 --format=${'x'.repeat(100)}`
  await $.tool.call({ tool: 'PowerShell', command })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /^Blocked: /)).toBe('Blocked: git -C C:/work/repo switch feature-x')
  expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
  expect(await textOf(ui, /^Copy only: the refusal does not quote/)).toBeDefined()
  expect(await textOf(ui, /only the blocked part/)).toBeUndefined()
  expect(await textOf(ui, /^Do this: /)).toBe('Do this: Run this in a plain terminal: the blocked command (open Details)')
  await ui.press({ key: `copy:${id}` })
  expect(w.copies).toEqual([command])
  expect(w.runs).toHaveLength(0)
  await ui.unmount()
})

test('a long first line is cut to 80 characters in the fallback headline', async ($, on) => {
  const w = world(on)
  refuseAll(on, SWITCH_REFUSAL)
  const command = `git log --format=${'y'.repeat(200)}`
  await $.tool.call({ tool: 'PowerShell', command })
  await w.settle()
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /^Blocked: /)).toBe(`Blocked: ${command.slice(0, 80)} [cut]`)
  await ui.unmount()
})

const NOT_WHOLE = [
  { name: 'a prefix of a longer word', part: 'rm -rf /tmp', command: 'rm -rf /tmp/build' },
  { name: 'a part fed by a pipe', part: 'git switch feature-x', command: 'echo y | git switch feature-x' },
  { name: 'a part followed by a redirect', part: 'git switch feature-x', command: 'git switch feature-x 2>&1' },
  { name: 'a contraction before the quote', part: '', command: 'git switch feature-x' },
  { name: 'inside a comment', part: 'git push --force origin main', command: '# never; git push --force origin main' },
  { name: 'inside a double-quoted string', part: 'git push --force origin main', command: 'echo "x; git push --force origin main;"' },
  { name: 'inside a here-doc', part: 'git push --force origin main', command: 'cat <<EOF\ngit push --force origin main\nEOF' },
  { name: 'inside an ANSI-C string', part: 'git push --force origin main', command: "echo $'a\\'; git push --force origin main'" },
  { name: 'after a line continuation', part: 'git push --force origin main', command: 'echo \\\ngit push --force origin main' },
  { name: 'after a background operator', part: 'git push --force origin main', command: 'sleep 1 & git push --force origin main' },
  { name: 'inside typographic quotes', part: 'Remove-Item -Recurse C:\\data', command: 'Write-Output \u201cnote; Remove-Item -Recurse C:\\data; done\u201d' },
  { name: 'after the stop-parsing token', part: 'Remove-Item -Recurse -Force C:\\data', command: 'icacls C:\\x --% /grant Users:F; Remove-Item -Recurse -Force C:\\data' },
  { name: 'on the line after a trailing pipe', part: 'Remove-Item -Recurse', command: 'Get-ChildItem C:\\old |\nRemove-Item -Recurse' },
] as const

for (const one of NOT_WHOLE) {
  test(`a quoted span that is ${one.name} is not the blocked part`, async ($, on) => {
    const w = world(on)
    const reason =
      one.part === ''
        ? "BLOCKED: it can't switch here, it's another tree. Do it from a PLAIN terminal."
        : `BLOCKED: '${one.part}' needs the person. Do it from a PLAIN terminal.`
    refuseAll(on, reason)
    await $.tool.call({ tool: 'Bash', command: one.command })
    await w.settle()
    const id = String(mine(w).entries[0]?.id)
    const ui = await $.ui.mount(MOUNT)
    const head = one.command.split('\n').find(line => line.trim() !== '') ?? ''
    expect(await textOf(ui, /^Blocked: /)).toBe(`Blocked: ${head}`)
    expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
    await ui.press({ key: `copy:${id}` })
    expect(w.copies).toEqual([one.command])
    await ui.unmount()
  })
}

const CONTEXT = [
  { name: 'a cd before a later copy of the part', shell: 'Bash', command: 'git push --dry-run; cd ../prod && git push', part: 'git push' },
  { name: 'a cd behind if', shell: 'Bash', command: 'if cd ../prod; then :; fi; git push', part: 'git push' },
  { name: 'a cd in a brace group', shell: 'Bash', command: '{ cd ../prod; }; git push', part: 'git push' },
  { name: 'builtin cd', shell: 'Bash', command: 'builtin cd ../prod; git push', part: 'git push' },
  { name: 'command cd', shell: 'Bash', command: 'command cd ../prod; git push', part: 'git push' },
  { name: 'Set-Location in a script block', shell: 'PowerShell', command: '& { Set-Location ..\\prod }; git push', part: 'git push' },
  { name: 'an environment variable', shell: 'PowerShell', command: '$env:GIT_DIR = "x"; git push', part: 'git push' },
  { name: 'an indexed assignment', shell: 'PowerShell', command: "$PSDefaultParameterValues['*:WhatIf']=$true; Remove-Item -Recurse C:\\data", part: 'Remove-Item -Recurse C:\\data' },
  { name: 'a member assignment', shell: 'PowerShell', command: '$o.Mode = 1; git push', part: 'git push' },
  { name: 'an exit', shell: 'Bash', command: 'exit 0; git push --force', part: 'git push --force' },
] as const

for (const one of CONTEXT) {
  test(`a part after ${one.name} gets no Run`, async ($, on) => {
    const w = world(on)
    refuseAll(on, `BLOCKED: '${one.part}' needs the person. Do it from a PLAIN terminal.`)
    await $.tool.call({ tool: one.shell, command: one.command })
    await w.settle()
    const id = String(mine(w).entries[0]?.id)
    const ui = await $.ui.mount(MOUNT)
    expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
    expect(await ui.find({ key: `copy:${id}` })).toBeDefined()
    await ui.press({ key: `run:${id}` }).catch(() => undefined)
    await w.advance(700)
    await ui.press({ key: `confirm:${id}` }).catch(() => undefined)
    expect(w.runs).toHaveLength(0)
    await ui.unmount()
  })
}

test('a part after a cd is Copy only: alone it could act in another folder', async ($, on) => {
  const w = world(on)
  refuseAll(on, SWITCH_REFUSAL)
  await $.tool.call({ tool: 'PowerShell', command: `cd C:\\other && ${SWITCH_PART}` })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /^Blocked: /)).toBe(`Blocked: ${SWITCH_PART}`)
  expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
  expect(await textOf(ui, /^Copy only: an earlier part of the line changes the folder/)).toBeDefined()
  expect(await textOf(ui, /only the blocked part/)).toBe('Copy takes only the blocked part above, not the whole line.')
  await ui.press({ key: `copy:${id}` })
  expect(w.copies).toEqual([SWITCH_PART])
  await ui.unmount()
})

// -------------------------------------------------------- recommended action

const ROWS = [
  { name: 'I need you to confirm', text: `BLOCKED: 'git x' acts on a tree. "I need you to confirm it is not in use."`, act: 'Confirm it is not in use, then run: git x' },
  { name: 'from a PLAIN terminal', text: "BLOCKED: 'git x' is reserved. Do it from a PLAIN terminal.", act: 'Run this in a plain terminal: git x' },
  { name: 'governs agents, not you', text: "BLOCKED: 'git x' is reserved. The gate governs\n    agents, not you.", act: 'Run this in a plain terminal: git x' },
  { name: "the user's call", text: "BLOCKED: 'git x' deletes a tree. That is the user's call, not yours.", act: 'Decide; if you agree, run it yourself: git x' },
  { name: 'a human act', text: "BLOCKED: 'git x' changes the gate. Re-install is a human act.", act: 'Do it yourself, from a plain terminal: git x' },
  { name: 'only the owner', text: "BLOCKED: 'git x' signs a release. Only the owner signs.", act: 'Only you can do this; if you agree, run it yourself: git x' },
  { name: 'let the user decide', text: "BLOCKED: 'git x' turns a gate off. Say so and let the user decide.", act: 'Decide what the session asks under "For you".' },
  { name: 'ask the user', text: "BLOCKED: 'git x' removes your own tree. Then ask the user, in these words: done here.", act: 'Answer what the session asks under "For you".' },
  { name: 'I need you to', text: "BLOCKED: 'git x' turns a gate off. \"I need you to do it.\"", act: 'Do what the session asks under "For you".' },
] as const

for (const row of ROWS) {
  test(`the phrase "${row.name}" maps to its recommended action`, async ($, on) => {
    const w = world(on)
    refuseAll(on, row.text)
    await $.tool.call({ tool: 'PowerShell', command: 'git x' })
    await w.settle()
    const ui = await $.ui.mount(MOUNT)
    expect(await textOf(ui, /^Do this: /)).toBe(`Do this: ${row.act}`)
    await ui.unmount()
  })
}

test('the real rule 3d refusal maps to Confirm, with the blocked part', async ($, on) => {
  const w = world(on)
  refuseAll(on, REMOVE_REFUSAL)
  await $.tool.call({ tool: 'PowerShell', command: REMOVE_PART })
  await w.settle()
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /^Do this: /)).toBe(`Do this: Confirm it is not in use, then run: ${REMOVE_PART}`)
  await ui.unmount()
})

test('a question shows its (Recommended) option as Do this, and preference as its need', async ($, on) => {
  const w = world(on)
  let answer: (() => void) | undefined
  const gate = new Promise<void>(resolve => {
    answer = resolve
  })
  on('tool.call', { tool: 'AskUserQuestion' }, async () => {
    await gate
    return { result: { questions: [], answers: {} }, text: 'answered' }
  })
  const call = $.tool.call({
    tool: 'AskUserQuestion',
    questions: [
      {
        header: 'Approach',
        question: 'Which path should the build take?',
        multiSelect: false,
        options: [
          { label: 'Fast', description: 'Ship today' },
          { label: 'Careful (Recommended)', description: 'Ship tomorrow' },
        ],
      },
    ],
  })
  await w.settle()
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /^Question: /)).toBe('Question: Approach')
  expect(await textOf(ui, /^Do this: /)).toBe('Do this: Pick "Careful" (recommended), in repo (this session); the question waits there.')
  expect(await textOf(ui, /^Needs you for: /)).toBe('Needs you for: preference | confidence: not stated')
  expect(await textOf(ui, /^\[Approach\] /)).toContain('  - Careful (Recommended): Ship tomorrow')
  await ui.unmount()
  answer?.()
  await call
})

test('a question with no recommended option says where it waits', async ($, on) => {
  const w = world(on)
  let answer: (() => void) | undefined
  const gate = new Promise<void>(resolve => {
    answer = resolve
  })
  on('tool.call', { tool: 'AskUserQuestion' }, async () => {
    await gate
    return { result: { questions: [], answers: {} }, text: 'answered' }
  })
  const call = $.tool.call({
    tool: 'AskUserQuestion',
    questions: [{ header: 'Pick', question: 'Which one?', multiSelect: false, options: [{ label: 'A', description: '' }, { label: 'B', description: '' }] }],
  })
  await w.settle()
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /^Do this: /)).toBe('Do this: Answer in repo (this session); the question waits there.')
  await ui.unmount()
  answer?.()
  await call
})

// ---------------------------------------------------------- the owner signal

function signal(fields: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    tool: ACTION,
    title: 'Choose the license for the new package',
    why: 'Two licenses fit and they differ for adopters.',
    recommendedAction: 'Pick Apache-2.0 for the new package.',
    needsOwnerBecause: 'preference',
    reviewOutcome: 'review split evenly between the two licenses',
    confidence: 'medium',
    ...fields,
  }
}

async function callTool($: { tool: { call: (e: never) => Promise<unknown> } }, input: Record<string, unknown>): Promise<string> {
  return JSON.stringify(await $.tool.call(input as never))
}

test('session start registers owner_action and owner_action_done', async ($, on) => {
  const w = world(on)
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  expect(w.tools).toEqual(['owner_action', 'owner_action_done'])
})

test('owner_action files an entry that counts, shows Do this and Needs you for, and returns at once', async ($, on) => {
  const w = world(on)
  on('ui.render', { component: 'AbovePrompt' }, () => ({ type: 'engine', ref: 0 }))
  const said = await callTool($, signal())
  expect(said).toContain('Filed in the owner inbox as ')
  await w.settle()
  const entry = mine(w).entries[0]
  expect(entry).toMatchObject({ kind: 'signal', needs: 'preference', title: 'Choose the license for the new package' })
  const band = await $.ui.mount({ plugin: PLUGIN, surface: 'terminal', component: 'AbovePrompt', props: BAND_PROPS })
  expect((await band.find({ type: 'Button', key: 'korus-inbox:open' }))?.text).toBe('inbox 1')
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /^Choose the license/)).toBe('Choose the license for the new package')
  expect(await textOf(ui, /^Do this: /)).toBe('Do this: Pick Apache-2.0 for the new package.')
  expect(await textOf(ui, /^Needs you for: /)).toBe('Needs you for: preference | confidence: medium')
  expect(await textOf(ui, /^Why: /)).toBe('Why: Two licenses fit and they differ for adopters.')
  await band.unmount()
  await ui.unmount()
})

test('owner_action refuses a filing with no category, or one outside the four', async ($, on) => {
  const w = world(on)
  expect(await callTool($, signal({ needsOwnerBecause: undefined }))).toContain('needsOwnerBecause must be one of')
  expect(await callTool($, signal({ needsOwnerBecause: 'urgent' }))).toContain('needsOwnerBecause must be one of')
  await w.settle()
  expect(w.files.has(MY_FILE)).toBe(false)
})

test('owner_action refuses a filing with an empty reviewOutcome', async ($, on) => {
  const w = world(on)
  expect(await callTool($, signal({ reviewOutcome: '' }))).toContain('reviewOutcome is empty')
  expect(await callTool($, signal({ reviewOutcome: '\u200b' }))).toContain('reviewOutcome is empty')
  await w.settle()
  expect(w.files.has(MY_FILE)).toBe(false)
})

for (const need of ['preference', 'authority', 'private-context', 'cost'] as const) {
  test(`owner_action accepts the category ${need}`, async ($, on) => {
    const w = world(on)
    expect(await callTool($, signal({ needsOwnerBecause: need }))).toContain('Filed')
    await w.settle()
    const ui = await $.ui.mount(MOUNT)
    expect(await textOf(ui, /^Needs you for: /)).toBe(`Needs you for: ${need} | confidence: medium`)
    await ui.unmount()
  })
}

test('owner_action_done resolves the entry: it leaves the count for Done', async ($, on) => {
  const w = world(on)
  const said = await callTool($, signal())
  const id = /as ([0-9a-f-]{36})/.exec(said)?.[1] ?? ''
  await w.settle()
  expect(await callTool($, { tool: DONE, id: 'not-an-id' })).toContain('No owner_action entry')
  expect(await callTool($, { tool: DONE, id, note: 'settled in review' })).toContain(`Resolved ${id}`)
  await w.settle()
  expect(mine(w).entries).toHaveLength(0)
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /waiting on the owner$/)).toBe('0 waiting on the owner')
  await ui.press({ key: 'done:toggle' })
  expect(await textOf(ui, /^Resolved /)).toBe('Resolved 0s ago: settled in review.')
  await ui.unmount()
})

test('owner_action text is held to the disk limits', async ($, on) => {
  const w = world(on)
  await callTool($, signal({ title: `Pick\u001b[2J one ${'z'.repeat(400)}` }))
  await w.settle()
  const title = String(mine(w).entries[0]?.title)
  expect(title).not.toContain('\u001b')
  expect(title.length).toBeLessThanOrEqual(206)
})

test('a filed command runs on the two presses, in the given folder, through pwsh', async ($, on) => {
  const w = world(on)
  await callTool($, signal({ command: 'git tag v1.2.0', cwd: 'C:\\work\\release' }))
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /^Command: /)).toBe('Command: git tag v1.2.0')
  await ui.press({ key: `run:${id}` })
  await w.advance(700)
  await ui.press({ key: `confirm:${id}` })
  expect(w.runs).toEqual([{ argv: [PWSH, '-NoProfile', '-Command', 'git tag v1.2.0'], cwd: 'C:\\work\\release' }])
  expect(await textOf(ui, /waiting on the owner$/)).toBe('0 waiting on the owner')
  await ui.unmount()
})

const SIGNAL_NO_RUN = [
  { name: 'over 400 characters', fields: { command: `echo ${'zz '.repeat(131)}zzz` }, why: /^Copy only: too long to show safely/ },
  { name: 'over 6 lines', fields: { command: `${'git status\n'.repeat(6)}git status` }, why: /^Copy only: too many lines/ },
  { name: 'in a relative folder', fields: { command: 'git status', cwd: 'work\\repo' }, why: /^Copy only: its folder is not known as a full path/ },
  { name: 'filed by a subagent', fields: { command: 'git status', agentId: 'agent-1' }, why: /^Copy only: a subagent filed it/ },
] as const

for (const one of SIGNAL_NO_RUN) {
  test(`a filed command ${one.name} gets Copy only`, async ($, on) => {
    const w = world(on)
    await callTool($, signal(one.fields))
    await w.settle()
    const id = String(mine(w).entries[0]?.id)
    const ui = await $.ui.mount(MOUNT)
    expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: one.why })).toBeDefined()
    await ui.press({ key: `copy:${id}` })
    expect(w.copies).toEqual([one.fields.command])
    await ui.unmount()
  })
}

// ----------------------------------------------------------------- Run

for (const surface of SURFACES) {
  test(`Run executes only the blocked part, on the owner's two presses, on ${surface}`, async ($, on) => {
    const w = world(on)
    refuseAll(on, SWITCH_REFUSAL)
    await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
    await w.settle()
    const id = String(mine(w).entries[0]?.id)
    const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'Pane', requestId: PLUGIN, props: PANE_PROPS })
    await ui.press({ key: `run:${id}` })
    expect(w.runs).toHaveLength(0)
    expect(await ui.find({ type: 'Text', text: 'Run now runs this:' })).toBeDefined()
    expect((await shownRows(ui)).at(-1)).toBe(`argv[3]: ${SWITCH_PART}`)
    await ui.press({ key: `cancel:${id}` })
    await ui.press({ key: `run:${id}` })
    await w.advance(700)
    await ui.press({ key: `confirm:${id}` })
    expect(w.runs).toEqual([{ argv: [PWSH, '-NoProfile', '-Command', SWITCH_PART], cwd: CWD }])
    await ui.unmount()
  })

  test(`a Run that exits 0 moves the entry to Done and drops the count, on ${surface}`, async ($, on) => {
    const w = world(on)
    refuseAll(on, SWITCH_REFUSAL)
    on('ui.render', { component: 'AbovePrompt' }, () => ({ type: 'engine', ref: 0 }))
    await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
    await w.settle()
    const id = String(mine(w).entries[0]?.id)
    const band = await $.ui.mount({ plugin: PLUGIN, surface, component: 'AbovePrompt', props: BAND_PROPS })
    const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'Pane', requestId: PLUGIN, props: PANE_PROPS })
    expect((await band.find({ type: 'Button', key: 'korus-inbox:open' }))?.text).toBe('inbox 1')
    await ui.press({ key: `run:${id}` })
    await w.advance(700)
    await ui.press({ key: `confirm:${id}` })
    expect(await band.findAll({ type: 'Button' })).toHaveLength(0)
    expect(await textOf(ui, /waiting on the owner$/)).toBe('0 waiting on the owner')
    expect(await drawnCards(ui)).toBe(0)
    expect((await ui.find({ key: 'done:toggle' }))?.text).toBe('Done (1)')
    await ui.press({ key: 'done:toggle' })
    expect(await textOf(ui, /^Done: /)).toBe(`Done: ${SWITCH_PART}`)
    expect(await textOf(ui, /^Ran, exit 0/)).toBe('Ran, exit 0, 0s ago.')
    expect(mine(w).entries).toHaveLength(0)
    expect(w.files.get(MY_FILE)?.text ?? '').not.toContain('switched fine')
    await band.unmount()
    await ui.unmount()
  })
}

test('a Run that exits non-zero stays waiting and shows its output', async ($, on) => {
  const w = world(on, { exitCode: 1, stdout: 'fatal: no such branch\n' })
  refuseAll(on, SWITCH_REFUSAL)
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  await w.advance(700)
  await ui.press({ key: `confirm:${id}` })
  expect(await textOf(ui, /^ran, exit/)).toBe('ran, exit 1:')
  expect(await ui.find({ type: 'Text', text: 'out: fatal: no such branch' })).toBeDefined()
  expect(await textOf(ui, /waiting on the owner$/)).toBe('1 waiting on the owner')
  expect(await drawnCards(ui)).toBe(1)
  expect(mine(w).entries).toHaveLength(1)
  await ui.unmount()
})

test('with no Git Bash installed, a Bash Run fails, runs nothing, and stays waiting', async ($, on) => {
  const w = world(on)
  refuseQuoting(on)
  await $.tool.call({ tool: 'Bash', command: 'ls -la' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  await w.advance(700)
  await ui.press({ key: `confirm:${id}` })
  expect(w.runs).toHaveLength(0)
  expect(await textOf(ui, /^could not run/)).toBe('could not run:')
  expect(await ui.find({ type: 'Text', text: /Git Bash not found/ })).toBeDefined()
  expect(await textOf(ui, /waiting on the owner$/)).toBe('1 waiting on the owner')
  await ui.unmount()
})

test('a later main-loop success of the same part resolves the entry to Done', async ($, on) => {
  const w = world(on)
  refuse(on, command => (command.includes('&&') ? SWITCH_REFUSAL : undefined))
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  expect(mine(w).entries).toHaveLength(1)
  // A subagent's success does not count, nor does a different command.
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_PART, agentId: 'agent-1' } as never)
  await $.tool.call({ tool: 'PowerShell', command: 'git switch feature-xy' })
  await w.settle()
  expect(mine(w).entries).toHaveLength(1)
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_PART })
  await w.settle()
  expect(mine(w).entries).toHaveLength(0)
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /waiting on the owner$/)).toBe('0 waiting on the owner')
  await ui.press({ key: 'done:toggle' })
  expect(await textOf(ui, /^Resolved /)).toBe('Resolved 0s ago: it later ran fine in this session.')
  await ui.unmount()
})

test('a later success that only quotes the part, or ran elsewhere, resolves nothing', async ($, on) => {
  let cwd = CWD
  const w = world(on, { cwd: () => cwd })
  refuse(on, command => (command.includes('&&') ? SWITCH_REFUSAL : undefined))
  await $.tool.call({ tool: 'Bash', command: SWITCH_LINE })
  await w.settle()
  await $.tool.call({ tool: 'Bash', command: `echo "next; ${SWITCH_PART};"` })
  await $.tool.call({ tool: 'Bash', command: `# ${SWITCH_PART}` })
  cwd = 'C:\\work\\elsewhere'
  await $.tool.call({ tool: 'Bash', command: SWITCH_PART })
  await w.settle()
  expect(mine(w).entries).toHaveLength(1)
})

test('a question too long for one Text still draws, cut', async ($, on) => {
  const w = world(on)
  let answer: (() => void) | undefined
  const gate = new Promise<void>(resolve => {
    answer = resolve
  })
  on('tool.call', { tool: 'AskUserQuestion' }, async () => {
    await gate
    return { result: { questions: [], answers: {} }, text: 'answered' }
  })
  const option = { label: 'x'.repeat(100), description: 'y'.repeat(300) }
  const question = { header: 'h'.repeat(60), question: 'q'.repeat(1000), multiSelect: false, options: [option, option, option, option, option, option] }
  const call = $.tool.call({ tool: 'AskUserQuestion', questions: [question, question, question, question] })
  await w.settle()
  const ui = await $.ui.mount(MOUNT)
  const shown = await textOf(ui, /^\[h+\] /)
  expect((shown ?? '').length).toBeLessThanOrEqual(6006)
  expect(shown).toEndWith(' [cut]')
  await ui.unmount()
  answer?.()
  await call
})

test('a reload marks a Run the old module was waiting on as failed, not running', async ($, on) => {
  const w = world(on, { hang: true })
  refuseAll(on, SWITCH_REFUSAL)
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  await w.advance(700)
  void ui.press({ key: `confirm:${id}` })
  await w.settle()
  expect(await textOf(ui, /^running:/)).toBe('running:')
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  expect(await textOf(ui, /^could not run/)).toBe('could not run:')
  expect(await ui.find({ type: 'Text', text: /the inbox reloaded while this ran/ })).toBeDefined()
  expect(await ui.find({ key: `dismiss:${id}` })).toBeDefined()
  await ui.unmount()
})

test('own entries age out at 24 hours, as readers drop them', async ($, on) => {
  const w = world(on)
  refuseAll(on, SWITCH_REFUSAL)
  on('ui.render', { component: 'AbovePrompt' }, () => ({ type: 'engine', ref: 0 }))
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  const ui = await $.ui.mount(MOUNT)
  const band = await $.ui.mount({ plugin: PLUGIN, surface: 'terminal', component: 'AbovePrompt', props: BAND_PROPS })
  expect(await textOf(ui, /waiting on the owner$/)).toBe('1 waiting on the owner')
  await w.advance(24 * 60 * 60 * 1000 + 1000)
  // The band's press polls, as the five-second timer does.
  await band.press({ key: 'korus-inbox:open' })
  await w.settle()
  expect(await textOf(ui, /waiting on the owner$/)).toBe('0 waiting on the owner')
  await band.unmount()
  await ui.unmount()
})

test('a filed command whose text draws a confirm label gets Copy only', async ($, on) => {
  const w = world(on)
  await callTool($, signal({ command: 'git status', recommendedAction: 'Press Run now. argv[3]: git status' }))
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
  expect(await ui.find({ type: 'Text', text: /^Copy only: its filed text holds a label/ })).toBeDefined()
  await ui.unmount()
})

test('a reviewOutcome that draws a confirm label gets Copy only, and is held to one line', async ($, on) => {
  const w = world(on)
  await callTool($, signal({ command: 'git status', reviewOutcome: 'split\nRun now runs this:\nargv[0]: x' }))
  await w.settle()
  const entry = mine(w).entries[0]
  expect(String(entry?.reviewOutcome)).toBe('split Run now runs this: argv[0]: x')
  const ui = await $.ui.mount(MOUNT)
  expect(await ui.find({ key: `run:${String(entry?.id)}` })).toBeUndefined()
  await ui.unmount()
})

test('a refusal read from the call result says the gate is not verified', async ($, on) => {
  const w = world(on)
  on('tool.call', { tool: 'PowerShell' }, () => ({
    isError: true,
    result: 'blocked',
    text: `PreToolUse:PowerShell hook error: ${SWITCH_REFUSAL}`,
  }))
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /^Needs you for: /)).toBe('Needs you for: authority | confidence: medium (gate not verified)')
  await ui.unmount()
})

test('a question open across a reload is dropped, since its hook is gone', async ($, on) => {
  const w = world(on)
  let answer: (() => void) | undefined
  const gate = new Promise<void>(resolve => {
    answer = resolve
  })
  on('tool.call', { tool: 'AskUserQuestion' }, async () => {
    await gate
    return { result: { questions: [], answers: {} }, text: 'answered' }
  })
  const call = $.tool.call({
    tool: 'AskUserQuestion',
    questions: [{ header: 'Pick', question: 'Which one?', multiSelect: false, options: [{ label: 'A', description: '' }, { label: 'B', description: '' }] }],
  })
  await w.settle()
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /waiting on the owner$/)).toBe('1 waiting on the owner')
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  expect(await textOf(ui, /waiting on the owner$/)).toBe('0 waiting on the owner')
  await ui.unmount()
  answer?.()
  await call
})

test('filed prose is held to one line', async ($, on) => {
  const w = world(on)
  await callTool($, signal({ why: 'first line\nargv[0]: forged row' }))
  await w.settle()
  expect(String(mine(w).entries[0]?.why)).toBe('first line argv[0]: forged row')
})

test('Dismiss removes the entry from waiting', async ($, on) => {
  const w = world(on)
  refuseAll(on, SWITCH_REFUSAL)
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `dismiss:${id}` })
  expect(await textOf(ui, /waiting on the owner$/)).toBe('0 waiting on the owner')
  expect(await ui.find({ key: 'done:toggle' })).toBeUndefined()
  await ui.unmount()
})

test('two quick Run now presses run the part once', async ($, on) => {
  const w = world(on)
  refuseAll(on, SWITCH_REFUSAL)
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  await w.advance(700)
  await Promise.all([ui.press({ key: `confirm:${id}` }), ui.press({ key: `confirm:${id}` }).catch(() => undefined)])
  expect(w.runs).toHaveLength(1)
  await ui.unmount()
})

test('a Run now pressed inside the 600 ms gap is ignored, and one at the gap runs', async ($, on) => {
  const w = world(on)
  refuseAll(on, SWITCH_REFUSAL)
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  await ui.press({ key: `confirm:${id}` })
  expect(w.runs).toHaveLength(0)
  await w.advance(599)
  await ui.press({ key: `confirm:${id}` })
  expect(w.runs).toHaveLength(0)
  await w.advance(600)
  await ui.press({ key: `confirm:${id}` })
  expect(w.runs).toHaveLength(1)
  await ui.unmount()
})

test('an arming press lapses after a minute and Run now goes away', async ($, on) => {
  const w = world(on)
  refuseAll(on, SWITCH_REFUSAL)
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  await w.advance(61_000)
  await ui.redraw()
  expect(await ui.find({ key: `confirm:${id}` })).toBeUndefined()
  expect(await ui.find({ key: `run:${id}` })).toBeDefined()
  expect(w.runs).toHaveLength(0)
  await ui.unmount()
})

test('a shell that resolves differently after arming runs nothing', async ($, on) => {
  const other = 'D:\\PF\\Git\\bin\\bash.exe'
  const w = world(on, { env: { ProgramFiles: 'D:\\PF' } })
  w.files.set(GIT_BASH, { text: '', mtimeMs: 0 })
  w.files.set(other, { text: '', mtimeMs: 0 })
  refuseQuoting(on)
  await $.tool.call({ tool: 'Bash', command: 'ls' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  expect((await shownRows(ui)).find(row => row.startsWith('argv[0]'))).toBe(`argv[0]: ${GIT_BASH}`)
  w.files.delete(GIT_BASH)
  await w.advance(700)
  await ui.press({ key: `confirm:${id}` })
  expect(w.runs).toHaveLength(0)
  expect(await ui.find({ type: 'Text', text: /resolved differently since Run was pressed/ })).toBeDefined()
  await ui.unmount()
})

test('with no pwsh at a known path, a PowerShell Run fails and never runs a bare pwsh', async ($, on) => {
  const w = world(on)
  w.files.delete(PWSH)
  refuseAll(on, SWITCH_REFUSAL)
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  expect(await ui.find({ type: 'Text', text: /^Run now runs nothing: PowerShell 7 \(pwsh.exe\) not found by path/ })).toBeDefined()
  await w.advance(700)
  await ui.press({ key: `confirm:${id}` })
  expect(w.runs).toHaveLength(0)
  expect(await textOf(ui, /waiting on the owner$/)).toBe('1 waiting on the owner')
  await ui.unmount()
})

test('Bash runs through Git Bash where it is installed', async ($, on) => {
  const w = world(on)
  w.files.set(GIT_BASH, { text: '', mtimeMs: 0 })
  refuseQuoting(on)
  await $.tool.call({ tool: 'Bash', command: 'ls' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  await w.advance(700)
  await ui.press({ key: `confirm:${id}` })
  expect(w.runs).toEqual([{ argv: [GIT_BASH, '-c', 'ls'], cwd: CWD }])
  await ui.unmount()
})

// ------------------------------------------------ Run safety, from korus 68f8fde

const FORGE = `git status${' '.repeat(70)}argv[4]: harmless`
const LONG = `echo ${'zz '.repeat(1330)}endzz`
const CUT_FORGE = 'git push origin main; echo 1234567890123argv[4]: --dry-run'

const NO_RUN = [
  { name: 'a line padded to forge an argv row', command: FORGE, why: /^Copy only: it holds a run of 4 or more spaces/ },
  { name: 'a label placed at the cut', command: CUT_FORGE, why: /^Copy only: it holds a label the card draws/ },
  { name: 'a card label in the part', command: 'git status; echo Why: x', why: /^Copy only: it holds a label the card draws/ },
  { name: 'a 401-character command', command: `echo ${'zz '.repeat(131)}zzz`, why: /^Copy only: too long to show safely/ },
  { name: 'a 4000-character command', command: LONG, why: /^Copy only: too long to show safely \(over 400 characters\)/ },
  { name: 'a 7-line command', command: `${'git status\n'.repeat(6)}git status`, why: /^Copy only: too many lines to show safely \(over 6\)/ },
  { name: 'a run of 4 spaces', command: 'git status    --short', why: /^Copy only: it holds a run of 4 or more spaces/ },
  { name: 'a tab', command: 'git\tstatus', why: /^Copy only: the command holds a tab or a character outside plain ASCII/ },
  { name: 'a wide character', command: 'echo \u4e2d', why: /^Copy only: the refusal does not quote/ },
  { name: 'a line ending in a space', command: 'git status \nls', why: /^Copy only: a line ends in a space/ },
  { name: 'a character the screen strips', command: 'Remove-Item\u000b-Recurse C:\\x', why: /^Copy only: the refusal does not quote/ },
] as const

for (const surface of SURFACES) {
  for (const one of NO_RUN) {
    test(`${one.name} gets Copy and no Run, on ${surface}`, async ($, on) => {
      const w = world(on)
      refuseQuoting(on)
      await $.tool.call({ tool: 'PowerShell', command: one.command })
      await w.settle()
      const entry = mine(w).entries[0]
      expect(entry?.command).toBe(one.command.replace('\u000b', ''))
      const id = String(entry?.id)
      const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'Pane', requestId: PLUGIN, props: PANE_PROPS })
      expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
      expect(await ui.find({ type: 'Text', text: one.why })).toBeDefined()
      await ui.press({ key: `run:${id}` }).catch(() => undefined)
      await w.advance(700)
      await ui.press({ key: `confirm:${id}` }).catch(() => undefined)
      expect(w.runs).toHaveLength(0)
      await ui.press({ key: `copy:${id}` })
      // Copy puts the cleaned text on the clipboard, as the card shows it.
      expect(w.copies).toEqual([one.command.replace('\u000b', '')])
      await ui.unmount()
    })
  }
}

const AT_EDGE = [
  { name: 'exactly 400 characters', command: `echo ${'zz '.repeat(131)}zz` },
  { name: 'exactly 6 lines', command: `${'git status\n'.repeat(5)}git status` },
  { name: 'a run of 3 spaces', command: 'git status   --short' },
] as const

for (const one of AT_EDGE) {
  test(`a command of ${one.name} still gets Run`, async ($, on) => {
    const w = world(on)
    refuseQuoting(on)
    await $.tool.call({ tool: 'PowerShell', command: one.command })
    await w.settle()
    const id = String(mine(w).entries[0]?.id)
    const ui = await $.ui.mount(MOUNT)
    await ui.press({ key: `run:${id}` })
    await w.advance(700)
    await ui.press({ key: `confirm:${id}` })
    expect(w.runs).toEqual([{ argv: [PWSH, '-NoProfile', '-Command', one.command], cwd: CWD }])
    await ui.unmount()
  })
}

test('the 400-character edge is exactly 400, and the 401 case one more', () => {
  expect(AT_EDGE[0].command).toHaveLength(400)
  expect(`echo ${'zz '.repeat(131)}zzz`).toHaveLength(401)
})

const NO_FULL_PATH = [
  { name: 'session.cwd() fails', opts: { cwdFails: true } },
  { name: 'the cwd is relative', opts: { cwd: 'work\\repo' } },
  { name: 'the cwd is rooted on the current Windows drive only', opts: { cwd: '/work/repo' } },
  { name: 'the cwd is a share path', opts: { cwd: '\\\\server\\share' } },
] as const

for (const one of NO_FULL_PATH) {
  test(`Run is not offered and Copy still works when ${one.name}`, async ($, on) => {
    const w = world(on, one.opts)
    refuseQuoting(on)
    await $.tool.call({ tool: 'PowerShell', command: 'git push origin main' })
    await w.settle()
    const id = String(mine(w).entries[0]?.id)
    const ui = await $.ui.mount(MOUNT)
    expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: 'Copy only: the session folder is not known as a full path.' })).toBeDefined()
    await ui.press({ key: `copy:${id}` })
    expect(w.copies).toEqual(['git push origin main'])
    await ui.unmount()
  })
}

test('a folder holding a run of 4 spaces is Copy only, with its own reason', async ($, on) => {
  const w = world(on, { cwd: 'C:\\My    Projects' })
  refuseQuoting(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git status' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
  expect(await ui.find({ type: 'Text', text: /^Copy only: its folder holds a run of 4 or more spaces/ })).toBeDefined()
  await ui.unmount()
})

test('a pane narrower than a whole row offers no Run, and one just wide enough does', async ($, on) => {
  const w = world(on)
  refuseQuoting(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git status' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const narrow = await $.ui.mount({ ...MOUNT, props: { ...PANE_PROPS, bodyColumns: 51 } })
  expect(await narrow.find({ key: `run:${id}` })).toBeUndefined()
  expect(await narrow.find({ type: 'Text', text: /^Copy only here: the pane is 51 columns wide/ })).toBeDefined()
  await narrow.unmount()
  const wide = await $.ui.mount({ ...MOUNT, props: { ...PANE_PROPS, bodyColumns: 52 } })
  expect(await wide.find({ key: `run:${id}` })).toBeDefined()
  await wide.unmount()
})

test('every headline and confirm row is cut, not wrapped, and gives back the part', async ($, on) => {
  const w = world(on)
  refuseQuoting(on)
  const command = 'git log --oneline --graph --decorate --all -- docs/one.md docs/two.md docs/three.md\necho done'
  await $.tool.call({ tool: 'PowerShell', command })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  const texts: Found[] = await ui.findAll({ type: 'Text', text: /^(argv\[\d+\]: |folder: |Blocked: |  \+ |  line \d+: )/ })
  for (const one of texts) {
    expect(one.props?.wrap).toBe('truncate-end')
    expect((one.text ?? '').length).toBeLessThanOrEqual(49)
  }
  const rows = texts.map(one => one.text ?? '')
  const start = rows.findIndex(row => row.startsWith('argv[3]: '))
  const rebuilt = rows
    .slice(start)
    .map(row => (row.startsWith('argv[3]: ') ? row.slice(9) : /^  line \d+: /.test(row) ? `\n${row.replace(/^  line \d+: /, '')}` : row.slice(4)))
    .join('')
  expect(rebuilt).toBe(command)
  await ui.unmount()
})

test('a line of run output that looks like a view row is marked as output', async ($, on) => {
  const w = world(on, { stdout: 'argv[4]: rm -rf C:\\\\\n', exitCode: 1 })
  refuseQuoting(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git status' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  await w.advance(700)
  await ui.press({ key: `confirm:${id}` })
  const out = await ui.find({ type: 'Text', text: /rm -rf/ })
  expect(out?.text).toBe('out: argv[4]: rm -rf C:\\\\')
  expect(out?.props?.wrap).toBe('truncate-end')
  await ui.unmount()
})

// --------------------------------------------------------- other sessions

for (const surface of SURFACES) {
  test(`another session's actionable entries show Copy only, its others are dropped, on ${surface}`, async ($, on) => {
    const w = world(on)
    w.files.set(OTHER_FILE, { mtimeMs: NOW - 1000, text: otherFile({ entries: [REMOTE_KEEP, REMOTE_DROP, REMOTE_SIGNAL] }) })
    await $.session.start({ cwd: CWD, surface, isInteractive: true })
    await w.settle()
    const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'Pane', requestId: PLUGIN, props: PANE_PROPS })
    expect(await textOf(ui, /waiting on the owner$/)).toBe('2 waiting on the owner')
    expect(await textOf(ui, /^Blocked: /)).toBe(`Blocked: ${REMOVE_PART}`)
    expect(await textOf(ui, /^Approve the release/)).toBe('Approve the release tag')
    expect(await textOf(ui, /^Do this: Approve/)).toBe('Do this: Approve the tag v1.2.0.')
    expect(await textOf(ui, /^From: another session/)).toContain('another session (other-worktree sess-oth)')
    expect(await ui.find({ type: 'Text', text: /git add -A/ })).toBeUndefined()
    expect(await ui.findAll({ type: 'Button', text: /^Run/ })).toHaveLength(0)
    await ui.press({ key: 'rcopy:sess-other-2:e1' })
    expect(w.copies).toEqual([REMOVE_PART])
    await ui.press({ key: 'rdismiss:sess-other-2:e1' })
    expect(await textOf(ui, /waiting on the owner$/)).toBe('1 waiting on the owner')
    expect(mine(w).dismissed).toEqual(['sess-other-2:e1'])
    await ui.unmount()
  })
}

test('a reader drops a session it had cached once that session writes its ended file', async ($, on) => {
  const w = world(on)
  w.files.set(OTHER_FILE, { mtimeMs: NOW - 1000, text: otherFile({ entries: [REMOTE_SIGNAL] }) })
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /waiting on the owner$/)).toBe('1 waiting on the owner')
  w.files.set(OTHER_FILE, { mtimeMs: NOW + 1000, text: otherFile({ ended: true, updatedAt: NOW + 1000 }) })
  await w.advance(5000)
  expect(await textOf(ui, /waiting on the owner$/)).toBe('0 waiting on the owner')
  await ui.unmount()
})

test('a session end writes an ended file that other panes skip', async ($, on) => {
  const w = world(on)
  refuseAll(on, SWITCH_REFUSAL)
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  await $.session.end({ reason: 'prompt_input_exit', sessionId: ME, resume: { id: ME } } as never)
  await w.settle()
  const file = JSON.parse(w.files.get(MY_FILE)?.text ?? '{}') as { ended: boolean; entries: unknown[] }
  expect(file.ended).toBe(true)
  expect(file.entries).toHaveLength(0)
})

// ----------------------------------------------------------------- the band

for (const surface of SURFACES) {
  test(`the band is absent while nothing waits, on ${surface}`, async ($, on) => {
    const w = world(on)
    on('ui.render', { component: 'AbovePrompt' }, () => ({ type: 'engine', ref: 0 }))
    await $.session.start({ cwd: CWD, surface, isInteractive: true })
    await w.settle()
    const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'AbovePrompt', props: BAND_PROPS })
    expect(await ui.findAll({ type: 'Button' })).toHaveLength(0)
    await ui.unmount()
  })

  test(`the band shows inbox N, hotkey i, and its press opens the pane, on ${surface}`, async ($, on) => {
    const w = world(on)
    refuseAll(on, SWITCH_REFUSAL)
    on('ui.render', { component: 'AbovePrompt' }, () => ({ type: 'engine', ref: 0 }))
    await $.session.start({ cwd: CWD, surface, isInteractive: true })
    await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
    await w.settle()
    const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'AbovePrompt', props: BAND_PROPS })
    const button = await ui.find({ type: 'Button', key: 'korus-inbox:open' })
    expect(button?.text).toBe('inbox 1')
    expect(button?.props.hotkey).toBe('i')
    expect(w.opens).toHaveLength(0)
    await ui.press({ key: 'korus-inbox:open' })
    await w.settle()
    expect(w.opens).toEqual([PLUGIN])
    await ui.unmount()
  })

  test(`the band yields to a survey, on ${surface}`, async ($, on) => {
    const w = world(on)
    refuseAll(on, SWITCH_REFUSAL)
    on('ui.render', { component: 'AbovePrompt' }, () => ({ type: 'engine', ref: 0 }))
    await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
    await w.settle()
    const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'AbovePrompt', props: { ...BAND_PROPS, hasSurvey: true } })
    expect(await ui.findAll({ type: 'Button' })).toHaveLength(0)
    await ui.unmount()
  })
}

test('the band draws first, above a band another hook drew', async ($, on) => {
  const w = world(on)
  refuseAll(on, SWITCH_REFUSAL)
  on('ui.render', { component: 'AbovePrompt' }, ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>another band</Text>
  })
  const ui = await $.ui.mount({ plugin: PLUGIN, surface: 'terminal', component: 'AbovePrompt', props: BAND_PROPS })
  expect(await ui.drawn()).toMatchObject({ type: 'Text', children: ['another band'] })
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  const kids = ((await ui.drawn()) as { children?: { type: string }[] }).children ?? []
  expect(kids.map(kid => kid.type)).toEqual(['Button', 'Text'])
  await ui.unmount()
})

// ------------------------------------------- Run safety kept from #197

test('a press keyed to one entry runs that entry after a newer row shifts the list', async ($, on) => {
  const w = world(on)
  refuseQuoting(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git push origin first' })
  await w.settle()
  const first = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${first}` })
  await w.advance(1000)
  await $.tool.call({ tool: 'PowerShell', command: 'git push origin second' })
  await w.settle()
  await ui.press({ key: `confirm:${first}` })
  expect(w.runs).toEqual([{ argv: [PWSH, '-NoProfile', '-Command', 'git push origin first'], cwd: CWD }])
  await ui.unmount()
})

test('a held Enter on Run now, repeating every 100 ms, never runs the command', async ($, on) => {
  const w = world(on)
  refuseQuoting(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git push origin main' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  for (let i = 0; i < 20; i++) {
    await ui.press({ key: `confirm:${id}` })
    await w.advance(100)
  }
  expect(w.runs).toHaveLength(0)
  expect(await ui.find({ key: `confirm:${id}` })).toBeDefined()
  await ui.unmount()
})

test('ignored Run now presses do not keep the arm alive past its minute', async ($, on) => {
  const w = world(on)
  refuseQuoting(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git push origin main' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  for (let i = 0; i < 122; i++) {
    await w.advance(500)
    await ui.press({ key: `confirm:${id}` }).catch(() => undefined)
  }
  await ui.redraw()
  expect(w.runs).toHaveLength(0)
  expect(await ui.find({ key: `confirm:${id}` })).toBeUndefined()
  expect(await ui.find({ key: `run:${id}` })).toBeDefined()
  await ui.unmount()
})

test('Cancel clears the shown argv and Run now', async ($, on) => {
  const w = world(on)
  refuseQuoting(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git push origin main' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  expect(await ui.find({ type: 'Text', text: /^argv\[0\]/ })).toBeDefined()
  await ui.press({ key: `cancel:${id}` })
  expect(await ui.find({ type: 'Text', text: /^argv\[0\]/ })).toBeUndefined()
  expect(await ui.find({ key: `confirm:${id}` })).toBeUndefined()
  await w.advance(700)
  await ui.press({ key: `confirm:${id}` }).catch(() => undefined)
  expect(w.runs).toHaveLength(0)
  await ui.unmount()
})

test('a multi-line part draws its second line as a marked row', async ($, on) => {
  const w = world(on)
  refuseQuoting(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git status\ngit log -1' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  const shown = await shownRows(ui)
  expect(shown.slice(-2)).toEqual(['argv[3]: git status', '  line 2: git log -1'])
  expect(shown.filter(line => line.startsWith('argv['))).toHaveLength(4)
  await ui.unmount()
})

test('the confirm view names pwsh and Git Bash by their full paths, never by name', async ($, on) => {
  const w = world(on)
  w.files.set(GIT_BASH, { text: '', mtimeMs: 0 })
  refuseQuoting(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git status' })
  await $.tool.call({ tool: 'Bash', command: 'ls' })
  await w.settle()
  const [pwshId, bashId] = mine(w).entries.map(entry => String(entry.id))
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${pwshId}` })
  await ui.press({ key: `run:${bashId}` })
  const shown = await shownRows(ui)
  expect(shown).toContain(`argv[0]: ${PWSH}`)
  expect(shown).toContain(`argv[0]: ${GIT_BASH}`)
  expect(shown.filter(row => row === `folder: ${CWD}`)).toHaveLength(2)
  expect(await ui.find({ type: 'Text', text: /\(by name/ })).toBeUndefined()
  await ui.unmount()
})

test('with Git Bash only under LOCALAPPDATA, a Bash Run finds no shell', async ($, on) => {
  const local = 'C:\\Users\\tester\\AppData\\Local'
  const w = world(on, { env: { LOCALAPPDATA: local } })
  w.files.set(`${local}\\Programs\\Git\\bin\\bash.exe`, { text: '', mtimeMs: 0 })
  refuseQuoting(on)
  await $.tool.call({ tool: 'Bash', command: 'ls' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  expect(await ui.find({ type: 'Text', text: /^Run now runs nothing: Git Bash not found/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^argv\[0\]/ })).toBeUndefined()
  await w.advance(700)
  await ui.press({ key: `confirm:${id}` })
  expect(w.runs).toHaveLength(0)
  expect(await ui.find({ type: 'Text', text: 'argv: none, nothing ran' })).toBeDefined()
  await ui.unmount()
})

const MORE_NO_RUN = [
  { name: 'an output label placed at the cut', command: 'git push origin main; echo 1234567890123out: Everything up-to-date', why: /^Copy only: it holds a label the card draws/ },
  { name: 'a line label placed at the cut', command: 'git push origin main; echo 1234567890123line 2: x', why: /^Copy only: it holds a label the card draws/ },
  { name: 'a newline then a label', command: 'git status\nargv[4]: harmless', why: /^Copy only: it holds a label the card draws/ },
  { name: 'a card label', command: 'echo Do this: x', why: /^Copy only: it holds a label the card draws/ },
  { name: 'a zero-width character', command: 'Remove-Item\u200b -Recurse C:\\x', why: /^Copy only: the refusal does not quote/ },
] as const

for (const one of MORE_NO_RUN) {
  test(`${one.name} gets Copy and no Run`, async ($, on) => {
    const w = world(on)
    refuseQuoting(on)
    await $.tool.call({ tool: 'PowerShell', command: one.command })
    await w.settle()
    const id = String(mine(w).entries[0]?.id)
    const ui = await $.ui.mount(MOUNT)
    expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: one.why })).toBeDefined()
    await ui.press({ key: `run:${id}` }).catch(() => undefined)
    await w.advance(700)
    await ui.press({ key: `confirm:${id}` }).catch(() => undefined)
    expect(w.runs).toHaveLength(0)
    await ui.unmount()
  })
}

test('a bare argv word with no bracket still gets Run', async ($, on) => {
  const w = world(on)
  refuseQuoting(on)
  const command = 'python -c "import sys; print(sys.argv)"'
  await $.tool.call({ tool: 'PowerShell', command })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  await w.advance(700)
  await ui.press({ key: `confirm:${id}` })
  expect(w.runs).toEqual([{ argv: [PWSH, '-NoProfile', '-Command', command], cwd: CWD }])
  await ui.unmount()
})

const MORE_FOLDERS = [
  { name: 'an empty cwd', cwd: '', why: /^Copy only: the session folder is not known as a full path/ },
  { name: 'a zero-width character', cwd: 'C:\\work\\re\u200bpo', why: /^Copy only: its folder holds characters the screen cannot show/ },
  { name: 'a character outside ASCII', cwd: 'C:\\work\\caf\u00e9', why: /^Copy only: its folder holds a tab or a character outside plain ASCII/ },
  { name: 'a label in its name', cwd: 'C:\\work\\out: x', why: /^Copy only: its folder holds a label/ },
] as const

for (const one of MORE_FOLDERS) {
  test(`a folder holding ${one.name} is Copy only, with its own reason`, async ($, on) => {
    const w = world(on, { cwd: one.cwd })
    refuseQuoting(on)
    await $.tool.call({ tool: 'PowerShell', command: 'git status' })
    await w.settle()
    const id = String(mine(w).entries[0]?.id)
    const ui = await $.ui.mount(MOUNT)
    expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: one.why })).toBeDefined()
    expect(await ui.find({ key: `copy:${id}` })).toBeDefined()
    await ui.unmount()
  })
}

// ------------------------------------------ the shared folder, kept from #197

test('a half-written file keeps the last good read rather than dropping the session', async ($, on) => {
  const w = world(on)
  w.files.set(OTHER_FILE, { mtimeMs: NOW - 1000, text: otherFile({ entries: [REMOTE_SIGNAL] }) })
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /waiting on the owner$/)).toBe('1 waiting on the owner')
  w.files.set(OTHER_FILE, { mtimeMs: NOW + 1000, text: '{"format":"korus-inbox/1","entr' })
  await w.advance(5000)
  expect(await textOf(ui, /waiting on the owner$/)).toBe('1 waiting on the owner')
  await ui.unmount()
})

test('a Dismiss pressed in another pane clears this session entry too', async ($, on) => {
  const w = world(on)
  refuseAll(on, SWITCH_REFUSAL)
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /waiting on the owner$/)).toBe('1 waiting on the owner')
  w.files.set(OTHER_FILE, { mtimeMs: NOW + 1000, text: otherFile({ updatedAt: NOW + 1000, dismissed: [`${ME}:${id}`] }) })
  await w.advance(5000)
  expect(await textOf(ui, /waiting on the owner$/)).toBe('0 waiting on the owner')
  expect(mine(w).entries).toHaveLength(0)
  await ui.unmount()
})

test('one file listing an id twice shows it once', async ($, on) => {
  const w = world(on)
  w.files.set(OTHER_FILE, { mtimeMs: NOW - 1000, text: otherFile({ entries: [REMOTE_SIGNAL, REMOTE_SIGNAL] }) })
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /waiting on the owner$/)).toBe('1 waiting on the owner')
  expect(await drawnCards(ui)).toBe(1)
  await ui.unmount()
})

test('a write after the session ended does not bring its file back', async ($, on) => {
  const w = world(on)
  refuseAll(on, SWITCH_REFUSAL)
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  await $.session.end({ reason: 'prompt_input_exit', sessionId: ME, resume: { id: ME } } as never)
  await w.settle()
  await $.tool.call({ tool: 'PowerShell', command: `${SWITCH_LINE} --late` })
  await w.settle()
  const file = JSON.parse(w.files.get(MY_FILE)?.text ?? '{}') as { ended: boolean }
  expect(file.ended).toBe(true)
})

test('a shared refusal is cut to the shared detail limit', async ($, on) => {
  const w = world(on)
  const long = `${SWITCH_REFUSAL}\n${'More words for the reader. '.repeat(100)}`
  refuseAll(on, long)
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  const detail = String(mine(w).entries[0]?.detail)
  expect(detail.length).toBeLessThanOrEqual(1506)
  expect(detail).toEndWith(' [cut]')
  expect(mine(w).entries[0]?.ask).toBeDefined()
})

// ------------------------------------------------------- legacy entries

test('a refused entry an earlier version kept, with no ask, is deleted at load', async ($, on) => {
  const w = world(on)
  refuseAll(on, SWITCH_REFUSAL)
  // The shape version 0.1.0 kept: a refused entry with no `ask` field. It is
  // added to what $.state answers for `own`, as a value kept across a reload.
  const legacy = { id: 'legacy-1', kind: 'refused', createdAt: NOW, shell: 'Bash', command: 'git add -A', cwd: CWD, refusal: 'BLOCKED' }
  let isSeeding = true
  on('state.get', async ($, e, next) => {
    const got = await next(e)
    const name = e as unknown as { plugin?: string; key?: string }
    if (!isSeeding || name.plugin !== PLUGIN || name.key !== 'own') return got
    // The hook answers `{ value: { value, version } }`.
    const read = got.value as { value?: unknown; version: number }
    const value: unknown[] = Array.isArray(read.value) ? read.value : []
    if (value.some(one => (one as { id?: unknown }).id === legacy.id)) return got
    return { ...got, value: { ...read, value: [...value, legacy] } } as typeof got
  })
  // The recording writes the seeded list back, so the legacy entry is kept.
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  isSeeding = false
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /waiting on the owner$/)).toBe('2 waiting on the owner')
  expect(await ui.find({ key: 'dismiss:legacy-1' })).toBeDefined()
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  await ui.redraw()
  expect(await textOf(ui, /waiting on the owner$/)).toBe('1 waiting on the owner')
  expect(await ui.find({ key: 'dismiss:legacy-1' })).toBeUndefined()
  expect(mine(w).entries.map(one => one.id)).not.toContain('legacy-1')
  await ui.unmount()
})
