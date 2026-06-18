import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { FlowSession } from '../types'
import type { ThemeName } from '../theme'

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

function loadSidebarTab(): 'library' | 'workspace' {
  try {
    return localStorage.getItem('pathly:sidebarTab') === 'workspace' ? 'workspace' : 'library'
  } catch { return 'library' }
}

/** Lifecycle status of a notebook one-shot AI action (AI Split / AI Analyze). */
export type NotebookActionStatus = 'idle' | 'running' | 'success' | 'error'

/** Per-file, per-action run state. The single source of truth for an in-flight run. */
export interface NotebookActionSlot {
  status: NotebookActionStatus
  /** Terminal tab id of the running PTY (present while running). */
  tabId?: string
  /** Set true when the user requested a stop, so this run's onExit reports "stopped" not "done". */
  stopping?: boolean
}

export interface NotebookActionRecord {
  split?: NotebookActionSlot
  analyze?: NotebookActionSlot
}

export interface UiState {
  sidebarCollapsed: boolean
  /** Which tab the expanded sidebar shows — persisted to localStorage 'pathly:sidebarTab' */
  sidebarTab: 'library' | 'workspace'
  activePanel: 'plan' | 'editor' | 'flow' | 'monitor' | 'settings' | 'notebook' | 'db-explorer' | 'command-center'
  dirtyItems: Set<string>
  theme: ThemeName
  preferredDark: ThemeName
  preferredLight: ThemeName
  userLockedPaths: Set<string>
  userLockedFolders: Set<string>
  activeFlowSessions: Record<string, FlowSession>
  activeMonitorTab: string | null
  lastUsedFlowPath: string | null
  chatOpen: boolean
  cliMonitorOpen: boolean
  skillsPanelOpen: boolean
  notebookPath: string | null
  notebookViewMode: 'cells' | 'editor'
  notebookPreviewOpen: boolean
  /** Draft paths per notebook file — keyed by notebookPath */
  notebookDraftPaths: Record<string, string>
  /** Analysis file paths per notebook file — keyed by notebookPath */
  notebookAnalysisPaths: Record<string, string>
  notebookAnalysisPanelOpen: boolean
  /** Per-file, per-action run state — single source of truth for in-flight AI actions */
  notebookActions: Record<string, NotebookActionRecord>
  setNotebookAnalysisPanelOpen: (v: boolean) => void
  /** Increment to request the embedded source editor to save */
  notebookSaveRequested: number
  /** Increment to request the embedded source editor to open its draft diff viewer */
  notebookOpenDraftRequested: number
  /** Increment to request the embedded source editor to undo */
  notebookUndoRequested: number
  /** Increment to request the embedded source editor to redo */
  notebookRedoRequested: number
  setSidebarCollapsed: (v: boolean) => void
  setSidebarTab: (tab: 'library' | 'workspace') => void
  setNotebookViewMode: (mode: 'cells' | 'editor') => void
  toggleNotebookPreview: () => void
  setNotebookDraftPath: (p: string | null, forFile?: string) => void
  setNotebookAnalysisPath: (p: string | null, forFile?: string) => void
  /** Merge a patch into a file's action slot; pass null to clear the slot. */
  setNotebookAction: (filePath: string, action: 'split' | 'analyze', patch: Partial<NotebookActionSlot> | null) => void
  requestNotebookSave: () => void
  requestNotebookOpenDraft: () => void
  requestNotebookUndo: () => void
  requestNotebookRedo: () => void
  setActivePanel: (p: 'plan' | 'editor' | 'flow' | 'monitor' | 'settings' | 'notebook' | 'db-explorer' | 'command-center') => void
  setNotebookPath: (path: string | null) => void
  markDirty: (path: string) => void
  clearDirty: (path: string) => void
  setTheme: (t: ThemeName) => void
  setPreferredDark: (t: ThemeName) => void
  setPreferredLight: (t: ThemeName) => void
  toggleUserLock: (path: string) => void
  toggleFolderLock: (path: string) => void
  setActiveFlowSessions: (updater: (prev: Record<string, FlowSession>) => Record<string, FlowSession>) => void
  setActiveMonitorTab: (tab: string | null) => void
  setLastUsedFlowPath: (p: string | null) => void
  toggleChat: () => void
  toggleCliMonitor: () => void
  toggleSkillsPanel: () => void
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      sidebarTab: loadSidebarTab(),
      activePanel: 'monitor',
      dirtyItems: new Set(),
      theme: 'dark',
      preferredDark: 'dark',
      preferredLight: 'light',
      userLockedPaths: loadUserLockedPaths(),
      userLockedFolders: loadUserLockedFolders(),
      activeFlowSessions: {},
      activeMonitorTab: null,
      lastUsedFlowPath: loadLastUsedFlowPath(),
      chatOpen: false,
      cliMonitorOpen: false,
      skillsPanelOpen: true,
      notebookPath: null,
      notebookViewMode: 'cells',
      notebookPreviewOpen: true,
      notebookDraftPaths: {},
      notebookAnalysisPaths: {},
      notebookAnalysisPanelOpen: false,
      notebookActions: {},
      notebookSaveRequested: 0,
      notebookOpenDraftRequested: 0,
      notebookUndoRequested: 0,
      notebookRedoRequested: 0,
      setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
      setSidebarTab: (tab) => {
        try { localStorage.setItem('pathly:sidebarTab', tab) } catch {}
        set({ sidebarTab: tab })
      },
      toggleNotebookPreview: () => set((s) => ({ notebookPreviewOpen: !s.notebookPreviewOpen })),
      setNotebookDraftPath: (p, forFile) => set((s) => {
        const key = forFile ?? s.notebookPath ?? ''
        if (!key) return {}
        if (p === null) {
          const next = { ...s.notebookDraftPaths }
          delete next[key]
          return { notebookDraftPaths: next }
        }
        return { notebookDraftPaths: { ...s.notebookDraftPaths, [key]: p } }
      }),
      setNotebookAnalysisPath: (p, forFile) => set((s) => {
        const key = forFile ?? s.notebookPath ?? ''
        if (!key) return {}
        if (p === null) {
          const next = { ...s.notebookAnalysisPaths }
          delete next[key]
          return { notebookAnalysisPaths: next }
        }
        const update: Partial<UiState> = {
          notebookAnalysisPaths: { ...s.notebookAnalysisPaths, [key]: p },
          // Only auto-open the report panel when the finished run is for the file the user
          // is currently viewing — a background file's completion must not pop a panel here.
          ...(key === s.notebookPath ? { notebookAnalysisPanelOpen: true } : {}),
        }
        return update
      }),
      setNotebookAction: (filePath, action, patch) =>
        set((s) => {
          if (!filePath) return {}
          const record = s.notebookActions[filePath] ?? {}
          if (patch === null) {
            const { [action]: _omit, ...restActions } = record
            if (Object.keys(restActions).length === 0) {
              const { [filePath]: _drop, ...restFiles } = s.notebookActions
              return { notebookActions: restFiles }
            }
            return { notebookActions: { ...s.notebookActions, [filePath]: restActions } }
          }
          const prevSlot: NotebookActionSlot = record[action] ?? { status: 'idle' }
          const nextSlot: NotebookActionSlot = { ...prevSlot, ...patch }
          return { notebookActions: { ...s.notebookActions, [filePath]: { ...record, [action]: nextSlot } } }
        }),
      setNotebookAnalysisPanelOpen: (v) => set({ notebookAnalysisPanelOpen: v }),
      requestNotebookSave: () => set((s) => ({ notebookSaveRequested: s.notebookSaveRequested + 1 })),
      requestNotebookOpenDraft: () => set((s) => ({ notebookOpenDraftRequested: s.notebookOpenDraftRequested + 1 })),
      requestNotebookUndo: () => set((s) => ({ notebookUndoRequested: s.notebookUndoRequested + 1 })),
      requestNotebookRedo: () => set((s) => ({ notebookRedoRequested: s.notebookRedoRequested + 1 })),
      setActivePanel: (p) => set({ activePanel: p }),
      setNotebookPath: (path) => set((s) => ({
        notebookPath: path,
        ...(path !== s.notebookPath ? { notebookAnalysisPanelOpen: false } : {}),
      })),
      setNotebookViewMode: (mode) => set({ notebookViewMode: mode }),
      markDirty: (path) => set((s) => ({ dirtyItems: new Set([...s.dirtyItems, path]) })),
      clearDirty: (path) =>
        set((s) => {
          const d = new Set(s.dirtyItems)
          d.delete(path)
          return { dirtyItems: d }
        }),
      setTheme: (t) => set({ theme: t }),
      setPreferredDark: (t) => set({ preferredDark: t, theme: t }),
      setPreferredLight: (t) => set({ preferredLight: t, theme: t }),
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
      toggleChat: () => set((s) => ({ chatOpen: !s.chatOpen })),
      toggleCliMonitor: () => set((s) => ({ cliMonitorOpen: !s.cliMonitorOpen })),
      toggleSkillsPanel: () => set((s) => ({ skillsPanelOpen: !s.skillsPanelOpen })),
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
      partialize: (s) => ({ sidebarCollapsed: s.sidebarCollapsed, theme: s.theme, preferredDark: s.preferredDark, preferredLight: s.preferredLight, notebookPreviewOpen: s.notebookPreviewOpen }),
    }
  )
)

export const selectNotebookDraftPath = (s: UiState): string | null =>
  s.notebookDraftPaths[s.notebookPath ?? ''] ?? null

export const selectNotebookAnalysisPath = (s: UiState): string | null =>
  s.notebookAnalysisPaths[s.notebookPath ?? ''] ?? null

export const selectNotebookSplit = (s: UiState): NotebookActionSlot | undefined =>
  s.notebookActions[s.notebookPath ?? '']?.split

export const selectNotebookAnalyze = (s: UiState): NotebookActionSlot | undefined =>
  s.notebookActions[s.notebookPath ?? '']?.analyze
