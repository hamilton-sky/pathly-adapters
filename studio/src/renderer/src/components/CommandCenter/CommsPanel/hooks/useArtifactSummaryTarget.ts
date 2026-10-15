import { useCallback, useEffect, useState } from 'react'
import {
  apiGetDefaultSelection,
  apiSetDefaultSelection,
  apiGetDefaultStyle,
  apiSetDefaultStyle,
  SUMMARY_STYLE_DEFAULT,
  type SummaryStyle,
} from '../../../../store/commsApi'
import { DEFAULT_SUMMARY_SELECTION, type AiSelection } from '../../../../services/aiRouter'

// useArtifactSummaryTarget — owns the artifact-summary AI target AND depth for the panel.
//
// Seeds from the app-defaults (apiGetDefaultSelection / apiGetDefaultStyle); when the
// target is unset it falls back to the built-in local model (DEFAULT_SUMMARY_SELECTION —
// free; a CLI engine is the user's explicit pick). The depth falls back to topic-map.
// Persists every change back as the app default so the choices survive reloads. The dropped/uploaded summary flow reads `selection` + `style`
// from here; the ArtifactsView toolbar drives `setSelection` / `setStyle`.

export function useArtifactSummaryTarget(): {
  selection: AiSelection
  setSelection: (sel: AiSelection) => void
  style: SummaryStyle
  setStyle: (style: SummaryStyle) => void
} {
  const [selection, setSel] = useState<AiSelection>(DEFAULT_SUMMARY_SELECTION)
  const [style, setStyleState] = useState<SummaryStyle>(SUMMARY_STYLE_DEFAULT)

  useEffect(() => {
    let alive = true
    void apiGetDefaultSelection().then((stored) => { if (alive && stored) setSel(stored) })
    void apiGetDefaultStyle().then((stored) => { if (alive && stored) setStyleState(stored) })
    return () => { alive = false }
  }, [])

  const setSelection = useCallback((sel: AiSelection) => {
    setSel(sel)
    // Persist as the app default (best-effort). Off is a valid stored default.
    void apiSetDefaultSelection(sel)
  }, [])

  const setStyle = useCallback((next: SummaryStyle) => {
    setStyleState(next)
    void apiSetDefaultStyle(next)
  }, [])

  return { selection, setSelection, style, setStyle }
}
