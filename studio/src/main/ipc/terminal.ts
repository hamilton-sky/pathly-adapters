import { ipcMain, BrowserWindow, app } from 'electron'
import { getApiSecret } from '@main/apiConfig'
import { execFile } from 'child_process'
import { join } from 'path'
import * as fs from 'fs'
import * as os from 'os'
import * as path from 'path'
import { parseClaudeJsonResult, feedStreamJson, newStreamJsonState, type StreamJsonState } from './claudeJson'
import { parseCodexResult } from './codexJson'

let pty: typeof import('node-pty') | null = null
try {
  pty = require('node-pty')
} catch {
  console.warn('[terminal] node-pty not available')
}

const ALLOWED_SHELLS = new Set(['bash', 'zsh', 'sh', 'pwsh', 'powershell.exe', 'cmd.exe', 'claude', 'codex', 'agy'])

const activePtys = new Map<string, import('node-pty').IPty>()
// Maps tabId → the BrowserWindow that should receive PTY data for that tab
const ptyWindows = new Map<string, BrowserWindow>()
// Maps tabId → webContentsId of the sender that spawned it
const ptyOwners = new Map<string, number>()
// Maps tabId → accumulated output lines for runner result reporting + failure-reason tails
const ptyOutput = new Map<string, string[]>()

// Strip ANSI and return the last few meaningful output lines — used to surface WHY a run
// failed (rate limit, auth error, the agent's final message) instead of a generic message.
function tailMeaningfulOutput(chunks: string[]): string {
  const text = chunks
    .join('')
    // CSI sequences INCLUDING private-mode prefixes (< = > ?) and intermediates — e.g.
    // \x1b[>4m, \x1b[<u, \x1b[?25h. The old [0-9;?] class missed < > = and let them leak.
    .replace(/\x1b\[[\x30-\x3f]*[\x20-\x2f]*[\x40-\x7e]/g, '')
    // OSC sequences (\x1b] ... BEL/ST) and any other ESC-prefixed control.
    .replace(/\x1b\][\s\S]*?(?:\x07|\x1b\\)/g, '')
    .replace(/\x1b[@-Z\\-_]/g, '')
    .replace(/\r/g, '\n')
  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean)
  return lines.slice(-6).join(' | ').slice(-600)
}
/** Strip ANSI so pattern matching works on the rendered text, not the escape soup. */
function stripAnsi(s: string): string {
  return s
    .replace(/\x1b\[[\x30-\x3f]*[\x20-\x2f]*[\x40-\x7e]/g, '')
    .replace(/\x1b\][\s\S]*?(?:\x07|\x1b\\)/g, '')
}

// Interactive gates an engine can raise at startup. Each one BLOCKS the process until
// answered — which is fatal for a headless one-shot: the PTY never exits, no result is
// ever POSTed, and the stage hangs instead of failing. Two distinct screens:
//
//   • FOLDER TRUST — claude asks once per never-before-seen directory ("Do you trust the
//     files in this folder?") and records the answer in ~/.claude.json. It is NOT the same
//     screen as the bypass-permissions warning and is NOT waived by
//     --dangerously-skip-permissions, so every first run in a fresh project hit it.
//   • BYPASS PERMISSIONS — the --dangerously-skip-permissions confirmation.
//
// Answering these automatically is the intended behavior here: Pathly is a headless
// orchestrator (no human in the per-step loop), the run already carries an explicit
// autonomy flag, and cwd is validated under $HOME before spawn. We log every auto-answer
// so it stays auditable rather than silent.
const TRUST_PROMPT_RE = /Do you trust the files in this (?:folder|directory)|trust the files in|folder is not trusted/i
const BYPASS_PROMPT_RE = /Bypass Permissions mode/i

/** Watch a HEADLESS engine PTY for a startup gate and answer it, so a first-run trust
 *  prompt fails-open into a real run instead of hanging the stage forever. Interactive
 *  tabs handle their own gates inline (they must also inject a prompt afterwards). */
function attachHeadlessGateDismisser(p: import('node-pty').IPty, tabId: string): void {
  let buf = ''
  let trustDone = false
  let bypassDone = false
  const sub = p.onData((chunk: string) => {
    if (trustDone && bypassDone) { sub.dispose(); return }
    buf = (buf + stripAnsi(chunk)).slice(-4000)
    if (!bypassDone && BYPASS_PROMPT_RE.test(buf)) {
      bypassDone = true
      slog('gate', tabId, 'auto-answered bypass-permissions screen')
      p.write('\r')
      buf = ''
      return
    }
    if (!trustDone && TRUST_PROMPT_RE.test(buf)) {
      trustDone = true
      slog('gate', tabId, 'auto-answered folder-trust prompt')
      p.write('\r')
      buf = ''
    }
  })
  // Startup gates only appear in the first seconds; stop watching so a long run's output
  // can never trip these patterns mid-flight (e.g. an agent echoing the prompt text).
  setTimeout(() => sub.dispose(), 30000)
}

// Maps tabId → runner metadata registered before spawn
const runnerTabMeta = new Map<string, { run_id: string; topic: string; spawnedAt: number; label: string; category?: 'flow' | 'loop' | 'single' }>()
// Tracks tabs killed by the user (not by the runner exiting naturally)
const ptyKilledByRunner = new Set<string>()
// Maps tabId → temp .ps1 script path created for that runner (Windows only)
const runnerScripts = new Map<string, string>()

function sendToWindow(tabId: string, channel: string, ...args: unknown[]): void {
  const win = ptyWindows.get(tabId)
  if (win && !win.isDestroyed()) {
    win.webContents.send(channel, ...args)
  }
}

function isValidCwd(dir: string): boolean {
  try {
    const real = fs.realpathSync(dir)
    const home = path.resolve(app.getPath('home'))
    return real.startsWith(home + path.sep) || real === home
  } catch {
    return false
  }
}

// Engines whose launcher we resolve to an absolute path before spawning. A Claude/Codex
// self-update rewrites the PATH shim (`npm i -g`) or moves a versioned install dir; if the
// runner spawns the bare name mid-swap, PowerShell throws CommandNotFound and the flow stage
// dies. Resolving an absolute launcher per spawn (and briefly waiting one out if it's mid-swap)
// keeps in-flight stages alive across an update.
const RESOLVABLE_ENGINES_LIST = ['claude', 'codex', 'agy'] as const
const RESOLVABLE_ENGINES = new Set<string>(RESOLVABLE_ENGINES_LIST)

const delay = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms))

/** Resolve an absolute path to a CLI engine's launcher, checking known install locations
 *  first and falling back to the bare name (PATH lookup). Prefers the npm `.ps1` shim so
 *  PowerShell arg-passing matches the previous bare-name behavior exactly (no regression). */
function resolveEnginePath(engine: string): string {
  if (process.platform === 'win32') {
    const appData = process.env.APPDATA ?? ''
    const localAppData = process.env.LOCALAPPDATA ?? ''
    const home = process.env.USERPROFILE ?? os.homedir()
    const candidates =
      engine === 'agy'
        ? [
            join(localAppData, 'agy', 'bin', 'agy.exe'),
            join(localAppData, 'Microsoft', 'WindowsApps', 'agy.cmd'),
            join(appData, 'npm', 'agy.cmd'),
            join(appData, 'npm', 'agy.ps1'),
          ]
        : [
            // npm-global shims — prefer .ps1 (what PATH resolves to today → identical arg handling)
            join(appData, 'npm', `${engine}.ps1`),
            join(appData, 'npm', `${engine}.cmd`),
            // native-installer locations
            join(localAppData, 'Programs', engine, `${engine}.exe`),
            join(home, '.local', 'bin', `${engine}.exe`),
          ]
    for (const c of candidates) {
      if (c && fs.existsSync(c)) return c
    }
  } else {
    for (const c of posixEngineCandidates(engine)) {
      try { if (fs.existsSync(c)) return c } catch { /* ignore */ }
    }
  }
  return engine // rely on PATH on non-Windows or if known paths don't exist
}

/** Generic POSIX bin dirs any engine may be installed into (engine-independent).
 *  The old fixed list had only the four "conventional" entries and missed every
 *  version-manager global bin — an `npm i -g` under nvm lands in
 *  `~/.nvm/versions/node/<ver>/bin`, which a fixed list can never name. */
function posixBinDirs(): string[] {
  const home = os.homedir()
  const out = [
    join(home, '.local', 'bin'),
    join(home, '.npm-global', 'bin'),
    join(home, '.bun', 'bin'),
    join(home, 'Library', 'pnpm'),
    join(home, '.volta', 'bin'),
    '/opt/homebrew/bin',
    '/usr/local/bin',
  ]
  // Version-manager node installs — enumerate versions rather than guessing one.
  for (const mgr of [join(home, '.nvm', 'versions', 'node'), join(home, '.fnm', 'node-versions')]) {
    try {
      for (const ver of fs.readdirSync(mgr)) {
        out.push(join(mgr, ver, 'bin'), join(mgr, ver, 'installation', 'bin'))
      }
    } catch { /* manager not installed */ }
  }
  return out
}

/** Dirs a specific engine's NATIVE installer uses — `~/.claude/local/claude` is Claude
 *  Code's default macOS install and was the most consequential omission from the old
 *  list (it is not on PATH for a Finder-launched app). */
function posixNativeDirs(engine: string): string[] {
  const home = os.homedir()
  return [join(home, `.${engine}`, 'local'), join(home, `.${engine}`, 'bin')]
}

/** Every place a POSIX install can put this engine's launcher, most-specific first. */
function posixEngineCandidates(engine: string): string[] {
  return [...posixNativeDirs(engine), ...posixBinDirs()].map((d) => join(d, engine))
}

/** PATH for spawned engines, widened with the dirs an engine can install into.
 *  A GUI-launched Electron app on macOS inherits launchd's minimal PATH
 *  (/usr/bin:/bin:/usr/sbin:/sbin) — NOT the user's zsh PATH — so a bare-name spawn,
 *  or a child process the engine itself shells out to (git, node), can fail to resolve
 *  even though the same command works in the user's terminal. Prepending the known
 *  install dirs makes a spawn behave identically whether the app was started from a
 *  terminal or from Finder. Existing PATH entries keep their order after the extras. */
function enrichedPath(): string {
  const existing = (process.env.PATH ?? '').split(path.delimiter).filter(Boolean)
  if (process.platform === 'win32') return existing.join(path.delimiter)
  const extras = Array.from(new Set([
    ...RESOLVABLE_ENGINES_LIST.flatMap(posixNativeDirs),
    ...posixBinDirs(),
  ])).filter((d) => {
    try { return fs.existsSync(d) } catch { return false }
  })
  return Array.from(new Set([...extras, ...existing])).join(path.delimiter)
}

/** True if `engine` resolves on PATH right now (one cheap `where`/`which` probe). */
function isOnPath(engine: string): Promise<boolean> {
  return new Promise((resolve) => {
    const probe = process.platform === 'win32' ? 'where' : 'which'
    try {
      const env = { ...process.env, PATH: enrichedPath() }
      execFile(probe, [engine], { timeout: 3000, windowsHide: true, env }, (err, stdout) => {
        resolve(!err && typeof stdout === 'string' && stdout.trim().length > 0)
      })
    } catch {
      resolve(false)
    }
  })
}

/** Resolve a launcher for a runner engine, surviving an in-progress self-update.
 *  Fast path: a known absolute launcher exists → use it (PATH-independent). Otherwise the
 *  launcher is either installed somewhere we don't list (PATH still works — don't stall) or
 *  mid-swap during an update (briefly absent). Probe PATH once; only if that also fails do we
 *  wait a few seconds for the swap to finish before giving up and falling back to the bare name. */
async function resolveEngineLauncher(engine: string): Promise<string> {
  const first = resolveEnginePath(engine)
  if (first !== engine) return first
  if (await isOnPath(engine)) return engine
  for (let attempt = 0; attempt < 3; attempt++) {
    await delay(1000)
    const retry = resolveEnginePath(engine)
    if (retry !== engine) return retry
    if (await isOnPath(engine)) return engine
  }
  return engine
}

// ── Engine preflight ─────────────────────────────────────────────────────────
// Nothing used to check that an engine was actually INSTALLED. ADAPTER_META is derived
// statically from adapters.yaml, so every engine always rendered as available and a
// missing binary surfaced only as a `pty.spawn FAILED` line in the main-process console
// — no UI signal, no remedy. This probes the real filesystem/PATH so the renderer can
// grey out what isn't there and show the command that installs it.

/** Mirrored in preload/index.ts and renderer types/global.d.ts — keep in sync. */
export interface EnginePreflight {
  engine: string
  /** CliAdapter id the UI keys off ('claude' | 'codex' | 'antigravity'). */
  adapter: string
  available: boolean
  /** Absolute launcher, the bare name if only PATH resolved it, else null. */
  resolvedPath: string | null
  /** Shell command that installs it — shown verbatim in the UI. */
  installHint: string
}

const ENGINE_INSTALL_HINTS: Record<string, string> = {
  claude: 'npm install -g @anthropic-ai/claude-code',
  codex: 'npm install -g @openai/codex',
  agy: 'npm install -g @google/antigravity-cli',
}

async function preflightEngine(engine: string): Promise<EnginePreflight> {
  const abs = resolveEnginePath(engine)
  // resolveEnginePath returns the bare name when no known location matched — fall back to
  // an actual PATH probe rather than reporting "missing" for an install we don't enumerate.
  const found = abs !== engine ? abs : (await isOnPath(engine)) ? engine : null
  return {
    engine,
    adapter: adapterIdFromLauncher(engine),
    available: found !== null,
    resolvedPath: found,
    installHint: ENGINE_INSTALL_HINTS[engine] ?? '',
  }
}

// Probing hits the filesystem + spawns `which`, so cache briefly — the selectors that
// consume this re-render often. `force` bypasses it after the user installs something.
let preflightCache: { at: number; data: EnginePreflight[] } | null = null
const PREFLIGHT_TTL_MS = 30000

async function preflightEngines(force: boolean): Promise<EnginePreflight[]> {
  if (!force && preflightCache && Date.now() - preflightCache.at < PREFLIGHT_TTL_MS) {
    return preflightCache.data
  }
  const data = await Promise.all(RESOLVABLE_ENGINES_LIST.map(preflightEngine))
  preflightCache = { at: Date.now(), data }
  slog('preflight', data.map((d) => `${d.engine}=${d.available ? d.resolvedPath : 'MISSING'}`).join(' '))
  return data
}

// Windows PowerShell 5.1 reads AND writes files with the legacy ANSI code page (cp1252) by default,
// so a Get-Content|Set-Content round-trip over a UTF-8 file mojibakes multi-byte chars
// (em-dash — = E2 80 94 → misread as cp1252 "â€"" → re-saved as UTF-8). This preamble makes
// THIS PowerShell session default to UTF-8 for cmdlet I/O + console output (the engine's stdout we
// parse as JSON). NOTE: it only covers cmdlets run in this session — $PSDefaultParameterValues is a
// session var, NOT inherited by a child PowerShell the agent itself spawns for its edits, and
// Get-Content ignores the console codepage. The engine-agnostic prevention for that lives in the
// AI-action prompts (commentUtils.ts), which tell the agent to write UTF-8 via its native tools.
const PS_UTF8_PREAMBLE = [
  '$OutputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false',
  "$PSDefaultParameterValues['*:Encoding'] = 'utf8'",
]
const PS_UTF8_INLINE = PS_UTF8_PREAMBLE.join('; ')

function resolveShell(command: string | undefined): { shell: string; args: string[] } {
  if (process.platform !== 'win32') {
    if (RESOLVABLE_ENGINES.has(command ?? '')) {
      // Resolve to an absolute launcher — this path previously spawned the BARE name via
      // `bash -c "exec claude"`, so a manual engine tab got none of the resolution the runner
      // path does. A non-login, non-interactive bash sources no ~/.zshrc or ~/.zprofile, so a
      // native (~/.claude/local) or nvm-global install was simply invisible and the tab died
      // with "command not found". We deliberately do NOT switch to a login shell to fix that:
      // an rc banner containing "> " would trip the prompt-ready matcher in the initialInput
      // injector below and submit a prompt early. Absolute path + enrichedPath() covers it
      // without letting user rc output into the stream.
      const exe = resolveEnginePath(command as string)
      const shell = process.env.SHELL || 'zsh'
      return { shell, args: ['-c', `exec '${exe.replace(/'/g, "'\\''")}'`] }
    }
    return { shell: command ?? process.env.SHELL ?? 'zsh', args: [] }
  }
  if (command === 'claude' || command === 'codex' || command === 'agy') {
    // Absolute launcher (falls back to the bare name) so manual tabs survive a self-update too.
    const exe = resolveEnginePath(command)
    return { shell: 'powershell.exe', args: ['-NoExit', '-Command', `${PS_UTF8_INLINE}; & '${exe}'`] }
  }
  return { shell: 'powershell.exe', args: [] }
}

// ClaudeJsonResult, parseClaudeJsonResult and the stream-json renderer moved to ./claudeJson
// (pure, no Electron deps → unit-tested in claudeJson.test.ts).

/** Spawn a specific argv interactively — the shell stays open after the command exits so the user can keep chatting. */
function resolveInteractiveShell(argv: string[]): { shell: string; args: string[] } {
  const cmd = argv[0]
  const rest = argv.slice(1)
  if (process.platform !== 'win32') {
    const escaped = [cmd, ...rest].map((a) => `'${a.replace(/'/g, "'\\''")}'`).join(' ')
    return { shell: 'bash', args: ['-c', `exec ${escaped}`] }
  }
  // Windows: -NoExit keeps PowerShell open after the process exits so the user sees the result
  const tokens = [cmd, ...rest].map((a) => `'${a}'`).join(' ')
  return { shell: 'powershell.exe', args: ['-NoExit', '-Command', `${PS_UTF8_INLINE}; & ${tokens}`] }
}

/** Spawn a specific argv non-interactively — used by the runner so the PTY exits when the agent finishes. */
function resolveRunnerShell(argv: string[]): { shell: string; args: string[]; tempScript?: string } {
  if (process.platform !== 'win32') {
    return { shell: argv[0], args: argv.slice(1) }
  }
  // Windows: -EncodedCommand (base64 UTF-16LE) has a hard ~32 KB limit from Win32's CreateProcess.
  // Pathly stage prompts easily exceed this. Write a .ps1 script to a temp file instead.
  //
  // For arguments containing newlines OR any variant of single quote (U+0027 apostrophe,
  // U+2018/U+2019 curly quotes) use a PowerShell here-string (@'...'@) which requires
  // NO escaping whatsoever. Agent contracts contain contractions (Don't, can't, isn't) that
  // would terminate a single-quoted string early if not handled this way.
  //
  // For short flag arguments (no newlines, no quotes) use plain single-quoted strings.
  //
  // IMPORTANT: write with UTF-8 BOM so PowerShell 5.1 reads the file as UTF-8.
  const tmpScript = path.join(os.tmpdir(), `pathly-runner-${Date.now()}.ps1`)
  const bom = Buffer.from([0xEF, 0xBB, 0xBF])

  // Detect the engine by launcher BASENAME — argv[0] may be a resolved absolute path
  // (…\claude.ps1) rather than the bare name, so a `=== 'claude'` check would miss.
  const engineBase = path.basename(argv[0]).toLowerCase()
  const isClaude = engineBase.startsWith('claude')
  const isCodex = engineBase.startsWith('codex')

  // A cmd.exe batch shim (.cmd/.bat) SHREDS any argument containing a newline: cmd's batch
  // parser truncates the value at the first CR/LF, and the escaped remainder makes cmd print
  // "The system cannot find the path specified" — yet the whole chain still exits 0. So a
  // multi-line prompt handed to a batch shim silently produces NO real run (empirically
  // confirmed with agy.cmd). Two mitigations below key off this flag: claude/codex move the
  // prompt onto stdin regardless of length (there's a channel); an engine with no stdin path
  // (agy) is failed loudly rather than recording a false success.
  const isBatchShim = /\.(cmd|bat)$/i.test(argv[0])

  // Windows caps a process command line (~32 KB). A big composed prompt (e.g. the planner
  // skill) passed as `claude -p <prompt>` blows it → claude.exe "filename or extension is too
  // long". claude's print mode reads the prompt from STDIN, so for an over-long prompt we pipe
  // it instead of putting it on the command line. (The first long non-flag arg is the prompt.)
  // Both claude and codex read the prompt from STDIN, so an over-long prompt is piped instead
  // of placed on the command line. claude's `-p` reads stdin directly; `codex exec` reads stdin
  // when the prompt is `-` or absent (per `codex exec --help`: "If not provided as an argument
  // (or if `-` is used), instructions are read from stdin"). This is what stops the big-prompt
  // codex.ps1 crash ("The filename or extension is too long").
  const STDIN_PROMPT_MAX = 8000
  let pipeIdx = -1
  if (isClaude || isCodex) {
    for (let i = 1; i < argv.length; i++) {
      const a = argv[i]
      if (a.startsWith('-')) continue
      // Pipe when the prompt is over-long OR — through a batch shim — carries a newline that
      // the shim would otherwise shred. Either way it moves off the command line onto stdin.
      if (a.length > STDIN_PROMPT_MAX || (isBatchShim && /[\r\n]/.test(a))) { pipeIdx = i; break }
    }
  }

  // Batch shim + a still-on-command-line newline arg = guaranteed silent shred (the engine has
  // no stdin fallback, or the multi-line arg is a non-prompt one we don't pipe). Fail loudly so
  // the run surfaces as an error instead of a false success. This is the agy-diagram failure mode.
  if (isBatchShim && pipeIdx === -1) {
    const shredIdx = argv.findIndex((a, i) => i > 0 && /[\r\n]/.test(a))
    if (shredIdx !== -1) {
      throw new Error(
        `Cannot run a multi-line prompt through a batch shim (${path.basename(argv[0])}). ` +
        'A .cmd/.bat wrapper truncates the argument at the first newline and the run would ' +
        "silently do nothing. Install the engine's native launcher (.exe / .ps1), or use " +
        'claude/codex, which move the prompt onto stdin.',
      )
    }
  }

  const varDecls: string[] = []
  const callTokens: string[] = []
  let pipePrefix = ''

  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (i === pipeIdx) {
      // Pipe the prompt via stdin — keep it OFF the command line so a huge prompt can never
      // overflow the Win32 command-line limit. claude's `-p` reads stdin when the value is
      // omitted; `codex exec` reads stdin only when the prompt arg is `-`, so substitute it.
      const body = a.endsWith('\n') ? a : `${a}\n`
      varDecls.push(`$prompt = @'\n${body}'@`)
      pipePrefix = '$prompt | '
      if (isCodex) callTokens.push("'-'")
      continue
    }
    // Use a here-string for any arg that has newlines or single-quote variants.
    // Here-strings only end at `'@` at column 0 — virtually impossible in prompt content.
    if (/['''\r\n]/.test(a)) {
      const varName = `$a${i}`
      // PowerShell requires a newline immediately before the closing marker.
      const body = a.endsWith('\n') ? a : `${a}\n`
      varDecls.push(`${varName} = @'\n${body}'@`)
      // PS 5.1 does not escape " when passing a variable to a native exe, so
      // the C-runtime argument parser sees unescaped quotes and truncates the value.
      // Replace " with \" so the C-runtime receives the literal double-quote characters.
      callTokens.push(`(${varName}.Replace('"', '\\"'))`)
    } else {
      callTokens.push(`'${a}'`)
    }
  }

  // `codex exec` reads stdin even when the prompt is passed as an argument ("Reading additional
  // input from stdin…") and stalls forever in a PTY whose stdin never closes. Piping $null gives
  // it an immediately-closed stdin so it proceeds with the prompt arg. If we're already piping
  // the prompt (claude over-long path) that pipe serves the same purpose.
  const stdinClose = pipePrefix || (isCodex ? '$null | ' : '')
  // UTF-8 preamble first — hardens this session's cmdlet I/O + console encoding. See PS_UTF8_PREAMBLE.
  const scriptLines = [...PS_UTF8_PREAMBLE, ...varDecls, `${stdinClose}& ${callTokens.join(' ')}`].join('\n') + '\r\n'
  fs.writeFileSync(tmpScript, Buffer.concat([bom, Buffer.from(scriptLines, 'utf8')]))
  return {
    shell: 'powershell.exe',
    args: ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', tmpScript],
    tempScript: tmpScript,
  }
}

/** Force-terminate a PTY and its child process tree.
 *  On Windows the runner shell is `powershell.exe -File …ps1`, which spawns the
 *  real engine (`claude`/`codex`) as a child. node-pty's kill() only ends the
 *  PowerShell host, leaving the engine running — `taskkill /T` reaps the tree. */
function killPtyTree(p: import('node-pty').IPty): void {
  if (process.platform === 'win32' && p.pid) {
    try {
      execFile('taskkill', ['/PID', String(p.pid), '/T', '/F'], () => { /* ignore */ })
      return
    } catch { /* fall through to node-pty kill */ }
  }
  try { p.kill() } catch { /* ignore */ }
}

export function killAllPtys(): void {
  activePtys.forEach((p) => { try { p.kill() } catch { /* ignore */ } })
  runnerScripts.forEach((scriptPath) => { try { fs.unlinkSync(scriptPath) } catch { /* ignore */ } })
  activeEngines.clear()
  activePtys.clear()
  ptyWindows.clear()
  ptyOwners.clear()
  ptyOutput.clear()
  runnerTabMeta.clear()
  ptyKilledByRunner.clear()
  runnerScripts.clear()
  // Sweep any orphaned runner scripts left by force-killed PTYs (taskkill doesn't fire onExit).
  try {
    const dir = os.tmpdir()
    for (const f of fs.readdirSync(dir)) {
      if (f.startsWith('pathly-runner-') && f.endsWith('.ps1')) {
        try { fs.unlinkSync(path.join(dir, f)) } catch { /* ignore */ }
      }
    }
  } catch { /* ignore */ }
}

// ── CLI-engine spawn scheduler ───────────────────────────────────────────────
// One place controls how many CLI engines run at once. Every spawn funnels through
// terminal:spawn. Two classes of engine:
//   • headless one-shots (Analyze/Split/agents/board/goals) — capped and QUEUED.
//   • interactive sessions (chat / manual `claude`) — capped but REJECTED (never queued),
//     since they are long-lived and user-initiated.
// A global ceiling bounds the SUM so the machine/API are never flooded. All caps configurable.
const RATE_LIMIT_COOLDOWN_MS = 15000
const RATE_LIMIT_RE = /rate.?limit|usage limit|quota|\b429\b|too many requests|overloaded/i
const CLI_ENGINES = new Set(['claude', 'codex', 'antigravity', 'agy', 'copilot'])

const caps = { global: 8, headless: 5, interactive: 5 }
const gatedRunning = new Set<string>()        // headless one-shots currently running
const interactiveRunning = new Set<string>()  // interactive engine sessions currently running
interface QueueItem { tabId: string; priority: number; resolve: () => void; reject: (e: Error) => void }
const engineQueue: QueueItem[] = []           // ordered — front runs next

// Identified live engines (PTY spawned, not yet exited) — the CLI monitor's SINGLE source of
// truth. Keyed by tabId; carries enough to render a monitor row WITHOUT the renderer's
// terminalStore (which a window reload would wipe while these PTYs keep running here). Populated
// right after pty.spawn; removed in releaseEngineSlot (the one place exit/kill/cancel converge).
interface RunningEngine {
  tabId: string
  adapter: string
  label: string
  startedAt: number
  /** How the engine was spawned — the board's primary grouping (runner tab → flow, else single). */
  category: 'flow' | 'loop' | 'single'
  /** Feature/topic this engine serves, when known (runner topic or spawn telemetry.feature). */
  feature?: string
  /** Agent role from spawn telemetry (single-shot editor/AI actions); absent for runner tabs. */
  role?: string
  /** Pipeline run id (runner tabs only) — keys the per-flow cost rollup (/db/runs/<run_id>/cost). */
  runId?: string
  /** When the engine finished — set only on RECENT/history entries. */
  finishedAt?: number
}
const activeEngines = new Map<string, RunningEngine>()
// Engines accepted by the gate but still WAITING for a slot (queued / paused). Same record shape,
// startedAt = when queued. Registered at request time so the monitor can render queued rows with a
// real adapter/category/feature, then moved to activeEngines when the PTY actually spawns.
const queuedEngines = new Map<string, RunningEngine>()
// Recently-finished engines (bounded, newest first) — the monitor's RECENT/history list. Pushed in
// releaseEngineSlot (exit / kill / cancel) so a spawn's record is visible after it ends, and it
// survives a renderer reload (it lives in the main process).
const RECENT_CAP = 40
const recentEngines: RunningEngine[] = []

/** Normalize a launcher (bare 'claude' or a resolved '…\claude.ps1') to a CliAdapter id so the
 *  monitor badges it consistently regardless of how it was spawned. */
function adapterIdFromLauncher(launcher: string): string {
  const base = path.basename(launcher).toLowerCase().replace(/\.(ps1|cmd|exe)$/, '')
  if (base.startsWith('claude')) return 'claude'
  if (base.startsWith('codex')) return 'codex'
  if (base.startsWith('agy') || base.startsWith('antigravity')) return 'antigravity'
  if (base.startsWith('copilot')) return 'copilot'
  return base || 'claude'
}

let queuePaused = false
let rateLimitedUntil = 0
let spawnStateWin: BrowserWindow | null = null

// Lightweight spawn-lifecycle tracing → main-process console (the `npm run dev` terminal).
// Flip SPAWN_DEBUG to false to silence.
const SPAWN_DEBUG = true
function slog(...a: unknown[]): void { if (SPAWN_DEBUG) console.log('[spawn]', ...a) }
function spawnCounts(): string {
  return `running=${gatedRunning.size} interactive=${interactiveRunning.size} total=${totalRunning()}/${caps.global} queued=${engineQueue.length} paused=${queuePaused}`
}

function totalRunning(): number { return gatedRunning.size + interactiveRunning.size }
function canStartHeadless(): boolean {
  return !queuePaused && gatedRunning.size < caps.headless && totalRunning() < caps.global
}
function canStartInteractive(): boolean {
  return interactiveRunning.size < caps.interactive && totalRunning() < caps.global
}

function broadcastSpawnState(): void {
  try {
    spawnStateWin?.webContents.send('spawn:state', {
      running: gatedRunning.size,
      interactive: interactiveRunning.size,
      total: totalRunning(),
      engines: Array.from(activeEngines.values()),
      queuedEngines: Array.from(queuedEngines.values()),
      recentEngines: [...recentEngines],
      queued: engineQueue.map((w) => w.tabId),
      paused: queuePaused,
      rateLimitedUntil,
      caps: { ...caps },
    })
  } catch { /* ignore */ }
}

function acquireEngineSlot(tabId: string, priority = 0, meta?: RunningEngine): Promise<void> {
  if (canStartHeadless()) {
    gatedRunning.add(tabId)
    broadcastSpawnState()
    return Promise.resolve()
  }
  if (meta) queuedEngines.set(tabId, meta)   // waiting for a slot → render it as a queued row
  return new Promise<void>((resolve, reject) => {
    const item: QueueItem = { tabId, priority, resolve, reject }
    // Keep priority items (runner/board) ahead of inline editor actions, preserving order in a tier.
    const idx = priority > 0 ? engineQueue.findIndex((w) => w.priority < priority) : -1
    if (idx === -1) engineQueue.push(item)
    else engineQueue.splice(idx, 0, item)
    broadcastSpawnState()
  })
}

// Start as many queued runs as the caps now allow (a freed interactive slot may unblock several).
function promoteQueue(): void {
  while (engineQueue.length && canStartHeadless()) {
    const next = engineQueue.shift() as QueueItem
    gatedRunning.add(next.tabId)
    queuedEngines.delete(next.tabId)   // promoted to running — activeEngines.set follows after pty.spawn
    next.resolve()
  }
}

function releaseEngineSlot(tabId: string): void {
  const finished = activeEngines.get(tabId) ?? queuedEngines.get(tabId)  // capture before delete → RECENT
  const wasEngine = activeEngines.delete(tabId)   // live engine gone (exit/kill) — drop from the monitor registry
  queuedEngines.delete(tabId)                     // also clear it if it was still waiting for a slot
  if (finished) {
    recentEngines.unshift({ ...finished, finishedAt: Date.now() })
    if (recentEngines.length > RECENT_CAP) recentEngines.length = RECENT_CAP
  }
  const qi = engineQueue.findIndex((w) => w.tabId === tabId)
  if (qi !== -1) {
    const [w] = engineQueue.splice(qi, 1) // cancelled while queued — reject so the spawn() call unblocks
    w.reject(new Error('cancelled'))
    slog('release: cancelled while queued', tabId, '|', spawnCounts())
    broadcastSpawnState()
    return
  }
  if (!gatedRunning.delete(tabId) && !interactiveRunning.delete(tabId)) {
    if (wasEngine) broadcastSpawnState()   // slot untracked but an engine was removed — keep the monitor honest
    slog('release: not tracked', tabId)
    return
  }
  slog('release', tabId, '|', spawnCounts())
  promoteQueue()
  broadcastSpawnState()
}

// Hold before starting a gated run if we recently hit a rate limit, so a 429 burst backs off.
async function awaitRateLimitCooldown(): Promise<void> {
  const wait = rateLimitedUntil - Date.now()
  if (wait > 0) await new Promise<void>((r) => setTimeout(r, wait))
}

function reorderQueue(tabId: string, dir: 'up' | 'down'): void {
  const i = engineQueue.findIndex((w) => w.tabId === tabId)
  if (i === -1) return
  const j = dir === 'up' ? i - 1 : i + 1
  if (j < 0 || j >= engineQueue.length) return
  const tmp = engineQueue[i]; engineQueue[i] = engineQueue[j]; engineQueue[j] = tmp
  broadcastSpawnState()
}

/** Telemetry hint passed by renderer-driven one-shot spawns (editor AI actions, HQ
 *  summaries) so the spawn gate can project a project-tier invocation+span for them.
 *  Absent for runner/board tabs — those are projected Python-side by the supervisor. */
interface SpawnTelemetryMeta {
  telemetry?: { scopeTier: string; label: string; feature?: string; role?: string }
}

export function registerTerminalHandlers(win: BrowserWindow): void {
  spawnStateWin = win
  ipcMain.handle('terminal:spawn', async (event, tabId: string, cwd: string, command?: string, runnerArgv?: string[], initialInput?: string, spawnMeta?: SpawnTelemetryMeta) => {
    slog('request', tabId, '| command=' + (command ?? '-'), 'argv0=' + (runnerArgv?.[0] ?? '-'), 'hasInput=' + !!initialInput, '|', spawnCounts())
    if (!pty) { console.error('[spawn] reject: node-pty unavailable', tabId); throw new Error('node-pty is not available') }
    if (activePtys.has(tabId)) {
      console.error('[spawn] reject: tab already exists', tabId)
      throw new Error('Tab already exists')
    }

    if (!cwd) {
      throw new Error('Working directory is required')
    }

    if (!isValidCwd(cwd)) {
      throw new Error('Invalid working directory: ' + cwd)
    }

    let shell: string
    let shellArgs: string[]
    let tempScript: string | undefined

    if (runnerArgv && runnerArgv.length > 0) {
      if (!ALLOWED_SHELLS.has(runnerArgv[0])) {
        throw new Error('Shell not allowed: ' + runnerArgv[0])
      }
      // Resolve the engine to an absolute launcher so a self-update that rewrites the PATH
      // shim doesn't kill this stage with CommandNotFound. Gating below still keys off the
      // original bare name, so queue classification is unchanged.
      let effectiveArgv = runnerArgv
      if (RESOLVABLE_ENGINES.has(runnerArgv[0])) {
        const launcher = await resolveEngineLauncher(runnerArgv[0])
        if (launcher !== runnerArgv[0]) {
          effectiveArgv = [launcher, ...runnerArgv.slice(1)]
          slog('resolved engine', runnerArgv[0], '→', launcher)
        }
      }
      if (initialInput) {
        // Interactive runner: open the CLI normally so the user can keep chatting after
        ;({ shell, args: shellArgs } = resolveInteractiveShell(effectiveArgv))
      } else {
        // Headless runner: PTY exits when agent finishes
        ;({ shell, args: shellArgs, tempScript } = resolveRunnerShell(effectiveArgv))
      }
      if (tempScript) runnerScripts.set(tabId, tempScript)
    } else {
      // Manual terminal tab: just the adapter name
      if (command !== undefined && !ALLOWED_SHELLS.has(command)) {
        throw new Error('Shell not allowed: ' + command)
      }
      ;({ shell, args: shellArgs } = resolveShell(command))
    }

    // The monitor record for this engine, from what's known now: adapter, plus category/feature/
    // role from the runner topic or spawn telemetry. Used both while queued (waiting for a slot)
    // and once the PTY spawns, so a queued engine renders with the same identity it'll run with.
    const buildEngineMeta = (startedAt: number): RunningEngine => {
      const rmeta = runnerTabMeta.get(tabId)
      const adapter = adapterIdFromLauncher(runnerArgv?.[0] ?? command ?? '')
      return {
        tabId,
        adapter,
        label: rmeta?.label ?? spawnMeta?.telemetry?.label ?? adapter,
        startedAt,
        // Prefer the explicit category from the spawn payload (board one-shot → 'single',
        // FSM pipeline → 'flow'); fall back to the old presence-based guess for any spawn
        // that predates the threaded category. Fixes board single-agent runs reading as FLOW.
        category: rmeta?.category ?? (rmeta ? 'flow' : 'single'),
        feature: rmeta?.topic ?? spawnMeta?.telemetry?.feature,
        role: spawnMeta?.telemetry?.role,
        runId: rmeta?.run_id,
      }
    }

    // Gate only headless CLI-engine runs (not interactive sessions or manual shells). The slot
    // is held until the PTY exits (released in onExit/kill), so the cap limits RUNNING engines.
    const argvEngine = !!runnerArgv && runnerArgv.length > 0 && CLI_ENGINES.has(runnerArgv[0])
    const cmdEngine = !!command && CLI_ENGINES.has(command)
    const headlessEngine = argvEngine && !initialInput            // one-shot — queued
    const interactiveEngine = (argvEngine && !!initialInput) || cmdEngine  // chat / manual — rejected over cap
    if (headlessEngine) {
      // Runner/board stages register before spawn → give them priority so a headless burst
      // can't starve the pipeline. Then honor any active rate-limit cooldown.
      const priority = runnerTabMeta.has(tabId) ? 10 : 0
      slog('headless', tabId, canStartHeadless() ? 'run now' : 'QUEUED', 'priority=' + priority, '|', spawnCounts())
      await acquireEngineSlot(tabId, priority, buildEngineMeta(Date.now()))
      const cd = rateLimitedUntil - Date.now()
      if (cd > 0) slog('headless', tabId, `rate-limit cooldown ${cd}ms`)
      await awaitRateLimitCooldown()
    } else if (interactiveEngine) {
      if (!canStartInteractive()) {
        console.error('[spawn] reject: interactive over cap', tabId, '|', spawnCounts())
        throw new Error(`Too many engines running (${totalRunning()}/${caps.global}). Close a session before opening another.`)
      }
      interactiveRunning.add(tabId)
      slog('interactive', tabId, 'run now', '|', spawnCounts())
      broadcastSpawnState()
    } else {
      slog('ungated', tabId, '(manual shell / non-engine)')
    }

    let ptyProcess: import('node-pty').IPty
    try {
      ptyProcess = pty.spawn(shell, shellArgs, {
        name: 'xterm-color',
        cols: 80,
        rows: 24,
        cwd: cwd,
        // Export PATHLY_PROJECT_ROOT so the stop hook (which runs as a child of this
        // agent PTY) can find the active feature in the DB and write the BILLING_UPDATE.
        // Without it, stop_telemetry.py hits `if not project_root: sys.exit(0)` and
        // in-app COST silently stays blank. cwd IS the project root (validated above);
        // the hook forward-slash-normalizes it, matching the stored fsm_events key.
        // Runner spawns are billed authoritatively by the gate → /runner/terminal/result
        // (adapter-agnostic, run-keyed). Mark them so the claude stop hook SKIPS them and can't
        // double-bill / mis-attribute via its "most recent feature" guess. Interactive claude
        // (no runner tab) carries no marker, so the hook still bills it (its only cost source).
        env: {
          ...process.env,
          // Widened PATH — a Finder-launched Electron app inherits launchd's minimal PATH,
          // not the user's shell PATH, so without this an engine (or a tool the engine
          // shells out to) can be unresolvable even though it works in the user's terminal.
          PATH: enrichedPath(),
          PATHLY_PROJECT_ROOT: cwd,
          ...(runnerTabMeta.has(tabId) ? { PATHLY_GATE_BILLED: '1' } : {}),
        } as Record<string, string>,
      })
    } catch (e) {
      console.error('[spawn] pty.spawn FAILED', tabId, 'shell=' + shell, 'args=' + JSON.stringify(shellArgs).slice(0, 200), '→', (e as Error).message)
      if (headlessEngine || interactiveEngine) releaseEngineSlot(tabId)
      // A missing engine binary is by far the most common spawn failure, and a bare
      // ENOENT tells the user nothing. Name the engine and the command that installs it.
      const wanted = runnerArgv?.[0] ?? command
      const bare = wanted ? path.basename(wanted).replace(/\.(ps1|cmd|exe)$/, '') : ''
      if (RESOLVABLE_ENGINES.has(bare) && /ENOENT|not found|cannot find/i.test((e as Error).message)) {
        throw new Error(
          `'${bare}' is not installed, or is not visible to Pathly. ` +
          `Install it with: ${ENGINE_INSTALL_HINTS[bare] ?? `install ${bare}`}`,
        )
      }
      throw e
    }
    const ptyStartedAt = Date.now()

    // Register this live engine with the authoritative gate so the CLI monitor renders EVERY
    // running engine — board/runner, editor one-shot, and manual REPL — from ONE source of truth,
    // not the renderer's per-tab status (which races the spawn round-trip and misses backend runs).
    if (headlessEngine || interactiveEngine) {
      activeEngines.set(tabId, buildEngineMeta(ptyStartedAt))
      queuedEngines.delete(tabId)   // was queued (if at all) → now running
      broadcastSpawnState()
    }

    // Default target window is the main window
    ptyWindows.set(tabId, win)
    // Phase 2: record ownership
    ptyOwners.set(tabId, event.sender.id)

    // Inject the stage prompt using the same two-phase pattern as launchTerminal.ts:
    //
    //   Phase 1 — if the --dangerously-skip-permissions warning screen appears,
    //             auto-dismiss it with a bare \r and keep watching.
    //
    //   Phase 2 — wait for Claude's '> ' input prompt (ANSI-stripped), which is the
    //             reliable signal that readline is ready to accept input.
    //             Then send bracketed paste + \r as ONE atomic write.
    //             Splitting into two writes with a delay is racy — \r can arrive while
    //             Claude is still flushing startup output, confusing readline.
    //             (This is the same lesson learned in launchTerminal.ts writeToTerminal.)
    //
    //   Fallback — if '> ' never appears within 5 s, inject anyway.
    if (initialInput) {
      let injected = false
      let bypassDismissed = false
      let trustDismissed = false
      let strippedBuf = ''

      const doInject = (): void => {
        if (injected) return
        injected = true
        clearTimeout(fallbackTimer)
        unsubscribe.dispose()
        // Write the bracketed paste.
        ptyProcess.write('\x1b[200~' + initialInput + '\x1b[201~')
        // Wait for Claude to render the paste indicator '[Pasted text…]' in the
        // terminal output — that confirms Ink has finished processing the paste
        // and the input field is active. Then send \r to submit.
        // Same event-driven approach as waiting for '> ' before injecting.
        // Fallback: send \r after 6 s if the indicator never appears (large prompts
        // can take several seconds to render in Claude's Ink UI).
        let enterSent = false
        const enterFallback = setTimeout(() => {
          if (!enterSent) { enterSent = true; ptyProcess.write('\r') }
        }, 6000)
        let pasteBuf = ''
        const pasteRenderSub = ptyProcess.onData((chunk: string) => {
          if (enterSent) return
          pasteBuf += chunk
            .replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '')
            .replace(/\x1b\][\s\S]*?(?:\x07|\x1b\\)/g, '')
          // Claude shows "[Pasted text", "[Large input", or "[Input (N lines)]"
          // depending on prompt size — match any of these paste-complete signals.
          if (/\[Pasted text|\[Large input|\[Input \(/.test(pasteBuf)) {
            enterSent = true
            clearTimeout(enterFallback)
            pasteRenderSub.dispose()
            ptyProcess.write('\r')
          }
        })
      }

      const fallbackTimer = setTimeout(doInject, 5000)

      const unsubscribe = ptyProcess.onData((data: string) => {
        if (injected) return
        // Strip ANSI escape sequences so pattern matching works reliably
        strippedBuf += stripAnsi(data)

        // Phase 1: auto-dismiss either startup gate. Both are cleared the same way (Enter
        // accepts the default). Reset the buffer after answering — the dismissed screen's
        // own text can contain "> ", which would otherwise read as "readline is ready" in
        // phase 2 and inject the prompt into a UI that isn't listening yet.
        if (!bypassDismissed && BYPASS_PROMPT_RE.test(strippedBuf)) {
          bypassDismissed = true
          slog('gate', tabId, 'auto-answered bypass-permissions screen')
          ptyProcess.write('\r')
          strippedBuf = ''
          return
        }
        if (!trustDismissed && TRUST_PROMPT_RE.test(strippedBuf)) {
          trustDismissed = true
          slog('gate', tabId, 'auto-answered folder-trust prompt')
          ptyProcess.write('\r')
          strippedBuf = ''
          return
        }

        // Phase 2: Claude's '> ' prompt means readline is ready — inject now
        if (strippedBuf.includes('> ')) {
          doInject()
        }
      })
    } else if (headlessEngine) {
      // A headless one-shot has no injector, so before this it had NO path at all for a
      // startup gate — a first run in an untrusted folder simply hung until killed.
      attachHeadlessGateDismisser(ptyProcess, tabId)
    }

    // Stream-json one-shots (editor / chat) asked claude for an event stream so the gate can
    // capture cost/tokens/tool-calls. Render those events to clean prose + "⚙ Tool" lines instead
    // of dumping raw JSON. ONLY these tabs are affected — every other spawn is byte-identical.
    const isStreamJsonTab = headlessEngine && !runnerTabMeta.has(tabId)
      && !!spawnMeta?.telemetry && !!runnerArgv?.includes('stream-json')
    const streamState: StreamJsonState | null = isStreamJsonTab ? newStreamJsonState() : null

    ptyProcess.onData((data: string) => {
      if (streamState) {
        feedStreamJson(streamState, data, (text) => sendToWindow(tabId, `terminal:data:${tabId}`, text))
      } else {
        sendToWindow(tabId, `terminal:data:${tabId}`, data)
      }
      // Buffer a rolling RAW tail for every tab so onExit can report the real failure reason for
      // notebook/editor AI actions too (stream tabs read the clean result from streamState).
      const lines = ptyOutput.get(tabId) ?? []
      lines.push(data)
      if (lines.length > 500) lines.splice(0, lines.length - 500)
      ptyOutput.set(tabId, lines)
    })

    ptyProcess.onExit(({ exitCode }) => {
      const wallS = ((Date.now() - ptyStartedAt) / 1000).toFixed(1)
      const isEngine = headlessEngine || interactiveEngine
      const dbgTail = tailMeaningfulOutput(ptyOutput.get(tabId) ?? []).slice(-500).replace(/\s+/g, ' ').trim()
      if (exitCode !== 0) console.error('[spawn] exit', tabId, 'code=' + exitCode, `(${wallS}s)`, '| tail:', dbgTail || '(no output)')
      else if (isEngine) slog('exit', tabId, 'code=0', `(${wallS}s) engine | tail:`, dbgTail || '(no output)')
      else slog('exit', tabId, 'code=0', `(${wallS}s)`)
      activePtys.delete(tabId)
      ptyOwners.delete(tabId)
      releaseEngineSlot(tabId)
      const scriptPath = runnerScripts.get(tabId)
      if (scriptPath) { runnerScripts.delete(tabId); try { fs.unlinkSync(scriptPath) } catch { /* ignore */ } }
      const exitTailRaw = tailMeaningfulOutput(ptyOutput.get(tabId) ?? [])
      // One-shot telemetry: a gated headless engine run that is NOT a runner tab but carries a
      // telemetry hint (editor AI actions, HQ summaries). Cost/tokens/tool-count come from the
      // stream-json renderer's captured result event; the exit tail is normalized to the agent's
      // result prose so stdout-reading consumers (aiRouter) stay clean instead of seeing JSON.
      const telem = spawnMeta?.telemetry
      const isOneShotTelem = headlessEngine && !runnerTabMeta.has(tabId) && !!telem
      const oneShotParsed = streamState?.result
        ?? (isOneShotTelem ? parseClaudeJsonResult((ptyOutput.get(tabId) ?? []).join('')) : null)
      const exitTail = oneShotParsed?.result ? oneShotParsed.result.slice(-4000) : exitTailRaw
      // If a gated engine run hit a rate limit, arm a cooldown so the next gated runs back off.
      if (headlessEngine && exitCode !== 0 && RATE_LIMIT_RE.test(exitTailRaw)) {
        rateLimitedUntil = Date.now() + RATE_LIMIT_COOLDOWN_MS
        broadcastSpawnState()
      }
      sendToWindow(tabId, 'terminal:exit', tabId, exitCode, exitTail)
      const runnerMeta = runnerTabMeta.get(tabId)
      if (runnerMeta) {
        const userInitiated = ptyKilledByRunner.has(tabId)
        const stdoutTail = (ptyOutput.get(tabId) ?? []).join('')
        // Parse the claude --output-format=json result
        const stageResult = parseClaudeJsonResult(stdoutTail)
        if (stageResult) {
          sendToWindow(tabId, 'terminal:stage-result', tabId, stageResult)
        }
        const wallSeconds = (Date.now() - runnerMeta.spawnedAt) / 1000
        runnerTabMeta.delete(tabId)
        ptyOutput.delete(tabId)
        ptyKilledByRunner.delete(tabId)
        const label = runnerMeta.label || tabId
        const banner = exitCode === 0
          ? `\r\n\x1b[2m──\x1b[0m \x1b[1;32m${label} DONE\x1b[0m \x1b[2m──────────────────────────────\x1b[0m\r\n`
          : `\r\n\x1b[2m──\x1b[0m \x1b[1;31m${label} ABORTED\x1b[0m \x1b[2m──────────────────────────────\x1b[0m\r\n`
        sendToWindow(tabId, `terminal:data:${tabId}`, banner)
        // The adapter that SPAWNED this run (its launcher). Sent so the server parses the result
        // with the RIGHT usage parser instead of inferring from RunnerState.current_adapter,
        // which — under early-advance — may already point at the NEXT stage's engine, so a codex
        // stage's output would be parsed by the claude parser (no token usage) → 0 tokens / $0.
        const runnerAdapter = path.basename(runnerArgv?.[0] ?? '').toLowerCase().replace(/\.(ps1|cmd|exe)$/, '')
        const postBody = JSON.stringify({
          run_id: runnerMeta.run_id,
          topic: runnerMeta.topic,
          exit_code: exitCode,
          stdout_tail: stdoutTail,
          wall_seconds: wallSeconds,
          user_initiated: userInitiated,
          adapter: runnerAdapter,
        })
        const doPost = () => fetch('http://127.0.0.1:8765/runner/terminal/result', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Pathly-Secret': getApiSecret() },
          body: postBody,
        })
        doPost().catch(() => setTimeout(() => doPost().catch(() => { /* give up */ }), 1000))
      } else {
        // Renderer-driven one-shot (editor / chat): project its telemetry to the project tier
        // so EVERY CLI the app spawns is observable, not just supervisor-driven runs. Cost +
        // tokens come from the parsed JSON result (null for non-json/codex → span-only). Best-effort.
        if (isOneShotTelem && telem) {
          const wallSeconds = (Date.now() - ptyStartedAt) / 1000
          const engineBase = path.basename(runnerArgv?.[0] ?? '').toLowerCase().replace(/\.(ps1|cmd|exe)$/, '')
          // claude reports cost + tokens + result in one JSON envelope; codex emits JSONL with
          // tokens but NEVER a dollar cost, and parseClaudeJsonResult can't read it — so a codex
          // one-shot would be stuck at $0 / 0 tokens. Parse the codex stream here for tokens (the
          // server estimates cost from them via db/pricing.py) + the final agent message.
          const codex = !oneShotParsed && engineBase.includes('codex')
            ? parseCodexResult((ptyOutput.get(tabId) ?? []).join(''))
            : null
          const usage = oneShotParsed?.usage
          const invBody = JSON.stringify({
            project_root: cwd,
            feature: telem.feature ?? '(project)',
            scope_tier: telem.scopeTier || 'project',
            run_id: tabId,
            label: telem.label || 'one-shot',
            agent_role: telem.role || engineBase || 'agent',
            adapter: engineBase || 'claude',
            // The server re-parses stdout_tail with the ONE robust parser (parse_result) and
            // prefers it; these client-parsed values are a fallback (spawn-parse-unification).
            stdout_tail: (ptyOutput.get(tabId) ?? []).join(''),
            cost_usd: oneShotParsed?.total_cost_usd ?? 0,
            tokens_in: usage?.input_tokens ?? codex?.tokens_in ?? 0,
            tokens_out: usage?.output_tokens ?? codex?.tokens_out ?? 0,
            tool_uses: streamState?.toolUses ?? 0,
            session_id: null,
            summary: (oneShotParsed?.result ?? codex?.result ?? '').slice(0, 2000),
            wall_seconds: wallSeconds,
          })
          const postInv = () => fetch('http://127.0.0.1:8765/db/invocation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Pathly-Secret': getApiSecret() },
            body: invBody,
          })
          postInv().catch(() => setTimeout(() => postInv().catch(() => { /* give up */ }), 1000))
        }
        ptyOutput.delete(tabId)
      }
      ptyWindows.delete(tabId)
    })

    activePtys.set(tabId, ptyProcess)
  })

  ipcMain.on('terminal:write', (event, tabId: string, data: string) => {
    // Phase 2: only allow the owning sender to write
    if (ptyOwners.get(tabId) !== event.sender.id) return
    const MAX_WRITE = 65536 // 64KB
    if (typeof data !== 'string' || data.length > MAX_WRITE) return
    activePtys.get(tabId)?.write(data)
  })

  ipcMain.handle('terminal:resize', (event, tabId: string, cols: number, rows: number) => {
    if (ptyOwners.get(tabId) !== event.sender.id) return
    const safeCols = Math.max(1, Math.min(500, Math.floor(Number(cols))))
    const safeRows = Math.max(1, Math.min(500, Math.floor(Number(rows))))
    activePtys.get(tabId)?.resize(safeCols, safeRows)
  })

  ipcMain.handle('terminal:kill', (event, tabId: string) => {
    const p = activePtys.get(tabId)
    if (p) {
      // A live PTY exists — enforce ownership before force-killing it.
      if (ptyOwners.get(tabId) !== event.sender.id) return
      if (runnerTabMeta.has(tabId)) {
        ptyKilledByRunner.add(tabId)
      }
      killPtyTree(p)
      activePtys.delete(tabId)
      ptyOwners.delete(tabId)
      ptyWindows.delete(tabId)
      releaseEngineSlot(tabId)
      return
    }
    // No PTY yet — the spawn is still queued (the UI shows it as optimistically running).
    // Cancel the queued slot so Stop works before the engine ever starts. Mirrors the
    // unguarded queue-control 'cancel' path (queued items carry no ptyOwners entry).
    releaseEngineSlot(tabId)
  })

  ipcMain.handle('terminal:queue-control', (_event, action: {
    type: 'pause' | 'resume' | 'cancel' | 'reorder' | 'set-caps'
    tabId?: string
    dir?: 'up' | 'down'
    caps?: Partial<{ global: number; headless: number; interactive: number }>
  }) => {
    switch (action.type) {
      case 'pause': queuePaused = true; broadcastSpawnState(); break
      case 'resume': queuePaused = false; promoteQueue(); broadcastSpawnState(); break
      case 'cancel': if (action.tabId) releaseEngineSlot(action.tabId); break // rejects the queued spawn
      case 'reorder': if (action.tabId && action.dir) reorderQueue(action.tabId, action.dir); break
      case 'set-caps':
        if (action.caps) {
          if (typeof action.caps.global === 'number') caps.global = Math.max(1, Math.min(32, Math.floor(action.caps.global)))
          if (typeof action.caps.headless === 'number') caps.headless = Math.max(1, Math.min(32, Math.floor(action.caps.headless)))
          if (typeof action.caps.interactive === 'number') caps.interactive = Math.max(1, Math.min(32, Math.floor(action.caps.interactive))) // min 1 — a 0 cap rejects every interactive spawn
          promoteQueue() // raising caps may unblock queued runs
          broadcastSpawnState()
        }
        break
    }
  })

  ipcMain.handle('terminal:preflight', async (_event, force?: boolean) => preflightEngines(force === true))

  // Synchronous snapshot of the LIVE gate engines (main-process-owned, so it survives a
  // renderer reload). Lets a renderer that reloaded mid-run re-verify a one-shot's liveness
  // authoritatively on mount — unlike the async `spawn:state` push, which can arrive empty
  // first and race a reconcile into false-clearing a run that is actually still alive.
  ipcMain.handle('terminal:get-engines', () => Array.from(activeEngines.values()))

  ipcMain.handle('terminal:register-runner', (_event, tabId: string, topic: string, runId: string, label?: string, category?: 'flow' | 'loop' | 'single') => {
    runnerTabMeta.set(tabId, { run_id: runId, topic, spawnedAt: Date.now(), label: label ?? tabId, category })
  })

  ipcMain.handle('terminal:popout', (event, tabId: string, label: string) => {
    if (ptyOwners.get(tabId) !== event.sender.id) return
    const ptyProcess = activePtys.get(tabId)
    if (!ptyProcess) throw new Error(`No PTY for tab ${tabId}`)

    const safeLabel = String(label ?? '').replace(/[\x00-\x1F\x7F]/g, '').slice(0, 100) || 'Terminal'

    const popupWin = new BrowserWindow({
      width: 900,
      height: 600,
      title: safeLabel,
      backgroundColor: '#1e1e2e',
      show: false,
      webPreferences: {
        preload: join(__dirname, '../preload/index.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false,
      },
    })

    popupWin.once('ready-to-show', () => {
      popupWin.show()
      popupWin.focus()
    })

    // Route PTY data to popup window and transfer ownership
    ptyWindows.set(tabId, popupWin)
    ptyOwners.set(tabId, popupWin.webContents.id)

    // Load same app with a ?terminal=<tabId> param so renderer shows popup mode
    if (app.isPackaged) {
      void popupWin.loadFile(join(__dirname, '../../renderer/index.html'), {
        query: { terminal: tabId, label },
      })
    } else {
      const devUrl = process.env.ELECTRON_RENDERER_URL ?? 'http://localhost:5173'
      void popupWin.loadURL(`${devUrl}?terminal=${encodeURIComponent(tabId)}&label=${encodeURIComponent(label)}`)
    }

    popupWin.on('closed', () => {
      const p = activePtys.get(tabId)
      if (p) { try { p.kill() } catch { /* ignore */ } activePtys.delete(tabId) }
      ptyOwners.delete(tabId)
      ptyWindows.delete(tabId)
    })
  })
}
