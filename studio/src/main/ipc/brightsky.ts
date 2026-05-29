import { ipcMain, BrowserWindow } from 'electron'

const BRIGHTSKY_BASE_URL = 'https://brightsky-ai.onrender.com'

// The Brightsky backend always redirects to http://localhost:3000/auth/success?code=xxx
// after a successful Google OAuth flow (hardcoded in auth.controller.ts).
// We intercept this via a BrowserWindow's will-navigate event — no local HTTP server needed.
const OAUTH_SUCCESS_PREFIX_1 = 'http://localhost:3000/auth/success'
const OAUTH_SUCCESS_PREFIX_2 = 'http://127.0.0.1:3000/auth/success'

// Tracks whether an OAuth flow is already in progress so we never open two auth windows.
let loginInProgress = false

export function registerBrightskyHandlers(win: BrowserWindow): void {
  ipcMain.handle('brightsky:login', async () => {
    if (loginInProgress) return

    loginInProgress = true

    try {
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
    const authWin = new BrowserWindow({
      width: 500,
      height: 650,
      title: 'Sign in with Google',
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
      },
    })

    let settled = false

    function settle(fn: () => void): void {
      if (settled) return
      settled = true
      clearTimeout(timeout)
      // Destroy after microtask so the will-navigate handler can return first
      setImmediate(() => {
        if (!authWin.isDestroyed()) authWin.destroy()
      })
      fn()
    }

    // Intercept the redirect before it loads — extract the code without hitting localhost:3000
    authWin.webContents.on('will-navigate', (_event, url) => {
      if (url.startsWith(OAUTH_SUCCESS_PREFIX_1) || url.startsWith(OAUTH_SUCCESS_PREFIX_2)) {
        _event.preventDefault()
        const code = new URL(url).searchParams.get('code')
        if (code) {
          settle(() => resolve(code))
        } else {
          settle(() => reject(new Error('Auth cancelled — no code in callback URL')))
        }
      }
    })

    // Same intercept for did-navigate (fires if will-navigate was not prevented in time)
    authWin.webContents.on('did-navigate', (_event, url) => {
      if (url.startsWith(OAUTH_SUCCESS_PREFIX_1) || url.startsWith(OAUTH_SUCCESS_PREFIX_2)) {
        const code = new URL(url).searchParams.get('code')
        if (code) {
          settle(() => resolve(code))
        } else {
          settle(() => reject(new Error('Auth cancelled — no code in callback URL')))
        }
      }
    })

    // User closed the window without completing auth
    authWin.on('closed', () => {
      settle(() => reject(new Error('Auth window closed')))
    })

    const timeout = setTimeout(() => {
      settle(() => reject(new Error('Auth timed out')))
    }, 60_000)

    authWin.loadURL(`${BRIGHTSKY_BASE_URL}/auth/google`)
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
