import React, { useState } from 'react'
import { ArrowLeft, FileText, BookOpen, Sparkles, ChevronsUp, Plus, Copy, Undo2 } from 'lucide-react'
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
        {viewMode === 'cells' && <NotebookCatalog />}
        {viewMode === 'cells' && <NotebookCanvas />}
        {viewMode === 'cells' && !chatOpen && <div className={styles.resizeHandle} />}
        <div className={viewMode === 'preview' ? styles.previewWrapperFull : styles.previewWrapper}>
          <PreviewPanel />
        </div>
      </div>
      <div className={styles.legend}>
        <span className={styles.legendItem}><ChevronsUp size={12} /><b>Drag a cell or ⌘↑/↓</b> to move cells</span>
        <span className={styles.legendItem}><Plus size={12} /><b>Insert</b> a new cell, or drag from the catalog</span>
        <span className={styles.legendItem}><Copy size={12} /><b>⋯ menu</b> — duplicate · convert · delete</span>
        <span className={styles.legendItem}><Sparkles size={12} /><b>Select text</b> → new cell from selection</span>
        <span className={styles.legendItem}><Undo2 size={12} /><b>Undo / redo</b> — 50 steps</span>
      </div>
    </div>
  )
}
