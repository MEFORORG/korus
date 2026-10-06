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
  timeouts: (number | undefined)[]
  copies: string[]
  opens: string[]
  tools: string[]
  statusCalls: (string | undefined)[]
  settle: () => Promise<void>
  advance: (ms: number) => Promise<void>
}

type WorldOptions = {
  env?: Record<string, string>
  cwd?: string | (() => string)
  cwdFails?: boolean
  stdout?: string
  exitCode?: number
  /** Exit code for one command by its argv; undefined falls back to `exitCode`. */
  exitCodeFor?: (argv: readonly string[]) => number | undefined
  hang?: boolean
  /** Output for one command by its argv; undefined falls back to `stdout`. */
  stdoutFor?: (argv: readonly string[]) => string | undefined
  /** Awaited after a run is recorded, before it returns: holds a run in flight. */
  gate?: (argv: readonly string[]) => Promise<void> | undefined
  /** A machine that is not Windows: HOME only, no ProgramFiles, `/` paths. */
  unix?: boolean
}

const UNIX_HOME = '/opt/tester'
const UNIX_FILE = `${UNIX_HOME}/.korus-inbox/${ME}.json`
const UNIX_CWD = '/work/repo'

// The engine beneath the plugin: an in-memory shared folder, a fixed session,
// a recorded process runner and clipboard. Nothing touches the real disk.
function world(on: On, opts: WorldOptions = {}): World {
  const files = new Map<string, { text: string; mtimeMs: number }>()
  const runs: World['runs'] = []
  const timeouts: World['timeouts'] = []
  const copies: string[] = []
  const opens: string[] = []
  const tools: string[] = []
  const statusCalls: (string | undefined)[] = []
  const clock = mock.clock(on, { now: NOW })
  if (opts.unix === true) {
    mock.env(on, { HOME: UNIX_HOME, ...opts.env })
  } else {
    mock.env(on, { USERPROFILE: HOME, ProgramFiles: 'C:\\Program Files', ...opts.env })
    files.set(PWSH, { text: '', mtimeMs: 0 })
  }
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  on('session.end', ($, e) => ({ sessionId: e.sessionId }))
  on('session.id', () => ({ value: ME }))
  on('session.cwd', () => {
    if (opts.cwdFails === true) throw new Error('no cwd')
    return { value: typeof opts.cwd === 'function' ? opts.cwd() : (opts.cwd ?? (opts.unix === true ? UNIX_CWD : CWD)) }
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
  // A `/` path reaches the hook in the host's spelling, so compare without the drive.
  const bare = (path: string): string => path.replace(/\\/g, '/').replace(/^[A-Za-z]:/, '')
  on('fs.exists', ($, e) => ({ value: files.has(e.path) || [...files.keys()].some(key => bare(key) === bare(e.path)) }))
  on('fs.read', ($, e) => {
    const file = files.get(e.path)
    if (file === undefined) throw new Error('ENOENT')
    return { value: file.text }
  })
  on('fs.list', ($, e) => ({
    value: [...files.entries()]
      .filter(([path]) => path.startsWith(`${e.path}\\`) || path.startsWith(`${e.path}/`))
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
    timeouts.push(e.init?.timeoutMs)
    await opts.gate?.(e.argv)
    return {
      value: {
        exitCode: opts.exitCodeFor?.(e.argv) ?? opts.exitCode ?? 0,
        stdout: opts.stdoutFor?.(e.argv) ?? opts.stdout ?? 'switched fine\n',
        stderr: '',
        isStdoutTruncated: false,
        isStderrTruncated: false,
      },
    }
  })
  return { files, runs, timeouts, copies, opens, tools, statusCalls, settle: clock.settle, advance: clock.advance }
}

// ------------------------------------------------------------- refusal texts

const SWITCH_PART = 'git switch feature-x'
// The part is first on its line: the only place Run is offered for it.
const SWITCH_LINE = `${SWITCH_PART} && git push origin feature-x`

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

// The kit hands a hook the host's spelling of a path, so a `/` path written
// on a Windows host arrives with a drive and backslashes; this finds it either way.
function mine(w: World, path = MY_FILE): { entries: Record<string, unknown>[]; dismissed: string[] } {
  const file =
    w.files.get(path) ?? [...w.files.entries()].find(([key]) => key.replace(/\\/g, '/').endsWith(path.replace(/\\/g, '/')))?.[1]
  if (file === undefined) return { entries: [], dismissed: [] }
  return JSON.parse(file.text) as { entries: Record<string, unknown>[]; dismissed: string[] }
}

const MOUNT = { plugin: PLUGIN, surface: 'terminal', component: 'Pane', requestId: PLUGIN, props: PANE_PROPS } as const

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
    await $.tool.call({ tool: 'PowerShell', command: `${REMOVE_PART} && git status` })
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
  // Two lines joined would read as one different command, so the step names Copy.
  expect(await textOf(ui, /^Do this: /)).toBe(
    'Do this: Run the whole command in a plain terminal: the command Copy gives (Details shows it whole)',
  )
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

// Run is offered for a refusal only when its blocked part is the FIRST command
// on the line, with nothing at all before it. Every other position is Copy
// only, with one reason, and Copy and Do this give the whole command. These
// are the old deny-list's cases and the ones it missed; none needs a word
// list now, so none can be missed by one.
const NOT_FIRST_REASON = 'Copy only: other commands come before this part, so it could run in a different context.'
const NO_PART_REASON = 'Copy only: the refusal does not quote one whole part of this line, so Copy takes the whole line and Run is not offered.'

const NOT_FIRST: readonly { name: string; shell: 'Bash' | 'PowerShell'; command: string; part: string; reason?: string }[] = [
  { name: 'a PowerShell drive change', shell: 'PowerShell', command: 'D:; Remove-Item -Recurse -Force build', part: 'Remove-Item -Recurse -Force build' },
  { name: 'a grep guard joined by &&', shell: 'Bash', command: 'grep -q x f && rm -rf build', part: 'rm -rf build' },
  { name: 'a git-state change joined by &&', shell: 'PowerShell', command: 'git add a && git switch b', part: 'git switch b' },
  { name: 'a test run joined by &&', shell: 'PowerShell', command: 'npm test && npm publish', part: 'npm publish' },
  { name: 'a branch switch joined by &&', shell: 'PowerShell', command: 'git switch other && git push --force', part: 'git push --force' },
  { name: 'a plain && chain', shell: 'PowerShell', command: `git fetch && ${SWITCH_PART}`, part: SWITCH_PART },
  { name: 'a cd joined by &&', shell: 'PowerShell', command: `cd C:\\other && ${SWITCH_PART}`, part: SWITCH_PART },
  { name: 'a cd behind if', shell: 'Bash', command: 'if cd ../prod; then :; fi; git push', part: 'git push' },
  { name: 'a cd in a brace group', shell: 'Bash', command: '{ cd ../prod; }; git push', part: 'git push' },
  { name: 'builtin cd', shell: 'Bash', command: 'builtin cd ../prod; git push', part: 'git push' },
  { name: 'command cd', shell: 'Bash', command: 'command cd ../prod; git push', part: 'git push' },
  { name: 'Set-Location in a script block', shell: 'PowerShell', command: '& { Set-Location ..\\prod }; git push', part: 'git push' },
  { name: 'an environment variable', shell: 'PowerShell', command: '$env:GIT_DIR = "x"; git push', part: 'git push' },
  { name: 'an indexed assignment', shell: 'PowerShell', command: "$PSDefaultParameterValues['*:WhatIf']=$true; Remove-Item -Recurse C:\\data", part: 'Remove-Item -Recurse C:\\data' },
  { name: 'a member assignment', shell: 'PowerShell', command: '$o.Mode = 1; git push', part: 'git push' },
  { name: 'an exit', shell: 'Bash', command: 'exit 0; git push --force', part: 'git push --force' },
  { name: 'printf -v setting a variable', shell: 'Bash', command: 'printf -v d /tmp/build; rm -rf $d/x', part: 'rm -rf $d/x' },
  { name: 'read setting a variable', shell: 'Bash', command: 'read d; git push', part: 'git push' },
  { name: 'Set-Variable', shell: 'PowerShell', command: 'Set-Variable d C:\\proj\\out; Remove-Item -Recurse -Force C:\\proj\\out', part: 'Remove-Item -Recurse -Force C:\\proj\\out' },
  { name: '-OutVariable', shell: 'PowerShell', command: 'Get-ChildItem -OutVariable d; git push', part: 'git push' },
  { name: 'a shortened -OutVar', shell: 'PowerShell', command: 'Get-ChildItem -OutVar d; git push', part: 'git push' },
  { name: 'a compound assignment', shell: 'PowerShell', command: '$x += 1; git push', part: 'git push' },
  { name: 'a Bash append assignment', shell: 'Bash', command: 'd+=x; rm -rf $d', part: 'rm -rf $d' },
  { name: 'a guard joined by ||', shell: 'Bash', command: 'git diff --quiet || git commit -am wip', part: 'git commit -am wip' },
  { name: 'git diff --quiet joined by &&', shell: 'Bash', command: 'git diff --quiet && git commit -am wip', part: 'git commit -am wip' },
  { name: 'a test joined by &&', shell: 'Bash', command: 'test -f lock && rm -rf build', part: 'rm -rf build' },
  { name: 'Get-Item joined by &&', shell: 'PowerShell', command: 'Get-Item lock && Remove-Item build', part: 'Remove-Item build' },
  { name: 'iex', shell: 'PowerShell', command: 'iex "Set-Location ..\\prod"; git push', part: 'git push' },
  { name: 'Set-Alias', shell: 'PowerShell', command: 'Set-Alias git hub; git push', part: 'git push' },
  { name: 'Import-Module', shell: 'PowerShell', command: 'Import-Module .\\tools.psm1; git push', part: 'git push' },
  { name: 'a line ender', shell: 'Bash', command: 'kill $$; git push', part: 'git push' },
  { name: 'Stop-Process', shell: 'PowerShell', command: 'Stop-Process -Id $PID; git push', part: 'git push' },
  { name: 'a pipe feeding it', shell: 'PowerShell', command: 'echo y | git switch feature-x', part: 'git switch feature-x' },
  { name: 'a later copy after the part opens the line as a longer word', shell: 'Bash', command: 'git push --dry-run; cd ../prod && git push', part: 'git push', reason: NO_PART_REASON },
]

for (const surface of SURFACES) {
  for (const one of NOT_FIRST) {
    test(`a part after ${one.name} is Copy only, and Copy and Do this give the whole line, on ${surface}`, async ($, on) => {
      const w = world(on)
      refuseAll(on, `BLOCKED: '${one.part}' needs the person. Do it from a PLAIN terminal.`)
      await $.tool.call({ tool: one.shell, command: one.command })
      await w.settle()
      const id = String(mine(w).entries[0]?.id)
      const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'Pane', requestId: PLUGIN, props: PANE_PROPS })
      expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
      expect(await ui.find({ type: 'Text', text: one.reason ?? NOT_FIRST_REASON })).toBeDefined()
      expect(await textOf(ui, /^Blocked: /)).toBe(`Blocked: ${one.command}`)
      expect(await textOf(ui, /^Do this: /)).toBe(`Do this: Run the whole command in a plain terminal: ${one.command}`)
      await ui.press({ key: `run:${id}` }).catch(() => undefined)
      await w.advance(700)
      await ui.press({ key: `confirm:${id}` }).catch(() => undefined)
      expect(w.runs).toHaveLength(0)
      await ui.press({ key: `copy:${id}` })
      expect(w.copies).toEqual([one.command])
      await ui.unmount()
    })
  }

  test(`a part after a cd gives the whole line to Copy and Do this, never the bare part, on ${surface}`, async ($, on) => {
    const w = world(on)
    refuseAll(on, SWITCH_REFUSAL)
    const command = `cd C:\\other && ${SWITCH_PART}`
    await $.tool.call({ tool: 'PowerShell', command })
    await w.settle()
    const id = String(mine(w).entries[0]?.id)
    const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'Pane', requestId: PLUGIN, props: PANE_PROPS })
    expect(await textOf(ui, /^Blocked: /)).toBe(`Blocked: ${command}`)
    expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: NOT_FIRST_REASON })).toBeDefined()
    expect(await textOf(ui, /^Do this: /)).toBe(`Do this: Run the whole command in a plain terminal: ${command}`)
    expect(await textOf(ui, /^Copy takes the whole command/)).toBe('Copy takes the whole command, not the blocked part alone.')
    await ui.press({ key: `copy:${id}` })
    expect(w.copies).toEqual([command])
    await ui.unmount()
  })

  test(`a first-position git switch b keeps Run, and Run gets exactly the part, on ${surface}`, async ($, on) => {
    const w = world(on)
    refuseAll(on, "BLOCKED: 'git switch b' needs the person. Do it from a PLAIN terminal.")
    await $.tool.call({ tool: 'PowerShell', command: 'git switch b' })
    await $.tool.call({ tool: 'PowerShell', command: 'git switch b && git push origin b' })
    await w.settle()
    const ids = mine(w).entries.map(entry => String(entry.id))
    const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'Pane', requestId: PLUGIN, props: PANE_PROPS })
    for (const id of ids) {
      await ui.press({ key: `run:${id}` })
      await w.advance(700)
      await ui.press({ key: `confirm:${id}` })
    }
    expect(w.runs).toEqual([
      { argv: [PWSH, '-NoProfile', '-Command', 'git switch b'], cwd: CWD },
      { argv: [PWSH, '-NoProfile', '-Command', 'git switch b'], cwd: CWD },
    ])
    await ui.unmount()
  })

  test(`the 3952-character crafted line from the review renders fast, and is Copy only, on ${surface}`, async ($, on) => {
    const w = world(on)
    // The line that took the removed deny-list 5772 ms in node 22.
    const crafted = `${'$'.repeat(1976)}${'-'.repeat(1976)}`
    expect(crafted).toHaveLength(3952)
    const command = `${crafted}; git push`
    refuseAll(on, "BLOCKED: 'git push' needs the person. Do it from a PLAIN terminal.")
    await $.tool.call({ tool: 'PowerShell', command })
    await w.settle()
    const id = String(mine(w).entries[0]?.id)
    expect(mine(w).entries[0]?.command).toBe(command)
    const started = performance.now()
    const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'Pane', requestId: PLUGIN, props: PANE_PROPS })
    await ui.press({ key: `run:${id}` }).catch(() => undefined)
    await ui.redraw()
    // Generous: the removed regex alone took over 5 seconds on this line.
    expect(performance.now() - started).toBeLessThan(1000)
    expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: NOT_FIRST_REASON })).toBeDefined()
    await ui.unmount()
  })
}

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

for (const surface of SURFACES) {
  test(`on Windows a Bash refusal is Copy only, even with Git Bash installed, on ${surface}`, async ($, on) => {
    const w = world(on)
    w.files.set('C:\\Program Files\\Git\\bin\\bash.exe', { text: '', mtimeMs: 0 })
    refuseQuoting(on)
    await $.tool.call({ tool: 'Bash', command: 'ls -la' })
    await w.settle()
    const id = String(mine(w).entries[0]?.id)
    const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'Pane', requestId: PLUGIN, props: PANE_PROPS })
    expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: /^Copy only: on Windows, Run is offered only for PowerShell/ })).toBeDefined()
    await ui.press({ key: `run:${id}` }).catch(() => undefined)
    await w.advance(700)
    await ui.press({ key: `confirm:${id}` }).catch(() => undefined)
    expect(w.runs).toHaveLength(0)
    await ui.press({ key: `copy:${id}` })
    expect(w.copies).toEqual(['ls -la'])
    await ui.unmount()
  })
}

test('off Windows, with no bash at a known path, a Bash Run fails, runs nothing, and stays waiting', async ($, on) => {
  const w = world(on, { unix: true })
  refuseQuoting(on)
  await $.tool.call({ tool: 'Bash', command: 'ls -la' })
  await w.settle()
  const id = String(mine(w, UNIX_FILE).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  await w.advance(700)
  await ui.press({ key: `confirm:${id}` })
  expect(w.runs).toHaveLength(0)
  expect(await textOf(ui, /^could not run/)).toBe('could not run:')
  expect(await ui.find({ type: 'Text', text: /bash not found/ })).toBeDefined()
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
  const w = world(on, { unix: true })
  w.files.set('/bin/bash', { text: '', mtimeMs: 0 })
  w.files.set('/usr/bin/bash', { text: '', mtimeMs: 0 })
  refuseQuoting(on)
  await $.tool.call({ tool: 'Bash', command: 'ls' })
  await w.settle()
  const id = String(mine(w, UNIX_FILE).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  expect((await shownRows(ui)).find(row => row.startsWith('argv[0]'))).toBe('argv[0]: /bin/bash')
  w.files.delete('/bin/bash')
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

test('off Windows, Bash keeps Run, through /bin/bash by path', async ($, on) => {
  const w = world(on, { unix: true })
  w.files.set('/bin/bash', { text: '', mtimeMs: 0 })
  refuseQuoting(on)
  await $.tool.call({ tool: 'Bash', command: 'ls' })
  await w.settle()
  const id = String(mine(w, UNIX_FILE).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  await w.advance(700)
  await ui.press({ key: `confirm:${id}` })
  expect(w.runs).toEqual([{ argv: ['/bin/bash', '-c', 'ls'], cwd: UNIX_CWD }])
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
    // Its part is not first on its line, so the card names the whole line.
    expect(await textOf(ui, /^Blocked: /)).toBe(`Blocked: ${REMOTE_KEEP.command}`)
    expect(await textOf(ui, /^Do this: Confirm/)).toBe(
      `Do this: Confirm it is not in use, then run the whole command in a plain terminal: ${REMOTE_KEEP.command}`,
    )
    expect(await textOf(ui, /^Approve the release/)).toBe('Approve the release tag')
    expect(await textOf(ui, /^Do this: Approve/)).toBe('Do this: Approve the tag v1.2.0.')
    expect(await textOf(ui, /^From: another session/)).toContain('another session (other-worktree sess-oth)')
    expect(await ui.find({ type: 'Text', text: /git add -A/ })).toBeUndefined()
    expect(await ui.findAll({ type: 'Button', text: /^Run/ })).toHaveLength(0)
    await ui.press({ key: 'rcopy:sess-other-2:e1' })
    expect(w.copies).toEqual([REMOTE_KEEP.command])
    await ui.press({ key: 'rdismiss:sess-other-2:e1' })
    expect(await textOf(ui, /waiting on the owner$/)).toBe('1 waiting on the owner')
    expect(mine(w).dismissed).toEqual(['sess-other-2:e1'])
    await ui.unmount()
  })
}

// ------------------------------------------------------ the session's title

const RENAME = 'mcp__ccd_session_mgmt__set_session_title'
const QUESTION = {
  tool: 'AskUserQuestion',
  questions: [{ header: 'Pick', question: 'Which one?', multiSelect: false, options: [{ label: 'A', description: '' }, { label: 'B', description: '' }] }],
} as const

type Kit = Parameters<Parameters<typeof test>[1]>[0]
type HookResult = Record<string, unknown>

function ownTitle(w: World): unknown {
  const file = w.files.get(MY_FILE)
  return file === undefined ? undefined : (JSON.parse(file.text) as { title?: unknown }).title
}

// The bottom of the classic chains the title arrives on, and of the rename
// tool, registered before the test first calls $. `result` is what a hook
// beneath returns on each classic event.
function titleHooks(on: On, rename: () => boolean = () => true, result: () => HookResult = () => ({})): void {
  on('classic.SessionStart', result)
  on('classic.UserPromptSubmit', result)
  on('tool.call', { tool: RENAME }, () => (rename() ? { result: 'ok', text: 'ok' } : { isError: true, result: 'declined', text: 'declined' }))
}

// One waiting entry, so this session's file is written at all.
async function withOwnEntry($: Kit, on: On, rename?: () => boolean, result?: () => HookResult): Promise<World> {
  const w = world(on)
  refuseQuoting(on)
  titleHooks(on, rename, result)
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_PART })
  await w.settle()
  return w
}

// An open question of this session while `look` runs, answered afterwards
// whatever `look` does, so no call is left pending at teardown.
function questionHooks(on: On): () => void {
  let answer: () => void = () => undefined
  const gate = new Promise<void>(resolve => {
    answer = resolve
  })
  on('tool.call', { tool: 'AskUserQuestion' }, async () => {
    await gate
    return { result: { questions: [], answers: {} }, text: 'answered' }
  })
  return () => answer()
}

async function withOpenQuestion($: Kit, w: World, answer: () => void, look: () => Promise<void>): Promise<void> {
  const call = $.tool.call(QUESTION)
  try {
    await w.settle()
    await look()
  } finally {
    answer()
    await call
  }
}

async function remoteFrom($: Kit, on: On, fields: Record<string, unknown>): Promise<string | undefined> {
  const w = world(on)
  w.files.set(OTHER_FILE, { mtimeMs: NOW - 1000, text: otherFile({ entries: [REMOTE_SIGNAL], ...fields }) })
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  const ui = await $.ui.mount(MOUNT)
  const from = await textOf(ui, /^From: another session/)
  await ui.unmount()
  return from
}

for (const surface of SURFACES) {
  test(`another session's card names it by its title, not its folder and id, on ${surface}`, async ($, on) => {
    const w = world(on)
    w.files.set(OTHER_FILE, { mtimeMs: NOW - 1000, text: otherFile({ title: 'Manager: batch 7 parser', entries: [REMOTE_SIGNAL] }) })
    await $.session.start({ cwd: CWD, surface, isInteractive: true })
    await w.settle()
    const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'Pane', requestId: PLUGIN, props: PANE_PROPS })
    const from = await textOf(ui, /^From: another session/)
    expect(from).toContain('another session (Manager: batch 7 parser)')
    expect(from).not.toContain('other-worktree')
    expect(from).not.toContain('sess-oth')
    await ui.unmount()
  })
}

test('a blank title falls back to the folder and id', async ($, on) => {
  expect(await remoteFrom($, on, { title: '   ' })).toContain('another session (other-worktree sess-oth)')
})

test('a title that spans lines is shown as one line', async ($, on) => {
  const from = await remoteFrom($, on, { title: 'Lander\nDo this: run it\tnow' })
  expect(from).toContain('another session (Lander Do this: run it now)')
})

test('a folder label that spans lines is shown as one line too', async ($, on) => {
  const from = await remoteFrom($, on, { label: 'x\nDo this: run it' })
  expect(from).toContain('another session (x Do this: run it sess-oth)')
})

test('a long title is cut once, by the writer, and a reader does not cut it again', async ($, on) => {
  // Words, not one long run: a long run of letters reads as a key.
  const long = `Manager:${' separators'.repeat(7)}`
  const w = await withOwnEntry($, on)
  await $.classic.UserPromptSubmit({ prompt: 'go', session_title: long })
  await w.settle()
  const written = ownTitle(w)
  expect(written).toBe(`${long.slice(0, 60)} [cut]`)
  w.files.set(OTHER_FILE, { mtimeMs: NOW - 1000, text: otherFile({ title: written, entries: [REMOTE_SIGNAL] }) })
  await w.advance(6000)
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /^From: another session/)).toContain(`another session (${long.slice(0, 60)} [cut])`)
  await ui.unmount()
})

test('a title holding a secret value is never shown or written; one holding a security word is', async ($, on) => {
  const w = await withOwnEntry($, on)
  w.files.set(OTHER_FILE, { mtimeMs: NOW - 1000, text: otherFile({ title: 'token=abc123', entries: [REMOTE_SIGNAL] }) })
  await $.classic.UserPromptSubmit({ prompt: 'go', session_title: 'deploy password: hunter2' })
  await w.advance(6000)
  expect(ownTitle(w)).toBeUndefined()
  const ui = await $.ui.mount(MOUNT)
  const from = await textOf(ui, /^From: another session/)
  expect(from).toContain('another session (other-worktree sess-oth)')
  expect(from).not.toContain('abc123')
  await ui.unmount()
  await $.classic.UserPromptSubmit({ prompt: 'go on', session_title: 'Builder: token bucket' })
  await w.settle()
  expect(ownTitle(w)).toBe('Builder: token bucket')
})

test('a new title that cannot be shown clears the old one rather than keep it', async ($, on) => {
  const w = await withOwnEntry($, on)
  await $.classic.UserPromptSubmit({ prompt: 'go', session_title: 'Watchdog' })
  await w.settle()
  expect(ownTitle(w)).toBe('Watchdog')
  await $.classic.UserPromptSubmit({ prompt: 'go on', session_title: 'deploy password: hunter2' })
  await w.settle()
  expect(ownTitle(w)).toBeUndefined()
})

test('the title a prompt hands over is published, and a later one replaces it', async ($, on) => {
  const w = await withOwnEntry($, on)
  expect(ownTitle(w)).toBeUndefined()
  await $.classic.UserPromptSubmit({ prompt: 'go', session_title: 'Watchdog' })
  await w.settle()
  expect(ownTitle(w)).toBe('Watchdog')
  await $.classic.UserPromptSubmit({ prompt: 'go on', session_title: 'Manager: batch 7 parser' })
  await w.settle()
  expect(ownTitle(w)).toBe('Manager: batch 7 parser')
  // A prompt with no title keeps the one held.
  await $.classic.UserPromptSubmit({ prompt: 'again' })
  await w.settle()
  expect(ownTitle(w)).toBe('Manager: batch 7 parser')
})

test('the title session start hands over is published', async ($, on) => {
  const w = await withOwnEntry($, on)
  await $.classic.SessionStart({ source: 'resume', session_title: 'Lander' })
  await w.settle()
  expect(ownTitle(w)).toBe('Lander')
})

for (const event of ['SessionStart', 'UserPromptSubmit'] as const) {
  test(`a title a hook beneath sets on ${event} wins over the one the event carried`, async ($, on) => {
    const w = await withOwnEntry($, on, undefined, () => ({ sessionTitle: 'Set by a hook' }))
    if (event === 'SessionStart') await $.classic.SessionStart({ source: 'resume', session_title: 'Old title' })
    else await $.classic.UserPromptSubmit({ prompt: 'go', session_title: 'Old title' })
    await w.settle()
    expect(ownTitle(w)).toBe('Set by a hook')
  })
}

test("a blocked prompt's hook title is dropped, as the app drops it", async ($, on) => {
  const w = await withOwnEntry($, on, undefined, () => ({ sessionTitle: 'Never applied', block: 'no' }))
  await $.classic.UserPromptSubmit({ prompt: 'go', session_title: 'Watchdog' })
  await w.settle()
  expect(ownTitle(w)).toBe('Watchdog')
})

test("an empty hook title leaves the event's own title in force", async ($, on) => {
  const w = await withOwnEntry($, on, undefined, () => ({ sessionTitle: '' }))
  await $.classic.UserPromptSubmit({ prompt: 'go', session_title: 'Watchdog' })
  await w.settle()
  expect(ownTitle(w)).toBe('Watchdog')
})

test("a subagent's prompt does not set the session's title", async ($, on) => {
  const w = await withOwnEntry($, on)
  await $.classic.UserPromptSubmit({ prompt: 'go', session_title: 'Sub', agent_id: 'agent-1' })
  await w.settle()
  expect(ownTitle(w)).toBeUndefined()
})

test('a rename of this session is published at once; one of another session, or one that failed, is not', async ($, on) => {
  let fails = false
  const w = await withOwnEntry($, on, () => !fails)
  await $.tool.call({ tool: RENAME, session_id: 'local_other', title: 'Not me' })
  await w.settle()
  expect(ownTitle(w)).toBeUndefined()
  await $.tool.call({ tool: RENAME, session_id: 'self', title: 'Special: inbox titles' })
  await w.settle()
  expect(ownTitle(w)).toBe('Special: inbox titles')
  fails = true
  await $.tool.call({ tool: RENAME, session_id: 'self', title: 'Declined' })
  await w.settle()
  expect(ownTitle(w)).toBe('Special: inbox titles')
})

test("a subagent's rename does not set the session's title", async ($, on) => {
  const w = await withOwnEntry($, on)
  await $.tool.call({ tool: RENAME, session_id: 'self', title: 'From a subagent', agentId: 'agent-1' } as never)
  await w.settle()
  expect(ownTitle(w)).toBeUndefined()
})

// The kit keeps one session id across the end, so these read the name the
// pane draws for the session rather than its (ended) file.
for (const reason of ['clear', 'resume'] as const) {
  test(`a ${reason} forgets the title, so the next conversation does not inherit it`, async ($, on) => {
    const w = world(on)
    titleHooks(on)
    const answer = questionHooks(on)
    await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
    await $.classic.UserPromptSubmit({ prompt: 'go', session_title: 'Watchdog' })
    await $.session.end({ reason, sessionId: ME } as never)
    await withOpenQuestion($, w, answer, async () => {
      const ui = await $.ui.mount(MOUNT)
      expect(await ui.find({ type: 'Text', text: /repo \(this session\)/ })).toBeDefined()
      expect(await ui.find({ type: 'Text', text: /Watchdog/ })).toBeUndefined()
      await ui.unmount()
    })
  })
}

test("this session's own question card names it by its title", async ($, on) => {
  const w = world(on)
  titleHooks(on)
  const answer = questionHooks(on)
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await $.classic.UserPromptSubmit({ prompt: 'go', session_title: 'Watchdog' })
  await withOpenQuestion($, w, answer, async () => {
    const ui = await $.ui.mount(MOUNT)
    expect(await ui.find({ type: 'Text', text: /Watchdog \(this session\)/ })).toBeDefined()
    await ui.unmount()
  })
})

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

test('the confirm view names pwsh by its full path, never by name', async ($, on) => {
  const w = world(on)
  refuseQuoting(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git status' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  const shown = await shownRows(ui)
  expect(shown).toContain(`argv[0]: ${PWSH}`)
  expect(shown.filter(row => row === `folder: ${CWD}`)).toHaveLength(1)
  expect(await ui.find({ type: 'Text', text: /\(by name/ })).toBeUndefined()
  await ui.unmount()
})

test('with pwsh only under LOCALAPPDATA, a PowerShell Run finds no shell', async ($, on) => {
  const local = 'C:\\Users\\tester\\AppData\\Local'
  const w = world(on, { env: { LOCALAPPDATA: local } })
  w.files.delete(PWSH)
  w.files.set(`${local}\\Microsoft\\PowerShell\\7\\pwsh.exe`, { text: '', mtimeMs: 0 })
  refuseQuoting(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git status' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  expect(await ui.find({ type: 'Text', text: /^Run now runs nothing: PowerShell 7 \(pwsh.exe\) not found by path/ })).toBeDefined()
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

// ------------------------------------------ what resolves an entry by itself

const NOT_FINE = [
  { name: 'a later || that hides its failure', command: `${SWITCH_PART} || true` },
  { name: 'a later ; that sets the exit status', command: `${SWITCH_PART}; echo done` },
  { name: 'a pipe after it', command: `${SWITCH_PART} | Out-Null` },
  { name: 'an earlier cd', command: `cd C:\\elsewhere && ${SWITCH_PART}` },
  { name: 'an earlier ; part', command: `git fetch; ${SWITCH_PART}` },
  { name: 'an earlier && chain', command: `git fetch && ${SWITCH_PART}` },
] as const

for (const one of NOT_FINE) {
  test(`a later success with ${one.name} resolves nothing`, async ($, on) => {
    const w = world(on)
    refuse(on, command => (command === SWITCH_LINE ? SWITCH_REFUSAL : undefined))
    await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
    await w.settle()
    await $.tool.call({ tool: 'PowerShell', command: one.command })
    await w.settle()
    expect(mine(w).entries).toHaveLength(1)
  })
}

test('a later success that starts with the part, then && alone, resolves it', async ($, on) => {
  const w = world(on)
  refuse(on, command => (command === SWITCH_LINE ? SWITCH_REFUSAL : undefined))
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  await $.tool.call({ tool: 'PowerShell', command: `${SWITCH_PART} && git fetch` })
  await w.settle()
  expect(mine(w).entries).toHaveLength(0)
})

const OWN_SEPARATOR = ['git push origin main || true', 'git push origin main | Out-Null', 'git push origin main; echo done'] as const

for (const part of OWN_SEPARATOR) {
  test(`a part with its own separator, ${part}, is never resolved by a later success of it`, async ($, on) => {
    const w = world(on)
    let isFirst = true
    refuse(on, command => {
      if (command !== part || !isFirst) return undefined
      isFirst = false
      return `BLOCKED: '${part}' needs the person. Do it from a PLAIN terminal.`
    })
    await $.tool.call({ tool: 'PowerShell', command: part })
    await w.settle()
    expect(mine(w).entries).toHaveLength(1)
    await $.tool.call({ tool: 'PowerShell', command: part })
    await w.settle()
    expect(mine(w).entries).toHaveLength(1)
  })
}

test('a part joined inside by && alone is resolved by a later success of it', async ($, on) => {
  const w = world(on)
  const part = 'git fetch && git push origin main'
  let isFirst = true
  refuse(on, command => {
    if (command !== part || !isFirst) return undefined
    isFirst = false
    return `BLOCKED: '${part}' needs the person. Do it from a PLAIN terminal.`
  })
  await $.tool.call({ tool: 'PowerShell', command: part })
  await w.settle()
  expect(mine(w).entries).toHaveLength(1)
  await $.tool.call({ tool: 'PowerShell', command: part })
  await w.settle()
  expect(mine(w).entries).toHaveLength(0)
})

const INLINE = [
  { name: 'a long command by Copy rather than cut it', command: `git fetch origin && git push ${'x'.repeat(170)}`, shown: 'the command Copy gives (Details shows it whole)' },
  { name: 'a two-line command by Copy rather than join it', command: 'git fetch origin\ngit push', shown: 'the command Copy gives (Details shows it whole)' },
  { name: 'a short one-line command inline', command: 'git fetch origin && git push', shown: 'git fetch origin && git push' },
] as const

for (const one of INLINE) {
  test(`Do this names ${one.name}`, async ($, on) => {
    const w = world(on)
    refuseAll(on, "BLOCKED: 'git push' needs the person. Do it from a PLAIN terminal.")
    await $.tool.call({ tool: 'PowerShell', command: one.command })
    await w.settle()
    const ui = await $.ui.mount(MOUNT)
    expect(await textOf(ui, /^Do this: /)).toBe(`Do this: Run the whole command in a plain terminal: ${one.shown}`)
    await ui.unmount()
  })
}

test('a part that was not first on its line is never resolved by a later success', async ($, on) => {
  const w = world(on)
  const line = `git fetch && ${SWITCH_PART}`
  refuse(on, command => (command === line ? SWITCH_REFUSAL : undefined))
  await $.tool.call({ tool: 'PowerShell', command: line })
  await w.settle()
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_PART })
  await w.settle()
  expect(mine(w).entries).toHaveLength(1)
})

test('a later success launched in the background resolves nothing', async ($, on) => {
  const w = world(on)
  refuse(on, command => (command === SWITCH_LINE ? SWITCH_REFUSAL : undefined))
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_PART, run_in_background: true } as never)
  await w.settle()
  expect(mine(w).entries).toHaveLength(1)
})

test('a later success whose result reads as a launch resolves nothing', async ($, on) => {
  const w = world(on)
  on('classic.PreToolUse', ($, e) => (inputCommand(e) === SWITCH_LINE ? { deny: SWITCH_REFUSAL } : {}))
  on('tool.call', { tool: 'PowerShell' }, ($, e) =>
    e.command === SWITCH_LINE
      ? { isError: true, result: 'blocked', text: `PreToolUse:PowerShell hook error: ${SWITCH_REFUSAL}` }
      : { result: 'ok', text: 'Command running in background with ID: b1' },
  )
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_PART })
  await w.settle()
  expect(mine(w).entries).toHaveLength(1)
})

test('a later success in the other shell resolves nothing', async ($, on) => {
  const w = world(on)
  refuse(on, command => (command === SWITCH_LINE ? SWITCH_REFUSAL : undefined))
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  await $.tool.call({ tool: 'Bash', command: SWITCH_PART })
  await w.settle()
  expect(mine(w).entries).toHaveLength(1)
})

test('an entry a subagent raised is never resolved by a later main-loop success', async ($, on) => {
  const w = world(on)
  refuse(on, command => (command === SWITCH_LINE ? SWITCH_REFUSAL : undefined))
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE, agentId: 'agent-1' } as never)
  await w.settle()
  expect(mine(w).entries).toHaveLength(1)
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_PART })
  await w.settle()
  expect(mine(w).entries).toHaveLength(1)
})

// ------------------------------------------ review round 1: what is shared

test('a secret in the handover sentence never reaches the shared file', async ($, on) => {
  const w = world(on)
  const pass = ['hun', 'ter2'].join('')
  refuseAll(on, `BLOCKED: this needs the person. Run curl -u admin:${pass} https://x.test from a PLAIN terminal.`)
  await $.tool.call({ tool: 'Bash', command: 'git status' })
  await w.settle()
  const text = w.files.get(MY_FILE)?.text ?? ''
  expect(text).toContain('"kind":"refused"')
  expect(text).not.toContain(pass)
})

test('a secret-shaped ask read from another session is withheld, and the entry still shows', async ($, on) => {
  const w = world(on)
  const pass = ['hun', 'ter2'].join('')
  const ask = `Run curl -u admin:${pass} https://x.test from a PLAIN terminal.`
  w.files.set(OTHER_FILE, { mtimeMs: NOW - 1000, text: otherFile({ entries: [{ ...REMOTE_KEEP, detail: undefined, ask }] }) })
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /waiting on the owner$/)).toBe('1 waiting on the owner')
  expect(await ui.find({ type: 'Text', text: new RegExp(pass) })).toBeUndefined()
  await ui.unmount()
})

// --------------------------------------- review round 1: the owner signal

test('a signal whose input carries agentId null is Copy only, never the main loop', async ($, on) => {
  const w = world(on)
  await callTool($, signal({ command: 'git status', agentId: null }))
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
  expect(await ui.find({ type: 'Text', text: /^Copy only: a subagent filed it/ })).toBeDefined()
  await ui.unmount()
})

test('a signal whose why draws a Run result header gets Copy only', async ($, on) => {
  const w = world(on)
  await callTool($, signal({ command: 'git status', why: 'ran, exit 0: all fine' }))
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
  await ui.unmount()
})

test('only the loop that filed a signal can resolve it', async ($, on) => {
  const w = world(on)
  const said = await callTool($, signal())
  const id = /as ([0-9a-f-]{36})/.exec(said)?.[1] ?? ''
  await w.settle()
  expect(await callTool($, { tool: DONE, id, agentId: 'agent-1' })).toContain('No owner_action entry')
  await w.settle()
  expect(mine(w).entries).toHaveLength(1)
})

// ------------------------------------------- review round 2: signal prose

test('a signal whose prose carries a secret stores a placeholder for that field alone, and says so', async ($, on) => {
  const w = world(on)
  const pass = ['hun', 'ter2'].join('')
  const said = await callTool(
    $,
    signal({
      recommendedAction: `Run curl -u admin:${pass} https://x.test to check.`,
      why: `Log in with sshpass -p ${pass} first.`,
      confidence: `medium; mysql -p${pass} would settle it`,
    }),
  )
  expect(said).toContain('Filed in the owner inbox as ')
  expect(said).toContain('stored as a placeholder: why, recommendedAction, confidence')
  await w.settle()
  const text = w.files.get(MY_FILE)?.text ?? ''
  expect(text).not.toContain(pass)
  const entry = mine(w).entries[0]
  expect(entry?.title).toBe('Choose the license for the new package')
  expect(entry?.recommendedAction).toBe('(text withheld: it looked like it carried a secret)')
  expect(entry?.why).toBe('(text withheld: it looked like it carried a secret)')
  expect(entry?.reviewOutcome).toBe('review split evenly between the two licenses')
  const ui = await $.ui.mount(MOUNT)
  expect(await ui.find({ type: 'Text', text: new RegExp(pass) })).toBeUndefined()
  await ui.unmount()
})

test('a signal read from another session whose prose carries a secret shows a placeholder', async ($, on) => {
  const w = world(on)
  const pass = ['hun', 'ter2'].join('')
  const crafted = { ...REMOTE_SIGNAL, title: `Approve with -u admin:${pass}`, reviewOutcome: `sshpass -p ${pass} did not help`, confidence: 'high' }
  w.files.set(OTHER_FILE, { mtimeMs: NOW - 1000, text: otherFile({ entries: [crafted] }) })
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /waiting on the owner$/)).toBe('1 waiting on the owner')
  expect(await ui.find({ type: 'Text', text: new RegExp(pass) })).toBeUndefined()
  expect(await textOf(ui, /^\(text withheld/)).toBe('(text withheld: it looked like it carried a secret)')
  await ui.unmount()
})

// ------------------------------------------- review round 2: the arm lapse

// What $.state holds for this session's own entries, as the plugin last read it.
function ownState(on: On): () => Record<string, unknown>[] {
  let latest: Record<string, unknown>[] = []
  on('state.get', async ($, e, next) => {
    const got = await next(e)
    const name = e as unknown as { plugin?: string; key?: string }
    const value = (got.value as { value?: unknown } | undefined)?.value
    if (name.plugin === PLUGIN && name.key === 'own' && Array.isArray(value)) latest = value as Record<string, unknown>[]
    return got
  })
  return () => latest
}

test('a lapsed arm is cleared from the entry, not only hidden', async ($, on) => {
  const w = world(on)
  const state = ownState(on)
  refuseQuoting(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git push origin main' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  await ui.redraw()
  expect(state().find(one => one.id === id)?.armedAt).toBeDefined()
  await w.advance(61_000)
  await ui.redraw()
  const after = state().find(one => one.id === id)
  expect(after?.armedAt).toBeUndefined()
  expect(after?.armedArgv).toBeUndefined()
  expect(await ui.find({ key: `run:${id}` })).toBeDefined()
  await ui.unmount()
})

test('a Cancel clears the arm from the entry', async ($, on) => {
  const w = world(on)
  const state = ownState(on)
  refuseQuoting(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git push origin main' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  await ui.press({ key: `cancel:${id}` })
  await ui.redraw()
  expect(state().find(one => one.id === id)?.armedAt).toBeUndefined()
  await ui.unmount()
})

test('after an arm lapses, a full list evicts that entry rather than a newer one', async ($, on) => {
  const w = world(on)
  refuseQuoting(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git push origin main' })
  await w.settle()
  const armed = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${armed}` })
  await w.advance(61_000)
  await ui.unmount()
  const filed: string[] = []
  for (let i = 0; i < 50; i++) {
    const said = await callTool($, signal({ title: `Signal number ${i}` }))
    filed.push(/as ([0-9a-f-]{36})/.exec(said)?.[1] ?? '')
  }
  await w.settle()
  const ids = mine(w).entries.map(one => String(one.id))
  expect(ids).not.toContain(armed)
  expect(ids).toHaveLength(50)
  expect(ids).toEqual(filed)
})

test('an arm still inside its minute is kept when the list is full', async ($, on) => {
  const w = world(on)
  refuseQuoting(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git push origin main' })
  await w.settle()
  const armed = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${armed}` })
  await ui.unmount()
  for (let i = 0; i < 50; i++) await callTool($, signal({ title: `Signal number ${i}` }))
  await w.settle()
  const ids = mine(w).entries.map(one => String(one.id))
  expect(ids).toContain(armed)
  expect(ids).toHaveLength(50)
})

// ------------------------------------- review round 2: the refusal's own lines

const DRAWN_LABEL = [
  { name: 'a Why line holding a label', text: "BLOCKED: 'git status' would print argv[0]: x. Do it from a PLAIN terminal." },
  { name: 'a For you line holding a label', text: "BLOCKED: 'git status' needs the person. Press Run now from a PLAIN terminal." },
  // The confirm row copies the refusal's words into Do this uncut, while For
  // you is cut at 240 characters, before the label, and Why ends earlier.
  { name: 'a Do this line holding a label', text: `BLOCKED: 'git status' needs the person. I need you to confirm this ${'and '.repeat(60)}Run now: argv[0]: x` },
] as const

for (const one of DRAWN_LABEL) {
  test(`a refusal with ${one.name} gets Copy only`, async ($, on) => {
    const w = world(on)
    refuseAll(on, one.text)
    await $.tool.call({ tool: 'PowerShell', command: 'git status' })
    await w.settle()
    const id = String(mine(w).entries[0]?.id)
    const ui = await $.ui.mount(MOUNT)
    expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: /^Copy only: its Do this, Why or For you line holds a label/ })).toBeDefined()
    await ui.unmount()
  })
}

const NEW_LABELS = ['argv: x', 'Copy only: x', 'Needs you for: x', 'confidence: x', 'Review: x', 'Question: x', 'Resolved']

for (const label of NEW_LABELS) {
  test(`a command holding the drawn label "${label}" gets Copy only`, async ($, on) => {
    const w = world(on)
    refuseQuoting(on)
    await $.tool.call({ tool: 'PowerShell', command: `echo ${label}` })
    await w.settle()
    const id = String(mine(w).entries[0]?.id)
    const ui = await $.ui.mount(MOUNT)
    expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: /^Copy only: it holds a label the card draws/ })).toBeDefined()
    await ui.unmount()
  })
}

// ------------------------------------------- review round 2: the withheld ask

test('a withheld ask keeps its kind and its row, here and in a reader', async ($, on) => {
  const w = world(on)
  const pass = ['hun', 'ter2'].join('')
  refuseAll(on, `BLOCKED: 'git status' needs the person. Run curl -u admin:${pass} https://x.test from a PLAIN terminal.`)
  await $.tool.call({ tool: 'PowerShell', command: 'git status' })
  await w.settle()
  const written = w.files.get(MY_FILE)?.text ?? ''
  expect(written).not.toContain(pass)
  const entry = mine(w).entries[0]
  expect(entry?.kind).toBe('refused')
  expect(String(entry?.ask)).toBe('ask withheld: it looked like it carried a secret. The gate handed it over as: from a PLAIN terminal')
  const ui = await $.ui.mount(MOUNT)
  // The refusal was withheld with it, so the part cannot be read back: the whole command.
  expect(await textOf(ui, /^Do this: /)).toBe('Do this: Run the whole command in a plain terminal: git status')
  await ui.unmount()
  // Another session reads the same file and keeps the entry by the same rule.
  w.files.set(OTHER_FILE, { mtimeMs: NOW - 1000, text: written.replace(`"sessionId":"${ME}"`, '"sessionId":"sess-other-2"') })
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  const reader = await $.ui.mount(MOUNT)
  const remoteKey = `rcopy:sess-other-2:${String(entry?.id)}`
  expect(await reader.find({ key: remoteKey })).toBeDefined()
  expect((await reader.findAll({ type: 'Text', text: /^Do this: Run the whole command in a plain terminal: git status$/ })).length).toBe(2)
  await reader.unmount()
})

test('a withheld confirm ask keeps its row without the words it withheld', async ($, on) => {
  const w = world(on)
  const pass = ['hun', 'ter2'].join('')
  refuseAll(on, `BLOCKED: 'git status' needs the person. "I need you to confirm curl -u admin:${pass} is safe."`)
  await $.tool.call({ tool: 'PowerShell', command: 'git status' })
  await w.settle()
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /^Do this: /)).toBe('Do this: Confirm it is safe, then run the whole command in a plain terminal: git status')
  expect(await ui.find({ type: 'Text', text: new RegExp(pass) })).toBeUndefined()
  await ui.unmount()
})

test('a reader drops a refused entry whose ask looks secret but hands nothing over', async ($, on) => {
  const w = world(on)
  const pass = ['hun', 'ter2'].join('')
  const crafted = { ...REMOTE_KEEP, detail: undefined, ask: `Use curl -u admin:${pass} https://x.test to finish.` }
  w.files.set(OTHER_FILE, { mtimeMs: NOW - 1000, text: otherFile({ entries: [crafted] }) })
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /waiting on the owner$/)).toBe('0 waiting on the owner')
  await ui.unmount()
})

// --------------------------------------- review round 2: render time, bounded

// 120 entries: read and counted in full, with the newest 40 drawn, under the
// engine's bound of 100000 characters of text in one Pane.
const FILES = 3
test('a render over 120 crafted remote entries stays under 10 seconds', async ($, on) => {
  const w = world(on)
  const crafted = `${'$'.repeat(1976)}${'-'.repeat(1976)}; git push`
  const detail = `BLOCKED: 'git push' needs the person. Do it from a PLAIN terminal. ${"'a' ".repeat(400)}`
  for (let f = 0; f < FILES; f++) {
    const entries = Array.from({ length: 40 }, (_, i) => ({
      id: `e${i}`,
      kind: 'refused',
      createdAt: NOW - 60_000,
      shell: 'PowerShell',
      command: crafted,
      cwd: 'C:\\elsewhere',
      refusal: "BLOCKED: 'git push' needs the person.",
      detail,
      ask: 'Do it from a PLAIN terminal.',
    }))
    w.files.set(`${DIR}\\sess-many-${f}.json`, { mtimeMs: NOW - 1000, text: otherFile({ sessionId: `sess-many-${f}`, entries }) })
  }
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  const started = performance.now()
  const ui = await $.ui.mount(MOUNT)
  await ui.redraw()
  const elapsed = performance.now() - started
  expect(await textOf(ui, /waiting on the owner$/)).toBe(`${FILES * 40} waiting on the owner`)
  // Generous on purpose: a loaded machine is slow, a backtracking regex is
  // seconds per entry. Measured at 137 ms on 2026-10-02.
  expect(elapsed).toBeLessThan(10_000)
  await ui.unmount()
})

// ---------------------------------- many remote entries: drawn cap, held cap

// Remote entries spread over `files` files of `per` entries each, newest
// first by index: entry 0 of file 0 is the newest of all. Each carries a long
// refusal and why line, about the size of a real card, so 200 of them drawn
// whole would pass the engine's 100000-character bound on one Pane.
function manyRemote(w: World, files: number, per: number): void {
  const detail = `BLOCKED: 'git push' needs the person. Do it from a PLAIN terminal. ${'word '.repeat(240)}`
  for (let f = 0; f < files; f++) {
    const entries = Array.from({ length: per }, (_, i) => ({
      id: `m${f}-${i}`,
      kind: 'refused',
      createdAt: NOW - 60_000 - (f * per + i) * 1000,
      shell: 'PowerShell',
      command: `git push origin topic-${f}-${i}`,
      cwd: 'C:\\elsewhere',
      refusal: "BLOCKED: 'git push' needs the person.",
      detail,
      ask: 'Do it from a PLAIN terminal.',
    }))
    w.files.set(`${DIR}\\sess-bulk-${f}.json`, {
      mtimeMs: NOW - 1000,
      text: otherFile({ sessionId: `sess-bulk-${f}`, entries }),
    })
  }
}

async function paneChars(ui: Finder): Promise<number> {
  return (await ui.findAll({ type: 'Text' })).reduce((sum, one) => sum + (one.text ?? '').length, 0)
}

test('200 remote entries draw the newest 40, under the pane bound, and say how many more wait', async ($, on) => {
  const w = world(on)
  on('ui.render', { component: 'AbovePrompt' }, () => ({ type: 'engine', ref: 0 }))
  manyRemote(w, 5, 40)
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /waiting on the owner$/)).toBe('200 waiting on the owner')
  expect(await drawnCards(ui)).toBe(40)
  expect(await paneChars(ui)).toBeLessThan(100_000)
  // Newest first: the newest entry is drawn and the 41st newest is not.
  expect(await ui.find({ key: 'rdismiss:sess-bulk-0:m0-0' })).toBeDefined()
  expect(await ui.find({ key: 'rdismiss:sess-bulk-0:m0-39' })).toBeDefined()
  expect(await ui.find({ key: 'rdismiss:sess-bulk-1:m1-0' })).toBeUndefined()
  expect(await textOf(ui, /more waiting/)).toBe(
    '160 more waiting from other sessions are not shown. /inbox shows the newest 40.',
  )
  await ui.unmount()
})

test('the band counts every waiting entry, drawn or not, and a Dismiss keeps the counts equal', async ($, on) => {
  const w = world(on)
  on('ui.render', { component: 'AbovePrompt' }, () => ({ type: 'engine', ref: 0 }))
  refuseAll(on, SWITCH_REFUSAL)
  manyRemote(w, 5, 40)
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_LINE })
  await w.settle()
  const band = await $.ui.mount({ plugin: PLUGIN, surface: 'terminal', component: 'AbovePrompt', props: BAND_PROPS })
  const ui = await $.ui.mount(MOUNT)
  const bandCount = async () =>
    Number(/^inbox (\d+)$/.exec((await band.find({ type: 'Button', key: 'korus-inbox:open' }))?.text ?? '')?.[1])
  const headCount = async () => Number(/^(\d+) waiting/.exec((await textOf(ui, /waiting on the owner$/)) ?? '')?.[1])
  const moreCount = async () => Number(/^(\d+) more/.exec((await textOf(ui, /more waiting/)) ?? '')?.[1])
  expect(await bandCount()).toBe(201)
  expect(await headCount()).toBe(201)
  expect((await drawnCards(ui)) + (await moreCount())).toBe(201)
  expect(await $.command.run({ command: 'inbox' })).toMatchObject({ text: 'Owner inbox opened: 201 waiting.' })

  await ui.press({ key: 'rdismiss:sess-bulk-0:m0-0' })
  // At once, before any poll: the list and its total move in one write, so
  // the counts drop by exactly one and still agree.
  await w.settle()
  expect(await bandCount()).toBe(200)
  expect(await headCount()).toBe(200)
  expect((await drawnCards(ui)) + (await moreCount())).toBe(200)
  await w.advance(5000)
  expect(await bandCount()).toBe(200)
  expect(await headCount()).toBe(200)
  // The next poll refills the drawn cards from what was not drawn.
  expect(await drawnCards(ui)).toBe(41)
  expect((await drawnCards(ui)) + (await moreCount())).toBe(200)
  await band.unmount()
  await ui.unmount()
})

test('800 remote entries keep the state small, and none of them vanishes from the count', async ($, on) => {
  const w = world(on)
  manyRemote(w, 20, 40)
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  await w.advance(5000)
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /waiting on the owner$/)).toBe('800 waiting on the owner')
  expect(await drawnCards(ui)).toBe(40)
  expect(await textOf(ui, /more waiting/)).toBe('760 more waiting from other sessions are not shown. /inbox shows the newest 40.')
  await ui.unmount()
})

test('remote cards stop at the text budget, short of 40, when each is large', async ($, on) => {
  const w = world(on)
  const big = (i: number) => ({
    id: `q${i}`,
    kind: 'question',
    createdAt: NOW - 60_000 - i * 1000,
    questions: Array.from({ length: 4 }, () => ({
      header: 'Pick',
      question: 'q'.repeat(1000),
      options: Array.from({ length: 6 }, () => ({ label: 'l'.repeat(100), description: 'd'.repeat(300) })),
    })),
  })
  // Two files of 15: one file of these passes the 256 KB a reader takes.
  for (let f = 0; f < 2; f++) {
    w.files.set(`${DIR}\\sess-big-${f}.json`, {
      mtimeMs: NOW - 1000,
      text: otherFile({ sessionId: `sess-big-${f}`, entries: Array.from({ length: 15 }, (_, i) => big(f * 15 + i)) }),
    })
  }
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  const ui = await $.ui.mount(MOUNT)
  expect(await textOf(ui, /waiting on the owner$/)).toBe('30 waiting on the owner')
  const drawn = await drawnCards(ui)
  expect(drawn).toBeGreaterThan(0)
  expect(drawn).toBeLessThan(30)
  expect(await paneChars(ui)).toBeLessThan(100_000)
  expect(await textOf(ui, /more waiting/)).toBe(
    `${30 - drawn} more waiting from other sessions are not shown. /inbox shows the newest ${drawn}.`,
  )
  await ui.unmount()
})

test('opening Details on the last remote card that fits keeps the card, and Hide details closes it', async ($, on) => {
  const w = world(on)
  // Signals at their longest fields: about 2600 characters each with Details
  // closed, so the budget runs out short of 40. Each carries a long command
  // that Details would add.
  const long = (i: number) => ({
    id: `s${i}`,
    kind: 'signal',
    createdAt: NOW - 60_000 - i * 1000,
    title: 'a b '.repeat(50),
    why: 'c d '.repeat(150),
    recommendedAction: 'e f '.repeat(100),
    needs: 'authority',
    reviewOutcome: 'not applicable: only the owner signs',
    confidence: 'g h '.repeat(30),
    cwd: `C:\\work\\${'w'.repeat(480)}`,
    command: `echo ${'word '.repeat(700)}`,
  })
  w.files.set(OTHER_FILE, { mtimeMs: NOW - 1000, text: otherFile({ entries: Array.from({ length: 40 }, (_, i) => long(i)) }) })
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  const ui = await $.ui.mount(MOUNT)
  const drawn = await drawnCards(ui)
  expect(drawn).toBeGreaterThan(0)
  expect(drawn).toBeLessThan(40)
  const last = `sess-other-2:s${drawn - 1}`
  await ui.press({ key: `rdetails:${last}` })
  expect(await drawnCards(ui)).toBe(drawn)
  expect(await ui.find({ key: `rdismiss:${last}` })).toBeDefined()
  expect((await ui.find({ key: `rdetails:${last}` }))?.text).toBe('Hide details')
  expect(await textOf(ui, /^Details do not fit/)).toBe(
    'Details do not fit in the pane now. Hide the details of another card, or Copy this one.',
  )
  expect(await paneChars(ui)).toBeLessThan(100_000)
  await ui.press({ key: `rdetails:${last}` })
  expect((await ui.find({ key: `rdetails:${last}` }))?.text).toBe('Details')
  expect(await textOf(ui, /^Details do not fit/)).toBeUndefined()
  // Details opened on the newest card push no older card off the pane: the
  // cards fit first, and these Details find no room left.
  await ui.press({ key: 'rdetails:sess-other-2:s0' })
  expect(await drawnCards(ui)).toBe(drawn)
  expect(await ui.find({ key: `rdismiss:${last}` })).toBeDefined()
  expect(await textOf(ui, /^Details do not fit/)).toBeDefined()
  expect(await paneChars(ui)).toBeLessThan(100_000)
  await ui.unmount()
})

test('a remote card with room to spare draws its Details when opened', async ($, on) => {
  const w = world(on)
  w.files.set(OTHER_FILE, { mtimeMs: NOW - 1000, text: otherFile({ entries: [REMOTE_SIGNAL] }) })
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: 'rdetails:sess-other-2:e3' })
  expect(await ui.find({ type: 'Text', text: 'Full command:' })).toBeDefined()
  expect(await textOf(ui, /^Details do not fit/)).toBeUndefined()
  expect(await textOf(ui, /more waiting/)).toBeUndefined()
  await ui.unmount()
})

// ------------------------------------------------------ go to the session

// Every id here is made up. None is a real account, organization or session.
const LOCAL = `${HOME}\\AppData\\Local`
const ROAMING = `${HOME}\\AppData\\Roaming`
const INSTALL = `${LOCAL}\\AnthropicClaude`
const STUB = `${INSTALL}\\claude.exe`
const APP_EXE = `${INSTALL}\\app-9.9.9\\claude.exe`
const SYSTEM_ROOT = 'C:\\Windows'
const PS = `${SYSTEM_ROOT}\\System32\\WindowsPowerShell\\v1.0\\powershell.exe`
const INSTANCE = `${HOME}\\.claude-desktop-3`
const APP_SID = 'local_11111111-2222-4333-8444-555555555555'
const GO = 'rgo:sess-other-2:e3'
const ACCOUNT = '00000000-1111-4222-8333-444444444444'
const ORG = '99999999-8888-4777-8666-555555555555'
const MY_SID = 'local_aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'
const MY_INSTANCE = `${HOME}\\.claude-desktop-2`
const MY_ENV = {
  CLAUDE_CODE_HOST_SESSION_ID: MY_SID,
  CLAUDE_CODE_EXECPATH: `${MY_INSTANCE}\\claude-code\\9.9.9\\0123456789ab\\claude.exe`,
  CLAUDE_CODE_ACCOUNT_UUID: ACCOUNT,
  CLAUDE_CODE_ORGANIZATION_UUID: ORG,
}
const MY_RECORD = `${MY_INSTANCE}\\claude-code-sessions\\${ACCOUNT}\\${ORG}\\${MY_SID}.json`
const RECORD_TEXT = JSON.stringify({ sessionId: MY_SID, cliSessionId: ME })

// One process-list line, as the query prints it: executable, tab, command line.
function processLine(exe: string, commandLine: string): string {
  return `${exe}\t${commandLine}`
}
function mainProcess(folder: string): string {
  return processLine(APP_EXE, `"${APP_EXE}" --user-data-dir="${folder}" `)
}

type DesktopOptions = {
  fields?: Record<string, unknown>
  processes?: readonly string[]
  gate?: WorldOptions['gate']
  /** The user's home folder; the app's install and the inbox folder follow it. */
  home?: string
  /** A query that exits with this code, still printing the process list. */
  queryExitCode?: number
  /** A machine whose environment has no SystemRoot. */
  isSystemRootUnset?: boolean
}

// A desktop machine with the app's launcher installed, a process list holding
// `processes` (by default a running instance 3), and another session's file
// naming `place`.
function desktop(on: On, place: unknown, options: DesktopOptions = {}): World {
  const home = options.home ?? HOME
  const local = `${home}\\AppData\\Local`
  const processes = options.processes ?? [mainProcess(INSTANCE)]
  const env: Record<string, string> = { USERPROFILE: home, LOCALAPPDATA: local, APPDATA: `${home}\\AppData\\Roaming` }
  if (options.isSystemRootUnset !== true) env.SystemRoot = SYSTEM_ROOT
  const w = world(on, {
    env,
    stdoutFor: argv => (argv[0] === PS ? `${processes.join('\r\n')}\r\n` : undefined),
    exitCodeFor: argv => (argv[0] === PS ? options.queryExitCode : undefined),
    gate: options.gate,
  })
  w.files.set(`${local}\\AnthropicClaude\\claude.exe`, { text: '', mtimeMs: 0 })
  w.files.set(`${home}\\.korus-inbox\\sess-other-2.json`, {
    mtimeMs: NOW - 1000,
    text: otherFile({ title: 'Watchdog', place, entries: [REMOTE_SIGNAL], ...options.fields }),
  })
  return w
}

function launches(w: World, stub = STUB): (readonly string[])[] {
  return w.runs.filter(run => run.argv[0] === stub).map(run => run.argv)
}

async function paneWithGo($: Kit, w: World): Promise<{ ui: Awaited<ReturnType<Kit['ui']['mount']>>; found: Found | undefined }> {
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  const ui = await $.ui.mount(MOUNT)
  return { ui, found: await ui.find({ type: 'Button', key: GO }) }
}

async function pressGo($: Kit, w: World): Promise<(readonly string[])[]> {
  const { ui, found } = await paneWithGo($, w)
  expect(found).toBeDefined()
  await ui.press({ key: GO })
  await w.settle()
  await ui.unmount()
  return launches(w)
}

function placeWritten(w: World): unknown {
  return (JSON.parse(w.files.get(MY_FILE)?.text ?? '{}') as { place?: unknown }).place
}

async function publishWith($: Kit, on: On, env: Record<string, string>, record?: string): Promise<World> {
  const w = world(on, { env })
  if (record !== undefined) w.files.set(MY_RECORD, { text: record, mtimeMs: 0 })
  refuseQuoting(on)
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await $.tool.call({ tool: 'PowerShell', command: SWITCH_PART })
  await w.settle()
  return w
}

// ---- the writer

test("a desktop session publishes where the app shows it, once the app's record names it", async ($, on) => {
  const w = await publishWith($, on, MY_ENV, RECORD_TEXT)
  expect(placeWritten(w)).toEqual({ instance: MY_INSTANCE, id: MY_SID })
})

test("a process that inherited another session's app environment publishes no place", async ($, on) => {
  const w = await publishWith($, on, MY_ENV, JSON.stringify({ sessionId: MY_SID, cliSessionId: 'the-parent-session' }))
  expect(placeWritten(w)).toBeUndefined()
})

test('a session outside the desktop app publishes no place', async ($, on) => {
  const w = await publishWith($, on, {})
  expect(placeWritten(w)).toBeUndefined()
})

test('a session whose app record is written after it starts publishes its place within a few polls', async ($, on) => {
  const w = await publishWith($, on, MY_ENV)
  expect(placeWritten(w)).toBeUndefined()
  w.files.set(MY_RECORD, { text: RECORD_TEXT, mtimeMs: 0 })
  await w.advance(6000)
  expect(placeWritten(w)).toEqual({ instance: MY_INSTANCE, id: MY_SID })
})

test('an ended file names no place', async ($, on) => {
  const w = await publishWith($, on, MY_ENV, RECORD_TEXT)
  expect(placeWritten(w)).toEqual({ instance: MY_INSTANCE, id: MY_SID })
  await $.session.end({ reason: 'clear', sessionId: ME } as never)
  await w.settle()
  expect(placeWritten(w)).toBeUndefined()
})

// ---- the button

test('Go to session reads the process list, then hands the link to the running instance through the launcher', async ($, on) => {
  const w = desktop(on, { instance: INSTANCE, id: APP_SID })
  const { ui, found } = await paneWithGo($, w)
  expect(found?.text).toBe('Go to session')
  await ui.press({ key: GO })
  await w.settle()
  expect(w.runs.map(run => run.argv[0])).toEqual([PS, STUB])
  expect(w.runs[0]?.argv.slice(1, 4)).toEqual(['-NoProfile', '-NonInteractive', '-Command'])
  expect(w.runs[0]?.argv.join(' ')).not.toContain(INSTANCE)
  expect(launches(w)).toEqual([[STUB, `--user-data-dir=${INSTANCE}`, `claude://claude.ai/epitaxy/${APP_SID}`]])
  expect(w.timeouts).toEqual([15_000, 20_000])
  await ui.unmount()
})

test("the folder launched is this machine's own spelling, never the file's", async ($, on) => {
  const w = desktop(on, { instance: `${HOME}\\.CLAUDE-DESKTOP-3`, id: APP_SID })
  expect((await pressGo($, w)).map(argv => argv[1])).toEqual([`--user-data-dir=${INSTANCE}`])
})

test('a running instance is recognised with or without quotes around its folder', async ($, on) => {
  const w = desktop(on, { instance: INSTANCE, id: APP_SID }, { processes: [processLine(APP_EXE, `${APP_EXE} --user-data-dir=${INSTANCE}`)] })
  expect(await pressGo($, w)).toHaveLength(1)
})

test('a session whose file has gone quiet offers no Go to session', async ($, on) => {
  const w = desktop(on, { instance: INSTANCE, id: APP_SID }, { fields: { updatedAt: NOW - 13 * 60 * 1000 } })
  const { ui, found } = await paneWithGo($, w)
  expect(found).toBeUndefined()
  await ui.unmount()
})

test('a file that was fresh when read stops offering Go to session once it goes quiet', async ($, on) => {
  const w = desktop(on, { instance: INSTANCE, id: APP_SID })
  const { ui, found } = await paneWithGo($, w)
  expect(found).toBeDefined()
  await w.advance(13 * 60 * 1000)
  expect(await ui.find({ type: 'Button', key: GO })).toBeUndefined()
  await ui.unmount()
})

test('a file dated more than five minutes ahead offers no Go to session; one a little ahead does', async ($, on) => {
  const far = desktop(on, { instance: INSTANCE, id: APP_SID }, { fields: { updatedAt: NOW + 10 * 60 * 1000 } })
  const { ui, found } = await paneWithGo($, far)
  expect(found).toBeUndefined()
  far.files.set(OTHER_FILE, {
    mtimeMs: NOW + 1,
    text: otherFile({ title: 'Watchdog', place: { instance: INSTANCE, id: APP_SID }, updatedAt: NOW + 2 * 60 * 1000, entries: [REMOTE_SIGNAL] }),
  })
  await far.advance(6000)
  expect(await ui.find({ type: 'Button', key: GO })).toBeDefined()
  await ui.unmount()
})

const BAD_PLACES: { name: string; place: unknown }[] = [
  { name: 'a quote in the folder', place: { instance: `${HOME}\\x" --inspect\\.claude-desktop-3`, id: APP_SID } },
  { name: 'a control character in the folder', place: { instance: `${HOME}\\x\n\\.claude-desktop-3`, id: APP_SID } },
  { name: 'a trailing dot', place: { instance: `${INSTANCE}.`, id: APP_SID } },
  { name: 'a trailing space', place: { instance: `${INSTANCE} `, id: APP_SID } },
  { name: 'a folder that is no instance folder', place: { instance: `${HOME}\\Documents`, id: APP_SID } },
  { name: 'the default instance, whose hand-off is not measured', place: { instance: `${ROAMING}\\Claude`, id: APP_SID } },
  { name: 'an id that is not an app id', place: { instance: INSTANCE, id: 'local_x?y=1' } },
  { name: 'an id with something after it', place: { instance: INSTANCE, id: `${APP_SID} --flag` } },
  { name: 'a place that is not an object', place: `${INSTANCE}|${APP_SID}` },
]
for (const { name, place } of BAD_PLACES) {
  test(`a place with ${name} offers no Go to session`, async ($, on) => {
    const w = desktop(on, place)
    const { ui, found } = await paneWithGo($, w)
    expect(found).toBeUndefined()
    await ui.unmount()
  })
}

// Each names instance 3 in a folder that is not this home. The process list
// holds both that folder and this home's instance 3, so only the check that
// the file's folder is this machine's own folder stands between the press and
// a launch; it refuses before the process list is even read.
const FOREIGN_FOLDERS: { name: string; instance: string }[] = [
  { name: "another user's home", instance: 'C:\\Users\\tester2\\.claude-desktop-3' },
  { name: 'another drive', instance: 'D:\\profiles\\.claude-desktop-3' },
  { name: 'a folder nested below the home', instance: `${HOME}\\Code\\p\\.claude-desktop-3` },
]
for (const { name, instance } of FOREIGN_FOLDERS) {
  test(`a place naming ${name} is refused when pressed, even with this home's instance running`, async ($, on) => {
    const w = desktop(on, { instance, id: APP_SID }, { processes: [mainProcess(instance), mainProcess(INSTANCE)] })
    await pressGo($, w)
    expect(w.runs).toEqual([])
  })
}

const REFUSED_ON_PRESS: { name: string; instance: string; processes?: readonly string[] }[] = [
  { name: 'an instance no process holds', instance: INSTANCE, processes: [] },
  { name: 'an instance only a renderer names', instance: INSTANCE, processes: [processLine(APP_EXE, `"${APP_EXE}" --type=renderer --user-data-dir="${INSTANCE}"`)] },
  { name: 'an instance held by a program outside the install', instance: INSTANCE, processes: [mainProcess(INSTANCE).replace(APP_EXE, `${HOME}\\Downloads\\claude.exe`)] },
  { name: 'a different instance that is running', instance: `${HOME}\\.claude-desktop-4` },
]
for (const { name, instance, processes } of REFUSED_ON_PRESS) {
  test(`a place naming ${name} is refused when pressed, and nothing is launched`, async ($, on) => {
    const w = desktop(on, { instance, id: APP_SID }, { processes: processes ?? [mainProcess(name === 'a different instance that is running' ? INSTANCE : instance)] })
    expect(await pressGo($, w)).toEqual([])
  })
}

test('a lockfile planted in an instance folder does not count as that instance running', async ($, on) => {
  const w = desktop(on, { instance: INSTANCE, id: APP_SID }, { processes: [] })
  w.files.set(`${INSTANCE}\\lockfile`, { text: '', mtimeMs: 0 })
  expect(await pressGo($, w)).toEqual([])
})

test('without the launcher installed, nothing is launched', async ($, on) => {
  const w = desktop(on, { instance: INSTANCE, id: APP_SID })
  w.files.delete(STUB)
  expect(await pressGo($, w)).toEqual([])
})

test('a second press while the first launch is in flight launches nothing more', async ($, on) => {
  let release: () => void = () => undefined
  const held = new Promise<void>(resolve => {
    release = resolve
  })
  const w = desktop(on, { instance: INSTANCE, id: APP_SID }, { gate: argv => (argv[0] === STUB ? held : undefined) })
  const { ui } = await paneWithGo($, w)
  await ui.press({ key: GO })
  await w.settle()
  await ui.press({ key: GO })
  await w.settle()
  release()
  await w.settle()
  expect(launches(w)).toHaveLength(1)
  await ui.press({ key: GO })
  await w.settle()
  expect(launches(w)).toHaveLength(2)
  await ui.unmount()
})

test('outside the desktop app, pressing Go to session runs nothing', async ($, on) => {
  const w = world(on)
  w.files.set(OTHER_FILE, { mtimeMs: NOW - 1000, text: otherFile({ place: { instance: INSTANCE, id: APP_SID }, entries: [REMOTE_SIGNAL] }) })
  const { ui } = await paneWithGo($, w)
  await ui.press({ key: GO })
  await w.settle()
  expect(w.runs).toEqual([])
  await ui.unmount()
})

// ---- the guards at the press

test('a process list query that fails does not count as the instance running, whatever it printed', async ($, on) => {
  const w = desktop(on, { instance: INSTANCE, id: APP_SID }, { queryExitCode: 1 })
  expect(await pressGo($, w)).toEqual([])
  expect(w.runs.map(run => run.argv[0])).toEqual([PS])
})

// Each line holds a main process of the app whose folder only resembles
// instance 3's: the folder must equal it, not start with it, end it or hold it.
const NEAR_FOLDERS: { name: string; folder: string }[] = [
  { name: 'a longer number', folder: `${INSTANCE}4` },
  { name: 'a folder inside it', folder: `${INSTANCE}\\x` },
  { name: 'the home it sits in', folder: HOME },
  { name: 'a longer path that ends with it', folder: `D:\\copy\\${INSTANCE}` },
]
for (const { name, folder } of NEAR_FOLDERS) {
  test(`a running instance whose folder is ${name} does not count as instance 3 running`, async ($, on) => {
    const w = desktop(on, { instance: INSTANCE, id: APP_SID }, { processes: [mainProcess(folder)] })
    expect(await pressGo($, w)).toEqual([])
  })
}

// The app counts only from its install folder, %LOCALAPPDATA%\AnthropicClaude:
// a folder beside it whose name starts the same is somewhere else.
const OUTSIDE_INSTALL: { name: string; exe: string }[] = [
  { name: 'a sibling folder sharing its name as a prefix', exe: `${LOCAL}\\AnthropicClaudeBeta\\app-9.9.9\\claude.exe` },
  { name: 'the folder that holds the install', exe: `${LOCAL}\\claude.exe` },
]
for (const { name, exe } of OUTSIDE_INSTALL) {
  test(`a claude.exe in ${name} does not count as the app running`, async ($, on) => {
    const w = desktop(on, { instance: INSTANCE, id: APP_SID }, { processes: [mainProcess(INSTANCE).replace(APP_EXE, exe)] })
    expect(await pressGo($, w)).toEqual([])
  })
}

test('with SystemRoot unset, a press runs nothing at all, not even a powershell found by PATH', async ($, on) => {
  const w = desktop(on, { instance: INSTANCE, id: APP_SID }, { isSystemRootUnset: true })
  await pressGo($, w)
  expect(w.runs).toEqual([])
})

test('a button drawn while its session was alive launches nothing when pressed after it went quiet', async ($, on) => {
  // The file's session goes quiet two seconds after the pane is drawn, and
  // the next poll, which would redraw the pane, is five seconds away (POLL_MS).
  // So the button is still drawn when it is pressed three seconds later; the
  // find below fails loudly if a shorter poll ever redraws it first.
  const w = desktop(on, { instance: INSTANCE, id: APP_SID }, { fields: { updatedAt: NOW - 12 * 60 * 1000 + 2000 } })
  const { ui, found } = await paneWithGo($, w)
  expect(found).toBeDefined()
  await w.advance(3000)
  expect(await ui.find({ type: 'Button', key: GO })).toBeDefined()
  await ui.press({ key: GO })
  await w.settle()
  expect(w.runs).toEqual([])
  await ui.unmount()
})

test('a held place whose id lost its shape after the file was read is refused at the press, and nothing runs', async ($, on) => {
  const w = desktop(on, { instance: INSTANCE, id: APP_SID })
  // The reader checks the shape when it reads the file. Here every read of
  // the held entries returns a bad id instead. The pane draws the button
  // without checking the id, so only the check at the press can refuse it.
  on('state.get', async ($$: unknown, e: { key?: unknown }, next: (e: unknown) => unknown) => {
    const got = await next(e)
    if (e.key !== 'remoteHeld') return got
    const copy = JSON.parse(JSON.stringify(got)) as { value?: { value?: { entries?: { place?: { id: string } }[] } } }
    for (const entry of copy.value?.value?.entries ?? []) if (entry.place !== undefined) entry.place.id = `${APP_SID} --inspect`
    return copy
  })
  expect(await pressGo($, w)).toEqual([])
  expect(w.runs).toEqual([])
})

// ---- a home folder with a space in it

// Windows quotes an argument that holds a space, either the whole argument or
// only the folder, and the process list shows the quotes.
const SPACE_HOME = 'C:\\Users\\Ann Lee'
const SPACE_INSTANCE = `${SPACE_HOME}\\.claude-desktop-3`
const SPACE_STUB = `${SPACE_HOME}\\AppData\\Local\\AnthropicClaude\\claude.exe`
const SPACE_APP_EXE = `${SPACE_HOME}\\AppData\\Local\\AnthropicClaude\\app-9.9.9\\claude.exe`
const SPACE_QUOTINGS: { name: string; commandLine: string }[] = [
  { name: 'the whole argument quoted', commandLine: `"${SPACE_APP_EXE}" "--user-data-dir=${SPACE_INSTANCE}" --flag` },
  { name: 'only the folder quoted', commandLine: `"${SPACE_APP_EXE}" --user-data-dir="${SPACE_INSTANCE}" --flag` },
]
for (const { name, commandLine } of SPACE_QUOTINGS) {
  test(`a home folder with a space gets a working Go to session, with ${name}`, async ($, on) => {
    const w = desktop(on, { instance: SPACE_INSTANCE, id: APP_SID }, { home: SPACE_HOME, processes: [processLine(SPACE_APP_EXE, commandLine)] })
    await pressGo($, w)
    expect(launches(w, SPACE_STUB)).toEqual([[SPACE_STUB, `--user-data-dir=${SPACE_INSTANCE}`, `claude://claude.ai/epitaxy/${APP_SID}`]])
  })
}

// The switch counts only as a whole argument of its own, split the way
// CommandLineToArgvW splits it. Each expected split below was read from that
// function on Windows 11 on 2026-10-06, so a reader splitting any other way
// would count a switch the app never sees.
const SWITCH_NOT_WHOLE: { name: string; commandLine: string }[] = [
  { name: 'the tail of a longer switch', commandLine: `"${APP_EXE}" --x--user-data-dir=${INSTANCE}` },
  { name: 'inside another quoted argument', commandLine: `"${APP_EXE}" "--note=see --user-data-dir=${INSTANCE} here"` },
  { name: 'the folder and more in one quoted value', commandLine: `"${APP_EXE}" --user-data-dir="${INSTANCE} x"` },
  // A backslash before a quote makes it a plain quote, so the quoting goes on.
  { name: 'inside an argument with an escaped quote', commandLine: `"${APP_EXE}" "--note=a\\" --user-data-dir=${INSTANCE} b"` },
  // Three quotes inside quotes give one quote, which stays in the argument.
  { name: 'a folder followed by a doubled quote', commandLine: `"${APP_EXE}" "--user-data-dir=${INSTANCE}"""` },
  // Windows splits this as `x"` then `y --user-data-dir=...`: two quotes inside
  // quotes give one quote and end the quoting.
  { name: 'the tail of an argument after a doubled quote', commandLine: `"${APP_EXE}" "x"" y" --user-data-dir=${INSTANCE}` },
  // The program name ends at the next quote, with no escapes, so the quoted
  // argument after it is one argument.
  { name: 'inside the argument after a program name ending in a backslash', commandLine: `"${APP_EXE}\\" "x --user-data-dir=${INSTANCE} x"` },
]
for (const { name, commandLine } of SWITCH_NOT_WHOLE) {
  test(`a --user-data-dir= found as ${name} does not count`, async ($, on) => {
    const w = desktop(on, { instance: INSTANCE, id: APP_SID }, { processes: [processLine(APP_EXE, commandLine)] })
    expect(await pressGo($, w)).toEqual([])
  })
}

// The app reads a switch with `--`, `-` or `/` before it, in any case, and
// could take either of two data folders. So every data-folder switch must
// name the folder, and a line that stops the app reading switches part way
// does not count.
const OTHER = `${HOME}\\.claude-desktop-4`
const SWITCH_READINGS: { name: string; commandLine: string; isRunning: boolean }[] = [
  { name: 'the folder switch in capitals', commandLine: `"${APP_EXE}" --USER-DATA-DIR=${INSTANCE}`, isRunning: true },
  { name: 'a second folder switch after it', commandLine: `"${APP_EXE}" --user-data-dir=${INSTANCE} --user-data-dir=${OTHER}`, isRunning: false },
  { name: 'a second folder switch before it', commandLine: `"${APP_EXE}" --user-data-dir=${OTHER} --user-data-dir=${INSTANCE}`, isRunning: false },
  { name: 'a second folder switch with one dash', commandLine: `"${APP_EXE}" --user-data-dir=${INSTANCE} -user-data-dir=${OTHER}`, isRunning: false },
  { name: 'a second folder switch with a slash', commandLine: `"${APP_EXE}" --user-data-dir=${INSTANCE} /User-Data-Dir=${OTHER}`, isRunning: false },
  { name: 'the folder switch after a bare --', commandLine: `"${APP_EXE}" -- --user-data-dir=${INSTANCE}`, isRunning: false },
  { name: 'the folder switch after --single-argument', commandLine: `"${APP_EXE}" --single-argument --user-data-dir=${INSTANCE}`, isRunning: false },
  { name: 'a quoted type switch', commandLine: `"${APP_EXE}" "--type=renderer" --user-data-dir=${INSTANCE}`, isRunning: false },
  { name: 'a type switch with one dash', commandLine: `"${APP_EXE}" -type=renderer --user-data-dir=${INSTANCE}`, isRunning: false },
]
for (const { name, commandLine, isRunning } of SWITCH_READINGS) {
  test(`a command line with ${name} ${isRunning ? 'counts' : 'does not count'} as instance 3 running`, async ($, on) => {
    const w = desktop(on, { instance: INSTANCE, id: APP_SID }, { processes: [processLine(APP_EXE, commandLine)] })
    expect(await pressGo($, w)).toHaveLength(isRunning ? 1 : 0)
  })
}
