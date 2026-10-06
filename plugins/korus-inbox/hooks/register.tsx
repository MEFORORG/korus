import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type {
  InboxDismissal,
  InboxEntry,
  InboxNeed,
  InboxOption,
  InboxPlace,
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
// and copied, never run. A remote card's Go to session press runs two
// things: a fixed Windows PowerShell query of the process list (no card value
// reaches it), and, when that shows the instance running, the app's launcher
// with a link, at a folder rebuilt from this machine's own environment. Run
// exists only for this session's own entries, read
// from $.state at the moment the owner presses it. Only the newest remote
// entries are held and drawn; the count still takes in every one.

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
// The desktop app's tool that renames a session; `session_id: 'self'` is this one.
const RENAME_TOOL = 'mcp__ccd_session_mgmt__set_session_title'
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
// The engine refuses a whole Pane over 100000 characters of text, and a
// remote $.state update fails at about 4 MB. A remote card runs about 670
// characters (150 of them blanked the pane), so 40 come to about 27000 and
// leave over 70000 for this session's 50 own cards. The state holds the same
// 40: at most about 20 KB each in JSON, so under 1 MB at worst.
const MAX_REMOTE_SHOWN = 40
// A card can run far past 670: a question to 6000 characters, and Details
// open adds the command and refusal. So the remote cards also stop at this
// much text, counted generously, whatever their number.
const REMOTE_TEXT_BUDGET = 50_000
const RUN_TIMEOUT_MS = 5 * 60 * 1000
const TAIL_LINES = 15
const HEAD_CUT = 80
const BASH_ON_WINDOWS =
  'Copy only: on Windows, Run is offered only for PowerShell. Git Bash can expand a Bash command differently from what the card shows.'

const own = atom({ plugin: 'korus-inbox', key: 'own' } as const, [])
// The newest remote entries and the count of all of them, in one atom, so
// one write moves both and no render pairs a new list with an old total.
const remote = atom({ plugin: 'korus-inbox', key: 'remoteHeld' } as const, { entries: [], total: 0 })
const dismissed = atom({ plugin: 'korus-inbox', key: 'dismissed' } as const, [])
const folderNote = atom({ plugin: 'korus-inbox', key: 'folderNote' } as const, null)
const expanded = atom({ plugin: 'korus-inbox', key: 'expanded' } as const, [])
const title = atom({ plugin: 'korus-inbox', key: 'title' } as const, null)

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
  act: (match: RegExpExecArray, target: Target) => string
}

// What the step names: the blocked part, when it is first on its line, or else
// the whole command. A part that is not first is never offered alone, because
// alone it could run in a different context from the line it came from.
type Target = { part: string } | { whole: string }

const WHOLE = 'run the whole command in a plain terminal: '

function step(target: Target, partLead: string, wholeLead: string): string {
  return 'part' in target ? `${partLead}${target.part}` : `${wholeLead}${target.whole}`
}

const ACTION_ROWS: readonly ActionRow[] = [
  {
    name: 'I need you to confirm',
    phrase: /\bI\s+need\s+you\s+to\s+confirm\b([^."\n]*)/i,
    act: (match, target) =>
      `Confirm${match[1] !== undefined && match[1].trim() !== '' ? ` ${flat(match[1])}` : ' it is safe'}, then ${step(target, 'run: ', WHOLE)}`,
  },
  {
    name: 'from a PLAIN terminal',
    phrase: /\bplain\s+terminal\b/i,
    act: (match, target) => step(target, 'Run this in a plain terminal: ', 'Run the whole command in a plain terminal: '),
  },
  {
    name: 'governs agents, not you',
    phrase: /\bgoverns\s+agents,?\s+not\s+you\b/i,
    act: (match, target) => step(target, 'Run this in a plain terminal: ', 'Run the whole command in a plain terminal: '),
  },
  {
    name: "the user's call",
    phrase: /\buser['\u2019]?s\s+call\b/i,
    act: (match, target) => `Decide; if you agree, ${step(target, 'run it yourself: ', WHOLE)}`,
  },
  {
    name: 'a human act',
    phrase: /\bhuman\s+act\b/i,
    act: (match, target) => step(target, 'Do it yourself, from a plain terminal: ', `Do it yourself: ${WHOLE}`),
  },
  {
    name: 'only the owner',
    phrase: /\bonly\s+the\s+owner\b/i,
    act: (match, target) => `Only you can do this; if you agree, ${step(target, 'run it yourself: ', WHOLE)}`,
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

// A withheld ask keeps the row that let it in: the placeholder names the row,
// and handover() reads the same row back from it. So withholding never changes
// which step the card gives, and a reader keeps the entry by the same rule as
// any other, rather than by an exception for the placeholder.
function askWithheld(row: ActionRow): string {
  return `ask withheld: it looked like it carried a secret. The gate handed it over as: ${row.name}`
}

// The ask as stored: withheld when it looks like a secret by either check.
// The row is the one that let the entry in, so it is never lost to a cut.
function guardAsk(ask: string, row: ActionRow): string {
  return looksSecret(ask) || questionLooksSecret(ask) ? askWithheld(row) : ask
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

// What may follow the part: the line's end or a separator. A pipe after it is
// fine, since the part alone still runs as it would have.
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

// The separators a plain text uses outside its quotes. Only for text isPlain
// accepted, where every quote closes and nothing escapes one.
function separatorsOf(text: string): string[] {
  return text.replace(/'[^']*'|"[^"]*"/g, '').match(/&&|\|\||[;|\n]/g) ?? []
}

const NO_PART =
  'Copy only: the refusal does not quote one whole part of this line, so Copy takes the whole line and Run is not offered.'
const NOT_FIRST = 'Copy only: other commands come before this part, so it could run in a different context.'

// The blocked part, or why there is none to use. An allow-list, not a list of
// what to refuse: the part counts only when it is the FIRST command on the
// line, with nothing at all before it. Anything before it, even a plain `&&`
// chain, could change the folder, the environment, a variable or whether the
// part ran at all, and no list of such words has ever been complete.
type Part = { part?: string; whyNot?: string }

function partOf(command: string | undefined, refusal: string | undefined, shell: Shell): Part {
  if (command === undefined || refusal === undefined) return { whyNot: NO_PART }
  const span = QUOTED.exec(refusal)?.[1]
  if (span === undefined || span.trim() === '' || span !== span.trim()) return { whyNot: NO_PART }
  if (command.startsWith(span) && isPlain(span, shell) && AFTER_OK.test(command.slice(span.length))) return { part: span }
  return { whyNot: command.indexOf(span) > 0 ? NOT_FIRST : NO_PART }
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
// take their numbers from this, so the three never disagree. The remote list
// holds only the newest entries; its total counts every one waiting, so an
// entry not held or not drawn still counts.
function waitingOf(
  mine: readonly InboxEntry[],
  theirs: { readonly entries: readonly InboxRemoteEntry[]; readonly total: number },
): { own: InboxEntry[]; remote: InboxRemoteEntry[]; remoteCount: number; count: number } {
  const waitingOwn = mine.filter(isWaiting)
  return { own: waitingOwn, remote: [...theirs.entries], remoteCount: theirs.total, count: waitingOwn.length + theirs.total }
}

async function waiting($: Engine): Promise<ReturnType<typeof waitingOf>> {
  return waitingOf(await read($, own), await read($, remote))
}

let writeChain: Promise<void> = Promise.resolve()
let lastWritten = ''
// Sessions whose ended file is written: a late write (a question's finally,
// a heartbeat) must not bring them back with ended:false.
const endedIds = new Set<string>()

// The folder name: what a reader shows when the session has no title yet.
async function label($: Engine): Promise<string> {
  const root = await $.session.root().catch(() => '')
  const base = root.split(/[\\/]/).filter(part => part !== '').pop() ?? 'session'
  return clean(base, 60)
}

// The name the owner sees for this session in the app's session list. The
// folder name and the session id are the background names, which the owner
// cannot match to a session there, so the title wins whenever there is one.
async function shownName($: Engine): Promise<string> {
  return (await read($, title)) ?? (await label($))
}

const TITLE_MAX = 60

// A title as one plain line, or '' when there is none to show. Flattened, so a
// title cannot start a row of the card; checked for a secret before it is cut,
// so a key cannot slip under the check by being cut short; and cut once. A
// cut title is left as it is, so a reader's pass does not cut it again. Only a
// value shape counts as a secret: words such as "token" are ordinary in a
// title. The writer and every reader apply it, whoever wrote the file.
function titleOf(raw: unknown): string {
  const text = flat(clean(raw, 1000))
  if (text === '' || questionLooksSecret(text)) return ''
  return text.length > TITLE_MAX + ' [cut]'.length ? cut(text, TITLE_MAX) : text
}

// Keeps the newest title the engine handed over, and republishes when it
// changed, so other sessions' cards name this one as the app now does. A title
// that cannot be shown clears the one held: the app no longer shows that one.
// No title at all (undefined) leaves the one held.
async function noteTitle($: Engine, raw: unknown): Promise<void> {
  if (raw === undefined) return
  const shown = titleOf(raw)
  const next = shown === '' ? null : shown
  if (next === (await read($, title))) return
  await update($, title, () => next)
  void publish($)
}

// The title a classic event carries, or the one a hook beneath set in its
// result, which wins as it does in the app. The app drops a hook's title when
// the event is blocked, and ignores an empty one. A subagent's event never
// names the session.
async function titleFromEvent(
  $: Engine,
  e: { agent_id?: string; session_title?: string },
  result: { block?: string; preventContinuation?: true; sessionTitle?: string },
): Promise<void> {
  if (e.agent_id !== undefined) return
  const isBlocked = result.block !== undefined || result.preventContinuation === true
  const set = !isBlocked && typeof result.sessionTitle === 'string' && result.sessionTitle !== '' ? result.sessionTitle : e.session_title
  await noteTitle($, set).catch(() => undefined)
}

// ------------------------------------------------- where the app shows it

// Each extra instance of the desktop app runs with its own data folder,
// %USERPROFILE%\.claude-desktop-N. A launch naming a running instance's
// folder hands a claude:// link to that instance, which brings the session
// forward, and exits. The default instance (%APPDATA%\Claude) is not offered:
// a hand-off to it has not been measured.
const APP_ID = /^local_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
// The last segment of an instance folder, matched exactly: no trailing dot or
// space, which Windows would resolve to the same folder under another name.
const INSTANCE_NAME = /\\\.claude-desktop-\d{1,3}$/i
// A file whose session wrote within this long is alive. A file dated further
// ahead than this is not believed.
const FRESH_MS = HEARTBEAT_MS + 2 * 60 * 1000
const AHEAD_MS = 5 * 60 * 1000
const LAUNCH_TIMEOUT_MS = 20_000
const QUERY_TIMEOUT_MS = 15_000
// A new session's record can lag its start, so its place is looked up again
// at each poll for this many polls (about two minutes), then only at publish.
const PLACE_TRIES = 24
// The app's processes, one line each: its executable, a tab, its command line.
// A fixed script: nothing from any file reaches it.
const PROCESS_QUERY =
  "Get-CimInstance Win32_Process -Filter \"Name='claude.exe'\" | ForEach-Object { [string]$_.ExecutablePath + \"`t\" + [string]$_.CommandLine }"

// The shape a place must have to be offered at all. The folder is matched
// against this machine's own folders only when the owner presses.
function placeOf(raw: unknown): InboxPlace | undefined {
  if (typeof raw !== 'object' || raw === null) return undefined
  const { instance, id } = raw as Record<string, unknown>
  if (typeof instance !== 'string' || typeof id !== 'string') return undefined
  if (!APP_ID.test(id) || instance.length > 260 || /["\x00-\x1f]/.test(instance) || !INSTANCE_NAME.test(instance)) return undefined
  return { instance, id }
}

// A place another session wrote is offered while that session is alive.
function isPlaceFresh(at: number | undefined, now: number): boolean {
  return at !== undefined && now - at <= FRESH_MS && at - now <= AHEAD_MS
}

// Only a found place is kept. A new session starts before the app has
// written its id into the record, so a miss is looked up again.
let placeCache: { sessionId: string; place: InboxPlace } | undefined
let placeTries = 0

// This session's place in the app, from what the app put in its environment,
// and only when the app's own record of that session names this session. A
// process a session starts inherits that environment, and the record keeps it
// from claiming its parent's place. Undefined outside the desktop app.
async function myPlace($: Engine): Promise<InboxPlace | undefined> {
  const sessionId = await $.session.id()
  if (placeCache?.sessionId === sessionId) return placeCache.place
  let place: InboxPlace | undefined
  const id = await $.env.get('CLAUDE_CODE_HOST_SESSION_ID')
  const exec = await $.env.get('CLAUDE_CODE_EXECPATH')
  const account = await $.env.get('CLAUDE_CODE_ACCOUNT_UUID')
  const org = await $.env.get('CLAUDE_CODE_ORGANIZATION_UUID')
  // Matched on the path as written, so the folder keeps its own spelling.
  const instance = exec === undefined ? undefined : /^(.+)\\claude-code\\/i.exec(exec)?.[1]
  const candidate = instance === undefined ? undefined : placeOf({ instance, id })
  if (candidate !== undefined && account !== undefined && org !== undefined && UUID.test(account) && UUID.test(org)) {
    const record = `${candidate.instance}\\claude-code-sessions\\${account}\\${org}\\${candidate.id}.json`
    const text = await $.fs.read(record).catch(() => '')
    try {
      const parsed = JSON.parse(text) as { cliSessionId?: unknown }
      if (parsed.cliSessionId === sessionId) place = candidate
    } catch {
      // Not written yet, or mid-write: looked up again later.
    }
  }
  if (place !== undefined) placeCache = { sessionId, place }
  return place
}

// Looks this session's place up again while it is still missing, for a
// while after start, and publishes it the moment it is found.
async function retryPlace($: Engine): Promise<void> {
  if (placeCache !== undefined || placeTries >= PLACE_TRIES) return
  placeTries += 1
  if ((await myPlace($)) !== undefined) void publish($)
}

// The folder a place names, rebuilt from this machine's own environment, or
// undefined when it names no instance folder here. The file's spelling is
// never launched: only the folder built here is.
async function instanceFolder($: Engine, instance: string): Promise<string | undefined> {
  const home = (await $.env.get('USERPROFILE'))?.replace(/\\+$/, '')
  const numbered = /\\\.claude-desktop-(\d{1,3})$/i.exec(instance)
  if (home === undefined || home === '' || numbered === null) return undefined
  const built = `${home}\\.claude-desktop-${numbered[1]}`
  return built.toLowerCase() === instance.toLowerCase() ? built : undefined
}

const isBlank = (ch: string | undefined): boolean => ch === ' ' || ch === '\t'

// A command line split into its arguments the way CommandLineToArgvW splits
// it, which is how the app reads its own. The program name runs to the next
// quote or blank, with no escapes. After it, blanks outside quotes split;
// backslashes are literal unless a quote follows them; and a run of quotes
// inside quotes gives one literal quote for every three. Windows quotes an
// argument that holds a space, the whole argument or a part of it, so a home
// folder with a space shows up quoted either way.
function argsOf(commandLine: string): string[] {
  const n = commandLine.length
  let i = 0
  let program = ''
  if (commandLine[0] === '"') {
    for (i = 1; i < n && commandLine[i] !== '"'; i += 1) program += commandLine[i]
    i += 1
  } else {
    for (; i < n && !isBlank(commandLine[i]); i += 1) program += commandLine[i]
  }
  const args = [program]
  while (isBlank(commandLine[i])) i += 1
  let arg = ''
  let isArg = i < n
  let quotes = 0
  let slashes = 0
  while (i < n) {
    const ch = commandLine[i]
    if (isBlank(ch) && quotes === 0) {
      args.push(arg)
      arg = ''
      slashes = 0
      while (isBlank(commandLine[i])) i += 1
      isArg = i < n
      continue
    }
    i += 1
    if (ch === '\\') {
      arg += ch
      slashes += 1
      continue
    }
    if (ch !== '"') {
      arg += ch
      slashes = 0
      continue
    }
    if (slashes % 2 === 0) {
      arg = arg.slice(0, arg.length - slashes / 2)
      quotes += 1
    } else {
      arg = `${arg.slice(0, arg.length - (slashes + 1) / 2)}"`
    }
    slashes = 0
    for (; commandLine[i] === '"'; i += 1) {
      quotes += 1
      if (quotes === 3) {
        arg += '"'
        quotes = 0
      }
    }
    if (quotes === 2) quotes = 0
  }
  if (isArg) args.push(arg)
  return args
}

// A switch as the app reads one on Windows: `--`, `-` or `/` before its name,
// the name in any case, and its value after the first `=`.
function switchOf(arg: string): { name: string; value: string } | undefined {
  const prefix = /^(--|-|\/)/.exec(arg)?.[0]
  if (prefix === undefined || prefix.length === arg.length) return undefined
  const equals = arg.indexOf('=')
  return equals < 0
    ? { name: arg.slice(prefix.length).toLowerCase(), value: '' }
    : { name: arg.slice(prefix.length, equals).toLowerCase(), value: arg.slice(equals + 1) }
}

// Whether a command line is a main process of the app (no type switch) whose
// data folder is this one. Every data-folder switch must name it, since the
// app could take either of two. A line that would stop the app reading
// switches part way, with `--` or --single-argument, does not count.
function holdsFolder(commandLine: string, dataDir: string): boolean {
  if (commandLine.toLowerCase().includes('single-argument')) return false
  const args = argsOf(commandLine).slice(1)
  if (args.includes('--')) return false
  const switches = args.map(switchOf).filter(one => one !== undefined)
  if (switches.some(one => one.name === 'type')) return false
  const folders = switches.filter(one => one.name === 'user-data-dir')
  return folders.length > 0 && folders.every(one => one.value.toLowerCase() === dataDir.toLowerCase())
}

// Whether an instance of the app runs with this data folder, read from the
// process list. A file in the folder would not do: whoever can write an inbox
// file can plant one, and a launch into a folder no instance holds starts the
// app on it. Only a main process counts (no --type), from the app's install.
async function isInstanceRunning($: Engine, dataDir: string, install: string): Promise<boolean> {
  const systemRoot = (await $.env.get('SystemRoot'))?.replace(/\\+$/, '')
  if (systemRoot === undefined || systemRoot === '') return false
  const shell = `${systemRoot}\\System32\\WindowsPowerShell\\v1.0\\powershell.exe`
  const listed = await $.process.run([shell, '-NoProfile', '-NonInteractive', '-Command', PROCESS_QUERY], {
    timeoutMs: QUERY_TIMEOUT_MS,
  })
  if (listed.exitCode !== 0) return false
  const prefix = `${install}\\`.toLowerCase()
  return listed.stdout.split(/\r?\n/).some(line => {
    const tab = line.indexOf('\t')
    if (tab < 0) return false
    const exe = line.slice(0, tab).toLowerCase()
    const commandLine = line.slice(tab + 1)
    return exe.startsWith(prefix) && holdsFolder(commandLine, dataDir)
  })
}

const launching = new Set<string>()
// The keys whose Go to session was fresh at the last poll.
let lastFresh = ''

// Brings another session forward in its own, running instance of the app.
// It does not start an instance: one is launched only when the process list
// shows it running, so the launch hands the link over. An instance that exits
// between the check and the launch is the gap. No shell: each value is one
// argument. The app is the install's own launcher, which outlives app updates
// and exits as soon as it has handed the link over. It lives under
// LOCALAPPDATA, where the user can write, because the app installs there.
async function goTo($: Engine, key: string, raw: InboxPlace | undefined, at: number | undefined): Promise<void> {
  if (launching.has(key)) return
  launching.add(key)
  try {
    const place = placeOf(raw)
    if (place === undefined || !isPlaceFresh(at, await $.clock.now())) {
      $.ui.toast('Go to session: that session has gone quiet, so its app window may be closed.')
      return
    }
    const dataDir = await instanceFolder($, place.instance)
    const appData = (await $.env.get('LOCALAPPDATA'))?.replace(/\\+$/, '')
    if (dataDir === undefined || appData === undefined || appData === '') {
      $.ui.toast('Go to session: that session names no app instance on this machine.')
      return
    }
    const install = `${appData}\\AnthropicClaude`
    const app = `${install}\\claude.exe`
    if (!(await $.fs.exists(app).catch(() => false))) {
      $.ui.toast(clean(`Go to session: the app was not found at ${app}.`, 200))
      return
    }
    if (!(await isInstanceRunning($, dataDir, install))) {
      $.ui.toast('Go to session: that app instance is not running.')
      return
    }
    const ran = await $.process.run([app, `--user-data-dir=${dataDir}`, `claude://claude.ai/epitaxy/${place.id}`], {
      timeoutMs: LAUNCH_TIMEOUT_MS,
    })
    if (ran.exitCode !== 0) $.ui.toast(`Go to session: the app exited ${ran.exitCode}.`)
  } catch (error: unknown) {
    $.ui.toast(clean(`Go to session did not open it: ${errorText(error)}`, 200))
  } finally {
    launching.delete(key)
  }
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
        title: (await read($, title)) ?? undefined,
        // An ended file names no place: the id it was for is gone.
        place: options.ended !== undefined ? undefined : await myPlace($).catch(() => undefined),
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

// A signal's prose gets the full secret check, the one a command gets: a
// recommended action can carry `-p<password>` or `curl -u user:pass` as
// easily as a command can. A hit stores the placeholder for that field alone.
function signalProse(text: string | undefined): string | undefined {
  return text !== undefined && looksSecret(text) ? QUESTION_SECRET : text
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
  // The title the owner sees in the app's session list. A file with none, or
  // from a version before titles, falls back to the folder and id prefix.
  const shown = titleOf(file.title)
  // Offered only while the asking session is alive, so its instance runs.
  const place = placeOf(file.place)
  const placeAt = place === undefined ? undefined : file.updatedAt
  const sessionLabel = shown !== '' ? shown : `${flat(clean(file.label, 60)) || 'session'} ${stem.slice(0, 8)}`
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
    // The handover rule reads the ask as written, before any withholding, so
    // a secret-looking ask is held to the same rule as any other. Withheld,
    // it keeps the row that let it in.
    const askText = typeof e.ask === 'string' ? clean(e.ask, 300) || undefined : undefined
    const found = askText === undefined ? undefined : handover(askText)
    if (e.kind === 'refused' && found === undefined) return []
    const ask = askText === undefined || found === undefined ? undefined : guardAsk(askText, found.row)
    return [
      {
        key: `${stem}:${e.id}`,
        sessionLabel,
        place,
        placeAt,
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
        title: signalProse(prose(e.title, 200)),
        why: signalProse(prose(e.why, 600)),
        recommendedAction: signalProse(prose(e.recommendedAction, 400)),
        needs: asNeed(e.needs),
        reviewOutcome: signalProse(prose(e.reviewOutcome, 300)),
        confidence: signalProse(prose(e.confidence, 120)),
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
  // Only the newest are held, so the update stays far under its size limit;
  // the total keeps the rest in the count.
  const held = { entries: visible.slice(0, MAX_REMOTE_SHOWN), total: visible.length }
  const current = await read($, remote)
  if (JSON.stringify(current) !== JSON.stringify(held)) await update($, remote, () => held)
  // A Go to session button goes stale with time alone, which no state write
  // marks, so the pane is redrawn when the set of fresh ones changes.
  const fresh = held.entries.filter(entry => entry.place !== undefined && isPlaceFresh(entry.placeAt, now)).map(entry => entry.key).join(' ')
  if (fresh !== lastFresh) {
    lastFresh = fresh
    $.ui.invalidate('ui.render')
  }
  await retryPlace($).catch(() => undefined)

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

// Armed now: the Run press was less than a minute ago. A lapsed or cancelled
// arm clears armedAt, and this also reads the clock, so an arm whose clear was
// lost (a reload drops the timer) still counts as lapsed.
function isArmedAt(entry: InboxEntry, now: number): boolean {
  return entry.armedAt !== undefined && now - entry.armedAt < ARM_MS
}

async function addOwn($: Engine, entry: InboxEntry): Promise<void> {
  const now = await $.clock.now()
  // Done entries go first when the list is full, so a waiting one is kept.
  await update($, own, list => {
    const next = [...list.filter(one => one.id !== entry.id), entry]
    // An entry running, or armed and not yet lapsed, is never the one dropped,
    // so a Run's result always has its entry to land on.
    const isBusy = (one: InboxEntry): boolean => one.run?.status === 'running' || isArmedAt(one, now)
    while (next.length > MAX_ENTRIES) {
      const doneAt = next.findIndex(one => isDone(one) && !isBusy(one))
      const at = doneAt >= 0 ? doneAt : next.findIndex(one => !isBusy(one))
      if (at < 0) break
      next.splice(at, 1)
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
// owner's. Only when all of these hold: the entry's blocked part was first on
// its line; the entry and the later call both came from the main loop; the
// later call ran in the foreground and finished without error; it ran in the
// same shell and the same folder; and it STARTS with the part, followed by
// nothing or by `&&` alone, so its success is the part's own.
async function resolveBySuccess($: Engine, command: string, shell: Shell, cwd: string): Promise<void> {
  const mine = await read($, own)
  const ranFine = (part: string): boolean => {
    // A part with its own `;`, `||`, `|` or line break could fail inside and
    // still exit 0, so only a part joined by `&&` alone, or by nothing, counts.
    if (!command.startsWith(part) || !separatorsOf(part).every(one => one === '&&')) return false
    const rest = command.slice(part.length)
    if (rest.trim() === '') return true
    return /^[ \t]*&&/.test(rest) && isPlain(rest, shell) && separatorsOf(rest).every(one => one === '&&')
  }
  const matches = (one: InboxEntry): boolean => {
    if (one.kind !== 'refused' || one.agentId !== undefined || !isWaiting(one) || one.run?.status === 'running') return false
    if (one.shell !== shell || one.cwd !== clean(cwd, 500)) return false
    const part = partOf(one.command, one.detail, one.shell).part
    return part !== undefined && ranFine(part)
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
// Blocked, Why, From, Command, Do this and For you, and a Run's own result
// headers: running, ran, exit N, could not run, Done and Run now. The rest
// of what the card draws counts too: argv:, Copy only:, Needs you for:,
// confidence:, Review:, Question: and Resolved. The cut
// falls at the same place on every pane, so a command could put `argv[4]: x` at the start of a
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
const LABEL_LIKE =
  /argv\s*[[:]|(folder|out|error|bash|shell|blocked|why|from|command|do this|for you|running|could not run|done|copy only|needs you for|confidence|review|question)\s*:|line\s*\d+\s*:|ran,\s*exit|run now|resolved/i
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

// The blocked part of a refused entry, worked out once for each use.
function entryPart(entry: InboxEntry): Part | undefined {
  return entry.kind === 'refused' ? partOf(entry.command, entry.detail, entry.shell) : undefined
}

// The text Run would execute: a refusal's blocked part alone, a signal's
// command. Undefined when there is none.
function runText(entry: InboxEntry, part: Part | undefined = entryPart(entry)): string | undefined {
  if (entry.kind === 'refused') return part?.part
  if (entry.kind === 'signal') return entry.command
  return undefined
}

// Why Run is not offered for this entry, or undefined when it is. Render, the
// arming press and the claim all ask this one function, so they always agree,
// and it judges the text Run would actually execute. A caller that already
// worked out the part passes it, so a render reads each refusal once.
function runBlock(entry: InboxEntry, part: Part | undefined = entryPart(entry)): string | undefined {
  if (entry.kind === 'question' || entry.command === undefined) return 'Copy only: no command is stored.'
  const text = runText(entry, part)
  if (text === undefined) return part?.whyNot ?? NO_PART
  if (entry.isRunnable !== true) return entry.copyOnly ?? 'Copy only: its folder is not known.'
  if (!isAbsolutePath(entry.cwd)) return 'Copy only: the session folder is not known as a full path.'
  const problem = showProblem(text, MAX_RUN_LINES)
  if (problem !== undefined) return COMMAND_PROBLEM[problem]
  const folderProblem = showProblem(entry.cwd, 1)
  if (folderProblem !== undefined) return FOLDER_PROBLEM[folderProblem]
  const filed = [entry.title, entry.why, entry.recommendedAction, entry.confidence, entry.reviewOutcome]
  if (entry.kind === 'signal' && filed.some(one => one !== undefined && LABEL_LIKE.test(one))) {
    return 'Copy only: its filed text holds a label the confirm view draws, such as `argv[` or `Run now`.'
  }
  // The card draws Do this, Why and For you above the confirm view, so they
  // are held to the same rule as the text: no drawn label in any of them. Do
  // this can carry the refusal's own words, as the confirm row's capture does.
  if (entry.kind === 'refused') {
    const doThis = doThisOf({ ...entry, questions: [], part }, 'this session')
    const drawn = [doThis, whyOf(entry.detail ?? entry.refusal), entry.ask ?? '']
    if (drawn.some(one => LABEL_LIKE.test(one))) {
      return 'Copy only: its Do this, Why or For you line holds a label the confirm view draws, such as `argv[` or `Run now`.'
    }
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
    if (!(await onWindows($))) return ['pwsh', '-NoProfile', '-Command', command]
    const places = [programFiles !== undefined ? `${programFiles}\\PowerShell\\7\\pwsh.exe` : undefined]
    for (const place of places) {
      if (place !== undefined && (await $.fs.exists(place).catch(() => false))) return [place, '-NoProfile', '-Command', command]
    }
    throw new Error('PowerShell 7 (pwsh.exe) not found by path; Copy the command instead')
  }
  // Bash runs only off Windows, and by path. On Windows the entry is Copy
  // only from the moment it is recorded; this refuses again in case one
  // slipped through. Git Bash there can glob- or @file-expand an argv the
  // confirm view showed plainly, and a bare `bash` can be WSL's.
  if (await onWindows($)) throw new Error(BASH_ON_WINDOWS)
  for (const place of ['/bin/bash', '/usr/bin/bash']) {
    if (await $.fs.exists(place).catch(() => false)) return [place, '-c', command]
  }
  throw new Error('bash not found; Copy the command instead')
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
  // Once the arm lapses, clear it and redraw, so a stale Run now is not left
  // on screen and the entry no longer counts as busy when the list is full.
  // Only this arm is cleared: a later press, or a run, has moved armSeq or
  // armedAt on.
  if (isArmed) {
    $.clock.after(ARM_MS + 50, () => {
      void update($, own, list =>
        list.map(one => (one.id === id && armSeq.get(id) === seq && one.armedAt === now ? disarmed(one) : one)),
      )
        .catch(() => undefined)
        .finally(() => $.ui.invalidate('ui.render'))
    })
  }
}

// An entry with no arm left on it.
function disarmed(entry: InboxEntry): InboxEntry {
  return { ...entry, armedAt: undefined, quietFrom: undefined, armedArgv: undefined, armedError: undefined }
}

async function dismissRemote($: Engine, key: string): Promise<void> {
  const now = await $.clock.now()
  await update($, dismissed, list =>
    [...list.filter((one: InboxDismissal) => one.key !== key && now - one.at < DAY_MS), { key, at: now }].slice(
      -MAX_DISMISSED,
    ),
  )
  // The list and its total move in one write. A poll that already read this
  // Dismiss has removed the key, so nothing here counts it off twice. The
  // next poll refills the held list.
  await update($, remote, held => {
    const entries = held.entries.filter(one => one.key !== key)
    return entries.length < held.entries.length ? { entries, total: Math.max(0, held.total - 1) } : held
  })
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

type Filed = { entry?: InboxEntry; refusal?: string; withheld?: string[] }

// Every field is untrusted text, held to the same strip and length limits as
// a disk entry.
async function fileSignal($: Engine, input: Record<string, unknown>, agentId: string | undefined): Promise<Filed> {
  const needs = asNeed(input.needsOwnerBecause)
  if (needs === undefined) return { refusal: NEEDS_RULE }
  const reviewText = prose(input.reviewOutcome, 300)
  const reviewOutcome = reviewText === undefined ? undefined : signalProse(flat(reviewText))
  if (reviewOutcome === undefined || reviewOutcome === '') {
    return {
      refusal:
        'Not filed: reviewOutcome is empty. Say why adversarial review could not decide, or "not applicable: <reason>" when review does not apply, for example when a gate reserves the act to the person.',
    }
  }
  // One line each, so filed prose cannot draw rows of its own on the card.
  const line = (value: unknown, max: number): string | undefined => {
    const text = prose(value, max)
    return text === undefined ? undefined : signalProse(flat(text) || undefined)
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
  const fields = { title, why, recommendedAction, reviewOutcome, confidence }
  return { entry, withheld: Object.entries(fields).flatMap(([name, value]) => (value === QUESTION_SECRET ? [name] : [])) }
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
  /** A refusal's blocked part, worked out once when the card is built. */
  part?: Part
}

// A card with its blocked part worked out once, for the whole render.
function cardOf(entry: InboxEntry | InboxRemoteEntry): Card {
  const card: Card = { ...entry, questions: entry.questions ?? [] }
  return card.kind === 'refused' ? { ...card, part: partOf(card.command, card.detail, card.shell) } : card
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
  const part = card.part?.part
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
  // The part alone only when it is first on its line; otherwise the whole
  // command, as Copy gives it, since alone the part could act elsewhere.
  const part = card.part?.part
  const target: Target =
    part !== undefined
      ? { part: inline(part) }
      : card.command !== undefined
        ? { whole: inline(card.command) }
        : { part: 'the blocked command' }
  return found.row.act(found.match, target)
}

// A command inside the Do this sentence, shown only where it fits exactly: one
// line of 160 characters or fewer. Otherwise the step names Copy, which gives
// it exactly, rather than show a joined or cut text the owner might retype.
function inline(text: string): string {
  const shown = clean(text, MAX_COMMAND)
  return shown.includes('\n') || shown.length > 160 ? 'the command Copy gives (Details shows it whole)' : shown
}

// The card's Why line, without its label; undefined when it draws none.
function whyLineOf(card: Card): string | undefined {
  if (card.kind === 'signal') return card.why
  if (card.kind === 'refused') return whyOf(card.detail ?? card.refusal)
  return undefined
}

// The text one remote card draws with Details closed, counted generously:
// every line it draws in full, plus a fixed amount for its labels, notes and
// buttons, which come to about 360 at most.
function remoteCardChars(card: Card, from: string, where: string, folderText: string | undefined): number {
  const needs = needsOf(card)
  const lines = [
    headOf(card),
    doThisOf(card, where),
    `${needs.needs}${needs.confidence}`,
    whyLineOf(card) ?? '',
    card.kind === 'refused' ? (card.ask ?? '') : '',
    card.kind === 'question' ? questionText(card.questions) : '',
    from,
    folderText ?? '',
  ]
  return 600 + lines.reduce((sum, line) => sum + line.length, 0)
}

// What Details adds to a remote card when open: the command, the refusal and
// the review line, with their labels.
function remoteDetailsChars(card: Card): number {
  return 100 + [card.command ?? '', card.detail ?? card.refusal ?? '', needsOf(card).review].reduce((sum, line) => sum + line.length, 0)
}

// What Copy puts on the clipboard: the text the card shows, cleaned like it.
function copyTextOf(card: Card): string | undefined {
  if (card.kind === 'question') return questionText(card.questions)
  const text = card.kind === 'refused' ? (card.part?.part ?? card.command) : card.command
  return text === undefined ? undefined : clean(text, MAX_COMMAND)
}

// A call launched to run in the background has not finished, so its success
// says nothing about the part. So does a result that reads as a launch.
function isBackground(input: unknown, text: string | undefined): boolean {
  const flag = (input as { run_in_background?: unknown }).run_in_background
  return flag === true || /\bbackground\b|\blaunched\b/i.test(text ?? '')
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
    // An arm's lapse timer died with the old module too, so every arm goes:
    // the owner presses Run again.
    await update($, own, list =>
      list.map(one => (one.armedAt !== undefined ? disarmed(one) : one)).map(one =>
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
    // Whatever comes next (a clear, a resume) is another conversation, whose
    // title the engine hands over afresh; this one's must not carry into it.
    await update($, title, () => null)
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

  // The engine hands a hook the session's title only on these two events, so
  // a rename shows on other sessions' cards from the next prompt on, unless
  // the session renamed itself (the tool.call hook below catches that). A
  // hook beneath may set a new title in its result; that one wins.
  on('classic.SessionStart', async ($, e, next) => {
    const result = await next(e)
    await titleFromEvent($, e, result)
    return result
  })
  on('classic.UserPromptSubmit', async ($, e, next) => {
    const result = await next(e)
    await titleFromEvent($, e, result)
    return result
  })

  on('tool.call', async ($, e, next) => {
    if (e.tool === RENAME_TOOL) {
      const ran = await next(e)
      const input = e as unknown as Record<string, unknown>
      // Only a rename of this session, from the main loop, that went through.
      if (ran.isError !== true && e.agentId === undefined && input.session_id === 'self') {
        await noteTitle($, input.title).catch(() => undefined)
      }
      return ran
    }
    if (e.tool === toolNames.action || e.tool === toolNames.done) {
      const input = e as unknown as Record<string, unknown>
      // The tool's input and the engine's own fields share this record. Only
      // an absent agentId is the main loop: any value the input could carry,
      // null included, reads as a subagent, which is Copy only.
      const agentId = input.agentId === undefined ? undefined : typeof input.agentId === 'string' ? input.agentId : 'unknown'
      if (e.tool === toolNames.action) {
        const filed = await fileSignal($, input, agentId)
        if (filed.entry === undefined) return { deny: filed.refusal ?? NEEDS_RULE }
        const withheld =
          filed.withheld !== undefined && filed.withheld.length > 0
            ? ` These fields looked like they carried a secret and were stored as a placeholder: ${filed.withheld.join(', ')}.`
            : ''
        return {
          result: `Filed in the owner inbox as ${filed.entry.id}. This does not wait for the owner. If it resolves without them, call ${DONE_TOOL} with this id.${withheld}`,
        }
      }
      const id = typeof input.id === 'string' ? input.id : ''
      const note = prose(input.note, 200)
      const mine = await read($, own)
      const target = mine.find(one => one.id === id && one.kind === 'signal' && one.agentId === agentId)
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
          const isWindows = await onWindows($).catch(() => true)
          const isFullPath = isAbsolutePath(cwd, isWindows)
          const copyOnly = !isMainLoop
            ? 'Copy only: a subagent raised it, and its folder is not known.'
            : shell === 'Bash' && isWindows
              ? BASH_ON_WINDOWS
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
            // The ask is a sentence of the refusal, so the refusal's own secret
            // check applies to it too, before it reaches the shared file.
            // Withheld, it keeps the row that let it in.
            ask: guardAsk(ask, found.row),
            viaOutput: denied === undefined,
          })
        }
      } else if (ran.isError !== true && isMainLoop && !isBackground(e, ran.text)) {
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
    const myLabel = await shownName($)
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
      const why = whyLineOf(card)
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
      if (card.kind !== 'refused' || card.command === undefined) return null
      const part = card.part?.part
      if (part === undefined) {
        return <Text dimColor wrap="wrap">Copy takes the whole command, not the blocked part alone.</Text>
      }
      if (part === card.command) return null
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
      const card = cardOf(entry)
      const where = entry.cwd !== undefined && entry.cwd !== '' ? entry.cwd : '(unknown)'
      const from = `${entry.agentId !== undefined ? 'a subagent of this session' : 'this session'}, ${age(now - entry.createdAt)} ago`
      const run = entry.run
      const isArmed = entry.armedAt !== undefined && now - entry.armedAt < ARM_MS
      const text = runText(entry, card.part)
      const textBlock = entry.kind === 'question' ? undefined : runBlock(entry, card.part)
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

    // What a remote card shows, worked out once: drawn from, and measured
    // for the text budget.
    const remoteView = (entry: InboxRemoteEntry) => {
      const card = cardOf(entry)
      const from = `another session (${entry.sessionLabel}), ${age(now - entry.createdAt)} ago`
      const where = `another session (${entry.sessionLabel})`
      const folderText =
        entry.kind === 'question' ? undefined : entry.cwd !== undefined && entry.cwd !== '' ? entry.cwd : '(unknown)'
      const isOpen = opened.has(`rdetails:${entry.key}`)
      return { entry, card, from, where, folderText, isOpen, chars: remoteCardChars(card, from, where, folderText) }
    }

    // A card read from disk: shown and copied. No Run, ever. Its one launch is
    // Go to session, which hands a link to an instance already running.
    // Details the owner opened are drawn only when they fit the budget; the
    // card itself always stays, so its Hide details stays within reach.
    const remoteCard = (
      { entry, card, from, where, folderText, isOpen }: ReturnType<typeof remoteView>,
      isDetailsShown: boolean,
    ) => {
      return (
        <Box key={`remote:${entry.key}`} flexDirection="column" marginTop={1}>
          <Text bold wrap="wrap">
            {headOf(card)}
          </Text>
          {commonLines(card, from, where, folderText, `remote:${entry.key}`)}
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
            {entry.place !== undefined && isPlaceFresh(entry.placeAt, now) && (
              <Button
                key={`rgo:${entry.key}`}
                label="Go to session"
                onPress={() => {
                  void goTo($, entry.key, entry.place, entry.placeAt)
                }}
              />
            )}
            <Button key={`rdismiss:${entry.key}`} label="Dismiss" onPress={() => dismissRemote($, entry.key)} />
          </Box>
          {isOpen && entry.kind !== 'question' && isDetailsShown && detailsLines(card, `remote:${entry.key}`)}
          {isOpen && entry.kind !== 'question' && !isDetailsShown && (
            <Text dimColor wrap="wrap">
              Details do not fit in the pane now. Hide the details of another card, or Copy this one.
            </Text>
          )}
        </Box>
      )
    }

    const doneCard = (entry: InboxEntry) => {
      const card = cardOf(entry)
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

    // The newest remote cards, up to MAX_REMOTE_SHOWN and the text budget.
    // The first card over the budget stops the drawing, so what is drawn is
    // always the newest run, and the rest are named in one line. Whether a
    // card fits is measured with Details closed, in a first pass over every
    // card, so opening Details never hides a card. Open Details then take
    // what budget the drawn cards left, newest first.
    const fitting: ReturnType<typeof remoteView>[] = []
    let budget = REMOTE_TEXT_BUDGET
    for (const entry of list.remote.slice(0, MAX_REMOTE_SHOWN)) {
      const view = remoteView(entry)
      if (view.chars > budget) break
      budget -= view.chars
      fitting.push(view)
    }
    const shownRemote = fitting.map(view => {
      const details = view.isOpen && view.entry.kind !== 'question' ? remoteDetailsChars(view.card) : 0
      const isDetailsShown = details > 0 && details <= budget
      if (isDetailsShown) budget -= details
      return { view, isDetailsShown }
    })
    const moreRemote = list.remoteCount - shownRemote.length

    const rows = [
      ...list.own.map(entry => ({ createdAt: entry.createdAt, draw: () => ownCard(entry) })),
      ...shownRemote.map(({ view, isDetailsShown }) => ({
        createdAt: view.entry.createdAt,
        draw: () => remoteCard(view, isDetailsShown),
      })),
    ].sort((a, b) => b.createdAt - a.createdAt)
    const isDoneOpen = opened.has('done')

    return (
      <Box flexDirection="column">
        <Text bold>{`${list.count} waiting on the owner`}</Text>
        {moreRemote > 0 && (
          <Text dimColor wrap="wrap">
            {`${moreRemote} more waiting from other sessions are not shown. /inbox shows the newest ${shownRemote.length}.`}
          </Text>
        )}
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
