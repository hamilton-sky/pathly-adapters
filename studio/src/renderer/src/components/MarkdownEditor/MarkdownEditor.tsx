import React from 'react'
import { Sparkles, ChevronsUp, Plus, Copy, Undo2, PanelRightOpen } from 'lucide-react'
import { Tooltip } from '../ui'
import { useUiStore } from '../../store/uiStore'
import styles from './MarkdownEditor.module.css'
import EditorHeader, { NotebookViewMode } from './EditorHeader/EditorHeader'
import EditorCanvas from './EditorCanvas/EditorCanvas'
import PreviewPanel from './PreviewPanel/PreviewPanel'
import EditorLanding from './EditorLanding/EditorLanding'
import AnalysisPanel from './AnalysisPanel/AnalysisPanel'
import { Editor } from '../Editor'
import { usePreviewResize } from './usePreviewResize'

export default function MarkdownEditorPanel() {
  const notebookPath = useUiStore((s) => s.notebookPath)
  const viewMode = useUiStore((s) => s.notebookViewMode)
  const setViewMode = useUiStore((s) => s.setNotebookViewMode)
  const previewOpen = useUiStore((s) => s.notebookPreviewOpen)
  const togglePreview = useUiStore((s) => s.toggleNotebookPreview)
  const preview = usePreviewResize()

  if (!notebookPath) {
    return <EditorLanding />
  }

  return (
    <div className={styles.root}>
      <AnalysisPanel />
      <EditorHeader
        viewMode={viewMode}
        onToggleViewMode={() => setViewMode(viewMode === 'cells' ? 'editor' : 'cells')}
      />

      {viewMode === 'editor' ? (
        /* Source view — Editor in embedded mode; EditorHeader owns the action bar */
        <div className={styles.editorWrapper}>
          <Editor path={notebookPath} embedded />
        </div>
      ) : (
        /* Notebook cells + live preview panel */
        <>
          <div className={styles.body}>
            <EditorCanvas />
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
            <span className={styles.legendItem}><ChevronsUp size={12} /><b>⌘↑/↓</b> to move cells</span>
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
