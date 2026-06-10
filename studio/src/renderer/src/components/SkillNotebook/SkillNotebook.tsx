import React from 'react'
import { ArrowLeft, FileText, BookOpen, Sparkles, ChevronsUp, Plus, Copy, Undo2, PanelRightOpen } from 'lucide-react'
import { Tooltip } from '../ui'
import { useUiStore } from '../../store/uiStore'
import styles from './SkillNotebook.module.css'
import NotebookHeader, { NotebookViewMode } from './NotebookHeader/NotebookHeader'
import NotebookCanvas from './NotebookCanvas/NotebookCanvas'
import PreviewPanel from './PreviewPanel/PreviewPanel'
import { Editor } from '../Editor'
import { usePreviewResize } from './usePreviewResize'

const STEPS = [
  { icon: ArrowLeft, label: 'Open the Files tab on the left', sub: 'Click the FILES icon in the sidebar' },
  { icon: FileText, label: 'Click any skill .md file', sub: 'Skills, agents, templates…' },
  { icon: Sparkles, label: 'Edit visually or in source', sub: 'Rearrange cells, preview, add comments, export' },
]

export default function SkillNotebookPanel() {
  const skillNotebookPath = useUiStore((s) => s.skillNotebookPath)
  const viewMode = useUiStore((s) => s.skillNotebookViewMode)
  const setViewMode = useUiStore((s) => s.setSkillNotebookViewMode)
  const previewOpen = useUiStore((s) => s.notebookPreviewOpen)
  const togglePreview = useUiStore((s) => s.toggleNotebookPreview)
  const preview = usePreviewResize()

  if (!skillNotebookPath) {
    return (
      <div className={styles.empty}>
        <div className={styles.emptyArrow}>
          <ArrowLeft size={28} />
        </div>
        <BookOpen size={28} className={styles.emptyIcon} />
        <p className={styles.emptyTitle}>No file open — pick one from the Files sidebar</p>
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
        onToggleViewMode={() => setViewMode(viewMode === 'cells' ? 'editor' : 'cells')}
      />

      {viewMode === 'editor' ? (
        /* Source view — Editor in embedded mode; NotebookHeader owns the action bar */
        <div className={styles.editorWrapper}>
          <Editor path={skillNotebookPath} embedded />
        </div>
      ) : (
        /* Notebook cells + live preview panel */
        <>
          <div className={styles.body}>
            <NotebookCanvas />
            {previewOpen ? (
              <>
                <div className={styles.resizeHandle} onMouseDown={preview.onDragStart} />
                <div ref={preview.previewRef} className={styles.previewWrapper}>
                  <PreviewPanel />
                </div>
              </>
            ) : (
              <Tooltip label="Open preview" placement="left">
                <button
                  type="button"
                  className={styles.previewReopenBtn}
                  onClick={togglePreview}
                  aria-label="Open preview"
                >
                  <PanelRightOpen size={14} />
                </button>
              </Tooltip>
            )}
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
