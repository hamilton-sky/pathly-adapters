import { describe, expect, it } from 'vitest'
import {
  BOARD_CONTEXT_UNAVAILABLE_MARKER,
  formatTokens,
  sectionStatusLabel,
  stripUnavailableMarker,
  usagePercent,
} from './manifestUtils'

describe('formatTokens', () => {
  it('compacts thousands', () => {
    expect(formatTokens(1234)).toBe('1.2k')
    expect(formatTokens(6000)).toBe('6.0k')
  })
  it('keeps small counts plain', () => {
    expect(formatTokens(999)).toBe('999')
    expect(formatTokens(0)).toBe('0')
  })
  it('guards non-finite input', () => {
    expect(formatTokens(NaN)).toBe('0')
    expect(formatTokens(-5)).toBe('0')
  })
})

describe('sectionStatusLabel', () => {
  it('labels a section the user turned off', () => {
    expect(sectionStatusLabel({ name: 'summaries', included: false, cut_reason: 'off' })).toBe('off')
  })

  it('labels included sections', () => {
    expect(sectionStatusLabel({ name: 'goals', included: true, cut_reason: null })).toBe('included')
  })
  it('labels cut sections with their reason', () => {
    expect(sectionStatusLabel({ name: 'events', included: false, cut_reason: 'over budget' })).toBe(
      'cut - over budget',
    )
  })
  it('labels cut sections without a reason', () => {
    expect(sectionStatusLabel({ name: 'events', included: false, cut_reason: null })).toBe('cut')
  })
})

describe('unavailable marker', () => {
  it('strips the marker from answer text', () => {
    const content = `Here is the answer.\n\n${BOARD_CONTEXT_UNAVAILABLE_MARKER}`
    expect(stripUnavailableMarker(content)).toBe('Here is the answer.')
    expect(stripUnavailableMarker('plain answer')).toBe('plain answer')
  })
})

describe('usagePercent', () => {
  it('rounds and clamps to 0-100', () => {
    expect(usagePercent(1500, 6000)).toBe(25)
    expect(usagePercent(9000, 6000)).toBe(100)
    expect(usagePercent(-5, 6000)).toBe(0)
  })

  it('reads a zero or invalid budget as 0%', () => {
    expect(usagePercent(100, 0)).toBe(0)
    expect(usagePercent(Number.NaN, 6000)).toBe(0)
  })
})
