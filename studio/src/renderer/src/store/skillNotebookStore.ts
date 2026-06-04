import { create } from 'zustand'

export interface BodyCell {
  id: string
  type: 'body'
  heading: string
  content: string
}

export interface FragmentCell {
  id: string
  type: 'fragment'
  fragmentName: string
  category: string
  description: string
}

export type NotebookCell = BodyCell | FragmentCell

interface SkillNotebookState {
  cells: NotebookCell[]
  history: NotebookCell[][]
  historyIndex: number
  featurePath: string | null
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
  insertFragment: (fragmentName: string, afterCellId: string | null) => void
  removeCell: (cellId: string) => void
  moveCell: (cellId: string, afterCellId: string | null) => void
}

export const useSkillNotebookStore = create<SkillNotebookState>((set, get) => ({
  cells: [],
  history: [],
  historyIndex: -1,
  featurePath: null,
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
      const data = await res.json() as { body_cells: Array<{ id: string; heading: string; content: string }>; composition_key: string }
      const bodyCells: BodyCell[] = data.body_cells.map(bc => ({
        id: bc.id,
        type: 'body',
        heading: bc.heading,
        content: bc.content,
      }))
      get().pushCells(bodyCells)
    } catch {
      get().setPreviewLoading(false)
    }
  },
  insertFragment: (fragmentName: string, afterCellId: string | null) => {
    const state = get()
    const newCell: FragmentCell = {
      id: crypto.randomUUID(),
      type: 'fragment',
      fragmentName,
      category: '',
      description: '',
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
  },
  removeCell: (cellId: string) => {
    const state = get()
    const cell = state.cells.find(c => c.id === cellId)
    if (!cell || cell.type === 'body') return
    const newCells = state.cells.filter(c => c.id !== cellId)
    get().pushCells(newCells)
  },
  moveCell: (cellId: string, afterCellId: string | null) => {
    const state = get()
    const cell = state.cells.find(c => c.id === cellId)
    if (!cell || cell.type === 'body') return
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
}))
