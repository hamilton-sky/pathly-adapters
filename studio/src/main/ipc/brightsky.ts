import { ipcMain, shell, BrowserWindow } from 'electron'
import http from 'http'
import { AddressInfo } from 'net'

const BRIGHTSKY_BASE_URL = 'https://brightsky-ai.onrender.com'

// Tracks whether an OAuth flow is already in progress so we never open two browser tabs.
let loginInProgress = false

export function registerBrightskyHandlers(win: BrowserWindow): void {
  ipcMain.handle('brightsky:login', async () => {
    if (loginInProgress) return

    loginInProgress = true

    try {
      // Use a local HTTP server to capture the OAuth callback code.
      // This approach works in both dev and packaged builds without
      // registering a custom protocol client, and avoids platform
      // differences between macOS (open-url) and Windows (second-instance).
      const code = await captureOAuthCode()
      await exchangeCode(code, win)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Auth failed'
      win.webContents.send('brightsky:token', { error: message })
    } finally {
      loginInProgress = false
    }
  })
}

function captureOAuthCode(): Promise<string> {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      const url = new URL(req.url ?? '/', `http://localhost`)
      const code = url.searchParams.get('code')

      if (!code) {
        res.writeHead(400, { 'Content-Type': 'text/html' })
        res.end('<html><body><p>Authentication cancelled.</p></body></html>')
        server.close()
        clearTimeout(timeout)
        reject(new Error('Auth cancelled'))
        return
      }

      res.writeHead(200, { 'Content-Type': 'text/html' })
      res.end(
        '<html><body><p>Authentication complete. You may close this tab.</p></body></html>'
      )

      server.close()
      clearTimeout(timeout)
      resolve(code)
    })

    server.listen(0, '127.0.0.1', () => {
      const port = (server.address() as AddressInfo).port
      const redirectUri = `http://127.0.0.1:${port}/callback`
      const authUrl = `${BRIGHTSKY_BASE_URL}/auth/google?redirect_uri=${encodeURIComponent(redirectUri)}`
      shell.openExternal(authUrl)
    })

    const timeout = setTimeout(() => {
      server.close()
      reject(new Error('Auth timed out'))
    }, 60_000)
  })
}

async function exchangeCode(code: string, win: BrowserWindow): Promise<void> {
  const response = await fetch(`${BRIGHTSKY_BASE_URL}/auth/exchange-code`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  })

  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText)
    throw new Error(`Exchange failed: ${text}`)
  }

  const data = (await response.json()) as {
    access_token: string
    refresh_token: string
    user: { id: string; email: string; displayName: string }
  }

  win.webContents.send('brightsky:token', {
    access_token: data.access_token,
    refresh_token: data.refresh_token,
    user: data.user,
  })
}
