// On file open, light up the Reports chip if the file already has saved analyses. The
// in-memory mdEditorAnalysisPaths map (which gates the chip + panel) isn't persisted, so a
// reopened file would otherwise show nothing. This also folds any pre-gallery `<file>.analysis`
// into the array sidecar first, then hydrates the path WITHOUT opening the panel (open:false).
// Mirrors useDiagramHydrate.

import { useEffect } from 'react'
import { useUiStore } from '../../../store/uiStore'
import { readSidecar, migrateLegacyAnalysis } from './analysisSidecar'
import { analysisSidecarPathFor } from '../analysisTypes'

export function useAnalysisHydrate(filePath: string | null): void {
  const setAnalysisPath = useUiStore((s) => s.setMdEditorAnalysisPath)

  useEffect(() => {
    if (!filePath) return
    let active = true
    void (async () => {
      // Best-effort one-time migration of the legacy single-report file.
      await migrateLegacyAnalysis(filePath)
      const s = await readSidecar(filePath)
      if (!active || !s || s.analyses.length === 0) return
      setAnalysisPath(analysisSidecarPathFor(filePath), filePath, { open: false })
    })()
    return () => {
      active = false
    }
  }, [filePath, setAnalysisPath])
}
