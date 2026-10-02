import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type {
  InboxDismissal,
  InboxEntry,
  InboxOption,
  InboxQuestion,
  InboxRemoteEntry,
  InboxRun,
} from '../types'

// What waits on the owner, gathered across sessions. Each session writes its
// own entries to one JSON file in a shared folder under the home folder, and
// every pane reads the 200 newest files of 256 KB or less. Entries read from disk are untrusted text: they
// are shown and copied, never run. Run exists only for this session's own
// refused commands, read from $.state at the moment the owner presses it.

const PANE = 'korus-inbox'
const COMMAND = 'inbox'
const FORMAT = 'korus-inbox/1'
const FOLDER = '.korus-inbox'
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
const MAX_DISMISSED = 500
const MAX_PENDING_REFUSALS = 200
const RUN_TIMEOUT_MS = 5 * 60 * 1000
const TAIL_LINES = 15
const GIT_BASH = 'C:\\Program Files\\Git\\bin\\bash.exe'

const own = atom({ plugin: 'korus-inbox', key: 'own' } as const, [])
const remote = atom({ plugin: 'korus-inbox', key: 'remote' } as const, [])
const dismissed = atom({ plugin: 'korus-inbox', key: 'dismissed' } as const, [])
const folderNote = atom({ plugin: 'korus-inbox', key: 'folderNote' } as const, null)

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

// The text a session's tool result starts with when a settings PreToolUse
// hook blocked the call (seen 2026-10-02: "PreToolUse:PowerShell hook error:
// BLOCKED: ..."). The classic.PreToolUse hook below is the primary signal;
// this is the fallback for a refusal that reached the result some other way.
const HOOK_REFUSAL = /^\s*PreToolUse:(Bash|PowerShell) hook\b/

function firstLine(text: string): string {
  const line = text.split(/\r?\n/).find(one => one.trim() !== '') ?? ''
  return clean(line.trim(), 300)
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

// A question waits until it is answered; a refused command waits until a Run
// the owner pressed has finished (a Run that could not start still waits).
function isWaiting(entry: InboxEntry): boolean {
  return (
    entry.kind === 'question' ||
    entry.run === undefined ||
    entry.run.status === 'running' ||
    entry.run.status === 'failed'
  )
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

function parseQuestions(value: unknown): InboxQuestion[] {
  if (!Array.isArray(value)) return []
  const guard = (text: string): string => (questionLooksSecret(text) ? QUESTION_SECRET : text)
  return value.slice(0, 4).flatMap((one: unknown): InboxQuestion[] => {
    if (typeof one !== 'object' || one === null) return []
    const q = one as Record<string, unknown>
    const options = Array.isArray(q.options) ? q.options : []
    return [
      {
        header: guard(clean(q.header, 60)),
        question: guard(clean(q.question, 1000)),
        options: options.slice(0, 6).flatMap((opt: unknown): InboxOption[] => {
          if (typeof opt !== 'object' || opt === null) return []
          const o = opt as Record<string, unknown>
          return [{ label: guard(clean(o.label, 100)), description: guard(clean(o.description, 300)) }]
        }),
      },
    ]
  })
}

type ParsedFile = { entries: InboxRemoteEntry[]; dismissed: string[] }

const NOTHING: ParsedFile = { entries: [], dismissed: [] }

// Everything here is untrusted: each field is checked for type, cut to a
// length, stripped of control characters, and a command that looks like a
// secret is withheld even though the writing session should have done so.
// Undefined means the text did not parse (a write in flight); a file that
// parsed but is ended, stale or of another format reads as holding nothing.
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
    if (e.kind !== 'question' && e.kind !== 'refused') return []
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
let lastStatus: string | undefined = '\u0000'

async function refreshStatus($: Engine): Promise<void> {
  const mine = (await read($, own)).filter(isWaiting).length
  const theirs = (await read($, remote)).length
  const count = mine + theirs
  const text = count === 0 ? undefined : `inbox ${count}`
  if (text !== lastStatus) {
    lastStatus = text
    $.ui.status(text)
  }
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
  const mine = await read($, own)
  if (mine.some(entry => goneKeys.has(`${me}:${entry.id}`))) {
    await update($, own, list => list.filter(entry => !goneKeys.has(`${me}:${entry.id}`)))
    void publish($)
  }
  await refreshStatus($)
}

// ----------------------------------------------------------------- recording

async function addOwn($: Engine, entry: InboxEntry): Promise<void> {
  await update($, own, list => [...list.filter(one => one.id !== entry.id), entry].slice(-MAX_ENTRIES))
  void publish($)
  await refreshStatus($)
}

async function removeOwn($: Engine, id: string): Promise<void> {
  await update($, own, list => list.filter(one => one.id !== id))
  void publish($)
  await refreshStatus($)
}

// The exact command is kept for Run; the shared file and the screen get it
// cleaned. Either spelling looking like a secret withholds it.
function captureCommand(command: string): { command?: string; withheld?: string } {
  if (looksSecret(command) || looksSecret(clean(command, MAX_COMMAND + 1))) return { withheld: WITHHELD_SECRET }
  if (command.length > MAX_COMMAND) return { withheld: WITHHELD_LONG }
  return { command }
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

// Every argv element starts a line with its index. A newline inside one
// continues on a line marked `  | `, so a command cannot draw a fake element.
function argvText(argv: readonly string[]): string {
  return argv
    .map((part, index) => `argv[${index}]: ${(index === 0 ? binaryText(part) : part).split('\n').join('\n  | ')}`)
    .join('\n')
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
    const programFiles = await $.env.get('ProgramFiles')
    const installed = programFiles !== undefined ? `${programFiles}\\PowerShell\\7\\pwsh.exe` : undefined
    const pwsh = installed !== undefined && (await $.fs.exists(installed).catch(() => false)) ? installed : 'pwsh'
    return [pwsh, '-NoProfile', '-Command', command]
  }
  // Bash runs by path, never as a bare `bash`: on Windows that name can
  // resolve to WSL's System32\bash.exe, not the Git Bash the Bash tool runs.
  // Where no known path exists, Run fails and says so; Copy still works.
  const programFiles = await $.env.get('ProgramFiles')
  const localAppData = await $.env.get('LOCALAPPDATA')
  const isWindows = programFiles !== undefined || (await folder($))?.sep === '\\'
  const places = isWindows
    ? [
        GIT_BASH,
        programFiles !== undefined ? `${programFiles}\\Git\\bin\\bash.exe` : undefined,
        localAppData !== undefined ? `${localAppData}\\Programs\\Git\\bin\\bash.exe` : undefined,
      ]
    : ['/bin/bash', '/usr/bin/bash']
  for (const place of places) {
    if (place !== undefined && (await $.fs.exists(place).catch(() => false))) return [place, '-c', command]
  }
  throw new Error(isWindows ? 'Git Bash not found; Copy the command instead' : 'bash not found; Copy the command instead')
}

async function runOwn($: Engine, id: string): Promise<void> {
  // The command comes from $.state at the moment of the press, never from the
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
      const isRunnable =
        one.id === id &&
        one.kind === 'refused' &&
        one.isRunnable === true &&
        isAbsolutePath(one.cwd) &&
        one.command !== undefined &&
        clean(one.command, MAX_COMMAND) === one.command &&
        one.run?.status !== 'running'
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
    if (entry.command === undefined || !isAbsolutePath(entry.cwd)) throw new Error('not runnable; press Run again')
    if (shown === undefined) throw new Error(entry.armedError ?? 'no command line was shown; press Run again')
    // Resolved again at the press, and run only if it matches what the confirm
    // view showed: a pwsh.exe removed in between must not quietly become PATH.
    const argv = await shellArgv($, entry.shell, entry.command)
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
  await refreshStatus($)
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
    if (entry?.command === undefined || entry.run?.status === 'running') return
    runBefore = entry.run?.startedAt
    try {
      const argv = await shellArgv($, entry.shell, entry.command)
      if (argv.some(part => clean(part, MAX_COMMAND) !== part)) {
        throw new Error('the shell path holds characters the screen cannot show; Copy the command instead')
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
  await refreshStatus($)
}

// ------------------------------------------------------------------- drawing

function questionText(questions: readonly InboxQuestion[]): string {
  return questions
    .map(q => {
      const options = q.options.map(o => `  - ${o.label}${o.description !== '' ? `: ${o.description}` : ''}`)
      return [`${q.header !== '' ? `[${q.header}] ` : ''}${q.question}`, ...options].join('\n')
    })
    .join('\n')
}

// ------------------------------------------------------------------- the mod

export const register: Register = on => {
  // tool_use_id -> what a settings PreToolUse hook refused, read on the way
  // back up through classic.PreToolUse and spent by the tool.call hook.
  const refusals = new Map<string, string>()

  on('session.start', async ($, e, next) => {
    const started = await next(e)
    await $.command.register({ name: COMMAND, description: 'Show what waits on the owner across sessions' })
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
    await poll($).catch(() => undefined)
    await $.ui.open({ id: PANE, title: 'Owner inbox' })
    const mine = (await read($, own)).filter(isWaiting).length
    const theirs = (await read($, remote)).length
    return { text: `Owner inbox opened: ${mine + theirs} waiting.` }
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
        const line = firstLine(denied ?? ran.text ?? '')
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
        })
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
    const waiting = mine.filter(isWaiting).length + theirs.length

    // Every Button key names its entry, never its row: a row that moves
    // between the draw and the press cannot carry a press to another entry.
    // Own keys are minted UUIDs; remote keys are checked to a safe alphabet.
    const ownRow = (entry: InboxEntry) => {
      const command = entry.command === undefined ? undefined : clean(entry.command, MAX_COMMAND)
      const where = entry.cwd !== undefined && entry.cwd !== '' ? entry.cwd : '(unknown)'
      const run = entry.run
      const isArmed = entry.armedAt !== undefined && now - entry.armedAt < ARM_MS
      // Run is offered only for a main-loop refusal (a subagent's folder is
      // not known), only in a folder known as a full path, and only when the
      // screen shows exactly the text that runs.
      const canRun =
        entry.kind === 'refused' &&
        entry.isRunnable === true &&
        isAbsolutePath(entry.cwd) &&
        entry.command !== undefined &&
        command === entry.command &&
        run?.status !== 'running'
      const copyText = entry.kind === 'question' ? questionText(entry.questions ?? []) : command
      return (
        <Box key={`own:${entry.id}`} flexDirection="column" marginTop={1}>
          <Text bold>{`${entry.kind === 'question' ? 'question' : 'refused'}  this session  ${age(now - entry.createdAt)} ago`}</Text>
          {entry.kind === 'question' && <Text wrap="wrap">{questionText(entry.questions ?? [])}</Text>}
          {entry.kind === 'refused' && (
            <Box flexDirection="column">
              <Text wrap="wrap">{`${entry.shell ?? 'shell'}: ${command ?? `(${entry.withheld ?? 'command not stored'})`}`}</Text>
              <Text dimColor wrap="wrap">{`cwd: ${where}`}</Text>
              <Text dimColor wrap="wrap">{`refusal: ${entry.refusal ?? ''}`}</Text>
            </Box>
          )}
          {run !== undefined && (
            <Box flexDirection="column">
              <Text wrap="wrap">
                {run.status === 'running'
                  ? `running in ${where}: ${command ?? ''}`
                  : run.status === 'done'
                    ? `ran in ${where}: ${command ?? ''}  exit ${run.exitCode ?? '?'}`
                    : `could not run in ${where}: ${command ?? ''}`}
              </Text>
              <Text dimColor wrap="wrap">
                {run.argv !== undefined ? argvText(run.argv) : 'argv: none, nothing ran'}
              </Text>
              {run.tail !== undefined && run.tail !== '' && <Text dimColor wrap="wrap">{run.tail}</Text>}
            </Box>
          )}
          {isArmed && canRun && (
            <Box flexDirection="column">
              <Text color="yellow" wrap="wrap">
                {entry.armedArgv !== undefined
                  ? `Run now runs this in ${where}:`
                  : `Run now runs nothing: ${entry.armedError ?? 'no shell was found'}`}
              </Text>
              {entry.armedArgv !== undefined && <Text wrap="wrap">{argvText(entry.armedArgv)}</Text>}
              <Text dimColor wrap="wrap">
                {`Run now ignores a press within ${ARM_GAP_MS} ms of the last press, so one double press cannot run it.`}
              </Text>
            </Box>
          )}
          {entry.kind === 'refused' && entry.command !== undefined && !canRun && run?.status !== 'running' && (
            <Text dimColor>
              {entry.isRunnable !== true
                ? (entry.copyOnly ?? 'Copy only: its folder is not known.')
                : !isAbsolutePath(entry.cwd)
                  ? 'Copy only: the session folder is not known as a full path.'
                  : 'Copy only: the command holds characters the screen cannot show.'}
            </Text>
          )}
          <Box>
            {canRun && !isArmed && (
              <Button key={`run:${entry.id}`} label="Run" onPress={() => arm($, entry.id, true)} />
            )}
            {canRun && isArmed && (
              <Button
                key={`confirm:${entry.id}`}
                label="Run now"
                variant="primary"
                onPress={() => {
                  void runOwn($, entry.id)
                }}
              />
            )}
            {canRun && isArmed && (
              <Button key={`cancel:${entry.id}`} label="Cancel" onPress={() => arm($, entry.id, false)} />
            )}
            {copyText !== undefined && copyText !== '' && (
              <Button
                key={`copy:${entry.id}`}
                label="Copy"
                onPress={async press => {
                  const copied = await $.ui.copy({ text: copyText, surface: press.surface })
                  $.ui.toast(copied.isCopied ? 'Copied.' : `Not copied: ${copied.reason}`)
                }}
              />
            )}
            {run?.status !== 'running' && (
              <Button key={`dismiss:${entry.id}`} label="Dismiss" onPress={() => removeOwn($, entry.id)} />
            )}
          </Box>
        </Box>
      )
    }

    // A row read from disk: shown and copied, nothing else. No Run, ever.
    const remoteRow = (entry: InboxRemoteEntry) => {
      const copyText = entry.kind === 'question' ? questionText(entry.questions) : entry.command
      return (
        <Box key={`remote:${entry.key}`} flexDirection="column" marginTop={1}>
          <Text bold>{`${entry.kind === 'question' ? 'question' : 'refused'}  ${entry.sessionLabel}  ${age(now - entry.createdAt)} ago`}</Text>
          {entry.kind === 'question' && <Text wrap="wrap">{questionText(entry.questions)}</Text>}
          {entry.kind === 'refused' && (
            <Box flexDirection="column">
              <Text wrap="wrap">{`${entry.shell ?? 'shell'}: ${entry.command ?? `(${entry.withheld ?? 'command not stored'})`}`}</Text>
              <Text dimColor wrap="wrap">{`cwd: ${entry.cwd !== undefined && entry.cwd !== '' ? entry.cwd : '(unknown)'}`}</Text>
              <Text dimColor wrap="wrap">{`refusal: ${entry.refusal ?? ''}`}</Text>
            </Box>
          )}
          <Box>
            {copyText !== undefined && copyText !== '' && (
              <Button
                key={`rcopy:${entry.key}`}
                label="Copy"
                onPress={async press => {
                  const copied = await $.ui.copy({ text: copyText, surface: press.surface })
                  $.ui.toast(copied.isCopied ? 'Copied.' : `Not copied: ${copied.reason}`)
                }}
              />
            )}
            <Button key={`rdismiss:${entry.key}`} label="Dismiss" onPress={() => dismissRemote($, entry.key)} />
          </Box>
        </Box>
      )
    }

    const rows = [
      ...mine.map(entry => ({ createdAt: entry.createdAt, draw: () => ownRow(entry) })),
      ...theirs.map(entry => ({ createdAt: entry.createdAt, draw: () => remoteRow(entry) })),
    ].sort((a, b) => b.createdAt - a.createdAt)

    return (
      <Box flexDirection="column">
        <Text bold>{`${waiting} waiting on the owner`}</Text>
        {note !== null && <Text color="yellow">{note}</Text>}
        {rows.length === 0 && <Text dimColor>Nothing waits on the owner.</Text>}
        {rows.map(row => row.draw())}
      </Box>
    )
  })
}
