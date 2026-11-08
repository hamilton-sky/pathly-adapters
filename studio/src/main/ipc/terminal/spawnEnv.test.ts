import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

vi.mock('./shells', () => ({ enrichedPath: () => '/enriched/bin' }))

import { buildSpawnEnv } from './spawnEnv'

describe('buildSpawnEnv', () => {
  beforeEach(() => { delete process.env.PATHLY_RUN_TOKEN })
  afterEach(() => { delete process.env.PATHLY_RUN_TOKEN })

  it('gives a runner tab with a token PATHLY_RUN_TOKEN, exactly as received', () => {
    const env = buildSpawnEnv('/proj', { run_token: 'tok-abc_123' })
    expect(env.PATHLY_RUN_TOKEN).toBe('tok-abc_123')
  })

  it('gives a runner tab without a token no PATHLY_RUN_TOKEN key', () => {
    expect('PATHLY_RUN_TOKEN' in buildSpawnEnv('/proj', {})).toBe(false)
    expect('PATHLY_RUN_TOKEN' in buildSpawnEnv('/proj', { run_token: '' })).toBe(false)
  })

  it('gives a non-runner tab no PATHLY_RUN_TOKEN and no PATHLY_GATE_BILLED', () => {
    const env = buildSpawnEnv('/proj', undefined)
    expect('PATHLY_RUN_TOKEN' in env).toBe(false)
    expect('PATHLY_GATE_BILLED' in env).toBe(false)
  })

  it('keeps PATHLY_GATE_BILLED for runner tabs and the project root + enriched PATH for all', () => {
    const runner = buildSpawnEnv('/proj', { run_token: 't' })
    expect(runner.PATHLY_GATE_BILLED).toBe('1')
    expect(runner.PATHLY_PROJECT_ROOT).toBe('/proj')
    expect(runner.PATH).toBe('/enriched/bin')
    const manual = buildSpawnEnv('/other', undefined)
    expect(manual.PATHLY_PROJECT_ROOT).toBe('/other')
    expect(manual.PATH).toBe('/enriched/bin')
  })

  it('does not write the token into process.env', () => {
    buildSpawnEnv('/proj', { run_token: 'secret' })
    expect(process.env.PATHLY_RUN_TOKEN).toBeUndefined()
  })

  describe('PATHLY_CHIEF_HOOK_SECRET', () => {
    // Made-up values only.
    beforeEach(() => { process.env.PATHLY_CHIEF_HOOK_SECRET = 'made-up-studio-own-value' })
    afterEach(() => { delete process.env.PATHLY_CHIEF_HOOK_SECRET })

    it("never reaches a non-chief child, even when Studio's own environment has one", () => {
      expect('PATHLY_CHIEF_HOOK_SECRET' in buildSpawnEnv('/proj', undefined)).toBe(false)
      expect('PATHLY_CHIEF_HOOK_SECRET' in buildSpawnEnv('/proj', {})).toBe(false)
      expect('PATHLY_CHIEF_HOOK_SECRET' in buildSpawnEnv('/proj', { run_token: 't' })).toBe(false)
      expect('PATHLY_CHIEF_HOOK_SECRET' in buildSpawnEnv('/proj', { run_token: 't' }, undefined)).toBe(false)
      expect('PATHLY_CHIEF_HOOK_SECRET' in buildSpawnEnv('/proj', { run_token: 't' }, '')).toBe(false)
    })

    it('gives a chief child exactly the claimed value', () => {
      const env = buildSpawnEnv('/proj', { run_token: 't' }, 'made-up-claimed-value')
      expect(env.PATHLY_CHIEF_HOOK_SECRET).toBe('made-up-claimed-value')
      expect(env.PATHLY_RUN_TOKEN).toBe('t')
    })

    it('does not write the claimed value into process.env', () => {
      buildSpawnEnv('/proj', { run_token: 't' }, 'made-up-claimed-value')
      expect(process.env.PATHLY_CHIEF_HOOK_SECRET).toBe('made-up-studio-own-value')
    })
  })
})
