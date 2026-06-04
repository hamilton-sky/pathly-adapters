import { ipcMain, BrowserWindow, app } from 'electron'
import { join } from 'path'
import * as fs from 'fs'
import * as os from 'os'
import * as path from 'path'

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
// Maps tabId → accumulated output lines for runner result reporting
const ptyOutput = new Map<string, string[]>()
// Maps tabId → runner metadata registered before spawn
const runnerTabMeta = new Map<string, { run_id: string; topic: string; spawnedAt: number; label: string }>()
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

/** Resolve the absolute path to agy.exe — checks known install location first, falls back to PATH. */
function resolveAgyPath(): string {
  if (process.platform === 'win32') {
    const localAppData = process.env.LOCALAPPDATA ?? ''
    const knownPath = join(localAppData, 'agy', 'bin', 'agy.exe')
    if (fs.existsSync(knownPath)) return knownPath
    // Also check npm bin (our fallback copy)
    const appData = process.env.APPDATA ?? ''
    const npmPath = join(appData, 'npm', 'agy.exe')
    if (fs.existsSync(npmPath)) return npmPath
  }
  return 'agy'  // rely on PATH on non-Windows or if known paths don't exist
}

function resolveShell(command: string | undefined): { shell: string; args: string[] } {
  if (process.platform !== 'win32') {
    if (command === 'claude' || command === 'codex' || command === 'agy') {
      return { shell: 'bash', args: ['-c', `exec ${command}`] }
    }
    return { shell: command ?? 'bash', args: [] }
  }
  if (command === 'claude') return { shell: 'powershell.exe', args: ['-NoExit', '-Command', 'claude'] }
  if (command === 'codex')  return { shell: 'powershell.exe', args: ['-NoExit', '-Command', 'codex'] }
  if (command === 'agy') {
    const agyExe = resolveAgyPath()
    return { shell: 'powershell.exe', args: ['-NoExit', '-Command', `& '${agyExe}'`] }
  }
  return { shell: 'powershell.exe', args: [] }
}

interface ClaudeJsonResult {
  result: string
  total_cost_usd: number
  duration_ms: number
  usage: {
    input_tokens: number
    output_tokens: number
    cache_read_input_tokens: number
    cache_creation_input_tokens: number
  }
  permission_denials?: Array<{
    tool_name: string
    tool_use_id?: string
    tool_input?: unknown
  }>
}

/** Extract the balanced { … } object starting at position 0.
 *  Handles string escaping so embedded braces inside strings are ignored. */
function extractBalancedJson(s: string): string | null {
  let depth = 0
  let inString = false
  let escape = false
  for (let i = 0; i < s.length; i++) {
    const c = s[i]
    if (escape) { escape = false; continue }
    if (c === '\\' && inString) { escape = true; continue }
    if (c === '"') { inString = !inString; continue }
    if (inString) continue
    if (c === '{') depth++
    else if (c === '}') {
      depth--
      if (depth === 0) return s.slice(0, i + 1)
    }
  }
  return null
}

function parseClaudeJsonResult(stdout: string): ClaudeJsonResult | null {
  // Strip ANSI escape sequences
  const stripped = stdout.replace(/\x1b\[[0-9;]*[mGKHFABCDJsu]/g, '')

  // Claude emits {"type":"result",...} as compact JSON on one logical line, but
  // the PTY terminal wraps it at the column width with \r\n sequences.  We find
  // the marker, walk back to the opening brace, flatten the PTY wrapping in
  // that section, then extract a balanced { } object before parsing.
  const idxA = stripped.lastIndexOf('"type":"result"')
  const idxB = stripped.lastIndexOf('"type": "result"')
  const markerIdx = Math.max(idxA, idxB)
  if (markerIdx === -1) return null

  // Walk backward to find the opening brace for this object
  let start = markerIdx
  while (start > 0 && stripped[start] !== '{') start--
  if (stripped[start] !== '{') return null

  // Flatten PTY-introduced \r\n wrapping within the JSON section only
  const flat = stripped.slice(start).replace(/\r\n/g, '').replace(/\r/g, '')
  const json = extractBalancedJson(flat)
  if (!json) return null

  try {
    const parsed = JSON.parse(json) as { type?: string } & ClaudeJsonResult
    if (parsed.type === 'result') return parsed
  } catch { /* malformed */ }
  return null
}

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
  return { shell: 'powershell.exe', args: ['-NoExit', '-Command', `& ${tokens}`] }
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

  const varDecls: string[] = []
  const callTokens: string[] = []

  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    // Use a here-string for any arg that has newlines or single-quote variants.
    // Here-strings only end at `'@` at column 0 — virtually impossible in prompt content.
    if (/['''\r\n]/.test(a)) {
      const varName = `$a${i}`
      // PowerShell requires a newline immediately before the closing marker.
      const body = a.endsWith('\n') ? a : `${a}\n`
      varDecls.push(`${varName} = @'\n${body}'@`)
      callTokens.push(varName)
    } else {
      callTokens.push(`'${a}'`)
    }
  }

  const scriptLines = [...varDecls, `& ${callTokens.join(' ')}`].join('\n') + '\r\n'
  fs.writeFileSync(tmpScript, Buffer.concat([bom, Buffer.from(scriptLines, 'utf8')]))
  return {
    shell: 'powershell.exe',
    args: ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', tmpScript],
    tempScript: tmpScript,
  }
}

export function killAllPtys(): void {
  activePtys.forEach((p) => { try { p.kill() } catch { /* ignore */ } })
  runnerScripts.forEach((scriptPath) => { try { fs.unlinkSync(scriptPath) } catch { /* ignore */ } })
  activePtys.clear()
  ptyWindows.clear()
  ptyOwners.clear()
  ptyOutput.clear()
  runnerTabMeta.clear()
  ptyKilledByRunner.clear()
  runnerScripts.clear()
}

export function registerTerminalHandlers(win: BrowserWindow): void {
  ipcMain.handle('terminal:spawn', (event, tabId: string, cwd: string, command?: string, runnerArgv?: string[], initialInput?: string) => {
    if (!pty) throw new Error('node-pty is not available')
    if (activePtys.has(tabId)) {
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
      if (initialInput) {
        // Interactive runner: open the CLI normally so the user can keep chatting after
        ;({ shell, args: shellArgs } = resolveInteractiveShell(runnerArgv))
      } else {
        // Headless runner: PTY exits when agent finishes
        ;({ shell, args: shellArgs, tempScript } = resolveRunnerShell(runnerArgv))
      }
      if (tempScript) runnerScripts.set(tabId, tempScript)
    } else {
      // Manual terminal tab: just the adapter name
      if (command !== undefined && !ALLOWED_SHELLS.has(command)) {
        throw new Error('Shell not allowed: ' + command)
      }
      ;({ shell, args: shellArgs } = resolveShell(command))
    }

    const ptyProcess = pty.spawn(shell, shellArgs, {
      name: 'xterm-color',
      cols: 80,
      rows: 24,
      cwd: cwd,
      env: process.env as Record<string, string>,
    })

    // Default target window is the main window
    ptyWindows.set(tabId, win)
    // Phase 2: record ownership
    ptyOwners.set(tabId, event.sender.id)

    // Inject the stage prompt once Claude's UI has finished rendering.
    // Use bracketed paste (\x1b[200~...\x1b[201~) so multi-line content is treated
    // as a single paste rather than one submit per line.
    if (initialInput) {
      let injected = false
      let debounce: ReturnType<typeof setTimeout> | null = null
      const injectPrompt = (): void => {
        if (injected) return
        injected = true
        ptyProcess.write('\x1b[200~' + initialInput + '\x1b[201~\r')
      }
      const unsubscribe = ptyProcess.onData(() => {
        if (injected) return
        if (debounce) clearTimeout(debounce)
        debounce = setTimeout(() => {
          injectPrompt()
          unsubscribe.dispose()
        }, 800)
      })
    }

    ptyProcess.onData((data: string) => {
      sendToWindow(tabId, `terminal:data:${tabId}`, data)
      if (runnerTabMeta.has(tabId)) {
        const lines = ptyOutput.get(tabId) ?? []
        lines.push(data)
        if (lines.length > 500) lines.splice(0, lines.length - 500)
        ptyOutput.set(tabId, lines)
      }
    })

    ptyProcess.onExit(({ exitCode }) => {
      activePtys.delete(tabId)
      ptyOwners.delete(tabId)
      const scriptPath = runnerScripts.get(tabId)
      if (scriptPath) { runnerScripts.delete(tabId); try { fs.unlinkSync(scriptPath) } catch { /* ignore */ } }
      sendToWindow(tabId, 'terminal:exit', tabId)
      const meta = runnerTabMeta.get(tabId)
      if (meta) {
        const userInitiated = ptyKilledByRunner.has(tabId)
        const stdoutTail = (ptyOutput.get(tabId) ?? []).join('')
        // Parse the claude --output-format=json result
        const stageResult = parseClaudeJsonResult(stdoutTail)
        if (stageResult) {
          sendToWindow(tabId, 'terminal:stage-result', tabId, stageResult)
        }
        const wallSeconds = (Date.now() - meta.spawnedAt) / 1000
        runnerTabMeta.delete(tabId)
        ptyOutput.delete(tabId)
        ptyKilledByRunner.delete(tabId)
        const label = meta.label || tabId
        const banner = exitCode === 0
          ? `\r\n\x1b[2m──\x1b[0m \x1b[1;32m${label} DONE\x1b[0m \x1b[2m──────────────────────────────\x1b[0m\r\n`
          : `\r\n\x1b[2m──\x1b[0m \x1b[1;31m${label} ABORTED\x1b[0m \x1b[2m──────────────────────────────\x1b[0m\r\n`
        sendToWindow(tabId, `terminal:data:${tabId}`, banner)
        const postBody = JSON.stringify({
          run_id: meta.run_id,
          topic: meta.topic,
          exit_code: exitCode,
          stdout_tail: stdoutTail,
          wall_seconds: wallSeconds,
          user_initiated: userInitiated,
        })
        const doPost = () => fetch('http://127.0.0.1:8765/runner/terminal/result', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: postBody,
        })
        doPost().catch(() => setTimeout(() => doPost().catch(() => { /* give up */ }), 1000))
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
    if (ptyOwners.get(tabId) !== event.sender.id) return
    const p = activePtys.get(tabId)
    if (p) {
      if (runnerTabMeta.has(tabId)) {
        ptyKilledByRunner.add(tabId)
      }
      p.kill()
      activePtys.delete(tabId)
      ptyOwners.delete(tabId)
      ptyWindows.delete(tabId)
    }
  })

  ipcMain.handle('terminal:register-runner', (_event, tabId: string, topic: string, runId: string, label?: string) => {
    runnerTabMeta.set(tabId, { run_id: runId, topic, spawnedAt: Date.now(), label: label ?? tabId })
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
