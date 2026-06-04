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
}))
