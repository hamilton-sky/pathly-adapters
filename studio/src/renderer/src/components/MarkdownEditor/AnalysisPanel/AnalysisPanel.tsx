import React, { useEffect, useState } from 'react'
import { X, RefreshCw, FileCode, Trash2 } from 'lucide-react'
import { useUiStore, selectMdEditorAnalysisPath } from '../../../store/uiStore'
import { MarkdownPreview } from '../../Editor/MarkdownPreview'
import styles from './AnalysisPanel.module.css'

export default function AnalysisPanel() {
  const analysisPath    = useUiStore(selectMdEditorAnalysisPath)
  const setAnalysisPath = useUiStore((s) => s.setMdEditorAnalysisPath)
  const panelOpen       = useUiStore((s) => s.mdEditorAnalysisPanelOpen)
  const setPanelOpen    = useUiStore((s) => s.setMdEditorAnalysisPanelOpen)
  const setMdEditorPath     = useUiStore((s) => s.setMdEditorPath)
  const setMdEditorViewMode = useUiStore((s) => s.setMdEditorViewMode)

  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(false)

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
  )
}
