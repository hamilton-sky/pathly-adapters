import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { PathlyItem, ProjectEntry } from '../types'

interface StudioStore {
  selectedItem: PathlyItem | null
  activePanel: 'editor' | 'flow' | 'monitor'
  sidebarCollapsed: boolean
  projectPath: string
  projects: ProjectEntry[]
  activeTopic: string | null
  dirtyItems: Set<string>
  setSelectedItem: (item: PathlyItem | null) => void
  setActivePanel: (panel: StudioStore['activePanel']) => void
  setSidebarCollapsed: (v: boolean) => void
  setProjectPath: (p: string) => void
  setActiveTopic: (t: string | null) => void
  markDirty: (path: string) => void
  clearDirty: (path: string) => void
  addProject: (p: ProjectEntry) => void
  removeProject: (path: string) => void
  updateProject: (path: string, patch: Partial<ProjectEntry>) => void
}

export const useStore = create<StudioStore>()(
  persist(
    (set) => ({
      // Non-persisted state
      selectedItem: null,
      activePanel: 'editor',
      projectPath: '',
      activeTopic: null,
      dirtyItems: new Set<string>(),

      // Persisted state
      sidebarCollapsed: false,
      projects: [],

      setSelectedItem: (item) => set({ selectedItem: item }),
      setActivePanel: (panel) => set({ activePanel: panel }),
      setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
      setProjectPath: (p) => set({ projectPath: p }),
      setActiveTopic: (t) => set({ activeTopic: t }),

      markDirty: (path) =>
        set((s) => {
          const next = new Set(s.dirtyItems)
          next.add(path)
          return { dirtyItems: next }
        }),

      clearDirty: (path) =>
        set((s) => {
          const next = new Set(s.dirtyItems)
          next.delete(path)
          return { dirtyItems: next }
        }),

      addProject: (p) =>
        set((s) => {
          const exists = s.projects.some((x) => x.path === p.path)
          if (exists) return {}
          return { projects: [...s.projects, p] }
        }),

      removeProject: (path) =>
        set((s) => ({ projects: s.projects.filter((p) => p.path !== path) })),

      updateProject: (path, patch) =>
        set((s) => ({
          projects: s.projects.map((p) => (p.path === path ? { ...p, ...patch } : p))
        }))
    }),
    {
      name: 'pathly-studio',
      partialize: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        projects: state.projects
      }),
      // Set must be serialized/deserialized manually
      storage: {
        getItem: (name) => {
          const raw = localStorage.getItem(name)
          if (!raw) return null
          return JSON.parse(raw)
        },
        setItem: (name, value) => {
          localStorage.setItem(name, JSON.stringify(value))
        },
        removeItem: (name) => {
          localStorage.removeItem(name)
        }
      }
    }
  )
)
