import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { CommandCenterState, SectionDef } from '../components/CommandCenter/types'
import { MAX_SECTIONS } from '../components/CommandCenter/types'

const mkFeature = (fid: string): SectionDef => ({ id: fid, scope: 'feature', featureId: fid })
const GLOBAL_SEC: SectionDef = { id: 'global', scope: 'global' }
const PROJECT_SEC: SectionDef = { id: 'project', scope: 'project' }

const INITIAL_FEATURE = 'send-to-agent-diff'

const INITIAL: CommandCenterState = {
  sections: [mkFeature(INITIAL_FEATURE)],
  featureTabs: [INITIAL_FEATURE],
  preset: 'pipeline',
  mainFeature: INITIAL_FEATURE,
  sidebarCollapsed: false,
  openFeature: INITIAL_FEATURE,
  sizes: {},
}

export interface CommandCenterActions {
  applyPreset: (preset: 'board' | 'pipeline' | 'focus') => void
  toggleSection: (scope: 'project' | 'global') => void
  addFeatureSection: (featureId: string) => void
  toggleFeatureSection: (featureId: string) => void
  removeFeatureTab: (featureId: string) => void
  addAnySection: () => void
  setMainFeature: (fid: string) => void
  syncToFeatures: (validIds: string[], preferred?: string) => void
  openFeatureFromRail: (fid: string) => void
  openNewFeature: (fid: string) => void
  toggleOpenFeature: (fid: string) => void
  toggleSidebar: () => void
  setSize: (id: string, px: number) => void
}

export type CommandCenterStore = CommandCenterState & CommandCenterActions

export const useCommandCenterStore = create<CommandCenterStore>()(
  persist(
    (set) => ({
      ...INITIAL,

      applyPreset: (preset) => {
        set((s) => {
          const fid = s.mainFeature
          const sections: SectionDef[] = preset === 'board'
            ? [GLOBAL_SEC, PROJECT_SEC, mkFeature(fid)]
            : [mkFeature(fid)]
          return { ...s, sections, sidebarCollapsed: preset === 'focus', preset, sizes: {} }
        })
      },

      toggleSection: (scope) => {
        set((s) => {
          const exists = s.sections.some((sec) => sec.scope === scope)
          if (exists) {
            return { ...s, sections: s.sections.filter((sec) => sec.scope !== scope), preset: 'custom', sizes: {} }
          }
          if (s.sections.length >= MAX_SECTIONS) return s
          const newSec: SectionDef = scope === 'project' ? PROJECT_SEC : GLOBAL_SEC
          return { ...s, sections: [...s.sections, newSec], preset: 'custom', sizes: {} }
        })
      },

      addFeatureSection: (featureId) => {
        set((s) => {
          const inTabs = s.featureTabs.includes(featureId)
          const inSections = s.sections.some((sec) => sec.scope === 'feature' && sec.featureId === featureId)
          const newTabs = inTabs ? s.featureTabs :
            s.featureTabs.length < MAX_SECTIONS ? [...s.featureTabs, featureId] : s.featureTabs
          const newSections = inSections ? s.sections :
            s.sections.length < MAX_SECTIONS ? [...s.sections, mkFeature(featureId)] : s.sections
          return { ...s, featureTabs: newTabs, sections: newSections, preset: 'custom', sizes: {} }
        })
      },

      toggleFeatureSection: (featureId) => {
        set((s) => {
          const isActive = s.sections.some((sec) => sec.scope === 'feature' && sec.featureId === featureId)
          if (isActive) {
            return { ...s, sections: s.sections.filter((sec) => !(sec.scope === 'feature' && sec.featureId === featureId)) }
          }
          if (s.sections.length >= MAX_SECTIONS) return s
          return { ...s, sections: [...s.sections, mkFeature(featureId)] }
        })
      },

      removeFeatureTab: (featureId) => {
        set((s) => {
          if (s.featureTabs.length <= 1) return s
          const newTabs = s.featureTabs.filter((fid) => fid !== featureId)
          const newSections = s.sections.filter((sec) => !(sec.scope === 'feature' && sec.featureId === featureId))
          const newMain = s.mainFeature === featureId ? newTabs[newTabs.length - 1] : s.mainFeature
          return { ...s, featureTabs: newTabs, sections: newSections, mainFeature: newMain, sizes: {} }
        })
      },

      addAnySection: () => {
        set((s) => {
          if (s.sections.length >= MAX_SECTIONS) return s
          if (!s.sections.some((sec) => sec.scope === 'project')) {
            return { ...s, sections: [...s.sections, PROJECT_SEC], preset: 'custom' }
          }
          if (!s.sections.some((sec) => sec.scope === 'global')) {
            return { ...s, sections: [...s.sections, GLOBAL_SEC], preset: 'custom' }
          }
          return s
        })
      },

      setMainFeature: (fid) => {
        set((s) => {
          const inTabs = s.featureTabs.includes(fid)
          const newTabs = !inTabs && s.featureTabs.length < MAX_SECTIONS
            ? [...s.featureTabs, fid] : s.featureTabs
          const inSections = s.sections.some((sec) => sec.scope === 'feature' && sec.featureId === fid)
          const newSections = !inSections && newTabs.includes(fid) && s.sections.length < MAX_SECTIONS
            ? [...s.sections, mkFeature(fid)] : s.sections
          return { ...s, mainFeature: fid, featureTabs: newTabs, sections: newSections }
        })
      },

      // Reconcile the open board layout with the active project's feature set.
      // Called whenever the features list changes — critically on a PROJECT SWITCH,
      // where the previously-open feature tabs/sections belong to the old project and
      // must not linger (feature boards are keyed by feature id alone, so a stale tab
      // would keep showing the old project's board). Feature tabs/sections whose id
      // isn't in `validIds` are dropped; mainFeature/openFeature are re-seeded to a
      // valid feature only when the current one is gone (so a user's arrangement on
      // the same project is preserved across refreshes). Project/Global sections are
      // project-agnostic and left untouched.
      syncToFeatures: (validIds, preferred) => {
        set((s) => {
          const valid = new Set(validIds)
          const featureTabs = s.featureTabs.filter((fid) => valid.has(fid))
          let sections = s.sections.filter((sec) => sec.scope !== 'feature' || valid.has(sec.featureId))

          let mainFeature = s.mainFeature
          let tabs = featureTabs
          if (!valid.has(mainFeature)) {
            // Current main is gone (project switch, or it was archived) — re-seed to a
            // valid feature and surface it, or clear when the project has none.
            mainFeature = preferred && valid.has(preferred) ? preferred : (featureTabs[0] ?? validIds[0] ?? '')
            if (mainFeature) {
              if (!tabs.includes(mainFeature)) tabs = [...tabs, mainFeature]
              if (!sections.some((sec) => sec.scope === 'feature' && sec.featureId === mainFeature)
                  && sections.length < MAX_SECTIONS) {
                sections = [...sections, mkFeature(mainFeature)]
              }
            }
          }

          // Keep a collapsed rail (openFeature === null) collapsed; only re-seed an
          // openFeature that pointed at a now-missing feature.
          const openFeature = s.openFeature === null || valid.has(s.openFeature)
            ? s.openFeature
            : (mainFeature || null)

          // No-op guard: this runs on every features refresh — skip the state update
          // (and its store-wide re-render) when the reconciled layout is unchanged.
          const tabsSame = tabs.length === s.featureTabs.length && tabs.every((t, i) => t === s.featureTabs[i])
          const secsSame = sections.length === s.sections.length && sections.every((sec, i) => sec.id === s.sections[i].id)
          if (tabsSame && secsSame && mainFeature === s.mainFeature && openFeature === s.openFeature) return s
          return { ...s, featureTabs: tabs, sections, mainFeature, openFeature }
        })
      },

      openFeatureFromRail: (fid) => {
        set((s) => {
          const inTabs = s.featureTabs.includes(fid)
          const newTabs = !inTabs && s.featureTabs.length < MAX_SECTIONS
            ? [...s.featureTabs, fid] : s.featureTabs
          const inSections = s.sections.some((sec) => sec.scope === 'feature' && sec.featureId === fid)
          const newSections = !inSections && s.sections.length < MAX_SECTIONS
            ? [...s.sections, mkFeature(fid)] : s.sections
          return { ...s, mainFeature: fid, openFeature: fid, sidebarCollapsed: false, featureTabs: newTabs, sections: newSections }
        })
      },

      openNewFeature: (fid) => {
        set((s) => {
          // If already tracked, just surface it.
          if (s.featureTabs.includes(fid)) {
            const inSections = s.sections.some((sec) => sec.scope === 'feature' && sec.featureId === fid)
            const newSections = !inSections && s.sections.length < MAX_SECTIONS
              ? [...s.sections, mkFeature(fid)] : s.sections
            return { ...s, mainFeature: fid, openFeature: fid, sections: newSections }
          }

          // At cap: evict the right-most feature tab to make room for the new one.
          let tabs = s.featureTabs
          let sections = s.sections
          if (tabs.length >= MAX_SECTIONS) {
            const evict = tabs[tabs.length - 1]
            tabs = tabs.slice(0, -1)
            sections = sections.filter((sec) => !(sec.scope === 'feature' && sec.featureId === evict))
          }

          const newTabs = [...tabs, fid]
          const newSections = sections.length < MAX_SECTIONS
            ? [...sections, mkFeature(fid)] : sections

          return {
            ...s,
            featureTabs: newTabs,
            sections: newSections,
            mainFeature: fid,
            openFeature: fid,
            preset: 'custom',
            sizes: {},
          }
        })
      },

      toggleOpenFeature: (fid) => {
        set((s) => ({ ...s, openFeature: s.openFeature === fid ? null : fid }))
      },

      toggleSidebar: () => {
        set((s) => ({ ...s, sidebarCollapsed: !s.sidebarCollapsed }))
      },

      setSize: (id, px) => {
        set((s) => ({ ...s, sizes: { ...s.sizes, [id]: px } }))
      },
    }),
    {
      name: 'pathly-command-center-layout',
      version: 3,
      migrate: (_persistedState, version) => {
        if (version < 3) return { ...INITIAL }
        return _persistedState as CommandCenterState
      },
    },
  ),
)
