import { describe, it, expect } from 'vitest'
import { buildSummarizePrompt } from './summaryPrompt'

describe('buildSummarizePrompt', () => {
  it('asks for a topic map with the default item cap and includes the text', () => {
    const p = buildSummarizePrompt('# Doc\n## Storage\nWAL.')
    expect(p).toContain('compact topic map')
    expect(p).toContain('Maximum 3 items')
    expect(p).toContain('Output ONLY the topic-map lines')
    expect(p).toContain('# Doc\n## Storage\nWAL.')
  })

  it('honours a custom maxSentences cap', () => {
    expect(buildSummarizePrompt('x', 5)).toContain('Maximum 5 items')
  })

  it('truncates very long input to 8000 chars before the document body', () => {
    const long = 'a'.repeat(9000)
    const p = buildSummarizePrompt(long)
    const body = p.split('Document:\n')[1]
    expect(body.length).toBe(8000)
  })
})
