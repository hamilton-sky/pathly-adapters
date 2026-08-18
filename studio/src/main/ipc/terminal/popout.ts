// Detach one terminal tab into its own BrowserWindow.
//
// Purely a window-management concern — it transfers PTY ownership to the popup and hands it
// back on close. Kept out of the spawn path so nothing there has to reason about windows.

import { BrowserWindow, app, type IpcMainInvokeEvent } from 'electron'
import { join } from 'path'
import { activePtys, ptyOwners, ptyWindows } from './ptyRegistry'

export function openTerminalPopout(event: IpcMainInvokeEvent, tabId: string, label: string): void {
  if (ptyOwners.get(tabId) !== event.sender.id) return
  const ptyProcess = activePtys.get(tabId)
  if (!ptyProcess) throw new Error(`No PTY for tab ${tabId}`)

  const safeLabel = String(label ?? '').replace(/[\x00-\x1F\x7F]/g, '').slice(0, 100) || 'Terminal'

  const popupWin = new BrowserWindow({
    width: 900,
    height: 600,
    title: safeLabel,
    backgroundColor: '#1e1e2e',
    show: false,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })

  popupWin.once('ready-to-show', () => {
    popupWin.show()
    popupWin.focus()
  })

  // Route PTY data to popup window and transfer ownership
  ptyWindows.set(tabId, popupWin)
  ptyOwners.set(tabId, popupWin.webContents.id)

  // Load same app with a ?terminal=<tabId> param so renderer shows popup mode
  if (app.isPackaged) {
    void popupWin.loadFile(join(__dirname, '../../renderer/index.html'), {
      query: { terminal: tabId, label },
    })
  } else {
    const devUrl = process.env.ELECTRON_RENDERER_URL ?? 'http://localhost:5173'
    void popupWin.loadURL(`${devUrl}?terminal=${encodeURIComponent(tabId)}&label=${encodeURIComponent(label)}`)
  }

  popupWin.on('closed', () => {
    const p = activePtys.get(tabId)
    if (p) { try { p.kill() } catch { /* ignore */ } activePtys.delete(tabId) }
    ptyOwners.delete(tabId)
    ptyWindows.delete(tabId)
  })
}
