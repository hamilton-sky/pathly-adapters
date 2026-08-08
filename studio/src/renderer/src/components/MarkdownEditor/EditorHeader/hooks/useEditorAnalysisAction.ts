// Spawn hook for the AI-Analyze action — a focused clone of useEditorDiagramAction.
// It launches the agent in a terminal tab, polls the `.analyses.json` sidecar until it
// parses with >= 1 report, then opens the analysis gallery panel.
//
// Analyze went multi-report (every run APPENDS a report entry, like Diagram), so it no
// longer overwrites a single `.analysis` file and no longer routes through composeClientSkill
// — the lens presets (ANALYZE_LENSES) carry the full append-contract prompt.

import { useCallback } from 'react'
import { useOneShotReconcile } from './useOneShotReconcile'
import { useTerminalStore } from '../../../../store/terminalStore'
import { useUiStore } from '../../../../store/uiStore'
import type { TerminalTab } from '../../../../store/terminalStore'
import { useToastStore } from '../../../../store/toastStore'
import { getSpawnCwd, describeAgentFailure } from '../../../Editor/commentUtils'
import { STORAGE_KEY_ANALYZE } from '../../../Editor/commentUtils'
import { resolvePrompt } from '../../../shared/PromptActionConfig/presetTypes'
import { buildCliArgv, cliLabel, type EditorCli } from '../editorCli'
import { ANALYZE_LENSES } from '../actionPresets'
import { analysisSidecarPathFor } from '../../analysisTypes'
import { readSidecar } from '../../AnalysisGalleryPanel/analysisSidecar'

const toast = (
  msg: string,
  variant: 'info' | 'success' | 'error',
  category: 'phase_summary' | 'agent_done',
) => useToastStore.getState().push(msg, variant, { category })

/** Poll the sidecar up to 5×600ms; resolve true once it parses with >= 1 report. */
async function pollForAnalysis(filePath: string): Promise<boolean> {
  for (let i = 0; i < 5; i++) {
    if (i > 0) await new Promise<void>((r) => setTimeout(r, 600))
    const sidecar = await readSidecar(filePath)
    if (sidecar && sidecar.analyses.length > 0) return true
  }
  return false
}

function vars(filePath: string): Record<string, string> {
  const norm = filePath.replace(/\\/g, '/')
  return { FILE: norm, SIDECAR: analysisSidecarPathFor(norm) }
}

/** Resolve the prompt: explicit one-shot > stored override > selected lens default. */
function resolveAnalysisPrompt(
  once: string | null | undefined,
  selectedPreset: string,
  filePath: string,
): string {
  // An edited one-shot prompt may still carry {{FILE}}/{{SIDECAR}} tokens (the peek modal
  // only pre-substitutes FILE), so always run it back through resolvePrompt.
  if (once) return resolvePrompt(once, vars(filePath))
  try {
    const stored = localStorage.getItem(STORAGE_KEY_ANALYZE)
    if (stored) return resolvePrompt(stored, vars(filePath))
  } catch {
    /* ignore */
  }
  const preset = ANALYZE_LENSES.find((p) => p.name === selectedPreset) ?? ANALYZE_LENSES[0]
  return resolvePrompt(preset.prompt, vars(filePath))
}

export function useEditorAnalysisAction(
  mdEditorPath: string | null,
  analyzeOncePrompt: string | null,
  onAnalyzeOnceUsed: () => void,
  analyzeCli: EditorCli,
  selectedPreset: string,
) {
  const addTab = useTerminalStore((s) => s.addTab)
  const openTab = useTerminalStore((s) => s.openTab)
  const setMdEditorAction = useUiStore((s) => s.setMdEditorAction)
  const setMdEditorAnalysisPath = useUiStore((s) => s.setMdEditorAnalysisPath)
  // Reload-resilient liveness reconcile — re-verify a persisted 'running' analyze slot against
  // the live gate engines (which survive a reload, unlike terminalStore.tabs) and clear if gone.
  useOneShotReconcile(mdEditorPath, 'analyze')

  const clearIfStill = useCallback(
    (forFile: string, tabId: string) => {
      const slot = useUiStore.getState().mdEditorActions[forFile]?.analyze
      if (slot && slot.status !== 'running' && slot.tabId === tabId) {
        setMdEditorAction(forFile, 'analyze', null)
      }
    },
    [setMdEditorAction],
  )

  const handleAnalyze = useCallback(
    async (promptOverride?: string) => {
      const forFile = mdEditorPath
      if (!forFile) return
      if (useUiStore.getState().mdEditorActions[forFile]?.analyze?.status === 'running') return

      const norm = forFile.replace(/\\/g, '/')
      const fileName = norm.split('/').pop() ?? 'file'
      const tabId = `analyze-${Date.now().toString(36)}`
      const prompt = resolveAnalysisPrompt(promptOverride ?? analyzeOncePrompt, selectedPreset, forFile)

      addTab(tabId, `Analyze · ${fileName}`, 'left', analyzeCli as TerminalTab['kind'], undefined, undefined, prompt)
      useTerminalStore.getState().updateTabStatus(tabId, 'running')
      setMdEditorAction(forFile, 'analyze', { status: 'running', tabId, stopping: false })
      openTab(tabId)
      toast(`AI Analyze started · ${fileName} (${cliLabel(analyzeCli)})`, 'info', 'phase_summary')

      const unsubscribe = window.pathly.terminal.onExit(
        (exitedTabId: string, exitCode?: number, tail?: string) => {
          if (exitedTabId !== tabId) return
          unsubscribe()
          const live = useUiStore.getState().mdEditorActions[forFile]?.analyze
          if (!live || live.tabId !== tabId) return
          void pollForAnalysis(forFile).then((ok) => {
            if (ok) {
              // Setting the path opens the gallery automatically when forFile is visible
              // (the store's setMdEditorAnalysisPath flips mdEditorAnalysisPanelOpen).
              setMdEditorAnalysisPath(analysisSidecarPathFor(forFile), forFile)
              useTerminalStore.getState().updateTabStatus(tabId, 'done')
              useTerminalStore.getState().closeTab(tabId)
              setMdEditorAction(forFile, 'analyze', { status: 'success', tabId, stopping: false })
              toast(`AI Analyze ready · ${fileName} — open the Reports`, 'success', 'agent_done')
              setTimeout(() => clearIfStill(forFile, tabId), 3000)
            } else {
              useTerminalStore.getState().updateTabStatus(tabId, 'error')
              useTerminalStore.getState().closeTab(tabId)
              setMdEditorAction(forFile, 'analyze', { status: 'error', tabId, stopping: false })
              toast(describeAgentFailure('AI Analyze', fileName, exitCode, tail), 'error', 'agent_done')
              setTimeout(() => clearIfStill(forFile, tabId), 3000)
            }
          })
        },
      )

      try {
        await window.pathly.terminal.spawn(tabId, getSpawnCwd(forFile), undefined, buildCliArgv(analyzeCli, prompt), undefined, {
          telemetry: { scopeTier: 'project', label: 'ai-analyze', role: 'analyzer' },
        })
        onAnalyzeOnceUsed()
      } catch (e) {
        unsubscribe()
        const slot = useUiStore.getState().mdEditorActions[forFile]?.analyze
        if ((e instanceof Error && /cancelled/i.test(e.message)) || !slot || slot.tabId !== tabId) {
          useTerminalStore.getState().closeTab(tabId)
          setMdEditorAction(forFile, 'analyze', null)
          return
        }
        useTerminalStore.getState().updateTabStatus(tabId, 'error')
        useTerminalStore.getState().closeTab(tabId)
        setMdEditorAction(forFile, 'analyze', { status: 'error', tabId, stopping: false })
        toast(`AI Analyze failed · ${fileName} — could not launch ${cliLabel(analyzeCli)}`, 'error', 'agent_done')
        setTimeout(() => clearIfStill(forFile, tabId), 3000)
      }
    },
    [mdEditorPath, analyzeOncePrompt, selectedPreset, analyzeCli, addTab, openTab, setMdEditorAction, setMdEditorAnalysisPath, clearIfStill],
  )

  const stopAnalyze = useCallback(() => {
    const forFile = mdEditorPath
    if (!forFile) return
    const tabId = useUiStore.getState().mdEditorActions[forFile]?.analyze?.tabId
    if (!tabId) return
    void window.pathly.terminal.kill(tabId)
    useTerminalStore.getState().updateTabStatus(tabId, 'done')
    useTerminalStore.getState().closeTab(tabId)
    setMdEditorAction(forFile, 'analyze', null)
    const fileName = forFile.replace(/\\/g, '/').split('/').pop() ?? 'file'
    toast(`AI Analyze stopped · ${fileName}`, 'info', 'phase_summary')
  }, [mdEditorPath, setMdEditorAction])

  return { handleAnalyze, stopAnalyze }
}
