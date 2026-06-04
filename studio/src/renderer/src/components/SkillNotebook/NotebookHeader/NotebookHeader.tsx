import React, { useState } from 'react'
import { Undo2, Redo2 } from 'lucide-react'
import { useSkillNotebookStore } from '../../../store/skillNotebookStore'
import { useUiStore } from '../../../store/uiStore'
import styles from './NotebookHeader.module.css'

export default function NotebookHeader() {
  const { undo, redo, cells, historyIndex, history } = useSkillNotebookStore()
  const skillNotebookPath = useUiStore(s => s.skillNotebookPath)
  const [exportState, setExportState] = useState<'idle' | 'success' | 'error'>('idle')

  const canUndo = historyIndex > 0
  const canRedo = historyIndex < history.length - 1

  const pathParts = skillNotebookPath ? skillNotebookPath.split('/') : []
  const skillName = pathParts[pathParts.length - 1]?.replace('.md', '') ?? ''
  const parentName = pathParts[pathParts.length - 2] ?? ''

  const handleExport = async () => {
    const fragmentOrder = cells
      .filter(c => c.type === 'fragment')
      .map(c => (c as any).fragmentName as string)
    const skillKey = skillNotebookPath
      ? skillNotebookPath.replace(/^.*core\/skills\//, '').replace('.md', '')
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

  const handleValidate = async () => {
    try { await fetch('http://localhost:8765/health') } catch {}
  }

  return (
    <div className={styles.headerRoot}>
      <div className={styles.headerTopRow}>
        <div className={styles.breadcrumb}>
          <span className={styles.breadcrumbMuted}>Skills › {parentName} › </span>
          <span className={styles.skillName}>{skillName}</span>
          <span className={styles.stageBadge}>NOTEBOOK</span>
        </div>
        <div className={styles.actions}>
          <button
            type="button"
            className="pathly-btn-b"
            onClick={undo}
            disabled={!canUndo}
            title="Undo"
          >
            <Undo2 size={13} />
          </button>
          <button
            type="button"
            className="pathly-btn-b"
            onClick={redo}
            disabled={!canRedo}
            title="Redo"
          >
            <Redo2 size={13} />
          </button>
          <div className={styles.divider} />
          <button type="button" className="pathly-btn-b" onClick={handleValidate} title="Validate FSM connection">
            Validate
          </button>
          <button
            type="button"
            className={`${styles.exportBtn} ${exportState === 'success' ? styles.exportSuccess : exportState === 'error' ? styles.exportError : ''}`}
            onClick={handleExport}
            disabled={exportState !== 'idle'}
          >
            {exportState === 'success' ? '✓ Exported' : exportState === 'error' ? 'Error' : 'Export Skill'}
          </button>
        </div>
      </div>
    </div>
  )
}
