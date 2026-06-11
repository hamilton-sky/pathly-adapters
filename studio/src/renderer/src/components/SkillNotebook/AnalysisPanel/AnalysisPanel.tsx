import React, { useEffect, useState } from 'react'
import { X, RefreshCw } from 'lucide-react'
import { useUiStore } from '../../../store/uiStore'
import { MarkdownPreview } from '../../Editor/MarkdownPreview'
import styles from './AnalysisPanel.module.css'

export default function AnalysisPanel() {
  const analysisPath    = useUiStore((s) => s.notebookAnalysisPath)
  const setAnalysisPath = useUiStore((s) => s.setNotebookAnalysisPath)
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

  async function handleClose() {
    if (analysisPath) await window.pathly.fs.delete(analysisPath)
    setAnalysisPath(null)
  }

  if (!analysisPath) return null

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.title}>Skill Analysis</span>
        <button
          type="button"
          className={styles.closeBtn}
          onClick={() => void handleClose()}
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
    </div>
  )
}
