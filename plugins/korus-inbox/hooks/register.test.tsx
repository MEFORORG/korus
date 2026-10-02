import { test, expect, mock } from 'claude-code/testing'
import type { On } from 'claude-code'

// Every fixture here is synthetic: invented sessions, folders and commands.

const PLUGIN = 'korus-inbox'
const SURFACES = ['terminal', 'desktop'] as const
const NOW = Date.UTC(2026, 0, 1, 12, 0, 0)
const HOME = 'C:\\Users\\tester'
const DIR = `${HOME}\\.korus-inbox`
const ME = 'sess-own-1'
const MY_FILE = `${DIR}\\${ME}.json`
const OTHER_FILE = `${DIR}\\sess-other-2.json`
const CWD = 'C:\\work\\repo'

const PANE_PROPS = {
  title: 'Owner inbox',
  isFocused: false,
  bodyColumns: 100,
  placement: 'dock',
  scroll: { offset: 0, bodyRows: 40 },
  view: {},
} as const

type World = {
  files: Map<string, { text: string; mtimeMs: number }>
  runs: { argv: readonly string[]; cwd: string | undefined }[]
  copies: string[]
  status: () => string | undefined
  settle: () => Promise<void>
  advance: (ms: number) => Promise<void>
}

// The engine beneath the plugin: an in-memory shared folder, a fixed session,
// a recorded process runner and clipboard. Nothing touches the real disk.
function world(on: On, opts: { env?: Record<string, string>; cwd?: string; cwdFails?: boolean } = {}): World {
  const files = new Map<string, { text: string; mtimeMs: number }>()
  const runs: World['runs'] = []
  const copies: string[] = []
  let status: string | undefined
  const clock = mock.clock(on, { now: NOW })
  mock.env(on, { USERPROFILE: HOME, ...opts.env })
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  on('session.end', ($, e) => ({ sessionId: e.sessionId }))
  on('session.id', () => ({ value: ME }))
  on('session.cwd', () => {
    if (opts.cwdFails === true) throw new Error('no cwd')
    return { value: opts.cwd ?? CWD }
  })
  on('session.root', () => ({ value: CWD }))
  on('command.register', ($, e) => ({ value: { command: e.name } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.toast', () => ({ value: undefined }))
  on('ui.status', ($, e) => {
    status = e.text
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
  on('process.run', ($, e) => {
    runs.push({ argv: e.argv, cwd: e.init?.cwd })
    return {
      value: { exitCode: 0, stdout: 'pushed fine\n', stderr: '', isStdoutTruncated: false, isStderrTruncated: false },
    }
  })
  return { files, runs, copies, status: () => status, settle: clock.settle, advance: clock.advance }
}

// A settings PreToolUse hook that blocks every call. The 2.1.286 kit routes
// $.tool.call through classic.PreToolUse, so the deny ends the call there and
// the tool hooks below never run. The 2.1.284 kit does not, so the tool hooks
// answer as a session prints a hook refusal, which the fallback path reads.
function refuseShell(on: On): void {
  const REASON = 'BLOCKED: pushes to main go through the queue'
  on('classic.PreToolUse', () => ({ deny: REASON }))
  on('tool.call', { tool: 'PowerShell' }, () => ({
    isError: true,
    result: 'blocked',
    text: `PreToolUse:PowerShell hook error: ${REASON}`,
  }))
  on('tool.call', { tool: 'Bash' }, () => ({
    isError: true,
    result: 'blocked',
    text: `PreToolUse:Bash hook error: ${REASON}`,
  }))
}

// The rows the confirm and result views draw: a label, or a continuation mark.
const ROW = /^(argv\[\d+\]: |folder: |  [|+] )/

type Found = { text?: string; props?: Record<string, unknown> }

async function shownRows(ui: { findAll: (query: { type: 'Text'; text: RegExp }) => Promise<Found[]> }): Promise<string[]> {
  return (await ui.findAll({ type: 'Text', text: ROW })).map(one => one.text ?? '')
}

// A bare pwsh, as the confirm and result views draw it in the test folder.
const PWSH_ROWS = [
  `folder: ${CWD}`,
  'argv[0]: pwsh (by name: PATH, and on Windows the',
  '  +  run folder first)',
  'argv[1]: -NoProfile',
  'argv[2]: -Command',
  'argv[3]: git push origin main',
]

function mine(w: World): { entries: Record<string, unknown>[]; dismissed: string[] } {
  const file = w.files.get(MY_FILE)
  if (file === undefined) return { entries: [], dismissed: [] }
  return JSON.parse(file.text) as { entries: Record<string, unknown>[]; dismissed: string[] }
}

test('a pending AskUserQuestion is listed, then clears once answered', async ($, on) => {
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
          { label: 'Careful', description: 'Ship tomorrow' },
        ],
      },
    ],
  })
  await w.settle()
  expect(w.status()).toBe('inbox 1')
  const written = mine(w).entries
  expect(written).toHaveLength(1)
  expect(written[0]?.kind).toBe('question')
  expect(JSON.stringify(written[0])).toContain('Which path should the build take?')
  expect(JSON.stringify(written[0])).toContain('Careful')

  answer?.()
  await call
  await w.settle()
  expect(w.status()).toBeUndefined()
  expect(mine(w).entries).toHaveLength(0)
})

test('a refused PowerShell call is recorded with its cwd and first refusal line', async ($, on) => {
  const w = world(on)
  refuseShell(on)
  const ran = await $.tool.call({ tool: 'PowerShell', command: 'git push origin main' })
  expect(ran.isError).toBe(true)
  await w.settle()
  const entries = mine(w).entries
  expect(entries).toHaveLength(1)
  expect(entries[0]).toMatchObject({
    kind: 'refused',
    shell: 'PowerShell',
    command: 'git push origin main',
    cwd: CWD,
  })
  expect(String(entries[0]?.refusal)).toEndWith('BLOCKED: pushes to main go through the queue')
  expect(w.status()).toBe('inbox 1')
})

test('a refusal that reaches the result as the session prints it is recorded too', async ($, on) => {
  const w = world(on)
  on('tool.call', { tool: 'PowerShell' }, () => ({
    isError: true,
    result: 'blocked',
    text: 'PreToolUse:PowerShell hook error: BLOCKED: no force-push\nsecond line with output',
  }))
  await $.tool.call({ tool: 'PowerShell', command: 'git push --force' })
  await w.settle()
  expect(mine(w).entries[0]).toMatchObject({
    command: 'git push --force',
    refusal: 'PreToolUse:PowerShell hook error: BLOCKED: no force-push',
  })
})

test('an allowed call is not recorded, and neither is a command that merely failed', async ($, on) => {
  const w = world(on)
  on('classic.PreToolUse', () => ({}))
  on('tool.call', { tool: 'PowerShell' }, () => ({ result: 'ok', text: 'ok' }))
  on('tool.call', { tool: 'Bash' }, () => ({ isError: true, result: 'Exit code 1', text: 'Exit code 1' }))
  await $.tool.call({ tool: 'PowerShell', command: 'git status' })
  await $.tool.call({ tool: 'Bash', command: 'false' })
  await w.settle()
  expect(w.files.size).toBe(0)
  expect(w.status()).toBeUndefined()
})

test('a secret-looking command is stored as a placeholder and offers no Run', async ($, on) => {
  const w = world(on)
  refuseShell(on)
  await $.tool.call({ tool: 'Bash', command: 'curl -H "Authorization: Bearer sk-live-0000"' })
  await $.tool.call({ tool: 'Bash', command: 'export GH_TOKEN=abc' })
  await $.tool.call({ tool: 'Bash', command: 'echo aGVsbG8gd29ybGQgdGhpcyBpcyBhIGxvbmcgcnVuIDEyMzQ1Ng==' })
  await $.tool.call({ tool: 'Bash', command: 'psql postgres://bob:hunter2@db.local/app' })
  await $.tool.call({ tool: 'Bash', command: 'curl -u bob:hunter2 https://example.test' })
  await $.tool.call({ tool: 'Bash', command: 'echo 0123456789abcdef0123456789abcdef' })
  await $.tool.call({ tool: 'PowerShell', command: 'ConvertTo-SecureString hunter2 -AsPlainText -Force' })
  await $.tool.call({ tool: 'Bash', command: 'DB_PASS=hunter2 ./migrate' })
  await $.tool.call({ tool: 'Bash', command: 'mysql -u root -phunter2 app' })
  await $.tool.call({ tool: 'Bash', command: 'aws configure set id AKIAABCDEFGHIJKLMNOP' })
  await w.settle()
  const text = w.files.get(MY_FILE)?.text ?? ''
  expect(text).not.toContain('Bearer')
  expect(text).not.toContain('GH_TOKEN')
  expect(text).not.toContain('aGVsbG8')
  expect(text).not.toContain('hunter2')
  expect(text).not.toContain('0123456789abcdef')
  const entries = mine(w).entries
  expect(entries).toHaveLength(10)
  for (const entry of entries) {
    expect(entry.command).toBeUndefined()
    expect(entry.withheld).toContain('secret')
  }
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'Pane', requestId: PLUGIN, props: PANE_PROPS })
    expect(await ui.findAll({ type: 'Button', text: 'Run' })).toHaveLength(0)
    expect(await ui.findAll({ type: 'Button', text: 'Copy' })).toHaveLength(0)
    expect(await ui.findAll({ type: 'Text', text: /withheld/ })).toHaveLength(10)
    await ui.unmount()
  }
})

for (const surface of SURFACES) {
  test(`a disk entry from another session shows Copy and no Run on ${surface}`, async ($, on) => {
    const w = world(on)
    w.files.set(OTHER_FILE, {
      mtimeMs: NOW - 1000,
      text: JSON.stringify({
        format: 'korus-inbox/1',
        sessionId: 'sess-other-2',
        label: 'other-worktree',
        updatedAt: NOW - 1000,
        ended: false,
        entries: [
          {
            id: 'e1',
            kind: 'refused',
            createdAt: NOW - 60_000,
            shell: 'PowerShell',
            command: 'Remove-Item -Recurse C:\\data \u001b[2J',
            cwd: 'C:\\elsewhere',
            refusal: 'BLOCKED: not here',
          },
          {
            id: 'e2',
            kind: 'refused',
            createdAt: NOW - 30_000,
            shell: 'Bash',
            command: 'echo password=hunter2',
            cwd: 'C:\\elsewhere',
            refusal: 'BLOCKED',
          },
          { id: 'old', kind: 'refused', createdAt: NOW - 25 * 60 * 60 * 1000, command: 'stale', refusal: 'x' },
        ],
        dismissed: [],
      }),
    })
    await $.session.start({ cwd: CWD, surface, isInteractive: true })
    await w.settle()
    expect(w.status()).toBe('inbox 2')

    const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'Pane', requestId: PLUGIN, props: PANE_PROPS })
    const commands = (await ui.findAll({ type: 'Text', text: /^(PowerShell|Bash):/ })).map(one => one.text)
    expect(commands).toHaveLength(2)
    expect(commands[0]).toContain('withheld')
    expect(commands[1]).toContain('Remove-Item -Recurse C:\\data')
    expect(commands.join('')).not.toContain('\u001b')
    expect(commands.join('')).not.toContain('hunter2')
    expect(await ui.find({ type: 'Text', text: /other-worktree/ })).toBeDefined()
    expect(await ui.findAll({ type: 'Button', text: /^Run/ })).toHaveLength(0)
    expect(await ui.findAll({ type: 'Button', text: 'Copy' })).toHaveLength(1)

    await ui.press({ key: 'rcopy:sess-other-2:e1' })
    expect(w.copies).toEqual(['Remove-Item -Recurse C:\\data [2J'])
    expect(w.runs).toHaveLength(0)

    await ui.press({ key: 'rdismiss:sess-other-2:e1' })
    expect(w.status()).toBe('inbox 1')
    expect(mine(w).dismissed).toEqual(['sess-other-2:e1'])
    await ui.unmount()
  })

  test(`Run executes only on the owner's two presses, on ${surface}`, async ($, on) => {
    const w = world(on)
    refuseShell(on)
    await $.tool.call({ tool: 'PowerShell', command: 'git push origin main' })
    await w.settle()
    expect(w.runs).toHaveLength(0)

    const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'Pane', requestId: PLUGIN, props: PANE_PROPS })
    expect((await ui.find({ type: 'Text', text: /^PowerShell:/ }))?.text).toBe('PowerShell: git push origin main')
    expect((await ui.find({ type: 'Text', text: /^cwd:/ }))?.text).toBe(`cwd: ${CWD}`)

    const id = String(mine(w).entries[0]?.id)
    await ui.press({ key: `run:${id}` })
    expect(w.runs).toHaveLength(0)
    expect(await ui.find({ type: 'Button', text: 'Run now' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'Run now runs this:' })).toBeDefined()

    await ui.press({ key: `cancel:${id}` })
    expect(w.runs).toHaveLength(0)

    await ui.press({ key: `run:${id}` })
    await w.advance(700)
    await ui.press({ key: `confirm:${id}` })
    expect(w.runs).toEqual([{ argv: ['pwsh', '-NoProfile', '-Command', 'git push origin main'], cwd: CWD }])
    expect((await ui.find({ type: 'Text', text: /^ran, exit/ }))?.text).toBe('ran, exit 0:')
    expect(await shownRows(ui)).toEqual(PWSH_ROWS)
    expect(await ui.find({ type: 'Text', text: 'pushed fine' })).toBeDefined()
    expect(await ui.findAll({ type: 'Button', text: /^Run/ })).toHaveLength(1)
    expect(w.status()).toBeUndefined()
    expect(mine(w).entries).toHaveLength(0)
    expect(w.files.get(MY_FILE)?.text ?? '').not.toContain('pushed fine')
    await ui.unmount()
  })
}

test('with no Git Bash installed, a Bash Run fails and runs nothing, never a bare bash', async ($, on) => {
  const w = world(on)
  refuseShell(on)
  await $.tool.call({ tool: 'Bash', command: 'ls -la' })
  await w.settle()
  const ui = await $.ui.mount({
    plugin: PLUGIN,
    surface: 'terminal',
    component: 'Pane',
    requestId: PLUGIN,
    props: PANE_PROPS,
  })
  const id = String(mine(w).entries[0]?.id)
  await ui.press({ key: `run:${id}` })
  await w.advance(700)
  await ui.press({ key: `confirm:${id}` })
  expect(w.runs).toHaveLength(0)
  expect((await ui.find({ type: 'Text', text: /^could not run/ }))?.text).toBe('could not run:')
  expect(await ui.find({ type: 'Text', text: /Git Bash not found/ })).toBeDefined()
  expect(w.status()).toBe('inbox 1')
  await ui.unmount()
})

test('a session end writes an ended file that other panes skip', async ($, on) => {
  const w = world(on)
  refuseShell(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git push origin main' })
  await w.settle()
  await $.session.end({ reason: 'prompt_input_exit', sessionId: ME, resume: { id: ME } } as never)
  await w.settle()
  const file = JSON.parse(w.files.get(MY_FILE)?.text ?? '{}') as { ended: boolean; entries: unknown[] }
  expect(file.ended).toBe(true)
  expect(file.entries).toHaveLength(0)
})

const MOUNT = { plugin: PLUGIN, surface: 'terminal', component: 'Pane', requestId: PLUGIN, props: PANE_PROPS } as const
const GIT_BASH = 'C:\\Program Files\\Git\\bin\\bash.exe'

test('Bash runs through Git Bash where it is installed, not a bare bash that may be WSL', async ($, on) => {
  const w = world(on)
  w.files.set(GIT_BASH, { text: '', mtimeMs: 0 })
  refuseShell(on)
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

test('two quick Run now presses run the command once', async ($, on) => {
  const w = world(on)
  refuseShell(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git push origin main' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  await w.advance(700)
  await Promise.all([
    ui.press({ key: `confirm:${id}` }),
    ui.press({ key: `confirm:${id}` }).catch(() => undefined),
  ])
  expect(w.runs).toHaveLength(1)
  await ui.unmount()
})

test('an arming press lapses after a minute and Run now goes away', async ($, on) => {
  const w = world(on)
  refuseShell(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git push origin main' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  expect(await ui.find({ key: `confirm:${id}` })).toBeDefined()
  await w.advance(61_000)
  await ui.redraw()
  expect(await ui.find({ key: `confirm:${id}` })).toBeUndefined()
  expect(await ui.find({ key: `run:${id}` })).toBeDefined()
  expect(w.runs).toHaveLength(0)
  await ui.unmount()
})

test('a press keyed to one entry runs that entry after a newer row shifts the list', async ($, on) => {
  const w = world(on)
  refuseShell(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git push origin first' })
  await w.settle()
  const first = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${first}` })
  await w.advance(1000)
  await $.tool.call({ tool: 'PowerShell', command: 'git push origin second' })
  await w.settle()
  await ui.press({ key: `confirm:${first}` })
  expect(w.runs).toEqual([{ argv: ['pwsh', '-NoProfile', '-Command', 'git push origin first'], cwd: CWD }])
  await ui.unmount()
})

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

const ONE_REFUSED = [{ id: 'e1', kind: 'refused', createdAt: NOW - 60_000, shell: 'Bash', command: 'ls', refusal: 'BLOCKED' }]

test('a reader drops a session it had cached once that session writes its ended file', async ($, on) => {
  const w = world(on)
  w.files.set(OTHER_FILE, { mtimeMs: NOW - 1000, text: otherFile({ entries: ONE_REFUSED }) })
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  expect(w.status()).toBe('inbox 1')
  w.files.set(OTHER_FILE, { mtimeMs: NOW + 1000, text: otherFile({ ended: true, updatedAt: NOW + 1000 }) })
  await w.advance(5000)
  expect(w.status()).toBeUndefined()
})

test('a half-written file keeps the last good read rather than dropping the session', async ($, on) => {
  const w = world(on)
  w.files.set(OTHER_FILE, { mtimeMs: NOW - 1000, text: otherFile({ entries: ONE_REFUSED }) })
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  expect(w.status()).toBe('inbox 1')
  w.files.set(OTHER_FILE, { mtimeMs: NOW + 1000, text: '{"format":"korus-inbox/1","entr' })
  await w.advance(5000)
  expect(w.status()).toBe('inbox 1')
})

test('a Dismiss pressed in another pane clears this session entry too', async ($, on) => {
  const w = world(on)
  refuseShell(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git push origin main' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  expect(w.status()).toBe('inbox 1')
  w.files.set(OTHER_FILE, { mtimeMs: NOW + 1000, text: otherFile({ updatedAt: NOW + 1000, dismissed: [`${ME}:${id}`] }) })
  await w.advance(5000)
  expect(w.status()).toBeUndefined()
  expect(mine(w).entries).toHaveLength(0)
})

test('a command holding a character the screen strips is Copy only', async ($, on) => {
  const w = world(on)
  refuseShell(on)
  await $.tool.call({ tool: 'PowerShell', command: 'Remove-Item\u000b-Recurse C:\\x' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
  expect(await ui.find({ type: 'Text', text: /^Copy only: the command holds/ })).toBeDefined()
  expect(w.runs).toHaveLength(0)
  await ui.unmount()
})

test('one file listing an id twice shows it once', async ($, on) => {
  const w = world(on)
  w.files.set(OTHER_FILE, { mtimeMs: NOW - 1000, text: otherFile({ entries: [...ONE_REFUSED, ...ONE_REFUSED] }) })
  await $.session.start({ cwd: CWD, surface: 'terminal', isInteractive: true })
  await w.settle()
  expect(w.status()).toBe('inbox 1')
})

test('a write after the session ended does not bring its file back', async ($, on) => {
  const w = world(on)
  refuseShell(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git push origin main' })
  await w.settle()
  await $.session.end({ reason: 'prompt_input_exit', sessionId: ME, resume: { id: ME } } as never)
  await w.settle()
  await $.tool.call({ tool: 'PowerShell', command: 'git push origin late' })
  await w.settle()
  const file = JSON.parse(w.files.get(MY_FILE)?.text ?? '{}') as { ended: boolean }
  expect(file.ended).toBe(true)
})

test('PowerShell runs through the installed pwsh by path where it exists', async ($, on) => {
  const installed = 'C:\\Program Files\\PowerShell\\7\\pwsh.exe'
  const w = world(on, { env: { ProgramFiles: 'C:\\Program Files' } })
  w.files.set(installed, { text: '', mtimeMs: 0 })
  refuseShell(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git push origin main' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  await w.advance(700)
  await ui.press({ key: `confirm:${id}` })
  expect(w.runs).toEqual([{ argv: [installed, '-NoProfile', '-Command', 'git push origin main'], cwd: CWD }])
  await ui.unmount()
})

test('a refusal in a folder the screen would show altered is Copy only', async ($, on) => {
  const w = world(on, { cwd: 'C:\\work\\re\u200bpo' })
  refuseShell(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git push origin main' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
  expect(await ui.find({ key: `copy:${id}` })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^Copy only: its folder holds/ })).toBeDefined()
  expect(w.runs).toHaveLength(0)
  await ui.unmount()
})

test('a Run now pressed inside the 600 ms gap is ignored, and one at the gap runs', async ($, on) => {
  const w = world(on)
  refuseShell(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git push origin main' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  expect(await ui.find({ type: 'Text', text: /^Run now ignores a press within 600 ms of the last press/ })).toBeDefined()
  // The same instant as the arming press: a double click.
  await ui.press({ key: `confirm:${id}` })
  expect(w.runs).toHaveLength(0)
  // 599 ms after the last press: still inside the gap, which starts again.
  await w.advance(599)
  await ui.press({ key: `confirm:${id}` })
  expect(w.runs).toHaveLength(0)
  expect(await ui.find({ key: `confirm:${id}` })).toBeDefined()
  // 600 ms after the last press: outside the gap.
  await w.advance(600)
  await ui.press({ key: `confirm:${id}` })
  expect(w.runs).toHaveLength(1)
  await ui.unmount()
})

test('a held Enter on Run now, repeating every 100 ms, never runs the command', async ($, on) => {
  const w = world(on)
  refuseShell(on)
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
  refuseShell(on)
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
  refuseShell(on)
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

test('a multi-line command cannot draw a fake argv element', async ($, on) => {
  const w = world(on)
  refuseShell(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git status\nargv[4]: harmless' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  const shown = await shownRows(ui)
  expect(shown.slice(-2)).toEqual(['argv[3]: git status', '  | argv[4]: harmless'])
  expect(shown.filter(line => line.startsWith('argv['))).toHaveLength(4)
  await ui.unmount()
})

const NO_FULL_PATH = [
  { name: 'session.cwd() fails', opts: { cwdFails: true } },
  { name: 'the cwd is empty', opts: { cwd: '' } },
  { name: 'the cwd is relative', opts: { cwd: 'work\\repo' } },
  { name: 'the cwd is rooted on the current Windows drive only', opts: { cwd: '/work/repo' } },
  { name: 'the cwd is a share path', opts: { cwd: '\\\\server\\share' } },
] as const

for (const one of NO_FULL_PATH) {
  test(`Run is not offered and Copy still works when ${one.name}`, async ($, on) => {
    const w = world(on, one.opts)
    refuseShell(on)
    await $.tool.call({ tool: 'PowerShell', command: 'git push origin main' })
    await w.settle()
    const id = String(mine(w).entries[0]?.id)
    const ui = await $.ui.mount(MOUNT)
    expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: 'Copy only: the session folder is not known as a full path.' })).toBeDefined()
    await ui.press({ key: `copy:${id}` })
    expect(w.copies).toEqual(['git push origin main'])
    expect(w.runs).toHaveLength(0)
    await ui.unmount()
  })
}

test('the confirm and result views name a bare pwsh as found by name, and every argv element', async ($, on) => {
  const w = world(on)
  refuseShell(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git push origin main' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  expect(await shownRows(ui)).toEqual([])
  await ui.press({ key: `run:${id}` })
  expect(await ui.find({ type: 'Text', text: 'Run now runs this:' })).toBeDefined()
  expect(await shownRows(ui)).toEqual(PWSH_ROWS)
  await w.advance(700)
  await ui.press({ key: `confirm:${id}` })
  expect(w.runs).toHaveLength(1)
  expect(await shownRows(ui)).toEqual(PWSH_ROWS)
  await ui.unmount()
})

test('the confirm view names the installed pwsh and Git Bash by their full paths', async ($, on) => {
  const installed = 'C:\\Program Files\\PowerShell\\7\\pwsh.exe'
  const w = world(on, { env: { ProgramFiles: 'C:\\Program Files' } })
  w.files.set(installed, { text: '', mtimeMs: 0 })
  w.files.set(GIT_BASH, { text: '', mtimeMs: 0 })
  refuseShell(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git status' })
  await $.tool.call({ tool: 'Bash', command: 'ls' })
  await w.settle()
  const [pwshId, bashId] = mine(w).entries.map(entry => String(entry.id))
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${pwshId}` })
  await ui.press({ key: `run:${bashId}` })
  expect(await shownRows(ui)).toEqual([
    `folder: ${CWD}`,
    `argv[0]: ${installed}`,
    'argv[1]: -NoProfile',
    'argv[2]: -Command',
    'argv[3]: git status',
    `folder: ${CWD}`,
    `argv[0]: ${GIT_BASH}`,
    'argv[1]: -c',
    'argv[2]: ls',
  ])
  expect(await ui.find({ type: 'Text', text: /\(by name/ })).toBeUndefined()
  await ui.unmount()
})

test('with no Git Bash, the confirm view says Run now runs nothing', async ($, on) => {
  const w = world(on)
  refuseShell(on)
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

test('a shell that resolves differently after arming runs nothing', async ($, on) => {
  const installed = 'C:\\Program Files\\PowerShell\\7\\pwsh.exe'
  const w = world(on, { env: { ProgramFiles: 'C:\\Program Files' } })
  w.files.set(installed, { text: '', mtimeMs: 0 })
  refuseShell(on)
  await $.tool.call({ tool: 'PowerShell', command: 'git push origin main' })
  await w.settle()
  const id = String(mine(w).entries[0]?.id)
  const ui = await $.ui.mount(MOUNT)
  await ui.press({ key: `run:${id}` })
  w.files.delete(installed)
  await w.advance(700)
  await ui.press({ key: `confirm:${id}` })
  expect(w.runs).toHaveLength(0)
  expect(await ui.find({ type: 'Text', text: /resolved differently since Run was pressed/ })).toBeDefined()
  await ui.unmount()
})

// The Lander's forge: one line padded with spaces until a soft wrap would
// start a screen row with a fake argv element.
const FORGE = `git status${' '.repeat(70)}argv[4]: harmless`
const LONG = `echo ${'zz '.repeat(1330)}endzz`

const NO_RUN = [
  { name: 'a line padded to forge an argv row', command: FORGE, why: /^Copy only: it holds a run of 4 or more spaces/ },
  { name: 'a 4000-character command', command: LONG, why: /^Copy only: too long to show safely \(over 400 characters\)/ },
  { name: 'a 7-line command', command: `${'git status\n'.repeat(6)}git status`, why: /^Copy only: too many lines to show safely \(over 6\)/ },
  { name: 'a run of 4 spaces', command: 'git status    --short', why: /^Copy only: it holds a run of 4 or more spaces/ },
  { name: 'a tab', command: 'git\tstatus', why: /^Copy only: the command holds a tab or a character outside plain ASCII/ },
  { name: 'a wide character', command: 'echo \u4e2d', why: /^Copy only: the command holds a tab or a character outside plain ASCII/ },
  { name: 'a line ending in a space', command: 'git status \nls', why: /^Copy only: a line ends in a space/ },
] as const

for (const surface of SURFACES) {
  for (const one of NO_RUN) {
    test(`${one.name} gets Copy and no Run, on ${surface}`, async ($, on) => {
      const w = world(on)
      refuseShell(on)
      await $.tool.call({ tool: 'PowerShell', command: one.command })
      await w.settle()
      const entry = mine(w).entries[0]
      expect(entry?.command).toBe(one.command)
      const id = String(entry?.id)
      const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'Pane', requestId: PLUGIN, props: PANE_PROPS })
      expect(await ui.find({ key: `run:${id}` })).toBeUndefined()
      expect(await ui.find({ type: 'Text', text: one.why })).toBeDefined()
      // The arming press and the claim refuse it too, drawn or not.
      await ui.press({ key: `run:${id}` }).catch(() => undefined)
      await w.advance(700)
      await ui.press({ key: `confirm:${id}` }).catch(() => undefined)
      expect(await ui.find({ key: `confirm:${id}` })).toBeUndefined()
      expect(w.runs).toHaveLength(0)
      await ui.press({ key: `copy:${id}` })
      expect(w.copies).toEqual([one.command])
      await ui.unmount()
    })
  }

  test(`an ordinary command still gets Run, on ${surface}`, async ($, on) => {
    const w = world(on)
    refuseShell(on)
    const command = 'git -C C:\\x worktree remove C:\\y'
    await $.tool.call({ tool: 'PowerShell', command })
    await w.settle()
    const id = String(mine(w).entries[0]?.id)
    const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'Pane', requestId: PLUGIN, props: PANE_PROPS })
    await ui.press({ key: `run:${id}` })
    expect((await shownRows(ui)).at(-1)).toBe(`argv[3]: ${command}`)
    await w.advance(700)
    await ui.press({ key: `confirm:${id}` })
    expect(w.runs).toEqual([{ argv: ['pwsh', '-NoProfile', '-Command', command], cwd: CWD }])
    await ui.unmount()
  })

  test(`every confirm row starts with a label or a mark, is cut not wrapped, and gives back the command, on ${surface}`, async ($, on) => {
    const w = world(on)
    refuseShell(on)
    const command = 'git log --oneline --graph --decorate --all -- docs/one.md docs/two.md docs/three.md\nargv[9]: x'
    await $.tool.call({ tool: 'PowerShell', command })
    await w.settle()
    const id = String(mine(w).entries[0]?.id)
    const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'Pane', requestId: PLUGIN, props: PANE_PROPS })
    await ui.press({ key: `run:${id}` })
    const texts: Found[] = await ui.findAll({ type: 'Text', text: ROW })
    for (const one of texts) {
      expect(one.props?.wrap).toBe('truncate-end')
      expect((one.text ?? '').length).toBeLessThanOrEqual(49)
    }
    const rows = texts.map(one => one.text ?? '')
    const start = rows.findIndex(row => row.startsWith('argv[3]: '))
    expect(rows.filter(row => row.startsWith('argv['))).toHaveLength(4)
    const rebuilt = rows
      .slice(start)
      .map(row => (row.startsWith('argv[3]: ') ? row.slice(9) : row.startsWith('  | ') ? `\n${row.slice(4)}` : row.slice(4)))
      .join('')
    expect(rebuilt).toBe(command)
    await ui.unmount()
  })
}
