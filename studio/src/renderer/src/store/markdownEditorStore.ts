import { create } from 'zustand'
import { useProjectStore } from './projectStore'

export interface BodyCell {
  id: string
  type: 'body'
  heading: string
  /** markdown heading level (# count). 0 = preamble/no heading. Preserved on save. */
  headingLevel?: number
  content: string
  /** true = loaded from the original skill file; cannot be deleted, only reverted */
  isSystem?: boolean
  /** snapshot of content at load time — used by revertBodyCell */
  originalContent?: string
}

export interface FragmentCell {
  id: string
  type: 'fragment'
  fragmentName: string
  category: string
  description: string
  path?: string
}

export type MarkdownEditorCell = BodyCell | FragmentCell

interface MarkdownEditorState {
  cells: MarkdownEditorCell[]
  history: MarkdownEditorCell[][]
  historyIndex: number
  /** historyIndex at the time of the last successful save (or initial load) */
  savedHistoryIndex: number
  featurePath: string | null
  compositionKey: string
  /** Verbatim YAML frontmatter block from the loaded file — preserved byte-for-byte on save */
  frontmatterRaw: string
  /** Path of the last skill successfully loaded into the store — used to skip redundant reloads */
  lastAppliedPath: string | null
  previewSections: Array<{ heading: string; content: string; origin: 'body' | 'fragment' }>
  previewTokens: number
  previewLoading: boolean
  pushCells: (cells: MarkdownEditorCell[]) => void
  undo: () => void
  redo: () => void
  /** Call after a successful save or after loadSkill to mark the current state as clean */
  markCellsSaved: () => void
  /** Reset lastAppliedPath to force a reload on next canvas mount (e.g. after source-mode save) */
  resetLastAppliedPath: () => void
  setFeaturePath: (path: string | null) => void
  setPreview: (sections: Array<{ heading: string; content: string; origin: 'body' | 'fragment' }>, tokens: number) => void
  setPreviewLoading: (loading: boolean) => void
  loadSkill: (skillPath: string) => Promise<void>
  insertFragment: (fragmentName: string, afterCellId: string | null, path?: string) => string
  insertBodyCell: (heading: string, content: string, afterCellId: string | null) => string
  removeCell: (cellId: string) => void
  duplicateCell: (cellId: string) => void
  moveCell: (cellId: string, afterCellId: string | null) => void
  updateBodyCell: (cellId: string, content: string, heading?: string) => void
  revertBodyCell: (cellId: string) => void
  splitBodyCell: (cellId: string, newCells: Array<{ heading: string; content: string }>) => void
}

export const useMarkdownEditorStore = create<MarkdownEditorState>((set, get) => ({
  cells: [],
  history: [],
  historyIndex: -1,
  savedHistoryIndex: -1,
  featurePath: null,
  lastAppliedPath: null,
  compositionKey: '',
  frontmatterRaw: '',
  previewSections: [],
  previewTokens: 0,
  previewLoading: false,
  pushCells: (cells) => {
    const state = get()
    const newHistory = state.history.slice(0, state.historyIndex + 1)
    if (newHistory.length >= 50) newHistory.shift()
    newHistory.push(cells)
    set({ cells, history: newHistory, historyIndex: newHistory.length - 1 })
  },
  undo: () => {
    const { historyIndex, history } = get()
    if (historyIndex <= 0) return
    const newIndex = historyIndex - 1
    set({ cells: history[newIndex], historyIndex: newIndex })
  },
  redo: () => {
    const { historyIndex, history } = get()
    if (historyIndex >= history.length - 1) return
    const newIndex = historyIndex + 1
    set({ cells: history[newIndex], historyIndex: newIndex })
  },
  markCellsSaved: () => set({ savedHistoryIndex: get().historyIndex }),
  resetLastAppliedPath: () => set({ lastAppliedPath: null }),
  setFeaturePath: (path) => set({ featurePath: path }),
  setPreview: (sections, tokens) => set({ previewSections: sections, previewTokens: tokens, previewLoading: false }),
  setPreviewLoading: (loading) => set({ previewLoading: loading }),
  loadSkill: async (skillPath: string) => {
    // Skip if the same path was already loaded — prevents re-loading when the notebook
    // canvas remounts after a view-mode switch (which would wipe manually inserted cells).
    if (skillPath === get().lastAppliedPath) return
    try {
      const { apiFetch } = await import('../lib/config')
      const res = await apiFetch('/skills/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill_path: skillPath, project_root: useProjectStore.getState().projectPath }),
      })
      const data = await res.json() as {
        body_cells: Array<{ id: string; heading: string; headingLevel?: number; content: string }>
        fragment_cells?: Array<{ id: string; fragmentName: string; category: string; description: string }>
        composition_key: string
        frontmatter?: string
      }
      const bodyCells: BodyCell[] = data.body_cells.map(bc => ({
        id: bc.id,
        type: 'body',
        heading: bc.heading,
        headingLevel: bc.headingLevel ?? 2,
        content: bc.content,
        isSystem: true,
        originalContent: bc.content,
      }))
      const fragmentCells: FragmentCell[] = (data.fragment_cells ?? []).map(fc => ({
        id: fc.id,
        type: 'fragment',
        fragmentName: fc.fragmentName,
        category: fc.category,
        description: fc.description,
      }))
      // Start a FRESH, file-scoped history. Do NOT append via pushCells — the history
      // stack is global to the store, so appending would let undo/redo walk back into a
      // previously-opened file's cells (showing file A's content under file B's title).
      // Resetting here scopes undo/redo to edits within the current file only.
      const initialCells = [...bodyCells, ...fragmentCells]
      set({
        compositionKey: data.composition_key ?? '',
        frontmatterRaw: data.frontmatter ?? '',
        lastAppliedPath: skillPath,
        cells: initialCells,
        history: [initialCells],
        historyIndex: 0,
        savedHistoryIndex: 0,
      })
    } catch {
      get().setPreviewLoading(false)
    }
  },
  insertBodyCell: (heading: string, content: string, afterCellId: string | null) => {
    const state = get()
    const newCell: BodyCell = {
      id: crypto.randomUUID(),
      type: 'body',
      heading,
      headingLevel: 2,
      content,
      isSystem: false,
      originalContent: '',
    }
    const newCells = afterCellId === null
      ? [newCell, ...state.cells]
      : (() => {
          const idx = state.cells.findIndex(c => c.id === afterCellId)
          const next = [...state.cells]
          next.splice(idx + 1, 0, newCell)
          return next
        })()
    get().pushCells(newCells)
    return newCell.id
  },
  insertFragment: (fragmentName: string, afterCellId: string | null, path?: string) => {
    const state = get()
    const newCell: FragmentCell = {
      id: crypto.randomUUID(),
      type: 'fragment',
      fragmentName,
      category: '',
      description: '',
      path,
    }
    const newCells = afterCellId === null
      ? [newCell, ...state.cells]
      : (() => {
          const idx = state.cells.findIndex(c => c.id === afterCellId)
          const next = [...state.cells]
          next.splice(idx + 1, 0, newCell)
          return next
        })()
    get().pushCells(newCells)
    return newCell.id
  },
  removeCell: (cellId: string) => {
    const state = get()
    const cell = state.cells.find(c => c.id === cellId)
    // System body cells cannot be deleted — only reverted (use revertBodyCell)
    if (!cell || (cell.type === 'body' && cell.isSystem === true)) return
    const newCells = state.cells.filter(c => c.id !== cellId)
    get().pushCells(newCells)
  },
  duplicateCell: (cellId: string) => {
    const state = get()
    const idx = state.cells.findIndex(c => c.id === cellId)
    if (idx === -1) return
    const cell = state.cells[idx]
    // A duplicate is always an editable, user-owned copy (never a system cell)
    const clone: MarkdownEditorCell = cell.type === 'body'
      ? { ...cell, id: crypto.randomUUID(), isSystem: false, originalContent: '' }
      : { ...cell, id: crypto.randomUUID() }
    const next = [...state.cells]
    next.splice(idx + 1, 0, clone)
    get().pushCells(next)
  },
  moveCell: (cellId: string, afterCellId: string | null) => {
    const state = get()
    const cell = state.cells.find(c => c.id === cellId)
    if (!cell) return
    const without = state.cells.filter(c => c.id !== cellId)
    let newCells: MarkdownEditorCell[]
    if (afterCellId === null) {
      newCells = [cell, ...without]
    } else {
      const idx = without.findIndex(c => c.id === afterCellId)
      const next = [...without]
      next.splice(idx + 1, 0, cell)
      newCells = next
    }
    get().pushCells(newCells)
  },
  updateBodyCell: (cellId: string, content: string, heading?: string) => {
    const state = get()
    const newCells = state.cells.map(c =>
      c.id === cellId && c.type === 'body'
        ? { ...c, content, ...(heading !== undefined ? { heading } : {}) }
        : c
    )
    get().pushCells(newCells)
  },
  revertBodyCell: (cellId: string) => {
    const state = get()
    const newCells = state.cells.map(c =>
      c.id === cellId && c.type === 'body' && c.isSystem
        ? { ...c, content: c.originalContent ?? c.content }
        : c
    )
    get().pushCells(newCells)
  },
  splitBodyCell: (cellId: string, newCells: Array<{ heading: string; content: string }>) => {
    const state = get()
    const idx = state.cells.findIndex(c => c.id === cellId)
    if (idx === -1) return
    const replacements: BodyCell[] = newCells.map(nc => ({
      id: crypto.randomUUID(),
      type: 'body',
      heading: nc.heading,
      headingLevel: 2,
      content: nc.content,
      isSystem: false,
      originalContent: '',
    }))
    const next = [...state.cells]
    next.splice(idx, 1, ...replacements)
    get().pushCells(next)
  },
}))
