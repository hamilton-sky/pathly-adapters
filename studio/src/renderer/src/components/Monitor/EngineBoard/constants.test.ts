import { describe, expect, it } from 'vitest'
import { CATEGORY_META } from './constants'
import { CATEGORY_ORDER, categoryColor } from '../../CliMonitorBar/constants'

describe('consult run category', () => {
  it('CATEGORY_META has flow, loop, single, consult in that order', () => {
    expect(CATEGORY_META.map((c) => c.key)).toEqual(['flow', 'loop', 'single', 'consult'])
  })

  it('gives consult its own section label and blurb', () => {
    const consult = CATEGORY_META.find((c) => c.key === 'consult')
    expect(consult?.label).toBe('Consults')
    expect(consult?.blurb).toBe("role agents answering agents' questions")
  })

  it('gives every category a distinct design-system colour', () => {
    const colors = CATEGORY_META.map((c) => c.color)
    expect(new Set(colors).size).toBe(colors.length)
    for (const color of colors) expect(color).toMatch(/^var\(--[a-z-]+\)$/)
  })

  it("the dock's categoryColor('consult') is the board's consult colour", () => {
    const consult = CATEGORY_META.find((c) => c.key === 'consult')
    expect(consult).toBeDefined()
    expect(categoryColor('consult')).toBe(consult?.color)
  })

  it("the dock's colours match the board's for every category", () => {
    for (const meta of CATEGORY_META) expect(categoryColor(meta.key)).toBe(meta.color)
  })

  it("the dock's CATEGORY_ORDER ends with consult", () => {
    expect(CATEGORY_ORDER[CATEGORY_ORDER.length - 1]).toBe('consult')
    expect(CATEGORY_ORDER).toEqual(['flow', 'loop', 'single', 'consult'])
  })
})
