// The PTY registry — the per-tab maps that ARE a live terminal, plus teardown.
//
// One concern: what exists right now, keyed by tabId (the process, its target window, its
// owning renderer, its rolling output tail, its runner metadata, its temp script). Everything
// else in this subsystem reads through here rather than keeping its own copy.

import { BrowserWindow } from 'electron'
import { execFile } from 'child_process'
import * as fs from 'fs'
import * as os from 'os'
import * as path from 'path'
import { resetGateState } from './spawnGate'

export const activePtys = new Map<string, import('node-pty').IPty>()
// Maps tabId → the BrowserWindow that should receive PTY data for that tab
export const ptyWindows = new Map<string, BrowserWindow>()
// Maps tabId → webContentsId of the sender that spawned it
export const ptyOwners = new Map<string, number>()
// Maps tabId → accumulated output lines for runner result reporting + failure-reason tails
export const ptyOutput = new Map<string, string[]>()

// Maps tabId → runner metadata registered before spawn
export const runnerTabMeta = new Map<string, { run_id: string; topic: string; spawnedAt: number; label: string; category?: 'flow' | 'loop' | 'single' }>()
// Tracks tabs killed by the user (not by the runner exiting naturally)
export const ptyKilledByRunner = new Set<string>()
// Tabs the user explicitly stopped — suppresses the transient-failure retry, so Stop always
// Maps tabId → temp .ps1 script path created for that runner (Windows only)
export const runnerScripts = new Map<string, string>()

// Strip ANSI and return the last few meaningful output lines — used to surface WHY a run
// failed (rate limit, auth error, the agent's final message) instead of a generic message.
export function tailMeaningfulOutput(chunks: string[]): string {
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

export function sendToWindow(tabId: string, channel: string, ...args: unknown[]): void {
  const win = ptyWindows.get(tabId)
  if (win && !win.isDestroyed()) {
    win.webContents.send(channel, ...args)
  }
}

/** Force-terminate a PTY and its child process tree.
 *  On Windows the runner shell is `powershell.exe -File …ps1`, which spawns the
 *  real engine (`claude`/`codex`) as a child. node-pty's kill() only ends the
 *  PowerShell host, leaving the engine running — `taskkill /T` reaps the tree. */
export function killPtyTree(p: import('node-pty').IPty): void {
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
  resetGateState()
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
