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
): { status: () => string | undefined; settle: () => Promise<void> } {
  let last: string | undefined
  const clock = mock.clock(on)
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  on('command.register', () => ({ value: undefined }))
  on('fs.read', () => {
    if (seat === null) throw new Error('ENOENT')
    return { value: seat }
  })
  on('session.usage', () => ({
    value: {
      startedAt: 0,
      context: { window: 200_000, tokens: 84_800, percent: 42.4 },
      rateLimits: [{ kind: 'five_hour', percentUsed: 17.6 }],
    },
  }))
  on('ui.status', ($, e) => {
    last = e.text
    return { value: undefined }
  })
  return { status: () => last, settle: clock.settle }
}

test('status line names the seat, context and rate limit', async ($, on) => {
  const engine = engineForStart(on, 'manager\n')
  await $.session.start({ cwd: '/work', surface: 'terminal', isInteractive: true })
  await engine.settle()
  expect(engine.status()).toBe('seat manager | ctx 42% | five_hour 18%')
})

test('status line reads no seat marker when the file is missing', async ($, on) => {
  const engine = engineForStart(on, null)
  await $.session.start({ cwd: '/work', surface: 'terminal', isInteractive: true })
  await engine.settle()
  expect(engine.status()).toBe('seat no seat marker | ctx 42% | five_hour 18%')
})

// The engine beneath the board: which paths exist, and what the script prints. Records every
// argv the plugin asked to run and every path it asked about.
function engineForBoard(
  on: On,
  stdout: string,
  existing: readonly string[] = [DEFAULT_SCRIPT],
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
      value: { exitCode: 0, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false },
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
}

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
