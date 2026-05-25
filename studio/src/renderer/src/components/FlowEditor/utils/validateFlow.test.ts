import { describe, it, expect } from 'vitest'
import { validateFlow } from './validateFlow'
import type { FlowYaml } from '../../../types'

const base: FlowYaml = {
  version: 1,
  flow: 'test',
  states: ['start', 'end'],
  transitions: {
    start: ['end'],
    end: [],
  },
  agent_map: {},
}

describe('validateFlow', () => {
  it('returns no issues for a valid flow', () => {
    const issues = validateFlow(base)
    const errors = issues.filter((i) => i.level === 'error')
    expect(errors).toHaveLength(0)
  })

  it('returns an error when a transition target is not in states', () => {
    const flow: FlowYaml = {
      ...base,
      states: ['start'],
      transitions: { start: ['missing'] },
    }
    const issues = validateFlow(flow)
    const errors = issues.filter((i) => i.level === 'error')
    expect(errors.length).toBeGreaterThan(0)
    expect(errors.some((i) => i.message.includes('missing'))).toBe(true)
  })

  it('returns a warning when agent_map behavior is not in knownBehaviors', () => {
    const flow: FlowYaml = {
      ...base,
      agent_map: { start: 'unknown-behavior', end: '' },
    }
    const issues = validateFlow(flow, ['known-behavior'])
    const warnings = issues.filter((i) => i.level === 'warning' && i.id === 'start')
    expect(warnings.length).toBeGreaterThan(0)
  })

  it('returns an error when transition_rules.default points to an invalid target', () => {
    const flow: FlowYaml = {
      ...base,
      transitions: { start: ['end'], end: [] },
      transition_rules: {
        start: { default: 'nowhere' },
      },
    }
    const issues = validateFlow(flow)
    const errors = issues.filter((i) => i.level === 'error' && i.id === 'start->nowhere')
    expect(errors.length).toBeGreaterThan(0)
  })
})
