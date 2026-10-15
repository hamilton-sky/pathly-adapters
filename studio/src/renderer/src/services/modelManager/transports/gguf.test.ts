import { describe, expect, it } from 'vitest'
import { oneShotGeneration } from './gguf'

describe('oneShotGeneration — local summary settings', () => {
  it('never reasons, and caps the answer', () => {
    expect(oneShotGeneration('x')).toMatchObject({ maxTokens: 1024, thoughtBudget: 0 })
  })

  it('sizes the context to the prompt, within 4k–16k', () => {
    expect(oneShotGeneration('x').contextSize).toBe(4096)
    expect(oneShotGeneration('x'.repeat(9000)).contextSize).toBe(3000 + 1024 + 512)
    expect(oneShotGeneration('x'.repeat(200_000)).contextSize).toBe(16384)
  })
})
