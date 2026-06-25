import { useCallback, useEffect, useState } from 'react'
import { apiGetDefaultSelection, apiSetDefaultSelection } from '../../../../store/commsApi'
import { type AiSelection } from '../../../../services/aiRouter'
import { RECOMMENDED_MODEL_ID } from '../../../../services/modelManager'

// useArtifactSummaryTarget — owns the artifact-summary AI target for the panel.
//
// Seeds from the app-default (apiGetDefaultSelection); when unset, falls back to a
// built-in (the recommended local model). Persists every change back as the app
// default so the choice survives reloads. The dropped/uploaded summary flow reads
// `selection` from here; the ArtifactsView toolbar selector drives `setSelection`.

/** Built-in fallback when no app-default selection is stored yet. */
const BUILTIN_DEFAULT: AiSelection = { type: 'model', id: RECOMMENDED_MODEL_ID }

export function useArtifactSummaryTarget(): {
  selection: AiSelection
  setSelection: (sel: AiSelection) => void
} {
  const [selection, setSel] = useState<AiSelection>(BUILTIN_DEFAULT)

  useEffect(() => {
    let alive = true
    void apiGetDefaultSelection().then((stored) => {
      if (alive && stored) setSel(stored)
    })
    return () => { alive = false }
  }, [])

  const setSelection = useCallback((sel: AiSelection) => {
    setSel(sel)
    // Persist as the app default (best-effort). Off is a valid stored default.
    void apiSetDefaultSelection(sel)
  }, [])

  return { selection, setSelection }
}
