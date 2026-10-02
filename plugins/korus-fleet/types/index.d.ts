// The input contract: what the fleet script prints with -Json. The board reads these fields and
// nothing else. docs/PLUGINS.md states the same contract for a reader without this file.
export type FleetJsonRow = {
  Seat: string | null
  Box: string
  Branch: string | null
  State: string
  // null where the script could not read the record's age.
  AgeHours: number | null
}

export type FleetJson = {
  receipt: {
    renderedAtUtc: string
    liveSessionsInRepo: number
    // One string or a list of them; an empty list or string means none.
    stopConditions?: string | string[] | null
  }
  rows: FleetJsonRow[]
}

// What the pane draws, derived from FleetJson.
export type FleetRow = {
  seat: string | null
  box: string
  branch: string | null
  ageHours: number | null
}

export type FleetBoard = {
  renderedAt: string
  liveSessions: number
  stopConditions: string | null
  // Set when the script exited non-zero but still printed a board.
  warning: string | null
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
