import { shell, type BrowserWindow } from 'electron'
import { navigationDecision, windowOpenDecision } from './navigationPolicy'

/**
 * Keep an app window (one loaded WITH the preload) on the app. Links in rendered
 * Markdown open in the system browser; nothing can navigate the window, or open a new
 * one, onto a page that would inherit window.pathly. Call on every preload window.
 */
export function guardAppWindow(win: BrowserWindow): void {
  const contents = win.webContents

  contents.setWindowOpenHandler(({ url }) => {
    if (windowOpenDecision(url) === 'external') void shell.openExternal(url)
    return { action: 'deny' }
  })

  contents.on('will-navigate', (event, url) => {
    const decision = navigationDecision(contents.getURL(), url)
    if (decision === 'allow') return
    event.preventDefault()
    if (decision === 'external') void shell.openExternal(url)
  })
}
