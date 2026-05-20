import { create } from 'zustand'
import { persist } from 'zustand/middleware'

function loadUserLockedPaths(): Set<string> {
  try {
    const saved = localStorage.getItem('pathly:userLockedPaths')
    return new Set(saved ? (JSON.parse(saved) as string[]) : [])
  } catch { return new Set() }
}

export interface UiState {
  sidebarCollapsed: boolean
  activePanel: 'plan' | 'editor' | 'flow' | 'monitor' | 'settings'
  dirtyItems: Set<string>
  theme: 'dark' | 'light'
  userLockedPaths: Set<string>
  setSidebarCollapsed: (v: boolean) => void
  setActivePanel: (p: 'plan' | 'editor' | 'flow' | 'monitor' | 'settings') => void
  markDirty: (path: string) => void
  clearDirty: (path: string) => void
  setTheme: (t: 'dark' | 'light') => void
  toggleUserLock: (path: string) => void
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      activePanel: 'monitor',
      dirtyItems: new Set(),
      theme: 'dark',
      userLockedPaths: loadUserLockedPaths(),
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
      toggleUserLock: (path) =>
        set((s) => {
          const next = new Set(s.userLockedPaths)
          if (next.has(path)) next.delete(path)
          else next.add(path)
          try { localStorage.setItem('pathly:userLockedPaths', JSON.stringify([...next])) } catch {}
          return { userLockedPaths: next }
        }),
    }),
    {
      name: 'pathly-studio-ui',
      partialize: (s) => ({ sidebarCollapsed: s.sidebarCollapsed, theme: s.theme }),
    }
  )
)
