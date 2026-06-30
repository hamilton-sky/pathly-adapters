// Panel-local diagram actions: owns the CLI + preset selection (seeded from the persisted
// keys, editable via the gear modal) and the spawn-hook instance; exposes generate-by-preset
// / by-style / run-once helpers plus "add to board" (user-triggered, renderer-side — the
// agent never posts). Keeps DiagramGalleryPanel presentational.

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useEditorDiagramAction } from '../EditorHeader/hooks/useEditorDiagramAction'
import {
  loadEditorCli,
  loadPreset,
  saveEditorCli,
  savePreset,
  type EditorCli,
} from '../EditorHeader/editorCli'
import { DIAGRAM_PRESETS, CLI_KEY_DIAGRAM, PRESET_KEY_DIAGRAM } from '../EditorHeader/diagramPresets'
import { resolvePrompt } from '../../shared/PromptActionConfig/presetTypes'
import { useToastStore } from '../../../store/toastStore'
import { useCommsStore } from '../../../store/commsStore'
import { useProjectStore } from '../../../store/projectStore'
import { sidecarPathFor, type DiagramEntry } from '../diagramTypes'
import { buildBoardTargets } from '../boardTargets'
import type { BoardTarget } from '../../shared/AddToBoardButton/AddToBoardButton'
import { addDiagramToBoard } from './addDiagramToBoard'
import { markDiagramOnBoard } from './diagramSidecar'

export function useDiagramGeneration(mdEditorPath: string | null) {
  const [peekOpen, setPeekOpen] = useState(false)
  const [localCli, setLocalCli] = useState<EditorCli>(() => loadEditorCli(CLI_KEY_DIAGRAM))
  const [localPreset, setLocalPreset] = useState<string>(() => loadPreset(PRESET_KEY_DIAGRAM))
  const { handleDiagram, stopDiagram } = useEditorDiagramAction(mdEditorPath, null, () => {}, localCli, localPreset)

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

  const fromPreset = useCallback(
    (name: string) => {
      if (!mdEditorPath) return
      const preset = DIAGRAM_PRESETS.find((p) => p.name === name) ?? DIAGRAM_PRESETS[0]
      const norm = mdEditorPath.replace(/\\/g, '/')
      void handleDiagram(resolvePrompt(preset.prompt, { FILE: norm, SIDECAR: sidecarPathFor(norm) }))
    },
    [mdEditorPath, handleDiagram],
  )

  // Regenerate only knows the card's style; pick the first preset of that style.
  const fromStyle = useCallback(
    (style: DiagramEntry['style']) => {
      const preset = DIAGRAM_PRESETS.find((p) => p.style === style) ?? DIAGRAM_PRESETS[0]
      fromPreset(preset.name)
    },
    [fromPreset],
  )

  const runOnce = useCallback(
    (prompt: string) => {
      setPeekOpen(false)
      void handleDiagram(prompt)
    },
    [handleDiagram],
  )

  // Post one diagram to the board (copy — the card stays). Persists the marker so it
  // survives reload. Returns true on success so the caller can refresh the cards.
  const addToBoard = useCallback(
    async (entry: DiagramEntry, target?: BoardTarget): Promise<boolean> => {
      if (!mdEditorPath) return false
      const id = await addDiagramToBoard(mdEditorPath, entry, target)
      if (id) {
        await markDiagramOnBoard(mdEditorPath, entry.id, { id, at: new Date().toISOString() })
        useToastStore
          .getState()
          .push(`Added to board · ${entry.title || entry.style}`, 'success', { category: 'agent_done' })
        return true
      }
      useToastStore.getState().push('Could not add to board', 'error', { category: 'agent_done' })
      return false
    },
    [mdEditorPath],
  )

  const changeCli = useCallback((c: EditorCli) => {
    setLocalCli(c)
    saveEditorCli(CLI_KEY_DIAGRAM, c)
  }, [])

  const changePreset = useCallback((name: string) => {
    setLocalPreset(name)
    savePreset(PRESET_KEY_DIAGRAM, name)
  }, [])

  return {
    peekOpen,
    setPeekOpen,
    localCli,
    localPreset,
    fromPreset,
    fromStyle,
    runOnce,
    addToBoard,
    boardTargets,
    stopDiagram,
    changeCli,
    changePreset,
  }
}
