// Data hook for the gallery: loads the diagram sidecar for the active file and
// exposes the parsed diagrams plus reload/remove. Mirrors how AnalysisPanel
// reads its report file — load on file change, never append from the renderer.
//
// Path assumes: src/components/MarkdownEditor/DiagramGalleryPanel/useDiagramSidecar.ts

import { useCallback, useEffect, useState } from 'react'
import { readSidecar, removeDiagram } from './diagramSidecar'
import type { DiagramEntry, DiagramSidecar } from '../diagramTypes'

export interface UseDiagramSidecar {
  sidecar: DiagramSidecar | null
  diagrams: DiagramEntry[]
  loading: boolean
  /** Re-read the sidecar from disk (call after a generate run completes). */
  reload: () => void
  /** Remove one diagram by id; resolves to the count remaining. */
  remove: (id: string) => Promise<number>
}

export function useDiagramSidecar(filePath: string | null): UseDiagramSidecar {
  const [sidecar, setSidecar] = useState<DiagramSidecar | null>(null)
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
      const next = await removeDiagram(filePath, id)
      setSidecar(next)
      return next?.diagrams.length ?? 0
    },
    [filePath],
  )

  return { sidecar, diagrams: sidecar?.diagrams ?? [], loading, reload, remove }
}
