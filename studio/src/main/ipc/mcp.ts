import { ipcMain } from 'electron'

// mcp_server.py does not yet exist — stubs return false/null until mcp-fsm-driver is complete.
export function registerMcpHandlers(): void {
  ipcMain.handle('mcp:ping', async () => {
    console.warn('[mcp] mcp_server.py not available — using file-watch fallback')
    return false
  })

  ipcMain.handle('mcp:state', async () => null)
}
