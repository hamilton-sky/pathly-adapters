import { describe, it, expect } from 'vitest'
import { buildSummarizePrompt, parseStructuredSummary } from './summaryPrompt'

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

describe('parseStructuredSummary', () => {
  it('splits an explicit ## Description / ## Summary block', () => {
    const { description, summary } = parseStructuredSummary(
      '## Description\nWhat it is.\n\n## Summary\n- a: x\n- b: y',
    )
    expect(description).toBe('What it is.')
    expect(summary).toBe('- a: x\n- b: y')
  })

  it('ignores a chatty CLI-agent preamble before the sections', () => {
    // A headless CLI (claude/codex) may prepend prose; the unanchored parser still extracts both.
    const { description, summary } = parseStructuredSummary(
      'Sure, here is the summary:\n\n## Description\nThe design doc.\n\n## Summary\n- one\n- two',
    )
    expect(description).toBe('The design doc.')
    expect(summary).toBe('- one\n- two')
  })

  it('derives a description from the summary when the block is absent', () => {
    const raw = 'This is the only sentence produced. And a second one. And a third.'
    const { description, summary } = parseStructuredSummary(raw)
    expect(summary).toBe(raw)
    expect(description).toBe('This is the only sentence produced. And a second one.')
  })

  it('derives a description when the Description section is present but empty', () => {
    const { description, summary } = parseStructuredSummary(
      '## Description\n\n## Summary\nFirst point here. Second point.',
    )
    expect(summary).toBe('First point here. Second point.')
    expect(description).toBe('First point here. Second point.')
  })

  it('caps an overlong derived description', () => {
    const { description } = parseStructuredSummary('x'.repeat(400))
    expect(description).not.toBeNull()
    expect(description!.length).toBeLessThanOrEqual(300)
    expect(description!.endsWith('…')).toBe(true)
  })

  it('returns a null description only when there is no text at all', () => {
    expect(parseStructuredSummary('   ')).toEqual({ description: null, summary: '' })
  })
})
