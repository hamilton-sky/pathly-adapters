import React from 'react'
import { BookOpen } from 'lucide-react'
import { useUiStore } from '../../store/uiStore'
import styles from './SkillNotebook.module.css'
import NotebookHeader from './NotebookHeader/NotebookHeader'
import NotebookCanvas from './NotebookCanvas/NotebookCanvas'
import PreviewPanel from './PreviewPanel/PreviewPanel'

export default function SkillNotebookPanel() {
  const skillNotebookPath = useUiStore((s) => s.skillNotebookPath)

  if (!skillNotebookPath) {
    return (
      <div className={styles.empty}>
        <BookOpen size={32} className={styles.emptyIcon} />
        <p className={styles.emptyTitle}>No skill open</p>
        <p className={styles.emptyHint}>Click a skill <code>.md</code> file in the sidebar to open it here.</p>
      </div>
    )
  }

  return (
    <div className={styles.root}>
      <NotebookHeader />
      <div className={styles.body}>
        <NotebookCanvas />
        <div className={styles.resizeHandle} />
        <div className={styles.previewWrapper}>
          <PreviewPanel />
        </div>
      </div>
    </div>
  )
}
