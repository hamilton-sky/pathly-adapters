import { useState, useCallback } from 'react'

export type ViewMode = 'cards' | 'list'

const STORAGE_KEY = 'pathly.diffViewMode'

/**
 * Persisted view-mode toggle. Remembers the user's last choice in
 * localStorage so the viewer reopens in the layout they last used.
 */
export function useViewMode(initial: ViewMode = 'cards'): [ViewMode, (v: ViewMode) => void] {
  const [mode, setMode] = useState<ViewMode>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      return saved === 'cards' || saved === 'list' ? saved : initial
    } catch {
      return initial
    }
  })

  const set = useCallback((v: ViewMode) => {
    setMode(v)
    try {
      localStorage.setItem(STORAGE_KEY, v)
    } catch {
      /* ignore quota / disabled storage */
    }
  }, [])

  return [mode, set]
}
