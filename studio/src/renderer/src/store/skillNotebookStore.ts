import { create } from 'zustand'

export interface BodyCell {
  id: string
  type: 'body'
  heading: string
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

export type NotebookCell = BodyCell | FragmentCell

interface SkillNotebookState {
  cells: NotebookCell[]
  history: NotebookCell[][]
  historyIndex: number
  featurePath: string | null
  compositionKey: string
  previewSections: Array<{ heading: string; content: string; origin: 'body' | 'fragment' }>
  previewTokens: number
  previewLoading: boolean
  pushCells: (cells: NotebookCell[]) => void
  undo: () => void
  redo: () => void
  setFeaturePath: (path: string | null) => void
  setPreview: (sections: Array<{ heading: string; content: string; origin: 'body' | 'fragment' }>, tokens: number) => void
  setPreviewLoading: (loading: boolean) => void
  loadSkill: (skillPath: string) => Promise<void>
  insertFragment: (fragmentName: string, afterCellId: string | null, path?: string) => string
  insertBodyCell: (heading: string, content: string, afterCellId: string | null) => string
  removeCell: (cellId: string) => void
  moveCell: (cellId: string, afterCellId: string | null) => void
  updateBodyCell: (cellId: string, content: string, heading?: string) => void
  revertBodyCell: (cellId: string) => void
  splitBodyCell: (cellId: string, newCells: Array<{ heading: string; content: string }>) => void
}

export const useSkillNotebookStore = create<SkillNotebookState>((set, get) => ({
  cells: [],
  history: [],
  historyIndex: -1,
  featurePath: null,
  compositionKey: '',
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
  setFeaturePath: (path) => set({ featurePath: path }),
  setPreview: (sections, tokens) => set({ previewSections: sections, previewTokens: tokens, previewLoading: false }),
  setPreviewLoading: (loading) => set({ previewLoading: loading }),
  loadSkill: async (skillPath: string) => {
    try {
      const res = await fetch('http://localhost:8765/skills/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill_path: skillPath }),
      })
      const data = await res.json() as {
        body_cells: Array<{ id: string; heading: string; content: string }>
        fragment_cells?: Array<{ id: string; fragmentName: string; category: string; description: string }>
        composition_key: string
      }
      const bodyCells: BodyCell[] = data.body_cells.map(bc => ({
        id: bc.id,
        type: 'body',
        heading: bc.heading,
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
      set({ compositionKey: data.composition_key ?? '' })
      get().pushCells([...bodyCells, ...fragmentCells])
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
  moveCell: (cellId: string, afterCellId: string | null) => {
    const state = get()
    const cell = state.cells.find(c => c.id === cellId)
    if (!cell) return
    const without = state.cells.filter(c => c.id !== cellId)
    let newCells: NotebookCell[]
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
      content: nc.content,
      isSystem: false,
      originalContent: '',
    }))
    const next = [...state.cells]
    next.splice(idx, 1, ...replacements)
    get().pushCells(next)
  },
}))
