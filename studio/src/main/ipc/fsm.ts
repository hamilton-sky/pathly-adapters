import { ipcMain } from 'electron'

const FSM_BASE = `http://127.0.0.1:${process.env['PATHLY_FSM_HTTP_PORT'] ?? '8765'}`

export function registerFsmHandlers(): void {
  ipcMain.handle('fsm:ping', async (): Promise<boolean> => {
    try {
      const res = await fetch(`${FSM_BASE}/health`, { signal: AbortSignal.timeout(500) })
      return res.ok
    } catch {
      return false
    }
  })

  ipcMain.handle('fsm:state', async (_event, topic: string, projectRoot: string, flow: string = 'team') => {
    try {
      const res = await fetch(`${FSM_BASE}/next_action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ flow, topic, project_root: projectRoot }),
        signal: AbortSignal.timeout(2000),
      })
      return res.ok ? res.json() : null
    } catch {
      return null
    }
  })
}
