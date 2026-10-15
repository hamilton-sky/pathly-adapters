import { describe, expect, it } from 'vitest'
import { migrateModelSelection } from './modelStore'
import { RECOMMENDED_MODEL_ID } from '../data/models'

describe('migrateModelSelection', () => {
  it('the default is qwen3-8b', () => {
    expect(RECOMMENDED_MODEL_ID).toBe('qwen3-8b')
  })

  it('moves the saved v0 default (phi-4-mini) to the new default once', () => {
    expect(migrateModelSelection({ selectedModelId: 'phi-4-mini', responseMode: 'deep' }, 0))
      .toEqual({ selectedModelId: 'qwen3-8b', responseMode: 'deep' })
  })

  it('keeps any other saved choice', () => {
    const saved = { selectedModelId: 'qwen3-4b', responseMode: 'fast' }
    expect(migrateModelSelection(saved, 0)).toBe(saved)
  })

  it('keeps phi-4-mini when picked after the default changed (v1+)', () => {
    const saved = { selectedModelId: 'phi-4-mini', responseMode: 'fast' }
    expect(migrateModelSelection(saved, 1)).toBe(saved)
  })

  it('tolerates an empty store', () => {
    expect(migrateModelSelection(undefined, 0)).toBeUndefined()
  })
})
