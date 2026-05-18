import { create } from 'zustand'

export interface TerminalTab {
  id: string
  label: string
  pane: 'left' | 'right'
}

export interface TerminalState {
  open: boolean
  tabs: TerminalTab[]
  activeTabIdLeft: string | null
  activeTabIdRight: string | null
  splitEnabled: boolean
  toggle(): void
  addTab(id: string, label: string, pane?: 'left' | 'right'): void
  closeTab(id: string): void
  setActiveTab(id: string): void
  renameTab(id: string, label: string): void
  toggleSplit(): void
}

export const useTerminalStore = create<TerminalState>()((set) => ({
  open: false,
  tabs: [],
  activeTabIdLeft: null,
  activeTabIdRight: null,
  splitEnabled: false,

  toggle: () => set((s) => ({ open: !s.open })),

  addTab: (id, label, pane = 'left') =>
    set((s) => {
      const tab: TerminalTab = { id, label, pane }
      const update: Partial<TerminalState> = { tabs: [...s.tabs, tab] }
      if (pane === 'left') update.activeTabIdLeft = id
      else update.activeTabIdRight = id
      return update
    }),

  closeTab: (id) =>
    set((s) => {
      const tab = s.tabs.find((t) => t.id === id)
      const pane = tab?.pane ?? 'left'
      const tabs = s.tabs.filter((t) => t.id !== id)
      const paneTabs = tabs.filter((t) => t.pane === pane)
      const prevActive = pane === 'left' ? s.activeTabIdLeft : s.activeTabIdRight
      const newActive = prevActive === id
        ? (paneTabs[paneTabs.length - 1]?.id ?? null)
        : prevActive
      if (pane === 'left') return { tabs, activeTabIdLeft: newActive }
      return { tabs, activeTabIdRight: newActive }
    }),

  setActiveTab: (id) =>
    set((s) => {
      const tab = s.tabs.find((t) => t.id === id)
      if (!tab) return {}
      if (tab.pane === 'left') return { activeTabIdLeft: id }
      return { activeTabIdRight: id }
    }),

  renameTab: (id, label) =>
    set((s) => ({ tabs: s.tabs.map((t) => t.id === id ? { ...t, label } : t) })),

  toggleSplit: () =>
    set((s) => {
      if (s.splitEnabled) {
        // Collapse: move all right-pane tabs to left
        const tabs = s.tabs.map((t) => ({ ...t, pane: 'left' as const }))
        return { splitEnabled: false, tabs, activeTabIdRight: null }
      }
      return { splitEnabled: true }
    }),
}))
