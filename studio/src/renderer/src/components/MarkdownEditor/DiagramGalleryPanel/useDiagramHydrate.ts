// On file open, light up the diagram Gallery chip if the file already has saved diagrams.
// The in-memory mdEditorDiagramPaths map (which gates the chip + panel) isn't persisted, so a
// reopened file would otherwise show nothing until a regenerate repopulated it. This reads the
// on-disk `<file>.diagrams.json` and hydrates the path WITHOUT opening the panel (open:false).

import { useEffect } from 'react'
import { useUiStore } from '../../../store/uiStore'
import { readSidecar } from './diagramSidecar'
import { sidecarPathFor } from '../diagramTypes'

export function useDiagramHydrate(filePath: string | null): void {
  const setDiagramPath = useUiStore((s) => s.setMdEditorDiagramPath)

  useEffect(() => {
    if (!filePath) return
    let active = true
    void readSidecar(filePath).then((s) => {
      if (!active || !s || s.diagrams.length === 0) return
      setDiagramPath(sidecarPathFor(filePath), filePath, { open: false })
    })
    return () => {
      active = false
    }
  }, [filePath, setDiagramPath])
}
