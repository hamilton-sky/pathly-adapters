import React, { useState } from 'react'
import { ArrowLeft, FileText, BookOpen, Sparkles } from 'lucide-react'
import { useUiStore } from '../../store/uiStore'
import styles from './SkillNotebook.module.css'
import NotebookHeader from './NotebookHeader/NotebookHeader'
import NotebookCanvas from './NotebookCanvas/NotebookCanvas'
import NotebookCatalog from './NotebookCatalog/NotebookCatalog'
import PreviewPanel from './PreviewPanel/PreviewPanel'

const STEPS = [
  { icon: ArrowLeft, label: 'Go to FILES in the sidebar', sub: 'Switch to the FILES tab on the left' },
  { icon: FileText, label: 'Click a skill .md file', sub: 'Any skill in your project' },
  { icon: Sparkles, label: 'Edit in notebook mode', sub: 'Drag fragments, preview, export' },
]

type ViewMode = 'cells' | 'preview'

export default function SkillNotebookPanel() {
  const skillNotebookPath = useUiStore((s) => s.skillNotebookPath)
  const chatOpen = useUiStore((s) => s.chatOpen)
  const [viewMode, setViewMode] = useState<ViewMode>('cells')

  if (!skillNotebookPath) {
    return (
      <div className={styles.empty}>
        <div className={styles.emptyArrow}>
          <ArrowLeft size={28} />
        </div>
        <BookOpen size={28} className={styles.emptyIcon} />
        <p className={styles.emptyTitle}>Open a skill to get started</p>
        <ol className={styles.emptySteps}>
          {STEPS.map(({ icon: Icon, label, sub }, i) => (
            <li key={i} className={styles.emptyStep}>
              <span className={styles.emptyStepNum}>{i + 1}</span>
              <Icon size={15} className={styles.emptyStepIcon} />
              <span className={styles.emptyStepText}>
                <strong>{label}</strong>
                <span>{sub}</span>
              </span>
            </li>
          ))}
        </ol>
      </div>
    )
  }

  return (
    <div className={styles.root}>
      <NotebookHeader viewMode={viewMode} onViewModeChange={setViewMode} />
      <div className={styles.body}>
        <NotebookCatalog />
        <NotebookCanvas />
        {!chatOpen && (
          <>
            <div className={styles.resizeHandle} />
            <div className={styles.previewWrapper}>
              <PreviewPanel />
            </div>
          </>
        )}
      </div>
    </div>
  )
}
