// Spawn hook for the Diagram action — a focused clone of the AI-Analyze branch in
// useEditorAgentActions.ts. The run itself (terminal tab, spawn, sidecar polling, gallery
// hand-off) is startDiagramRun in ./diagramRun, shared with HQ's diagram_artifact action;
// this hook adds the React parts: the open file, the one-shot prompt and the preset choice.

import { useCallback } from 'react'
import { useOneShotReconcile } from './useOneShotReconcile'
import { useTerminalStore } from '../../../../store/terminalStore'
import { useUiStore } from '../../../../store/uiStore'
import { useToastStore } from '../../../../store/toastStore'
import type { EditorCli } from '../editorCli'
import { resolveDiagramPrompt, startDiagramRun } from './diagramRun'

export function useEditorDiagramAction(
  mdEditorPath: string | null,
  diagramOncePrompt: string | null,
  onDiagramOnceUsed: () => void,
  diagramCli: EditorCli,
  selectedPreset: string,
) {
  const setMdEditorAction = useUiStore((s) => s.setMdEditorAction)
  // Reload-resilient liveness reconcile — re-verify a persisted 'running' diagram slot against
  // the live gate engines (which survive a reload, unlike terminalStore.tabs) and clear if gone.
  useOneShotReconcile(mdEditorPath, 'diagram')

  const handleDiagram = useCallback(
    async (promptOverride?: string) => {
      const forFile = mdEditorPath
      if (!forFile) return
      const prompt = resolveDiagramPrompt(promptOverride ?? diagramOncePrompt, selectedPreset, forFile)
      if ((await startDiagramRun(forFile, prompt, diagramCli)) === 'launched') onDiagramOnceUsed()
    },
    [mdEditorPath, diagramOncePrompt, onDiagramOnceUsed, selectedPreset, diagramCli],
  )

  const stopDiagram = useCallback(() => {
    const forFile = mdEditorPath
    if (!forFile) return
    const tabId = useUiStore.getState().mdEditorActions[forFile]?.diagram?.tabId
    if (!tabId) return
    void window.pathly.terminal.kill(tabId)
    useTerminalStore.getState().updateTabStatus(tabId, 'done')
    useTerminalStore.getState().closeTab(tabId)
    setMdEditorAction(forFile, 'diagram', null)
    const fileName = forFile.replace(/\\/g, '/').split('/').pop() ?? 'file'
    useToastStore.getState().push(`Diagram stopped · ${fileName}`, 'info', { category: 'phase_summary' })
  }, [mdEditorPath, setMdEditorAction])

  return { handleDiagram, stopDiagram }
}
