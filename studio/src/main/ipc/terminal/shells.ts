// Shell + launcher resolution for every PTY the app spawns.
//
// One concern: given a tab's command or runner argv, produce the (shell, args) pair to hand
// node-pty — including Windows temp-script encoding, the PowerShell UTF-8 preamble, and
// resolving a bare engine name to an absolute launcher so a mid-flight `npm i -g` self-update
// cannot kill a running stage with CommandNotFound.
//
// Leaf module: imports nothing from the rest of the terminal subsystem except logging.

import { execFile } from 'child_process'
import { join } from 'path'
import * as fs from 'fs'
import * as os from 'os'
import * as path from 'path'
import { app } from 'electron'
import { slog } from './log'

/** A spawn cwd must resolve inside the user's home — the outer guard on every PTY we start. */
export function isValidCwd(dir: string): boolean {
  try {
    const real = fs.realpathSync(dir)
    const home = path.resolve(app.getPath('home'))
    return real.startsWith(home + path.sep) || real === home
  } catch {
    return false
  }
}

export const ALLOWED_SHELLS = new Set(['bash', 'zsh', 'sh', 'pwsh', 'powershell.exe', 'cmd.exe', 'claude', 'codex', 'agy'])

// Engines whose launcher we resolve to an absolute path before spawning. A Claude/Codex
// self-update rewrites the PATH shim (`npm i -g`) or moves a versioned install dir; if the
// runner spawns the bare name mid-swap, PowerShell throws CommandNotFound and the flow stage
// dies. Resolving an absolute launcher per spawn (and briefly waiting one out if it's mid-swap)
// keeps in-flight stages alive across an update.
export const ENGINE_INSTALL_HINTS: Record<string, string> = {
  claude: 'npm install -g @anthropic-ai/claude-code',
  codex: 'npm install -g @openai/codex',
  agy: 'npm install -g @google/antigravity-cli',
}

export const RESOLVABLE_ENGINES_LIST = ['claude', 'codex', 'agy'] as const
export const RESOLVABLE_ENGINES = new Set<string>(RESOLVABLE_ENGINES_LIST)

const delay = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms))

/** Resolve an absolute path to a CLI engine's launcher, checking known install locations
 *  first and falling back to the bare name (PATH lookup). Prefers the npm `.ps1` shim so
 *  PowerShell arg-passing matches the previous bare-name behavior exactly (no regression). */
export function resolveEnginePath(engine: string): string {
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
export function enrichedPath(): string {
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
export function isOnPath(engine: string): Promise<boolean> {
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
export async function resolveEngineLauncher(engine: string): Promise<string> {
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

/** Normalize a launcher (bare 'claude' or a resolved '…\claude.ps1') to a CliAdapter id so the
 *  monitor badges it consistently regardless of how it was spawned. */
export function adapterIdFromLauncher(launcher: string): string {
  const base = path.basename(launcher).toLowerCase().replace(/\.(ps1|cmd|exe)$/, '')
  if (base.startsWith('claude')) return 'claude'
  if (base.startsWith('codex')) return 'codex'
  if (base.startsWith('agy') || base.startsWith('antigravity')) return 'antigravity'
  if (base.startsWith('copilot')) return 'copilot'
  return base || 'claude'
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

export function resolveShell(command: string | undefined): { shell: string; args: string[] } {
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
export function resolveInteractiveShell(argv: string[]): { shell: string; args: string[] } {
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
export function resolveRunnerShell(argv: string[]): { shell: string; args: string[]; tempScript?: string } {
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
