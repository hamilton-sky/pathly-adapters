import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UiState {
  sidebarCollapsed: boolean
  activePanel: 'plan' | 'editor' | 'flow' | 'monitor' | 'settings'
  dirtyItems: Set<string>
  theme: 'dark' | 'light'
  setSidebarCollapsed: (v: boolean) => void
  setActivePanel: (p: 'plan' | 'editor' | 'flow' | 'monitor' | 'settings') => void
  markDirty: (path: string) => void
  clearDirty: (path: string) => void
  setTheme: (t: 'dark' | 'light') => void
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      activePanel: 'plan',
      dirtyItems: new Set(),
      theme: 'dark',
      setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
      setActivePanel: (p) => set({ activePanel: p }),
      markDirty: (path) => set((s) => ({ dirtyItems: new Set([...s.dirtyItems, path]) })),
      clearDirty: (path) =>
        set((s) => {
          const d = new Set(s.dirtyItems)
          d.delete(path)
          return { dirtyItems: d }
        }),
      setTheme: (t) => set({ theme: t }),
    }),
    {
      name: 'pathly-studio-ui',
      partialize: (s) => ({ sidebarCollapsed: s.sidebarCollapsed, theme: s.theme }),
    }
  )
)
