import { useState, useCallback } from 'react'
import { useTerminalStore } from '../../../../store/terminalStore'
import { useUiStore } from '../../../../store/uiStore'
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

  const handleSplit = useCallback(async () => {
    if (!notebookPath || splitState === 'running') return
    setSplitState('running')
    onSplitOnceUsed()
    const draftPath = notebookPath + '.draft'
    const norm = notebookPath.replace(/\\/g, '/')
    const fileName = norm.split('/').pop() ?? 'skill'
    const tabId = `split-${Date.now().toString(36)}`
    addTab(tabId, `Split · ${fileName}`)
    openTab(tabId)
    toast(`AI Split started · ${fileName} (${cliLabel(splitCli)})`, 'info', 'phase_summary')
    const stopProgress = attachProgress(tabId, setSplitProgress, (line) => toast(`Split: ${line}`, 'info', 'phase_summary'))
    const unsubscribe = window.pathly.terminal.onExit((exitedTabId: string) => {
      if (exitedTabId !== tabId) return
      unsubscribe()
      stopProgress()
      setSplitProgress(null)
      void pollForFile(draftPath).then((found) => {
        if (found) {
          setNotebookDraftPath(draftPath)
          setNotebookViewMode('editor')
          setSplitState('success')
          toast(`AI Split ready · ${fileName} — review the diff`, 'success', 'agent_done')
          setTimeout(() => setSplitState('idle'), 3000)
        } else {
          setSplitState('error')
          toast(`AI Split failed · ${fileName} — no draft produced`, 'error', 'agent_done')
          setTimeout(() => setSplitState('idle'), 3000)
        }
      })
    })
    const prompt = splitOncePrompt ?? getEffectivePrompt(buildSplitPrompt, STORAGE_KEY_SPLIT, notebookPath)
    try {
      await window.pathly.terminal.spawn(tabId, getSpawnCwd(notebookPath), undefined, buildCliArgv(splitCli, prompt))
    } catch {
      unsubscribe()
      stopProgress()
      setSplitProgress(null)
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
    addTab(tabId, `Analyze · ${fileName}`)
    openTab(tabId)
    toast(`AI Analyze started · ${fileName} (${cliLabel(analyzeCli)})`, 'info', 'phase_summary')
    const stopProgress = attachProgress(tabId, setAnalyzeProgress, (line) => toast(`Analyze: ${line}`, 'info', 'phase_summary'))
    const unsubscribe = window.pathly.terminal.onExit((exitedTabId: string) => {
      if (exitedTabId !== tabId) return
      unsubscribe()
      stopProgress()
      setAnalyzeProgress(null)
      void pollForFile(analysisPath).then((found) => {
        if (found) {
          setNotebookAnalysisPath(analysisPath)
          setAnalyzeState('success')
          toast(`AI Analyze ready · ${fileName} — open the Report`, 'success', 'agent_done')
          setTimeout(() => setAnalyzeState('idle'), 3000)
        } else {
          setAnalyzeState('error')
          toast(`AI Analyze failed · ${fileName} — no report produced`, 'error', 'agent_done')
          setTimeout(() => setAnalyzeState('idle'), 3000)
        }
      })
    })
    const prompt = analyzeOncePrompt ?? getEffectivePrompt(buildAnalyzePrompt, STORAGE_KEY_ANALYZE, notebookPath)
    try {
      await window.pathly.terminal.spawn(tabId, getSpawnCwd(notebookPath), undefined, buildCliArgv(analyzeCli, prompt))
    } catch {
      unsubscribe()
      stopProgress()
      setAnalyzeProgress(null)
      setAnalyzeState('error')
      toast(`AI Analyze failed · ${fileName} — could not launch ${cliLabel(analyzeCli)}`, 'error', 'agent_done')
      setTimeout(() => setAnalyzeState('idle'), 3000)
    }
  }, [notebookPath, analyzeState, analyzeOncePrompt, onAnalyzeOnceUsed, addTab, openTab, setNotebookAnalysisPath, analyzeCli])

  return { handleSplit, handleAnalyze, splitState, analyzeState, splitProgress, analyzeProgress }
}
