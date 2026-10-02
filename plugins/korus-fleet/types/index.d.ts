// The input contract: what the fleet script prints with -Json. The board reads these fields and
// nothing else. docs/PLUGINS.md states the same contract for a reader without this file.
export type FleetJsonRow = {
  Seat: string | null
  Box: string
  Branch: string | null
  State: string
  AgeHours: number
}

export type FleetJson = {
  receipt: {
    renderedAtUtc: string
    liveSessionsInRepo: number
    stopConditions?: string | null
  }
  rows: FleetJsonRow[]
}

// What the pane draws, derived from FleetJson.
export type FleetRow = {
  seat: string | null
  box: string
  branch: string | null
  ageHours: number
}

export type FleetBoard = {
  renderedAt: string
  liveSessions: number
  stopConditions: string | null
  running: FleetRow[]
  error: string | null
}

declare module 'claude-code' {
  interface PluginState {
    'korus-fleet': {
      board: FleetBoard | null
      isRefreshing: boolean
    }
  }
}
