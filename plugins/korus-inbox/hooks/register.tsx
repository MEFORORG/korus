import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type {
  InboxDismissal,
  InboxEntry,
  InboxNeed,
  InboxOption,
  InboxQuestion,
  InboxRemoteEntry,
  InboxRun,
} from '../types'

// What waits on the owner, gathered across sessions, and only what the owner
// can act on: an open question, a refused command whose refusal hands the act
// to the person, and an owner signal the model filed through the owner_action
// tool. Each session writes its own entries to one JSON file in a shared
// folder under the home folder, and every pane reads the 200 newest files of
// 256 KB or less. Entries read from disk are untrusted text: they are shown
// and copied, never run. Run exists only for this session's own entries, read
// from $.state at the moment the owner presses it.

const PLUGIN = 'korus-inbox'
const PANE = 'korus-inbox'
const COMMAND = 'inbox'
const FORMAT = 'korus-inbox/1'
const FOLDER = '.korus-inbox'
const ACTION_TOOL = 'owner_action'
const DONE_TOOL = 'owner_action_done'
// The full names the model calls. The engine names a plugin tool
// `mcp__<plugin>__<name>`; session.start replaces these with the names
// $.tool.register returns, so the match follows the engine and not this guess.
const toolNames = { action: `mcp__${PLUGIN}__${ACTION_TOOL}`, done: `mcp__${PLUGIN}__${DONE_TOOL}` }
const DAY_MS = 24 * 60 * 60 * 1000
const POLL_MS = 5000
const HEARTBEAT_MS = 10 * 60 * 1000
const ARM_MS = 60 * 1000
// A confirm this soon after the arming press is ignored, so one double click
// or a repeated Enter cannot arm and run in a single gesture.
const ARM_GAP_MS = 600
const MAX_FILE_BYTES = 256 * 1024
const MAX_FILES = 200
const MAX_ENTRIES = 50
const MAX_COMMAND = 4000
const MAX_DETAIL = 8000
const MAX_DETAIL_SHARED = 1500
const MAX_DISMISSED = 500
const MAX_PENDING_REFUSALS = 200
const RUN_TIMEOUT_MS = 5 * 60 * 1000
const TAIL_LINES = 15
const HEAD_CUT = 80
const GIT_BASH = 'C:\\Program Files\\Git\\bin\\bash.exe'

const own = atom({ plugin: 'korus-inbox', key: 'own' } as const, [])
const remote = atom({ plugin: 'korus-inbox', key: 'remote' } as const, [])
const dismissed = atom({ plugin: 'korus-inbox', key: 'dismissed' } as const, [])
const folderNote = atom({ plugin: 'korus-inbox', key: 'folderNote' } as const, null)
const expanded = atom({ plugin: 'korus-inbox', key: 'expanded' } as const, [])

type Engine = EngineInterface

// ---------------------------------------------------------------- text rules

// Control characters (ANSI escapes included), zero-width and bidirectional
// marks, and Unicode line separators are stripped from every string shown or
// copied, so a file cannot repaint the terminal, hide text, or reorder what
// the owner reads. Newlines and tabs stay, and every line is drawn.
const CONTROL =
  /[\u0000-\u0008\u000b-\u001f\u007f-\u009f\u00ad\u034f\u061c\u180e\u200b-\u200f\u2028-\u202e\u2060-\u2069\ufe00-\ufe0f\ufeff\ufff9-\ufffb\u{e0000}-\u{e007f}]/gu

function clean(value: unknown, max: number): string {
  if (typeof value !== 'string') return ''
  const text = value.replace(CONTROL, '')
  return text.length > max ? `${text.slice(0, max)} [cut]` : text
}

function flat(text: string): string {
  return text.replace(/\s+/g, ' ').trim()
}

function cut(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)} [cut]` : text
}

// A command or refusal that looks like it carries a secret is never stored:
// a placeholder takes its place. It errs toward withholding: a false match
// costs the owner a Copy, a missed one writes the secret to a shared file.
const SECRET_WORDS =
  /token|passw|secret|credential|api[_-]?key|bearer\s|authorization:|sshpass|asplaintext|convertto-securestring|(key|pass|pwd|pw)\s*[=:]/i
const URL_CREDENTIALS = /[a-z][a-z0-9+.-]*:\/\/[^\s/:@]+:[^\s/@]+@/i
const BASIC_AUTH = /(^|\s)(-u\s*|--user[=\s]+)\S+:\S+/
const MYSQL_PASSWORD = /\bmysql\w*\b.*\s-p\S/i
const KNOWN_KEYS = /\b(AKIA|ASIA)[A-Z0-9]{16}\b|\b(ghp|gho|ghs|ghu|github_pat|sk|xox[abp])[-_][A-Za-z0-9_-]{10,}/
const HEX_RUN = /[0-9a-f]{32,}/i
const LONG_RUN = /[A-Za-z0-9+/_=-]{32,}/g

function looksSecret(text: string): boolean {
  if (SECRET_WORDS.test(text) || URL_CREDENTIALS.test(text) || BASIC_AUTH.test(text)) return true
  if (MYSQL_PASSWORD.test(text) || KNOWN_KEYS.test(text)) return true
  if (HEX_RUN.test(text)) return true
  for (const run of text.match(LONG_RUN) ?? []) {
    // A path is a long run too; a key has digits and both cases in it.
    if (/[0-9]/.test(run) && /[a-z]/.test(run) && /[A-Z]/.test(run)) return true
  }
  return false
}

// Questions are prose, where "token" and "key" are ordinary words, so they
// are held to the shapes that carry a value rather than to the words.
function questionLooksSecret(text: string): boolean {
  return (
    /(token|password|passwd|secret|key|pass|pwd)\s*[=:]\s*\S/i.test(text) ||
    URL_CREDENTIALS.test(text) ||
    KNOWN_KEYS.test(text) ||
    HEX_RUN.test(text) ||
    (text.match(LONG_RUN) ?? []).some(run => /[0-9]/.test(run) && /[a-z]/.test(run) && /[A-Z]/.test(run))
  )
}

const WITHHELD_SECRET = 'command withheld: it looked like it carried a secret'
const WITHHELD_LONG = `command withheld: longer than ${MAX_COMMAND} characters`
const REFUSAL_SECRET = 'refusal text withheld: it looked like it carried a secret'
const QUESTION_SECRET = '(text withheld: it looked like it carried a secret)'
const NO_ACTION = 'No recommended action recorded.'

// The text a session's tool result starts with when a settings PreToolUse
// hook blocked the call (seen 2026-10-02: "PreToolUse:PowerShell hook error:
// BLOCKED: ..."). The classic.PreToolUse hook below is the primary signal;
// this is the fallback for a refusal that reached the result some other way.
const HOOK_REFUSAL = /^\s*PreToolUse:(Bash|PowerShell) hook\b/

// The prefixes a refusal carries before its reason: the hook wrapper and the
// gate's own BLOCKED or DENIED.
const REFUSAL_PREFIX = /^\s*(PreToolUse:\w+ hook( error| blocked)?\s*:|BLOCKED\s*:|DENIED\s*:|Error\s*:)\s*/i

function stripPrefix(text: string): string {
  let rest = text
  for (let i = 0; i < 4; i++) {
    const next = rest.replace(REFUSAL_PREFIX, '')
    if (next === rest) break
    rest = next
  }
  return rest
}

function firstLine(text: string): string {
  const line = text.split(/\r?\n/).find(one => one.trim() !== '') ?? ''
  return clean(line.trim(), 300)
}

// The refusal's reason as one short sentence: prefixes off, cut at the first
// sentence end.
function whyOf(text: string | undefined): string {
  if (text === undefined || text === '') return ''
  const body = flat(stripPrefix(text))
  const end = body.search(/[.!?](\s|$)/)
  return cut(end < 0 ? body : body.slice(0, end + 1), 200)
}

function lastLines(text: string, count: number): string {
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  while (lines.length > 0 && lines[lines.length - 1]?.trim() === '') lines.pop()
  return clean(lines.slice(-count).join('\n'), 3000)
}

function age(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000))
  if (s < 60) return `${s}s`
  const m = Math.round(s / 60)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  return `${h}h${String(m % 60).padStart(2, '0')}m`
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

// ------------------------------------------------ what hands the act over

// A refused command reaches the inbox only when its refusal hands the act to
// the person. Each row names a phrase a gate prints and the step it maps to.
// The order is priority: the first row that matches decides the step. Read
// off the gates' own deny texts on 2026-10-02 (worktree_gate.ps1 rules 3,
// 3b, 3d and 1a, and its announce/off row); a refusal no row matches is a
// guard the agent routes around itself, and it is not recorded at all.
type ActionRow = {
  name: string
  phrase: RegExp
  act: (match: RegExpExecArray, part: string) => string
}

const ACTION_ROWS: readonly ActionRow[] = [
  {
    name: 'I need you to confirm',
    phrase: /\bI\s+need\s+you\s+to\s+confirm\b([^."\n]*)/i,
    act: (match, part) => `Confirm${match[1] !== undefined && match[1].trim() !== '' ? ` ${flat(match[1])}` : ' it is safe'}, then run: ${part}`,
  },
  {
    name: 'from a PLAIN terminal',
    phrase: /\bplain\s+terminal\b/i,
    act: (match, part) => `Run this in a plain terminal: ${part}`,
  },
  {
    name: 'governs agents, not you',
    phrase: /\bgoverns\s+agents,?\s+not\s+you\b/i,
    act: (match, part) => `Run this in a plain terminal: ${part}`,
  },
  {
    name: "the user's call",
    phrase: /\buser['\u2019]?s\s+call\b/i,
    act: (match, part) => `Decide; if you agree, run it yourself: ${part}`,
  },
  {
    name: 'a human act',
    phrase: /\bhuman\s+act\b/i,
    act: (match, part) => `Do it yourself, from a plain terminal: ${part}`,
  },
  {
    name: 'only the owner',
    phrase: /\bonly\s+the\s+owner\b/i,
    act: (match, part) => `Only you can do this; if you agree, run it yourself: ${part}`,
  },
  {
    name: 'let the user decide',
    phrase: /\blet\s+the\s+user\s+decide\b/i,
    act: () => 'Decide what the session asks under "For you".',
  },
  {
    name: 'ask the user',
    phrase: /\bask\s+the\s+user\b/i,
    act: () => 'Answer what the session asks under "For you".',
  },
  {
    name: 'I need you to',
    phrase: /\bI\s+need\s+you\s+to\b/i,
    act: () => 'Do what the session asks under "For you".',
  },
]

type Handover = { row: ActionRow; match: RegExpExecArray }

function handover(text: string | undefined): Handover | undefined {
  if (text === undefined) return undefined
  for (const row of ACTION_ROWS) {
    const match = row.phrase.exec(text)
    if (match !== null) return { row, match }
  }
  return undefined
}

// The refusal's sentence around the phrase that hands the act over.
function sentenceAround(text: string, at: number, length: number): string {
  let start = 0
  for (const m of text.slice(0, at).matchAll(/[.!?]\s|:\n|\n[ \t]*\*[ \t]|\n[ \t]*\n/g)) start = m.index + m[0].length
  const after = text.slice(at + length)
  const end = after.search(/[.!?](\s|$)|:\n|\n[ \t]*\n/)
  const tail = end < 0 ? after : after.slice(0, end + 1)
  return cut(flat(`${text.slice(start, at + length)}${tail}`).replace(/^\*\s*/, ''), 240)
}

// ------------------------------------------------- the blocked part of a line

// The first single-quoted span in the refusal. A quote inside a word (don't)
// opens nothing, so a contraction cannot start a span.
const QUOTED = /(?:^|[^A-Za-z0-9])'([^']+)'(?![A-Za-z0-9])/

// The part must sit in the command as a whole subcommand: from the line's
// start or after a separator, to the line's end or before one. A pipe before
// it is refused, since alone the part would read no input.
const BEFORE_OK = /(^|;|&&|\|\||\n)[ \t]*$/
const AFTER_OK = /^[ \t]*($|;|&&|\|\||\|(?!\|)|\r?\n)/

type Shell = string | undefined

// True only when the shell would read this text plainly, ending at top level:
// outside every quote, with no comment, here-doc, here-string, redirect,
// subshell, brace group, call or background operator, escape or line
// continuation anywhere in it. A shape it cannot read for sure counts as not
// plain, so the part is not used and the card falls back to Copy of the whole
// line. Bash and PowerShell differ on escapes; an unknown shell gets both rules.
function isPlain(text: string, shell: Shell): boolean {
  const isBash = shell !== 'PowerShell'
  // PowerShell reads typographic quotes as quotes, and after `--%` it passes
  // the rest of the line through verbatim, so neither can be read plainly.
  if (/[^\x00-\x7f]/.test(text) || text.includes('--%')) return false
  let quote = ''
  for (let i = 0; i < text.length; i++) {
    const c = text[i] ?? ''
    if (quote === "'") {
      if (c === "'") quote = ''
      continue
    }
    if (quote === '"') {
      if (c === '`' || c === '$' || (isBash && c === '\\')) return false
      if (c === '"') quote = ''
      continue
    }
    if (c === "'" || c === '"') {
      if (text[i - 1] === '$' || text[i - 1] === '@') return false
      quote = c
      continue
    }
    if ('#{}()<>`'.includes(c)) return false
    if (isBash && c === '\\') return false
    if (c === '&' && text[i + 1] !== '&' && text[i - 1] !== '&') return false
  }
  return quote === ''
}

// Where the part sits in the command as a plain, whole subcommand, or -1.
function locatePart(command: string, part: string, shell: Shell): number {
  if (!isPlain(part, shell)) return -1
  let from = 0
  for (;;) {
    const at = command.indexOf(part, from)
    if (at < 0) return -1
    const before = command.slice(0, at)
    const isPiped = /(^|[^|])\|\s*$/.test(before)
    if (!isPiped && BEFORE_OK.test(before) && AFTER_OK.test(command.slice(at + part.length)) && isPlain(before, shell)) return at
    from = at + 1
  }
}

// The exact subcommand the refusal quotes, or undefined when the first quoted
// span is not a plain, whole subcommand of the recorded command, verbatim.
function blockedPart(command: string | undefined, refusal: string | undefined, shell: Shell): string | undefined {
  if (command === undefined || refusal === undefined) return undefined
  const match = QUOTED.exec(refusal)
  const part = match?.[1]
  if (part === undefined || part.trim() === '' || part !== part.trim()) return undefined
  return locatePart(command, part, shell) >= 0 ? part : undefined
}

// Words in the earlier parts of the line that can change the folder, the
// environment or the control flow the part ran under, so the part alone could
// act somewhere else than it would have. Matched anywhere, quotes included:
// a false match costs a Run, a missed one runs in the wrong place.
const CONTEXT_CHANGE =
  /(^|[^\w$-])(cd|chdir|pushd|popd|set-location|push-location|pop-location|sl|export|source|set|setx|unset|env|builtin|command|exec|eval|alias|function|if|then|else|elif|do|while|until|for|foreach|case|trap|exit|return|break|continue|throw)(?![\w-])|\$env:|\$[^\s;|&=]*\s*=(?!=)|(^|[;&|\n])\s*\.(?=\s)|(^|[;&|\n\s])[A-Za-z_]\w*=/i

function changesContext(command: string, part: string, shell: Shell): boolean {
  const at = locatePart(command, part, shell)
  return at > 0 && CONTEXT_CHANGE.test(command.slice(0, at))
}

// ---------------------------------------------------------- the shared folder

let folderCache: { dir: string; sep: string } | null | undefined

async function folder($: Engine): Promise<{ dir: string; sep: string } | null> {
  if (folderCache !== undefined) return folderCache
  const profile = await $.env.get('USERPROFILE')
  const home = profile !== undefined && profile !== '' ? profile : await $.env.get('HOME')
  if (home === undefined || !(/^[A-Za-z]:[\\/]/.test(home) || home.startsWith('/'))) {
    folderCache = null
    return null
  }
  const sep = home.includes('\\') ? '\\' : '/'
  folderCache = { dir: `${home.replace(/[\\/]+$/, '')}${sep}${FOLDER}`, sep }
  return folderCache
}

const SAFE_STEM = /^[A-Za-z0-9_-]{1,100}$/

// An entry is done when a Run of it exited 0, or it resolved without one (the
// same part later ran fine in this session, or its filer said so). A failed
// Run, or one that exited non-zero, leaves it waiting.
function isDone(entry: InboxEntry): boolean {
  if (entry.kind === 'question') return false
  if (entry.resolvedAt !== undefined) return true
  return entry.run?.status === 'done' && entry.run.exitCode === 0
}

function isWaiting(entry: InboxEntry): boolean {
  return !isDone(entry)
}

// THE ONE COUNT. The band, the pane header, the waiting list and /inbox all
// take their numbers from this, so the three never disagree.
function waitingOf(
  mine: readonly InboxEntry[],
  theirs: readonly InboxRemoteEntry[],
): { own: InboxEntry[]; remote: InboxRemoteEntry[]; count: number } {
  const waitingOwn = mine.filter(isWaiting)
  return { own: waitingOwn, remote: [...theirs], count: waitingOwn.length + theirs.length }
}

async function waiting($: Engine): Promise<ReturnType<typeof waitingOf>> {
  return waitingOf(await read($, own), await read($, remote))
}

let writeChain: Promise<void> = Promise.resolve()
let lastWritten = ''
// Sessions whose ended file is written: a late write (a question's finally,
// a heartbeat) must not bring them back with ended:false.
const endedIds = new Set<string>()

async function label($: Engine): Promise<string> {
  const root = await $.session.root().catch(() => '')
  const base = root.split(/[\\/]/).filter(part => part !== '').pop() ?? 'session'
  return clean(base, 60)
}

// Writes this session's file, queued so two writes never interleave. $.fs has
// no rename and no delete, so the write is in place and whole; a reader that
// catches it half-written fails to parse it and reads it again next poll.
function publish($: Engine, options: { ended?: string; heartbeat?: boolean } = {}): Promise<void> {
  writeChain = writeChain
    .then(async () => {
      const place = await folder($)
      if (place === null) return
      const sessionId = options.ended ?? (await $.session.id())
      if (!SAFE_STEM.test(sessionId)) return
      if (options.ended === undefined && endedIds.has(sessionId)) return
      if (options.ended !== undefined) endedIds.add(sessionId)
      const path = `${place.dir}${place.sep}${sessionId}.json`
      const now = await $.clock.now()
      const entries = options.ended !== undefined ? [] : (await read($, own)).filter(isWaiting)
      const gone = options.ended !== undefined ? [] : await read($, dismissed)
      const body = {
        format: FORMAT,
        sessionId,
        label: await label($),
        updatedAt: now,
        ended: options.ended !== undefined,
        // Run output is never written: only what the owner must act on.
        entries: entries.map(entry => ({
          id: entry.id,
          kind: entry.kind,
          createdAt: entry.createdAt,
          questions: entry.questions,
          shell: entry.shell,
          command: entry.command === undefined ? undefined : clean(entry.command, MAX_COMMAND),
          withheld: entry.withheld,
          cwd: entry.cwd,
          refusal: entry.refusal,
          detail: entry.detail === undefined ? undefined : cut(entry.detail, MAX_DETAIL_SHARED),
          ask: entry.ask,
          viaOutput: entry.viaOutput,
          title: entry.title,
          why: entry.why,
          recommendedAction: entry.recommendedAction,
          needs: entry.needs,
          reviewOutcome: entry.reviewOutcome,
          confidence: entry.confidence,
        })),
        dismissed: gone.filter(one => now - one.at < DAY_MS).map(one => one.key),
      }
      const isEmpty = body.entries.length === 0 && body.dismissed.length === 0 && !body.ended
      if (isEmpty && lastWritten === '' && !(await $.fs.exists(path).catch(() => false))) return
      const text = JSON.stringify(body)
      const stamp = text.replace(/"updatedAt":\d+,/, '')
      if (stamp === lastWritten && options.ended === undefined && options.heartbeat !== true) return
      await $.fs.write(path, text)
      lastWritten = stamp
      if ((await read($, folderNote)) !== null) await update($, folderNote, () => null)
    })
    .catch(async (error: unknown) => {
      const note = clean(`could not write the shared folder: ${errorText(error)}`, 200)
      await update($, folderNote, () => note).catch(() => undefined)
    })
  return writeChain
}

// ------------------------------------------------------------ reading others

function guardProse(text: string): string {
  return questionLooksSecret(text) ? QUESTION_SECRET : text
}

function parseQuestions(value: unknown): InboxQuestion[] {
  if (!Array.isArray(value)) return []
  return value.slice(0, 4).flatMap((one: unknown): InboxQuestion[] => {
    if (typeof one !== 'object' || one === null) return []
    const q = one as Record<string, unknown>
    const options = Array.isArray(q.options) ? q.options : []
    return [
      {
        header: guardProse(clean(q.header, 60)),
        question: guardProse(clean(q.question, 1000)),
        options: options.slice(0, 6).flatMap((opt: unknown): InboxOption[] => {
          if (typeof opt !== 'object' || opt === null) return []
          const o = opt as Record<string, unknown>
          return [{ label: guardProse(clean(o.label, 100)), description: guardProse(clean(o.description, 300)) }]
        }),
      },
    ]
  })
}

const NEEDS: readonly InboxNeed[] = ['preference', 'authority', 'private-context', 'cost']

function asNeed(value: unknown): InboxNeed | undefined {
  return NEEDS.find(one => one === value)
}

function prose(value: unknown, max: number): string | undefined {
  if (typeof value !== 'string') return undefined
  const text = clean(value, max)
  return text === '' ? undefined : guardProse(text)
}

type ParsedFile = { entries: InboxRemoteEntry[]; dismissed: string[] }

const NOTHING: ParsedFile = { entries: [], dismissed: [] }

// Everything here is untrusted: each field is checked for type, cut to a
// length, stripped of control characters, and a command that looks like a
// secret is withheld even though the writing session should have done so.
// Undefined means the text did not parse (a write in flight); a file that
// parsed but is ended, stale or of another format reads as holding nothing.
// A refused entry whose own words do not hand the act to the person is not
// actionable, so it is dropped here too, whoever wrote it.
function parseFile(stem: string, text: string, now: number): ParsedFile | undefined {
  let raw: unknown
  try {
    raw = JSON.parse(text)
  } catch {
    return undefined
  }
  if (typeof raw !== 'object' || raw === null) return NOTHING
  const file = raw as Record<string, unknown>
  if (file.format !== FORMAT || file.ended === true) return NOTHING
  if (typeof file.updatedAt !== 'number' || now - file.updatedAt > DAY_MS) return NOTHING
  const sessionLabel = `${clean(file.label, 60) || 'session'} ${stem.slice(0, 8)}`
  const list = Array.isArray(file.entries) ? file.entries.slice(0, MAX_ENTRIES) : []
  const entries = list.flatMap((one: unknown): InboxRemoteEntry[] => {
    if (typeof one !== 'object' || one === null) return []
    const e = one as Record<string, unknown>
    if (typeof e.id !== 'string' || !/^[A-Za-z0-9_.-]{1,100}$/.test(e.id)) return []
    if (e.kind !== 'question' && e.kind !== 'refused' && e.kind !== 'signal') return []
    if (typeof e.createdAt !== 'number' || !Number.isFinite(e.createdAt)) return []
    if (now - e.createdAt > DAY_MS || e.createdAt - now > 5 * 60 * 1000) return []
    let command = typeof e.command === 'string' ? clean(e.command, MAX_COMMAND) : undefined
    let withheld = typeof e.withheld === 'string' ? clean(e.withheld, 120) : undefined
    if (command !== undefined && looksSecret(command)) {
      command = undefined
      withheld = WITHHELD_SECRET
    }
    let refusal = typeof e.refusal === 'string' ? clean(e.refusal, 300) : undefined
    if (refusal !== undefined && looksSecret(refusal)) refusal = REFUSAL_SECRET
    let detail = typeof e.detail === 'string' ? clean(e.detail, MAX_DETAIL_SHARED) : undefined
    if (detail !== undefined && looksSecret(detail)) detail = REFUSAL_SECRET
    const ask = prose(e.ask, 300)
    if (e.kind === 'refused' && (ask === undefined || (ask !== QUESTION_SECRET && handover(ask) === undefined))) return []
    return [
      {
        key: `${stem}:${e.id}`,
        sessionLabel,
        kind: e.kind,
        createdAt: e.createdAt,
        questions: e.kind === 'question' ? parseQuestions(e.questions) : [],
        shell: e.shell === 'Bash' || e.shell === 'PowerShell' ? e.shell : undefined,
        command,
        withheld,
        cwd: typeof e.cwd === 'string' ? clean(e.cwd, 500) : undefined,
        refusal,
        detail,
        ask,
        viaOutput: e.viaOutput === true,
        title: prose(e.title, 200),
        why: prose(e.why, 600),
        recommendedAction: prose(e.recommendedAction, 400),
        needs: asNeed(e.needs),
        reviewOutcome: prose(e.reviewOutcome, 300),
        confidence: prose(e.confidence, 120),
      },
    ]
  })
  const gone = Array.isArray(file.dismissed)
    ? file.dismissed
        .slice(0, MAX_DISMISSED)
        .filter((key): key is string => typeof key === 'string' && key.length <= 220)
    : []
  return { entries, dismissed: gone }
}

const lastGood = new Map<string, { mtimeMs: number; parsed: ParsedFile }>()

// The one way the pane opens, from /inbox and from the band's Button alike.
async function openInbox($: Engine): Promise<number> {
  await poll($).catch(() => undefined)
  await $.ui.open({ id: PANE, title: 'Owner inbox' })
  return (await waiting($)).count
}

async function poll($: Engine): Promise<void> {
  const place = await folder($)
  if (place === null) {
    await update($, folderNote, () => 'no home folder in USERPROFILE or HOME; the shared folder is off')
    return
  }
  const me = await $.session.id()
  const now = await $.clock.now()
  const listing = await $.fs.list(place.dir).catch(() => [])
  const files = listing
    .filter(one => one.kind === 'file' && !one.isLink && one.name.endsWith('.json'))
    .filter(one => one.name !== `${me}.json` && now - one.mtimeMs < DAY_MS && one.size <= MAX_FILE_BYTES)
    .sort((a, b) => b.mtimeMs - a.mtimeMs)
    .slice(0, MAX_FILES)
  const found: InboxRemoteEntry[] = []
  const goneKeys = new Set((await read($, dismissed)).map(one => one.key))
  const seen = new Set<string>()
  for (const one of files) {
    const stem = one.name.slice(0, -'.json'.length)
    if (!SAFE_STEM.test(stem)) continue
    seen.add(stem)
    const cached = lastGood.get(stem)
    let parsed = cached !== undefined && cached.mtimeMs === one.mtimeMs ? cached.parsed : undefined
    if (parsed === undefined) {
      const text = await $.fs.read(`${place.dir}${place.sep}${one.name}`).catch(() => undefined)
      // The listing checked the size; a file can grow between the listing and the read.
      parsed = typeof text === 'string' && text.length <= MAX_FILE_BYTES ? parseFile(stem, text, now) : undefined
      if (parsed !== undefined) lastGood.set(stem, { mtimeMs: one.mtimeMs, parsed })
      else if (cached !== undefined) parsed = cached.parsed // a write in flight: keep the last good read
      else continue
    }
    for (const key of parsed.dismissed) goneKeys.add(key)
    found.push(...parsed.entries.filter(entry => now - entry.createdAt < DAY_MS))
  }
  for (const stem of [...lastGood.keys()]) if (!seen.has(stem)) lastGood.delete(stem)

  const keys = new Set<string>()
  const visible = found
    .filter(entry => !goneKeys.has(entry.key) && !keys.has(entry.key) && keys.add(entry.key) !== undefined)
    .sort((a, b) => b.createdAt - a.createdAt)
  const current = await read($, remote)
  if (JSON.stringify(current) !== JSON.stringify(visible)) await update($, remote, () => visible)

  // A Dismiss pressed in another pane clears one of this session's entries
  // here too. Any file can name one, so this only ever hides, never adds.
  // A running entry stays, so its result is not lost. Own entries age out at
  // the same 24 hours readers use, so every pane counts the same set.
  const isGone = (entry: InboxEntry): boolean =>
    entry.run?.status !== 'running' && (goneKeys.has(`${me}:${entry.id}`) || now - entry.createdAt >= DAY_MS)
  const mine = await read($, own)
  if (mine.some(isGone)) {
    await update($, own, list => list.filter(entry => !isGone(entry)))
    void publish($)
  }
}

// ----------------------------------------------------------------- recording

async function addOwn($: Engine, entry: InboxEntry): Promise<void> {
  // Done entries go first when the list is full, so a waiting one is kept.
  await update($, own, list => {
    const next = [...list.filter(one => one.id !== entry.id), entry]
    while (next.length > MAX_ENTRIES) {
      const doneAt = next.findIndex(isDone)
      next.splice(doneAt >= 0 ? doneAt : 0, 1)
    }
    return next
  })
  void publish($)
}

async function removeOwn($: Engine, id: string): Promise<void> {
  await update($, own, list => list.filter(one => one.id !== id))
  void publish($)
}

// The exact command is kept for Run; the shared file and the screen get it
// cleaned. Either spelling looking like a secret withholds it.
function captureCommand(command: string): { command?: string; withheld?: string } {
  if (looksSecret(command) || looksSecret(clean(command, MAX_COMMAND + 1))) return { withheld: WITHHELD_SECRET }
  if (command.length > MAX_COMMAND) return { withheld: WITHHELD_LONG }
  return { command }
}

// A refused command that the same session later ran fine is no longer the
// owner's: the blocked part (or, with none, the whole line) ran as a whole
// subcommand of a later main-loop call that did not error, in the same
// folder, read by the same plain-text rule the blocked part uses.
async function resolveBySuccess($: Engine, command: string, shell: Shell, cwd: string): Promise<void> {
  const mine = await read($, own)
  const target = (one: InboxEntry): string | undefined =>
    one.kind === 'refused' ? (blockedPart(one.command, one.detail, one.shell) ?? one.command) : undefined
  const matches = (one: InboxEntry): boolean => {
    const text = target(one)
    return (
      isWaiting(one) &&
      one.run?.status !== 'running' &&
      one.cwd === clean(cwd, 500) &&
      text !== undefined &&
      (command === text || locatePart(command, text, shell) >= 0)
    )
  }
  if (!mine.some(matches)) return
  const now = await $.clock.now()
  await update($, own, list =>
    list.map(one => (matches(one) ? { ...one, resolvedAt: now, resolvedBy: 'it later ran fine in this session' } : one)),
  )
  void publish($)
}

// ----------------------------------------------------------------------- run

// Run happens only in a folder known as a full path. A failed $.session.cwd()
// records an empty one, and an empty or relative cwd would run the command in
// whatever folder the host process happens to be in.
// On Windows only a drive path counts: `/x` there is relative to the current
// drive. A `//` or `\\` share path is refused everywhere.
function isAbsolutePath(path: string | undefined, isWindows?: boolean): path is string {
  if (path === undefined) return false
  if (/^[A-Za-z]:[\\/]/.test(path)) return true
  return isWindows !== true && path.startsWith('/') && !path.startsWith('//')
}

async function onWindows($: Engine): Promise<boolean> {
  return (await $.env.get('ProgramFiles')) !== undefined || (await folder($))?.sep === '\\'
}

// argv[0] as the owner reads it. A bare name is looked up by the process
// runner, and on Windows that lookup can try the run folder before PATH, so
// the screen says so rather than implying a known file.
function binaryText(binary: string): string {
  return /[\\/]/.test(binary) ? binary : `${binary} (by name: PATH, and on Windows the run folder first)`
}

// The confirm view promises the owner reads exactly what runs. Text that soft-
// wraps can start a screen line with a forged `argv[N]:`, and a long text can
// bury its payload far from Run now. So Run is offered only for text the view
// can show faithfully, and the view draws every row itself, one Text each, cut
// at the edge rather than wrapped.
//
// RUN_CHUNK: the view breaks a line into rows of at most 40 characters. With a
// prefix of at most 12 (`Blocked: `, `argv[3]: `, `  line 2: `), a row needs
// at most RUN_COLUMNS, 52 cells. A pane narrower than that would cut rows
// short, so it offers no Run.
// MAX_RUN_CHARS: 400 characters is at most 10 such rows. With the line breaks
// below the whole text fits in about 16 rows, on one screen with Run now.
// MAX_RUN_LINES: 6 lines. A blocked part is one or two lines; 6 still lets a
// short script run, and more is a script the owner should read in an editor.
// SPACE_RUN: 4 or more spaces in a row. Padding is how a wrapped line forges a
// row start; an ordinary command rarely holds more than 2 together. No row
// wraps now, so this guards the rows' columns, not their starts.
// LABEL_LIKE: any label the views and the card draw: `argv[`, `folder:`,
// `line 2:`, `out:`, `error:`, a shell name and colon, and the card's own
// Blocked, Why, From, Command, Do this and For you. The cut falls at the same
// place on every pane, so a command could put `argv[4]: x` at the start of a
// `  + ` row and have it read as a new row. Text holding a label is Copy only.
// Each is matched anywhere, since the cut can fall right before it: so
// `stdout:` is Copy only too, while a bare `sys.argv` with no `[` still runs.
// RUN_ASCII: printable ASCII and newlines only. Every such character is one
// cell wide on every surface. A tab, a wide character, a combining mark or a
// look-alike letter is not, so the rows above would not line up as counted.
// A line that ends in a space hides that space at the row's end, and a shell
// can read `\ ` before a newline differently from `\`, so that is Copy only too.
const RUN_CHUNK = 40
const MAX_RUN_CHARS = 400
const MAX_RUN_LINES = 6
const SPACE_RUN = /[^\S\n]{4,}/
const RUN_ASCII = /^[\x20-\x7e\n]*$/
const TRAILING_SPACE = / (\n|$)/
const LABEL_LIKE = /argv\s*\[|(folder|out|error|bash|shell|blocked|why|from|command|do this|for you)\s*:|line\s*\d+\s*:/i
const RUN_COLUMNS = 12 + RUN_CHUNK

type ShowProblem = 'stripped' | 'ascii' | 'long' | 'lines' | 'spaces' | 'trailing' | 'label'

// Why the view cannot show this text faithfully, or undefined when it can.
function showProblem(text: string, maxLines: number): ShowProblem | undefined {
  if (clean(text, MAX_COMMAND) !== text) return 'stripped'
  if (!RUN_ASCII.test(text)) return 'ascii'
  if (text.length > MAX_RUN_CHARS) return 'long'
  if (text.split('\n').length > maxLines) return 'lines'
  if (SPACE_RUN.test(text)) return 'spaces'
  if (TRAILING_SPACE.test(text)) return 'trailing'
  if (LABEL_LIKE.test(text)) return 'label'
  return undefined
}

const COMMAND_PROBLEM: Record<ShowProblem, string> = {
  stripped: 'Copy only: the command holds characters the screen cannot show.',
  ascii: 'Copy only: the command holds a tab or a character outside plain ASCII, which the screen cannot show at a known width.',
  long: `Copy only: too long to show safely (over ${MAX_RUN_CHARS} characters).`,
  lines: `Copy only: too many lines to show safely (over ${MAX_RUN_LINES}).`,
  spaces: 'Copy only: it holds a run of 4 or more spaces, which can line text up to look like something else.',
  trailing: 'Copy only: a line ends in a space, which the screen cannot show.',
  label: 'Copy only: it holds a label the card draws, such as `argv[` or `out:`, which could read as a row of it.',
}

const FOLDER_PROBLEM: Record<ShowProblem, string> = {
  stripped: 'Copy only: its folder holds characters the screen cannot show.',
  ascii: 'Copy only: its folder holds a tab or a character outside plain ASCII, which the screen cannot show at a known width.',
  long: `Copy only: its folder is too long to show safely (over ${MAX_RUN_CHARS} characters).`,
  lines: 'Copy only: its folder holds a line break.',
  spaces: 'Copy only: its folder holds a run of 4 or more spaces, which can line text up to look like something else.',
  trailing: 'Copy only: its folder ends in a space, which the screen cannot show.',
  label: 'Copy only: its folder holds a label the card draws, such as `argv[` or `out:`.',
}

const NO_PART =
  'Copy only: the refusal does not quote one whole part of this line, so Copy takes the whole line and Run is not offered.'

// The text Run would execute: a refusal's blocked part alone, a signal's
// command. Undefined when there is none.
function runText(entry: InboxEntry): string | undefined {
  if (entry.kind === 'refused') return blockedPart(entry.command, entry.detail, entry.shell)
  if (entry.kind === 'signal') return entry.command
  return undefined
}

// Why Run is not offered for this entry, or undefined when it is. Render, the
// arming press and the claim all ask this one function, so they always agree,
// and it judges the text Run would actually execute.
function runBlock(entry: InboxEntry): string | undefined {
  if (entry.kind === 'question' || entry.command === undefined) return 'Copy only: no command is stored.'
  const text = runText(entry)
  if (text === undefined) return NO_PART
  if (entry.isRunnable !== true) return entry.copyOnly ?? 'Copy only: its folder is not known.'
  if (!isAbsolutePath(entry.cwd)) return 'Copy only: the session folder is not known as a full path.'
  const problem = showProblem(text, MAX_RUN_LINES)
  if (problem !== undefined) return COMMAND_PROBLEM[problem]
  const folderProblem = showProblem(entry.cwd, 1)
  if (folderProblem !== undefined) return FOLDER_PROBLEM[folderProblem]
  const filed = [entry.title, entry.why, entry.recommendedAction, entry.confidence, entry.reviewOutcome]
  if (entry.kind === 'signal' && filed.some(one => one !== undefined && (LABEL_LIKE.test(one) || /run now/i.test(one)))) {
    return 'Copy only: its filed text holds a label the confirm view draws, such as `argv[` or `Run now`.'
  }
  if (entry.kind === 'refused' && changesContext(entry.command, text, entry.shell)) {
    return 'Copy only: an earlier part of the line changes the folder or the environment, so this part alone could act somewhere else.'
  }
  return undefined
}

// One source line as screen rows of at most RUN_CHUNK characters. A row never
// ends in a space: the space moves to the next row, after its fixed prefix,
// where the owner can see it.
function chunks(line: string): string[] {
  const rows: string[] = []
  let start = 0
  while (start < line.length) {
    let end = Math.min(start + RUN_CHUNK, line.length)
    while (end < line.length && end > start + 1 && line[end - 1] === ' ') end--
    rows.push(line.slice(start, end))
    start = end
  }
  return rows.length === 0 ? [''] : rows
}

// The rows of one labelled value. The first row carries the label; a row cut
// from the same line starts `  + `, and a new line starts `  line N: `. A
// pipe would read as a shell pipe, so no mark uses one.
function labelledRows(head: string, text: string): string[] {
  return text.split('\n').flatMap((line, lineIndex) =>
    chunks(line).map((row, rowIndex) =>
      rowIndex > 0 ? `  + ${row}` : lineIndex > 0 ? `  line ${lineIndex + 1}: ${row}` : `${head}${row}`,
    ),
  )
}

function argvRows(argv: readonly string[]): string[] {
  return argv.flatMap((part, index) => labelledRows(`argv[${index}]: `, index === 0 ? binaryText(part) : part))
}

// Bumped by every Run and Cancel press and by every claim, so an arming press
// that finishes after any of them writes nothing.
const armSeq = new Map<string, number>()

function sameArgv(a: readonly string[] | undefined, b: readonly string[]): boolean {
  return a !== undefined && a.length === b.length && a.every((part, index) => part === b[index])
}

async function shellArgv($: Engine, shell: InboxEntry['shell'], command: string): Promise<string[]> {
  if (shell === 'PowerShell') {
    // By path where the installer puts it, so a pwsh.exe sitting in the
    // refused call's folder is not the one a cwd-first lookup finds.
    // On Windows never by bare name: that lookup can try the run folder
    // first, and a signal's folder is the model's choice. Where no known
    // path exists, Run fails and says so; Copy still works.
    // Program Files only: the user can write under LOCALAPPDATA, so a path
    // there could be a planted binary that looks legitimate on the confirm view.
    const programFiles = await $.env.get('ProgramFiles')
    const isWindows = programFiles !== undefined || (await folder($))?.sep === '\\'
    if (!isWindows) return ['pwsh', '-NoProfile', '-Command', command]
    const places = [programFiles !== undefined ? `${programFiles}\\PowerShell\\7\\pwsh.exe` : undefined]
    for (const place of places) {
      if (place !== undefined && (await $.fs.exists(place).catch(() => false))) return [place, '-NoProfile', '-Command', command]
    }
    throw new Error('PowerShell 7 (pwsh.exe) not found by path; Copy the command instead')
  }
  // Bash runs by path, never as a bare `bash`: on Windows that name can
  // resolve to WSL's System32\bash.exe, not the Git Bash the Bash tool runs.
  // Where no known path exists, Run fails and says so; Copy still works.
  const programFiles = await $.env.get('ProgramFiles')
  const isWindows = programFiles !== undefined || (await folder($))?.sep === '\\'
  const places = isWindows
    ? [GIT_BASH, programFiles !== undefined ? `${programFiles}\\Git\\bin\\bash.exe` : undefined]
    : ['/bin/bash', '/usr/bin/bash']
  for (const place of places) {
    if (place !== undefined && (await $.fs.exists(place).catch(() => false))) return [place, '-c', command]
  }
  throw new Error(isWindows ? 'Git Bash not found; Copy the command instead' : 'bash not found; Copy the command instead')
}

async function runOwn($: Engine, id: string): Promise<void> {
  // The text comes from $.state at the moment of the press, never from the
  // drawing or from disk, and only while the owner's arming press is fresh.
  // The check and the claim are one write, so two quick presses run it once.
  const startedAt = await $.clock.now()
  let claimed: InboxEntry | undefined
  let isIgnored = false
  await update($, own, list => {
    claimed = undefined
    isIgnored = false
    return list.map(one => {
      // The gap runs from the last press, Run or an ignored Run now; the
      // minute's lapse runs from the Run press alone.
      const isArmed = one.armedAt !== undefined && startedAt - one.armedAt < ARM_MS
      const lastPress = Math.max(one.armedAt ?? 0, one.quietFrom ?? 0)
      const isFresh = isArmed && startedAt - lastPress >= ARM_GAP_MS
      const isRunnable = one.id === id && runBlock(one) === undefined && one.run?.status !== 'running' && !isDone(one)
      if (!isRunnable || !isArmed) return one
      // A confirm inside the gap is ignored, not spent, and it starts the gap
      // again: a held Enter or a run of clicks never reaches the command.
      if (!isFresh) {
        isIgnored = true
        return { ...one, quietFrom: startedAt }
      }
      claimed = one
      const run: InboxRun = { status: 'running', startedAt, argv: one.armedArgv }
      return { ...one, armedAt: undefined, quietFrom: undefined, armedArgv: undefined, armedError: undefined, run }
    })
  })
  if (isIgnored) {
    $.ui.toast(`Run now ignored: wait ${ARM_GAP_MS} ms after the last press, then press it once.`)
    return
  }
  const entry: InboxEntry | undefined = claimed
  if (entry === undefined) return
  armSeq.set(id, (armSeq.get(id) ?? 0) + 1)
  const shown = entry.armedArgv
  let result: InboxRun
  try {
    // The claim checked all of these. They are checked again here so that a
    // miss records a failure rather than leaving the entry stuck running.
    const text = runText(entry)
    if (text === undefined || !isAbsolutePath(entry.cwd)) throw new Error('not runnable; press Run again')
    if (shown === undefined) throw new Error(entry.armedError ?? 'no command line was shown; press Run again')
    // Resolved again at the press, and run only if it matches what the confirm
    // view showed: a pwsh.exe removed in between must not quietly become PATH.
    const argv = await shellArgv($, entry.shell, text)
    if (!sameArgv(shown, argv)) throw new Error('the shell resolved differently since Run was pressed; press Run again')
    const ran = await $.process.run(argv, { cwd: entry.cwd, timeoutMs: RUN_TIMEOUT_MS })
    const output = [ran.stdout, ran.stderr].filter(part => part.trim() !== '').join('\n')
    result = {
      status: 'done',
      startedAt,
      finishedAt: await $.clock.now(),
      exitCode: ran.exitCode,
      argv,
      tail: lastLines(output, TAIL_LINES),
    }
  } catch (error: unknown) {
    // Nothing in here may throw, or the entry would stay running.
    result = {
      status: 'failed',
      startedAt,
      finishedAt: await $.clock.now().catch(() => startedAt),
      argv: shown,
      tail: clean(errorText(error), 300),
    }
  }
  await update($, own, list => list.map(one => (one.id === id ? { ...one, run: result } : one)))
  void publish($)
}

// The arming press resolves the binary, so the confirm view shows the exact
// argv before the second press. A shell that cannot be found arms with the
// reason instead, and Run now then records that failure and runs nothing.
async function arm($: Engine, id: string, isArmed: boolean): Promise<void> {
  const seq = (armSeq.get(id) ?? 0) + 1
  armSeq.set(id, seq)
  let armedArgv: string[] | undefined
  let armedError: string | undefined
  let runBefore: number | undefined
  if (isArmed) {
    const entry = (await read($, own)).find(one => one.id === id)
    const text = entry === undefined ? undefined : runText(entry)
    if (entry === undefined || text === undefined || runBlock(entry) !== undefined || entry.run?.status === 'running') return
    runBefore = entry.run?.startedAt
    try {
      const argv = await shellArgv($, entry.shell, text)
      for (const part of argv) {
        const problem = showProblem(part, MAX_RUN_LINES)
        if (problem !== undefined) {
          throw new Error(`the shell path cannot be shown exactly (${problem}); Copy the command instead`)
        }
      }
      armedArgv = argv
    } catch (error: unknown) {
      armedError = clean(errorText(error), 300)
    }
  }
  // Stamped after the binary is resolved, which is when Run now first shows.
  const now = await $.clock.now()
  await update($, own, list =>
    list.map(one => {
      if (one.id !== id) return one
      // A later Run or Cancel press, or a run that started meanwhile, wins.
      const isStale = armSeq.get(id) !== seq || (isArmed && one.run?.startedAt !== runBefore)
      if (isStale) return one
      return { ...one, armedAt: isArmed ? now : undefined, quietFrom: undefined, armedArgv, armedError }
    }),
  )
  // Redraw once the arming lapses, so a stale Run now is not left on screen.
  if (isArmed) $.clock.after(ARM_MS + 50, () => $.ui.invalidate('ui.render'))
}

async function dismissRemote($: Engine, key: string): Promise<void> {
  const now = await $.clock.now()
  await update($, dismissed, list =>
    [...list.filter((one: InboxDismissal) => one.key !== key && now - one.at < DAY_MS), { key, at: now }].slice(
      -MAX_DISMISSED,
    ),
  )
  await update($, remote, list => list.filter(one => one.key !== key))
  void publish($)
}

async function toggle($: Engine, key: string): Promise<void> {
  await update($, expanded, list => (list.includes(key) ? list.filter(one => one !== key) : [...list, key].slice(-200)))
}

// ---------------------------------------------------------- the owner signal

const ACTION_DESCRIPTION = [
  "File one item in the owner's inbox. Use it ONLY for something that truly needs the owner: a decision, an authority, or an act a gate reserves for the person. Never for a status update, a progress note, or anything you can route around yourself.",
  'Before you file, climb this ladder. 1. If you have a strong recommendation, act on it and do not file. 2. If you do not, put the choice through adversarial review and follow a clear recommendation from it. 3. File only when review cannot decide.',
  'File only for something only the owner has: their preference, their authority, private context only they hold, or a cost only they can accept. "Is this consequential?" is the wrong test. Say in reviewOutcome why review could not decide (or "not applicable: <reason>", for example "a gate reserves this act to the person"), and give your confidence and what reading would change your mind.',
  `The call returns at once with an entry id and does not wait for the owner, so keep working on anything else. If the matter resolves without the owner, call ${DONE_TOOL} with that id.`,
].join('\n\n')

const ACTION_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    title: { type: 'string', description: 'One line, in plain words: what needs the owner.' },
    why: { type: 'string', description: 'One or two sentences: why it needs the owner.' },
    recommendedAction: { type: 'string', description: 'What the owner should do, as one step.' },
    needsOwnerBecause: {
      type: 'string',
      enum: [...NEEDS],
      description: 'What only the owner has here: preference, authority, private-context, or cost.',
    },
    reviewOutcome: {
      type: 'string',
      description: 'Why adversarial review could not decide, or "not applicable: <reason>".',
    },
    confidence: {
      type: 'string',
      description: 'Your confidence in the recommended action, short, and what reading would change your mind.',
    },
    command: { type: 'string', description: 'Optional: the exact PowerShell command for the owner to run. Run is offered only for a short, plain one.' },
    cwd: { type: 'string', description: 'Optional: the absolute folder the command runs in.' },
  },
  required: ['title', 'why', 'recommendedAction', 'needsOwnerBecause', 'reviewOutcome', 'confidence'],
} as const

const DONE_DESCRIPTION = `Resolve an item this session filed with ${ACTION_TOOL}, once the matter settled without the owner. It moves to the inbox's Done section and stops counting.`

const DONE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    id: { type: 'string', description: `The entry id ${ACTION_TOOL} returned.` },
    note: { type: 'string', description: 'Optional: one line on how it resolved.' },
  },
  required: ['id'],
} as const

const NEEDS_RULE =
  'Not filed: needsOwnerBecause must be one of preference, authority, private-context or cost. The inbox takes only what only the owner has. If you have a strong recommendation, act on it; if not, put it through adversarial review and follow a clear answer from it.'

type Filed = { entry?: InboxEntry; refusal?: string }

// Every field is untrusted text, held to the same strip and length limits as
// a disk entry.
async function fileSignal($: Engine, input: Record<string, unknown>, agentId: string | undefined): Promise<Filed> {
  const needs = asNeed(input.needsOwnerBecause)
  if (needs === undefined) return { refusal: NEEDS_RULE }
  const reviewText = prose(input.reviewOutcome, 300)
  const reviewOutcome = reviewText === undefined ? undefined : flat(reviewText)
  if (reviewOutcome === undefined || reviewOutcome === '') {
    return {
      refusal:
        'Not filed: reviewOutcome is empty. Say why adversarial review could not decide, or "not applicable: <reason>" when review does not apply, for example when a gate reserves the act to the person.',
    }
  }
  // One line each, so filed prose cannot draw rows of its own on the card.
  const line = (value: unknown, max: number): string | undefined => {
    const text = prose(value, max)
    return text === undefined ? undefined : flat(text) || undefined
  }
  const title = line(input.title, 200)
  const why = line(input.why, 600)
  const recommendedAction = line(input.recommendedAction, 400)
  const confidence = line(input.confidence, 120)
  if (title === undefined || why === undefined || recommendedAction === undefined || confidence === undefined) {
    return { refusal: 'Not filed: title, why, recommendedAction and confidence are all required, as non-empty text.' }
  }
  const rawCommand = typeof input.command === 'string' && input.command.trim() !== '' ? input.command : undefined
  const sessionCwd = await $.session.cwd().catch(() => '')
  const givenCwd = typeof input.cwd === 'string' && input.cwd !== '' ? input.cwd : undefined
  const cwd = givenCwd ?? sessionCwd
  const isMainLoop = agentId === undefined
  const isFullPath = isAbsolutePath(cwd, await onWindows($).catch(() => true))
  const copyOnly =
    rawCommand === undefined
      ? undefined
      : !isMainLoop
        ? 'Copy only: a subagent filed it, and its folder is not known.'
        : !isFullPath
          ? 'Copy only: its folder is not known as a full path.'
          : clean(cwd, 500) !== cwd
            ? 'Copy only: its folder holds characters the screen cannot show.'
            : undefined
  const entry: InboxEntry = {
    id: crypto.randomUUID(),
    kind: 'signal',
    createdAt: await $.clock.now(),
    agentId,
    ...(rawCommand === undefined ? {} : captureCommand(rawCommand)),
    shell: rawCommand === undefined ? undefined : 'PowerShell',
    cwd: clean(cwd, 500),
    title,
    why,
    recommendedAction,
    needs,
    reviewOutcome,
    confidence,
    isRunnable: rawCommand !== undefined && copyOnly === undefined,
    copyOnly,
  }
  await addOwn($, entry)
  return { entry }
}

// ------------------------------------------------------------- what to show

type Needs = { needs: InboxNeed; review: string; confidence: string }

const GATE_NEEDS: Needs = {
  needs: 'authority',
  review: 'not applicable: the gate reserves this to the person',
  confidence: 'high',
}

// The same, for a refusal read from the call's result text rather than from
// the PreToolUse decision itself: its words say a gate reserved the act, and
// nothing here can prove a gate printed them.
const OUTPUT_NEEDS: Needs = {
  needs: 'authority',
  review: 'not applicable: the refusal says the act is the person\'s; read from the call result, so the gate is not verified',
  confidence: 'medium (gate not verified)',
}

// A question is the ladder's last step: the session asked. It needs the
// owner's preference unless its words say it needs something else.
function questionNeeds(questions: readonly InboxQuestion[]): Needs {
  const text = questions.map(q => `${q.header} ${q.question}`).join(' ')
  const needs: InboxNeed = /\b(cost|spend|pay|budget|bill)/i.test(text)
    ? 'cost'
    : /\b(approve|approval|authori[sz]e|permission|sign[- ]off|allowed to)\b/i.test(text)
      ? 'authority'
      : /\b(private|only you know|you know whether)\b/i.test(text)
        ? 'private-context'
        : 'preference'
  return { needs, review: 'asked in session', confidence: 'not stated' }
}

type Card = {
  kind: InboxEntry['kind']
  questions: readonly InboxQuestion[]
  shell?: string
  command?: string
  withheld?: string
  detail?: string
  refusal?: string
  ask?: string
  title?: string
  why?: string
  recommendedAction?: string
  needs?: InboxNeed
  reviewOutcome?: string
  confidence?: string
  viaOutput?: boolean
}

function needsOf(card: Card): Needs {
  if (card.kind === 'refused') return card.viaOutput === true ? OUTPUT_NEEDS : GATE_NEEDS
  if (card.kind === 'question') return questionNeeds(card.questions)
  return {
    needs: card.needs ?? 'preference',
    review: card.reviewOutcome ?? 'not stated',
    confidence: card.confidence ?? 'not stated',
  }
}

// Cut well under the engine's bound on one Text, which refuses the whole pane.
function questionText(questions: readonly InboxQuestion[]): string {
  return cut(questionLines(questions), 6000)
}

function questionLines(questions: readonly InboxQuestion[]): string {
  return questions
    .map(q => {
      const options = q.options.map(o => `  - ${o.label}${o.description !== '' ? `: ${o.description}` : ''}`)
      return [`${q.header !== '' ? `[${q.header}] ` : ''}${q.question}`, ...options].join('\n')
    })
    .join('\n')
}

// The headline of a refused or signal card, as one line.
function headOf(card: Card): string {
  if (card.kind === 'signal') return card.title ?? '(no title)'
  if (card.kind === 'question') {
    const q = card.questions[0]
    return `Question: ${cut(flat(q?.header !== undefined && q.header !== '' ? q.header : (q?.question ?? '')), HEAD_CUT)}`
  }
  const part = blockedPart(card.command, card.detail, card.shell)
  if (part !== undefined) return `Blocked: ${cut(flat(part), 120)}`
  if (card.command === undefined) return `Blocked: (${card.withheld ?? 'command not stored'})`
  return `Blocked: ${cut(clean(card.command, MAX_COMMAND).split(/\r?\n/).find(line => line.trim() !== '')?.trim() ?? '', HEAD_CUT)}`
}

// The one step the owner should take, never blank.
function doThisOf(card: Card, where: string): string {
  if (card.kind === 'signal') return card.recommendedAction ?? NO_ACTION
  if (card.kind === 'question') {
    for (const q of card.questions) {
      const best = q.options.find(o => /\(recommended\)/i.test(o.label))
      if (best !== undefined) {
        return `Pick "${flat(best.label.replace(/\(recommended\)/i, ''))}" (recommended), in ${where}; the question waits there.`
      }
    }
    return `Answer in ${where}; the question waits there.`
  }
  const found = handover(card.detail) ?? handover(card.ask)
  if (found === undefined) return NO_ACTION
  const part = blockedPart(card.command, card.detail, card.shell)
  const target = part ?? (card.command !== undefined ? 'the blocked command (open Details)' : 'the blocked command')
  return found.row.act(found.match, cut(flat(target), 160))
}

// What Copy puts on the clipboard: the text the card shows, cleaned like it.
function copyTextOf(card: Card): string | undefined {
  if (card.kind === 'question') return questionText(card.questions)
  const text = card.kind === 'refused' ? (blockedPart(card.command, card.detail, card.shell) ?? card.command) : card.command
  return text === undefined ? undefined : clean(text, MAX_COMMAND)
}

// ------------------------------------------------------------------- the mod

export const register: Register = on => {
  // tool_use_id -> what a settings PreToolUse hook refused, read on the way
  // back up through classic.PreToolUse and spent by the tool.call hook.
  const refusals = new Map<string, string>()

  on('session.start', async ($, e, next) => {
    const started = await next(e)
    // The band is the indicator now. This clears an `inbox N` an earlier
    // version left on the status line, and nothing sets it again.
    $.ui.status(undefined)
    // A question open across a reload lost the hook that would clear it, and
    // a refusal recorded before the actionable rule carries no `ask`; under
    // that rule it would never have been recorded. Both go.
    await update($, own, list => list.filter(one => one.kind !== 'question' && (one.kind !== 'refused' || one.ask !== undefined)))
    // A reload drops the wait on any Run the old module started, so its
    // result can never arrive. Record that rather than leave it running.
    const reloadedAt = await $.clock.now()
    await update($, own, list =>
      list.map(one =>
        one.run?.status === 'running'
          ? {
              ...one,
              run: {
                ...one.run,
                status: 'failed' as const,
                finishedAt: reloadedAt,
                tail: 'the inbox reloaded while this ran, so its result is not known; check before running it again',
              },
            }
          : one,
      ),
    )
    await $.command.register({ name: COMMAND, description: 'Show what waits on the owner across sessions' })
    // A failed registration costs the owner signal, never the rest of the inbox.
    try {
      toolNames.action = (await $.tool.register({ name: ACTION_TOOL, description: ACTION_DESCRIPTION, inputSchema: ACTION_SCHEMA })).tool
      toolNames.done = (await $.tool.register({ name: DONE_TOOL, description: DONE_DESCRIPTION, inputSchema: DONE_SCHEMA })).tool
    } catch (error: unknown) {
      $.ui.toast(clean(`Owner inbox: the owner_action tools did not register: ${errorText(error)}`, 200))
    }
    $.clock.every(POLL_MS, () => {
      void poll($).catch(() => undefined)
    })
    $.clock.every(HEARTBEAT_MS, () => {
      void publish($, { heartbeat: true })
    })
    await publish($)
    await poll($).catch(() => undefined)
    return started
  })

  on('session.end', async ($, e, next) => {
    if (SAFE_STEM.test(e.sessionId)) await publish($, { ended: e.sessionId })
    if (e.reason === 'clear') {
      await update($, own, () => [])
      lastWritten = ''
    }
    return next(e)
  })

  on('command.run', { command: COMMAND }, async $ => {
    const count = await openInbox($)
    return { text: `Owner inbox opened: ${count} waiting.` }
  })

  // The inbox's indicator, a Button. It draws above whatever the hooks below
  // drew, so another plugin's band stays and a tall one cannot scroll the
  // Button out of view. It yields to a survey and draws nothing at 0.
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const below = await next(e)
    const { count } = await waiting($)
    if (count === 0 || e.props.hasSurvey) return below
    const { Box, Button } = $.ui.resolve(e)
    const band = (
      <Button
        key="korus-inbox:open"
        label={`inbox ${count}`}
        hotkey="i"
        onPress={() => {
          void openInbox($).catch(() => $.ui.toast('Owner inbox did not open.'))
        }}
      />
    )
    // The engine draws nothing of its own here, so an engine element means
    // no other hook drew a band.
    if (below.type === 'engine') return band
    return (
      <Box flexDirection="column">
        {band}
        {below}
      </Box>
    )
  })

  on('classic.PreToolUse', async ($, e, next) => {
    const decision = await next(e)
    if ((e.tool === 'Bash' || e.tool === 'PowerShell') && typeof decision.deny === 'string') {
      if (refusals.size >= MAX_PENDING_REFUSALS) {
        const oldest = refusals.keys().next().value
        if (oldest !== undefined) refusals.delete(oldest)
      }
      refusals.set(e.tool_use_id, decision.deny)
    }
    return decision
  })

  on('tool.call', async ($, e, next) => {
    if (e.tool === toolNames.action || e.tool === toolNames.done) {
      const input = e as unknown as Record<string, unknown>
      const agentId = typeof input.agentId === 'string' ? input.agentId : undefined
      if (e.tool === toolNames.action) {
        const filed = await fileSignal($, input, agentId)
        if (filed.entry === undefined) return { deny: filed.refusal ?? NEEDS_RULE }
        return {
          result: `Filed in the owner inbox as ${filed.entry.id}. This does not wait for the owner. If it resolves without them, call ${DONE_TOOL} with this id.`,
        }
      }
      const id = typeof input.id === 'string' ? input.id : ''
      const note = prose(input.note, 200)
      const mine = await read($, own)
      const target = mine.find(one => one.id === id && one.kind === 'signal')
      if (target === undefined) return { deny: `No ${ACTION_TOOL} entry of this session has the id ${clean(id, 100)}.` }
      const now = await $.clock.now()
      await update($, own, list =>
        list.map(one => (one.id === id ? { ...one, resolvedAt: now, resolvedBy: note ?? 'its filer said it resolved' } : one)),
      )
      void publish($)
      return { result: `Resolved ${id}; it no longer counts in the owner inbox.` }
    }

    if (e.tool === 'AskUserQuestion') {
      // Recording never stands between the model and its question: a failure
      // here is dropped and the call goes on.
      let id: string | undefined
      try {
        const entry: InboxEntry = {
          id: crypto.randomUUID(),
          kind: 'question',
          createdAt: await $.clock.now(),
          agentId: e.agentId,
          questions: parseQuestions(e.questions),
        }
        await addOwn($, entry)
        id = entry.id
      } catch {
        id = undefined
      }
      try {
        return await next(e)
      } finally {
        if (id !== undefined) await removeOwn($, id).catch(() => undefined)
      }
    }
    if (e.tool !== 'Bash' && e.tool !== 'PowerShell') return next(e)

    const shell = e.tool
    const command = e.command
    const isMainLoop = e.agentId === undefined
    const cwd = await $.session.cwd().catch(() => '')
    // Run happens in the folder the owner reads; a folder the screen would
    // show altered (cut, or with characters stripped) is Copy only.
    const isCwdShown = clean(cwd, 500) === cwd
    let denied: string | undefined
    let ran: Awaited<ReturnType<typeof next>>
    try {
      ran = await next(e)
    } finally {
      // Taken here so a call that throws leaves nothing behind in the map.
      denied = refusals.get(e.tool_use_id)
      refusals.delete(e.tool_use_id)
    }
    try {
      const isRefused = ran.isError === true && (denied !== undefined || HOOK_REFUSAL.test(ran.text ?? ''))
      if (isRefused) {
        const full = denied ?? ran.text ?? ''
        // Only a refusal that hands the act to the person is the owner's.
        // Every other one is a guard the agent routes around: not recorded.
        // Matched and sliced on the cleaned text, the one that is stored, so
        // the sentence window cannot shift by a stripped character.
        const detail = clean(full, MAX_DETAIL)
        const found = handover(detail)
        if (found !== undefined) {
          const line = firstLine(full)
          const ask = sentenceAround(detail, found.match.index, found.match[0].length)
          // So is a folder not known as a full path; unsure of the platform,
          // the Windows rule, the stricter one, applies.
          const isFullPath = isAbsolutePath(cwd, await onWindows($).catch(() => true))
          const copyOnly = !isMainLoop
            ? 'Copy only: a subagent raised it, and its folder is not known.'
            : !isFullPath
              ? 'Copy only: the session folder is not known as a full path.'
              : !isCwdShown
                ? 'Copy only: its folder holds characters the screen cannot show.'
                : undefined
          await addOwn($, {
            id: crypto.randomUUID(),
            kind: 'refused',
            createdAt: await $.clock.now(),
            agentId: e.agentId,
            shell,
            ...captureCommand(command),
            cwd: clean(cwd, 500),
            isRunnable: copyOnly === undefined,
            copyOnly,
            refusal: looksSecret(line) ? REFUSAL_SECRET : line,
            detail: looksSecret(detail) ? REFUSAL_SECRET : detail,
            ask: questionLooksSecret(ask) ? QUESTION_SECRET : ask,
            viaOutput: denied === undefined,
          })
        }
      } else if (ran.isError !== true && isMainLoop) {
        await resolveBySuccess($, command, shell, cwd)
      }
    } catch {
      // Recording is best effort; the call's own result always goes back up.
    }
    return ran
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Button, Text } = $.ui.resolve(e)
    const now = await $.clock.now()
    const mine = await read($, own)
    const theirs = await read($, remote)
    const note = await read($, folderNote)
    const opened = new Set(await read($, expanded))
    const myLabel = await label($)
    const list = waitingOf(mine, theirs)
    const done = mine.filter(isDone)

    // Rows the card draws itself, each cut at the edge and never wrapped, so
    // a row starts only where these rows say it does.
    const drawRows = (prefix: string, lines: readonly string[]) =>
      lines.map((line, index) => (
        <Text key={`${prefix}:${index}`} wrap="truncate-end">
          {line}
        </Text>
      ))

    const copyButton = (key: string, text: string | undefined) =>
      text !== undefined && text !== '' ? (
        <Button
          key={key}
          label="Copy"
          onPress={async press => {
            const copied = await $.ui.copy({ text, surface: press.surface })
            $.ui.toast(copied.isCopied ? 'Copied.' : `Not copied: ${copied.reason}`)
          }}
        />
      ) : null

    // The lines every card shares, in order: Do this, Needs you for, Why, For
    // you, From, Folder. The headline is drawn by the caller.
    const commonLines = (card: Card, from: string, where: string, folderText: string | undefined, keyBase: string) => {
      const needs = needsOf(card)
      const why = card.kind === 'signal' ? card.why : card.kind === 'refused' ? whyOf(card.detail ?? card.refusal) : undefined
      return (
        <Box key={`${keyBase}:common`} flexDirection="column">
          <Text color="cyan" wrap="wrap">{`Do this: ${doThisOf(card, where)}`}</Text>
          <Text dimColor wrap="wrap">{`Needs you for: ${needs.needs} | confidence: ${needs.confidence}`}</Text>
          {why !== undefined && why !== '' && <Text wrap="wrap">{`Why: ${why}`}</Text>}
          {card.kind === 'refused' && card.ask !== undefined && <Text wrap="wrap">{`For you: ${card.ask}`}</Text>}
          {card.kind === 'question' && <Text wrap="wrap">{questionText(card.questions)}</Text>}
          <Text dimColor wrap="wrap">{`From: ${from}`}</Text>
          {folderText !== undefined && <Text dimColor wrap="wrap">{`Folder: ${folderText}`}</Text>}
        </Box>
      )
    }

    const detailsLines = (card: Card, keyBase: string) => (
      <Box key={`${keyBase}:details`} flexDirection="column">
        {card.command !== undefined && <Text dimColor>Full command:</Text>}
        {card.command !== undefined && <Text wrap="wrap">{clean(card.command, MAX_COMMAND)}</Text>}
        {card.kind === 'refused' && <Text dimColor>Full refusal:</Text>}
        {card.kind === 'refused' && <Text wrap="wrap">{card.detail ?? card.refusal ?? ''}</Text>}
        <Text dimColor wrap="wrap">{`Review: ${needsOf(card).review}`}</Text>
      </Box>
    )

    const partNote = (card: Card, canRun: boolean) => {
      if (card.kind !== 'refused') return null
      const part = blockedPart(card.command, card.detail, card.shell)
      if (part === undefined || part === card.command) return null
      return (
        <Text dimColor wrap="wrap">
          {canRun
            ? 'Copy and Run use only the blocked part above, not the whole line.'
            : 'Copy takes only the blocked part above, not the whole line.'}
        </Text>
      )
    }

    // Every Button key names its entry, never its row: a row that moves
    // between the draw and the press cannot carry a press to another entry.
    // Own keys are minted UUIDs; remote keys are checked to a safe alphabet.
    const ownCard = (entry: InboxEntry) => {
      const card: Card = { ...entry, questions: entry.questions ?? [] }
      const where = entry.cwd !== undefined && entry.cwd !== '' ? entry.cwd : '(unknown)'
      const from = `${entry.agentId !== undefined ? 'a subagent of this session' : 'this session'}, ${age(now - entry.createdAt)} ago`
      const run = entry.run
      const isArmed = entry.armedAt !== undefined && now - entry.armedAt < ARM_MS
      const text = runText(entry)
      const textBlock = entry.kind === 'question' ? undefined : runBlock(entry)
      // A pane too narrow for a whole row would cut it short, so it offers
      // Copy only; the claim needs a drawn Run now, so it cannot run there.
      const block =
        entry.kind !== 'question' && textBlock === undefined && e.props.bodyColumns < RUN_COLUMNS
          ? `Copy only here: the pane is ${e.props.bodyColumns} columns wide, and Run needs ${RUN_COLUMNS} so that no row is cut short.`
          : textBlock
      const canRun = entry.kind !== 'question' && block === undefined && text !== undefined && run?.status !== 'running'
      const tailHead = run?.status === 'failed' ? 'error: ' : 'out: '
      const isOpen = opened.has(`details:${entry.id}`)
      return (
        <Box key={`own:${entry.id}`} flexDirection="column" marginTop={1}>
          {entry.kind === 'refused' && canRun && text !== undefined ? (
            <Box flexDirection="column">{drawRows(`head:${entry.id}`, labelledRows('Blocked: ', text))}</Box>
          ) : (
            <Text bold wrap="wrap">
              {headOf(card)}
            </Text>
          )}
          {commonLines(card, from, entry.kind === 'question' ? `${myLabel} (this session)` : 'this session', entry.kind === 'question' ? undefined : where, `own:${entry.id}`)}
          {entry.kind === 'signal' && entry.command !== undefined && canRun && (
            <Box flexDirection="column">{drawRows(`cmd:${entry.id}`, labelledRows('Command: ', entry.command))}</Box>
          )}
          {entry.kind === 'signal' && entry.command === undefined && entry.withheld !== undefined && (
            <Text dimColor wrap="wrap">{`(${entry.withheld})`}</Text>
          )}
          {partNote(card, canRun)}
          {run !== undefined && (
            <Box flexDirection="column">
              <Text wrap="wrap">
                {run.status === 'running'
                  ? 'running:'
                  : run.status === 'done'
                    ? `ran, exit ${run.exitCode ?? '?'}:`
                    : 'could not run:'}
              </Text>
              {run.argv !== undefined ? (
                <Box flexDirection="column">
                  {drawRows(`rfolder:${entry.id}`, labelledRows('folder: ', where))}
                  {drawRows(`rargv:${entry.id}`, argvRows(run.argv))}
                </Box>
              ) : (
                <Text dimColor>argv: none, nothing ran</Text>
              )}
              {/* The command writes its own output, so every line of it is
                  marked and cut, and none can draw a row of the views. */}
              {run.tail !== undefined && run.tail !== '' && (
                <Box flexDirection="column">
                  {run.tail.split('\n').map((line, index) => (
                    <Text key={`tail:${entry.id}:${index}`} dimColor wrap="truncate-end">
                      {`${tailHead}${line}`}
                    </Text>
                  ))}
                </Box>
              )}
            </Box>
          )}
          {isArmed && canRun && (
            <Box flexDirection="column">
              <Text color="yellow" wrap="wrap">
                {entry.armedArgv !== undefined
                  ? 'Run now runs this:'
                  : `Run now runs nothing: ${entry.armedError ?? 'no shell was found'}`}
              </Text>
              {entry.armedArgv !== undefined && (
                <Box flexDirection="column">
                  {drawRows(`folder:${entry.id}`, labelledRows('folder: ', where))}
                  {drawRows(`argv:${entry.id}`, argvRows(entry.armedArgv))}
                </Box>
              )}
              <Text dimColor wrap="wrap">
                {`Run now ignores a press within ${ARM_GAP_MS} ms of the last press, so one double press cannot run it.`}
              </Text>
            </Box>
          )}
          {entry.kind !== 'question' && entry.command !== undefined && block !== undefined && run?.status !== 'running' && (
            <Text dimColor wrap="wrap">{block}</Text>
          )}
          <Box>
            {canRun && !isArmed && <Button key={`run:${entry.id}`} label="Run" onPress={() => arm($, entry.id, true)} />}
            {canRun && isArmed && (
              <Button
                key={`confirm:${entry.id}`}
                label="Run now"
                variant="primary"
                onPress={() => {
                  void runOwn($, entry.id).catch(() => undefined)
                }}
              />
            )}
            {canRun && isArmed && (
              <Button key={`cancel:${entry.id}`} label="Cancel" onPress={() => arm($, entry.id, false)} />
            )}
            {copyButton(`copy:${entry.id}`, copyTextOf(card))}
            {entry.kind !== 'question' && (
              <Button
                key={`details:${entry.id}`}
                label={isOpen ? 'Hide details' : 'Details'}
                onPress={() => toggle($, `details:${entry.id}`)}
              />
            )}
            {run?.status !== 'running' && (
              <Button key={`dismiss:${entry.id}`} label="Dismiss" onPress={() => removeOwn($, entry.id)} />
            )}
          </Box>
          {isOpen && entry.kind !== 'question' && detailsLines(card, `own:${entry.id}`)}
        </Box>
      )
    }

    // A card read from disk: shown and copied, nothing else. No Run, ever.
    const remoteCard = (entry: InboxRemoteEntry) => {
      const card: Card = entry
      const from = `another session (${entry.sessionLabel}), ${age(now - entry.createdAt)} ago`
      const isOpen = opened.has(`rdetails:${entry.key}`)
      return (
        <Box key={`remote:${entry.key}`} flexDirection="column" marginTop={1}>
          <Text bold wrap="wrap">
            {headOf(card)}
          </Text>
          {commonLines(
            card,
            from,
            `another session (${entry.sessionLabel})`,
            entry.kind === 'question' ? undefined : entry.cwd !== undefined && entry.cwd !== '' ? entry.cwd : '(unknown)',
            `remote:${entry.key}`,
          )}
          {entry.kind !== 'question' && entry.command !== undefined && (
            <Text dimColor wrap="wrap">
              Copy only: it came from another session.
            </Text>
          )}
          {partNote(card, false)}
          <Box>
            {copyButton(`rcopy:${entry.key}`, copyTextOf(card))}
            {entry.kind !== 'question' && (
              <Button
                key={`rdetails:${entry.key}`}
                label={isOpen ? 'Hide details' : 'Details'}
                onPress={() => toggle($, `rdetails:${entry.key}`)}
              />
            )}
            <Button key={`rdismiss:${entry.key}`} label="Dismiss" onPress={() => dismissRemote($, entry.key)} />
          </Box>
          {isOpen && entry.kind !== 'question' && detailsLines(card, `remote:${entry.key}`)}
        </Box>
      )
    }

    const doneCard = (entry: InboxEntry) => {
      const card: Card = { ...entry, questions: entry.questions ?? [] }
      const how =
        entry.resolvedAt !== undefined
          ? `Resolved ${age(now - entry.resolvedAt)} ago: ${entry.resolvedBy ?? 'resolved'}.`
          : `Ran, exit 0, ${age(now - (entry.run?.finishedAt ?? entry.createdAt))} ago.`
      return (
        <Box key={`done:${entry.id}`} flexDirection="column" marginTop={1}>
          <Text dimColor wrap="wrap">{`Done: ${headOf(card).replace(/^Blocked: /, '')}`}</Text>
          <Text dimColor wrap="wrap">
            {how}
          </Text>
          <Box>
            <Button key={`dismiss:${entry.id}`} label="Dismiss" onPress={() => removeOwn($, entry.id)} />
          </Box>
        </Box>
      )
    }

    const rows = [
      ...list.own.map(entry => ({ createdAt: entry.createdAt, draw: () => ownCard(entry) })),
      ...list.remote.map(entry => ({ createdAt: entry.createdAt, draw: () => remoteCard(entry) })),
    ].sort((a, b) => b.createdAt - a.createdAt)
    const isDoneOpen = opened.has('done')

    return (
      <Box flexDirection="column">
        <Text bold>{`${list.count} waiting on the owner`}</Text>
        {note !== null && <Text color="yellow">{note}</Text>}
        {rows.length === 0 && <Text dimColor>Nothing waits on the owner.</Text>}
        {rows.map(row => row.draw())}
        {done.length > 0 && (
          <Box flexDirection="column" marginTop={1}>
            <Button
              key="done:toggle"
              label={isDoneOpen ? `Hide done (${done.length})` : `Done (${done.length})`}
              onPress={() => toggle($, 'done')}
            />
            {isDoneOpen && done.map(entry => doneCard(entry))}
          </Box>
        )}
      </Box>
    )
  })
}
