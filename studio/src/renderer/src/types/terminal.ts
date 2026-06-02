export interface TerminalTab {
  id: string
  numericId: number
  label: string
  pane: 'left' | 'right'
  kind?: 'shell' | 'claude' | 'codex' | 'antigravity'
  status?: 'idle' | 'running' | 'error' | 'done'
  plan?: string
  stage?: string
  runnerOwned?: boolean
}
