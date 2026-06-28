import { describe, it, expect } from 'vitest'
import { buildSummarizePrompt } from './summaryPrompt'

describe('buildSummarizePrompt', () => {
  it('defaults to a topic map and includes the text', () => {
    const p = buildSummarizePrompt('# Doc\n## Storage\nWAL.')
    expect(p).toContain('compact topic map')
    expect(p).toContain('Maximum 3 items')
    expect(p).toContain('Output ONLY the topic-map lines')
    expect(p).toContain('# Doc\n## Storage\nWAL.')
  })

  it('produces a one-sentence gist prompt for the gist depth', () => {
    const p = buildSummarizePrompt('x', 'gist')
    expect(p).toContain('ONE-SENTENCE gist')
    expect(p).not.toContain('topic map')
  })

  it('produces a section-level prompt for the detailed depth', () => {
    const p = buildSummarizePrompt('x', 'detailed')
    expect(p).toContain('DETAILED summary')
    expect(p).toContain('key points or decisions')
  })

  it('emits a distinct prompt for each depth', () => {
    const text = '# Doc\n## A\nfoo'
    const gist = buildSummarizePrompt(text, 'gist')
    const topic = buildSummarizePrompt(text, 'topic-map')
    const detailed = buildSummarizePrompt(text, 'detailed')
    expect(new Set([gist, topic, detailed]).size).toBe(3)
  })

  it('truncates very long input to 8000 chars before the document body', () => {
    const long = 'a'.repeat(9000)
    const p = buildSummarizePrompt(long)
    const body = p.split('Document:\n')[1]
    expect(body.length).toBe(8000)
  })
})
