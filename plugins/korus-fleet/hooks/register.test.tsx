import { test, expect, mock } from 'claude-code/testing'
import type { On } from 'claude-code'

// Every fixture here is synthetic: invented seats and box names, no real paths.

const PLUGIN = 'korus-fleet'
const SURFACES = ['terminal', 'desktop'] as const
const DEFAULT_SCRIPT = 'scripts/coord/fleet.ps1'

const FLEET_JSON = JSON.stringify({
  receipt: {
    renderedAtUtc: '2026-01-01T00:00:00Z',
    liveSessionsInRepo: 2,
    stopConditions: null,
  },
  rows: [
    { Seat: 'builder', Box: 'box-beta', Branch: 'b/beta', State: 'RUNNING', AgeHours: 2.5 },
    { Seat: 'lander', Box: 'box-gamma', Branch: null, State: 'DEAD', AgeHours: 0.1 },
    { Seat: 'manager', Box: 'box-alpha', Branch: 'b/alpha', State: 'RUNNING', AgeHours: 0.5 },
  ],
})

const PANE_PROPS = {
  title: 'Fleet board',
  isFocused: false,
  bodyColumns: 80,
  placement: 'dock',
  scroll: { offset: 0, bodyRows: 20 },
  view: {},
} as const

const MOUNT = {
  plugin: PLUGIN,
  component: 'Pane',
  requestId: PLUGIN,
  props: PANE_PROPS,
  viewport: { columns: 100, rows: 30 },
} as const

// The engine beneath the plugin for a session start: the calls register makes.
function engineForStart(
  on: On,
  seat: string | null,
  rateLimits: readonly { kind: string; percentUsed: number }[] = [
    { kind: 'five_hour', percentUsed: 17.6 },
    { kind: 'seven_day', percentUsed: 3.2 },
  ],
): {
  status: () => string | undefined
  statusCalls: () => readonly (string | undefined)[]
  usageReads: () => number
  settle: () => Promise<void>
  advance: (ms: number) => Promise<void>
} {
  const calls: (string | undefined)[] = []
  let reads = 0
  const clock = mock.clock(on)
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  on('command.register', () => ({ value: undefined }))
  on('fs.read', () => {
    if (seat === null) throw new Error('ENOENT')
    return { value: seat }
  })
  on('session.usage', () => {
    reads += 1
    return {
      value: {
        startedAt: 0,
        context: { window: 200_000, tokens: 84_800, percent: 42.4 },
        rateLimits: [...rateLimits],
      },
    }
  })
  on('turn.complete', ($, e) => ({ text: e.answer }))
  on('ui.panes', () => ({ value: [] }))
  on('ui.status', ($, e) => {
    calls.push(e.text)
    return { value: undefined }
  })
  return {
    status: () => calls[calls.length - 1],
    statusCalls: () => calls,
    usageReads: () => reads,
    settle: clock.settle,
    advance: clock.advance,
  }
}

const ON = { options: { statusLine: true } } as const

test('status line is off by default: it draws nothing and reads no usage', async ($, on) => {
  const engine = engineForStart(on, 'manager\n')
  await $.session.start({ cwd: '/work', surface: 'terminal', isInteractive: true })
  await engine.settle()
  await engine.advance(10 * 60_000)
  await $.turn.complete({ answer: 'done', durationMs: 1000, isAborted: false, turnId: 'turn-main', reason: 'answer' })
  await engine.settle()
  // The one call clears a line an earlier load may have drawn.
  expect(engine.statusCalls()).toEqual([undefined])
  expect(engine.usageReads()).toBe(0)
})

test('status line, when on, redraws every minute and after each turn', ON, async ($, on) => {
  const engine = engineForStart(on, 'manager\n')
  await $.session.start({ cwd: '/work', surface: 'terminal', isInteractive: true })
  await engine.settle()
  expect(engine.usageReads()).toBe(1)
  await engine.advance(60_000)
  expect(engine.usageReads()).toBe(2)
  await $.turn.complete({ answer: 'done', durationMs: 1000, isAborted: false, turnId: 'turn-main', reason: 'answer' })
  await engine.settle()
  expect(engine.usageReads()).toBe(3)
  expect(engine.status()).toBe('seat manager | ctx 42% | 5h 18% | 7d 3%')
})

test('status line names the seat, context and rate limit', ON, async ($, on) => {
  const engine = engineForStart(on, 'manager\n')
  await $.session.start({ cwd: '/work', surface: 'terminal', isInteractive: true })
  await engine.settle()
  expect(engine.status()).toBe('seat manager | ctx 42% | 5h 18% | 7d 3%')
})

test('status line shows a rate-limit kind it has no short label for as given', ON, async ($, on) => {
  const engine = engineForStart(on, 'manager\n', [
    { kind: 'five_hour', percentUsed: 17.6 },
    { kind: 'spend_limit', percentUsed: 40 },
  ])
  await $.session.start({ cwd: '/work', surface: 'terminal', isInteractive: true })
  await engine.settle()
  expect(engine.status()).toBe('seat manager | ctx 42% | 5h 18% | spend_limit 40%')
})

test('status line reads no seat marker when the file is missing', ON, async ($, on) => {
  const engine = engineForStart(on, null)
  await $.session.start({ cwd: '/work', surface: 'terminal', isInteractive: true })
  await engine.settle()
  expect(engine.status()).toBe('seat no seat marker | ctx 42% | 5h 18% | 7d 3%')
})

// The engine beneath the board: which paths exist, and what the script prints. Records every
// argv the plugin asked to run and every path it asked about.
function engineForBoard(
  on: On,
  stdout: string,
  existing: readonly string[] = [DEFAULT_SCRIPT],
  exitCode = 0,
): { argvs: string[][]; asked: string[] } {
  const argvs: string[][] = []
  const asked: string[] = []
  mock.clock(on, { now: Date.UTC(2026, 0, 1) })
  // The engine hands this hook the path resolved against the working directory, with the
  // platform's separators, so compare by the relative tail the plugin asked for.
  on('fs.exists', ($, e) => {
    const path = e.path.replace(/\\/g, '/')
    const hit = existing.find(want => path === want || path.endsWith(`/${want}`))
    asked.push(hit ?? path)
    return { value: hit !== undefined }
  })
  on('process.run', ($, e) => {
    argvs.push([...e.argv])
    return {
      value: { exitCode, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false },
    }
  })
  return { argvs, asked }
}

for (const surface of SURFACES) {
  test(`board lists RUNNING rows newest first on ${surface}`, async ($, on) => {
    const engine = engineForBoard(on, FLEET_JSON)
    const ui = await $.ui.mount({ ...MOUNT, surface })
    expect((await ui.find({ type: 'Text', text: 'No reading yet.' }))?.text).toBe('No reading yet.')

    await ui.press({ key: 'refresh' })

    expect(engine.argvs).toEqual([['pwsh', '-NoProfile', '-File', DEFAULT_SCRIPT, '-Json']])
    const header = await ui.find({ type: 'Text', text: /RUNNING records/ })
    expect(header?.text).toContain('rendered 2026-01-01T00:00:00Z')
    expect(header?.text).toContain('live in repo 2')
    expect(header?.text).toContain('RUNNING records 2')

    const rows = (await ui.findAll({ type: 'Text', text: /box-/ })).map(row => row.text)
    expect(rows).toHaveLength(2)
    expect(rows[0]).toContain('box-alpha')
    expect(rows[0]).toContain('30m')
    expect(rows[1]).toContain('box-beta')
    expect(rows[1]).toContain('2.5h')
    expect(rows.join('\n')).not.toContain('box-gamma')
  })

  test(`board shows the parse error on ${surface} when stdout is not JSON`, async ($, on) => {
    engineForBoard(on, 'WARNING: something went wrong\n')
    const ui = await $.ui.mount({ ...MOUNT, surface })
    await ui.press({ key: 'refresh' })
    const message = `${DEFAULT_SCRIPT} output was not JSON`
    expect((await ui.find({ type: 'Text', text: message }))?.text).toBe(message)
    expect(await ui.findAll({ type: 'Text', text: /box-/ })).toHaveLength(0)
  })

  test(`board names the missing script on ${surface} and runs nothing`, async ($, on) => {
    const engine = engineForBoard(on, FLEET_JSON, [])
    const ui = await $.ui.mount({ ...MOUNT, surface })
    await ui.press({ key: 'refresh' })
    const error = await ui.find({ type: 'Text', text: /fleet script not found/ })
    expect(error?.text).toContain(`fleet script not found: ${DEFAULT_SCRIPT}`)
    expect(error?.text).toContain('fleetScript option')
    expect(engine.argvs).toHaveLength(0)
    expect(await ui.findAll({ type: 'Text', text: /box-/ })).toHaveLength(0)
  })

  test(`board refuses JSON outside the contract on ${surface}`, async ($, on) => {
    engineForBoard(on, JSON.stringify({ receipt: { renderedAtUtc: 'x' }, rows: 'none' }))
    const ui = await $.ui.mount({ ...MOUNT, surface })
    await ui.press({ key: 'refresh' })
    const message = `${DEFAULT_SCRIPT} output does not match the fleet JSON contract`
    expect((await ui.find({ type: 'Text', text: message }))?.text).toBe(message)
  })

  test(`board refuses a row whose Seat is not a string on ${surface}`, async ($, on) => {
    const rows = [{ Seat: 7, Box: 'box-alpha', Branch: null, State: 'RUNNING', AgeHours: 1 }]
    engineForBoard(on, JSON.stringify({ receipt: { renderedAtUtc: 'x', liveSessionsInRepo: 1 }, rows }))
    const ui = await $.ui.mount({ ...MOUNT, surface })
    await ui.press({ key: 'refresh' })
    expect((await ui.find({ type: 'Text', text: /does not match the fleet JSON contract/ }))?.text).toBeDefined()
  })
}

// The MessageFoundry fleet script prints stopConditions as a list, empty when healthy, and a
// null AgeHours for a record whose age it could not read. Both shapes are in the contract.
function fleetWith(stopConditions: unknown, rows: readonly object[]): string {
  return JSON.stringify({
    receipt: { renderedAtUtc: '2026-01-01T00:00:00Z', liveSessionsInRepo: 1, stopConditions },
    rows,
  })
}

const ROW = { Seat: 'builder', Box: 'box-alpha', Branch: null, State: 'RUNNING', AgeHours: 1 }

test('an empty stopConditions list draws no stop line', async ($, on) => {
  engineForBoard(on, fleetWith([], [ROW]))
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  await ui.press({ key: 'refresh' })
  expect((await ui.find({ type: 'Text', text: /RUNNING records 1/ }))?.text).toBeDefined()
  expect(await ui.findAll({ type: 'Text', text: /STOP CONDITION/ })).toHaveLength(0)
})

test('a stopConditions list is drawn joined', async ($, on) => {
  engineForBoard(on, fleetWith(['fence down', 'queue stalled'], [ROW]))
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  await ui.press({ key: 'refresh' })
  const stop = await ui.find({ type: 'Text', text: /STOP CONDITION/ })
  expect(stop?.text).toContain('fence down; queue stalled')
})

test('a row with no age is drawn with a question mark, after the aged rows', async ($, on) => {
  const unaged = { ...ROW, Box: 'box-unaged', AgeHours: null }
  engineForBoard(on, fleetWith(null, [unaged, { ...ROW, AgeHours: 3 }]))
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  await ui.press({ key: 'refresh' })
  const rows = (await ui.findAll({ type: 'Text', text: /box-/ })).map(row => row.text)
  expect(rows).toHaveLength(2)
  expect(rows[0]).toContain('box-alpha')
  expect(rows[1]).toContain('box-unaged')
  expect(rows[1]).toContain('?')
})

test('a non-zero exit with a board draws the board and a warning', async ($, on) => {
  engineForBoard(on, fleetWith(null, [ROW]), [DEFAULT_SCRIPT], 2)
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  await ui.press({ key: 'refresh' })
  const warning = await ui.find({ type: 'Text', text: /WARNING/ })
  expect(warning?.text).toContain(`${DEFAULT_SCRIPT} exited 2`)
  expect(await ui.findAll({ type: 'Text', text: /box-alpha/ })).toHaveLength(1)
})

test('a zero exit draws no warning', async ($, on) => {
  engineForBoard(on, fleetWith(null, [ROW]))
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  await ui.press({ key: 'refresh' })
  expect(await ui.findAll({ type: 'Text', text: /WARNING/ })).toHaveLength(0)
})

const CUSTOM_SCRIPT = 'tools/other-fleet.ps1'

test('the fleetScript option names the script the board runs', { options: { fleetScript: CUSTOM_SCRIPT } }, async ($, on) => {
  const engine = engineForBoard(on, FLEET_JSON, [CUSTOM_SCRIPT])
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  await ui.press({ key: 'refresh' })
  expect(engine.asked).toEqual([CUSTOM_SCRIPT])
  expect(engine.argvs).toEqual([['pwsh', '-NoProfile', '-File', CUSTOM_SCRIPT, '-Json']])
  expect((await ui.find({ type: 'Text', text: /RUNNING records 2/ }))?.text).toContain('RUNNING records 2')
})

test('a missing custom script is named by its own path', { options: { fleetScript: CUSTOM_SCRIPT } }, async ($, on) => {
  const engine = engineForBoard(on, FLEET_JSON, [DEFAULT_SCRIPT])
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  await ui.press({ key: 'refresh' })
  const error = await ui.find({ type: 'Text', text: /fleet script not found/ })
  expect(error?.text).toContain(`fleet script not found: ${CUSTOM_SCRIPT}`)
  expect(engine.argvs).toHaveLength(0)
})
