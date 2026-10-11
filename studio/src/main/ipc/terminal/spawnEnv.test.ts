import { describe, it, expect } from 'vitest'
import { buildSpawnEnv } from './spawnEnv'

const meta = { run_id: 'r1', topic: 't', spawnedAt: 0, label: 'l' }

describe('buildSpawnEnv', () => {
  it('gives a runner tab with a token PATHLY_RUN_TOKEN and the billed marker', () => {
    const env = buildSpawnEnv('/proj', { ...meta, run_token: 'tok-1' })
    expect(env.PATHLY_RUN_TOKEN).toBe('tok-1')
    expect(env.PATHLY_GATE_BILLED).toBe('1')
    expect(env.PATHLY_PROJECT_ROOT).toBe('/proj')
  })

  it('gives a runner tab without a token no PATHLY_RUN_TOKEN', () => {
    const env = buildSpawnEnv('/proj', meta)
    expect('PATHLY_RUN_TOKEN' in env).toBe(false)
    expect(env.PATHLY_GATE_BILLED).toBe('1')
  })

  it('gives a non-runner tab neither', () => {
    const env = buildSpawnEnv('/proj', undefined)
    expect('PATHLY_RUN_TOKEN' in env).toBe(false)
    expect('PATHLY_GATE_BILLED' in env).toBe(false)
    expect(env.PATHLY_PROJECT_ROOT).toBe('/proj')
  })
})
