import { atom, read, update } from 'claude-code'
import type { Engine, PluginOptions, Register } from 'claude-code'

import type { FleetBoard, FleetJson, FleetRow } from '../types'

// Read-only. It reads one file and runs one script; it never writes to the repository, the
// coordination directory, or any peer, and calls no file-write API.

const PANE = 'korus-fleet'
const STATUS_EVERY_MS = 60_000
// The pilot timed one run of the MessageFoundry fleet script at about 26 s (not re-measured
// here), so the board refreshes rarely and only while the pane is open.
const BOARD_EVERY_MS = 5 * 60_000
const FLEET_TIMEOUT_MS = 120_000

// Where scripts/coord/seat.ps1 -Declare writes the seat. Git-ignored by `*.local.*`.
const SEAT_MARKER = '.claude/seat.local.txt'
// The userConfig default, repeated here so a load with no options still has a path.
const DEFAULT_FLEET_SCRIPT = 'scripts/coord/fleet.ps1'

const board = atom({ plugin: 'korus-fleet', key: 'board' } as const, null)
const isRefreshing = atom({ plugin: 'korus-fleet', key: 'isRefreshing' } as const, false)

type Api = Engine

// The status line is opt-in (owner instruction 2026-10-02). The userConfig field `statusLine`
// defaults to false, and only a stored true turns it on.
function isStatusLineOn(options: PluginOptions): boolean {
  return options['statusLine'] === true
}

function fleetScriptFrom(options: PluginOptions): string {
  const value = options['fleetScript']
  return typeof value === 'string' && value.trim() !== '' ? value.trim() : DEFAULT_FLEET_SCRIPT
}

async function readSeat($: Api): Promise<string> {
  try {
    const text = await $.fs.read(SEAT_MARKER)
    return text.trim() || 'undeclared'
  } catch {
    return 'no seat marker'
  }
}

// Short labels for the rate-limit kinds the session reports (owner instruction 2026-10-02).
// Any other kind is shown as the session names it.
const LIMIT_LABELS: ReadonlyMap<string, string> = new Map([
  ['five_hour', '5h'],
  ['seven_day', '7d'],
])

function limitLabel(kind: string): string {
  return LIMIT_LABELS.get(kind) ?? kind
}

async function refreshStatus($: Api): Promise<void> {
  const parts = [`seat ${await readSeat($)}`]
  try {
    const usage = await $.session.usage()
    if (usage.context.percent !== undefined) {
      parts.push(`ctx ${Math.round(usage.context.percent)}%`)
    }
    for (const limit of usage.rateLimits) {
      parts.push(`${limitLabel(limit.kind)} ${Math.round(limit.percentUsed)}%`)
    }
  } catch (err) {
    parts.push(`usage unread: ${err instanceof Error ? err.name : 'error'}`)
  }
  $.ui.status(parts.join(' | '))
}

// The board consumes the FleetJson contract (types/index.d.ts) and nothing else. Anything that
// does not have that shape is reported as a contract mismatch rather than drawn half-read.
function isNullableString(value: unknown): boolean {
  return value === undefined || value === null || typeof value === 'string'
}

function isFleetJson(value: unknown): value is FleetJson {
  if (typeof value !== 'object' || value === null) return false
  const v = value as { receipt?: unknown; rows?: unknown }
  if (typeof v.receipt !== 'object' || v.receipt === null || !Array.isArray(v.rows)) return false
  const r = v.receipt as { renderedAtUtc?: unknown; liveSessionsInRepo?: unknown; stopConditions?: unknown }
  if (typeof r.renderedAtUtc !== 'string' || typeof r.liveSessionsInRepo !== 'number') return false
  const stops = r.stopConditions
  if (!isNullableString(stops) && !(Array.isArray(stops) && stops.every(s => typeof s === 'string'))) {
    return false
  }
  return v.rows.every(row => {
    if (typeof row !== 'object' || row === null) return false
    const x = row as { Seat?: unknown; Box?: unknown; Branch?: unknown; State?: unknown; AgeHours?: unknown }
    return (
      typeof x.Box === 'string' &&
      typeof x.State === 'string' &&
      isNullableString(x.Seat) &&
      isNullableString(x.Branch) &&
      (x.AgeHours === null || typeof x.AgeHours === 'number')
    )
  })
}

// A script may print its stop conditions as one string or as a list, and a healthy run's list is
// empty. Both an empty list and an empty string mean "none".
function stopText(stops: FleetJson['receipt']['stopConditions']): string | null {
  const text = Array.isArray(stops) ? stops.join('; ') : (stops ?? '')
  return text.trim() === '' ? null : text
}

async function loadBoard($: Api, script: string): Promise<FleetBoard> {
  const failed = async (error: string): Promise<FleetBoard> => ({
    renderedAt: new Date(await $.clock.now()).toISOString(),
    liveSessions: 0,
    stopConditions: null,
    warning: null,
    running: [],
    error,
  })
  let stdout: string
  let warning: string | null = null
  try {
    if (!(await $.fs.exists(script))) {
      return failed(`fleet script not found: ${script}. Set the korus-fleet fleetScript option to its path.`)
    }
    const ran = await $.process.run(['pwsh', '-NoProfile', '-File', script, '-Json'], {
      timeoutMs: FLEET_TIMEOUT_MS,
    })
    if (ran.exitCode !== 0 && ran.stdout.trim() === '') {
      return failed(`${script} exited ${ran.exitCode} with no output`)
    }
    if (ran.exitCode !== 0) {
      warning = `${script} exited ${ran.exitCode}; the rows below may be incomplete`
    }
    stdout = ran.stdout
  } catch (err) {
    return failed(`${script} did not run: ${err instanceof Error ? err.message : String(err)}`)
  }
  let parsed: unknown
  try {
    parsed = JSON.parse(stdout)
  } catch {
    return failed(`${script} output was not JSON`)
  }
  if (!isFleetJson(parsed)) {
    return failed(`${script} output does not match the fleet JSON contract`)
  }
  // A row with no age sorts last rather than first, so it never reads as the newest.
  const sortAge = (h: number | null): number => (h === null ? Number.POSITIVE_INFINITY : h)
  const running: FleetRow[] = parsed.rows
    .filter(row => row.State === 'RUNNING')
    .sort((a, b) => sortAge(a.AgeHours) - sortAge(b.AgeHours))
    .map(row => ({
      seat: row.Seat ?? null,
      box: row.Box,
      branch: row.Branch ?? null,
      ageHours: row.AgeHours,
    }))
  return {
    renderedAt: parsed.receipt.renderedAtUtc,
    liveSessions: parsed.receipt.liveSessionsInRepo,
    stopConditions: stopText(parsed.receipt.stopConditions),
    warning,
    running,
    error: null,
  }
}

// The guard is module memory, set before the first await, so two presses close together cannot
// both pass it. The isRefreshing atom only drives the button label. A module reload starts with
// the guard clear, so a refresh cut off by a reload never blocks the next one.
let inFlight = false

async function refreshBoard($: Api, script: string): Promise<void> {
  if (inFlight) return
  inFlight = true
  try {
    await update($, isRefreshing, () => true)
    const next = await loadBoard($, script)
    await update($, board, () => next)
  } finally {
    inFlight = false
    await update($, isRefreshing, () => false)
  }
}

async function isPaneShown($: Api): Promise<boolean> {
  const panes = await $.ui.panes()
  return panes.some(pane => pane.id === PANE && pane.isShown)
}

function age(hours: number | null): string {
  if (hours === null) return '?'
  return hours < 1 ? `${Math.round(hours * 60)}m` : `${hours.toFixed(1)}h`
}

export const register: Register = (on, options) => {
  const script = fleetScriptFrom(options)
  const showStatus = isStatusLineOn(options)

  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'fleet',
      description: 'Open the KORUS fleet board (read-only)',
    })
    if (showStatus) {
      void refreshStatus($)
      $.clock.every(STATUS_EVERY_MS, () => void refreshStatus($))
    } else {
      // Off: clear any line a load with the option on drew before this reload, and read no usage.
      $.ui.status(undefined)
    }
    $.clock.every(BOARD_EVERY_MS, () => {
      void isPaneShown($)
        .then(shown => (shown ? refreshBoard($, script) : undefined))
        .catch(() => undefined)
    })
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    if (showStatus) void refreshStatus($)
    return done
  })

  on('command.run', { command: 'fleet' }, async $ => {
    await $.ui.open({ id: PANE, title: 'Fleet board' })
    void refreshBoard($, script)
    return { text: 'Fleet board opened. It refreshes every 5 minutes while open.' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const current = await read($, board)
    const busy = await read($, isRefreshing)

    return (
      <Box flexDirection="column">
        <Box flexDirection="row">
          <Button key="refresh" label={busy ? 'Refreshing' : 'Refresh'} onPress={() => void refreshBoard($, script)} />
        </Box>
        {current === null && <Text dimColor>{busy ? `Reading ${script} (about 30 s)...` : 'No reading yet.'}</Text>}
        {current !== null && current.error !== null && <Text color="red">{current.error}</Text>}
        {current !== null && current.error === null && (
          <Box flexDirection="column">
            <Text dimColor>
              rendered {current.renderedAt} | live in repo {current.liveSessions} | RUNNING records {current.running.length}
            </Text>
            {current.warning !== null && <Text color="yellow">WARNING: {current.warning}</Text>}
            {current.stopConditions !== null && (
              <Text color="yellow">STOP CONDITION: {current.stopConditions}</Text>
            )}
            {current.running.map(row => (
              <Text>
                {(row.seat ?? 'UNDECLARED').padEnd(10)} {age(row.ageHours).padStart(6)} {row.box}
              </Text>
            ))}
          </Box>
        )}
      </Box>
    )
  })
}
