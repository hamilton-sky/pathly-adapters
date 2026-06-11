import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { BoardScope, CommandCenterState, Direction, Preset } from '../components/HQ/CommandCenter/types'

// Workspace UI state: which board sections are visible, layout direction,
// preset, the main feature, sidebar + accordion.
// Persisted to localStorage under key 'pathly-command-center-layout'.

const PRESETS: Record<Exclude<Preset, 'custom'>, Partial<CommandCenterState>> = {
  board:    { sections: ['global', 'project', 'feature'], direction: 'row', sidebarCollapsed: false },
  pipeline: { sections: ['feature'], direction: 'row', sidebarCollapsed: false },
  focus:    { sections: ['feature'], direction: 'row', sidebarCollapsed: true },
}

// Initial preset is 'pipeline' (sidebar expanded, feature section) — PORTING-MAP §6
const INITIAL: CommandCenterState = {
  sections: ['feature'],
  direction: 'row',
  preset: 'pipeline',
  mainFeature: 'send-to-agent-diff',
  sidebarCollapsed: false,
  openFeature: 'send-to-agent-diff',
  sizes: {},
}

export interface CommandCenterActions {
  applyPreset: (preset: Exclude<Preset, 'custom'>) => void
  toggleSection: (scope: BoardScope) => void
  addAnySection: () => void
  toggleDirection: () => void
  setMainFeature: (fid: string) => void
  openFeatureFromRail: (fid: string) => void
  toggleOpenFeature: (fid: string) => void
  toggleSidebar: () => void
  setSize: (scope: BoardScope, px: number) => void
}

export type CommandCenterStore = CommandCenterState & CommandCenterActions

export const useCommandCenterStore = create<CommandCenterStore>()(
  persist(
    (set) => ({
      ...INITIAL,

      applyPreset: (preset) => {
        const p = PRESETS[preset]
        set((s) => ({ ...s, ...p, preset, sections: p.sections!.slice(), sizes: {} }))
      },

      toggleSection: (scope) => {
        set((s) => {
          const i = s.sections.indexOf(scope)
          const sections = i > -1
            ? s.sections.filter((x) => x !== scope)
            : [...s.sections, scope]
          return { ...s, sections, preset: 'custom', sizes: {} }
        })
      },

      addAnySection: () => {
        set((s) => {
          const missing = (['feature', 'project', 'global'] as BoardScope[])
            .find((x) => s.sections.indexOf(x) < 0)
          if (!missing) return s
          return { ...s, sections: [...s.sections, missing], preset: 'custom' }
        })
      },

      toggleDirection: () => {
        set((s) => ({
          ...s,
          direction: (s.direction === 'row' ? 'column' : 'row') as Direction,
          sizes: {},
        }))
      },

      setMainFeature: (fid) => {
        set((s) => ({
          ...s,
          mainFeature: fid,
          sections: s.sections.indexOf('feature') < 0 ? [...s.sections, 'feature'] : s.sections,
        }))
      },

      openFeatureFromRail: (fid) => {
        set((s) => ({
          ...s,
          mainFeature: fid,
          openFeature: fid,
          sidebarCollapsed: false,
          sections: s.sections.indexOf('feature') < 0 ? [...s.sections, 'feature'] : s.sections,
        }))
      },

      toggleOpenFeature: (fid) => {
        set((s) => ({ ...s, openFeature: s.openFeature === fid ? null : fid }))
      },

      toggleSidebar: () => {
        set((s) => ({ ...s, sidebarCollapsed: !s.sidebarCollapsed }))
      },

      setSize: (scope, px) => {
        set((s) => ({ ...s, sizes: { ...s.sizes, [scope]: px } }))
      },
    }),
    {
      name: 'pathly-command-center-layout',
    },
  ),
)
