import type { TerminalTab } from '../store/terminalStore'

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
  kind: 'claude' | 'codex',
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
    addTab(tabId, kind === 'claude' ? 'claude' : 'codex', 'left', kind)
    await window.pathly?.terminal?.spawn(tabId, projectPath)
  }

  if (!open) toggle()

  if (kind === 'claude') {
    window.pathly?.terminal?.write(tabId, '/pathly ' + sanitized + '\n')
  } else {
    window.pathly?.terminal?.write(tabId, 'Use Pathly ' + sanitized + '\n')
  }

  return tabId
}
