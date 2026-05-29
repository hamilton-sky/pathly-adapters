import type { TerminalTab } from '../types/terminal'

export type TerminalKind = NonNullable<TerminalTab['kind']>

export interface LaunchTerminalParams {
  command: string | undefined
  label: string
  pane: 'left' | 'right'
  projectPath: string
  open: boolean
  toggle: () => void
  addTab: (id: string, label: string, pane: 'left' | 'right', kind: TerminalKind, plan?: string, stage?: string) => void
  plan?: string
  stage?: string
}

export async function launchTerminal(params: LaunchTerminalParams): Promise<void> {
  const { command, label, pane, projectPath, open, toggle, addTab, plan, stage } = params
  if (!open) toggle()
  const id = crypto.randomUUID()
  const kind: TerminalKind = command === 'claude' ? 'claude' : command === 'codex' ? 'codex' : 'shell'
  addTab(id, label, pane, kind, plan, stage)
  await window.pathly?.terminal?.spawn(id, projectPath, command)
}

export async function writeToTerminal(
  kind: 'claude' | 'codex' | 'shell',
  command: string,
  projectPath: string,
  tabs: TerminalTab[],
  addTab: (id: string, label: string, pane?: 'left' | 'right', kind?: TerminalTab['kind'], plan?: string, stage?: string) => void,
  open: boolean,
  toggle: () => void,
  rememberTabForKind: (kind: TerminalKind, id: string) => void,
  openTab: (id: string) => void,
  options: { revealFullTerminal?: boolean; plan?: string; stage?: string } = {}
): Promise<string> {
  const revealFullTerminal = options.revealFullTerminal ?? true
  const { plan, stage } = options
  const sanitized = command.replace(/[;&|><]/g, '')

  const existingTab = tabs.find((tab) => tab.kind === kind)
  let tabId: string

  if (existingTab) {
    tabId = existingTab.id
  } else {
    tabId = crypto.randomUUID()
    if (kind === 'shell') {
      addTab(tabId, 'Shell', 'left', 'shell', plan, stage)
      await window.pathly?.terminal?.spawn(tabId, projectPath, undefined)
    } else {
      addTab(tabId, kind === 'claude' ? 'claude' : 'codex', 'left', kind, plan, stage)
      await window.pathly?.terminal?.spawn(tabId, projectPath, kind)
    }
  }

  rememberTabForKind(kind, tabId)
  if (revealFullTerminal) {
    if (!open) toggle()
    openTab(tabId)
  }

  // If we just spawned a new tab, wait for the CLI prompt before writing.
  // We scan accumulated PTY output for the ready prompt ('> ' for claude/codex,
  // '$ ' or '# ' for shell) so we write only when readline is actually listening.
  // Falls back to 5s so we never hang forever.
  if (!existingTab) {
    await new Promise<void>((resolve) => {
      const fallback = setTimeout(resolve, 5000)
      let buf = ''
      const promptPatterns = kind === 'shell' ? ['$ ', '# ', '> '] : ['> ']
      const unsub = window.pathly?.terminal?.onData(tabId, (data: string) => {
        // Strip ANSI escape codes before scanning for the prompt
        buf += data.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '').replace(/\x1b\][\s\S]*?(?:\x07|\x1b\\)/g, '')
        if (promptPatterns.some((p) => buf.includes(p))) {
          clearTimeout(fallback)
          unsub?.()
          resolve()
        }
      })
      if (!unsub) {
        clearTimeout(fallback)
        resolve()
      }
    })
  }

  let cmdText: string
  if (kind === 'claude') {
    cmdText = sanitized
  } else if (kind === 'shell') {
    cmdText = sanitized
  } else {
    cmdText = 'Use Pathly ' + sanitized.replace(/^\/pathly\s*/, '')
  }

  // Send command + Enter as one atomic PTY write so readline processes them together.
  // Splitting into two writes with a delay was racy — the Enter sometimes arrived
  // while Claude Code was still flushing startup output, confusing readline.
  window.pathly?.terminal?.write(tabId, cmdText + '\r')

  return tabId
}
