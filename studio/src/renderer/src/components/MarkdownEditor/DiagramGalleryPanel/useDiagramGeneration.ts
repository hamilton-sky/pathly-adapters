// Panel-local diagram generation: owns the CLI + preset selection (seeded from the
// persisted keys, editable via the gear modal) and the spawn-hook instance, and exposes
// generate-by-preset / by-style / run-once helpers. Keeps DiagramGalleryPanel presentational.

import { useCallback, useState } from 'react'
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
import { sidecarPathFor, type DiagramEntry } from '../diagramTypes'

export function useDiagramGeneration(mdEditorPath: string | null) {
  const [peekOpen, setPeekOpen] = useState(false)
  const [localCli, setLocalCli] = useState<EditorCli>(() => loadEditorCli(CLI_KEY_DIAGRAM))
  const [localPreset, setLocalPreset] = useState<string>(() => loadPreset(PRESET_KEY_DIAGRAM))
  const { handleDiagram } = useEditorDiagramAction(mdEditorPath, null, () => {}, localCli, localPreset)

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
    changeCli,
    changePreset,
  }
}
