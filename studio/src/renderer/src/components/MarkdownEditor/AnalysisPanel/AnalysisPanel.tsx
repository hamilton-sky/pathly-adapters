import React, { useEffect, useMemo, useState } from 'react'
import { X, RefreshCw, FileCode, Trash2 } from 'lucide-react'
import { useUiStore, selectMdEditorAnalysisPath } from '../../../store/uiStore'
import { useToastStore } from '../../../store/toastStore'
import { useCommsStore } from '../../../store/commsStore'
import { useProjectStore } from '../../../store/projectStore'
import { MarkdownPreview } from '../../Editor/MarkdownPreview'
import { publishArtifactToBoard, boardArtifactPath } from '../boardArtifacts'
import { buildBoardTargets } from '../boardTargets'
import AddToBoardButton, { type BoardTarget } from '../../shared/AddToBoardButton/AddToBoardButton'
import styles from './AnalysisPanel.module.css'

export default function AnalysisPanel() {
  const analysisPath    = useUiStore(selectMdEditorAnalysisPath)
  const setAnalysisPath = useUiStore((s) => s.setMdEditorAnalysisPath)
  const panelOpen       = useUiStore((s) => s.mdEditorAnalysisPanelOpen)
  const setPanelOpen    = useUiStore((s) => s.setMdEditorAnalysisPanelOpen)
  const setMdEditorPath     = useUiStore((s) => s.setMdEditorPath)
  const setMdEditorViewMode = useUiStore((s) => s.setMdEditorViewMode)

  const features    = useCommsStore((s) => s.features)
  const loadFeatures = useCommsStore((s) => s.loadFeatures)
  const projectPath = useProjectStore((s) => s.projectPath)

  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [posting, setPosting] = useState(false)

  useEffect(() => {
    if (projectPath && features.length === 0) void loadFeatures(projectPath)
  }, [projectPath, features.length, loadFeatures])

  const targets = useMemo(
    () => (analysisPath ? buildBoardTargets(analysisPath, features.map((f) => f.id), projectPath) : []),
    [analysisPath, features, projectPath],
  )

  useEffect(() => {
    if (!analysisPath) return
    setLoading(true)
    void window.pathly.fs.read(analysisPath).then((c) => {
      setContent(c ?? '')
      setLoading(false)
    })
  }, [analysisPath])

  async function handleDiscard() {
    if (analysisPath) await window.pathly.fs.delete(analysisPath)
    setAnalysisPath(null)
    setPanelOpen(false)
  }

  function handleOpenInEditor() {
    if (!analysisPath) return
    setMdEditorPath(analysisPath)
    setMdEditorViewMode('editor')
    setPanelOpen(false)
  }

  // Move to board: freeze a copy as a board artifact, then clear the report slot so a fresh
  // Analyze can run. The board references the frozen copy, not the (now-cleared) live report.
  // The copy lives in the project-level board-artifacts dir so it survives the source moving.
  async function handleAddToBoard(target: BoardTarget) {
    if (!analysisPath || posting) return
    setPosting(true)
    const norm = analysisPath.replace(/\\/g, '/')
    const name = norm.split('/').pop() ?? 'report'
    const stem = name.replace(/\.[^/.]+$/, '')
    const frozenName = `${stem}.board.${Date.now().toString(36)}.md`
    const frozenPath = boardArtifactPath(projectPath, frozenName) || `${norm}.board.${Date.now().toString(36)}.md`
    const id = await publishArtifactToBoard(analysisPath, frozenPath, content, `Report: ${name}`, 'md', target)
    setPosting(false)
    if (!id) {
      useToastStore.getState().push('Could not add report to board', 'error', { category: 'agent_done' })
      return
    }
    useToastStore.getState().push('Report added to board', 'success', { category: 'agent_done' })
    await window.pathly.fs.delete(analysisPath)
    setAnalysisPath(null)
    setPanelOpen(false)
  }

  if (!analysisPath || !panelOpen) return null

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.title}>Skill Analysis</span>
        <button
          type="button"
          className={styles.closeBtn}
          onClick={() => setPanelOpen(false)}
          aria-label="Close analysis"
        >
          <X size={14} />
        </button>
      </div>
      <div className={styles.body}>
        {loading ? (
          <div className={styles.loading}>
            <RefreshCw size={15} className={styles.spinner} />
            Loading…
          </div>
        ) : (
          <MarkdownPreview content={content} />
        )}
      </div>
      <div className={styles.footer}>
        <AddToBoardButton
          onBoard={false}
          disabled={posting || loading}
          targets={targets}
          onPick={(t) => void handleAddToBoard(t)}
          label={posting ? 'Adding…' : 'Add to board'}
        />
        <div className={styles.footerRight}>
          <button type="button" className={styles.openBtn} onClick={handleOpenInEditor}>
            <FileCode size={12} />
            Open in editor
          </button>
          <button type="button" className={styles.discardBtn} onClick={() => void handleDiscard()}>
            <Trash2 size={12} />
            Discard
          </button>
        </div>
      </div>
    </div>
  )
}
