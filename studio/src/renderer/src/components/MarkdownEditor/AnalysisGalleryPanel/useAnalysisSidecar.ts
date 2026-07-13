// Data hook for the analysis gallery: loads the sidecar for the active file and
// exposes the parsed reports plus reload/remove. Mirrors useDiagramSidecar —
// load on file change, never append from the renderer.
//
// Path assumes: src/components/MarkdownEditor/AnalysisGalleryPanel/useAnalysisSidecar.ts

import { useCallback, useEffect, useState } from 'react'
import { readSidecar, removeAnalysis } from './analysisSidecar'
import type { AnalysisEntry, AnalysisSidecar } from '../analysisTypes'

export interface UseAnalysisSidecar {
  sidecar: AnalysisSidecar | null
  analyses: AnalysisEntry[]
  loading: boolean
  /** Re-read the sidecar from disk (call after an analyze run completes). */
  reload: () => void
  /** Remove one report by id; resolves to the count remaining. */
  remove: (id: string) => Promise<number>
}

export function useAnalysisSidecar(filePath: string | null): UseAnalysisSidecar {
  const [sidecar, setSidecar] = useState<AnalysisSidecar | null>(null)
  const [loading, setLoading] = useState(false)

  const reload = useCallback(() => {
    if (!filePath) {
      setSidecar(null)
      return
    }
    let active = true
    setLoading(true)
    void readSidecar(filePath).then((s) => {
      if (!active) return
      setSidecar(s)
      setLoading(false)
    })
    return () => {
      active = false
    }
  }, [filePath])

  useEffect(() => reload(), [reload])

  const remove = useCallback(
    async (id: string): Promise<number> => {
      if (!filePath) return 0
      const next = await removeAnalysis(filePath, id)
      setSidecar(next)
      return next?.analyses.length ?? 0
    },
    [filePath],
  )

  return { sidecar, analyses: sidecar?.analyses ?? [], loading, reload, remove }
}
