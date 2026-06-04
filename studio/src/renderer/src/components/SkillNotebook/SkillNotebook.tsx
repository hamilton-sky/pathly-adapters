import React from 'react'
import styles from './SkillNotebook.module.css'
import NotebookCanvas from './NotebookCanvas/NotebookCanvas'

export default function SkillNotebookPanel() {
  return (
    <div className={styles.root}>
      <NotebookCanvas />
      <div className={styles.resizeHandle} />
      <div className={styles.previewPlaceholder}>
        Preview — Conv 4
      </div>
    </div>
  )
}
