import React, { useState } from 'react'
import {
  ArrowLeft, Undo2, Redo2, Database, Download, FileCode,
} from 'lucide-react'
import { useSkillNotebookStore } from '../../../store/skillNotebookStore'
import { useUiStore } from '../../../store/uiStore'
import styles from './NotebookHeader.module.css'

export type NotebookViewMode = 'cells' | 'editor'

interface Props {
  viewMode: NotebookViewMode
  onToggleViewMode: () => void
}

export default function NotebookHeader({ viewMode, onToggleViewMode }: Props) {
  const { undo, redo, cells, historyIndex, history } = useSkillNotebookStore()
  const skillNotebookPath = useUiStore(s => s.skillNotebookPath)
  const setSkillNotebookPath = useUiStore(s => s.setSkillNotebookPath)
  const [exportState, setExportState] = useState<'idle' | 'success' | 'error'>('idle')

  const canUndo = historyIndex > 0
  const canRedo = historyIndex < history.length - 1

  const pathParts = skillNotebookPath ? skillNotebookPath.replace(/\\/g, '/').split('/') : []
  const skillName = pathParts[pathParts.length - 1]?.replace('.md', '') ?? ''
  const category = pathParts[pathParts.length - 2] ?? ''

  const handleExport = async () => {
    const fragmentOrder = cells
      .filter(c => c.type === 'fragment')
      .map(c => (c as any).fragmentName as string)
    const skillKey = skillNotebookPath
      ? skillNotebookPath.replace(/\\/g, '/').replace(/^.*core\/skills\//, '').replace('.md', '')
      : 'unknown'
    try {
      const res = await fetch('http://localhost:8765/skills/export', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill: skillKey, fragment_order: fragmentOrder }),
      })
      if (res.ok) {
        setExportState('success')
        setTimeout(() => setExportState('idle'), 2000)
      } else {
        setExportState('error')
        setTimeout(() => setExportState('idle'), 3000)
      }
    } catch {
      setExportState('error')
      setTimeout(() => setExportState('idle'), 3000)
    }
  }

  const handleSave = async () => {
    try { await fetch('http://localhost:8765/health') } catch {}
  }

  return (
    <div className={styles.headerRoot}>
      <button
        type="button"
        className={styles.backBtn}
        onClick={() => setSkillNotebookPath(null)}
        aria-label="Back"
      >
        <ArrowLeft size={16} />
      </button>

      <div className={styles.breadcrumb}>
        <span className={styles.breadcrumbText}>Skills › {category} › {skillName}</span>
      </div>

      <span className={styles.badge}>NOTEBOOK</span>

      <div className={styles.spacer} />

      {/* Only show undo/redo and save/export in cells mode */}
      {viewMode === 'cells' && (
        <>
          <button
            type="button"
            className={styles.iconBtn}
            onClick={undo}
            disabled={!canUndo}
            title="Undo"
            aria-label="Undo"
          >
            <Undo2 size={15} />
          </button>
          <button
            type="button"
            className={styles.iconBtn}
            onClick={redo}
            disabled={!canRedo}
            title="Redo"
            aria-label="Redo"
          >
            <Redo2 size={15} />
          </button>
          <button type="button" className={styles.saveBtn} onClick={handleSave}>
            <Database size={13} />
            Save
          </button>
          <button
            type="button"
            className={`${styles.exportBtn} ${exportState === 'success' ? styles.exportSuccess : exportState === 'error' ? styles.exportError : ''}`}
            onClick={handleExport}
            disabled={exportState !== 'idle'}
          >
            <Download size={13} />
            {exportState === 'success' ? 'Exported' : exportState === 'error' ? 'Error' : 'Export Skill'}
          </button>
        </>
      )}

      {/* Mode toggle — cells ↔ raw editor */}
      <button
        type="button"
        className={`${styles.modeToggleBtn} ${viewMode === 'editor' ? styles.modeToggleActive : ''}`}
        title={viewMode === 'editor' ? 'Back to notebook view' : 'View as editor (raw source)'}
        aria-label={viewMode === 'editor' ? 'Notebook view' : 'Editor view'}
        onClick={onToggleViewMode}
      >
        <FileCode size={15} />
        <span>{viewMode === 'editor' ? 'Notebook' : 'Editor'}</span>
      </button>
    </div>
  )
}
