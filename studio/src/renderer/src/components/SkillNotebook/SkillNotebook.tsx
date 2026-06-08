import React, { useState } from 'react'
import { ArrowLeft, FileText, BookOpen, Sparkles, ChevronsUp, Plus, Copy, Undo2 } from 'lucide-react'
import { useUiStore } from '../../store/uiStore'
import styles from './SkillNotebook.module.css'
import NotebookHeader, { NotebookViewMode } from './NotebookHeader/NotebookHeader'
import NotebookCanvas from './NotebookCanvas/NotebookCanvas'
import PreviewPanel from './PreviewPanel/PreviewPanel'
import { Editor } from '../Editor'

const STEPS = [
  { icon: ArrowLeft, label: 'Go to FILES in the sidebar', sub: 'Switch to the FILES tab on the left' },
  { icon: FileText, label: 'Click any .md file', sub: 'Skills, agents, templates, plan files…' },
  { icon: Sparkles, label: 'Edit in notebook mode', sub: 'Drag fragments, preview, export' },
]

export default function SkillNotebookPanel() {
  const skillNotebookPath = useUiStore((s) => s.skillNotebookPath)
  const chatOpen = useUiStore((s) => s.chatOpen)
  const [viewMode, setViewMode] = useState<NotebookViewMode>('cells')

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
      <NotebookHeader
        viewMode={viewMode}
        onToggleViewMode={() => setViewMode(m => m === 'cells' ? 'editor' : 'cells')}
      />

      {viewMode === 'editor' ? (
        /* Full editor — raw source view with its own edit/preview/split toggle */
        <div className={styles.editorWrapper}>
          <Editor />
        </div>
      ) : (
        /* Notebook cells + live preview panel */
        <>
          <div className={styles.body}>
            <NotebookCanvas />
            {!chatOpen && <div className={styles.resizeHandle} />}
            <div className={styles.previewWrapper}>
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
        </>
      )}
    </div>
  )
}
