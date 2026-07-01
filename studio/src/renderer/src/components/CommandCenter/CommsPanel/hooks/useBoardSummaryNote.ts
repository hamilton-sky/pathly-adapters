import { useCallback, useEffect, useState } from 'react'

// Per-board "default instruction" for artifact summaries — a free-text request
// (e.g. "always focus on security") appended to every summary run for artifacts
// dropped on THIS board. Unlike the AI target + depth (app-wide defaults), this is
// scoped per board, persisted in localStorage under pathly:summaryNote:<boardKey>,
// so each board keeps its own. Empty string = no default instruction.
export function useBoardSummaryNote(boardKey: string): [string, (v: string) => void] {
  const key = `pathly:summaryNote:${boardKey}`
  const [note, setNoteState] = useState('')

  useEffect(() => {
    try { setNoteState(localStorage.getItem(key) ?? '') } catch { setNoteState('') }
  }, [key])

  const setNote = useCallback((v: string) => {
    setNoteState(v)
    try {
      if (v) localStorage.setItem(key, v)
      else localStorage.removeItem(key)
    } catch { /* storage unavailable — keep the in-memory value */ }
  }, [key])

  return [note, setNote]
}
