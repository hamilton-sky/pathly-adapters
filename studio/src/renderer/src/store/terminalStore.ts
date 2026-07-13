import { create } from 'zustand'
import type { TerminalTab } from '../types/terminal'

export type { TerminalTab }
type TerminalKind = NonNullable<TerminalTab['kind']>

export interface SessionRecord {
  id: string
  label: string
  kind?: TerminalTab['kind']
  status: 'done' | 'error'
  startedAt?: number
  finishedAt: number
  lastLines: string[]
  prompt?: string
}

function stripAnsi(s: string): string {
  return s.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '').replace(/\x1b[()][AB012]/g, '').replace(/\x1b[^[\]]/g, '')
}
function snapshotLines(chunks: string[]): string[] {
  return chunks.map(stripAnsi).join('').split('\n').map(l => l.trimEnd()).filter(l => l.length > 0).slice(-8)
}

export interface TerminalState {
  open: boolean
  tabs: TerminalTab[]
  activeTabIdLeft: string | null
  activeTabIdRight: string | null
  splitEnabled: boolean
  hiddenTabIds: Record<string, boolean>
  tabIdByKind: Partial<Record<TerminalKind, string>>
  scrollbackByTabId: Record<string, string[]>
  tabCounter: number
  sessionHistory: SessionRecord[]
  /** Live CLI-engine spawn-scheduler state pushed from the main process. */
  spawnQueue: SpawnState
  toggle(): void
  addTab(id: string, label: string, pane?: 'left' | 'right', kind?: TerminalTab['kind'], plan?: string, stage?: string, prompt?: string): void
  addTabSilent(id: string, label: string, kind?: TerminalTab['kind'], plan?: string, stage?: string, prompt?: string): void
  closeTab(id: string): void
  hideTab(id: string): void
  setActiveTab(id: string): void
  openTab(id: string): void
  renameTab(id: string, label: string): void
  toggleSplit(): void
  rememberTabForKind(kind: TerminalKind, id: string): void
  appendScrollback(tabId: string, chunk: string): void
  clearScrollback(tabId: string): void
  updateTabStatus(id: string, status: TerminalTab['status']): void
  clearSessionHistory(): void
  setSpawnQueue(s: SpawnState): void
}

export const useTerminalStore = create<TerminalState>()((set) => ({
  open: false,
  tabs: [],
  activeTabIdLeft: null,
  activeTabIdRight: null,
  splitEnabled: false,
  hiddenTabIds: {},
  tabIdByKind: {},
  scrollbackByTabId: {},
  tabCounter: 0,
  sessionHistory: [],
  spawnQueue: { running: 0, interactive: 0, total: 0, engines: [], queuedEngines: [], queued: [], paused: false, rateLimitedUntil: 0, caps: { global: 8, headless: 5, interactive: 5 } },

  toggle: () => set((s) => ({ open: !s.open })),

  addTab: (id, label, pane = 'left', kind, plan, stage, prompt) =>
    set((s) => {
      const numericId = s.tabCounter + 1
      const tab: TerminalTab = { id, numericId, label, pane, kind, plan, stage, prompt }
      const update: Partial<TerminalState> = { tabs: [...s.tabs, tab], tabCounter: numericId }
      if (pane === 'left') update.activeTabIdLeft = id
      else update.activeTabIdRight = id
      if (kind) {
        update.tabIdByKind = { ...s.tabIdByKind, [kind]: id }
      }
      return update
    }),

  closeTab: (id) =>
    set((s) => {
      const tab = s.tabs.find((t) => t.id === id)
      const pane = tab?.pane ?? 'left'
      const tabs = s.tabs.filter((t) => t.id !== id)
      const tabIdByKind = { ...s.tabIdByKind }
      if (tab?.kind && tabIdByKind[tab.kind] === id) {
        delete tabIdByKind[tab.kind]
      }

      // Snapshot to history before deleting scrollback
      let sessionHistory = s.sessionHistory
      if (tab && (tab.status === 'done' || tab.status === 'error')) {
        const chunks = s.scrollbackByTabId[id] ?? []
        const record: SessionRecord = {
          id: tab.id,
          label: tab.label,
          kind: tab.kind,
          status: tab.status,
          startedAt: tab.startedAt,
          finishedAt: tab.finishedAt ?? Date.now(),
          lastLines: snapshotLines(chunks),
          prompt: tab.prompt,
        }
        sessionHistory = [record, ...s.sessionHistory].slice(0, 20)
      }

      const scrollbackByTabId = { ...s.scrollbackByTabId }
      delete scrollbackByTabId[id]
      const hiddenTabIds = { ...s.hiddenTabIds }
      delete hiddenTabIds[id]
      const paneTabs = tabs.filter((t) => t.pane === pane && !hiddenTabIds[t.id])
      const prevActive = pane === 'left' ? s.activeTabIdLeft : s.activeTabIdRight
      const newActive = prevActive === id
        ? (paneTabs[paneTabs.length - 1]?.id ?? null)
        : prevActive
      if (pane === 'left') return { tabs, activeTabIdLeft: newActive, tabIdByKind, scrollbackByTabId, hiddenTabIds, sessionHistory }
      return { tabs, activeTabIdRight: newActive, tabIdByKind, scrollbackByTabId, hiddenTabIds, sessionHistory }
    }),

  hideTab: (id) =>
    set((s) => {
      const tab = s.tabs.find((t) => t.id === id)
      if (!tab) return {}
      const hiddenTabIds = { ...s.hiddenTabIds, [id]: true }
      const visiblePaneTabs = s.tabs.filter((t) => t.pane === tab.pane && t.id !== id && !hiddenTabIds[t.id])
      const nextActive = visiblePaneTabs[visiblePaneTabs.length - 1]?.id ?? null
      if (tab.pane === 'left' && s.activeTabIdLeft === id) {
        return { hiddenTabIds, activeTabIdLeft: nextActive }
      }
      if (tab.pane === 'right' && s.activeTabIdRight === id) {
        return { hiddenTabIds, activeTabIdRight: nextActive }
      }
      return { hiddenTabIds }
    }),

  setActiveTab: (id) =>
    set((s) => {
      const tab = s.tabs.find((t) => t.id === id)
      if (!tab) return {}
      const hiddenTabIds = { ...s.hiddenTabIds }
      delete hiddenTabIds[id]
      if (tab.pane === 'left') return { activeTabIdLeft: id, hiddenTabIds }
      return { activeTabIdRight: id, hiddenTabIds }
    }),

  openTab: (id) =>
    set((s) => {
      const tab = s.tabs.find((t) => t.id === id)
      if (!tab) return {}
      const hiddenTabIds = { ...s.hiddenTabIds }
      delete hiddenTabIds[id]
      if (tab.pane === 'left') return { open: true, activeTabIdLeft: id, hiddenTabIds }
      return { open: true, activeTabIdRight: id, hiddenTabIds }
    }),

  renameTab: (id, label) =>
    set((s) => ({ tabs: s.tabs.map((t) => t.id === id ? { ...t, label } : t) })),

  toggleSplit: () =>
    set((s) => {
      if (s.splitEnabled) {
        // Collapse: move all right-pane tabs back to left
        const tabs = s.tabs.map((t) => ({ ...t, pane: 'left' as const }))
        const lastLeft = tabs[tabs.length - 1]?.id ?? null
        return { splitEnabled: false, tabs, activeTabIdLeft: lastLeft ?? s.activeTabIdLeft, activeTabIdRight: null }
      }
      // Split: put first tab left, second tab right (requires 2+ tabs)
      if (s.tabs.length < 2) return { splitEnabled: true }
      const tabs = s.tabs.map((t, i) => ({ ...t, pane: (i === 0 ? 'left' : 'right') as 'left' | 'right' }))
      return {
        splitEnabled: true,
        tabs,
        activeTabIdLeft: tabs[0].id,
        activeTabIdRight: tabs[1].id,
      }
    }),

  addTabSilent: (id, label, kind, plan, stage, prompt) =>
    set((s) => {
      const numericId = s.tabCounter + 1
      const tab: TerminalTab = { id, numericId, label, pane: 'left', kind, plan, stage, prompt }
      const update: Partial<TerminalState> = { tabs: [...s.tabs, tab], tabCounter: numericId }
      if (kind) update.tabIdByKind = { ...s.tabIdByKind, [kind]: id }
      // Does NOT change activeTabIdLeft — mini tabs don't steal focus from the full terminal
      return update
    }),

  rememberTabForKind: (kind, id) =>
    set((s) => ({ tabIdByKind: { ...s.tabIdByKind, [kind]: id } })),

  appendScrollback: (tabId, chunk) =>
    set((s) => ({
      scrollbackByTabId: {
        ...s.scrollbackByTabId,
        [tabId]: [...(s.scrollbackByTabId[tabId] ?? []), chunk].slice(-400),
      },
    })),

  clearScrollback: (tabId) =>
    set((s) => ({
      scrollbackByTabId: {
        ...s.scrollbackByTabId,
        [tabId]: [],
      },
    })),

  updateTabStatus: (id, status) =>
    set((s) => ({
      tabs: s.tabs.map((t) => {
        if (t.id !== id) return t
        const patch: Partial<import('../types/terminal').TerminalTab> = { status }
        if (status === 'running' && t.status !== 'running') patch.startedAt = Date.now()
        if (status === 'done' || status === 'error') patch.finishedAt = Date.now()
        return { ...t, ...patch }
      }),
    })),

  clearSessionHistory: () => set({ sessionHistory: [] }),

  setSpawnQueue: (s) => set({ spawnQueue: s }),
}))
