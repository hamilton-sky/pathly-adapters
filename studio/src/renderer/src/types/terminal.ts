export interface TerminalTab {
  id: string
  numericId: number
  label: string
  pane: 'left' | 'right'
  kind?: 'shell' | 'claude' | 'codex' | 'antigravity'
  status?: 'idle' | 'running' | 'error' | 'done'
  /** Epoch ms when status first became 'running' — used by CliMonitorBar elapsed timer. */
  startedAt?: number
  plan?: string
  stage?: string
  runnerOwned?: boolean
}
