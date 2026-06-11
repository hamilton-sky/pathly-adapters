import { useState, useCallback } from 'react'
import { useTerminalStore } from '../../../../store/terminalStore'
import { useUiStore } from '../../../../store/uiStore'
import { buildSplitPrompt, buildAnalyzePrompt, getSpawnCwd, getEffectivePrompt, STORAGE_KEY_SPLIT, STORAGE_KEY_ANALYZE } from '../../../Editor/commentUtils'

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
  skillNotebookPath: string | null,
  splitOncePrompt: string | null,
  analyzeOncePrompt: string | null,
  onSplitOnceUsed: () => void,
  onAnalyzeOnceUsed: () => void,
) {
  const addTab  = useTerminalStore((s) => s.addTab)
  const openTab = useTerminalStore((s) => s.openTab)
  const setNotebookDraftPath     = useUiStore((s) => s.setNotebookDraftPath)
  const setNotebookAnalysisPath  = useUiStore((s) => s.setNotebookAnalysisPath)
  const setSkillNotebookViewMode = useUiStore((s) => s.setSkillNotebookViewMode)

  const [splitState,   setSplitState]   = useState<ActionState>('idle')
  const [analyzeState, setAnalyzeState] = useState<ActionState>('idle')

  const handleSplit = useCallback(async () => {
    if (!skillNotebookPath || splitState === 'running') return
    setSplitState('running')
    onSplitOnceUsed()
    const draftPath = skillNotebookPath + '.draft'
    const norm = skillNotebookPath.replace(/\\/g, '/')
    const fileName = norm.split('/').pop() ?? 'skill'
    const tabId = `split-${Date.now().toString(36)}`
    addTab(tabId, `Split · ${fileName}`)
    openTab(tabId)
    const unsubscribe = window.pathly.terminal.onExit((exitedTabId: string) => {
      if (exitedTabId !== tabId) return
      unsubscribe()
      void pollForFile(draftPath).then((found) => {
        if (found) {
          setNotebookDraftPath(draftPath)
          setSkillNotebookViewMode('editor')
          setSplitState('success')
          setTimeout(() => setSplitState('idle'), 3000)
        } else {
          setSplitState('error')
          setTimeout(() => setSplitState('idle'), 3000)
        }
      })
    })
    const prompt = splitOncePrompt ?? getEffectivePrompt(buildSplitPrompt, STORAGE_KEY_SPLIT, skillNotebookPath)
    await window.pathly.terminal.spawn(tabId, getSpawnCwd(skillNotebookPath), undefined, [
      'claude', '-p', prompt, '--print', '--dangerously-skip-permissions',
    ])
  }, [skillNotebookPath, splitState, splitOncePrompt, onSplitOnceUsed, addTab, openTab, setNotebookDraftPath, setSkillNotebookViewMode])

  const handleAnalyze = useCallback(async () => {
    if (!skillNotebookPath || analyzeState === 'running') return
    setAnalyzeState('running')
    onAnalyzeOnceUsed()
    const analysisPath = skillNotebookPath + '.analysis'
    const norm = skillNotebookPath.replace(/\\/g, '/')
    const fileName = norm.split('/').pop() ?? 'skill'
    const tabId = `analyze-${Date.now().toString(36)}`
    addTab(tabId, `Analyze · ${fileName}`)
    openTab(tabId)
    const unsubscribe = window.pathly.terminal.onExit((exitedTabId: string) => {
      if (exitedTabId !== tabId) return
      unsubscribe()
      void pollForFile(analysisPath).then((found) => {
        if (found) {
          setNotebookAnalysisPath(analysisPath)
          setAnalyzeState('success')
          setTimeout(() => setAnalyzeState('idle'), 3000)
        } else {
          setAnalyzeState('error')
          setTimeout(() => setAnalyzeState('idle'), 3000)
        }
      })
    })
    const prompt = analyzeOncePrompt ?? getEffectivePrompt(buildAnalyzePrompt, STORAGE_KEY_ANALYZE, skillNotebookPath)
    await window.pathly.terminal.spawn(tabId, getSpawnCwd(skillNotebookPath), undefined, [
      'claude', '-p', prompt, '--print', '--dangerously-skip-permissions',
    ])
  }, [skillNotebookPath, analyzeState, analyzeOncePrompt, onAnalyzeOnceUsed, addTab, openTab, setNotebookAnalysisPath])

  return { handleSplit, handleAnalyze, splitState, analyzeState }
}
