// Spawn hook for the Diagram action — a focused clone of the AI-Analyze branch in
// useEditorAgentActions.ts. It launches the agent in a terminal tab, polls the
// sidecar until it parses with >= 1 diagram, then opens the gallery panel.
//
// Relies on the uiStore 'diagram' additions (store/uiStore.ts): the MdEditorActionRecord +
// setMdEditorAction action union, setMdEditorDiagramPath(path, forFile),
// mdEditorDiagramPanelOpen, and selectMdEditorDiagram.

import { useCallback } from 'react'
import { useOneShotReconcile } from './useOneShotReconcile'
import { useTerminalStore } from '../../../../store/terminalStore'
import { useUiStore } from '../../../../store/uiStore'
import type { TerminalTab } from '../../../../store/terminalStore'
import { useToastStore } from '../../../../store/toastStore'
import { getSpawnCwd, describeAgentFailure } from '../../../Editor/commentUtils'
import { resolvePrompt } from '../../../shared/PromptActionConfig/presetTypes'
import { buildCliArgv, cliLabel, type EditorCli } from '../editorCli'
import { effectiveModel } from '../../../../services/spawnPolicy'
import { DIAGRAM_PRESETS, STORAGE_KEY_DIAGRAM } from '../diagramPresets'
import { sidecarPathFor } from '../../diagramTypes'
import { readSidecar } from '../../DiagramGalleryPanel/diagramSidecar'

const toast = (
  msg: string,
  variant: 'info' | 'success' | 'error',
  category: 'phase_summary' | 'agent_done',
) => useToastStore.getState().push(msg, variant, { category })

/** Poll the sidecar up to 5×600ms; resolve true once it parses with >= 1 diagram. */
async function pollForDiagram(filePath: string): Promise<boolean> {
  for (let i = 0; i < 5; i++) {
    if (i > 0) await new Promise<void>((r) => setTimeout(r, 600))
    const sidecar = await readSidecar(filePath)
    if (sidecar && sidecar.diagrams.length > 0) return true
  }
  return false
}

/** Resolve the prompt: explicit one-shot > stored override > selected preset default. */
function resolveDiagramPrompt(
  once: string | null | undefined,
  selectedPreset: string,
  filePath: string,
): string {
  // An edited one-shot prompt may still carry {{FILE}}/{{SIDECAR}} tokens (the peek modal
  // only pre-substitutes FILE), so always run it back through resolvePrompt.
  if (once) return resolvePrompt(once, vars(filePath))
  try {
    const stored = localStorage.getItem(STORAGE_KEY_DIAGRAM)
    if (stored) return resolvePrompt(stored, vars(filePath))
  } catch {
    /* ignore */
  }
  const preset = DIAGRAM_PRESETS.find((p) => p.name === selectedPreset) ?? DIAGRAM_PRESETS[0]
  return resolvePrompt(preset.prompt, vars(filePath))
}

function vars(filePath: string): Record<string, string> {
  const norm = filePath.replace(/\\/g, '/')
  return { FILE: norm, SIDECAR: sidecarPathFor(norm) }
}

export function useEditorDiagramAction(
  mdEditorPath: string | null,
  diagramOncePrompt: string | null,
  onDiagramOnceUsed: () => void,
  diagramCli: EditorCli,
  selectedPreset: string,
) {
  const addTab = useTerminalStore((s) => s.addTab)
  const openTab = useTerminalStore((s) => s.openTab)
  const setMdEditorAction = useUiStore((s) => s.setMdEditorAction)
  const setMdEditorDiagramPath = useUiStore((s) => s.setMdEditorDiagramPath)
  // Reload-resilient liveness reconcile — re-verify a persisted 'running' diagram slot against
  // the live gate engines (which survive a reload, unlike terminalStore.tabs) and clear if gone.
  useOneShotReconcile(mdEditorPath, 'diagram')

  const clearIfStill = useCallback(
    (forFile: string, tabId: string) => {
      const slot = useUiStore.getState().mdEditorActions[forFile]?.diagram
      if (slot && slot.status !== 'running' && slot.tabId === tabId) {
        setMdEditorAction(forFile, 'diagram', null)
      }
    },
    [setMdEditorAction],
  )

  const handleDiagram = useCallback(
    async (promptOverride?: string) => {
      const forFile = mdEditorPath
      if (!forFile) return
      if (useUiStore.getState().mdEditorActions[forFile]?.diagram?.status === 'running') return

      const norm = forFile.replace(/\\/g, '/')
      const fileName = norm.split('/').pop() ?? 'file'
      const tabId = `diagram-${Date.now().toString(36)}`
      const prompt = resolveDiagramPrompt(promptOverride ?? diagramOncePrompt, selectedPreset, forFile)

      addTab(tabId, `Diagram · ${fileName}`, 'left', diagramCli as TerminalTab['kind'], undefined, undefined, prompt)
      useTerminalStore.getState().updateTabStatus(tabId, 'running')
      setMdEditorAction(forFile, 'diagram', { status: 'running', tabId, stopping: false })
      openTab(tabId)
      toast(`Diagram started · ${fileName} (${cliLabel(diagramCli)})`, 'info', 'phase_summary')

      const unsubscribe = window.pathly.terminal.onExit(
        (exitedTabId: string, exitCode?: number, tail?: string) => {
          if (exitedTabId !== tabId) return
          unsubscribe()
          const live = useUiStore.getState().mdEditorActions[forFile]?.diagram
          if (!live || live.tabId !== tabId) return
          void pollForDiagram(forFile).then((ok) => {
            if (ok) {
              // Setting the path opens the gallery automatically when forFile is visible
              // (the store's setMdEditorDiagramPath flips mdEditorDiagramPanelOpen).
              setMdEditorDiagramPath(sidecarPathFor(forFile), forFile)
              // Keep the terminal tab (do NOT closeTab) so the agent's output stays inspectable —
              // the diagram lands in the gallery, but the raw run is still viewable in the terminal.
              useTerminalStore.getState().updateTabStatus(tabId, 'done')
              setMdEditorAction(forFile, 'diagram', { status: 'success', tabId, stopping: false })
              toast(`Diagram ready · ${fileName}`, 'success', 'agent_done')
              setTimeout(() => clearIfStill(forFile, tabId), 3000)
            } else {
              // Keep the tab on failure too, so the error output is inspectable.
              useTerminalStore.getState().updateTabStatus(tabId, 'error')
              setMdEditorAction(forFile, 'diagram', { status: 'error', tabId, stopping: false })
              toast(describeAgentFailure('Diagram', fileName, exitCode, tail), 'error', 'agent_done')
              setTimeout(() => clearIfStill(forFile, tabId), 3000)
            }
          })
        },
      )

      try {
        await window.pathly.terminal.spawn(tabId, getSpawnCwd(forFile), undefined, buildCliArgv(diagramCli, prompt, effectiveModel('diagram', diagramCli)), undefined, {
          telemetry: { scopeTier: 'project', label: 'ai-diagram', role: 'diagrammer' },
        })
        onDiagramOnceUsed()
      } catch (e) {
        unsubscribe()
        const slot = useUiStore.getState().mdEditorActions[forFile]?.diagram
        if ((e instanceof Error && /cancelled/i.test(e.message)) || !slot || slot.tabId !== tabId) {
          useTerminalStore.getState().closeTab(tabId)
          setMdEditorAction(forFile, 'diagram', null)
          return
        }
        useTerminalStore.getState().updateTabStatus(tabId, 'error')
        useTerminalStore.getState().closeTab(tabId)
        setMdEditorAction(forFile, 'diagram', { status: 'error', tabId, stopping: false })
        toast(`Diagram failed · ${fileName} — could not launch ${cliLabel(diagramCli)}`, 'error', 'agent_done')
        setTimeout(() => clearIfStill(forFile, tabId), 3000)
      }
    },
    [mdEditorPath, diagramOncePrompt, selectedPreset, diagramCli, addTab, openTab, setMdEditorAction, setMdEditorDiagramPath, clearIfStill],
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
    toast(`Diagram stopped · ${fileName}`, 'info', 'phase_summary')
  }, [mdEditorPath, setMdEditorAction])

  return { handleDiagram, stopDiagram }
}
