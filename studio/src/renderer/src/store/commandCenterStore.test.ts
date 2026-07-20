import { describe, it, expect, beforeEach } from 'vitest'
import { useCommandCenterStore } from './commandCenterStore'
import type { CommandCenterState, SectionDef } from '../components/CommandCenter/types'

// syncToFeatures reconciles the open board layout with the active project's feature
// set — the fix for "switching projects updates the sidebar but not the boards": the
// previously-open feature tabs/sections belong to the old project and must be pruned
// (feature boards are keyed by feature id alone, so a stale tab keeps showing the old
// project's board). Project/Global sections are project-agnostic and preserved.

// Mirror mkFeature: feature section ids are namespaced `feature:<fid>` so they can never
// collide with the reserved 'global'/'project' section ids (see the collision regression below).
const feat = (fid: string): SectionDef => ({ id: `feature:${fid}`, scope: 'feature', featureId: fid })
const GLOBAL: SectionDef = { id: 'global', scope: 'global' }
const PROJECT: SectionDef = { id: 'project', scope: 'project' }

const setLayout = (partial: Partial<CommandCenterState>): void =>
  useCommandCenterStore.setState(partial)
const layout = () => useCommandCenterStore.getState()
const sectionIds = (): string[] => layout().sections.map((sec) => sec.id)

describe('commandCenterStore.syncToFeatures', () => {
  beforeEach(() => {
    setLayout({
      sections: [feat('planner-hierarchy')],
      featureTabs: ['planner-hierarchy'],
      mainFeature: 'planner-hierarchy',
      openFeature: 'planner-hierarchy',
      preset: 'custom',
      sizes: {},
    })
  })

  it('clears the feature area when switching to a project with no features (the invoice-tracker bug)', () => {
    setLayout({
      sections: [GLOBAL, PROJECT, feat('planner-hierarchy')],
      featureTabs: ['planner-hierarchy', 'production-readiness'],
      mainFeature: 'planner-hierarchy',
      openFeature: 'planner-hierarchy',
    })

    layout().syncToFeatures([])

    expect(layout().featureTabs).toEqual([])
    expect(sectionIds()).toEqual(['global', 'project']) // Project/Global preserved, feature pruned
    expect(layout().mainFeature).toBe('')
    expect(layout().openFeature).toBeNull()
  })

  it('prunes stale tabs and re-seeds mainFeature (preferring activeTopic) when switching to a different project', () => {
    layout().syncToFeatures(['auth', 'billing'], 'billing')

    expect(layout().mainFeature).toBe('billing')
    expect(layout().featureTabs).toEqual(['billing']) // planner-hierarchy dropped, billing seeded
    expect(sectionIds()).toEqual(['feature:billing'])
    expect(layout().openFeature).toBe('billing') // stale openFeature re-seeded to the new main
  })

  it('falls back to the first valid feature when there is no preferred topic', () => {
    layout().syncToFeatures(['auth', 'billing'])
    expect(layout().mainFeature).toBe('auth')
    expect(layout().featureTabs).toEqual(['auth'])
  })

  it('preserves a valid layout unchanged — does not auto-open a feature the user kept closed (no-op)', () => {
    setLayout({
      sections: [feat('a'), feat('b')],
      featureTabs: ['a', 'b'],
      mainFeature: 'a',
      openFeature: 'a',
    })
    const before = layout()

    layout().syncToFeatures(['a', 'b', 'c']) // 'c' exists in the project but is not open

    expect(layout().featureTabs).toEqual(['a', 'b']) // 'c' not force-added
    expect(sectionIds()).toEqual(['feature:a', 'feature:b'])
    expect(layout().mainFeature).toBe('a')
    // No-op guard: unchanged layout keeps the same array references (no re-render churn).
    expect(layout().featureTabs).toBe(before.featureTabs)
    expect(layout().sections).toBe(before.sections)
  })

  it('re-seeds mainFeature to a remaining feature when the current main is archived away', () => {
    setLayout({
      sections: [feat('a'), feat('b')],
      featureTabs: ['a', 'b'],
      mainFeature: 'b',
      openFeature: 'b',
    })

    layout().syncToFeatures(['a']) // 'b' archived/removed

    expect(layout().featureTabs).toEqual(['a'])
    expect(sectionIds()).toEqual(['feature:a'])
    expect(layout().mainFeature).toBe('a')
    expect(layout().openFeature).toBe('a')
  })

  it('keeps a collapsed rail collapsed (openFeature === null is not re-seeded)', () => {
    setLayout({
      sections: [feat('a')],
      featureTabs: ['a'],
      mainFeature: 'a',
      openFeature: null,
    })

    layout().syncToFeatures(['a', 'b']) // 'a' still valid

    expect(layout().openFeature).toBeNull()
  })
})

describe('commandCenterStore section-id collision (feature named like a reserved scope)', () => {
  const sectionIds = (): string[] => useCommandCenterStore.getState().sections.map((sec) => sec.id)

  it('a feature named "global" does not collide with the reserved Global board section', () => {
    // Regression: mkFeature used the bare feature id, so a feature literally named "global"
    // (e.g. an evaluate run that leaked the board scope into an unsubstituted <feature>) minted
    // a section with id==='global' — the same id as the reserved Global board section. Two
    // sections sharing one React key → duplicate-key warning + a flickering board.
    useCommandCenterStore.setState({ mainFeature: 'global' })
    useCommandCenterStore.getState().applyPreset('board') // Global + Project + the "global" feature

    const ids = sectionIds()
    expect(new Set(ids).size).toBe(ids.length) // every section id unique — no duplicate React key
    expect(ids).toContain('global') // the reserved Global board section
    expect(ids).toContain('feature:global') // the feature named "global", namespaced apart
  })
})
