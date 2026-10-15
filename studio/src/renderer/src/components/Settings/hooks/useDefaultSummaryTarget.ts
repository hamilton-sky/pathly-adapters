import { useEffect, useState } from 'react'
import { apiGetDefaultSelection, apiSetDefaultSelection } from '../../../store/commsApi'
import { DEFAULT_SUMMARY_SELECTION, type AiSelection } from '../../../services/aiRouter'

// Loads + persists the app-default AI summary target (the unified AiSelection used
// to summarize .md artifacts added to boards). Seeds from apiGetDefaultSelection()
// on mount — nothing saved shows DEFAULT_SUMMARY_SELECTION, the target summaries
// actually use then — and writes back via apiSetDefaultSelection() on every change. The DTO and
// AiSelection are structurally identical ({ type, id }), so no mapping is needed.
export function useDefaultSummaryTarget(): {
  selection: AiSelection | null
  setSelection: (sel: AiSelection) => void
} {
  const [selection, setSelectionState] = useState<AiSelection | null>(null)

  useEffect(() => {
    let alive = true
    void apiGetDefaultSelection().then((sel) => {
      if (alive) setSelectionState(sel ?? DEFAULT_SUMMARY_SELECTION)
    })
    return () => {
      alive = false
    }
  }, [])

  function setSelection(sel: AiSelection): void {
    setSelectionState(sel)
    void apiSetDefaultSelection(sel)
  }

  return { selection, setSelection }
}
