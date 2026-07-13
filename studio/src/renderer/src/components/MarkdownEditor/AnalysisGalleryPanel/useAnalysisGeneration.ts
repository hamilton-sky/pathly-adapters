// Panel-local analysis actions: owns the CLI + lens selection (seeded from the persisted
// keys, editable via the gear modal) and the spawn-hook instance; exposes generate-by-lens
// / run-once helpers plus "add to board" (user-triggered, renderer-side — the agent never
// posts). Keeps AnalysisGalleryPanel presentational. Mirrors useDiagramGeneration.

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useEditorAnalysisAction } from '../EditorHeader/hooks/useEditorAnalysisAction'
import {
  loadEditorCli,
  loadPreset,
  saveEditorCli,
  savePreset,
  CLI_KEY_ANALYZE,
  PRESET_KEY_ANALYZE,
  type EditorCli,
} from '../EditorHeader/editorCli'
import { ANALYZE_LENSES } from '../EditorHeader/actionPresets'
import { resolvePrompt } from '../../shared/PromptActionConfig/presetTypes'
import { useToastStore } from '../../../store/toastStore'
import { useCommsStore } from '../../../store/commsStore'
import { useProjectStore } from '../../../store/projectStore'
import { analysisSidecarPathFor, type AnalysisEntry } from '../analysisTypes'
import { buildBoardTargets } from '../boardTargets'
import type { BoardTarget } from '../../shared/AddToBoardButton/AddToBoardButton'
import { addAnalysisToBoard } from './addAnalysisToBoard'
import { markAnalysisOnBoard } from './analysisSidecar'

export function useAnalysisGeneration(mdEditorPath: string | null) {
  const [peekOpen, setPeekOpen] = useState(false)
  const [localCli, setLocalCli] = useState<EditorCli>(() => loadEditorCli(CLI_KEY_ANALYZE))
  const [localPreset, setLocalPreset] = useState<string>(() => loadPreset(PRESET_KEY_ANALYZE))
  const { handleAnalyze, stopAnalyze } = useEditorAnalysisAction(mdEditorPath, null, () => {}, localCli, localPreset)

  // Board-target list for the "Add to board" dropdown (Global / Project / each feature, with
  // the path-derived board marked "suggested"). Lazy-load the feature list if it's empty.
  const features = useCommsStore((s) => s.features)
  const loadFeatures = useCommsStore((s) => s.loadFeatures)
  const projectPath = useProjectStore((s) => s.projectPath)

  useEffect(() => {
    if (projectPath && features.length === 0) void loadFeatures(projectPath)
  }, [projectPath, features.length, loadFeatures])

  const boardTargets = useMemo(
    () => (mdEditorPath ? buildBoardTargets(mdEditorPath, features.map((f) => f.id), projectPath) : []),
    [mdEditorPath, features, projectPath],
  )

  const fromLens = useCallback(
    (name: string) => {
      if (!mdEditorPath) return
      const preset = ANALYZE_LENSES.find((p) => p.name === name) ?? ANALYZE_LENSES[0]
      const norm = mdEditorPath.replace(/\\/g, '/')
      void handleAnalyze(resolvePrompt(preset.prompt, { FILE: norm, SIDECAR: analysisSidecarPathFor(norm) }))
    },
    [mdEditorPath, handleAnalyze],
  )

  const runOnce = useCallback(
    (prompt: string) => {
      setPeekOpen(false)
      void handleAnalyze(prompt)
    },
    [handleAnalyze],
  )

  // Post one report to the board (copy — the card stays). Persists the marker so it
  // survives reload. Returns true on success so the caller can refresh the cards.
  const addToBoard = useCallback(
    async (entry: AnalysisEntry, target?: BoardTarget): Promise<boolean> => {
      if (!mdEditorPath) return false
      const id = await addAnalysisToBoard(mdEditorPath, entry, target, projectPath)
      if (id) {
        await markAnalysisOnBoard(mdEditorPath, entry.id, { id, at: new Date().toISOString() })
        useToastStore
          .getState()
          .push(`Added to board · ${entry.title || 'report'}`, 'success', { category: 'agent_done' })
        return true
      }
      useToastStore.getState().push('Could not add to board', 'error', { category: 'agent_done' })
      return false
    },
    [mdEditorPath, projectPath],
  )

  const changeCli = useCallback((c: EditorCli) => {
    setLocalCli(c)
    saveEditorCli(CLI_KEY_ANALYZE, c)
  }, [])

  const changePreset = useCallback((name: string) => {
    setLocalPreset(name)
    savePreset(PRESET_KEY_ANALYZE, name)
  }, [])

  return {
    peekOpen,
    setPeekOpen,
    localCli,
    localPreset,
    fromLens,
    runOnce,
    addToBoard,
    boardTargets,
    stopAnalyze,
    changeCli,
    changePreset,
  }
}
