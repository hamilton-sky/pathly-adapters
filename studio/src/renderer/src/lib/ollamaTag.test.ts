import { describe, expect, it } from 'vitest'
import { ollamaHasTag } from './ollamaTag'

describe('ollamaHasTag', () => {
  it('matches the exact tag or another tag of the same model', () => {
    expect(ollamaHasTag('qwen3:8b', ['qwen3:8b'])).toBe(true)
    expect(ollamaHasTag('qwen3:8b', ['qwen3:latest'])).toBe(true)
    expect(ollamaHasTag('qwen3:8b', ['phi4-mini:latest'])).toBe(false)
    expect(ollamaHasTag('', ['qwen3:8b'])).toBe(false)
  })
})
