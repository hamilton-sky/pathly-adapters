import { describe, expect, it } from 'vitest'
import { HQ_SECTIONS, hqSectionLabel, isHqSectionName, selectedHqSections, useHqContextStore } from './hqContextStore'

describe('hqContextStore', () => {
  it('mirrors the server sections, with artifact summaries opt-in', () => {
    expect(HQ_SECTIONS.map((s) => s.name)).toEqual(['questions', 'runs', 'goals', 'events', 'artifacts', 'summaries'])
    expect(selectedHqSections()).toEqual(['questions', 'runs', 'goals', 'events', 'artifacts'])
  })

  it('toggling changes what the next question carries', () => {
    const { toggle } = useHqContextStore.getState()
    toggle('summaries')
    toggle('events')
    expect(selectedHqSections()).toEqual(['questions', 'runs', 'goals', 'artifacts', 'summaries'])
    toggle('summaries')
    toggle('events')
  })

  it('an all-off choice sends an empty list (no board context)', () => {
    const none = Object.fromEntries(HQ_SECTIONS.map((s) => [s.name, false])) as Parameters<typeof selectedHqSections>[0]
    expect(selectedHqSections(none)).toEqual([])
  })

  it('labels and validates section names', () => {
    expect(hqSectionLabel('questions')).toBe('Pending questions')
    expect(hqSectionLabel('mystery')).toBe('mystery')
    expect(isHqSectionName('goals')).toBe(true)
    expect(isHqSectionName('mystery')).toBe(false)
  })
})
