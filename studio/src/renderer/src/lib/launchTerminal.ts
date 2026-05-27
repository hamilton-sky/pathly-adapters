import type { TerminalTab } from '../types/terminal'

export type TerminalKind = NonNullable<TerminalTab['kind']>

export interface LaunchTerminalParams {
  command: string | undefined
  label: string
  pane: 'left' | 'right'
  projectPath: string
  open: boolean
  toggle: () => void
  addTab: (id: string, label: string, pane: 'left' | 'right', kind: TerminalKind) => void
}

export async function launchTerminal(params: LaunchTerminalParams): Promise<void> {
  const { command, label, pane, projectPath, open, toggle, addTab } = params
  if (!open) toggle()
  const id = crypto.randomUUID()
  const kind: TerminalKind = command === 'claude' ? 'claude' : command === 'codex' ? 'codex' : 'shell'
  addTab(id, label, pane, kind)
  await window.pathly?.terminal?.spawn(id, projectPath, command)
}

export async function writeToTerminal(
  kind: 'claude' | 'codex' | 'shell',
  command: string,
  projectPath: string,
  tabs: TerminalTab[],
  addTab: (id: string, label: string, pane?: 'left' | 'right', kind?: TerminalTab['kind']) => void,
  open: boolean,
  toggle: () => void
): Promise<string> {
  const sanitized = command.replace(/[;&|><]/g, '')

  const existingTab = tabs.find((tab) => tab.kind === kind)
  let tabId: string

  if (existingTab) {
    tabId = existingTab.id
  } else {
    tabId = crypto.randomUUID()
    if (kind === 'shell') {
      addTab(tabId, 'Shell', 'left', 'shell')
      await window.pathly?.terminal?.spawn(tabId, projectPath, undefined)
    } else {
      addTab(tabId, kind === 'claude' ? 'claude' : 'codex', 'left', kind)
      await window.pathly?.terminal?.spawn(tabId, projectPath, kind)
    }
  }

  if (!open) toggle()

  // If we just spawned a new tab, wait for the first PTY output before writing.
  // Data-based wait is more reliable than a fixed sleep on slow machines.
  // Falls back to 4s so we never hang forever.
  if (!existingTab) {
    await new Promise<void>((resolve) => {
      const fallback = setTimeout(resolve, 4000)
      const unsub = window.pathly?.terminal?.onData(tabId, () => {
        clearTimeout(fallback)
        unsub?.()
        // Small pause after first output so readline is fully ready
        setTimeout(resolve, 300)
      })
      if (!unsub) {
        clearTimeout(fallback)
        resolve()
      }
    })
  }

  // Build the command text and the Enter sequence separately.
  // Two-write pattern: text first, then Enter — this matches how xterm.js sends
  // keystrokes one-at-a-time and avoids readline swallowing the newline on Windows ConPTY.
  let cmdText: string
  if (kind === 'claude') {
    cmdText = sanitized
  } else if (kind === 'shell') {
    cmdText = sanitized
  } else {
    cmdText = 'Use Pathly ' + sanitized.replace(/^\/pathly\s*/, '')
  }

  window.pathly?.terminal?.write(tabId, cmdText)

  // Small pause so readline buffers the text before seeing Enter
  await new Promise<void>((r) => setTimeout(r, 80))

  // '\r\n' covers Windows ConPTY (needs CR+LF), and '\r' alone is sufficient for
  // Unix PTY — sending both is safe and universally triggers readline execution.
  window.pathly?.terminal?.write(tabId, '\r\n')

  return tabId
}
