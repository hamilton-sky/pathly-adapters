import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { FlowSession } from '../types'

function loadUserLockedPaths(): Set<string> {
  try {
    const saved = localStorage.getItem('pathly:userLockedPaths')
    return new Set(saved ? (JSON.parse(saved) as string[]) : [])
  } catch { return new Set() }
}

function loadUserLockedFolders(): Set<string> {
  try {
    const saved = localStorage.getItem('pathly:userLockedFolders')
    return new Set(saved ? (JSON.parse(saved) as string[]) : [])
  } catch { return new Set() }
}

function loadLastUsedFlowPath(): string | null {
  try {
    return localStorage.getItem('pathly:lastUsedFlowPath')
  } catch { return null }
}

export interface UiState {
  sidebarCollapsed: boolean
  activePanel: 'plan' | 'editor' | 'flow' | 'monitor' | 'settings'
  dirtyItems: Set<string>
  theme: 'dark' | 'light'
  userLockedPaths: Set<string>
  userLockedFolders: Set<string>
  activeFlowSessions: Record<string, FlowSession>
  activeMonitorTab: string | null
  lastUsedFlowPath: string | null
  setSidebarCollapsed: (v: boolean) => void
  setActivePanel: (p: 'plan' | 'editor' | 'flow' | 'monitor' | 'settings') => void
  markDirty: (path: string) => void
  clearDirty: (path: string) => void
  setTheme: (t: 'dark' | 'light') => void
  toggleUserLock: (path: string) => void
  toggleFolderLock: (path: string) => void
  setActiveFlowSessions: (updater: (prev: Record<string, FlowSession>) => Record<string, FlowSession>) => void
  setActiveMonitorTab: (tab: string | null) => void
  setLastUsedFlowPath: (p: string | null) => void
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      activePanel: 'monitor',
      dirtyItems: new Set(),
      theme: 'dark',
      userLockedPaths: loadUserLockedPaths(),
      userLockedFolders: loadUserLockedFolders(),
      activeFlowSessions: {},
      activeMonitorTab: null,
      lastUsedFlowPath: loadLastUsedFlowPath(),
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
      toggleFolderLock: (path) =>
        set((s) => {
          const next = new Set(s.userLockedFolders)
          if (next.has(path)) next.delete(path)
          else next.add(path)
          try { localStorage.setItem('pathly:userLockedFolders', JSON.stringify([...next])) } catch {}
          return { userLockedFolders: next }
        }),
      setActiveFlowSessions: (updater) =>
        set((s) => ({ activeFlowSessions: updater(s.activeFlowSessions) })),
      setActiveMonitorTab: (tab) => set({ activeMonitorTab: tab }),
      setLastUsedFlowPath: (p) => {
        try {
          if (p === null) {
            localStorage.removeItem('pathly:lastUsedFlowPath')
          } else {
            localStorage.setItem('pathly:lastUsedFlowPath', p)
          }
        } catch {}
        set({ lastUsedFlowPath: p })
      },
    }),
    {
      name: 'pathly-studio-ui',
      partialize: (s) => ({ sidebarCollapsed: s.sidebarCollapsed, theme: s.theme }),
    }
  )
)
