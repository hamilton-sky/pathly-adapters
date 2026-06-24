import { useCallback, useEffect } from 'react'
import { useTerminalStore } from '../../../../store/terminalStore'
import { useUiStore } from '../../../../store/uiStore'
import type { TerminalTab } from '../../../../store/terminalStore'
import { useToastStore } from '../../../../store/toastStore'
import { buildSplitPrompt, buildAnalyzePrompt, getSpawnCwd, getEffectivePrompt, STORAGE_KEY_SPLIT, STORAGE_KEY_ANALYZE, describeAgentFailure } from '../../../Editor/commentUtils'
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

// All run state lives in uiStore.mdEditorActions, keyed by the file that started the run.
// This hook is a single shared instance (EditorHeader does not remount on navigation),
// so it MUST NOT hold any per-run React state — every read/write is keyed by the captured
// `forFile`, so a run completing while the user is on another file never touches the visible
// file's pill. The header derives the visible file's state via selectMdEditorSplit/Analyze.
export function useEditorAgentActions(
  mdEditorPath: string | null,
  splitOncePrompt: string | null,
  analyzeOncePrompt: string | null,
  onSplitOnceUsed: () => void,
  onAnalyzeOnceUsed: () => void,
  splitCli: EditorCli,
  analyzeCli: EditorCli,
) {
  const addTab  = useTerminalStore((s) => s.addTab)
  const openTab = useTerminalStore((s) => s.openTab)
  const setMdEditorSplitDraftPath = useUiStore((s) => s.setMdEditorSplitDraftPath)
  const setMdEditorAnalysisPath  = useUiStore((s) => s.setMdEditorAnalysisPath)
  const setMdEditorViewMode      = useUiStore((s) => s.setMdEditorViewMode)
  const setMdEditorAction        = useUiStore((s) => s.setMdEditorAction)
  // Subscribe to the tab list so the reconciliation effect below re-runs on add/remove.
  const tabs = useTerminalStore((s) => s.tabs)

  // Stale-run reconciliation: if the visible file has a slot still marked 'running' but its
  // terminal tab has vanished (closed manually, or a backend exit we never received), reset it
  // so the pill can't spin forever. Zero false positives — a healthy run keeps its tab in the
  // store until onExit closes it, and completed runs are status 'success'/'error', not 'running'.
  useEffect(() => {
    if (!mdEditorPath) return
    const slots = useUiStore.getState().mdEditorActions[mdEditorPath]
    if (!slots) return
    ;(['split', 'analyze'] as const).forEach((action) => {
      const slot = slots[action]
      if (slot?.status === 'running' && slot.tabId && !tabs.some((t) => t.id === slot.tabId)) {
        setMdEditorAction(mdEditorPath, action, null)
      }
    })
  }, [mdEditorPath, tabs, setMdEditorAction])

  // Clear a slot back to idle, but only if it still holds the transient state we set —
  // never clobber a newer run that started on the same file in the meantime.
  const clearIfStill = useCallback(
    (forFile: string, action: 'split' | 'analyze', tabId: string) => {
      const slot = useUiStore.getState().mdEditorActions[forFile]?.[action]
      // Only clear if THIS exact run still owns the slot — a newer run (running or completed)
      // carries a different tabId, so its terminal success/error is never wiped early.
      if (slot && slot.status !== 'running' && slot.tabId === tabId) setMdEditorAction(forFile, action, null)
    },
    [setMdEditorAction],
  )

  const handleSplit = useCallback(async (promptOverride?: string) => {
    const forFile = mdEditorPath
    if (!forFile) return
    if (useUiStore.getState().mdEditorActions[forFile]?.split?.status === 'running') return
    const draftPath = forFile + '.split.draft'
    const norm = forFile.replace(/\\/g, '/')
    const fileName = norm.split('/').pop() ?? 'skill'
    const tabId = `split-${Date.now().toString(36)}`
    const prompt = promptOverride ?? splitOncePrompt ?? getEffectivePrompt(buildSplitPrompt, STORAGE_KEY_SPLIT, forFile)
    addTab(tabId, `Split · ${fileName}`, 'left', splitCli as TerminalTab['kind'], undefined, undefined, prompt)
    // Optimistic running BEFORE the spawn await so startedAt is stamped at t0 (the elapsed
    // timer derives from tab.startedAt) and a quick navigate-away-and-back restores the pill.
    useTerminalStore.getState().updateTabStatus(tabId, 'running')
    setMdEditorAction(forFile, 'split', { status: 'running', tabId, stopping: false })
    openTab(tabId)
    toast(`AI Split started · ${fileName} (${cliLabel(splitCli)})`, 'info', 'phase_summary')
    // attachProgress drives only the milestone toasts now; the pill's timer is derived from
    // tab.startedAt in the header, so we discard the per-tick progress payload.
    const stopProgress = attachProgress(tabId, () => {}, (line) => toast(`Split: ${line}`, 'info', 'phase_summary'))
    const unsubscribe = window.pathly.terminal.onExit((exitedTabId: string, exitCode?: number, tail?: string) => {
      if (exitedTabId !== tabId) return
      unsubscribe()
      stopProgress()
      // If this run's slot is gone or replaced — e.g. the user hit Stop, which closes the tab
      // and clears the slot synchronously — this exit was already handled. No-op.
      const live = useUiStore.getState().mdEditorActions[forFile]?.split
      if (!live || live.tabId !== tabId) return
      void pollForFile(draftPath).then((found) => {
        if (found) {
          setMdEditorSplitDraftPath(draftPath, forFile)
          if (useUiStore.getState().mdEditorPath === forFile) setMdEditorViewMode('editor')
          useTerminalStore.getState().updateTabStatus(tabId, 'done')
          useTerminalStore.getState().closeTab(tabId)
          setMdEditorAction(forFile, 'split', { status: 'success', tabId, stopping: false })
          toast(`AI Split ready · ${fileName} — review the diff`, 'success', 'agent_done')
          setTimeout(() => clearIfStill(forFile, 'split', tabId), 3000)
        } else {
          useTerminalStore.getState().updateTabStatus(tabId, 'error')
          useTerminalStore.getState().closeTab(tabId)
          setMdEditorAction(forFile, 'split', { status: 'error', tabId, stopping: false })
          toast(describeAgentFailure('AI Split', fileName, exitCode, tail), 'error', 'agent_done')
          setTimeout(() => clearIfStill(forFile, 'split', tabId), 3000)
        }
      })
    })
    try {
      await window.pathly.terminal.spawn(tabId, getSpawnCwd(forFile), undefined, buildCliArgv(splitCli, prompt))
      onSplitOnceUsed()
    } catch (e) {
      unsubscribe()
      stopProgress()
      const slot = useUiStore.getState().mdEditorActions[forFile]?.split
      if ((e instanceof Error && /cancelled/i.test(e.message)) || !slot || slot.tabId !== tabId) {
        // Cancelled from the queue (or already finalized) — clean up quietly, no error toast.
        useTerminalStore.getState().closeTab(tabId)
        setMdEditorAction(forFile, 'split', null)
        return
      }
      useTerminalStore.getState().updateTabStatus(tabId, 'error')
      useTerminalStore.getState().closeTab(tabId)
      setMdEditorAction(forFile, 'split', { status: 'error', tabId, stopping: false })
      toast(`AI Split failed · ${fileName} — could not launch ${cliLabel(splitCli)}`, 'error', 'agent_done')
      setTimeout(() => clearIfStill(forFile, 'split', tabId), 3000)
    }
  }, [mdEditorPath, splitOncePrompt, onSplitOnceUsed, addTab, openTab, setMdEditorSplitDraftPath, setMdEditorViewMode, setMdEditorAction, clearIfStill, splitCli])

  const handleAnalyze = useCallback(async (promptOverride?: string) => {
    const forFile = mdEditorPath
    if (!forFile) return
    if (useUiStore.getState().mdEditorActions[forFile]?.analyze?.status === 'running') return
    const analysisPath = forFile + '.analysis'
    const norm = forFile.replace(/\\/g, '/')
    const fileName = norm.split('/').pop() ?? 'skill'
    const tabId = `analyze-${Date.now().toString(36)}`
    const prompt = promptOverride ?? analyzeOncePrompt ?? getEffectivePrompt(buildAnalyzePrompt, STORAGE_KEY_ANALYZE, forFile)
    addTab(tabId, `Analyze · ${fileName}`, 'left', analyzeCli as TerminalTab['kind'], undefined, undefined, prompt)
    useTerminalStore.getState().updateTabStatus(tabId, 'running')
    setMdEditorAction(forFile, 'analyze', { status: 'running', tabId, stopping: false })
    openTab(tabId)
    toast(`AI Analyze started · ${fileName} (${cliLabel(analyzeCli)})`, 'info', 'phase_summary')
    const stopProgress = attachProgress(tabId, () => {}, (line) => toast(`Analyze: ${line}`, 'info', 'phase_summary'))
    const unsubscribe = window.pathly.terminal.onExit((exitedTabId: string, exitCode?: number, tail?: string) => {
      if (exitedTabId !== tabId) return
      unsubscribe()
      stopProgress()
      // If this run's slot is gone or replaced (e.g. the user hit Stop), it was already handled. No-op.
      const live = useUiStore.getState().mdEditorActions[forFile]?.analyze
      if (!live || live.tabId !== tabId) return
      void pollForFile(analysisPath).then((found) => {
        if (found) {
          setMdEditorAnalysisPath(analysisPath, forFile)
          useTerminalStore.getState().updateTabStatus(tabId, 'done')
          useTerminalStore.getState().closeTab(tabId)
          setMdEditorAction(forFile, 'analyze', { status: 'success', tabId, stopping: false })
          toast(`AI Analyze ready · ${fileName} — open the Report`, 'success', 'agent_done')
          setTimeout(() => clearIfStill(forFile, 'analyze', tabId), 3000)
        } else {
          useTerminalStore.getState().updateTabStatus(tabId, 'error')
          useTerminalStore.getState().closeTab(tabId)
          setMdEditorAction(forFile, 'analyze', { status: 'error', tabId, stopping: false })
          toast(describeAgentFailure('AI Analyze', fileName, exitCode, tail), 'error', 'agent_done')
          setTimeout(() => clearIfStill(forFile, 'analyze', tabId), 3000)
        }
      })
    })
    try {
      await window.pathly.terminal.spawn(tabId, getSpawnCwd(forFile), undefined, buildCliArgv(analyzeCli, prompt))
      onAnalyzeOnceUsed()
    } catch (e) {
      unsubscribe()
      stopProgress()
      const slot = useUiStore.getState().mdEditorActions[forFile]?.analyze
      if ((e instanceof Error && /cancelled/i.test(e.message)) || !slot || slot.tabId !== tabId) {
        // Cancelled from the queue (or already finalized) — clean up quietly, no error toast.
        useTerminalStore.getState().closeTab(tabId)
        setMdEditorAction(forFile, 'analyze', null)
        return
      }
      useTerminalStore.getState().updateTabStatus(tabId, 'error')
      useTerminalStore.getState().closeTab(tabId)
      setMdEditorAction(forFile, 'analyze', { status: 'error', tabId, stopping: false })
      toast(`AI Analyze failed · ${fileName} — could not launch ${cliLabel(analyzeCli)}`, 'error', 'agent_done')
      setTimeout(() => clearIfStill(forFile, 'analyze', tabId), 3000)
    }
  }, [mdEditorPath, analyzeOncePrompt, onAnalyzeOnceUsed, addTab, openTab, setMdEditorAnalysisPath, setMdEditorAction, clearIfStill, analyzeCli])

  // Stop closes the tab IMMEDIATELY (like the terminal's own close button) rather than waiting
  // for onExit — a force-killed PTY (taskkill /T /F) may never deliver a clean exit event.
  // Clearing the slot makes the run's onExit a no-op if it does fire later.
  const stopRun = useCallback((forFile: string | null, action: 'split' | 'analyze', label: string) => {
    if (!forFile) return
    const tabId = useUiStore.getState().mdEditorActions[forFile]?.[action]?.tabId
    if (!tabId) return
    void window.pathly.terminal.kill(tabId)
    useTerminalStore.getState().updateTabStatus(tabId, 'done')
    useTerminalStore.getState().closeTab(tabId)
    setMdEditorAction(forFile, action, null)
    const fileName = forFile.replace(/\\/g, '/').split('/').pop() ?? 'file'
    toast(`${label} stopped · ${fileName}`, 'info', 'phase_summary')
  }, [setMdEditorAction])

  const stopSplit   = useCallback(() => stopRun(mdEditorPath, 'split', 'AI Split'),    [mdEditorPath, stopRun])
  const stopAnalyze = useCallback(() => stopRun(mdEditorPath, 'analyze', 'AI Analyze'), [mdEditorPath, stopRun])

  return { handleSplit, handleAnalyze, stopSplit, stopAnalyze }
}
