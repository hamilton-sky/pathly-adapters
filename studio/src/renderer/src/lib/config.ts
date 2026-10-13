// From the preload (PATHLY_FSM_HTTP_PORT), so Studio can run against a server on a port other
// than 8765. Falls back to the default where there is no preload (vitest, a plain browser).
export const PATHLY_API_BASE: string =
  (typeof window !== 'undefined' && window.pathly?.shell?.apiBase) || 'http://127.0.0.1:8765'

let _cachedSecret: string | null = null

async function _getSecret(): Promise<string> {
  if (_cachedSecret !== null) return _cachedSecret
  try {
    const cfg = await window.pathly.shell.apiConfig()
    _cachedSecret = cfg.secret
  } catch {
    _cachedSecret = ''
  }
  return _cachedSecret!
}

/** Fetch wrapper that automatically prepends PATHLY_API_BASE and injects X-Pathly-Secret. */
export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const secret = await _getSecret()
  const existing = (init?.headers ?? {}) as Record<string, string>
  const headers: Record<string, string> = { 'X-Pathly-Secret': secret, ...existing }
  return fetch(`${PATHLY_API_BASE}${path}`, { ...init, headers })
}
