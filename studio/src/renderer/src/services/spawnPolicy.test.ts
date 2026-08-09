import { vi, describe, it, expect, beforeEach } from 'vitest'

// Mock the one leaf dependency (the policy fetch) so we drive the cache deterministically.
vi.mock('../store/commsApi', () => ({
  apiGetModelPolicy: vi.fn(),
}))

import * as commsApi from '../store/commsApi'
import { effectiveModel, warmModelPolicy } from './spawnPolicy'

const getPolicy = commsApi.apiGetModelPolicy as ReturnType<typeof vi.fn>

// Mirror of supervisor/spawn_policy.py::effective_model — the renderer half.
describe('effectiveModel (client model-policy mirror)', () => {
  beforeEach(() => {
    getPolicy.mockReset()
  })

  it('an explicit model always wins', async () => {
    getPolicy.mockResolvedValue({ default: null, roles: { split: { adapter: 'claude', model: 'claude-opus-4' } } })
    await warmModelPolicy()
    expect(effectiveModel('split', 'claude', 'claude-haiku-4')).toBe('claude-haiku-4')
  })

  it('applies the per-role model within the same company', async () => {
    getPolicy.mockResolvedValue({ default: null, roles: { split: { adapter: 'claude', model: 'claude-opus-4' } } })
    await warmModelPolicy()
    expect(effectiveModel('split', 'claude')).toBe('claude-opus-4')
  })

  it('does NOT apply across companies (model-within-company)', async () => {
    getPolicy.mockResolvedValue({ default: null, roles: { split: { adapter: 'codex', model: 'gpt-5' } } })
    await warmModelPolicy()
    expect(effectiveModel('split', 'claude')).toBe('') // codex policy, claude spawn → no apply
  })

  it('falls back to the global default when there is no per-role override', async () => {
    getPolicy.mockResolvedValue({ default: { adapter: 'claude', model: 'claude-sonnet-5' }, roles: {} })
    await warmModelPolicy()
    expect(effectiveModel('analyze', 'claude')).toBe('claude-sonnet-5')
  })

  it('a per-role override beats the global default', async () => {
    getPolicy.mockResolvedValue({
      default: { adapter: 'claude', model: 'claude-sonnet-5' },
      roles: { analyze: { adapter: 'claude', model: 'claude-opus-4' } },
    })
    await warmModelPolicy()
    expect(effectiveModel('analyze', 'claude')).toBe('claude-opus-4')
  })

  it('an unwarmed / empty policy resolves to the engine default (empty string)', async () => {
    getPolicy.mockResolvedValue(null)
    await warmModelPolicy()
    expect(effectiveModel('split', 'claude')).toBe('')
  })
})
