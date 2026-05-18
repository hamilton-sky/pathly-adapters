import { create } from 'zustand'

export interface TerminalTab {
  id: string
  label: string
}

export interface TerminalState {
  open: boolean
  tabs: TerminalTab[]
  activeTabId: string | null
  toggle(): void
  addTab(id: string, label: string): void
  closeTab(id: string): void
  setActiveTab(id: string): void
}

export const useTerminalStore = create<TerminalState>()((set) => ({
  open: false,
  tabs: [],
  activeTabId: null,
  toggle: () => set((s) => ({ open: !s.open })),
  addTab: (id, label) =>
    set((s) => ({
      tabs: [...s.tabs, { id, label }],
      activeTabId: id,
    })),
  closeTab: (id) =>
    set((s) => {
      const idx = s.tabs.findIndex((t) => t.id === id)
      const tabs = s.tabs.filter((t) => t.id !== id)
      let activeTabId = s.activeTabId
      if (activeTabId === id) {
        activeTabId = tabs[Math.max(0, idx - 1)]?.id ?? tabs[0]?.id ?? null
      }
      return { tabs, activeTabId }
    }),
  setActiveTab: (id) => set({ activeTabId: id }),
}))
