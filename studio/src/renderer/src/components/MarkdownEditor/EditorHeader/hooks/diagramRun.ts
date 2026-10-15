// The Diagram one-shot as a plain function — the body of useEditorDiagramAction's
// handleDiagram, lifted out so HQ's operator (diagram_artifact) can start the SAME
// run for an artifact's file: same terminal tab, spawn gate, model policy, sidecar
// polling and gallery hand-off. The hook keeps the React bits (preset choice, the
// reload reconcile, the one-shot prompt flag).
//
// Relies on the uiStore 'diagram' additions (store/uiStore.ts): the MdEditorActionRecord +
// setMdEditorAction action union, setMdEditorDiagramPath(path, forFile),
// mdEditorDiagramPanelOpen, and selectMdEditorDiagram.

import { useTerminalStore } from '../../../../store/terminalStore'
import { useUiStore } from '../../../../store/uiStore'
import type { TerminalTab } from '../../../../store/terminalStore'
import { useToastStore } from '../../../../store/toastStore'
import { getSpawnCwd, describeAgentFailure } from '../../../Editor/commentUtils'
import { resolvePrompt } from '../../../shared/PromptActionConfig/presetTypes'
import { buildCliArgv, cliLabel, type EditorCli } from '../editorCli'
import { effectiveModel } from '../../../../services/spawnPolicy'
import { featureFromPath } from '../../../../utils/featureFromPath'
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

function vars(filePath: string): Record<string, string> {
  const norm = filePath.replace(/\\/g, '/')
  return { FILE: norm, SIDECAR: sidecarPathFor(norm) }
}

/** Resolve the prompt: explicit one-shot > stored override > selected preset default. */
export function resolveDiagramPrompt(
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

/** The prompt for a requested style (HQ's diagram_artifact): that style's first preset. */
export function diagramPromptForStyle(style: string, filePath: string): string {
  const preset = DIAGRAM_PRESETS.find((p) => p.style === style) ?? DIAGRAM_PRESETS[0]
  return resolvePrompt(preset.prompt, vars(filePath))
}

/** Clear the header slot a few seconds after a run settles, unless a newer run took it. */
function clearIfStill(forFile: string, tabId: string): void {
  const slot = useUiStore.getState().mdEditorActions[forFile]?.diagram
  if (slot && slot.status !== 'running' && slot.tabId === tabId) {
    useUiStore.getState().setMdEditorAction(forFile, 'diagram', null)
  }
}

export type DiagramRunStart = 'launched' | 'busy' | 'cancelled' | 'failed'

/** Start the diagram agent on *forFile* with *prompt*. Resolves once the spawn
 *  is in (not when the diagram lands — that is the gallery's job). */
export async function startDiagramRun(forFile: string, prompt: string, cli: EditorCli): Promise<DiagramRunStart> {
  const ui = useUiStore.getState()
  if (ui.mdEditorActions[forFile]?.diagram?.status === 'running') return 'busy'
  const { setMdEditorAction, setMdEditorDiagramPath } = ui
  const terminal = useTerminalStore.getState()

  const norm = forFile.replace(/\\/g, '/')
  const fileName = norm.split('/').pop() ?? 'file'
  const tabId = `diagram-${Date.now().toString(36)}`

  terminal.addTab(tabId, `Diagram · ${fileName}`, 'left', cli as TerminalTab['kind'], undefined, undefined, prompt)
  terminal.updateTabStatus(tabId, 'running')
  setMdEditorAction(forFile, 'diagram', { status: 'running', tabId, stopping: false })
  terminal.openTab(tabId)
  toast(`Diagram started · ${fileName} (${cliLabel(cli)})`, 'info', 'phase_summary')

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
    const feature = featureFromPath(forFile)
    await window.pathly.terminal.spawn(tabId, getSpawnCwd(forFile), undefined, buildCliArgv(cli, prompt, effectiveModel('diagram', cli)), undefined, {
      telemetry: { scopeTier: feature ? 'feature' : 'project', label: 'ai-diagram', role: 'diagrammer', ...(feature ? { feature } : {}) },
    })
    return 'launched'
  } catch (e) {
    unsubscribe()
    const slot = useUiStore.getState().mdEditorActions[forFile]?.diagram
    if ((e instanceof Error && /cancelled/i.test(e.message)) || !slot || slot.tabId !== tabId) {
      useTerminalStore.getState().closeTab(tabId)
      setMdEditorAction(forFile, 'diagram', null)
      return 'cancelled'
    }
    useTerminalStore.getState().updateTabStatus(tabId, 'error')
    useTerminalStore.getState().closeTab(tabId)
    setMdEditorAction(forFile, 'diagram', { status: 'error', tabId, stopping: false })
    toast(`Diagram failed · ${fileName} — could not launch ${cliLabel(cli)}`, 'error', 'agent_done')
    setTimeout(() => clearIfStill(forFile, tabId), 3000)
    return 'failed'
  }
}
