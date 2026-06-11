import * as fs from 'fs'
import * as path from 'path'
import * as os from 'os'
import * as crypto from 'crypto'

let _apiSecret = ''
let _apiBase = 'http://127.0.0.1:8765'

function _loadOrCreateSecret(): string {
  const secretFile = path.join(os.homedir(), '.pathly', 'server_secret.txt')
  const dir = path.dirname(secretFile)
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
  if (fs.existsSync(secretFile)) {
    const val = fs.readFileSync(secretFile, 'utf8').trim()
    if (val) return val
  }
  const val = crypto.randomBytes(32).toString('hex')
  fs.writeFileSync(secretFile, val, { encoding: 'utf8', mode: 0o600 })
  return val
}

export function initApiConfig(): void {
  const port = process.env['PATHLY_FSM_HTTP_PORT'] ?? '8765'
  _apiBase = `http://127.0.0.1:${port}`
  _apiSecret = process.env['PATHLY_API_SECRET'] ?? _loadOrCreateSecret()
  // Make it available to the FSM server via inherited env
  process.env['PATHLY_API_SECRET'] = _apiSecret
}

export function getApiSecret(): string { return _apiSecret }
export function getApiBase(): string { return _apiBase }

export function apiHeaders(): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    'X-Pathly-Secret': _apiSecret,
  }
}
