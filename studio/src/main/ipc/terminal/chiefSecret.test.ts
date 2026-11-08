import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

vi.mock('../../apiConfig', () => ({
  getApiBase: () => 'http://127.0.0.1:9999',
  getApiSecret: () => 'made-up-api-secret',
}))

import { claimChiefHookSecret, chiefSecretForSpawn, isChiefClaudeSpawn } from './chiefSecret'

// Made-up values only: no real secret is ever used in a test.
const SECRET = 'made-up-hook-secret-abc123'
const CHIEF = 'chief-0123456789ab'

function answer(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('claimChiefHookSecret', () => {
  let fetchMock: ReturnType<typeof vi.fn>
  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => { vi.unstubAllGlobals() })

  it('posts the run id, tokenless, to /chief/hook-secret and returns the secret on 200', async () => {
    fetchMock.mockResolvedValue(answer(200, { hook_secret: SECRET }))
    await expect(claimChiefHookSecret(CHIEF)).resolves.toBe(SECRET)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('http://127.0.0.1:9999/chief/hook-secret')
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual({ run_id: CHIEF })
    const headers = init.headers as Record<string, string>
    expect(headers['X-Pathly-Secret']).toBe('made-up-api-secret')
    expect(Object.keys(headers).map((h) => h.toLowerCase())).not.toContain('x-pathly-run-token')
  })

  it('returns null when the claim answers 409 (a second claim: the server closed the chief)', async () => {
    fetchMock.mockResolvedValue(answer(409, { error: 'claimed twice' }))
    await expect(claimChiefHookSecret(CHIEF)).resolves.toBeNull()
  })

  it.each([403, 404, 500])('returns null for a %i', async (status) => {
    fetchMock.mockResolvedValue(answer(status, { error: 'no' }))
    await expect(claimChiefHookSecret(CHIEF)).resolves.toBeNull()
  })

  it('returns null when the request fails', async () => {
    fetchMock.mockRejectedValue(new TypeError('fetch failed'))
    await expect(claimChiefHookSecret(CHIEF)).resolves.toBeNull()
  })

  it.each([{}, { hook_secret: '' }, { hook_secret: 42 }, 'not json'])('returns null for a 200 with no usable secret (%j)', async (body) => {
    fetchMock.mockResolvedValue(typeof body === 'string' ? new Response(body, { status: 200 }) : answer(200, body))
    await expect(claimChiefHookSecret(CHIEF)).resolves.toBeNull()
  })

  it('never logs the secret', async () => {
    const spies = (['log', 'info', 'warn', 'error', 'debug'] as const).map((m) => vi.spyOn(console, m).mockImplementation(() => undefined))
    fetchMock.mockResolvedValue(answer(200, { hook_secret: SECRET }))
    await claimChiefHookSecret(CHIEF)
    await chiefSecretForSpawn(CHIEF, ['claude'], true)
    for (const spy of spies) {
      expect(JSON.stringify(spy.mock.calls)).not.toContain(SECRET)
      spy.mockRestore()
    }
  })
})

describe('isChiefClaudeSpawn', () => {
  it('is true only for an interactive claude tab whose run id is a chief run id', () => {
    expect(isChiefClaudeSpawn(CHIEF, ['claude', '--session-id', 'x'], true)).toBe(true)
    expect(isChiefClaudeSpawn(CHIEF, ['codex'], true)).toBe(false)
    expect(isChiefClaudeSpawn(CHIEF, ['claude', '-p', 'x'], false)).toBe(false)
    expect(isChiefClaudeSpawn(CHIEF, undefined, true)).toBe(false)
    expect(isChiefClaudeSpawn(undefined, ['claude'], true)).toBe(false)
    expect(isChiefClaudeSpawn('run-0123456789ab', ['claude'], true)).toBe(false)
    expect(isChiefClaudeSpawn('chief-0123456789AB', ['claude'], true)).toBe(false)
    expect(isChiefClaudeSpawn('chief-0123456789ab0', ['claude'], true)).toBe(false)
    expect(isChiefClaudeSpawn('xchief-0123456789ab', ['claude'], true)).toBe(false)
  })
})

describe('chiefSecretForSpawn', () => {
  let fetchMock: ReturnType<typeof vi.fn>
  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => { vi.unstubAllGlobals() })

  it('claims nothing for a spawn that is not a claude chief', async () => {
    await expect(chiefSecretForSpawn('run-0123456789ab', ['claude'], true)).resolves.toBeUndefined()
    await expect(chiefSecretForSpawn(CHIEF, ['codex'], true)).resolves.toBeUndefined()
    await expect(chiefSecretForSpawn(CHIEF, ['claude'], false)).resolves.toBeUndefined()
    await expect(chiefSecretForSpawn(undefined, ['claude'], true)).resolves.toBeUndefined()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('returns the claimed value for a claude chief', async () => {
    fetchMock.mockResolvedValue(answer(200, { hook_secret: SECRET }))
    await expect(chiefSecretForSpawn(CHIEF, ['claude'], true)).resolves.toBe(SECRET)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('refuses the chief spawn when the claim answers 409', async () => {
    fetchMock.mockResolvedValue(answer(409, { error: 'claimed twice' }))
    await expect(chiefSecretForSpawn(CHIEF, ['claude'], true)).rejects.toThrow(/hook secret/i)
  })

  it('refuses the chief spawn when the claim fails', async () => {
    fetchMock.mockRejectedValue(new TypeError('fetch failed'))
    await expect(chiefSecretForSpawn(CHIEF, ['claude'], true)).rejects.toThrow(/hook secret/i)
  })
})
