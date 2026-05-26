export interface TerminalTab {
  id: string
  label: string
  pane: 'left' | 'right'
  kind?: 'shell' | 'claude' | 'codex'
  status?: 'idle' | 'running' | 'error' | 'done'
}
