import React, { useState } from 'react'
import { useToastStore } from '../../../store/toastStore'
import {
  ArrowLeft, Undo2, Redo2, Database, Download, FileCode,
} from 'lucide-react'
import { Tooltip } from '../../ui'
import { useSkillNotebookStore, BodyCell } from '../../../store/skillNotebookStore'
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
  const [saveState, setSaveState] = useState<'idle' | 'success' | 'error'>('idle')

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
    const bodyCells = cells
      .filter(c => c.type === 'body')
      .map(c => ({ heading: (c as BodyCell).heading, content: (c as BodyCell).content }))
    try {
      const res = await fetch('http://localhost:8765/skills/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill_path: skillNotebookPath, body_cells: bodyCells }),
      })
      if (res.ok) {
        setSaveState('success')
        useToastStore.getState().push('Skill saved', 'success', { category: 'db_crud' })
        setTimeout(() => setSaveState('idle'), 2000)
      } else {
        setSaveState('error')
        useToastStore.getState().push('Save failed — server error', 'error', { category: 'db_crud' })
        setTimeout(() => setSaveState('idle'), 3000)
      }
    } catch {
      setSaveState('error')
      useToastStore.getState().push('Save failed — server unreachable', 'error', { category: 'db_crud' })
      setTimeout(() => setSaveState('idle'), 3000)
    }
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
        <span className={styles.breadcrumbText}>Skills â€º {category} â€º {skillName}</span>
      </div>

      <span className={styles.badge}>NOTEBOOK</span>

      <div className={styles.spacer} />

      {/* Only show undo/redo and save/export in cells mode */}
      {viewMode === 'cells' && (
        <>
          <Tooltip label="Undo" shortcut="Ctrl+Z" placement="bottom">
            <button
              type="button"
              className={styles.iconBtn}
              onClick={undo}
              disabled={!canUndo}
              aria-label="Undo"
            >
              <Undo2 size={15} />
            </button>
          </Tooltip>
          <Tooltip label="Redo" shortcut="Ctrl+Shift+Z" placement="bottom">
            <button
              type="button"
              className={styles.iconBtn}
              onClick={redo}
              disabled={!canRedo}
              aria-label="Redo"
            >
              <Redo2 size={15} />
            </button>
          </Tooltip>
          <button
            type="button"
            className={`${styles.saveBtn} ${saveState === 'success' ? styles.saveSuccess : saveState === 'error' ? styles.saveError : ''}`}
            onClick={handleSave}
            disabled={saveState !== 'idle'}
          >
            <Database size={15} />
            {saveState === 'success' ? 'Saved' : saveState === 'error' ? 'Error' : 'Save'}
          </button>
          <button
            type="button"
            className={`${styles.exportBtn} ${exportState === 'success' ? styles.exportSuccess : exportState === 'error' ? styles.exportError : ''}`}
            onClick={handleExport}
            disabled={exportState !== 'idle'}
          >
            <Download size={15} />
            {exportState === 'success' ? 'Exported' : exportState === 'error' ? 'Error' : 'Export Skill'}
          </button>
        </>
      )}

      {/* Mode toggle — cells ↔ raw editor */}
      <Tooltip label={viewMode === 'editor' ? 'Back to notebook view' : 'View as editor (raw source)'} placement="bottom">
        <button
          type="button"
          className={`${styles.modeToggleBtn} ${viewMode === 'editor' ? styles.modeToggleActive : ''}`}
          aria-label={viewMode === 'editor' ? 'Notebook view' : 'Editor view'}
          onClick={onToggleViewMode}
        >
          <FileCode size={15} />
          <span>{viewMode === 'editor' ? 'Notebook' : 'Editor'}</span>
        </button>
      </Tooltip>
    </div>
  )
}
