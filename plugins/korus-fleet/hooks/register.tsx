import { atom, read, update } from 'claude-code'
import type { Engine, PluginOptions, Register } from 'claude-code'

import type { FleetBoard, FleetJson, FleetRow } from '../types'

// Read-only. It reads one file and runs one script; it never writes to the repository, the
// coordination directory, or any peer, and calls no file-write API.

const PANE = 'korus-fleet'
const STATUS_EVERY_MS = 60_000
// The MessageFoundry fleet script took about 26 s when measured, so the board refreshes rarely
// and only while the pane is open.
const BOARD_EVERY_MS = 5 * 60_000
const FLEET_TIMEOUT_MS = 120_000

// Where scripts/coord/seat.ps1 -Declare writes the seat. Git-ignored by `*.local.*`.
const SEAT_MARKER = '.claude/seat.local.txt'
// The userConfig default, repeated here so a load with no options still has a path.
const DEFAULT_FLEET_SCRIPT = 'scripts/coord/fleet.ps1'

const board = atom({ plugin: 'korus-fleet', key: 'board' } as const, null)
const isRefreshing = atom({ plugin: 'korus-fleet', key: 'isRefreshing' } as const, false)

type Api = Engine

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

async function refreshStatus($: Api): Promise<void> {
  const parts = [`seat ${await readSeat($)}`]
  try {
    const usage = await $.session.usage()
    if (usage.context.percent !== undefined) {
      parts.push(`ctx ${Math.round(usage.context.percent)}%`)
    }
    for (const limit of usage.rateLimits) {
      parts.push(`${limit.kind} ${Math.round(limit.percentUsed)}%`)
    }
  } catch (err) {
    parts.push(`usage unread: ${err instanceof Error ? err.name : 'error'}`)
  }
  $.ui.status(parts.join(' | '))
}

// The board consumes the FleetJson contract (types/index.d.ts) and nothing else. Anything that
// does not have that shape is reported as a contract mismatch rather than drawn half-read.
function isFleetJson(value: unknown): value is FleetJson {
  if (typeof value !== 'object' || value === null) return false
  const v = value as { receipt?: unknown; rows?: unknown }
  if (typeof v.receipt !== 'object' || v.receipt === null || !Array.isArray(v.rows)) return false
  const r = v.receipt as { renderedAtUtc?: unknown; liveSessionsInRepo?: unknown }
  if (typeof r.renderedAtUtc !== 'string' || typeof r.liveSessionsInRepo !== 'number') return false
  return v.rows.every(row => {
    if (typeof row !== 'object' || row === null) return false
    const x = row as { Box?: unknown; State?: unknown; AgeHours?: unknown }
    return typeof x.Box === 'string' && typeof x.State === 'string' && typeof x.AgeHours === 'number'
  })
}

async function loadBoard($: Api, script: string): Promise<FleetBoard> {
  const now = new Date(await $.clock.now()).toISOString()
  const failed = (error: string): FleetBoard => ({
    renderedAt: now,
    liveSessions: 0,
    stopConditions: null,
    running: [],
    error,
  })
  if (!(await $.fs.exists(script))) {
    return failed(`fleet script not found: ${script}. Set the korus-fleet fleetScript option to its path.`)
  }
  let stdout: string
  try {
    const ran = await $.process.run(['pwsh', '-NoProfile', '-File', script, '-Json'], {
      timeoutMs: FLEET_TIMEOUT_MS,
    })
    if (ran.exitCode !== 0 && ran.stdout.trim() === '') {
      return failed(`${script} exited ${ran.exitCode} with no output`)
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
  const running: FleetRow[] = parsed.rows
    .filter(row => row.State === 'RUNNING')
    .sort((a, b) => a.AgeHours - b.AgeHours)
    .map(row => ({
      seat: row.Seat ?? null,
      box: row.Box,
      branch: row.Branch ?? null,
      ageHours: row.AgeHours,
    }))
  return {
    renderedAt: parsed.receipt.renderedAtUtc,
    liveSessions: parsed.receipt.liveSessionsInRepo,
    stopConditions: parsed.receipt.stopConditions ?? null,
    running,
    error: null,
  }
}

async function refreshBoard($: Api, script: string): Promise<void> {
  if (await read($, isRefreshing)) return
  await update($, isRefreshing, () => true)
  try {
    const next = await loadBoard($, script)
    await update($, board, () => next)
  } finally {
    await update($, isRefreshing, () => false)
  }
}

async function isPaneShown($: Api): Promise<boolean> {
  const panes = await $.ui.panes()
  return panes.some(pane => pane.id === PANE && pane.isShown)
}

function age(hours: number): string {
  return hours < 1 ? `${Math.round(hours * 60)}m` : `${hours.toFixed(1)}h`
}

export const register: Register = (on, options) => {
  const script = fleetScriptFrom(options)

  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'fleet',
      description: 'Open the KORUS fleet board (read-only)',
    })
    void refreshStatus($)
    $.clock.every(STATUS_EVERY_MS, () => void refreshStatus($))
    $.clock.every(BOARD_EVERY_MS, () => {
      void isPaneShown($).then(shown => (shown ? refreshBoard($, script) : undefined))
    })
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    void refreshStatus($)
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
    const room = Math.max(1, (e.viewport?.rows ?? 24) - 7)

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
            {current.stopConditions !== null && (
              <Text color="yellow">STOP CONDITION: {current.stopConditions}</Text>
            )}
            {current.running.slice(0, room).map(row => (
              <Text>
                {(row.seat ?? 'UNDECLARED').padEnd(10)} {age(row.ageHours).padStart(6)} {row.box}
              </Text>
            ))}
            {current.running.length > room && (
              <Text dimColor>...and {current.running.length - room} more</Text>
            )}
          </Box>
        )}
      </Box>
    )
  })
}
