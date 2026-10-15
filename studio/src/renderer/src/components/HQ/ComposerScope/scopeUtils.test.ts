import { describe, expect, it } from 'vitest'
import type { HqContextManifest } from '../../../store/chatStore'
import { contextCount, DEFAULT_HQ_BUDGET_TOKENS, estimateContext, sectionTokens } from './scopeUtils'

const ALL_ON = { questions: true, runs: true, goals: true, events: true, artifacts: true, summaries: true }
const DEFAULTS = { ...ALL_ON, summaries: false }

function manifest(sections: HqContextManifest['sections'], budget = 8000): HqContextManifest {
  return { board: 'b', tokens_est: 0, budget, sections, model: 'qwen3-8b', eligible_model: true, unavailable: false }
}

const M = manifest([
  { name: 'questions', included: true, cut_reason: null, tokens: 300 },
  { name: 'runs', included: true, cut_reason: null, tokens: 200 },
  { name: 'goals', included: false, cut_reason: 'empty', tokens: 0 },
  { name: 'events', included: true, cut_reason: null, tokens: 100 },
  { name: 'artifacts', included: false, cut_reason: 'over budget', tokens: 900 },
  { name: 'summaries', included: false, cut_reason: 'off', tokens: 0 },
])

describe('contextCount', () => {
  it('counts ticked sections of all six', () => {
    expect(contextCount(DEFAULTS)).toEqual({ on: 5, total: 6 })
  })
})

describe('sectionTokens', () => {
  it('reads a measured size, including a section cut over budget', () => {
    expect(sectionTokens(M, 'questions')).toBe(300)
    expect(sectionTokens(M, 'artifacts')).toBe(900)
  })

  it('is null for a section never read, or with no manifest', () => {
    expect(sectionTokens(M, 'summaries')).toBeNull()
    expect(sectionTokens(M, 'goals')).toBeNull()
    expect(sectionTokens(null, 'questions')).toBeNull()
  })
})

describe('estimateContext', () => {
  it('sums the ticked sections the latest answer measured', () => {
    expect(estimateContext(DEFAULTS, M)).toEqual({ tokens: 1500, unmeasured: 1, budget: 8000 })
  })

  it('counts a ticked section with no size as unmeasured, never as zero', () => {
    expect(estimateContext(ALL_ON, M).unmeasured).toBe(2)
    expect(estimateContext({ ...DEFAULTS, artifacts: false }, M).tokens).toBe(600)
  })

  it('falls back to the server default budget before any answer', () => {
    expect(estimateContext(DEFAULTS, null)).toEqual({ tokens: 0, unmeasured: 5, budget: DEFAULT_HQ_BUDGET_TOKENS })
  })
})
