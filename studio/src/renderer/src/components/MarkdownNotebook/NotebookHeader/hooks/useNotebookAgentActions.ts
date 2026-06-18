import { useState, useCallback, useRef, useEffect } from 'react'
import { useTerminalStore } from '../../../../store/terminalStore'
import { useUiStore } from '../../../../store/uiStore'
import type { TerminalTab } from '../../../../store/terminalStore'
import { useToastStore } from '../../../../store/toastStore'
import { buildSplitPrompt, buildAnalyzePrompt, getSpawnCwd, getEffectivePrompt, STORAGE_KEY_SPLIT, STORAGE_KEY_ANALYZE } from '../../../Editor/commentUtils'
import { buildCliArgv, cliLabel, NotebookCli } from '../notebookCli'
import { attachProgress, ActionProgress } from '../notebookProgress'

const toast = (msg: string, variant: 'info' | 'success' | 'error', category: 'phase_summary' | 'agent_done') =>
  useToastStore.getState().push(msg, variant, { category })

type ActionState = 'idle' | 'running' | 'success' | 'error'

async function pollForFile(path: string): Promise<boolean> {
  for (let i = 0; i < 5; i++) {
    if (i > 0) await new Promise<void>((r) => setTimeout(r, 600))
    const content = await window.pathly.fs.read(path)
    if (content != null && content !== '') return true
  }
  return false
}

export function useNotebookAgentActions(
  notebookPath: string | null,
  splitOncePrompt: string | null,
  analyzeOncePrompt: string | null,
  onSplitOnceUsed: () => void,
  onAnalyzeOnceUsed: () => void,
  splitCli: NotebookCli,
  analyzeCli: NotebookCli,
) {
  const addTab  = useTerminalStore((s) => s.addTab)
  const openTab = useTerminalStore((s) => s.openTab)
  const setNotebookDraftPath     = useUiStore((s) => s.setNotebookDraftPath)
  const setNotebookAnalysisPath  = useUiStore((s) => s.setNotebookAnalysisPath)
  const setNotebookViewMode = useUiStore((s) => s.setNotebookViewMode)

  const [splitState,   setSplitState]   = useState<ActionState>('idle')
  const [analyzeState, setAnalyzeState] = useState<ActionState>('idle')
  const [splitProgress,   setSplitProgress]   = useState<ActionProgress | null>(null)
  const [analyzeProgress, setAnalyzeProgress] = useState<ActionProgress | null>(null)

  // Active PTY tab per action, and whether the current exit was a user-initiated stop.
  const splitTabRef       = useRef<string | null>(null)
  const analyzeTabRef     = useRef<string | null>(null)
  const splitStoppingRef   = useRef(false)
  const analyzeStoppingRef = useRef(false)

  // Each file has its own inline state — reset when navigating, then restore if a run is active
  useEffect(() => {
    // Always reset first so a run on file-A never bleeds into file-B's indicator
    setSplitState('idle')
    setAnalyzeState('idle')
    splitTabRef.current = null
    analyzeTabRef.current = null

    if (!notebookPath) return
    const stored = useUiStore.getState().notebookActiveTabs[notebookPath]
    if (stored?.split) {
      const tab = useTerminalStore.getState().tabs.find(t => t.id === stored.split)
      if (tab?.status === 'running') {
        splitTabRef.current = stored.split
        setSplitState('running')
      }
    }
    if (stored?.analyze) {
      const tab = useTerminalStore.getState().tabs.find(t => t.id === stored.analyze)
      if (tab?.status === 'running') {
        analyzeTabRef.current = stored.analyze
        setAnalyzeState('running')
      }
    }
  }, [notebookPath])

  const handleSplit = useCallback(async () => {
    if (!notebookPath || splitState === 'running') return
    setSplitState('running')
    onSplitOnceUsed()
    const draftPath = notebookPath + '.draft'
    const norm = notebookPath.replace(/\\/g, '/')
    const fileName = norm.split('/').pop() ?? 'skill'
    const tabId = `split-${Date.now().toString(36)}`
    splitTabRef.current = tabId
    useUiStore.getState().setNotebookActiveTab(notebookPath, 'split', tabId)
    const prompt = splitOncePrompt ?? getEffectivePrompt(buildSplitPrompt, STORAGE_KEY_SPLIT, notebookPath)
    addTab(tabId, `Split · ${fileName}`, 'left', splitCli as TerminalTab['kind'], undefined, undefined, prompt)
    openTab(tabId)
    toast(`AI Split started · ${fileName} (${cliLabel(splitCli)})`, 'info', 'phase_summary')
    const stopProgress = attachProgress(tabId, setSplitProgress, (line) => toast(`Split: ${line}`, 'info', 'phase_summary'))
    const unsubscribe = window.pathly.terminal.onExit((exitedTabId: string) => {
      if (exitedTabId !== tabId) return
      unsubscribe()
      stopProgress()
      setSplitProgress(null)
      splitTabRef.current = null
      if (splitStoppingRef.current) {
        splitStoppingRef.current = false
        useTerminalStore.getState().updateTabStatus(tabId, 'done')
        useTerminalStore.getState().closeTab(tabId)
        useUiStore.getState().setNotebookActiveTab(notebookPath, 'split', null)
        setSplitState('idle')
        toast(`AI Split stopped · ${fileName}`, 'info', 'phase_summary')
        return
      }
      void pollForFile(draftPath).then((found) => {
        if (found) {
          setNotebookDraftPath(draftPath)
          setNotebookViewMode('editor')
          useTerminalStore.getState().updateTabStatus(tabId, 'done')
          useTerminalStore.getState().closeTab(tabId)
          useUiStore.getState().setNotebookActiveTab(notebookPath, 'split', null)
          setSplitState('success')
          toast(`AI Split ready · ${fileName} — review the diff`, 'success', 'agent_done')
          setTimeout(() => setSplitState('idle'), 3000)
        } else {
          useTerminalStore.getState().updateTabStatus(tabId, 'error')
          useTerminalStore.getState().closeTab(tabId)
          useUiStore.getState().setNotebookActiveTab(notebookPath, 'split', null)
          setSplitState('error')
          toast(`AI Split failed · ${fileName} — no draft produced`, 'error', 'agent_done')
          setTimeout(() => setSplitState('idle'), 3000)
        }
      })
    })
    try {
      await window.pathly.terminal.spawn(tabId, getSpawnCwd(notebookPath), undefined, buildCliArgv(splitCli, prompt))
      useTerminalStore.getState().updateTabStatus(tabId, 'running')
    } catch {
      unsubscribe()
      stopProgress()
      setSplitProgress(null)
      useTerminalStore.getState().updateTabStatus(tabId, 'error')
      useTerminalStore.getState().closeTab(tabId)
      useUiStore.getState().setNotebookActiveTab(notebookPath, 'split', null)
      setSplitState('error')
      toast(`AI Split failed · ${fileName} — could not launch ${cliLabel(splitCli)}`, 'error', 'agent_done')
      setTimeout(() => setSplitState('idle'), 3000)
    }
  }, [notebookPath, splitState, splitOncePrompt, onSplitOnceUsed, addTab, openTab, setNotebookDraftPath, setNotebookViewMode, splitCli])

  const handleAnalyze = useCallback(async () => {
    if (!notebookPath || analyzeState === 'running') return
    setAnalyzeState('running')
    onAnalyzeOnceUsed()
    const analysisPath = notebookPath + '.analysis'
    const norm = notebookPath.replace(/\\/g, '/')
    const fileName = norm.split('/').pop() ?? 'skill'
    const tabId = `analyze-${Date.now().toString(36)}`
    analyzeTabRef.current = tabId
    useUiStore.getState().setNotebookActiveTab(notebookPath, 'analyze', tabId)
    const prompt = analyzeOncePrompt ?? getEffectivePrompt(buildAnalyzePrompt, STORAGE_KEY_ANALYZE, notebookPath)
    addTab(tabId, `Analyze · ${fileName}`, 'left', analyzeCli as TerminalTab['kind'], undefined, undefined, prompt)
    openTab(tabId)
    toast(`AI Analyze started · ${fileName} (${cliLabel(analyzeCli)})`, 'info', 'phase_summary')
    const stopProgress = attachProgress(tabId, setAnalyzeProgress, (line) => toast(`Analyze: ${line}`, 'info', 'phase_summary'))
    const unsubscribe = window.pathly.terminal.onExit((exitedTabId: string) => {
      if (exitedTabId !== tabId) return
      unsubscribe()
      stopProgress()
      setAnalyzeProgress(null)
      analyzeTabRef.current = null
      if (analyzeStoppingRef.current) {
        analyzeStoppingRef.current = false
        useTerminalStore.getState().updateTabStatus(tabId, 'done')
        useTerminalStore.getState().closeTab(tabId)
        useUiStore.getState().setNotebookActiveTab(notebookPath, 'analyze', null)
        setAnalyzeState('idle')
        toast(`AI Analyze stopped · ${fileName}`, 'info', 'phase_summary')
        return
      }
      void pollForFile(analysisPath).then((found) => {
        if (found) {
          setNotebookAnalysisPath(analysisPath)
          useTerminalStore.getState().updateTabStatus(tabId, 'done')
          useTerminalStore.getState().closeTab(tabId)
          useUiStore.getState().setNotebookActiveTab(notebookPath, 'analyze', null)
          setAnalyzeState('success')
          toast(`AI Analyze ready · ${fileName} — open the Report`, 'success', 'agent_done')
          setTimeout(() => setAnalyzeState('idle'), 3000)
        } else {
          useTerminalStore.getState().updateTabStatus(tabId, 'error')
          useTerminalStore.getState().closeTab(tabId)
          useUiStore.getState().setNotebookActiveTab(notebookPath, 'analyze', null)
          setAnalyzeState('error')
          toast(`AI Analyze failed · ${fileName} — no report produced`, 'error', 'agent_done')
          setTimeout(() => setAnalyzeState('idle'), 3000)
        }
      })
    })
    try {
      await window.pathly.terminal.spawn(tabId, getSpawnCwd(notebookPath), undefined, buildCliArgv(analyzeCli, prompt))
      useTerminalStore.getState().updateTabStatus(tabId, 'running')
    } catch {
      unsubscribe()
      stopProgress()
      setAnalyzeProgress(null)
      useTerminalStore.getState().updateTabStatus(tabId, 'error')
      useTerminalStore.getState().closeTab(tabId)
      useUiStore.getState().setNotebookActiveTab(notebookPath, 'analyze', null)
      setAnalyzeState('error')
      toast(`AI Analyze failed · ${fileName} — could not launch ${cliLabel(analyzeCli)}`, 'error', 'agent_done')
      setTimeout(() => setAnalyzeState('idle'), 3000)
    }
  }, [notebookPath, analyzeState, analyzeOncePrompt, onAnalyzeOnceUsed, addTab, openTab, setNotebookAnalysisPath, analyzeCli])

  const stopSplit = useCallback(() => {
    const storedId = useUiStore.getState().notebookActiveTabs[notebookPath ?? '']?.split
    const tab = splitTabRef.current ?? storedId ?? null
    if (!tab) return
    splitStoppingRef.current = true
    void window.pathly.terminal.kill(tab)
  }, [notebookPath])

  const stopAnalyze = useCallback(() => {
    const storedId = useUiStore.getState().notebookActiveTabs[notebookPath ?? '']?.analyze
    const tab = analyzeTabRef.current ?? storedId ?? null
    if (!tab) return
    analyzeStoppingRef.current = true
    void window.pathly.terminal.kill(tab)
  }, [notebookPath])

  return { handleSplit, handleAnalyze, stopSplit, stopAnalyze, splitState, analyzeState, splitProgress, analyzeProgress }
}
