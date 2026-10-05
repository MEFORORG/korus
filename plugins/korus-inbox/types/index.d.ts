// The korus-inbox contract: what the pane draws from, held in $.state.

/** One option of a pending question, as the model offered it. */
export type InboxOption = { label: string; description: string }

/** One question of a pending AskUserQuestion call. */
export type InboxQuestion = { header: string; question: string; options: InboxOption[] }

/** Why an entry needs the owner, on the driver ladder: only these four reach the owner. */
export type InboxNeed = 'preference' | 'authority' | 'private-context' | 'cost'

/** The result of a Run the owner pressed. Held in this session only, never written to disk. */
export type InboxRun = {
  status: 'running' | 'done' | 'failed'
  startedAt: number
  finishedAt?: number
  exitCode?: number
  /** The exact argv that ran, or would have; absent when no shell was found. */
  argv?: string[]
  tail?: string
}

/**
 * One entry this session raised: an open question, a refused command whose
 * refusal hands the act to the person, or an owner signal the model filed.
 * `command` is the exact text, kept only in this session's $.state; it is
 * absent when it looked like it carried a secret, or was too long to keep, and
 * `withheld` says why.
 */
export type InboxEntry = {
  id: string
  kind: 'question' | 'refused' | 'signal'
  createdAt: number
  agentId?: string
  questions?: InboxQuestion[]
  shell?: 'Bash' | 'PowerShell'
  command?: string
  withheld?: string
  cwd?: string
  /** The refusal's first line. */
  refusal?: string
  /** The whole refusal, cleaned and cut; the blocked part is read from it. */
  detail?: string
  /** The refusal's sentence that hands the act to the person. */
  ask?: string
  /** True when the refusal was read from the call's result text, not the PreToolUse decision: the gate is not verified. */
  viaOutput?: boolean
  /** An owner signal's own fields, as the model filed them, cleaned and cut. */
  title?: string
  why?: string
  recommendedAction?: string
  needs?: InboxNeed
  reviewOutcome?: string
  confidence?: string
  /** True for a main-loop entry in a folder known as a full path; anything else is Copy only. */
  isRunnable?: boolean
  /** Why an entry is Copy only, worked out when it was recorded. */
  copyOnly?: string
  /** When the owner pressed Run; Run now is offered for a minute after it, and ignores a press within 600 ms of the last one. */
  armedAt?: number
  /** When Run now was last pressed and ignored; the 600 ms gap runs from it too. */
  quietFrom?: number
  /** The argv the arming press resolved, shown before Run now and checked again at it. */
  armedArgv?: string[]
  /** Why the arming press found no shell to run; Run now then records it and runs nothing. */
  armedError?: string
  run?: InboxRun
  /** When the entry resolved without a Run: the same part later ran fine, or the filer said it is done. */
  resolvedAt?: number
  resolvedBy?: string
}

/**
 * One entry read from another session's file in the shared folder. Every
 * field is untrusted text: it is shown and copied, never run.
 */
export type InboxRemoteEntry = {
  key: string
  sessionLabel: string
  kind: 'question' | 'refused' | 'signal'
  createdAt: number
  questions: InboxQuestion[]
  shell?: string
  command?: string
  withheld?: string
  cwd?: string
  refusal?: string
  detail?: string
  ask?: string
  viaOutput?: boolean
  title?: string
  why?: string
  recommendedAction?: string
  needs?: InboxNeed
  reviewOutcome?: string
  confidence?: string
  /**
   * Where the app shows the asking session: its desktop instance's data
   * folder and its app session id. Present only when the asking session's
   * file is fresh, so its instance is running.
   */
  place?: InboxPlace
}

/** A desktop app instance's data folder and one of its session ids. */
export type InboxPlace = { instance: string; id: string }

/** A remote entry the owner dismissed: its key and when. */
export type InboxDismissal = { key: string; at: number }

declare module 'claude-code' {
  interface PluginState {
    'korus-inbox': {
      own: InboxEntry[]
      /**
       * The newest remote entries waiting, at most the 40 the pane draws, and
       * the count of every remote entry waiting, held or not.
       */
      remoteHeld: { entries: InboxRemoteEntry[]; total: number }
      dismissed: InboxDismissal[]
      folderNote: string | null
      /** Which Details and the Done section the owner has opened, by key. */
      expanded: string[]
      /**
       * This session's title as the app's session list shows it, or null until
       * the engine has handed one over. Held here so a reload keeps it.
       */
      title: string | null
    }
  }
}
