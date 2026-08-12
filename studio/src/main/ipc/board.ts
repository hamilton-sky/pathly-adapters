import { ipcMain, BrowserWindow, app } from 'electron'
import { join } from 'path'

interface BoardPopoutOpts {
  scope: 'feature' | 'project' | 'global'
  /** Feature id for a feature board; the active main-feature for project/global. */
  feature: string
  /** Project root — projectStore does not persist it, so the opener passes it. */
  project: string
  /** Display name for the window title + header strip. */
  name: string
}

// Tear a single board off into its own OS window. It loads the same renderer with
// a `?board=…` query param (App.tsx renders <PopoutBoard> for it) and connects to
// the same local Pathly server (127.0.0.1:8765) independently — so it stays live.
// Mirrors the terminal:popout handler in ipc/terminal.ts.
export function registerBoardHandlers(): void {
  ipcMain.handle('board:popout', (_event, opts: BoardPopoutOpts) => {
    const scope = String(opts?.scope ?? '')
    if (scope !== 'feature' && scope !== 'project' && scope !== 'global') {
      throw new Error(`Invalid board scope: ${scope}`)
    }
    const feature = String(opts?.feature ?? '')
    const project = String(opts?.project ?? '')
    const safeName =
      String(opts?.name ?? '').replace(/[\x00-\x1F\x7F]/g, '').slice(0, 120) || 'Board'

    const win = new BrowserWindow({
      width: 720,
      height: 820,
      minWidth: 340,
      minHeight: 420,
      title: safeName,
      backgroundColor: '#111827', // tokens.css :root --bg-base — repaints on theme apply
      show: false,
      webPreferences: {
        preload: join(__dirname, '../preload/index.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false,
        // Keep the board's SSE / poll sockets alive while the window is occluded —
        // same rationale as the main window (see index.ts createWindow).
        backgroundThrottling: false,
      },
    })
    win.setMenu(null)
    win.once('ready-to-show', () => { win.show(); win.focus() })

    const query = { board: scope, feature, project, name: safeName }
    if (app.isPackaged) {
      void win.loadFile(join(__dirname, '../../renderer/index.html'), { query })
    } else {
      const devUrl = process.env.ELECTRON_RENDERER_URL ?? 'http://localhost:5173'
      void win.loadURL(`${devUrl}?${new URLSearchParams(query).toString()}`)
    }
  })
}
