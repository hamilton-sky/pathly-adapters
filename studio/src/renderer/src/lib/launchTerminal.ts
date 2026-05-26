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
