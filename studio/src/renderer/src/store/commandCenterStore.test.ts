import { describe, it, expect, beforeEach } from 'vitest'
import { useCommandCenterStore } from './commandCenterStore'
import type { CommandCenterState, SectionDef } from '../components/CommandCenter/types'

// syncToFeatures reconciles the open board layout with the active project's feature
// set — the fix for "switching projects updates the sidebar but not the boards": the
// previously-open feature tabs/sections belong to the old project and must be pruned
// (feature boards are keyed by feature id alone, so a stale tab keeps showing the old
// project's board). Project/Global sections are project-agnostic and preserved.

const feat = (fid: string): SectionDef => ({ id: fid, scope: 'feature', featureId: fid })
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
    expect(sectionIds()).toEqual(['billing'])
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
    expect(sectionIds()).toEqual(['a', 'b'])
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
    expect(sectionIds()).toEqual(['a'])
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
