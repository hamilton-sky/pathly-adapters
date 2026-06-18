import { useCallback, useEffect } from 'react'
import { useTerminalStore } from '../../../../store/terminalStore'
import { useUiStore } from '../../../../store/uiStore'
import type { TerminalTab } from '../../../../store/terminalStore'
import { useToastStore } from '../../../../store/toastStore'
import { buildSplitPrompt, buildAnalyzePrompt, getSpawnCwd, getEffectivePrompt, STORAGE_KEY_SPLIT, STORAGE_KEY_ANALYZE } from '../../../Editor/commentUtils'
import { buildCliArgv, cliLabel, EditorCli } from '../editorCli'
import { attachProgress } from '../editorProgress'

const toast = (msg: string, variant: 'info' | 'success' | 'error', category: 'phase_summary' | 'agent_done') =>
  useToastStore.getState().push(msg, variant, { category })

async function pollForFile(path: string): Promise<boolean> {
  for (let i = 0; i < 5; i++) {
    if (i > 0) await new Promise<void>((r) => setTimeout(r, 600))
    const content = await window.pathly.fs.read(path)
    if (content != null && content !== '') return true
  }
  return false
}

// All run state lives in uiStore.notebookActions, keyed by the file that started the run.
// This hook is a single shared instance (EditorHeader does not remount on navigation),
// so it MUST NOT hold any per-run React state — every read/write is keyed by the captured
// `forFile`, so a run completing while the user is on another file never touches the visible
// file's pill. The header derives the visible file's state via selectNotebookSplit/Analyze.
export function useEditorAgentActions(
  notebookPath: string | null,
  splitOncePrompt: string | null,
  analyzeOncePrompt: string | null,
  onSplitOnceUsed: () => void,
  onAnalyzeOnceUsed: () => void,
  splitCli: EditorCli,
  analyzeCli: EditorCli,
) {
  const addTab  = useTerminalStore((s) => s.addTab)
  const openTab = useTerminalStore((s) => s.openTab)
  const setNotebookDraftPath     = useUiStore((s) => s.setNotebookDraftPath)
  const setNotebookAnalysisPath  = useUiStore((s) => s.setNotebookAnalysisPath)
  const setNotebookViewMode      = useUiStore((s) => s.setNotebookViewMode)
  const setNotebookAction        = useUiStore((s) => s.setNotebookAction)
  // Subscribe to the tab list so the reconciliation effect below re-runs on add/remove.
  const tabs = useTerminalStore((s) => s.tabs)

  // Stale-run reconciliation: if the visible file has a slot still marked 'running' but its
  // terminal tab has vanished (closed manually, or a backend exit we never received), reset it
  // so the pill can't spin forever. Zero false positives — a healthy run keeps its tab in the
  // store until onExit closes it, and completed runs are status 'success'/'error', not 'running'.
  useEffect(() => {
    if (!notebookPath) return
    const slots = useUiStore.getState().notebookActions[notebookPath]
    if (!slots) return
    ;(['split', 'analyze'] as const).forEach((action) => {
      const slot = slots[action]
      if (slot?.status === 'running' && slot.tabId && !tabs.some((t) => t.id === slot.tabId)) {
        setNotebookAction(notebookPath, action, null)
      }
    })
  }, [notebookPath, tabs, setNotebookAction])

  // Clear a slot back to idle, but only if it still holds the transient state we set —
  // never clobber a newer run that started on the same file in the meantime.
  const clearIfStill = useCallback(
    (forFile: string, action: 'split' | 'analyze', tabId: string) => {
      const slot = useUiStore.getState().notebookActions[forFile]?.[action]
      // Only clear if THIS exact run still owns the slot — a newer run (running or completed)
      // carries a different tabId, so its terminal success/error is never wiped early.
      if (slot && slot.status !== 'running' && slot.tabId === tabId) setNotebookAction(forFile, action, null)
    },
    [setNotebookAction],
  )

  const handleSplit = useCallback(async () => {
    const forFile = notebookPath
    if (!forFile) return
    if (useUiStore.getState().notebookActions[forFile]?.split?.status === 'running') return
    const draftPath = forFile + '.draft'
    const norm = forFile.replace(/\\/g, '/')
    const fileName = norm.split('/').pop() ?? 'skill'
    const tabId = `split-${Date.now().toString(36)}`
    const prompt = splitOncePrompt ?? getEffectivePrompt(buildSplitPrompt, STORAGE_KEY_SPLIT, forFile)
    addTab(tabId, `Split · ${fileName}`, 'left', splitCli as TerminalTab['kind'], undefined, undefined, prompt)
    // Optimistic running BEFORE the spawn await so startedAt is stamped at t0 (the elapsed
    // timer derives from tab.startedAt) and a quick navigate-away-and-back restores the pill.
    useTerminalStore.getState().updateTabStatus(tabId, 'running')
    setNotebookAction(forFile, 'split', { status: 'running', tabId, stopping: false })
    openTab(tabId)
    toast(`AI Split started · ${fileName} (${cliLabel(splitCli)})`, 'info', 'phase_summary')
    // attachProgress drives only the milestone toasts now; the pill's timer is derived from
    // tab.startedAt in the header, so we discard the per-tick progress payload.
    const stopProgress = attachProgress(tabId, () => {}, (line) => toast(`Split: ${line}`, 'info', 'phase_summary'))
    const unsubscribe = window.pathly.terminal.onExit((exitedTabId: string) => {
      if (exitedTabId !== tabId) return
      unsubscribe()
      stopProgress()
      const stopping = useUiStore.getState().notebookActions[forFile]?.split?.stopping
      if (stopping) {
        useTerminalStore.getState().updateTabStatus(tabId, 'done')
        useTerminalStore.getState().closeTab(tabId)
        setNotebookAction(forFile, 'split', null)
        toast(`AI Split stopped · ${fileName}`, 'info', 'phase_summary')
        return
      }
      void pollForFile(draftPath).then((found) => {
        if (found) {
          setNotebookDraftPath(draftPath, forFile)
          if (useUiStore.getState().notebookPath === forFile) setNotebookViewMode('editor')
          useTerminalStore.getState().updateTabStatus(tabId, 'done')
          useTerminalStore.getState().closeTab(tabId)
          setNotebookAction(forFile, 'split', { status: 'success', tabId, stopping: false })
          toast(`AI Split ready · ${fileName} — review the diff`, 'success', 'agent_done')
          setTimeout(() => clearIfStill(forFile, 'split', tabId), 3000)
        } else {
          useTerminalStore.getState().updateTabStatus(tabId, 'error')
          useTerminalStore.getState().closeTab(tabId)
          setNotebookAction(forFile, 'split', { status: 'error', tabId, stopping: false })
          toast(`AI Split failed · ${fileName} — no draft produced`, 'error', 'agent_done')
          setTimeout(() => clearIfStill(forFile, 'split', tabId), 3000)
        }
      })
    })
    try {
      await window.pathly.terminal.spawn(tabId, getSpawnCwd(forFile), undefined, buildCliArgv(splitCli, prompt))
      onSplitOnceUsed()
    } catch {
      unsubscribe()
      stopProgress()
      useTerminalStore.getState().updateTabStatus(tabId, 'error')
      useTerminalStore.getState().closeTab(tabId)
      setNotebookAction(forFile, 'split', { status: 'error', tabId, stopping: false })
      toast(`AI Split failed · ${fileName} — could not launch ${cliLabel(splitCli)}`, 'error', 'agent_done')
      setTimeout(() => clearIfStill(forFile, 'split', 'error'), 3000)
    }
  }, [notebookPath, splitOncePrompt, onSplitOnceUsed, addTab, openTab, setNotebookDraftPath, setNotebookViewMode, setNotebookAction, clearIfStill, splitCli])

  const handleAnalyze = useCallback(async () => {
    const forFile = notebookPath
    if (!forFile) return
    if (useUiStore.getState().notebookActions[forFile]?.analyze?.status === 'running') return
    const analysisPath = forFile + '.analysis'
    const norm = forFile.replace(/\\/g, '/')
    const fileName = norm.split('/').pop() ?? 'skill'
    const tabId = `analyze-${Date.now().toString(36)}`
    const prompt = analyzeOncePrompt ?? getEffectivePrompt(buildAnalyzePrompt, STORAGE_KEY_ANALYZE, forFile)
    addTab(tabId, `Analyze · ${fileName}`, 'left', analyzeCli as TerminalTab['kind'], undefined, undefined, prompt)
    useTerminalStore.getState().updateTabStatus(tabId, 'running')
    setNotebookAction(forFile, 'analyze', { status: 'running', tabId, stopping: false })
    openTab(tabId)
    toast(`AI Analyze started · ${fileName} (${cliLabel(analyzeCli)})`, 'info', 'phase_summary')
    const stopProgress = attachProgress(tabId, () => {}, (line) => toast(`Analyze: ${line}`, 'info', 'phase_summary'))
    const unsubscribe = window.pathly.terminal.onExit((exitedTabId: string) => {
      if (exitedTabId !== tabId) return
      unsubscribe()
      stopProgress()
      const stopping = useUiStore.getState().notebookActions[forFile]?.analyze?.stopping
      if (stopping) {
        useTerminalStore.getState().updateTabStatus(tabId, 'done')
        useTerminalStore.getState().closeTab(tabId)
        setNotebookAction(forFile, 'analyze', null)
        toast(`AI Analyze stopped · ${fileName}`, 'info', 'phase_summary')
        return
      }
      void pollForFile(analysisPath).then((found) => {
        if (found) {
          setNotebookAnalysisPath(analysisPath, forFile)
          useTerminalStore.getState().updateTabStatus(tabId, 'done')
          useTerminalStore.getState().closeTab(tabId)
          setNotebookAction(forFile, 'analyze', { status: 'success', tabId, stopping: false })
          toast(`AI Analyze ready · ${fileName} — open the Report`, 'success', 'agent_done')
          setTimeout(() => clearIfStill(forFile, 'analyze', tabId), 3000)
        } else {
          useTerminalStore.getState().updateTabStatus(tabId, 'error')
          useTerminalStore.getState().closeTab(tabId)
          setNotebookAction(forFile, 'analyze', { status: 'error', tabId, stopping: false })
          toast(`AI Analyze failed · ${fileName} — no report produced`, 'error', 'agent_done')
          setTimeout(() => clearIfStill(forFile, 'analyze', tabId), 3000)
        }
      })
    })
    try {
      await window.pathly.terminal.spawn(tabId, getSpawnCwd(forFile), undefined, buildCliArgv(analyzeCli, prompt))
      onAnalyzeOnceUsed()
    } catch {
      unsubscribe()
      stopProgress()
      useTerminalStore.getState().updateTabStatus(tabId, 'error')
      useTerminalStore.getState().closeTab(tabId)
      setNotebookAction(forFile, 'analyze', { status: 'error', tabId, stopping: false })
      toast(`AI Analyze failed · ${fileName} — could not launch ${cliLabel(analyzeCli)}`, 'error', 'agent_done')
      setTimeout(() => clearIfStill(forFile, 'analyze', 'error'), 3000)
    }
  }, [notebookPath, analyzeOncePrompt, onAnalyzeOnceUsed, addTab, openTab, setNotebookAnalysisPath, setNotebookAction, clearIfStill, analyzeCli])

  const stopSplit = useCallback(() => {
    const forFile = notebookPath
    if (!forFile) return
    const tabId = useUiStore.getState().notebookActions[forFile]?.split?.tabId
    if (!tabId) return
    setNotebookAction(forFile, 'split', { stopping: true })
    void window.pathly.terminal.kill(tabId)
  }, [notebookPath, setNotebookAction])

  const stopAnalyze = useCallback(() => {
    const forFile = notebookPath
    if (!forFile) return
    const tabId = useUiStore.getState().notebookActions[forFile]?.analyze?.tabId
    if (!tabId) return
    setNotebookAction(forFile, 'analyze', { stopping: true })
    void window.pathly.terminal.kill(tabId)
  }, [notebookPath, setNotebookAction])

  return { handleSplit, handleAnalyze, stopSplit, stopAnalyze }
}
