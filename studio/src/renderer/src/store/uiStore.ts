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

/** Lifecycle status of a notebook one-shot AI action (AI Split / AI Analyze / Diagram). */
export type MdEditorActionStatus = 'idle' | 'running' | 'success' | 'error'

/** Per-file, per-action run state. The single source of truth for an in-flight run. */
export interface MdEditorActionSlot {
  status: MdEditorActionStatus
  /** Terminal tab id of the running PTY (present while running). */
  tabId?: string
  /** Set true when the user requested a stop, so this run's onExit reports "stopped" not "done". */
  stopping?: boolean
}

export interface MdEditorActionRecord {
  split?: MdEditorActionSlot
  analyze?: MdEditorActionSlot
  // ── Diagram feature ──
  diagram?: MdEditorActionSlot
}

/** Editor one-shot action keys (widened from 'split' | 'analyze' for the Diagram feature). */
export type MdEditorAction = 'split' | 'analyze' | 'diagram'

export interface UiState {
  sidebarCollapsed: boolean
  /** Which tab the expanded sidebar shows — persisted to localStorage 'pathly:sidebarTab' */
  sidebarTab: 'library' | 'workspace'
  activePanel: 'plan' | 'editor' | 'flow' | 'monitor' | 'settings' | 'markdown-editor' | 'db-explorer' | 'command-center'
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
  mdEditorPath: string | null
  mdEditorViewMode: 'cells' | 'editor'
  mdEditorPreviewOpen: boolean
  /** AI-Split draft paths per notebook file — keyed by mdEditorPath. Comment drafts
   *  are tracked locally in the Editor, so the store carries only the split draft. */
  mdEditorSplitDraftPaths: Record<string, string>
  /** Analysis file paths per notebook file — keyed by mdEditorPath */
  mdEditorAnalysisPaths: Record<string, string>
  mdEditorAnalysisPanelOpen: boolean
  // ── Diagram feature: sidecar paths per notebook file + gallery panel flag ──
  /** Diagram sidecar (`<file>.diagrams.json`) paths per notebook file — keyed by mdEditorPath */
  mdEditorDiagramPaths: Record<string, string>
  mdEditorDiagramPanelOpen: boolean
  setMdEditorDiagramPanelOpen: (v: boolean) => void
  setMdEditorDiagramPath: (p: string | null, forFile?: string, opts?: { open?: boolean }) => void
  /** Per-file, per-action run state — single source of truth for in-flight AI actions */
  mdEditorActions: Record<string, MdEditorActionRecord>
  setMdEditorAnalysisPanelOpen: (v: boolean) => void
  /** Increment to request the embedded source editor to save */
  mdEditorSaveRequested: number
  /** Increment to request the embedded source editor to open its draft diff viewer */
  mdEditorOpenDraftRequested: number
  /** Increment to request the embedded source editor to undo */
  mdEditorUndoRequested: number
  /** Increment to request the embedded source editor to redo */
  mdEditorRedoRequested: number
  setSidebarCollapsed: (v: boolean) => void
  setSidebarTab: (tab: 'library' | 'workspace') => void
  setMdEditorViewMode: (mode: 'cells' | 'editor') => void
  toggleMdEditorPreview: () => void
  setMdEditorSplitDraftPath: (p: string | null, forFile?: string) => void
  setMdEditorAnalysisPath: (p: string | null, forFile?: string) => void
  /** Merge a patch into a file's action slot; pass null to clear the slot. */
  setMdEditorAction: (filePath: string, action: MdEditorAction, patch: Partial<MdEditorActionSlot> | null) => void
  requestMdEditorSave: () => void
  requestMdEditorOpenDraft: () => void
  requestMdEditorUndo: () => void
  requestMdEditorRedo: () => void
  setActivePanel: (p: 'plan' | 'editor' | 'flow' | 'monitor' | 'settings' | 'markdown-editor' | 'db-explorer' | 'command-center') => void
  setMdEditorPath: (path: string | null) => void
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
      activePanel: 'command-center',
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
      mdEditorPath: null,
      mdEditorViewMode: 'cells',
      mdEditorPreviewOpen: true,
      mdEditorSplitDraftPaths: {},
      mdEditorAnalysisPaths: {},
      mdEditorAnalysisPanelOpen: false,
      // ── Diagram feature ──
      mdEditorDiagramPaths: {},
      mdEditorDiagramPanelOpen: false,
      mdEditorActions: {},
      mdEditorSaveRequested: 0,
      mdEditorOpenDraftRequested: 0,
      mdEditorUndoRequested: 0,
      mdEditorRedoRequested: 0,
      setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
      setSidebarTab: (tab) => {
        try { localStorage.setItem('pathly:sidebarTab', tab) } catch {}
        set({ sidebarTab: tab })
      },
      toggleMdEditorPreview: () => set((s) => ({ mdEditorPreviewOpen: !s.mdEditorPreviewOpen })),
      setMdEditorSplitDraftPath: (p, forFile) => set((s) => {
        const key = forFile ?? s.mdEditorPath ?? ''
        if (!key) return {}
        if (p === null) {
          const next = { ...s.mdEditorSplitDraftPaths }
          delete next[key]
          return { mdEditorSplitDraftPaths: next }
        }
        return { mdEditorSplitDraftPaths: { ...s.mdEditorSplitDraftPaths, [key]: p } }
      }),
      setMdEditorAnalysisPath: (p, forFile) => set((s) => {
        const key = forFile ?? s.mdEditorPath ?? ''
        if (!key) return {}
        if (p === null) {
          const next = { ...s.mdEditorAnalysisPaths }
          delete next[key]
          return { mdEditorAnalysisPaths: next }
        }
        const update: Partial<UiState> = {
          mdEditorAnalysisPaths: { ...s.mdEditorAnalysisPaths, [key]: p },
          // Only auto-open the report panel when the finished run is for the file the user
          // is currently viewing — a background file's completion must not pop a panel here.
          ...(key === s.mdEditorPath ? { mdEditorAnalysisPanelOpen: true } : {}),
        }
        return update
      }),
      // ── Diagram feature: mirror of setMdEditorAnalysisPath ──
      setMdEditorDiagramPath: (p, forFile, opts) => set((s) => {
        const key = forFile ?? s.mdEditorPath ?? ''
        if (!key) return {}
        if (p === null) {
          const next = { ...s.mdEditorDiagramPaths }
          delete next[key]
          return { mdEditorDiagramPaths: next }
        }
        // `open` defaults true: a finished run pops the gallery. On-open hydration passes
        // open:false — it lights up the header chip without covering the editor.
        const open = opts?.open ?? true
        const update: Partial<UiState> = {
          mdEditorDiagramPaths: { ...s.mdEditorDiagramPaths, [key]: p },
          ...(open && key === s.mdEditorPath ? { mdEditorDiagramPanelOpen: true } : {}),
        }
        return update
      }),
      setMdEditorDiagramPanelOpen: (v) => set({ mdEditorDiagramPanelOpen: v }),
      setMdEditorAction: (filePath, action, patch) =>
        set((s) => {
          if (!filePath) return {}
          const record = s.mdEditorActions[filePath] ?? {}
          if (patch === null) {
            const { [action]: _omit, ...restActions } = record
            if (Object.keys(restActions).length === 0) {
              const { [filePath]: _drop, ...restFiles } = s.mdEditorActions
              return { mdEditorActions: restFiles }
            }
            return { mdEditorActions: { ...s.mdEditorActions, [filePath]: restActions } }
          }
          const prevSlot: MdEditorActionSlot = record[action] ?? { status: 'idle' }
          const nextSlot: MdEditorActionSlot = { ...prevSlot, ...patch }
          return { mdEditorActions: { ...s.mdEditorActions, [filePath]: { ...record, [action]: nextSlot } } }
        }),
      setMdEditorAnalysisPanelOpen: (v) => set({ mdEditorAnalysisPanelOpen: v }),
      requestMdEditorSave: () => set((s) => ({ mdEditorSaveRequested: s.mdEditorSaveRequested + 1 })),
      requestMdEditorOpenDraft: () => set((s) => ({ mdEditorOpenDraftRequested: s.mdEditorOpenDraftRequested + 1 })),
      requestMdEditorUndo: () => set((s) => ({ mdEditorUndoRequested: s.mdEditorUndoRequested + 1 })),
      requestMdEditorRedo: () => set((s) => ({ mdEditorRedoRequested: s.mdEditorRedoRequested + 1 })),
      setActivePanel: (p) => set({ activePanel: p }),
      setMdEditorPath: (path) => set((s) => ({
        mdEditorPath: path,
        ...(path !== s.mdEditorPath ? { mdEditorAnalysisPanelOpen: false } : {}),
        // ── Diagram feature: close the gallery on file switch, same as the report panel ──
        ...(path !== s.mdEditorPath ? { mdEditorDiagramPanelOpen: false } : {}),
      })),
      setMdEditorViewMode: (mode) => set({ mdEditorViewMode: mode }),
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
      partialize: (s) => ({ sidebarCollapsed: s.sidebarCollapsed, theme: s.theme, preferredDark: s.preferredDark, preferredLight: s.preferredLight, mdEditorPreviewOpen: s.mdEditorPreviewOpen }),
    }
  )
)

export const selectMdEditorSplitDraftPath = (s: UiState): string | null =>
  s.mdEditorSplitDraftPaths[s.mdEditorPath ?? ''] ?? null

export const selectMdEditorAnalysisPath = (s: UiState): string | null =>
  s.mdEditorAnalysisPaths[s.mdEditorPath ?? ''] ?? null

export const selectMdEditorSplit = (s: UiState): MdEditorActionSlot | undefined =>
  s.mdEditorActions[s.mdEditorPath ?? '']?.split

export const selectMdEditorAnalyze = (s: UiState): MdEditorActionSlot | undefined =>
  s.mdEditorActions[s.mdEditorPath ?? '']?.analyze

// ── Diagram feature selectors ──
export const selectMdEditorDiagramPath = (s: UiState): string | null =>
  s.mdEditorDiagramPaths[s.mdEditorPath ?? ''] ?? null

export const selectMdEditorDiagram = (s: UiState): MdEditorActionSlot | undefined =>
  s.mdEditorActions[s.mdEditorPath ?? '']?.diagram
