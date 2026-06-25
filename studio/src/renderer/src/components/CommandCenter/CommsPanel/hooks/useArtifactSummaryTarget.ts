import { useCallback, useEffect, useState } from 'react'
import { apiGetDefaultSelection, apiSetDefaultSelection } from '../../../../store/commsApi'
import { type AiSelection } from '../../../../services/aiRouter'

// useArtifactSummaryTarget — owns the artifact-summary AI target for the panel.
//
// Seeds from the app-default (apiGetDefaultSelection); when unset, falls back to a
// built-in CLI engine (claude) rather than a local model: an engine self-auths and
// is always available, so summaries work out-of-the-box without requiring the user
// to install/pull a local model first. Persists every change back as the app default
// so the choice survives reloads. The dropped/uploaded summary flow reads `selection`
// from here; the ArtifactsView toolbar selector drives `setSelection`.

/** Built-in fallback when no app-default is stored yet: a CLI engine, always available. */
const BUILTIN_DEFAULT: AiSelection = { type: 'engine', id: 'claude' }

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
