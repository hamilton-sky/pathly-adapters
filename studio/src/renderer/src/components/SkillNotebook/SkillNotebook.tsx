import React from 'react'
import styles from './SkillNotebook.module.css'
import NotebookHeader from './NotebookHeader/NotebookHeader'
import NotebookCanvas from './NotebookCanvas/NotebookCanvas'
import PreviewPanel from './PreviewPanel/PreviewPanel'

export default function SkillNotebookPanel() {
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
